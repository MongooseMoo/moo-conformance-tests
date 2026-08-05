import json
import xml.etree.ElementTree as ET

import pytest

import moo_conformance.paired_result as paired_result
from moo_conformance.admission import ADMISSION_PROBE_INVENTORY
from moo_conformance.execution_ledger import ExecutionLedgerError
from moo_conformance.paired_result import _load_expected_ids, validate_paired_result

TEST_CONTEXT = "test:paired-context"


def write_report(tmp_path, outcomes):
    root = ET.Element("testsuites")
    suite = ET.SubElement(root, "testsuite")
    for case_id, status in outcomes.items():
        case = ET.SubElement(suite, "testcase", name=f"test_yaml_conformance[{case_id}]")
        if status != "passed":
            element_name = "failure" if status == "failed" else status
            ET.SubElement(case, element_name, message=f"{status} reason")
    report = tmp_path / "paired.xml"
    ET.ElementTree(root).write(report, encoding="unicode")
    return report


def write_admission(tmp_path, statuses=None, context=TEST_CONTEXT):
    statuses = statuses or {}
    probes = []
    for identity in ADMISSION_PROBE_INVENTORY:
        status = statuses.get(identity, "passed")
        if status == "passed":
            probe = {
                "identity": identity,
                "status": status,
                "value": True,
                "prerequisite_blocked_by": [],
            }
        elif status in {"failed", "error"}:
            probe = {
                "identity": identity,
                "status": status,
                "detail": f"{status} detail",
                "prerequisite_blocked_by": [],
            }
        else:
            probe = {
                "identity": identity,
                "status": "blocked",
                "prerequisite_blocked_by": ["admission::option.OUTBOUND_NETWORK"],
            }
        probes.append(probe)
    path = tmp_path / "admission.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "phase": "admission",
                "context": context,
                "probes": probes,
            }
        )
    )
    return path


def validate_packaged(tmp_path, outcomes, **overrides):
    arguments = {
        "admission_path": write_admission(tmp_path),
        "admission_context": TEST_CONTEXT,
        "report_path": write_report(tmp_path, outcomes),
        "expected": "success",
        "expected_phase": "packaged",
        "admission_exit_code": 0,
        "packaged_exit_code": 0,
        "required_bad_identities": [],
        "expected_case_ids": set(outcomes),
    }
    arguments.update(overrides)
    return validate_paired_result(**arguments)


def test_validate_packaged_success_requires_exact_nonempty_surface(tmp_path) -> None:
    result = validate_packaged(
        tmp_path,
        {"suite.yaml::one": "passed", "suite.yaml::two": "skipped"},
    )

    assert result == {
        "schema_version": 3,
        "phase": "packaged",
        "expected_result": "success",
        "declared_bad_identities": [],
        "observed_bad_identities": [],
        "admission": {
            "schema_version": 2,
            "context": TEST_CONTEXT,
            "inventory": list(ADMISSION_PROBE_INVENTORY),
            "passed": 4,
            "failed": 0,
            "error": 0,
            "blocked": 0,
            "exit_code": 0,
        },
        "packaged": {
            "exit_code": 0,
            "packaged_cases": 2,
            "passed": 1,
            "skipped": 1,
            "failed": 0,
            "error": 0,
        },
    }


def test_validate_packaged_failure_preserves_exact_set_semantics(tmp_path) -> None:
    result = validate_packaged(
        tmp_path,
        {
            "suite.yaml::first": "failed",
            "suite.yaml::second": "error",
            "suite.yaml::passing": "passed",
        },
        expected="failure",
        packaged_exit_code=1,
        required_bad_identities=["suite.yaml::second", "suite.yaml::first"],
    )

    assert result["observed_bad_identities"] == [
        "suite.yaml::first",
        "suite.yaml::second",
    ]
    assert result["declared_bad_identities"] == result["observed_bad_identities"]


def test_validate_packaged_rejects_missing_or_extra_surface(tmp_path) -> None:
    with pytest.raises(ExecutionLedgerError, match="inexact surface"):
        validate_packaged(
            tmp_path,
            {"suite.yaml::one": "passed"},
            expected_case_ids={"suite.yaml::one", "suite.yaml::missing"},
        )


def test_validate_packaged_rejects_admission_from_another_candidate_context(
    tmp_path,
) -> None:
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(ExecutionLedgerError, match="context mismatch"):
        validate_packaged(
            tmp_path,
            {"suite.yaml::one": "passed"},
            admission_path=write_admission(other, context="other:candidate"),
        )


@pytest.mark.parametrize(
    ("declared", "message"),
    [
        (["suite.yaml::first"], "extra observed"),
        (
            ["suite.yaml::first", "suite.yaml::second", "suite.yaml::passing"],
            "missing observed",
        ),
    ],
)
def test_validate_packaged_rejects_inexact_failure_identity_set(
    tmp_path, declared, message
) -> None:
    with pytest.raises(ExecutionLedgerError, match=message):
        validate_packaged(
            tmp_path,
            {
                "suite.yaml::first": "failed",
                "suite.yaml::second": "error",
                "suite.yaml::passing": "passed",
            },
            expected="failure",
            packaged_exit_code=1,
            required_bad_identities=declared,
        )


@pytest.mark.parametrize(
    ("expected", "exit_code", "status", "message"),
    [
        ("success", 1, "passed", "expected success"),
        ("success", 1, "failed", "expected success"),
        ("failure", 0, "failed", "expected packaged failure"),
        ("failure", 1, "passed", "expected packaged failure"),
        ("failure", 2, "error", "expected packaged failure"),
    ],
)
def test_validate_packaged_rejects_exit_or_result_mismatch(
    tmp_path, expected, exit_code, status, message
) -> None:
    required = ["suite.yaml::one"] if expected == "failure" else []
    with pytest.raises(ExecutionLedgerError, match=message):
        validate_packaged(
            tmp_path,
            {"suite.yaml::one": status},
            expected=expected,
            packaged_exit_code=exit_code,
            required_bad_identities=required,
        )


def test_validate_admission_failure_uses_exact_failed_error_set_and_blocked_evidence(
    tmp_path,
) -> None:
    failed = "admission::option.OUTBOUND_NETWORK"
    admission = write_admission(
        tmp_path,
        {
            failed: "failed",
            "admission::feature.connectable_listener_port": "blocked",
        },
    )

    result = validate_paired_result(
        admission_path=admission,
        admission_context=TEST_CONTEXT,
        report_path=None,
        expected="failure",
        expected_phase="admission",
        admission_exit_code=1,
        packaged_exit_code=None,
        required_bad_identities=[failed],
        expected_case_ids={"suite.yaml::never-ran"},
    )

    assert result["phase"] == "admission"
    assert result["observed_bad_identities"] == [failed]
    assert result["admission"]["blocked"] == 1
    assert result["packaged"] is None


def test_validate_admission_failure_rejects_inexact_failed_error_set(tmp_path) -> None:
    admission = write_admission(
        tmp_path,
        {
            "admission::feature.ephemeral_listen": "error",
            "admission::option.PROMOTE_NUMBERS": "failed",
        },
    )

    with pytest.raises(ExecutionLedgerError, match="extra observed"):
        validate_paired_result(
            admission_path=admission,
            admission_context=TEST_CONTEXT,
            report_path=None,
            expected="failure",
            expected_phase="admission",
            admission_exit_code=1,
            packaged_exit_code=None,
            required_bad_identities=["admission::feature.ephemeral_listen"],
            expected_case_ids=None,
        )


def test_validate_admission_phase_rejects_manufactured_packaged_evidence(tmp_path) -> None:
    failed = "admission::feature.ephemeral_listen"
    admission = write_admission(tmp_path, {failed: "failed"})

    with pytest.raises(ExecutionLedgerError, match="must not contain a packaged report"):
        validate_paired_result(
            admission_path=admission,
            admission_context=TEST_CONTEXT,
            report_path=write_report(tmp_path, {"suite.yaml::case": "passed"}),
            expected="failure",
            expected_phase="admission",
            admission_exit_code=1,
            packaged_exit_code=0,
            required_bad_identities=[failed],
            expected_case_ids=None,
        )


def test_validate_rejects_malformed_admission_evidence(tmp_path) -> None:
    path = tmp_path / "admission.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "phase": "admission",
                "context": TEST_CONTEXT,
                "probes": [],
            }
        )
    )

    with pytest.raises(ExecutionLedgerError, match="incomplete probe inventory"):
        validate_paired_result(
            admission_path=path,
            admission_context=TEST_CONTEXT,
            report_path=None,
            expected="failure",
            expected_phase="admission",
            admission_exit_code=1,
            packaged_exit_code=None,
            required_bad_identities=["admission::feature.ephemeral_listen"],
            expected_case_ids=None,
        )


def test_validate_rejects_packaged_phase_when_admission_did_not_succeed(tmp_path) -> None:
    failed = "admission::feature.ephemeral_listen"
    admission = write_admission(tmp_path, {failed: "error"})

    with pytest.raises(ExecutionLedgerError, match="packaged phase requires successful admission"):
        validate_paired_result(
            admission_path=admission,
            admission_context=TEST_CONTEXT,
            report_path=None,
            expected="failure",
            expected_phase="packaged",
            admission_exit_code=1,
            packaged_exit_code=None,
            required_bad_identities=["suite.yaml::case"],
            expected_case_ids={"suite.yaml::case"},
        )


def test_validate_rejects_admission_phase_after_successful_admission(tmp_path) -> None:
    with pytest.raises(ExecutionLedgerError, match="expected admission failure"):
        validate_paired_result(
            admission_path=write_admission(tmp_path),
            admission_context=TEST_CONTEXT,
            report_path=None,
            expected="failure",
            expected_phase="admission",
            admission_exit_code=0,
            packaged_exit_code=None,
            required_bad_identities=["admission::feature.ephemeral_listen"],
            expected_case_ids={"suite.yaml::case"},
        )


@pytest.mark.parametrize(
    ("phase", "identities", "message"),
    [
        ("admission", ["admission::unknown"], "unknown admission"),
        ("admission", ["suite.yaml::case"], "unknown admission"),
        ("packaged", ["admission::feature.ephemeral_listen"], "unknown packaged"),
        ("packaged", ["suite.yaml::unknown"], "unknown packaged"),
        ("packaged", ["suite.yaml::case", "suite.yaml::case"], "duplicates"),
        ("packaged", [""], "non-empty strings"),
    ],
)
def test_validate_rejects_unknown_malformed_duplicate_or_phase_incompatible_declarations(
    tmp_path, phase, identities, message
) -> None:
    with pytest.raises(ExecutionLedgerError, match=message):
        validate_paired_result(
            admission_path=write_admission(tmp_path),
            admission_context=TEST_CONTEXT,
            report_path=write_report(tmp_path, {"suite.yaml::case": "failed"}),
            expected="failure",
            expected_phase=phase,
            admission_exit_code=0,
            packaged_exit_code=1,
            required_bad_identities=identities,
            expected_case_ids={"suite.yaml::case"},
        )


def test_validate_expected_success_requires_packaged_phase(tmp_path) -> None:
    with pytest.raises(ExecutionLedgerError, match="expected success requires packaged phase"):
        validate_paired_result(
            admission_path=write_admission(tmp_path),
            admission_context=TEST_CONTEXT,
            report_path=None,
            expected="success",
            expected_phase="admission",
            admission_exit_code=0,
            packaged_exit_code=None,
            required_bad_identities=[],
            expected_case_ids={"suite.yaml::case"},
        )


@pytest.mark.parametrize(
    "payload", ["", "not json", '"one,two"', "{}", "null", "[1]", '[""]']
)
def test_parse_required_bad_identities_rejects_malformed_payload(payload) -> None:
    with pytest.raises(ExecutionLedgerError, match="required_bad_identities"):
        paired_result._parse_required_bad_identities(payload)


def test_parse_required_bad_identities_preserves_array_for_validation() -> None:
    assert paired_result._parse_required_bad_identities('["two", "one"]') == ["two", "one"]


@pytest.mark.parametrize("content", ["[]", '["duplicate", "duplicate"]', "{}", "null"])
def test_load_expected_ids_rejects_invalid_lists(tmp_path, content) -> None:
    path = tmp_path / "expected.json"
    path.write_text(content)

    with pytest.raises(ExecutionLedgerError):
        _load_expected_ids(path)


def test_load_expected_ids_accepts_unique_nonempty_list(tmp_path) -> None:
    path = tmp_path / "expected.json"
    path.write_text(json.dumps(["suite.yaml::one", "suite.yaml::two"]))

    assert _load_expected_ids(path) == {"suite.yaml::one", "suite.yaml::two"}
