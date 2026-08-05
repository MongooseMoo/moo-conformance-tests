import json
from pathlib import Path

import pytest

from moo_conformance.execution_ledger import (
    CaseOutcome,
    ExecutionLedgerError,
    enforce_execution_surface,
    load_baseline,
    packaged_case_ids,
    parse_junit_report,
)


def write_report(path: Path, cases: list[str]) -> None:
    path.write_text(
        "<testsuites><testsuite>" + "".join(cases) + "</testsuite></testsuites>",
        encoding="utf-8",
    )


def case(case_id: str, child: str = "") -> str:
    return (
        '<testcase classname="src.moo_conformance.test_conformance" '
        f'name="test_yaml_conformance[{case_id}]">{child}</testcase>'
    )


def test_parse_junit_report_records_exact_outcomes(tmp_path: Path) -> None:
    report = tmp_path / "report.xml"
    write_report(
        report,
        [
            case("a.yaml::pass"),
            case("a.yaml::skip", '<skipped message="not supported"/>'),
            case("a.yaml::fail", '<failure message="wrong"/>'),
            case("a.yaml::error", '<error message="boom"/>'),
            '<testcase name="ordinary_unit_test"/>',
        ],
    )

    assert parse_junit_report(report) == {
        "a.yaml::pass": CaseOutcome("passed"),
        "a.yaml::skip": CaseOutcome("skipped", "not supported"),
        "a.yaml::fail": CaseOutcome("failed", "wrong"),
        "a.yaml::error": CaseOutcome("error", "boom"),
    }


def test_parse_junit_report_rejects_duplicate_identity(tmp_path: Path) -> None:
    report = tmp_path / "report.xml"
    write_report(report, [case("same.yaml::case"), case("same.yaml::case")])

    with pytest.raises(ExecutionLedgerError, match="duplicate conformance identity"):
        parse_junit_report(report)


def test_profile_union_requires_every_case_to_pass_once() -> None:
    expected = {"suite.yaml::always", "suite.yaml::variant"}
    reports = {
        "on": {
            "suite.yaml::always": CaseOutcome("passed"),
            "suite.yaml::variant": CaseOutcome("skipped", "off only"),
        },
        "off": {
            "suite.yaml::always": CaseOutcome("passed"),
            "suite.yaml::variant": CaseOutcome("passed"),
        },
    }

    ledger = enforce_execution_surface(reports, expected, {})

    assert ledger["packaged_cases"] == 2
    assert ledger["executed_cases"] == 2
    assert ledger["reviewed_never_executed_cases"] == 0


def test_profile_surface_must_be_exact() -> None:
    reports = {"profile": {"suite.yaml::present": CaseOutcome("passed")}}

    with pytest.raises(ExecutionLedgerError, match="inexact surface"):
        enforce_execution_surface(
            reports,
            {"suite.yaml::present", "suite.yaml::missing"},
            {},
        )


@pytest.mark.parametrize("status", ["failed", "error"])
def test_unsuccessful_case_always_fails(status: str) -> None:
    reports = {"profile": {"suite.yaml::case": CaseOutcome(status, "broken")}}

    with pytest.raises(ExecutionLedgerError, match="unsuccessful cases"):
        enforce_execution_surface(reports, {"suite.yaml::case"}, {})


def test_unreviewed_never_executed_case_fails() -> None:
    reports = {
        "profile": {"suite.yaml::case": CaseOutcome("skipped", "unsupported")}
    }

    with pytest.raises(ExecutionLedgerError, match="absent from the reviewed baseline"):
        enforce_execution_surface(reports, {"suite.yaml::case"}, {})


def test_exact_reviewed_skip_is_allowed() -> None:
    reports = {
        "one": {"suite.yaml::case": CaseOutcome("skipped", "unsupported")},
        "two": {"suite.yaml::case": CaseOutcome("skipped", "unsupported")},
    }

    ledger = enforce_execution_surface(
        reports,
        {"suite.yaml::case"},
        {"suite.yaml::case": "unsupported"},
    )

    assert ledger["reviewed_never_executed_cases"] == 1


def test_skip_reason_drift_fails() -> None:
    reports = {
        "profile": {"suite.yaml::case": CaseOutcome("skipped", "new reason")}
    }

    with pytest.raises(ExecutionLedgerError, match="baseline drift"):
        enforce_execution_surface(
            reports,
            {"suite.yaml::case"},
            {"suite.yaml::case": "reviewed reason"},
        )


def test_stale_baseline_entry_fails_after_case_executes() -> None:
    reports = {"profile": {"suite.yaml::case": CaseOutcome("passed")}}

    with pytest.raises(ExecutionLedgerError, match="stale skip baseline"):
        enforce_execution_surface(
            reports,
            {"suite.yaml::case"},
            {"suite.yaml::case": "unsupported"},
        )


def test_load_baseline_rejects_malformed_shape(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"schema_version": 1, "never_executed": []}))

    with pytest.raises(ExecutionLedgerError, match="never_executed"):
        load_baseline(baseline)


def test_reviewed_toast_baseline_contains_only_packaged_cases() -> None:
    baseline = load_baseline(Path("ci/toast-never-executed.json"))

    assert len(baseline) == 40
    assert set(baseline) <= packaged_case_ids()
