# Converting Toaststunt Tests to YAML

This guide explains how to convert Ruby test files from the toaststunt test suite to the declarative YAML format used by cow_py's conformance tests.

## Source Files

Ruby test files are located at:
```
/c/Users/Q/src/toaststunt/test/tests/test_*.rb
/c/Users/Q/src/toaststunt/test/tests/basic/*/test.in  (expression tests)
```

## Quick Reference

### Ruby Pattern -> YAML Pattern

| Ruby | YAML |
|------|------|
| `run_test_as('wizard')` | `permission: wizard` |
| `run_test_as('programmer')` | `permission: programmer` (default) |
| `assert_equal E_INVARG, random(0)` | `code: "random(0)"` + `expect: { error: E_INVARG }` |
| `assert_equal 5, simplify(command(%Q\|; return 15/3;\|))` | `code: "15/3"` + `expect: { value: 5 }` |
| `assert_equal "foo", index("foobar", "foo")` | `code: 'index("foobar", "foo")'` + `expect: { value: 1 }` |
| `assert r > 0 && r <= 100` | `expect: { range: [1, 100] }` |

### Expression Tests (.in/.out files)

Convert `.in`/`.out` file pairs like this:

```
# Input: test.in
1 + 1
sqrt(4.0)
"hello" + " world"

# Output: test.out
2
2.0
"hello world"
```

Becomes:

```yaml
name: arithmetic
description: Basic arithmetic operations

tests:
  - name: addition
    code: "1 + 1"
    expect:
      value: 2

  - name: sqrt
    code: "sqrt(4.0)"
    expect:
      value: 2.0

  - name: string_concat
    code: '"hello" + " world"'
    expect:
      value: "hello world"
```

## Error Codes

Use these exact strings in `expect.error`:

| Error | Description |
|-------|-------------|
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

## YAML Schema

### Full Schema

```yaml
name: suite_name              # Required: lowercase, underscores
description: "Human readable" # Optional

requires:                     # Optional: dependencies
  builtins: [random, sqrt]   # Required builtins
  features: [maps, 64bit]    # Required server features

setup:                        # Optional: runs before all tests
  permission: wizard
  code: |
    $test_obj = create($nothing);
    add_property($test_obj, "value", 0, {player, ""});

teardown:                     # Optional: runs after all tests
  permission: wizard
  code: |
    recycle($test_obj);

tests:
  - name: test_name           # Required: lowercase, underscores
    description: "Optional"   # Human-readable description
    permission: programmer    # Default: programmer
    skip: false               # Or: "reason string"
    skip_if: "not feature.64bit"  # Conditional skip

    # ONE of these (code is most common):
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

    # Expected outcome - ONE of:
    expect:
      value: 42               # Exact value match
      error: E_TYPE           # MOO error code
      type: int               # Type check (int, float, str, list, map, obj, err)
      match: "regex.*"        # Regex match on string
      contains: "needle"      # List/string contains value
      range: [1, 100]         # Numeric range (inclusive)
      notifications: ["msg"]  # Expected notify() messages
```

### Minimal Test

```yaml
name: math

tests:
  - name: addition
    code: "1 + 1"
    expect:
      value: 2
```

## CRITICAL: Testing Object Relationships

The Ruby test suite compares **actual object references at runtime**:

```ruby
a = create(NOTHING)      # a holds actual object, e.g., MooObj("#128")
b = create(a)            # b holds actual object, e.g., MooObj("#129")
assert_equal a, parent(b) # Compares actual values - both are "#128"
```

**The YAML format cannot express "expect the object we just created"** because expected values are static.

### The Principle: Test Relationships, Not Values

Instead of trying to predict object numbers, **translate the assertion into a boolean comparison**:

Ruby:
```ruby
assert_equal a, parent(b)
assert_equal b, parent(c)
assert_equal NOTHING, parent(a)
```

YAML (WRONG - can't know object numbers):
```yaml
# DON'T DO THIS - object numbers are unpredictable
expect:
  value: ["#128", "#129", -1]
```

YAML (CORRECT - test the relationship):
```yaml
statement: |
  a = create($nothing);
  b = create(a);
  c = create(b);
  return {parent(a) == $nothing, parent(b) == a, parent(c) == b};
expect:
  value: [1, 1, 1]
```

### When to Use This Pattern

Use boolean comparisons when the Ruby test:
- Creates objects and compares them (`assert_equal a, parent(b)`)
- Tests object identity (`assert_equal player, get(a, 'owner')`)
- Checks object relationships (`assert_equal [c, d], children(b)`)

### Full Example

Ruby test:
```ruby
def test_create
  run_test_as('wizard') do
    a = create(NOTHING)
    b = create(a)
    c = create(b, NOTHING)
    d = create(b, a)

    assert_equal NOTHING, parent(a)
    assert_equal a, parent(b)
    assert_equal b, parent(c)
    assert_equal b, parent(d)

    assert_equal b, children(a)
    assert_equal [c, d], children(b)
  end
end
```

YAML conversion:
```yaml
- name: create_parent_relationships
  permission: wizard
  statement: |
    a = create($nothing);
    b = create(a);
    c = create(b, $nothing);
    d = create(b, a);
    return {
      parent(a) == $nothing,
      parent(b) == a,
      parent(c) == b,
      parent(d) == b
    };
  expect:
    value: [1, 1, 1, 1]

- name: create_children_relationships
  permission: wizard
  statement: |
    a = create($nothing);
    b = create(a);
    c = create(b, $nothing);
    d = create(b, a);
    return {
      children(a) == {b},
      children(b) == {c, d}
    };
  expect:
    value: [1, 1]
```

### Static Values Are OK For

- Error codes: `expect: { error: E_INVARG }`
- Special objects: `$nothing` (-1), `$failed_match` (-4)
- Integers, floats, strings: `expect: { value: 42 }`
- Boolean results: `expect: { value: 1 }`

## Complex Examples

### Error Testing

```yaml
- name: division_by_zero_integer
  code: "1 / 0"
  expect:
    error: E_DIV

- name: division_by_zero_float
  code: "1.0 / 0.0"
  expect:
    error: E_DIV

- name: invalid_argument
  code: "random(0)"
  expect:
    error: E_INVARG
```

### Type Checking

```yaml
- name: random_returns_integer
  code: "random(100)"
  expect:
    type: int

- name: sqrt_returns_float
  code: "sqrt(4)"
  expect:
    type: float
```

### Range Checking

```yaml
- name: random_in_range
  code: "random(10)"
  expect:
    range: [1, 10]
```

### Setup/Teardown

```yaml
name: create_tests
description: Tests for create() builtin

setup:
  permission: wizard
  code: |
    add_property($system, "test_parent", create($nothing), {$wizard, ""});

teardown:
  permission: wizard
  code: |
    recycle($system.test_parent);
    delete_property($system, "test_parent");

tests:
  - name: create_with_parent
    permission: wizard
    code: "valid(create($system.test_parent))"
    expect:
      value: 1

  - name: create_inherits_from_parent
    permission: wizard
    code: "parent(create($system.test_parent)) == $system.test_parent"
    expect:
      value: 1
```

### Multi-line Statements

```yaml
- name: loop_sum
  statement: |
    sum = 0;
    for i in [1..10]
      sum = sum + i;
    endfor
    return sum;
  expect:
    value: 55

- name: conditional
  statement: |
    x = 5;
    if (x > 3)
      return "big";
    else
      return "small";
    endif
  expect:
    value: "big"
```

### Skipping Tests

```yaml
- name: file_open_test
  skip: "Requires fileio builtin"
  code: 'file_open("/tmp/test", "r")'
  expect:
    type: int

- name: 64bit_integer_test
  skip_if: "not feature.64bit"
  code: "9223372036854775807"
  expect:
    value: 9223372036854775807
```

### Notifications

```yaml
- name: notify_sends_message
  statement: |
    notify(player, "Hello");
    return 1;
  expect:
    value: 1
    notifications:
      - "Hello"
```

## Conversion Checklist

For each Ruby test file:

1. [ ] Create YAML file in appropriate directory (see Directory Mapping below)
2. [ ] Set `name` (lowercase, underscores, matches filename without .yaml)
3. [ ] Set `description` (from Ruby class comment or file header)
4. [ ] Convert `setup` method if present (class-level setup)
5. [ ] Convert `teardown` method if present (class-level teardown)
6. [ ] For each `def test_*` method:
   - [ ] Extract test name (remove `test_` prefix, convert to lowercase_underscores)
   - [ ] Extract permission from `run_test_as('...')`
   - [ ] Extract code from `command()`, `simplify()`, or helper methods
   - [ ] Extract expected value/error from `assert_equal` or `assert`
   - [ ] Handle multiple assertions -> multiple test entries
   - [ ] Handle parametrized tests (loops) -> multiple test entries
7. [ ] Run tests: `uv run pytest tests/conformance/ -v -k <suite_name>`
8. [ ] Mark failing tests as `skip: "Not implemented: <reason>"`

## Directory Mapping

| Ruby File | YAML Location |
|-----------|---------------|
| `test_math.rb` | `builtins/math.yaml` |
| `test_string_operations.rb` | `builtins/string_ops.yaml` |
| `test_algorithms.rb` | `builtins/algorithms.yaml` |
| `test_primitives.rb` | `builtins/primitives.yaml` |
| `test_looping.rb` | `language/looping.yaml` |
| `test_equality.rb` | `language/equality.yaml` |
| `test_eval.rb` | `language/eval.yaml` |
| `test_moocode_parsing.rb` | `language/parsing.yaml` |
| `test_create.rb` | `objects/create.yaml` |
| `test_recycle.rb` | `objects/recycle.yaml` |
| `test_objects.rb` | `objects/objects.yaml` |
| `test_objects_and_properties.rb` | `objects/properties.yaml` |
| `test_objects_and_verbs.rb` | `objects/verbs.yaml` |
| `test_http.rb` | `server/http.yaml` |
| `test_fileio.rb` | `server/fileio.yaml` |
| `test_exec.rb` | `server/exec.yaml` |
| `test_limits.rb` | `server/limits.yaml` |
| `basic/arithmetic/*` | `basic/arithmetic.yaml` |
| `basic/string/*` | `basic/string.yaml` |
| `basic/list/*` | `basic/list.yaml` |
| `basic/object/*` | `basic/object.yaml` |
| `basic/property/*` | `basic/property.yaml` |
| `basic/value/*` | `basic/value.yaml` |

## Common Ruby Patterns

### Pattern: Simple assertion

```ruby
def test_that_random_1_returns_1
  run_test_as('programmer') do
    assert_equal 1, random(1)
  end
end
```

Becomes:

```yaml
- name: random_1_returns_1
  code: "random(1)"
  expect:
    value: 1
```

### Pattern: Error assertion

```ruby
def test_that_random_0_is_invalid
  run_test_as('programmer') do
    assert_equal E_INVARG, random(0)
  end
end
```

Becomes:

```yaml
- name: random_0_is_invalid
  code: "random(0)"
  expect:
    error: E_INVARG
```

### Pattern: Command with simplify

```ruby
def test_division
  run_test_as('programmer') do
    assert_equal 5, simplify(command(%Q|; return 15 / 3; |))
  end
end
```

Becomes:

```yaml
- name: division
  code: "15 / 3"
  expect:
    value: 5
```

### Pattern: Multiple assertions in one test

```ruby
def test_modulus
  run_test_as('programmer') do
    assert_equal -3, simplify(command(%Q|; return -15 % -4; |))
    assert_equal 1, simplify(command(%Q|; return -15 % 4; |))
    assert_equal -1, simplify(command(%Q|; return 15 % -4; |))
    assert_equal 3, simplify(command(%Q|; return 15 % 4; |))
  end
end
```

Becomes multiple tests:

```yaml
- name: modulus_neg_neg
  code: "-15 % -4"
  expect:
    value: -3

- name: modulus_neg_pos
  code: "-15 % 4"
  expect:
    value: 1

- name: modulus_pos_neg
  code: "15 % -4"
  expect:
    value: -1

- name: modulus_pos_pos
  code: "15 % 4"
  expect:
    value: 3
```

### Pattern: Range/random testing

```ruby
def test_that_random_returns_a_number_between_1_and_max
  run_test_as('programmer') do
    1000.times do
      r = random
      assert r > 0 && r <= 2147483647
    end
  end
end
```

Becomes (single check, range validates):

```yaml
- name: random_in_valid_range
  code: "random()"
  expect:
    range: [1, 2147483647]
```

### Pattern: Wizard permission

```ruby
def test_create_as_wizard
  run_test_as('wizard') do
    assert_equal true, valid(create($nothing))
  end
end
```

Becomes:

```yaml
- name: create_as_wizard
  permission: wizard
  code: "valid(create($nothing))"
  expect:
    value: 1  # MOO true = 1
```

## Running Tests

```bash
# Run all conformance tests
uv run pytest tests/conformance/ -v

# Run specific suite
uv run pytest tests/conformance/ -v -k "arithmetic"

# Run specific test
uv run pytest tests/conformance/ -v -k "arithmetic::addition"

# Show skipped tests
uv run pytest tests/conformance/ -v --tb=no | grep SKIP

# Run against remote server
uv run pytest tests/conformance/ -v --transport=socket --moo-port=7777
```

## Tips

1. **YAML quoting**: Use single quotes for MOO strings containing double quotes:
   ```yaml
   code: 'index("hello", "e")'
   ```

2. **Multi-line code**: Use `|` for statement blocks:
   ```yaml
   statement: |
     x = 1;
     return x;
   ```

3. **Boolean values**: MOO uses 1/0, not true/false:
   ```yaml
   expect:
     value: 1  # true
   ```

4. **Object references**: For special objects, use integers:
   ```yaml
   expect:
     value: -1  # $nothing
   ```
   For dynamically created objects, use boolean comparisons instead (see "Testing Object Relationships" above).

5. **Lists**: Use YAML lists:
   ```yaml
   expect:
     value: [1, 2, 3]
   ```

6. **Maps**: Use YAML dicts (note MOO uses `->` but YAML uses `:`):
   ```yaml
   expect:
     value: {"a": 1, "b": 2}
   ```
