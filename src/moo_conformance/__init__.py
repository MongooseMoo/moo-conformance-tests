"""MOO Conformance Test Suite.

A portable conformance test suite for MOO language implementations.

Quick Start:
    # Start your MOO server on port 7777, then:
    pytest --pyargs moo_conformance --moo-port=7777

    # Or from source:
    cd moo-conformance-tests
    uv run pytest tests/ --moo-port=7777

Programmatic Usage:
    from moo_conformance import SocketTransport, YamlTestRunner, discover_yaml_tests

    transport = SocketTransport("localhost", 7777)
    transport.connect("wizard")
    result = transport.execute("1 + 1")
    print(result.value)  # 2
"""

from .transport import MooTransport, SocketTransport, ExecutionResult
from .runner import YamlTestRunner
from .schema import (
    MooTestSuite,
    MooTestCase,
    Expectation,
    TestStep,
    validate_test_suite,
)
from .moo_types import MooError, MooType, ERROR_CODES, TYPE_NAMES
from .plugin import get_tests_dir, get_db_path, discover_yaml_tests

__version__ = "0.1.0"

__all__ = [
    # Transport
    "MooTransport",
    "SocketTransport",
    "ExecutionResult",
    # Runner
    "YamlTestRunner",
    # Schema
    "MooTestSuite",
    "MooTestCase",
    "Expectation",
    "TestStep",
    "validate_test_suite",
    # Types
    "MooError",
    "MooType",
    "ERROR_CODES",
    "TYPE_NAMES",
    # Resource helpers
    "get_tests_dir",
    "get_db_path",
    "discover_yaml_tests",
]
