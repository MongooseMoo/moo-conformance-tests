"""Regression coverage for exact suite selection and strict skip handling."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from moo_conformance import cli, plugin


def _write_suite(path: Path, suite_name: str, test_name: str, *, skip: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    skip_line = f"    skip: {skip!r}\n" if skip is not None else ""
    path.write_text(
        f"""name: {suite_name}
tests:
  - name: {test_name}
{skip_line}    code: "1"
    expect:
      value: 1
""",
        encoding="utf-8",
    )


def test_cli_forwards_exact_file_and_directory_selectors(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []

    def capture(args: list[str]) -> int:
        captured.extend(args)
        return 0

    monkeypatch.setattr(cli.pytest, "main", capture)

    result = cli.main(
        [
            "src/moo_conformance/_tests/basic/one.yaml",
            "-q",
            "src/moo_conformance/_tests/language",
        ]
    )

    assert result == 0
    assert captured == [
        "--pyargs",
        "moo_conformance",
        "--moo-suite-path=basic/one.yaml",
        "--moo-suite-path=language",
        "-q",
    ]


def test_exact_yaml_file_does_not_collect_another(tmp_path: Path) -> None:
    tests_dir = tmp_path / "_tests"
    _write_suite(tests_dir / "basic" / "one.yaml", "one", "only_one")
    _write_suite(tests_dir / "basic" / "two.yaml", "two", "not_selected")

    discovered = plugin.discover_yaml_tests(tests_dir, ["basic/one.yaml"])

    assert [(path.name, test.name) for path, _suite, test in discovered] == [
        ("one.yaml", "only_one")
    ]


def test_directory_collects_every_and_only_descendant_suite(tmp_path: Path) -> None:
    tests_dir = tmp_path / "_tests"
    _write_suite(tests_dir / "selected" / "one.yaml", "one", "first")
    _write_suite(tests_dir / "selected" / "nested" / "two.yaml", "two", "second")
    _write_suite(tests_dir / "other" / "three.yaml", "three", "outside")

    discovered = plugin.discover_yaml_tests(tests_dir, ["selected"])

    assert {(path.name, test.name) for path, _suite, test in discovered} == {
        ("one.yaml", "first"),
        ("two.yaml", "second"),
    }


def test_literal_yaml_skip_remains_allowed(tmp_path: Path) -> None:
    tests_dir = tmp_path / "_tests"
    _write_suite(tests_dir / "literal.yaml", "literal", "allowed", skip="documented")
    [(_path, suite, test)] = plugin.discover_yaml_tests(tests_dir, ["literal.yaml"])
    item = SimpleNamespace(
        callspec=SimpleNamespace(params={"yaml_test_case": (suite, test)})
    )
    report = SimpleNamespace(skipped=True, outcome="skipped", longrepr="documented")

    plugin._reject_unexpected_runtime_skip(item, report)

    assert report.outcome == "skipped"


def test_matching_declared_conditional_skip_remains_allowed() -> None:
    suite = SimpleNamespace(skip=False)
    test = SimpleNamespace(skip=False, skip_if="missing builtin.background_test")
    item = SimpleNamespace(
        callspec=SimpleNamespace(params={"yaml_test_case": (suite, test)})
    )
    report = SimpleNamespace(
        skipped=True,
        outcome="skipped",
        longrepr=("test_conformance.py", 127, "Skipped: Requires builtin: background_test"),
    )

    plugin._reject_unexpected_runtime_skip(item, report)

    assert report.outcome == "skipped"


def test_declared_conditional_skip_does_not_allow_unrelated_runtime_skip() -> None:
    suite = SimpleNamespace(skip=False)
    test = SimpleNamespace(skip=False, skip_if="missing builtin.background_test")
    item = SimpleNamespace(
        callspec=SimpleNamespace(params={"yaml_test_case": (suite, test)})
    )
    report = SimpleNamespace(
        skipped=True,
        outcome="skipped",
        longrepr=("runner.py", 1, "Skipped: runtime condition"),
    )

    plugin._reject_unexpected_runtime_skip(item, report)

    assert report.outcome == "failed"


@pytest.mark.parametrize(
    ("reason", "when"),
    [
        ("fixture unavailable", "setup"),
        ("profile unavailable", "setup"),
        ("capability unavailable", "setup"),
        ("runtime condition", "call"),
    ],
)
def test_nonliteral_skip_categories_fail(reason: str, when: str) -> None:
    suite = SimpleNamespace(skip=False)
    test = SimpleNamespace(skip=False, skip_if=None)
    item = SimpleNamespace(
        callspec=SimpleNamespace(params={"yaml_test_case": (suite, test)})
    )
    report = SimpleNamespace(skipped=True, outcome="skipped", longrepr=reason, when=when)

    plugin._reject_unexpected_runtime_skip(item, report)

    assert report.outcome == "failed"
    assert reason in report.longrepr


def test_collection_skip_fails() -> None:
    report = SimpleNamespace(skipped=True, outcome="skipped", longrepr="collection condition")

    plugin._UnexpectedCollectionSkipPlugin().pytest_collectreport(report)

    assert report.outcome == "failed"
    assert "collection condition" in report.longrepr
