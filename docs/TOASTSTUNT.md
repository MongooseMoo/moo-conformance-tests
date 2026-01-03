# Running Conformance Tests Against Toaststunt

This documents how to run cow_py's conformance tests against the actual Toaststunt C implementation to verify expected behavior.

## Prerequisites

1. **Toaststunt Windows build** at `/c/Users/Q/src/toaststunt/test/`
   - `moo.exe` - the compiled server
   - `Test.db` - minimal test database
   - Required DLLs: `argon2.dll`, `nettle-8.dll`, `libgcc_s_seh-1.dll`, `libstdc++-6.dll`, `libwinpthread-1.dll`

2. **cow_py** with conformance test infrastructure

## How It Works

The conformance tests support two transports:

| Transport | Description | Use Case |
|-----------|-------------|----------|
| `direct` | Uses cow_py's VM in-process | Default - tests our implementation |
| `socket` | TCP connection to running MOO server | Tests against toaststunt reference |

Both transports use the same protocol:
1. Connect and authenticate (`connect <user>`)
2. Set PREFIX/SUFFIX markers for response parsing
3. Execute code via `; <code>` command (eval shortcut)
4. Parse eval result: `{0, errors}`, `{1, value}`, or `{2, {error, msg, val}}`

## Step 1: Start Toaststunt Server

Open a terminal in the toaststunt test directory:

```bash
cd /c/Users/Q/src/toaststunt/test

# Option A: Using batch file
./run_moo.bat

# Option B: Direct command
# moo.exe syntax: moo.exe <indb> <outdb> <port>
./moo.exe Test.db Test.out.db 9898

# Option C: PowerShell with logging
powershell -File run_server.ps1
```

The server should start and listen on port **9898**.

**Verify it's running:**
```bash
# Quick connection test
echo "connect wizard" | nc localhost 9898
```

## Step 2: Run Conformance Tests

From the cow_py directory:

```bash
cd /c/Users/Q/code/cow_py

# Run all conformance tests against toaststunt
uv run pytest tests/conformance/ -v --transport=socket --moo-port=9898

# Run specific test file
uv run pytest tests/conformance/ -v --transport=socket --moo-port=9898 -k "arithmetic"

# Run single test
uv run pytest tests/conformance/ -v --transport=socket --moo-port=9898 -k "arithmetic::addition"
```

## Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--transport` | `socket` | Transport type: `direct` or `socket` |
| `--moo-host` | `localhost` | Server hostname for socket transport |
| `--moo-port` | `7777` | Server port for socket transport |
| `--db-path` | `tests/conformance/Test.db` | Database for direct transport |

## Comparing Results

Run tests against both implementations to find discrepancies:

```bash
# Save toaststunt results
uv run pytest tests/conformance/ -v --transport=socket --moo-port=9898 2>&1 | tee reports/toaststunt-results.txt

# Save cow_py results
uv run pytest tests/conformance/ -v 2>&1 | tee reports/cowpy-results.txt

# Compare
diff reports/toaststunt-results.txt reports/cowpy-results.txt
```

## Toaststunt Test Configuration

The toaststunt Ruby test suite uses `test.yml` for configuration:

```yaml
host: localhost
port: 9898
verbose: false
ownership_quota: false
64bit: true
```

Our socket transport reads from command line args, not this file.

## Toaststunt Directory Structure

```
/c/Users/Q/src/toaststunt/test/
├── moo.exe              # Windows build
├── Test.db              # Minimal test database
├── test.yml             # Ruby test config (port 9898)
├── run_moo.bat          # Windows batch launcher
├── run_server.ps1       # PowerShell launcher with logging
├── server.log           # Server output log
├── tests/               # Ruby test files (test_*.rb)
│   ├── lib/             # Ruby test support
│   │   └── moo_support.rb  # Connection handling
│   ├── test_algorithms.rb
│   ├── test_create.rb
│   └── ...
└── *.dll                # Required Windows DLLs
```

## Troubleshooting

### Server won't start
- Check if port 9898 is already in use: `netstat -an | grep 9898`
- Ensure DLLs are present in the test directory
- Check `server.log` for error messages

### Connection refused
- Verify server is running: `ps aux | grep moo`
- Try connecting manually: `nc localhost 9898`
- Check firewall settings

### Tests hang
- Server might be waiting for input
- Check if PREFIX/SUFFIX markers are working
- Add timeout: `--timeout=30`

### Unexpected results
- Toaststunt may have different behavior than documented
- Check the Ruby test files for expected behavior
- Compare with `test.in`/`test.out` files in `tests/basic/`

## Building Toaststunt (if needed)

If you need to rebuild toaststunt:

```bash
cd /c/Users/Q/src/toaststunt

# Configure (only once)
mkdir -p build && cd build
cmake .. -G "MinGW Makefiles"

# Build
cmake --build . --config Release

# Copy to test directory
cp moo.exe ../test/
```

## Current Results (Dec 2025)

| Transport | Passed | Failed | Skipped |
|-----------|--------|--------|---------|
| `direct` (cow_py) | 945 | 0 | 165 |
| `socket` (toaststunt) | 579 | 381 | 165 |

The socket transport has lower pass rate due to:
1. **Output format differences** - moocode_parsing tests check disassembly/decompile output which differs
2. **Parser limitations** - SocketTransport's response parsing may not handle all edge cases
3. **Test infrastructure** - Some test_runner.py tests only work with DirectTransport

The socket transport is primarily useful for verifying specific builtin behavior, not comprehensive conformance.

## References

- Toaststunt source: `/c/Users/Q/src/toaststunt/`
- Ruby tests: `/c/Users/Q/src/toaststunt/test/tests/test_*.rb`
- Test support lib: `/c/Users/Q/src/toaststunt/test/tests/lib/moo_support.rb`
- cow_py transport: `/c/Users/Q/code/cow_py/tests/conformance/transport.py`

## Running Ruby Tests (Reference)

The original Ruby tests are the authoritative reference for expected behavior:

```bash
cd /c/Users/Q/src/toaststunt/test

# Install Ruby dependencies (once)
bundle install

# Run all Ruby tests against running server
bundle exec ruby -r rubygems -Itests/lib tests/test_anonymous.rb

# Or run via Makefile
make test_anonymous.rb

# Run all tests
make tests
```

Ruby test files are at `/c/Users/Q/src/toaststunt/test/tests/test_*.rb`.

## Investigation Findings (Dec 2025)

When debugging test failures against toaststunt, discovered:

1. **Test.db has `$anonymous` but NOT `$anon`** - Our tests incorrectly used `$anon`, causing E_PROPNF errors. Fixed by changing to `$anonymous` (matching Ruby tests).

2. **Transport property setup runs as user, not wizard** - The `_ensure_standard_properties()` connects as the test user (often `programmer`), then tries to add properties to #0, which fails with E_PERM. The error is silently swallowed by backtick error handling.

3. **Results improved after fix:**
   - Before: 141 failed, 968 passed
   - After: 109 failed, 1000 passed (32 tests fixed)

Remaining failures are mostly in areas needing specific DB setup or server features:
- `primitives` (16) - prototype tests need specific DB objects
- `objects` (15) - setup/permission issues  
- `algorithms` (15) - hash/crypt format differences
- `task_local` (11) - suspend/fork need server features
- `exec` (9) - exec() builtin needs special setup
