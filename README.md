# MOO Conformance Tests

A portable conformance test suite for MOO (MUD Object Oriented) language implementations. Tests are defined in YAML format and can be run against any MOO server via TCP socket.

## Features

- **YAML-based tests**: Declarative, easy to read and write
- **Socket transport**: Tests any MOO server over TCP
- **pytest integration**: Standard Python testing workflow
- **pip installable**: `pip install moo-conformance-tests`
- **Bundled database**: Includes Test.db for toaststunt compatibility

## Quick Start

### Install

```bash
pip install moo-conformance-tests
# or with uv
uv add moo-conformance-tests
```

### Run Tests

1. Start your MOO server on port 7777:
   ```bash
   # Example with toaststunt
   ./moo Test.db Test.out.db 7777
   ```

2. Run the conformance tests:
   ```bash
   pytest --pyargs moo_conformance --moo-port=7777
   ```

3. Lint for duplicate test definitions:
   ```bash
   moo-lint-duplicates
   # or from source
   uv run moo-lint-duplicates
   ```

   Auto-clean duplicate content definitions:
   ```bash
   # keep most descriptive test in each duplicate group (default strategy)
   moo-lint-duplicates --only content --fix-content

   # deterministic alternatives
   moo-lint-duplicates --only content --fix-content --keep-strategy first
   moo-lint-duplicates --only content --fix-content --keep-strategy last
   moo-lint-duplicates --only content --fix-content --keep-strategy longest-name
   ```

   Duplicate matching is exact structural matching after normalization
   (dictionary key order normalized; `name` ignored; `description` ignored by default).
   It is not fuzzy semantic equivalence.

   Semantic-lite duplicate checks (uses `moo-interp` parser/compiler):
   ```bash
   # run semantic check only
   moo-lint-duplicates --only semantic

   # run names/content checks plus semantic check
   moo-lint-duplicates --semantic

   # auto-clean semantic duplicates
   moo-lint-duplicates --only semantic --fix-semantic
   ```

   Semantic mode is bytecode-equivalence based for runnable MOO snippets
   (`code`, `statement`, `run` fields). It is stronger than text matching,
   but still not full program-equivalence.

### From Source

```bash
git clone https://github.com/MongooseMoo/moo-conformance-tests
cd moo-conformance-tests
uv sync
uv run pytest tests/ --moo-port=7777
```

## Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--moo-host` | `localhost` | MOO server hostname |
| `--moo-port` | `7777` | MOO server port |

## Test Categories

Tests are organized by category:

| Directory | Description |
|-----------|-------------|
| `basic/` | Expression tests (arithmetic, strings, lists) |
| `builtins/` | Builtin function tests |
| `language/` | Language construct tests (loops, equality) |
| `server/` | Server feature tests |
| `objects/` | Object system tests |
| `features/` | Advanced feature tests |

Run specific categories:
```bash
# Run only arithmetic tests
pytest --pyargs moo_conformance -k "arithmetic" --moo-port=7777

# Run all builtin tests
pytest --pyargs moo_conformance -k "builtins" --moo-port=7777
```

## Running Against Toaststunt

The test suite was developed against [toaststunt](https://github.com/lisdude/toaststunt), the reference MOO implementation.

```bash
# Start toaststunt
cd /path/to/toaststunt
./moo Test.db Test.out.db 9898

# Run tests
pytest --pyargs moo_conformance --moo-port=9898 -v
```

See [docs/TOASTSTUNT.md](docs/TOASTSTUNT.md) for detailed setup instructions.

## YAML Test Format

Tests are defined in YAML files:

```yaml
name: arithmetic
description: Basic arithmetic operations

tests:
  - name: addition
    code: "1 + 1"
    expect:
      value: 2

  - name: division_by_zero
    code: "1 / 0"
    expect:
      error: E_DIV

  - name: random_range
    code: "random(10)"
    expect:
      range: [1, 10]
```

See [docs/YAML_SCHEMA.md](docs/YAML_SCHEMA.md) for the full schema.

## Programmatic Usage

```python
from moo_conformance import SocketTransport, YamlTestRunner, discover_yaml_tests

# Connect to server
transport = SocketTransport("localhost", 7777)
transport.connect("wizard")

# Execute code directly
result = transport.execute("1 + 1")
print(result.value)  # 2

# Run all tests programmatically
runner = YamlTestRunner(transport)
for yaml_path, suite, test in discover_yaml_tests():
    runner.run_suite_setup(suite)
    runner.run_test(test)
```

## Test Database

The package includes `Test.db`, a minimal MOO database for testing. Access it via:

```python
from moo_conformance import get_db_path
db_path = get_db_path()
```

## Contributing Tests

1. Create a YAML file in the appropriate category
2. Follow the schema in [docs/YAML_SCHEMA.md](docs/YAML_SCHEMA.md)
3. Test against toaststunt to verify expected behavior
4. Submit a pull request

See [docs/CONVERTING.md](docs/CONVERTING.md) for converting tests from other formats.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Related Projects

- [toaststunt](https://github.com/lisdude/toaststunt) - Reference MOO implementation
- [cow_py](https://github.com/MongooseMoo/cow_py) - Python MOO server
- [moo_interp](https://github.com/MongooseMoo/moo_interp) - Python MOO interpreter
