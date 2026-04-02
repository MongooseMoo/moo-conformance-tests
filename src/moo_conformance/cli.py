"""CLI entry point for running tests or generating builtin signature YAMLs."""

import argparse
import sys

import pytest


def main(args: list[str] | None = None) -> int:
    """Run the conformance suite or generate Toast builtin signature YAMLs."""
    if args is None:
        args = sys.argv[1:]

    if "--generate-builtin-io-yamls" in args:
        return _run_builtin_io_generator(args)

    pytest_args = ["--pyargs", "moo_conformance"] + list(args)
    return pytest.main(pytest_args)


def _run_builtin_io_generator(args: list[str]) -> int:
    """Generate builtin signature conformance YAMLs from Toast source."""
    parser = argparse.ArgumentParser(prog="moo-conformance")
    parser.add_argument("--generate-builtin-io-yamls", action="store_true")
    parser.add_argument("--toast-src", required=True, help="Toast repo root or src directory")
    parser.add_argument(
        "--out",
        default="reports/generated_builtin_io",
        help="Directory to write generated YAML files",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow writing into a non-empty output directory",
    )
    parsed = parser.parse_args(args)

    from .builtin_io_generator import generate_builtin_io_yamls

    generated = generate_builtin_io_yamls(
        parsed.toast_src,
        parsed.out,
        overwrite=parsed.overwrite,
    )
    print(f"Generated {len(generated)} builtin YAML test files in {parsed.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
