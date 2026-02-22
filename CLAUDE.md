# moo-conformance-tests

Standalone pytest plugin for MOO language conformance testing. YAML-based tests run over TCP socket against any MOO server.

## Ecosystem

| Project | Path | Role |
|---------|------|------|
| **toaststunt** | `~/src/toaststunt/` | C++ reference implementation - **THE AUTHORITY** |
| **moo-conformance-tests** | `~/code/moo-conformance-tests/` | This project - YAML test suite |
| **barn** | `~/code/barn/` | Go MOO server |
| **cow_py** | `~/code/cow_py/` | Python MOO server |
| **moo_interp** | `~/code/moo_interp/` | Python MOO interpreter (VM, parser) |

## Key Paths

**ToastStunt (Reference)**:
- Binary: `~/src/toaststunt/build-msvc/Release/moo.exe` (also `test/moo.exe`)
- Test database: `~/src/toaststunt/test/Test.db`
- Ruby tests (original source): `~/src/toaststunt/test/tests/test_*.rb`

**This Project**:
- YAML tests: `src/moo_conformance/_tests/` (basic/, builtins/, language/, server/, etc.)
- Bundled Test.db: `src/moo_conformance/_db/Test.db`
- CLI entry point: `src/moo_conformance/cli.py` (`moo-conformance` command)
- Plugin/fixtures: `src/moo_conformance/plugin.py`
- Socket transport: `src/moo_conformance/transport.py`
- Test runner: `src/moo_conformance/runner.py`

**Utilities**:
- `~/code/barn/moo_client.exe` - CLI tool for manual MOO server testing

## Manual MOO Testing with moo_client

**CRITICAL: NEVER use `nc` (netcat) for MOO testing. ALWAYS use moo_client.**

The barn project includes `moo_client.exe` - a proper MOO client that handles telnet negotiation, line editing, and connection management correctly.

### Location
```
/c/Users/Q/code/barn/moo_client.exe
```

### Usage
```bash
# Send commands with -cmd flags (NOT stdin)
/c/Users/Q/code/barn/moo_client.exe -port 9898 -cmd "connect Wizard" -cmd "; return player;"

# Multiple commands
/c/Users/Q/code/barn/moo_client.exe -port 9898 -cmd "connect Wizard" -cmd "; return player.wizard;"

# Commands from file
/c/Users/Q/code/barn/moo_client.exe -port 9898 -file commands.txt
```

### Why NOT nc
- nc doesn't handle MOO's telnet negotiation properly
- nc doesn't handle PREFIX/SUFFIX response markers
- nc output is often garbled or incomplete
- moo_client is purpose-built for MOO protocol

### Quick Commands
```bash
# Check if Wizard player works
/c/Users/Q/code/barn/moo_client.exe -port 9898
> connect Wizard
> ; player
> ; player.wizard

# Check what players exist
> ; players()

# Test a builtin
> ; generate_json(42)
```

## Running Tests

The test suite supports two modes: **managed** (auto-starts/stops the server) and **external** (connects to an already-running server).

### Managed mode (recommended)

The `--server-command` flag starts and stops the server automatically. It uses the bundled Test.db and picks a free port.

```bash
# Auto-managed ToastStunt
uv run moo-conformance --server-command="~/src/toaststunt/test/moo.exe {db} NUL {port}" -v

# Specific category
uv run moo-conformance --server-command="~/src/toaststunt/test/moo.exe {db} NUL {port}" -k "arithmetic" -v

# Stop on first failure
uv run moo-conformance --server-command="~/src/toaststunt/test/moo.exe {db} NUL {port}" -x -v
```

Managed mode also auto-detects `--moo-server-dir` (needed for fileio_verified, fileio_host_write tests).

### External mode

Connect to a server you started yourself:

```bash
# Start ToastStunt manually
cd /c/Users/Q/src/toaststunt/test
./moo.exe Test.db NUL 9898

# Run against it
uv run moo-conformance --moo-port=9898 -v

# Or via pytest directly
uv run pytest --pyargs moo_conformance --moo-port=9898 -v
```

## Principles

1. **Toast is the reference** - Whatever ToastStunt does is correct by definition
2. **Test.db is authoritative** - Same database Toast uses; if Toast works with it, it's correct
3. **Never blame the database** - If a test passes on Toast but fails elsewhere, the other implementation is wrong
4. **Failures ARE the TODO list** - Don't skip tests to hide incomplete work

## YAML Test Schema

See `docs/YAML_SCHEMA.md` for the full schema. Basic structure:

```yaml
name: suite_name
tests:
  - name: test_name
    code: "1 + 1"
    expect:
      value: 2
```

Schema validation: `src/moo_conformance/schema.py`
