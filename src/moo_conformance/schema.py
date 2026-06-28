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

from copy import deepcopy
from dataclasses import dataclass, field
from itertools import product
from typing import Any


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

    Exactly ONE of these should be set:
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
            raise ValueError(f"Test '{self.name}' uses steps - call runner._execute_steps() instead")
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
    if 'name' not in data:
        raise ValueError("Test suite must have a 'name' field")

    # Build requirements
    requires_data = data.get('requires', {})
    config_val = requires_data.get('config', [])
    # Allow single string: config: server_dir
    if isinstance(config_val, str):
        config_val = [config_val]
    requires = Requirements(
        builtins=requires_data.get('builtins', []),
        features=requires_data.get('features', []),
        min_version=requires_data.get('min_version'),
        config=config_val,
    )

    # Build suite-level setup/teardown
    setup = None
    if 'setup' in data:
        setup = _parse_setup_teardown(data['setup'])

    teardown = None
    if 'teardown' in data:
        teardown = _parse_setup_teardown(data['teardown'])

    # Build test cases
    tests = []
    for test_data in data.get('tests', []):
        for expanded_test_data in _expand_table_test(test_data):
            test = _parse_test_case(expanded_test_data)
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


def _parse_setup_teardown(data: dict | str) -> SetupTeardown:
    """Parse setup/teardown block."""
    if isinstance(data, str):
        return SetupTeardown(code=data)
    return SetupTeardown(
        permission=data.get('permission', 'programmer'),
        code=data.get('code', ''),
    )


def _parse_output_expect(data: dict | str | list) -> OutputExpect:
    """Parse an output expectation for raw commands."""
    if isinstance(data, str):
        # Simple string is exact match
        return OutputExpect(exact=data)
    if isinstance(data, list):
        # List of strings is exact match on lines
        return OutputExpect(exact=data)
    # Dict with match/contains/exact
    return OutputExpect(
        exact=data.get('exact'),
        match=data.get('match'),
        contains=data.get('contains'),
    )


def _parse_expectation(data: dict) -> Expectation:
    """Parse an expectation block."""
    output = None
    if 'output' in data:
        output = _parse_output_expect(data['output'])

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


def _expand_table_test(data: dict) -> list[dict]:
    """Expand a table-driven test template into concrete test dictionaries."""
    table = data.get('table')
    if table is None:
        return [data]
    if not isinstance(table, dict):
        raise ValueError("Test table must be a mapping with rows")

    rows, columns = _table_rows(table)
    expanded: list[dict] = []
    for index, row in enumerate(rows):
        variables = _table_row_variables(row, columns, index)
        variables.setdefault("index", index)
        template = deepcopy({key: value for key, value in data.items() if key != 'table'})
        expanded.append(_substitute_table_values(template, variables))
    return expanded


def _table_rows(table: dict) -> tuple[list[Any], Any]:
    has_rows = 'rows' in table
    has_product = 'product' in table
    if has_rows == has_product:
        raise ValueError("Test table must include exactly one of rows or product")

    if has_rows:
        rows = table.get('rows')
        if not isinstance(rows, list):
            raise ValueError("Test table rows must be a list")
        return rows, table.get('columns')

    return _table_product_rows(table.get('product')), None


def _table_product_rows(table_product: Any) -> list[dict[str, Any]]:
    if not isinstance(table_product, list) or not table_product:
        raise ValueError("Test table product must be a non-empty list")

    axes: list[list[dict[str, Any]]] = []
    for axis in table_product:
        if not isinstance(axis, dict):
            raise ValueError("Test table product axes must be mappings")
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


def _parse_test_step(data: dict) -> TestStep:
    """Parse a single test step from YAML data."""
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
    has_restart_server = 'restart_server' in data

    action_count = sum([has_run, has_command, has_verb_setup, has_allocate_port,
                        has_new_connection, has_send, has_send_bytes,
                        has_read_connection, has_close_connection,
                        has_wait, has_assert_log, has_assert_file,
                        has_write_file, has_restart_server])

    if action_count == 0:
        raise ValueError("Test step must have an action field (run, command, verb_setup, "
                        "allocate_port, new_connection, send, send_bytes, read_connection, close_connection, wait, assert_log, "
                        "assert_file, write_file, or restart_server)")
    if action_count > 1:
        raise ValueError("Test step must have exactly one action field")

    expect = None
    if 'expect' in data:
        expect = _parse_expectation(data['expect'])

    # Parse verb_setup if present
    verb_setup = None
    if 'verb_setup' in data:
        vs_data = data['verb_setup']
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
            allocate_port = AllocatePort(capture=ap_data.get('capture', 'port'))
        else:
            allocate_port = AllocatePort(capture=ap_data)

    # Parse new_connection if present
    new_connection = None
    if 'new_connection' in data:
        nc_data = data['new_connection']
        if isinstance(nc_data, dict):
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
        s_data = data['send']
        send = SendOnConnection(
            text=s_data['text'],
            connection=s_data['connection'],
        )

    # Parse send_bytes if present
    send_bytes = None
    if 'send_bytes' in data:
        sb_data = data['send_bytes']
        send_bytes = SendBytesOnConnection(
            hex=sb_data['hex'],
            connection=sb_data['connection'],
        )

    # Parse read_connection if present
    read_connection = None
    if 'read_connection' in data:
        rc_data = data['read_connection']
        if isinstance(rc_data, dict):
            read_connection = ReadConnection(connection=rc_data['connection'])
        else:
            read_connection = ReadConnection(connection=rc_data)

    # Parse assert_log if present
    assert_log = None
    if 'assert_log' in data:
        al_data = data['assert_log']
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
        af_data = data['assert_file']
        assert_file = FileAssertion(
            path=af_data['path'],
            exists=af_data.get('exists', True),
            contains=af_data.get('contains'),
        )

    # Parse write_file if present
    write_file = None
    if 'write_file' in data:
        wf_data = data['write_file']
        write_file = WriteFile(
            path=wf_data['path'],
            content=wf_data['content'],
        )

    # Parse restart_server if present
    restart_server = None
    if 'restart_server' in data:
        rs_data = data['restart_server']
        if isinstance(rs_data, dict):
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
        restart_server=restart_server,
        capture=data.get('capture'),
        as_=data.get('as'),
        expect=expect,
    )


def _parse_test_case(data: dict) -> MooTestCase:
    """Parse a single test case from YAML data."""
    if 'name' not in data:
        raise ValueError("Test case must have a 'name' field")

    # Parse expectation
    expect = _parse_expectation(data.get('expect', {}))

    # Parse test setup/teardown
    test_setup = None
    if 'setup' in data:
        test_setup = _parse_setup_teardown(data['setup'])

    test_teardown = None
    if 'teardown' in data:
        test_teardown = _parse_setup_teardown(data['teardown'])

    # Parse steps (multi-step tests)
    steps = []
    for step_data in data.get('steps', []):
        steps.append(_parse_test_step(step_data))

    # Parse cleanup steps
    cleanup = []
    for cleanup_data in data.get('cleanup', []):
        cleanup.append(_parse_test_step(cleanup_data))

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
