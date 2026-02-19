"""CLI entry point for running MOO conformance tests.

Usage:
    moo-conformance --moo-port=9898
    moo-conformance --moo-port=9898 -k "arithmetic" -v
    uv tool run moo-conformance-tests --moo-port=9898
"""

import sys

import pytest


def main(args: list[str] | None = None) -> int:
    """Run the conformance test suite via pytest.

    Automatically adds --pyargs moo_conformance so pytest discovers
    the bundled YAML tests. All other arguments are passed through.
    """
    if args is None:
        args = sys.argv[1:]

    pytest_args = ["--pyargs", "moo_conformance"] + list(args)
    return pytest.main(pytest_args)


if __name__ == "__main__":
    sys.exit(main())
