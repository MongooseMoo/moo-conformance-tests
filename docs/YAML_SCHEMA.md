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

| Field | Description |
|-------|-------------|
| `run` | MOO code to execute (required) |
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
