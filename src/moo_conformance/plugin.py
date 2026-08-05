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

import importlib.resources
import os
from pathlib import Path
from typing import Any, Iterator

import pytest
import yaml

from .capabilities import CapabilityManager
from .conditions import declared_literal_skip_reason, declared_runtime_skip_reasons
from .profile_gate import ProfileGateError, load_manifest, validate_manifest_paths
from .runner import YamlTestRunner
from .schema import MooTestCase, MooTestSuite, validate_test_suite
from .server import ManagedServer
from .transport import MooTransport, SocketTransport

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
            "Supports {port}, {db}, {manifest}, and {server_dir} placeholders. "
            "When set, the server is started/stopped automatically."
        ),
    )
    parser.addoption(
        "--server-db",
        default=None,
        help="Path to database file for managed server (default: bundled Test.db)",
    )
    parser.addoption(
        "--server-db-dir",
        default=None,
        help="Directory containing canned DB fixtures referenced by suite.server_db",
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
    parser.addoption(
        "--oracle-profile-manifest",
        default=None,
        help="Path to the oracle profile manifest used to gate managed comparisons",
    )
    parser.addoption(
        "--target-profile-manifest",
        default=None,
        help="Path to the target profile manifest (defaults to managed server {manifest})",
    )
    parser.addoption(
        "--moo-login-script-env",
        default=None,
        help=(
            "Environment variable containing newline-separated raw login commands. "
            "When omitted, the harness uses the default connect command for the requested user."
        ),
    )
    parser.addoption(
        "--moo-skip-standard-properties",
        action="store_true",
        help="Skip automatic Test.db standard property initialization on connect.",
    )
    parser.addoption(
        "--moo-suite-path",
        action="append",
        default=[],
        help="Internal packaged-suite path selected by the moo-conformance CLI.",
    )
    parser.addoption(
        "--fail-on-unexpected-skip",
        action="store_true",
        help="Fail any skip not declared by a literal YAML skip field.",
    )


def _load_login_script(request) -> list[str] | None:
    env_name = request.config.getoption("--moo-login-script-env")
    if env_name is None:
        return None

    raw = os.environ.get(env_name)
    if raw is None or raw == "":
        raise pytest.UsageError(
            f"--moo-login-script-env={env_name} was provided, but that environment "
            "variable is empty"
        )

    commands = [line.strip() for line in raw.splitlines() if line.strip()]
    if not commands:
        raise pytest.UsageError(
            f"--moo-login-script-env={env_name} did not contain any login commands"
        )
    return commands


@pytest.fixture(scope="session")
def managed_server(request) -> Iterator[ManagedServer | None]:
    """Start a managed MOO server if --server-command is provided."""
    command = request.config.getoption("--server-command")
    if command is None:
        yield None
        return

    # A managed server is not always reachable at localhost: a server the
    # harness launches inside WSL must be dialed at the WSL NAT address when
    # Windows->WSL localhost forwarding is unavailable. The explicit
    # --moo-host value names where to reach the server this command starts.
    host = request.config.getoption("--moo-host")

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


@pytest.fixture(scope="session", autouse=True)
def profile_metadata_gate(request, managed_server) -> dict[str, object]:
    """Reject invalid profile comparisons before any tests execute."""
    oracle_manifest = request.config.getoption("--oracle-profile-manifest")
    if oracle_manifest is None:
        return {}

    target_manifest = request.config.getoption("--target-profile-manifest")
    if target_manifest is None:
        if managed_server is None:
            raise pytest.UsageError(
                "--target-profile-manifest is required with --oracle-profile-manifest "
                "unless --server-command is managing a target that writes {manifest}"
            )
        target_manifest = managed_server.manifest_path

    try:
        validate_manifest_paths(oracle_manifest, target_manifest)
    except ProfileGateError as exc:
        raise pytest.UsageError(str(exc)) from exc

    features = load_manifest(target_manifest).get("features")
    return features if isinstance(features, dict) else {}


@pytest.fixture(scope="session")
def moo_server_db_dir(request) -> str | None:
    """Get the directory containing canned DB fixtures, if configured."""
    return request.config.getoption("--server-db-dir")


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
def moo_config(
    moo_server_dir, moo_log_file, moo_server_db_dir, managed_server
) -> dict[str, str | None]:
    """Aggregate config values available for requires.config checks.

    Returns a dict mapping config key names to their values (or None if unavailable).
    """
    return {
        "server_dir": moo_server_dir,
        "log_file": moo_log_file,
        "managed_server": "1" if managed_server is not None else None,
        "server_db_dir": moo_server_db_dir,
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
    login_script = _load_login_script(request)
    ensure_standard_properties = not request.config.getoption("--moo-skip-standard-properties")
    t = SocketTransport(
        host,
        port,
        login_script=login_script,
        ensure_standard_properties=ensure_standard_properties,
    )
    t.connect("wizard")  # Connect ONCE at session start

    yield t

    # Cleanup
    t.disconnect()


@pytest.fixture(scope="session")
def runner(
    transport, moo_log_file, moo_server_dir, managed_server, moo_server_db_dir
) -> YamlTestRunner:
    """Create a test runner with the configured transport."""
    return YamlTestRunner(transport, log_file_path=moo_log_file,
                          server_dir=moo_server_dir, managed_server=managed_server,
                          server_db_dir=moo_server_db_dir)


def discover_yaml_tests(
    test_dir: Path | None = None,
    selected_paths: list[str] | None = None,
) -> list[tuple[Path, MooTestSuite, MooTestCase]]:
    """Discover all YAML test files and their test cases.

    Args:
        test_dir: Directory containing YAML tests. If None, uses bundled tests.
        selected_paths: Paths relative to test_dir. If empty, discovers all tests.

    Returns:
        List of (yaml_path, suite, test_case) tuples
    """
    if test_dir is None:
        test_dir = get_tests_dir()

    test_cases: list[tuple[Path, MooTestSuite, MooTestCase]] = []

    if not test_dir.exists():
        return test_cases

    yaml_files: set[Path] = set()
    for selected_path in selected_paths or ["."]:
        candidate = (test_dir / selected_path).resolve()
        try:
            candidate.relative_to(test_dir.resolve())
        except ValueError as exc:
            raise pytest.UsageError(f"Suite path escapes packaged tests: {selected_path}") from exc

        if candidate.is_file() and candidate.suffix == ".yaml":
            yaml_files.add(candidate)
        elif candidate.is_dir():
            yaml_files.update(candidate.rglob("*.yaml"))
        else:
            raise pytest.UsageError(f"Conformance suite path not found: {selected_path}")

    for yaml_file in sorted(yaml_files):
        try:
            with open(yaml_file, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if data is None:
                raise ValueError("YAML document is empty")

            suite = validate_test_suite(data)

            for test in suite.tests:
                test_cases.append((yaml_file, suite, test))

        except Exception as exc:
            raise pytest.UsageError(
                f"Failed to load conformance suite {yaml_file}: {exc}"
            ) from exc

    return test_cases


def conformance_case_id(
    yaml_path: Path,
    test: MooTestCase,
    tests_dir: Path | None = None,
) -> str:
    """Build the stable case ID from the full YAML path and expanded test name."""
    if tests_dir is None:
        tests_dir = get_tests_dir()
    try:
        relative_path = yaml_path.resolve().relative_to(tests_dir.resolve())
    except ValueError as exc:
        raise pytest.UsageError(
            f"Conformance suite is outside the configured tests directory: {yaml_path}"
        ) from exc
    return f"{relative_path.as_posix()}::{test.name}"


def pytest_generate_tests(metafunc: Any) -> None:
    """Generate test cases from YAML files.

    This is called by pytest during test collection to create
    parametrized test instances from YAML test definitions.
    """
    if "yaml_test_case" in metafunc.fixturenames:
        selected_paths = metafunc.config.getoption("--moo-suite-path")
        test_cases = discover_yaml_tests(selected_paths=selected_paths)

        # Create IDs for each test case
        ids: list[str] = []
        params: list[tuple[MooTestSuite, MooTestCase]] = []

        tests_dir = get_tests_dir()

        for yaml_path, suite, test in test_cases:
            ids.append(conformance_case_id(yaml_path, test, tests_dir))
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


def _skip_declared_yaml_case(suite: MooTestSuite, test: MooTestCase) -> None:
    """Skip a declared test or suite while preserving the more specific test reason."""
    reason = declared_literal_skip_reason(suite, test)
    if reason is not None:
        pytest.skip(reason)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Track provider test results to update capability states."""
    outcome = yield
    report = outcome.get_result()

    if item.config.getoption("--fail-on-unexpected-skip"):
        _reject_unexpected_runtime_skip(item, report)

    if call.when == "call":
        if hasattr(item, 'callspec') and 'yaml_test_case' in item.callspec.params:
            suite, test = item.callspec.params['yaml_test_case']

            provides = test.provides or suite.provides
            if provides:
                if report.passed:
                    capability_manager.mark_passed(provides, item.nodeid)
                elif report.failed:
                    capability_manager.mark_failed(provides, item.nodeid)


def _reject_unexpected_runtime_skip(item, report) -> None:
    if not report.skipped:
        return

    test = None
    if hasattr(item, "callspec") and "yaml_test_case" in item.callspec.params:
        suite, test = item.callspec.params["yaml_test_case"]

    if test is not None:
        actual_reason = _reported_runtime_skip_reason(report.longrepr)
        declared_reasons = declared_runtime_skip_reasons(suite, test)
        assumes = getattr(test, "assumes", ()) or getattr(suite, "assumes", ())
        if assumes:
            can_run, assumption_reason = capability_manager.can_run(assumes)
            if not can_run and assumption_reason is not None:
                declared_reasons.add(assumption_reason)
        if actual_reason in declared_reasons:
            return

    report.outcome = "failed"
    report.longrepr = (
        "Unexpected skip rejected by --fail-on-unexpected-skip: "
        f"{report.longrepr}"
    )


def _reported_runtime_skip_reason(longrepr) -> str | None:
    """Extract pytest's exact runtime skip reason without substring matching."""
    if isinstance(longrepr, tuple) and len(longrepr) >= 3:
        reason = str(longrepr[2])
    else:
        reason = str(longrepr)
    prefix = "Skipped: "
    return reason[len(prefix):] if reason.startswith(prefix) else None


class _UnexpectedCollectionSkipPlugin:
    def pytest_collectreport(self, report) -> None:
        if not report.skipped:
            return
        report.outcome = "failed"
        report.longrepr = (
            "Unexpected collection skip rejected by --fail-on-unexpected-skip: "
            f"{report.longrepr}"
        )


# Register markers
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "conformance: mark test as a MOO conformance test"
    )
    if config.getoption("--fail-on-unexpected-skip"):
        config.pluginmanager.register(
            _UnexpectedCollectionSkipPlugin(),
            "moo-conformance-unexpected-collection-skip",
        )
