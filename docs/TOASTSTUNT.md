# Running Conformance Tests Against Toaststunt

This documents how to run conformance tests against the Toaststunt C implementation to verify expected behavior.

## Prerequisites

1. **Toaststunt** - Get it from https://github.com/lisdude/toaststunt
   - Build instructions in the toaststunt README
   - You need `moo.exe` (or `moo` on Linux/Mac)
   - Required: `Test.db` from `<toaststunt>/test/`

2. **This package** installed:
   ```bash
   pip install moo-conformance-tests
   # or
   uv add moo-conformance-tests
   ```

## How It Works

The conformance tests connect to a running MOO server via TCP:

1. Connect and authenticate (`connect Wizard`)
2. Set PREFIX/SUFFIX markers for response parsing
3. Execute code via `; <code>` command (eval shortcut)
4. Parse eval result: `=> value` or error traceback

## Step 1: Start Toaststunt Server

```bash
cd <toaststunt>/test

# moo.exe syntax: moo <indb> <outdb> <port>
./moo Test.db Test.out.db 9898
```

The server should start and listen on port **9898**.

**Verify it's running:**
```bash
# Quick connection test (Linux/Mac)
echo "connect Wizard" | nc localhost 9898

# Or use telnet
telnet localhost 9898
```

## Step 2: Run Conformance Tests

```bash
# Run all conformance tests against toaststunt
pytest --pyargs moo_conformance --moo-port=9898

# Run specific test file
pytest --pyargs moo_conformance --moo-port=9898 -k "arithmetic"

# Run single test
pytest --pyargs moo_conformance --moo-port=9898 -k "arithmetic::addition"

# Verbose output
pytest --pyargs moo_conformance --moo-port=9898 -v
```

Or if running from a cloned repo:
```bash
cd moo-conformance-tests
pytest tests/ --moo-port=9898 -v
```

## Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--moo-host` | `localhost` | Server hostname |
| `--moo-port` | `7777` | Server port |

## Troubleshooting

### Server won't start
- Check if port is already in use: `netstat -an | grep 9898`
- Ensure required DLLs are present (Windows)
- Check server output for error messages

### Connection refused
- Verify server is running
- Try connecting manually with telnet/nc
- Check firewall settings

### Tests hang
- Server might be waiting for input
- Check if PREFIX/SUFFIX markers are working
- The default timeout is 10 seconds

### Login fails
- Player name is case-sensitive: use `Wizard` not `wizard`
- Check that Test.db has the Wizard player

## Building Toaststunt

If you need to build toaststunt from source:

```bash
git clone https://github.com/lisdude/toaststunt
cd toaststunt

# Linux/Mac
mkdir build && cd build
cmake ..
make

# Windows (MinGW)
mkdir build && cd build
cmake .. -G "MinGW Makefiles"
cmake --build . --config Release
```

See the toaststunt README for detailed build instructions.

## Running Original Ruby Tests

The toaststunt repo includes the original Ruby test suite:

```bash
cd <toaststunt>/test

# Install Ruby dependencies (once)
bundle install

# Run all Ruby tests against running server
bundle exec rake test

# Run specific test
bundle exec ruby -Itests/lib tests/test_algorithms.rb
```

## References

- Toaststunt: https://github.com/lisdude/toaststunt
- MOO Programmer's Manual: https://www.hayseed.net/MOO/manuals/ProgrammersManual.html
