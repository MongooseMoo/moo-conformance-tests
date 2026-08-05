"""Fail-closed validation for an explicit staged Barn/conformance candidate pair."""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from .admission import (
    ADMISSION_PROBE_INVENTORY,
    AdmissionEvidenceError,
    admission_bad_identities,
    admission_blocked_identities,
    admission_counts,
    load_admission_evidence,
)
from .execution_ledger import (
    CandidateInventory,
    CaseOutcome,
    ExecutionLedgerError,
    parse_junit_report,
    validate_candidate_inventory,
)


def validate_paired_result(
    *,
    admission_path: str | Path,
    admission_report_path: str | Path,
    admission_context: str,
    candidate_root: str | Path,
    candidate_tests_dir: str | Path,
    candidate_db_path: str | Path,
    candidate_db_dir: str | Path,
    report_path: str | Path | None,
    expected: str,
    expected_phase: str,
    admission_exit_code: int,
    packaged_exit_code: int | None,
    required_bad_identities: object,
) -> dict[str, object]:
    """Validate exactly one complete admission or packaged result surface."""
    if expected not in {"success", "failure"}:
        raise ExecutionLedgerError(f"unknown expected result: {expected!r}")
    if expected_phase not in {"admission", "packaged"}:
        raise ExecutionLedgerError(f"unknown expected phase: {expected_phase!r}")
    if expected == "success" and expected_phase != "packaged":
        raise ExecutionLedgerError("expected success requires packaged phase")

    inventory = validate_candidate_inventory(
        candidate_root,
        candidate_tests_dir,
        candidate_db_path=candidate_db_path,
        candidate_db_dir=candidate_db_dir,
    )
    candidate_case_ids = set(inventory["candidate_case_ids"])
    if expected_phase == "packaged":
        known_identities = candidate_case_ids
    else:
        known_identities = set(ADMISSION_PROBE_INVENTORY)

    declared_bad = _validate_required_bad_identities(
        required_bad_identities,
        expected=expected,
        phase=expected_phase,
        known_identities=known_identities,
    )

    try:
        admission = load_admission_evidence(
            admission_path,
            expected_context=admission_context,
        )
    except AdmissionEvidenceError as exc:
        raise ExecutionLedgerError(str(exc)) from exc
    admission_bad = admission_bad_identities(admission)
    admission_blocked = admission_blocked_identities(admission)
    counts = admission_counts(admission)
    admission_succeeded = (
        admission_exit_code == 0 and not admission_bad and not admission_blocked
    )
    admission_junit = parse_admission_junit(
        admission_report_path,
        expected_context=admission_context,
    )
    expected_junit_status = "passed" if admission_succeeded else "failed"
    if admission_junit.status != expected_junit_status:
        raise ExecutionLedgerError(
            "admission JUnit/JSON disagreement: "
            f"JSON success={admission_succeeded}, JUnit status={admission_junit.status}"
        )
    admission_summary: dict[str, object] = {
        "schema_version": 2,
        "context": admission_context,
        "inventory": list(ADMISSION_PROBE_INVENTORY),
        **counts,
        "exit_code": admission_exit_code,
        "junit_status": admission_junit.status,
    }
    inventory_summary = _inventory_summary(inventory)

    if expected_phase == "admission":
        if expected != "failure":
            raise ExecutionLedgerError("admission phase can only declare an expected failure")
        if admission_succeeded:
            raise ExecutionLedgerError("expected admission failure but admission succeeded")
        if admission_exit_code != 1 or not admission_bad:
            raise ExecutionLedgerError(
                "expected admission failure with pytest exit code 1 and at least one "
                f"failed/error probe; got exit_code={admission_exit_code}, counts={counts}"
            )
        if report_path is not None or packaged_exit_code is not None:
            raise ExecutionLedgerError(
                "admission-phase evidence must not contain a packaged report or exit code"
            )
        _require_exact_bad_set(admission_bad, declared_bad)
        return {
            "schema_version": 5,
            "phase": "admission",
            "expected_result": expected,
            "declared_bad_identities": sorted(declared_bad),
            "observed_bad_identities": sorted(admission_bad),
            "admission": admission_summary,
            "inventory": inventory_summary,
            "packaged": None,
        }

    if not admission_succeeded:
        raise ExecutionLedgerError(
            "packaged phase requires successful admission with exit code 0 and no "
            f"failed/error/blocked probes; got exit_code={admission_exit_code}, counts={counts}"
        )
    if report_path is None or packaged_exit_code is None:
        raise ExecutionLedgerError(
            "packaged phase requires a complete JUnit report and packaged exit code"
        )

    outcomes = parse_junit_report(report_path)
    missing = candidate_case_ids - set(outcomes)
    extra = set(outcomes) - candidate_case_ids
    if missing or extra:
        details: list[str] = []
        if missing:
            details.append("missing=" + ", ".join(sorted(missing)))
        if extra:
            details.append("unknown=" + ", ".join(sorted(extra)))
        raise ExecutionLedgerError("paired report has an inexact surface: " + "; ".join(details))

    packaged_counts = {
        status: sum(outcome.status == status for outcome in outcomes.values())
        for status in ("passed", "skipped", "failed", "error")
    }
    observed_bad = {
        case_id
        for case_id, outcome in outcomes.items()
        if outcome.status in {"failed", "error"}
    }
    bad_outcomes = packaged_counts["failed"] + packaged_counts["error"]

    if expected == "success" and (
        packaged_exit_code != 0 or bad_outcomes != 0 or packaged_counts["passed"] == 0
    ):
        raise ExecutionLedgerError(
            "expected success with packaged exit code 0, at least one pass, and no "
            f"failures/errors; got exit_code={packaged_exit_code}, counts={packaged_counts}"
        )
    if expected == "failure" and (packaged_exit_code != 1 or bad_outcomes == 0):
        raise ExecutionLedgerError(
            "expected packaged failure with pytest exit code 1 and at least one "
            f"failure/error; got exit_code={packaged_exit_code}, counts={packaged_counts}"
        )
    _require_exact_bad_set(observed_bad, declared_bad)

    return {
        "schema_version": 5,
        "phase": "packaged",
        "expected_result": expected,
        "declared_bad_identities": sorted(declared_bad),
        "observed_bad_identities": sorted(observed_bad),
        "admission": admission_summary,
        "inventory": inventory_summary,
        "packaged": {
            "exit_code": packaged_exit_code,
            "packaged_cases": len(candidate_case_ids),
            **packaged_counts,
        },
    }


def _require_exact_bad_set(observed: set[str], declared: set[str]) -> None:
    if observed == declared:
        return
    details: list[str] = []
    missing = declared - observed
    extra = observed - declared
    if missing:
        details.append("missing observed bad identities=" + ", ".join(sorted(missing)))
    if extra:
        details.append("extra observed bad identities=" + ", ".join(sorted(extra)))
    raise ExecutionLedgerError(
        "observed failed/error identities do not equal the declared exact set: "
        + "; ".join(details)
    )


def _parse_required_bad_identities(raw: str) -> list[str]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ExecutionLedgerError(
            f"required_bad_identities must be valid JSON: {exc}"
        ) from exc
    _validate_identity_list(data)
    return data


def _validate_identity_list(value: object) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(identity, str) or not identity or identity != identity.strip()
        for identity in value
    ):
        raise ExecutionLedgerError(
            "required_bad_identities must be a JSON array of non-empty strings without padding"
        )
    return value


def _validate_required_bad_identities(
    required_bad_identities: object,
    *,
    expected: str,
    phase: str,
    known_identities: set[str],
) -> set[str]:
    values = _validate_identity_list(required_bad_identities)
    declared = set(values)
    if len(declared) != len(values):
        raise ExecutionLedgerError("required_bad_identities contains duplicates")
    if expected == "success" and declared:
        raise ExecutionLedgerError("expected success requires empty required_bad_identities")
    if expected == "failure" and not declared:
        raise ExecutionLedgerError("expected failure requires non-empty required_bad_identities")
    unknown = declared - known_identities
    if unknown:
        raise ExecutionLedgerError(
            f"required_bad_identities contains unknown {phase} identities: "
            + ", ".join(sorted(unknown))
        )
    return declared


def parse_admission_junit(
    path: str | Path,
    *,
    expected_context: str,
) -> CaseOutcome:
    report_path = Path(path)
    try:
        root = ET.parse(report_path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise ExecutionLedgerError(
            f"cannot read admission JUnit report {report_path}: {exc}"
        ) from exc
    testcases = list(root.iter("testcase"))
    if len(testcases) != 1:
        raise ExecutionLedgerError(
            "admission JUnit must contain exactly one canonical testcase"
        )
    testcase = testcases[0]
    if (
        testcase.attrib.get("name") != "test_capability_admission"
        or testcase.attrib.get("classname") != "src.moo_conformance.test_conformance"
    ):
        raise ExecutionLedgerError(
            "admission JUnit does not identify the exact canonical admission test"
        )
    properties = {
        prop.attrib.get("name"): prop.attrib.get("value")
        for prop in testcase.findall("./properties/property")
    }
    if properties != {"admission_context": expected_context}:
        raise ExecutionLedgerError(
            "admission JUnit context mismatch or malformed context properties"
        )
    failure = testcase.find("failure")
    error = testcase.find("error")
    skipped = testcase.find("skipped")
    if failure is not None:
        return CaseOutcome("failed")
    if error is not None:
        return CaseOutcome("error")
    if skipped is not None:
        return CaseOutcome("skipped")
    return CaseOutcome("passed")


def _inventory_summary(inventory: CandidateInventory) -> dict[str, object]:
    trusted = inventory["trusted_case_ids"]
    candidate = inventory["candidate_case_ids"]
    additive = inventory["additive_case_ids"]
    return {
        "schema_version": 2,
        "candidate_anchor": inventory["candidate_anchor"],
        "trusted_cases": len(trusted),
        "candidate_cases": len(candidate),
        "additive_cases": len(additive),
        "candidate_identity_sha256": inventory["candidate_identity_sha256"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admission", required=True, type=Path)
    parser.add_argument("--admission-report", required=True, type=Path)
    parser.add_argument("--admission-context", required=True)
    parser.add_argument("--candidate-root", required=True, type=Path)
    parser.add_argument("--candidate-tests", required=True, type=Path)
    parser.add_argument("--candidate-db", required=True, type=Path)
    parser.add_argument("--candidate-db-dir", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--expected", required=True, choices=("success", "failure"))
    parser.add_argument("--phase", required=True, choices=("admission", "packaged"))
    parser.add_argument("--admission-exit-code", required=True, type=int)
    parser.add_argument("--packaged-exit-code", type=int)
    parser.add_argument("--required-bad-identities", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        required_bad_identities = _parse_required_bad_identities(
            args.required_bad_identities
        )
        result = validate_paired_result(
            admission_path=args.admission,
            admission_report_path=args.admission_report,
            admission_context=args.admission_context,
            candidate_root=args.candidate_root,
            candidate_tests_dir=args.candidate_tests,
            candidate_db_path=args.candidate_db,
            candidate_db_dir=args.candidate_db_dir,
            report_path=args.report,
            expected=args.expected,
            expected_phase=args.phase,
            admission_exit_code=args.admission_exit_code,
            packaged_exit_code=args.packaged_exit_code,
            required_bad_identities=required_bad_identities,
        )
    except ExecutionLedgerError as exc:
        parser.error(str(exc))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    observed_bad_identities = result["observed_bad_identities"]
    assert isinstance(observed_bad_identities, list)
    print(
        f"Paired result matched {result['expected_result']} in {result['phase']} phase: "
        f"{len(observed_bad_identities)} exact failed/error identities"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
