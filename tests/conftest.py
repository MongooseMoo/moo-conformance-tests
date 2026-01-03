"""pytest configuration for running YAML conformance tests.

This file imports fixtures from the moo_conformance package.
The pytest hooks (pytest_addoption, pytest_configure, pytest_generate_tests)
are handled by the package's conftest.py via the pytest11 entry point.
"""

import sys
from pathlib import Path

# Add src to path for development (when not installed)
src_path = Path(__file__).parent.parent / "src"
if src_path.exists():
    sys.path.insert(0, str(src_path))

# Import only fixtures - hooks are registered via entry point
from moo_conformance.plugin import (
    transport,
    runner,
    yaml_test_case,
    get_tests_dir,
    get_db_path,
)

__all__ = [
    "transport",
    "runner",
    "yaml_test_case",
    "get_tests_dir",
    "get_db_path",
]
