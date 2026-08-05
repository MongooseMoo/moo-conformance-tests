"""YAML schema for MOO conformance tests.

Defines dataclasses for test suites, test cases, and expectations.
Provides validation and conversion from raw YAML data.

MULTI-STEP TEST SUPPORT
=======================

For complex tests requiring dynamic setup, variable capture between steps,
or cleanup that must always run, use the `steps` and `cleanup` fields.

Some suites also target a specific managed-server database fixture via the
optional `server_db` field. When used, it selects the database file that the
managed server should start from for that suite.

Basic Example:
-------------
```yaml
tests:
  - name: capture_and_use
    steps:
      - run: "2 + 2"
        capture: x
      - run: "{x} + 1"
        expect:
          value: 5
```

Object Lifecycle Example:
------------------------
```yaml
tests:
  - name: create_and_cleanup
    steps:
      - run: "create($nothing)"
        capture: obj
        as: wizard
      - run: "valid({obj})"
        expect:
          value: 1
    cleanup:
      - run: "recycle({obj})"
        as: wizard
```

Dynamic Limits Example:
----------------------
```yaml
tests:
  - name: dynamic_limit_test
    steps:
      - run: "value_bytes({1, 2}) - value_bytes({})"
        capture: pad
        as: wizard
      - run: "compute_list_size()"
        capture: size
      - run: "$server_options.max_list_value_bytes = {pad} + {size}; load_server_options();"
        as: wizard
      - run: "create_oversized_list()"
        expect:
          error: E_QUOTA
```

Table-Driven Example:
---------------------
```yaml
tests:
  - name: typeof_{kind}
    table:
      columns: [kind, expr, expected]
      rows:
        - [int, "typeof(1)", 0]
        - [str, 'typeof("x")', 2]
    code: "{expr}"
    expect:
      value: "{expected}"
```

Table rows may also be mappings. For larger matrices, use `product` instead of
`rows`; each product entry is a row axis, and the test expands over the
cartesian product of those axes.

```yaml
tests:
  - name: pair_{left_kind}_{right_kind}
    table:
      product:
        - columns: [left_kind, left_expr]
          rows:
            - [int, "1"]
            - [str, '"x"']
        - columns: [right_kind, right_expr]
          rows:
            - [err, "E_ARGS"]
            - [list, "{}"]
    code: "some_builtin({left_expr}, {right_expr})"
```

A scalar that is exactly `{name}` is replaced with the row value without changing
its type; embedded placeholders are replaced as strings.

STEP FIELDS
===========

run: str (required)
    MOO code to execute. Multi-line code is supported.
    Use `return` at the end to capture the result.

capture: str (optional)
    Variable name to store the step's result.
    Use {varname} in subsequent steps to substitute.

as: str (optional)
    Permission level for this step (wizard, programmer).
    Reconnects with specified permission before executing.

expect: Expectation (optional)
    Assertion on this step's result.
    Supports: value, error, type, match, contains, range.

CLEANUP STEPS
=============

cleanup: list[TestStep]
    Steps that ALWAYS run, even if earlier steps fail.
    Use for resource cleanup (recycle objects, delete properties).
    Can use captured variables from earlier steps.

VARIABLE SUBSTITUTION
====================

{varname} in `run` code is replaced with the captured value:
- Object refs (#8) are unquoted: valid({obj}) → valid(#8)
- Error codes (E_PERM) are unquoted: {err} → E_PERM
- Strings are quoted: "{name}" → "\"foo\""
- Numbers pass through: {count} → 42

SKIP CONDITIONS
===============

skip_if: str
    Condition to skip the test. Supported:
    - "feature.64bit" - Skip if 64-bit feature is present
    - "not feature.maps" - Skip if maps feature is NOT present
    - "missing builtin.foo" - Skip if builtin 'foo' is not implemented
"""

import re
from copy import deepcopy
from dataclasses import dataclass, field
from itertools import product
from typing import Any

from .conditions import (
    SUPPORTED_CONFIG_REQUIREMENTS,
    parse_min_version,
    parse_skip_condition,
)

SUITE_FIELDS = frozenset({
    "name", "description", "version", "skip", "server_db", "requires", "setup",
    "teardown", "tests", "provides", "assumes",
})
REQUIREMENTS_FIELDS = frozenset({"builtins", "features", "min_version", "config"})
SETUP_TEARDOWN_FIELDS = frozenset({"permission", "code"})
TEST_FIELDS = frozenset({
    "name", "description", "skip", "skip_if", "permission", "setup", "teardown",
    "code", "statement", "verb", "steps", "args", "argstr", "expect", "cleanup",
    "timeout_ms", "provides", "assumes", "table",
})
EXPECTATION_FIELDS = frozenset({
    "value", "error", "type", "match", "contains", "range", "satisfies",
    "notifications", "output",
})
OUTPUT_EXPECT_FIELDS = frozenset({"exact", "match", "contains"})
TABLE_FIELDS = frozenset({"rows", "product", "columns"})
TABLE_PRODUCT_AXIS_FIELDS = frozenset({"rows", "columns"})
STEP_ACTION_FIELDS = frozenset({
    "run", "command", "verb_setup", "allocate_port", "new_connection", "send",
    "send_bytes", "read_connection", "close_connection", "wait", "assert_log",
    "assert_file", "write_file", "write_stdin", "restart_server",
})
STEP_FIELDS = STEP_ACTION_FIELDS | {"capture", "as", "expect"}
ACTION_PAYLOAD_FIELDS = {
    "verb_setup": frozenset({"object", "name", "args", "code"}),
    "allocate_port": frozenset({"capture"}),
    "new_connection": frozenset({"capture", "port"}),
    "send": frozenset({"text", "connection"}),
    "send_bytes": frozenset({"hex", "connection"}),
    "read_connection": frozenset({"connection"}),
    "assert_log": frozenset({"contains", "not_contains"}),
    "assert_file": frozenset({"path", "exists", "contains"}),
    "write_file": frozenset({"path", "content"}),
    "write_stdin": frozenset({"text"}),
    "restart_server": frozenset({"wait_ms", "down_ms"}),
}


def _require_mapping(data: Any, context: str) -> dict:
    if not isinstance(data, dict):
        raise ValueError(f"{context} must be a mapping")
    return data


def _reject_unknown_fields(data: dict, allowed: frozenset[str], context: str) -> None:
    unknown = sorted((key for key in data if key not in allowed), key=repr)
    if not unknown:
        return
    noun = "field" if len(unknown) == 1 else "fields"
    names = ", ".join(str(key) for key in unknown)
    raise ValueError(f"Unknown {noun} in {context}: {names}")


_REQUIREMENT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_]*$")


def _require_name_list(value: Any, field_name: str, *, allow_scalar: bool = False) -> list[str]:
    if allow_scalar and isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        raise ValueError(f"requires.{field_name} must be a list of names")
    if any(
        not isinstance(item, str) or _REQUIREMENT_NAME_RE.fullmatch(item) is None
        for item in value
    ):
        raise ValueError(f"requires.{field_name} must contain only non-empty names")
    return list(value)


@dataclass
class SetupTeardown:
    """Setup or teardown block for test suite or individual test."""
    permission: str = "programmer"
    code: str | list[str] = ""

    @property
    def code_lines(self) -> list[str]:
        """Get code as a list of lines."""
        if isinstance(self.code, str):
            if not self.code:
                return []
            # Split multi-line string into lines
            return [line for line in self.code.strip().split('\n') if line.strip()]
        return self.code


@dataclass
class OutputExpect:
    """Expected output from raw commands.

    For testing notify() output from command execution.
    Exactly ONE of these should be set.
    """
    exact: str | list[str] | None = None  # Exact line(s) match
    match: str | None = None              # Regex match on joined output
    contains: str | None = None           # Substring in joined output


@dataclass
class Expectation:
    """Expected test outcome.

    Every configured assertion is enforced. Compatible assertions may be
    combined.

    - value: Exact value match
    - error: MOO error code (E_TYPE, E_DIV, etc.)
    - type: Type check (int, float, str, list, map, obj, err)
    - match: Regex match on string result
    - contains: List/map contains value
    - range: Numeric range [min, max] (inclusive)
    - satisfies: MOO code predicate
    - notifications: Expected notification messages
    - output: Expected notify() output from raw commands
    """
    value: Any = None
    error: str | None = None
    type: str | None = None
    match: str | None = None
    contains: Any = None
    range: list[float] | None = None
    satisfies: str | None = None
    notifications: list[str] | None = None
    output: OutputExpect | None = None

    def is_error_expected(self) -> bool:
        """Check if this expectation expects an error."""
        return self.error is not None


@dataclass
class VerbSetup:
    """Declarative verb creation for test setup."""
    object: str           # Object ref (supports {var})
    name: str             # Verb name
    args: list[str]       # Verb args like ["this", "none", "this"]
    code: str             # Verb body


@dataclass
class NewConnection:
    """Open a new socket connection (for lifecycle testing)."""
    capture: str          # Variable name to store connection handle
    port: int | str | None = None  # Optional target port, literal or captured variable


@dataclass
class AllocatePort:
    """Capture an available localhost TCP port for tests that create listeners."""
    capture: str          # Variable name to store the allocated port number


@dataclass
class SendOnConnection:
    """Send raw text on a specific connection."""
    text: str             # Raw text to send
    connection: str       # Connection variable name


@dataclass
class SendBytesOnConnection:
    """Send raw bytes, represented as hex, on a specific connection."""
    hex: str              # Hex-encoded bytes to send
    connection: str       # Connection variable name


@dataclass
class ReadConnection:
    """Read pending output from a specific connection without sending input."""
    connection: str       # Connection variable name


@dataclass
class LogAssertion:
    """Assert that the server log contains expected text.

    Used with the assert_log step type to verify server_log() output.
    Only checks log entries written since the current test started.
    """
    contains: str | None = None     # Text that must be present in recent log entries
    not_contains: str | None = None  # Text that must be absent from recent log entries


@dataclass
class FileAssertion:
    """Assert that a file on disk has expected state.

    Used with the assert_file step type to verify file existence and contents.
    The path is relative to the server's working directory (server_dir).
    """
    path: str                      # Path relative to server_dir
    exists: bool = True            # Whether the file should exist
    contains: str | None = None    # Optional substring to find in file contents


@dataclass
class WriteFile:
    """Write a file to disk on the test host.

    Used with the write_file step type to create test fixtures before
    running MOO code that reads from files. The path is relative to
    the server's working directory (server_dir).
    """
    path: str        # Path relative to server_dir
    content: str     # File contents to write


@dataclass
class WriteStdin:
    """Write text to the managed server process stdin."""
    text: str


@dataclass
class RestartServer:
    """Restart the managed server process and reconnect transport."""
    wait_ms: int = 0  # Optional pause after restart before next step
    down_ms: int = 0  # Optional pause while the process is fully stopped, before restart


@dataclass
class TestStep:
    """A single step in a multi-step test.

    Steps execute sequentially, with optional variable capture.
    Variables can be substituted in subsequent steps using {varname} syntax.

    Exactly ONE of these should be set:
    - run: MOO code to execute (wrapped in ; prefix)
    - command: Raw command to send (for testing command parser)
    - verb_setup: Declarative verb creation
    - allocate_port: Capture an available localhost TCP port
    - new_connection: Open a new socket connection
    - send: Send raw text on a specific connection
    - send_bytes: Send raw hex bytes on a specific connection
    - read_connection: Read pending output from a specific connection
    - close_connection: Close a connection
    - wait: Pause for N milliseconds (no socket communication)
    - assert_log: Verify server log contains expected text
    - assert_file: Verify file existence and contents on disk
    - write_file: Create a file on the test host
    - write_stdin: Write text to the managed server process stdin
    - restart_server: Restart managed server process in-place
    """
    run: str | None = None                      # MOO code to execute
    command: str | None = None                  # Raw command (no ; prefix)
    verb_setup: VerbSetup | None = None         # Declarative verb creation
    allocate_port: AllocatePort | None = None   # Capture an available localhost TCP port
    new_connection: NewConnection | None = None # Open new connection
    send: SendOnConnection | None = None        # Send on specific connection
    send_bytes: SendBytesOnConnection | None = None # Send raw bytes on connection
    read_connection: ReadConnection | None = None # Read pending output on connection
    close_connection: str | None = None         # Close a connection by name
    wait: int | None = None                     # Pause for N milliseconds
    assert_log: LogAssertion | None = None      # Verify server log content
    assert_file: FileAssertion | None = None    # Verify file on disk
    write_file: WriteFile | None = None         # Create file on test host
    write_stdin: WriteStdin | None = None       # Write to managed server process stdin
    restart_server: RestartServer | None = None # Restart managed server
    capture: str | None = None                  # Variable name to store result
    as_: str | None = None                      # Permission for this step (wizard, programmer)
    expect: Expectation | None = None           # Optional assertion on this step's result


@dataclass
class MooTestCase:
    """A single test case."""
    name: str
    description: str = ""
    skip: bool | str = False
    skip_if: str | None = None
    permission: str = "programmer"
    setup: SetupTeardown | None = None
    teardown: SetupTeardown | None = None

    # Code to execute - ONE of these should be set:
    code: str | None = None       # Expression (wrapped in "return <code>;")
    statement: str | None = None  # Statement(s) - executed as-is
    verb: str | None = None       # Verb spec like "#0:do_login_command"
    steps: list["TestStep"] = field(default_factory=list)  # Multi-step test

    # Arguments (for verb calls)
    args: list[Any] = field(default_factory=list)
    argstr: str = ""

    # Expected outcome
    expect: Expectation = field(default_factory=Expectation)

    # Cleanup steps (always run, even on failure)
    cleanup: list["TestStep"] = field(default_factory=list)

    # Timeout override
    timeout_ms: int = 5000

    # Capability dependencies
    provides: str | None = None   # Capability this test provides (e.g., "fork", "queued_tasks")
    assumes: list[str] = field(default_factory=list)  # Capabilities this test assumes

    def has_steps(self) -> bool:
        """Check if this is a multi-step test."""
        return len(self.steps) > 0

    def get_code_to_execute(self) -> str:
        """Get the MOO code to execute for this test.

        Returns the code wrapped appropriately:
        - code: wrapped in "return <code>;"
        - statement: used as-is
        - verb: generates verb call code
        - steps: raises ValueError (steps are handled separately by runner)
        """
        if self.steps:
            raise ValueError(
                f"Test '{self.name}' uses steps - call runner._execute_steps() instead"
            )
        if self.code:
            code = self.code.strip()
            # Don't double-wrap if already has return
            if code.startswith("return "):
                return code if code.endswith(";") else code + ";"
            return f"return {code};"
        elif self.statement:
            stmt = self.statement.strip()
            return stmt if stmt.endswith(";") else stmt + ";"
        elif self.verb:
            # Parse verb spec like "#0:do_login_command"
            args_str = ", ".join(_value_to_moo(a) for a in self.args)
            return f"return {self.verb}({args_str});"
        else:
            raise ValueError(f"Test '{self.name}' has no code, statement, verb, or steps")


@dataclass
class Requirements:
    """Test suite requirements."""
    builtins: list[str] = field(default_factory=list)
    features: list[str] = field(default_factory=list)
    min_version: str | None = None
    config: list[str] = field(default_factory=list)


@dataclass
class MooTestSuite:
    """A collection of test cases."""
    name: str
    description: str = ""
    version: str = "1.0"
    skip: bool | str = False
    server_db: str | None = None
    requires: Requirements = field(default_factory=Requirements)
    setup: SetupTeardown | None = None
    teardown: SetupTeardown | None = None
    tests: list[MooTestCase] = field(default_factory=list)

    # Capability dependencies (suite-level defaults for all tests)
    provides: str | None = None   # Capability this suite provides
    assumes: list[str] = field(default_factory=list)  # Capabilities this suite assumes


def _value_to_moo(value: Any) -> str:
    """Convert Python value to MOO literal string."""
    if isinstance(value, str):
        # Object references like "#8" should not be quoted
        if value.startswith('#') and len(value) > 1:
            try:
                int(value[1:])  # Verify it's a valid object number
                return value    # Return unquoted: #8 not "#8"
            except ValueError:
                pass  # Not a valid object ref, treat as string
        # Error codes like "E_PERM" should not be quoted
        if value.startswith('E_') and value.isupper():
            return value
        escaped = value.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, bool):
        return '1' if value else '0'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    if isinstance(value, list):
        items = ', '.join(_value_to_moo(v) for v in value)
        return '{' + items + '}'
    if isinstance(value, dict):
        pairs = ', '.join(
            f'{_value_to_moo(k)} -> {_value_to_moo(v)}'
            for k, v in value.items()
        )
        return '[' + pairs + ']'
    return str(value)


def validate_test_suite(data: dict) -> MooTestSuite:
    """Validate and convert YAML data to TestSuite.

    Args:
        data: Raw dictionary from YAML.load()

    Returns:
        Validated TestSuite object

    Raises:
        ValueError: If required fields are missing or invalid
    """
    data = _require_mapping(data, "Test suite")
    _reject_unknown_fields(data, SUITE_FIELDS, "test suite")

    if 'name' not in data:
        raise ValueError("Test suite must have a 'name' field")
    if 'tests' not in data:
        raise ValueError("Test suite must have a 'tests' field")
    tests_data = data['tests']
    if not isinstance(tests_data, list):
        raise ValueError("Test suite 'tests' field must be a list")

    # Build requirements
    requires_data = data.get('requires', {})
    requires_data = _require_mapping(requires_data, "Test suite requirements")
    _reject_unknown_fields(requires_data, REQUIREMENTS_FIELDS, "test suite requirements")
    builtins_val = _require_name_list(requires_data.get('builtins', []), "builtins")
    features_val = _require_name_list(requires_data.get('features', []), "features")
    config_val = _require_name_list(
        requires_data.get('config', []), "config", allow_scalar=True
    )
    unknown_config = sorted(set(config_val) - SUPPORTED_CONFIG_REQUIREMENTS)
    if unknown_config:
        raise ValueError(
            "requires.config contains unsupported names: " + ", ".join(unknown_config)
        )
    min_version = requires_data.get('min_version')
    if min_version is not None:
        parse_min_version(min_version)
    requires = Requirements(
        builtins=builtins_val,
        features=features_val,
        min_version=min_version,
        config=config_val,
    )

    # Build suite-level setup/teardown
    setup = None
    if 'setup' in data:
        setup = _parse_setup_teardown(data['setup'], "suite setup")

    teardown = None
    if 'teardown' in data:
        teardown = _parse_setup_teardown(data['teardown'], "suite teardown")

    # Build test cases
    tests = []
    for test_index, test_data in enumerate(tests_data):
        context = f"test #{test_index + 1}"
        test_data = _require_mapping(test_data, context)
        _reject_unknown_fields(test_data, TEST_FIELDS, context)
        for expanded_test_data in _expand_table_test(test_data, context):
            test = _parse_test_case(expanded_test_data, context)
            tests.append(test)

    # Parse suite-level capability dependencies
    provides = data.get('provides')
    assumes = data.get('assumes', [])
    # Ensure assumes is always a list
    if isinstance(assumes, str):
        assumes = [assumes]

    return MooTestSuite(
        name=data['name'],
        description=data.get('description', ''),
        version=data.get('version', '1.0'),
        skip=data.get('skip', False),
        server_db=data.get('server_db'),
        requires=requires,
        setup=setup,
        teardown=teardown,
        tests=tests,
        provides=provides,
        assumes=assumes,
    )


def _parse_setup_teardown(data: dict | str, context: str) -> SetupTeardown:
    """Parse setup/teardown block."""
    if isinstance(data, str):
        return SetupTeardown(code=data)
    data = _require_mapping(data, context)
    _reject_unknown_fields(data, SETUP_TEARDOWN_FIELDS, context)
    return SetupTeardown(
        permission=data.get('permission', 'programmer'),
        code=data.get('code', ''),
    )


def _parse_output_expect(data: dict | str | list, context: str) -> OutputExpect:
    """Parse an output expectation for raw commands."""
    if isinstance(data, str):
        # Simple string is exact match
        return OutputExpect(exact=data)
    if isinstance(data, list):
        # List of strings is exact match on lines
        return OutputExpect(exact=data)
    # Dict with match/contains/exact
    data = _require_mapping(data, context)
    _reject_unknown_fields(data, OUTPUT_EXPECT_FIELDS, context)
    return OutputExpect(
        exact=data.get('exact'),
        match=data.get('match'),
        contains=data.get('contains'),
    )


def _parse_expectation(data: dict, context: str, *, route: str = "result") -> Expectation:
    """Parse an expectation block."""
    data = _require_mapping(data, context)
    _reject_unknown_fields(data, EXPECTATION_FIELDS, context)
    if route in {"command", "send", "send_bytes", "read_connection"}:
        unsupported = set(data) - {"output"}
        if unsupported:
            raise ValueError(f"{context}: {route} only supports output expectations")
    elif route == "result":
        if 'output' in data:
            raise ValueError(f"{context} does not support output expectations")
    elif route in {"run", "verb_setup"}:
        if 'output' in data:
            raise ValueError(f"{context}: {route} does not support output expectations")
    else:
        raise ValueError(f"{context}: {route} does not produce an expectation result")

    satisfies = data.get('satisfies')
    if satisfies is not None and "__actual__" not in satisfies:
        raise ValueError(f"{context} satisfies must reference __actual__")

    output = None
    if 'output' in data:
        output = _parse_output_expect(data['output'], f"{context} output")

    return Expectation(
        value=data.get('value'),
        error=data.get('error'),
        type=data.get('type'),
        match=data.get('match'),
        contains=data.get('contains'),
        range=data.get('range'),
        satisfies=data.get('satisfies'),
        notifications=data.get('notifications'),
        output=output,
    )


def _expand_table_test(data: dict, context: str) -> list[dict]:
    """Expand a table-driven test template into concrete test dictionaries."""
    table = data.get('table')
    if table is None:
        return [data]
    table = _require_mapping(table, f"{context} table")
    _reject_unknown_fields(table, TABLE_FIELDS, f"{context} table")

    rows, columns = _table_rows(table, context)
    expanded: list[dict] = []
    for index, row in enumerate(rows):
        variables = _table_row_variables(row, columns, index)
        variables.setdefault("index", index)
        template = deepcopy({key: value for key, value in data.items() if key != 'table'})
        expanded.append(_substitute_table_values(template, variables))
    return expanded


def _table_rows(table: dict, context: str) -> tuple[list[Any], Any]:
    has_rows = 'rows' in table
    has_product = 'product' in table
    if has_rows == has_product:
        raise ValueError("Test table must include exactly one of rows or product")

    if has_rows:
        rows = table.get('rows')
        if not isinstance(rows, list):
            raise ValueError("Test table rows must be a list")
        return rows, table.get('columns')

    return _table_product_rows(table.get('product'), context), None


def _table_product_rows(table_product: Any, context: str) -> list[dict[str, Any]]:
    if not isinstance(table_product, list) or not table_product:
        raise ValueError("Test table product must be a non-empty list")

    axes: list[list[dict[str, Any]]] = []
    for axis_index, axis in enumerate(table_product):
        axis_context = f"{context} table product axis #{axis_index + 1}"
        axis = _require_mapping(axis, axis_context)
        _reject_unknown_fields(axis, TABLE_PRODUCT_AXIS_FIELDS, axis_context)
        rows = axis.get('rows')
        if not isinstance(rows, list) or not rows:
            raise ValueError("Test table product axes must include a non-empty rows list")
        columns = axis.get('columns')
        axes.append([
            _table_row_variables(row, columns, index, include_index=False)
            for index, row in enumerate(rows)
        ])

    expanded: list[dict[str, Any]] = []
    for combination in product(*axes):
        variables: dict[str, Any] = {}
        for axis_variables in combination:
            overlap = set(variables).intersection(axis_variables)
            if overlap:
                names = ", ".join(sorted(overlap))
                raise ValueError(f"Product table variables must be unique: {names}")
            variables.update(axis_variables)
        expanded.append(variables)
    return expanded


def _table_row_variables(
    row: Any,
    columns: Any,
    index: int,
    *,
    include_index: bool = True,
) -> dict[str, Any]:
    if isinstance(row, dict):
        variables = dict(row)
    else:
        if not isinstance(columns, list) or not all(isinstance(item, str) for item in columns):
            raise ValueError("List table rows require string columns")
        if not isinstance(row, list):
            raise ValueError("Table row must be a mapping or list")
        if len(row) != len(columns):
            raise ValueError("Table row length must match columns length")
        variables = dict(zip(columns, row))
    if include_index:
        variables.setdefault("index", index)
    return variables


def _substitute_table_values(value: Any, variables: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return _substitute_table_string(value, variables)
    if isinstance(value, list):
        return [_substitute_table_values(item, variables) for item in value]
    if isinstance(value, dict):
        return {
            key: _substitute_table_values(item, variables)
            for key, item in value.items()
        }
    return value


def _substitute_table_string(value: str, variables: dict[str, Any]) -> Any:
    if value.startswith("{") and value.endswith("}") and value.count("{") == 1:
        key = value[1:-1]
        if key in variables:
            return variables[key]

    result = value
    for key, replacement in variables.items():
        result = result.replace("{" + key + "}", str(replacement))
    return result


def _parse_test_step(data: dict, context: str) -> TestStep:
    """Parse a single test step from YAML data."""
    data = _require_mapping(data, context)
    _reject_unknown_fields(data, STEP_FIELDS, context)
    # Must have exactly one action type
    has_run = 'run' in data
    has_command = 'command' in data
    has_verb_setup = 'verb_setup' in data
    has_allocate_port = 'allocate_port' in data
    has_new_connection = 'new_connection' in data
    has_send = 'send' in data
    has_send_bytes = 'send_bytes' in data
    has_read_connection = 'read_connection' in data
    has_close_connection = 'close_connection' in data
    has_wait = 'wait' in data
    has_assert_log = 'assert_log' in data
    has_assert_file = 'assert_file' in data
    has_write_file = 'write_file' in data
    has_write_stdin = 'write_stdin' in data
    has_restart_server = 'restart_server' in data

    action_count = sum([has_run, has_command, has_verb_setup, has_allocate_port,
                        has_new_connection, has_send, has_send_bytes,
                        has_read_connection, has_close_connection,
                        has_wait, has_assert_log, has_assert_file,
                        has_write_file, has_write_stdin, has_restart_server])

    if action_count == 0:
        raise ValueError(
            "Test step must have an action field (run, command, verb_setup, "
            "allocate_port, new_connection, send, send_bytes, read_connection, "
            "close_connection, wait, assert_log, assert_file, write_file, write_stdin, "
            "or restart_server)"
        )
    if action_count > 1:
        raise ValueError("Test step must have exactly one action field")

    action = next(field for field in STEP_ACTION_FIELDS if field in data)
    expect = None
    if 'expect' in data:
        expect = _parse_expectation(
            data['expect'], f"{context} expectation", route=action
        )

    # Parse verb_setup if present
    verb_setup = None
    if 'verb_setup' in data:
        vs_data = _require_mapping(data['verb_setup'], f"{context} verb_setup")
        _reject_unknown_fields(
            vs_data, ACTION_PAYLOAD_FIELDS['verb_setup'], f"{context} verb_setup"
        )
        verb_setup = VerbSetup(
            object=vs_data['object'],
            name=vs_data['name'],
            args=vs_data['args'],
            code=vs_data['code'],
        )

    # Parse allocate_port if present
    allocate_port = None
    if 'allocate_port' in data:
        ap_data = data['allocate_port']
        if isinstance(ap_data, dict):
            _reject_unknown_fields(
                ap_data, ACTION_PAYLOAD_FIELDS['allocate_port'], f"{context} allocate_port"
            )
            allocate_port = AllocatePort(capture=ap_data.get('capture', 'port'))
        else:
            allocate_port = AllocatePort(capture=ap_data)

    # Parse new_connection if present
    new_connection = None
    if 'new_connection' in data:
        nc_data = data['new_connection']
        if isinstance(nc_data, dict):
            _reject_unknown_fields(
                nc_data, ACTION_PAYLOAD_FIELDS['new_connection'], f"{context} new_connection"
            )
            new_connection = NewConnection(
                capture=nc_data.get('capture', 'conn'),
                port=nc_data.get('port'),
            )
        else:
            # Simple string form: new_connection: conn1
            new_connection = NewConnection(capture=nc_data)

    # Parse send if present
    send = None
    if 'send' in data:
        s_data = _require_mapping(data['send'], f"{context} send")
        _reject_unknown_fields(s_data, ACTION_PAYLOAD_FIELDS['send'], f"{context} send")
        send = SendOnConnection(
            text=s_data['text'],
            connection=s_data['connection'],
        )

    # Parse send_bytes if present
    send_bytes = None
    if 'send_bytes' in data:
        sb_data = _require_mapping(data['send_bytes'], f"{context} send_bytes")
        _reject_unknown_fields(
            sb_data, ACTION_PAYLOAD_FIELDS['send_bytes'], f"{context} send_bytes"
        )
        send_bytes = SendBytesOnConnection(
            hex=sb_data['hex'],
            connection=sb_data['connection'],
        )

    # Parse read_connection if present
    read_connection = None
    if 'read_connection' in data:
        rc_data = data['read_connection']
        if isinstance(rc_data, dict):
            _reject_unknown_fields(
                rc_data,
                ACTION_PAYLOAD_FIELDS['read_connection'],
                f"{context} read_connection",
            )
            read_connection = ReadConnection(connection=rc_data['connection'])
        else:
            read_connection = ReadConnection(connection=rc_data)

    # Parse assert_log if present
    assert_log = None
    if 'assert_log' in data:
        al_data = _require_mapping(data['assert_log'], f"{context} assert_log")
        _reject_unknown_fields(
            al_data, ACTION_PAYLOAD_FIELDS['assert_log'], f"{context} assert_log"
        )
        contains = al_data.get('contains')
        not_contains = al_data.get('not_contains')
        if contains is None and not_contains is None:
            raise ValueError("assert_log must specify contains or not_contains")
        assert_log = LogAssertion(
            contains=contains,
            not_contains=not_contains,
        )

    # Parse assert_file if present
    assert_file = None
    if 'assert_file' in data:
        af_data = _require_mapping(data['assert_file'], f"{context} assert_file")
        _reject_unknown_fields(
            af_data, ACTION_PAYLOAD_FIELDS['assert_file'], f"{context} assert_file"
        )
        assert_file = FileAssertion(
            path=af_data['path'],
            exists=af_data.get('exists', True),
            contains=af_data.get('contains'),
        )

    # Parse write_file if present
    write_file = None
    if 'write_file' in data:
        wf_data = _require_mapping(data['write_file'], f"{context} write_file")
        _reject_unknown_fields(
            wf_data, ACTION_PAYLOAD_FIELDS['write_file'], f"{context} write_file"
        )
        write_file = WriteFile(
            path=wf_data['path'],
            content=wf_data['content'],
        )

    # Parse write_stdin if present
    write_stdin = None
    if 'write_stdin' in data:
        ws_data = data['write_stdin']
        if isinstance(ws_data, dict):
            _reject_unknown_fields(
                ws_data, ACTION_PAYLOAD_FIELDS['write_stdin'], f"{context} write_stdin"
            )
            write_stdin = WriteStdin(text=ws_data['text'])
        else:
            write_stdin = WriteStdin(text=ws_data)

    # Parse restart_server if present
    restart_server = None
    if 'restart_server' in data:
        rs_data = data['restart_server']
        if isinstance(rs_data, dict):
            _reject_unknown_fields(
                rs_data, ACTION_PAYLOAD_FIELDS['restart_server'], f"{context} restart_server"
            )
            restart_server = RestartServer(
                wait_ms=rs_data.get('wait_ms', 0),
                down_ms=rs_data.get('down_ms', 0),
            )
        else:
            restart_server = RestartServer()

    return TestStep(
        run=data.get('run'),
        command=data.get('command'),
        verb_setup=verb_setup,
        allocate_port=allocate_port,
        new_connection=new_connection,
        send=send,
        send_bytes=send_bytes,
        read_connection=read_connection,
        close_connection=data.get('close_connection'),
        wait=data.get('wait'),
        assert_log=assert_log,
        assert_file=assert_file,
        write_file=write_file,
        write_stdin=write_stdin,
        restart_server=restart_server,
        capture=data.get('capture'),
        as_=data.get('as'),
        expect=expect,
    )


def _parse_test_case(data: dict, context: str) -> MooTestCase:
    """Parse a single test case from YAML data."""
    data = _require_mapping(data, context)
    _reject_unknown_fields(data, TEST_FIELDS - {'table'}, context)
    if 'name' not in data:
        raise ValueError("Test case must have a 'name' field")
    if 'skip_if' in data:
        try:
            parse_skip_condition(data['skip_if'])
        except ValueError as exc:
            raise ValueError(f"{context} skip_if: {exc}") from exc

    if data.get('steps') and 'expect' in data:
        raise ValueError("multi-step test cannot have a top-level expectation")

    # A missing top-level expectation means only that execution must succeed.
    expect = (
        _parse_expectation(data['expect'], f"{context} expectation")
        if 'expect' in data
        else Expectation()
    )

    # Parse test setup/teardown
    test_setup = None
    if 'setup' in data:
        test_setup = _parse_setup_teardown(data['setup'], f"{context} setup")

    test_teardown = None
    if 'teardown' in data:
        test_teardown = _parse_setup_teardown(data['teardown'], f"{context} teardown")

    # Parse steps (multi-step tests)
    steps = []
    for step_index, step_data in enumerate(data.get('steps', [])):
        steps.append(_parse_test_step(step_data, f"{context} step #{step_index + 1}"))

    # Parse cleanup steps
    cleanup = []
    for cleanup_index, cleanup_data in enumerate(data.get('cleanup', [])):
        if isinstance(cleanup_data, dict) and 'expect' in cleanup_data:
            raise ValueError("cleanup steps cannot have expectations")
        cleanup.append(
            _parse_test_step(cleanup_data, f"{context} cleanup step #{cleanup_index + 1}")
        )

    # Parse capability dependencies
    provides = data.get('provides')
    assumes = data.get('assumes', [])
    # Ensure assumes is always a list
    if isinstance(assumes, str):
        assumes = [assumes]

    return MooTestCase(
        name=data['name'],
        description=data.get('description', ''),
        skip=data.get('skip', False),
        skip_if=data.get('skip_if'),
        permission=data.get('permission', 'programmer'),
        setup=test_setup,
        teardown=test_teardown,
        code=data.get('code'),
        statement=data.get('statement'),
        verb=data.get('verb'),
        steps=steps,
        args=data.get('args', []),
        argstr=data.get('argstr', ''),
        expect=expect,
        cleanup=cleanup,
        timeout_ms=data.get('timeout_ms', 5000),
        provides=provides,
        assumes=assumes,
    )
