# YAML Test Schema

This document describes the full YAML schema for MOO conformance tests.

## Suite Structure

```yaml
name: suite_name              # Required: lowercase, underscores
description: "Human readable" # Optional
version: "1.0"               # Optional

requires:                     # Optional: dependencies
  builtins: [random, sqrt]   # Required builtins
  features: [maps, 64bit]    # Required server features
  config: [server_dir]       # Required config keys (see CLI Options)

setup:                        # Optional: runs before all tests
  permission: wizard
  code: |
    $test_obj = create($nothing);

teardown:                     # Optional: runs after all tests
  permission: wizard
  code: |
    recycle($test_obj);

tests:                        # Required: list of test cases
  - name: test_name
    ...
```

## Test Case Structure

```yaml
tests:
  - name: test_name           # Required: lowercase, underscores
    description: "Optional"   # Human-readable description
    permission: programmer    # Default: programmer (or "wizard")
    skip: false               # Or: "reason string"
    skip_if: "condition"      # Conditional skip (see below)

    # Code to execute - ONE of these:
    code: "expression"        # Expression - wrapped in "return <expr>;"
    statement: |              # Statement(s) - needs explicit return
      x = 5;
      return x * 2;
    verb: "#0:do_login"       # Verb call

    args: ["arg1", "arg2"]    # Arguments for verb calls
    argstr: "arg1 arg2"       # Argument string

    setup:                    # Test-level setup
      code: "x = 1;"

    teardown:                 # Test-level teardown (always runs)
      code: "x = 0;"

    expect:                   # Expected outcome
      value: 42               # Exact value match
```

## Expectation Types

Only ONE expectation type should be used per test:

### `value` - Exact Match
```yaml
expect:
  value: 42
  value: "hello"
  value: [1, 2, 3]
  value: {"a": 1}
```

### `error` - MOO Error
```yaml
expect:
  error: E_TYPE
  error: E_DIV
  error: E_PERM
```

### `type` - Type Check
```yaml
expect:
  type: int      # int, float, str, list, map, obj, err, anon
```

### `match` - Regex Match
```yaml
expect:
  match: "pattern.*"
```

### `contains` - Contains Value
```yaml
expect:
  contains: "needle"    # For strings
  contains: 42          # For lists
```

### `range` - Numeric Range
```yaml
expect:
  range: [1, 100]      # Inclusive: 1 <= value <= 100
```

### `notifications` - Expected Messages
```yaml
expect:
  notifications:
    - "Hello"
    - "World"
```

## Skip Conditions

```yaml
skip: true                           # Always skip
skip: "Reason string"                # Skip with reason
skip_if: "feature.64bit"             # Skip if feature present
skip_if: "not feature.maps"          # Skip if feature absent
skip_if: "missing builtin.foo"       # Skip if builtin missing
```

## CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--moo-host` | `localhost` | MOO server host |
| `--moo-port` | `7777` | MOO server port |
| `--server-command` | none | Shell command to start a managed MOO server (supports `{port}` and `{db}` placeholders) |
| `--server-db` | bundled Test.db | Database file for managed server |
| `--moo-server-dir` | none | Path to the MOO server's working directory |
| `--moo-log-file` | none | Path to the MOO server's log file |

### `--moo-server-dir`

The server's working directory on the host filesystem. Required by tests that use `assert_file` or `write_file` steps, since those steps resolve file paths relative to this directory.

When `--server-command` is used, the server directory is auto-detected from the managed server's temporary directory. When running against an external server, pass this option explicitly.

### `--moo-log-file`

Path to the server's log output file. Required by tests that use `assert_log` steps, since those steps read the log file to verify that expected entries were written.

When `--server-command` is used, the log file path is auto-detected from the managed server. When running against an external server, redirect the server's stdout/stderr to a file and pass that path.

## Config Requirements

The `requires.config` field lists config keys that must be available for the suite to run. If any required key is not provided, all tests in the suite are skipped.

```yaml
requires:
  config: [server_dir]          # Single key
  config: [server_dir, log_file] # Multiple keys
```

Available config keys:

| Key | Provided by | Description |
|-----|-------------|-------------|
| `server_dir` | `--moo-server-dir` | Server's working directory |
| `log_file` | `--moo-log-file` | Server's log file path |

When a required config key is missing, the test is skipped with a message indicating which `--moo-*` option to use.

## Multi-Step Tests

For complex tests requiring multiple steps with variable capture:

```yaml
tests:
  - name: create_and_verify
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

### Step Fields

Each step must have exactly ONE action field. The common fields (`capture`, `as`, `expect`) can be combined with any action.

**Action fields** (exactly one per step):

| Field | Description |
|-------|-------------|
| `run` | MOO code to execute |
| `command` | Raw command to send (no `;` prefix, for testing command parser) |
| `verb_setup` | Declarative verb creation (see below) |
| `new_connection` | Open a new socket connection |
| `send` | Send raw text on a specific connection |
| `close_connection` | Close a named connection |
| `wait` | Pause for N milliseconds |
| `assert_log` | Verify server log contains expected text |
| `assert_file` | Verify file existence and contents on disk |
| `write_file` | Create a file on the test host |

**Common fields** (optional, on any step):

| Field | Description |
|-------|-------------|
| `capture` | Variable name to store result |
| `as` | Permission level for this step |
| `expect` | Assertion on this step's result |

### Variable Substitution

Use `{varname}` to substitute captured values:

```yaml
steps:
  - run: "2 + 2"
    capture: x
  - run: "{x} + 1"    # Becomes "4 + 1"
    expect:
      value: 5
```

Variable types are converted appropriately:
- Objects: `{obj}` → `#8`
- Errors: `{err}` → `E_PERM`
- Strings: `{str}` → `"foo"`
- Numbers: `{num}` → `42`

### Step Type Details

#### `wait` - Pause Between Steps

Pauses execution for a specified number of milliseconds. No socket communication occurs during the wait. Useful for allowing forked tasks time to execute or for giving the server time to flush log output before checking it.

```yaml
steps:
  - run: |
      fork (0)
        #0.__prop = 42;
      endfork
      return "forked";
  - wait: 500
  - run: "return #0.__prop;"
    expect:
      value: 42
```

| Field | Type | Description |
|-------|------|-------------|
| `wait` | `int` | Duration in milliseconds |

The runner calls `time.sleep(wait / 1000)` and then continues to the next step.

#### `assert_log` - Verify Server Log Content

Checks that the server's log file contains expected text. Only examines log entries written since the current test started (the runner records the log file offset at the beginning of each test).

Requires: `--moo-log-file` (or auto-detected via `--server-command`). Suites should declare `requires.config: [log_file]` so tests are skipped when the log file is not configured.

```yaml
steps:
  - run: |
      return server_log("MY_TEST_MARKER");
  - wait: 200
  - assert_log:
      contains: "MY_TEST_MARKER"
```

| Field | Type | Description |
|-------|------|-------------|
| `assert_log.contains` | `str` | Text to search for in recent log entries |

If the text is not found, the assertion fails with an excerpt of the log content written since the test started.

#### `assert_file` - Verify File on Disk

Checks that a file on the host filesystem exists (or does not exist) and optionally contains expected text. The file path is resolved relative to the server's working directory (`server_dir`). A path safety check prevents directory traversal outside `server_dir`.

Requires: `--moo-server-dir` (or auto-detected via `--server-command`). Suites should declare `requires.config: [server_dir]`.

```yaml
steps:
  - run: |
      h = file_open("output.txt", "w-tn");
      file_writeline(h, "hello");
      file_close(h);
      return 1;
  - assert_file:
      path: "files/output.txt"
      exists: true
      contains: "hello"
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `assert_file.path` | `str` | (required) | File path relative to `server_dir` |
| `assert_file.exists` | `bool` | `true` | Whether the file should exist |
| `assert_file.contains` | `str` | `null` | Substring to find in file contents (only checked when `exists` is true) |

Note: Toast's file I/O builtins place files under a `files/` subdirectory within the server's working directory, so `assert_file` paths for MOO-created files typically start with `files/`.

#### `write_file` - Create File on Test Host

Writes a file to the host filesystem before MOO code executes. Useful for creating test fixtures that MOO code will read via `file_open`. The path is resolved relative to `server_dir` with the same safety checks as `assert_file`. Parent directories are created automatically if they do not exist.

Requires: `--moo-server-dir` (or auto-detected via `--server-command`). Suites should declare `requires.config: [server_dir]`.

```yaml
steps:
  - write_file:
      path: "files/input.txt"
      content: "test data from host"
  - run: |
      h = file_open("input.txt", "r-tn");
      data = file_readline(h);
      file_close(h);
      return data;
    expect:
      value: "test data from host"
```

| Field | Type | Description |
|-------|------|-------------|
| `write_file.path` | `str` | File path relative to `server_dir` |
| `write_file.content` | `str` | Content to write to the file |

## Test File Index

### Fork Tests (`_tests/fork/`)

| File | Description |
|------|-------------|
| `fork_timing.yaml` | Fork timing behavior: zero-delay fork execution, delayed task visibility in `queued_tasks()`, and `kill_task()` preventing execution. Uses `wait` steps to allow forked tasks time to run. |

### Server Tests (`_tests/server/`)

| File | Description |
|------|-------------|
| `dump_database.yaml` | `dump_database()` builtin: return value, checkpoint log entry via `assert_log`, wizard-only permission. Requires `log_file` config. |

### Builtin Tests (`_tests/builtins/`)

| File | Description |
|------|-------------|
| `server_log.yaml` | `server_log()` builtin: basic logging, logging with level parameter, wizard-only permission. Uses `assert_log` to verify log entries. Requires `log_file` config. |
| `fileio_verified.yaml` | File I/O builtins with disk verification: write/read roundtrip, write persistence via `assert_file`, file removal, directory listing, mkdir/rmdir, and `file_stat`. Requires `server_dir` config. |
| `fileio_errors.yaml` | File I/O error conditions: opening nonexistent files (`E_FILE`), writing to closed handles (`E_INVARG`), path traversal attempts (`E_INVARG`). |
| `fileio_host_write.yaml` | Integration test for `write_file` step type: writes a file from the test host, verifies MOO can read it via `file_open`/`file_readline`, then cleans up. Requires `server_dir` config. |

## Error Codes

| Code | Description |
|------|-------------|
| `E_TYPE` | Type mismatch |
| `E_DIV` | Division by zero |
| `E_PERM` | Permission denied |
| `E_PROPNF` | Property not found |
| `E_VERBNF` | Verb not found |
| `E_VARNF` | Variable not found |
| `E_INVIND` | Invalid index |
| `E_RANGE` | Range error |
| `E_ARGS` | Wrong number of arguments |
| `E_INVARG` | Invalid argument |
| `E_RECMOVE` | Recursive move |
| `E_MAXREC` | Maximum recursion exceeded |
| `E_NACC` | Not accessible |
| `E_QUOTA` | Quota exceeded |
| `E_FLOAT` | Floating point error |
| `E_FILE` | File I/O error |
| `E_EXEC` | Execution error |
| `E_INTRPT` | Interrupted |

## MOO Types

| Type | Description |
|------|-------------|
| `int` | Integer |
| `float` | Floating point |
| `str` | String |
| `list` | List `{1, 2, 3}` |
| `map` | Map `["a" -> 1]` |
| `obj` | Object reference `#123` |
| `err` | Error value `E_TYPE` |
| `anon` | Anonymous object `*#123` |

## Complete Example

```yaml
name: math_builtins
description: Tests for math builtin functions

requires:
  builtins: [sqrt, sin, cos, random]

setup:
  permission: wizard
  code: |
    add_property(#0, "test_val", 100, {#0, "rc"});

teardown:
  permission: wizard
  code: |
    delete_property(#0, "test_val");

tests:
  - name: sqrt_integer
    code: "sqrt(4)"
    expect:
      value: 2.0

  - name: sqrt_float
    code: "sqrt(2.0)"
    expect:
      range: [1.41, 1.42]

  - name: sqrt_negative
    code: "sqrt(-1)"
    expect:
      error: E_INVARG

  - name: random_range
    code: "random(10)"
    expect:
      type: int
      range: [1, 10]

  - name: trig_identity
    description: "sin^2 + cos^2 = 1"
    statement: |
      x = 0.5;
      return sin(x)^2 + cos(x)^2;
    expect:
      range: [0.999, 1.001]

  - name: property_access
    code: "#0.test_val"
    expect:
      value: 100
```
