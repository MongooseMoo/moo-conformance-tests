"""MOO Conformance Test Suite.

A portable conformance test suite for MOO language implementations.

Quick Start:
    # Start your MOO server on port 7777, then:
    pytest --pyargs moo_conformance --moo-port=7777

    # Or from source:
    cd moo-conformance-tests
    uv run pytest --moo-port=7777

Programmatic Usage:
    from moo_conformance import SocketTransport, YamlTestRunner, discover_yaml_tests

    transport = SocketTransport("localhost", 7777)
    transport.connect("wizard")
    result = transport.execute("1 + 1")
    print(result.value)  # 2
"""

from .builtin_io_generator import extract_builtin_specs, generate_builtin_io_yamls
from .moo_types import ERROR_CODES, TYPE_NAMES, MooError, MooType
from .plugin import discover_yaml_tests, get_db_path, get_tests_dir
from .runner import YamlTestRunner
from .schema import (
    Expectation,
    MooTestCase,
    MooTestSuite,
    TestStep,
    validate_test_suite,
)
from .transport import ExecutionResult, MooTransport, SocketTransport

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
    "extract_builtin_specs",
    "generate_builtin_io_yamls",
]
