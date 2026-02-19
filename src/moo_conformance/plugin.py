"""pytest fixtures and configuration for MOO conformance tests.

This module can be used as a pytest plugin to run conformance tests
against any MOO server.

Provides:
- Command line options (--moo-host, --moo-port)
- Transport fixture (SocketTransport)
- YAML test discovery and parametrization

Usage as pytest plugin:
    # In your conftest.py:
    pytest_plugins = ["moo_conformance.plugin"]

    # Or install the package and it auto-registers via entry point

Usage from command line:
    pytest --pyargs moo_conformance --moo-port=7777
"""

import pytest
import yaml
from pathlib import Path
from typing import Iterator
import importlib.resources

from .transport import MooTransport, SocketTransport
from .schema import validate_test_suite, MooTestSuite, MooTestCase
from .runner import YamlTestRunner
from .capabilities import CapabilityManager, CapabilityState
from .server import ManagedServer

# Global capability manager (session-scoped)
capability_manager = CapabilityManager()


def get_tests_dir() -> Path:
    """Get the path to the bundled tests directory.

    Uses importlib.resources to find the _tests directory within the package.
    """
    # Python 3.9+ style
    try:
        files = importlib.resources.files("moo_conformance")
        tests_path = files / "_tests"
        # For traversable resources, we need to get the actual path
        if hasattr(tests_path, "_path"):
            return Path(tests_path._path)
        # Fallback for different resource implementations
        return Path(str(tests_path))
    except (TypeError, AttributeError):
        # Fallback to __file__ based approach
        return Path(__file__).parent / "_tests"


def get_db_path() -> Path:
    """Get the path to the bundled Test.db file."""
    try:
        files = importlib.resources.files("moo_conformance")
        db_path = files / "_db" / "Test.db"
        if hasattr(db_path, "_path"):
            return Path(db_path._path)
        return Path(str(db_path))
    except (TypeError, AttributeError):
        return Path(__file__).parent / "_db" / "Test.db"


def pytest_addoption(parser):
    """Add conformance test command line options."""
    parser.addoption(
        "--moo-host",
        default="localhost",
        help="MOO server host (default: localhost)"
    )
    parser.addoption(
        "--moo-port",
        default=None,
        type=int,
        help="MOO server port (default: 7777)"
    )
    parser.addoption(
        "--server-command",
        default=None,
        help=(
            "Shell command to start a MOO server. "
            "Supports {port} and {db} placeholders. "
            "When set, the server is started/stopped automatically."
        ),
    )
    parser.addoption(
        "--server-db",
        default=None,
        help="Path to database file for managed server (default: bundled Test.db)",
    )
    parser.addoption(
        "--moo-server-dir",
        default=None,
        help="Path to the MOO server's working directory (auto-detected with --server-command)",
    )
    parser.addoption(
        "--moo-log-file",
        default=None,
        help="Path to the MOO server's log file (auto-detected with --server-command)",
    )


@pytest.fixture(scope="session")
def managed_server(request) -> Iterator[ManagedServer | None]:
    """Start a managed MOO server if --server-command is provided."""
    command = request.config.getoption("--server-command")
    if command is None:
        yield None
        return

    host = request.config.getoption("--moo-host")
    if host != "localhost":
        raise pytest.UsageError(
            "--server-command cannot be used with a non-localhost --moo-host"
        )

    port = request.config.getoption("--moo-port")

    db_option = request.config.getoption("--server-db")
    if db_option is not None:
        db_path = Path(db_option)
        if not db_path.exists():
            raise pytest.UsageError(f"Database file not found: {db_path}")
    else:
        db_path = get_db_path()

    server = ManagedServer(command, db_path, port=port, host=host)
    try:
        server.start()
        yield server
    finally:
        server.stop()


@pytest.fixture(scope="session")
def moo_server_dir(request, managed_server) -> str | None:
    """Get the MOO server's working directory.

    Priority: explicit --moo-server-dir > auto-detect from managed server.
    """
    explicit = request.config.getoption("--moo-server-dir")
    if explicit is not None:
        return explicit
    if managed_server is not None and managed_server._temp_dir is not None:
        return managed_server._temp_dir
    return None


@pytest.fixture(scope="session")
def moo_log_file(request, managed_server) -> str | None:
    """Get the MOO server's log file path.

    Priority: explicit --moo-log-file > auto-detect from managed server.
    """
    explicit = request.config.getoption("--moo-log-file")
    if explicit is not None:
        return explicit
    if managed_server is not None and managed_server.log_path is not None:
        return managed_server.log_path
    return None


@pytest.fixture(scope="session")
def moo_config(moo_server_dir, moo_log_file) -> dict[str, str | None]:
    """Aggregate config values available for requires.config checks.

    Returns a dict mapping config key names to their values (or None if unavailable).
    """
    return {
        "server_dir": moo_server_dir,
        "log_file": moo_log_file,
    }


@pytest.fixture(scope="session")
def transport(request, managed_server) -> Iterator[MooTransport]:
    """Create socket transport based on command line options.

    If a managed server is running, uses its port. Otherwise uses
    --moo-host/--moo-port (external server mode).

    Usage in tests:
        def test_something(transport):
            transport.connect()
            result = transport.execute("1 + 1")
    """
    host = request.config.getoption("--moo-host")
    if managed_server is not None:
        port = managed_server.port
    else:
        port = request.config.getoption("--moo-port")
        if port is None:
            port = 7777
    t = SocketTransport(host, port)
    t.connect("wizard")  # Connect ONCE at session start

    yield t

    # Cleanup
    t.disconnect()


@pytest.fixture(scope="session")
def runner(transport, moo_log_file, moo_server_dir) -> YamlTestRunner:
    """Create a test runner with the configured transport."""
    return YamlTestRunner(transport, log_file_path=moo_log_file,
                          server_dir=moo_server_dir)


def discover_yaml_tests(test_dir: Path | None = None) -> list[tuple[Path, MooTestSuite, MooTestCase]]:
    """Discover all YAML test files and their test cases.

    Args:
        test_dir: Directory containing YAML tests. If None, uses bundled tests.

    Returns:
        List of (yaml_path, suite, test_case) tuples
    """
    if test_dir is None:
        test_dir = get_tests_dir()

    test_cases = []

    if not test_dir.exists():
        return test_cases

    for yaml_file in test_dir.rglob("*.yaml"):
        try:
            with open(yaml_file, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if data is None:
                continue

            suite = validate_test_suite(data)

            # Skip entire suite if suite.skip is set
            if suite.skip:
                continue

            for test in suite.tests:
                test_cases.append((yaml_file, suite, test))

        except Exception as e:
            # Log but don't fail on bad YAML files
            print(f"Warning: Failed to load {yaml_file}: {e}")
            continue

    return test_cases


def pytest_generate_tests(metafunc):
    """Generate test cases from YAML files.

    This is called by pytest during test collection to create
    parametrized test instances from YAML test definitions.
    """
    if "yaml_test_case" in metafunc.fixturenames:
        test_cases = discover_yaml_tests()

        # Create IDs for each test case
        ids = []
        params = []

        tests_dir = get_tests_dir()

        for yaml_path, suite, test in test_cases:
            # Create a readable test ID
            try:
                relative_path = yaml_path.relative_to(tests_dir)
                test_id = f"{relative_path.stem}::{test.name}"
            except ValueError:
                test_id = f"{yaml_path.stem}::{test.name}"

            ids.append(test_id)
            params.append((suite, test))

        metafunc.parametrize("yaml_test_case", params, ids=ids)


@pytest.fixture
def yaml_test_case():
    """Placeholder fixture for parametrized YAML test cases.

    The actual value is provided by pytest_generate_tests.
    """
    pass


def pytest_collection_modifyitems(session, config, items):
    """Reorder tests to run providers before consumers."""
    providers = []
    consumers = []
    normal = []

    for item in items:
        # Get test case from parametrized fixture
        if hasattr(item, 'callspec') and 'yaml_test_case' in item.callspec.params:
            suite, test = item.callspec.params['yaml_test_case']

            # Check for provides (test-level or suite-level)
            provides = test.provides or suite.provides
            if provides:
                providers.append(item)
                capability_manager.register_provider(provides, item.nodeid)
                continue

            # Check for assumes (test-level or suite-level)
            assumes = test.assumes or suite.assumes
            if assumes:
                consumers.append(item)
                continue

        normal.append(item)

    items[:] = providers + normal + consumers


def pytest_runtest_setup(item):
    """Skip test if assumed capabilities aren't verified."""
    if hasattr(item, 'callspec') and 'yaml_test_case' in item.callspec.params:
        suite, test = item.callspec.params['yaml_test_case']

        # Get assumes from test or suite
        assumes = test.assumes or suite.assumes
        if assumes:
            can_run, reason = capability_manager.can_run(assumes)
            if not can_run:
                pytest.skip(reason)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Track provider test results to update capability states."""
    outcome = yield
    report = outcome.get_result()

    if call.when == "call":
        if hasattr(item, 'callspec') and 'yaml_test_case' in item.callspec.params:
            suite, test = item.callspec.params['yaml_test_case']

            provides = test.provides or suite.provides
            if provides:
                if report.passed:
                    capability_manager.mark_passed(provides, item.nodeid)
                elif report.failed:
                    capability_manager.mark_failed(provides, item.nodeid)


# Register markers
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "conformance: mark test as a MOO conformance test"
    )
