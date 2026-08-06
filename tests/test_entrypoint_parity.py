import subprocess
import sys
from pathlib import Path

import moo_conformance
from moo_conformance import plugin

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _write_suite(path: Path, test_name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""name: collision
tests:
  - name: {test_name}
    code: "1"
    expect:
      value: 1
""",
        encoding="utf-8",
    )


def _collect_conformance_node_ids(module: str, *args: str) -> list[str]:
    result = subprocess.run(
        [sys.executable, "-m", module, "--collect-only", "-qq", *args],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return [
        line
        for line in result.stdout.splitlines()
        if "::test_yaml_conformance[" in line
    ]


def test_case_ids_include_full_relative_yaml_path_and_expanded_name(tmp_path: Path) -> None:
    tests_dir = tmp_path / "_tests"
    _write_suite(tests_dir / "first" / "same.yaml", "expanded_one")
    _write_suite(tests_dir / "second" / "same.yaml", "expanded_one")

    discovered = plugin.discover_yaml_tests(tests_dir)
    ids = [
        plugin.conformance_case_id(path, test, tests_dir)
        for path, _suite, test in discovered
    ]

    assert ids == [
        "first/same.yaml::expanded_one",
        "second/same.yaml::expanded_one",
    ]


def test_ordinary_pytest_and_moo_conformance_collect_identical_node_ids() -> None:
    selector = "--moo-suite-path=basic/arithmetic.yaml"

    ordinary = _collect_conformance_node_ids("pytest", selector)
    packaged = _collect_conformance_node_ids("moo_conformance", selector)

    assert ordinary == packaged
    assert ordinary[0] == (
        "src/moo_conformance/test_conformance.py::"
        "test_yaml_conformance[basic/arithmetic.yaml::addition]"
    )


def test_source_advertises_root_pytest_instead_of_a_unit_only_path() -> None:
    package_doc = moo_conformance.__doc__ or ""

    assert "uv run pytest --moo-port=7777" in package_doc
    assert "pytest tests/" not in package_doc


def test_packaged_module_is_the_only_conformance_execution_owner() -> None:
    owners = sorted(
        path.relative_to(REPOSITORY_ROOT).as_posix()
        for path in REPOSITORY_ROOT.rglob("test_conformance.py")
        if ".venv" not in path.parts
    )

    assert owners == ["src/moo_conformance/test_conformance.py"]
