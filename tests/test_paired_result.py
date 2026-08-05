import json
import xml.etree.ElementTree as ET

import pytest

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
        required_bad_case=None,
    )

    assert result == {
        "schema_version": 1,
        "expected_result": "success",
        "required_bad_case": None,
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
        required_bad_case="suite.yaml::one",
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
            required_bad_case="suite.yaml::one" if expected == "failure" else None,
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
            required_bad_case=None,
        )


@pytest.mark.parametrize("required_bad_case", [None, "", "suite.yaml::other"])
def test_validate_expected_failure_requires_named_bad_case(
    tmp_path, monkeypatch, required_bad_case
) -> None:
    monkeypatch.setattr(
        "moo_conformance.paired_result.packaged_case_ids",
        lambda: {"suite.yaml::one", "suite.yaml::other"},
    )
    report = write_report(
        tmp_path,
        {"suite.yaml::one": "error", "suite.yaml::other": "passed"},
    )

    with pytest.raises(ExecutionLedgerError, match="required bad case"):
        validate_paired_result(
            report,
            expected="failure",
            exit_code=1,
            required_bad_case=required_bad_case,
        )


def test_validate_expected_failure_rejects_unrelated_bad_cases(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "moo_conformance.paired_result.packaged_case_ids",
        lambda: {"suite.yaml::required", "suite.yaml::unrelated"},
    )
    report = write_report(
        tmp_path,
        {"suite.yaml::required": "failed", "suite.yaml::unrelated": "error"},
    )

    with pytest.raises(ExecutionLedgerError, match="unexpected bad cases"):
        validate_paired_result(
            report,
            expected="failure",
            exit_code=1,
            required_bad_case="suite.yaml::required",
        )


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
