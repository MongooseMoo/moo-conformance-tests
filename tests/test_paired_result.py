import json
import xml.etree.ElementTree as ET

import pytest

import moo_conformance.paired_result as paired_result
from moo_conformance.execution_ledger import ExecutionLedgerError
from moo_conformance.paired_result import _load_expected_ids, validate_paired_result


def write_report(tmp_path, outcomes):
    root = ET.Element("testsuites")
    suite = ET.SubElement(root, "testsuite")
    for case_id, status in outcomes.items():
        case = ET.SubElement(
            suite,
            "testcase",
            name=f"test_yaml_conformance[{case_id}]",
        )
        if status != "passed":
            element_name = "failure" if status == "failed" else status
            ET.SubElement(case, element_name, message=f"{status} reason")
    report = tmp_path / "paired.xml"
    ET.ElementTree(root).write(report, encoding="unicode")
    return report


def test_validate_success_requires_exact_nonempty_passing_surface(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "moo_conformance.paired_result.packaged_case_ids",
        lambda: {"suite.yaml::one", "suite.yaml::two"},
    )
    report = write_report(
        tmp_path,
        {"suite.yaml::one": "passed", "suite.yaml::two": "skipped"},
    )

    result = validate_paired_result(
        report,
        expected="success",
        exit_code=0,
        required_bad_cases=[],
    )

    assert result == {
        "schema_version": 2,
        "expected_result": "success",
        "required_bad_cases": [],
        "exit_code": 0,
        "packaged_cases": 2,
        "passed": 1,
        "skipped": 1,
        "failed": 0,
        "error": 0,
    }


def test_validate_expected_failure_requires_bad_outcome_and_nonzero_exit(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "moo_conformance.paired_result.packaged_case_ids",
        lambda: {"suite.yaml::one"},
    )
    report = write_report(tmp_path, {"suite.yaml::one": "error"})

    result = validate_paired_result(
        report,
        expected="failure",
        exit_code=1,
        required_bad_cases=["suite.yaml::one"],
    )

    assert result["error"] == 1
    assert result["expected_result"] == "failure"


@pytest.mark.parametrize(
    ("outcomes", "expected", "exit_code", "message"),
    [
        ({"suite.yaml::one": "passed"}, "success", 1, "expected success"),
        ({"suite.yaml::one": "failed"}, "success", 1, "expected success"),
        ({"suite.yaml::one": "passed"}, "failure", 0, "expected failure"),
        ({"suite.yaml::one": "passed"}, "failure", 1, "expected failure"),
        ({"suite.yaml::one": "error"}, "failure", 2, "expected failure"),
    ],
)
def test_validate_rejects_result_mismatch(
    tmp_path, monkeypatch, outcomes, expected, exit_code, message
) -> None:
    monkeypatch.setattr(
        "moo_conformance.paired_result.packaged_case_ids",
        lambda: {"suite.yaml::one"},
    )
    report = write_report(tmp_path, outcomes)

    with pytest.raises(ExecutionLedgerError, match=message):
        validate_paired_result(
            report,
            expected=expected,
            exit_code=exit_code,
            required_bad_cases=["suite.yaml::one"] if expected == "failure" else [],
        )


def test_validate_rejects_inexact_surface(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "moo_conformance.paired_result.packaged_case_ids",
        lambda: {"suite.yaml::one", "suite.yaml::missing"},
    )
    report = write_report(tmp_path, {"suite.yaml::one": "passed"})

    with pytest.raises(ExecutionLedgerError, match="inexact surface"):
        validate_paired_result(
            report,
            expected="success",
            exit_code=0,
            required_bad_cases=[],
        )


def test_validate_expected_failure_requires_nonempty_declared_set(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "moo_conformance.paired_result.packaged_case_ids",
        lambda: {"suite.yaml::one", "suite.yaml::other"},
    )
    report = write_report(
        tmp_path,
        {"suite.yaml::one": "error", "suite.yaml::other": "passed"},
    )

    with pytest.raises(ExecutionLedgerError, match="non-empty required_bad_cases"):
        validate_paired_result(
            report,
            expected="failure",
            exit_code=1,
            required_bad_cases=[],
        )


def test_validate_expected_success_rejects_nonempty_declared_set(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "moo_conformance.paired_result.packaged_case_ids",
        lambda: {"suite.yaml::one"},
    )
    report = write_report(tmp_path, {"suite.yaml::one": "passed"})

    with pytest.raises(ExecutionLedgerError, match="empty required_bad_cases"):
        validate_paired_result(
            report,
            expected="success",
            exit_code=0,
            required_bad_cases=["suite.yaml::one"],
        )


def test_validate_expected_failure_accepts_exact_multiple_bad_cases(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "moo_conformance.paired_result.packaged_case_ids",
        lambda: {"suite.yaml::first", "suite.yaml::second", "suite.yaml::passing"},
    )
    report = write_report(
        tmp_path,
        {
            "suite.yaml::first": "failed",
            "suite.yaml::second": "error",
            "suite.yaml::passing": "passed",
        },
    )

    result = validate_paired_result(
        report,
        expected="failure",
        exit_code=1,
        required_bad_cases=["suite.yaml::second", "suite.yaml::first"],
    )

    assert result["required_bad_cases"] == ["suite.yaml::first", "suite.yaml::second"]


@pytest.mark.parametrize(
    ("required_bad_cases", "message"),
    [
        (["suite.yaml::failed", "suite.yaml::failed"], "duplicates"),
        (["suite.yaml::unknown"], "unknown"),
        ([""], "non-empty strings"),
        (["suite.yaml::failed", 7], "non-empty strings"),
    ],
)
def test_validate_rejects_duplicate_malformed_or_unknown_declarations(
    tmp_path, monkeypatch, required_bad_cases, message
) -> None:
    expected_ids = {"suite.yaml::failed", "suite.yaml::passing"}
    monkeypatch.setattr(
        "moo_conformance.paired_result.packaged_case_ids",
        lambda: expected_ids,
    )
    report = write_report(
        tmp_path,
        {"suite.yaml::failed": "failed", "suite.yaml::passing": "passed"},
    )

    with pytest.raises(ExecutionLedgerError, match=message):
        validate_paired_result(
            report,
            expected="failure",
            exit_code=1,
            required_bad_cases=required_bad_cases,
        )


@pytest.mark.parametrize(
    ("required_bad_cases", "message"),
    [
        (["suite.yaml::first"], "extra observed"),
        (["suite.yaml::first", "suite.yaml::second", "suite.yaml::passing"], "missing observed"),
    ],
)
def test_validate_rejects_inexact_observed_failure_set(
    tmp_path, monkeypatch, required_bad_cases, message
) -> None:
    expected_ids = {"suite.yaml::first", "suite.yaml::second", "suite.yaml::passing"}
    monkeypatch.setattr(
        "moo_conformance.paired_result.packaged_case_ids",
        lambda: expected_ids,
    )
    report = write_report(
        tmp_path,
        {
            "suite.yaml::first": "failed",
            "suite.yaml::second": "error",
            "suite.yaml::passing": "passed",
        },
    )

    with pytest.raises(ExecutionLedgerError, match=message):
        validate_paired_result(
            report,
            expected="failure",
            exit_code=1,
            required_bad_cases=required_bad_cases,
        )


@pytest.mark.parametrize(
    "payload",
    ["", "not json", '"suite.yaml::one,suite.yaml::two"', "{}", "null", "[1]", '[""]'],
)
def test_parse_required_bad_cases_rejects_malformed_payload(payload) -> None:
    with pytest.raises(ExecutionLedgerError, match="required_bad_cases"):
        paired_result._parse_required_bad_cases(payload)


def test_parse_required_bad_cases_preserves_json_array_for_validation() -> None:
    assert paired_result._parse_required_bad_cases('["suite.yaml::two", "suite.yaml::one"]') == [
        "suite.yaml::two",
        "suite.yaml::one",
    ]


@pytest.mark.parametrize("content", ["[]", '["duplicate", "duplicate"]', '{}', 'null'])
def test_load_expected_ids_rejects_invalid_lists(tmp_path, content) -> None:
    path = tmp_path / "expected.json"
    path.write_text(content)

    with pytest.raises(ExecutionLedgerError):
        _load_expected_ids(path)


def test_load_expected_ids_accepts_unique_nonempty_list(tmp_path) -> None:
    path = tmp_path / "expected.json"
    path.write_text(json.dumps(["suite.yaml::one", "suite.yaml::two"]))

    assert _load_expected_ids(path) == {"suite.yaml::one", "suite.yaml::two"}
