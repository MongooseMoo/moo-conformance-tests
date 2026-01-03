"""pytest fixtures and configuration for MOO conformance tests.

This module can be used as a pytest plugin to run conformance tests
against any MOO server.

Provides:
- Command line options (--moo-host, --moo-port)
- Transport fixture (SocketTransport)
- YAML test discovery and parametrization

Usage as pytest plugin:
    # In your conftest.py:
    pytest_plugins = ["moo_conformance.conftest"]

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
        default=7777,
        type=int,
        help="MOO server port (default: 7777)"
    )


@pytest.fixture(scope="session")
def transport(request) -> Iterator[MooTransport]:
    """Create socket transport based on command line options.

    Usage in tests:
        def test_something(transport):
            transport.connect()
            result = transport.execute("1 + 1")
    """
    host = request.config.getoption("--moo-host")
    port = request.config.getoption("--moo-port")
    t = SocketTransport(host, port)

    yield t

    # Cleanup
    t.disconnect()


@pytest.fixture(scope="session")
def runner(transport) -> YamlTestRunner:
    """Create a test runner with the configured transport."""
    return YamlTestRunner(transport)


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


# Register markers
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "conformance: mark test as a MOO conformance test"
    )
