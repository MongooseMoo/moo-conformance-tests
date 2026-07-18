"""CLI entry point for running tests or generating builtin reports."""

import argparse
import sys
from pathlib import PurePosixPath

import pytest


def main(args: list[str] | None = None) -> int:
    """Run the conformance suite or generate Toast builtin reports."""
    if args is None:
        args = sys.argv[1:]

    if "--generate-builtin-io-yamls" in args:
        return _run_builtin_io_generator(args)
    if "--generate-builtin-coverage-report" in args:
        return _run_builtin_coverage_report(args)

    selectors, forwarded_args = _split_suite_selectors(args)
    pytest_args = ["--pyargs", "moo_conformance"]
    pytest_args.extend(f"--moo-suite-path={selector}" for selector in selectors)
    pytest_args.extend(forwarded_args)
    return pytest.main(pytest_args)


def _split_suite_selectors(args: list[str]) -> tuple[list[str], list[str]]:
    """Separate advertised YAML FILE_OR_DIR selectors from pytest arguments."""
    selectors: list[str] = []
    forwarded: list[str] = []
    for arg in args:
        selector = _normalize_suite_selector(arg)
        if selector is None:
            forwarded.append(arg)
        else:
            selectors.append(selector)
    return selectors, forwarded


def _normalize_suite_selector(arg: str) -> str | None:
    normalized = arg.replace("\\", "/")
    parts = PurePosixPath(normalized).parts
    if "_tests" not in parts:
        return None

    marker = parts.index("_tests")
    relative_parts = parts[marker + 1 :]
    if any(part in ("", ".", "..") for part in relative_parts):
        raise SystemExit(f"invalid conformance suite path: {arg}")
    return PurePosixPath(*relative_parts).as_posix() if relative_parts else "."


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


def _run_builtin_coverage_report(args: list[str]) -> int:
    """Generate a Toast builtin call-shape coverage report."""
    parser = argparse.ArgumentParser(prog="moo-conformance")
    parser.add_argument("--generate-builtin-coverage-report", action="store_true")
    parser.add_argument("--toast-src", required=True, help="Toast repo root or src directory")
    parser.add_argument(
        "--tests-dir",
        default="src/moo_conformance/_tests",
        help="Directory containing YAML conformance suites",
    )
    parser.add_argument(
        "--out",
        default="reports/toast-builtin-coverage.md",
        help="Markdown report path",
    )
    parsed = parser.parse_args(args)

    from .builtin_coverage import generate_builtin_coverage_report

    report = generate_builtin_coverage_report(
        parsed.toast_src,
        parsed.tests_dir,
        parsed.out,
    )
    print(f"Generated builtin coverage report at {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
