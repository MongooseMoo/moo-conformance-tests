"""Fail-closed validation for an explicit Barn/conformance candidate pair."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .execution_ledger import (
    ExecutionLedgerError,
    packaged_case_ids,
    parse_junit_report,
)


def validate_paired_result(
    report_path: str | Path,
    *,
    expected: str,
    exit_code: int,
    required_bad_cases: object,
    expected_case_ids: set[str] | None = None,
) -> dict[str, object]:
    """Validate that a paired run covered the exact packaged surface and matched intent."""
    if expected not in {"success", "failure"}:
        raise ExecutionLedgerError(f"unknown expected result: {expected!r}")

    expected_case_ids = expected_case_ids if expected_case_ids is not None else packaged_case_ids()
    if not expected_case_ids:
        raise ExecutionLedgerError("packaged conformance collection is empty")
    declared_bad_cases = _validate_required_bad_cases(
        required_bad_cases,
        expected=expected,
        expected_case_ids=expected_case_ids,
    )

    outcomes = parse_junit_report(report_path)
    missing = expected_case_ids - set(outcomes)
    extra = set(outcomes) - expected_case_ids
    if missing or extra:
        details: list[str] = []
        if missing:
            details.append("missing=" + ", ".join(sorted(missing)))
        if extra:
            details.append("unknown=" + ", ".join(sorted(extra)))
        raise ExecutionLedgerError("paired report has an inexact surface: " + "; ".join(details))

    counts = {
        status: sum(outcome.status == status for outcome in outcomes.values())
        for status in ("passed", "skipped", "failed", "error")
    }
    bad_case_ids = {
        case_id
        for case_id, outcome in outcomes.items()
        if outcome.status in {"failed", "error"}
    }
    bad_outcomes = counts["failed"] + counts["error"]

    if expected == "success" and (
        exit_code != 0 or bad_outcomes != 0 or counts["passed"] == 0
    ):
        raise ExecutionLedgerError(
            "expected success with exit code 0, at least one pass, and no failures/errors; "
            f"got exit_code={exit_code}, counts={counts}"
        )
    if expected == "failure" and (exit_code != 1 or bad_outcomes == 0):
        raise ExecutionLedgerError(
            "expected failure with pytest exit code 1 and at least one failure/error; "
            f"got exit_code={exit_code}, counts={counts}"
        )
    if expected == "failure" and bad_case_ids != declared_bad_cases:
        mismatch_details: list[str] = []
        missing_bad_cases = declared_bad_cases - bad_case_ids
        extra_bad_cases = bad_case_ids - declared_bad_cases
        if missing_bad_cases:
            mismatch_details.append(
                "missing observed bad cases=" + ", ".join(sorted(missing_bad_cases))
            )
        if extra_bad_cases:
            mismatch_details.append(
                "extra observed bad cases=" + ", ".join(sorted(extra_bad_cases))
            )
        raise ExecutionLedgerError(
            "observed failed/error identities do not equal required_bad_cases: "
            + "; ".join(mismatch_details)
        )

    return {
        "schema_version": 2,
        "expected_result": expected,
        "required_bad_cases": sorted(declared_bad_cases),
        "exit_code": exit_code,
        "packaged_cases": len(expected_case_ids),
        **counts,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--expected", required=True, choices=("success", "failure"))
    parser.add_argument("--exit-code", required=True, type=int)
    parser.add_argument("--required-bad-cases", required=True)
    parser.add_argument("--expected-ids", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        expected_case_ids = _load_expected_ids(args.expected_ids) if args.expected_ids else None
        required_bad_cases = _parse_required_bad_cases(args.required_bad_cases)
        result = validate_paired_result(
            args.report,
            expected=args.expected,
            exit_code=args.exit_code,
            required_bad_cases=required_bad_cases,
            expected_case_ids=expected_case_ids,
        )
    except ExecutionLedgerError as exc:
        parser.error(str(exc))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"Paired result matched {result['expected_result']}: "
        f"{result['packaged_cases']} packaged cases, "
        f"{result['passed']} passed, {result['skipped']} skipped, "
        f"{result['failed']} failed, {result['error']} errors"
    )
    return 0


def _parse_required_bad_cases(raw: str) -> list[str]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ExecutionLedgerError(f"required_bad_cases must be valid JSON: {exc}") from exc
    if not isinstance(data, list) or any(
        not isinstance(case_id, str) or not case_id or case_id != case_id.strip()
        for case_id in data
    ):
        raise ExecutionLedgerError(
            "required_bad_cases must be a JSON array of non-empty strings without padding"
        )
    return data


def _validate_required_bad_cases(
    required_bad_cases: object,
    *,
    expected: str,
    expected_case_ids: set[str],
) -> set[str]:
    if not isinstance(required_bad_cases, list) or any(
        not isinstance(case_id, str) or not case_id or case_id != case_id.strip()
        for case_id in required_bad_cases
    ):
        raise ExecutionLedgerError(
            "required_bad_cases must be a JSON array of non-empty strings without padding"
        )

    declared_bad_cases = set(required_bad_cases)
    if len(declared_bad_cases) != len(required_bad_cases):
        raise ExecutionLedgerError("required_bad_cases contains duplicates")
    if expected == "success" and declared_bad_cases:
        raise ExecutionLedgerError("expected success requires empty required_bad_cases")
    if expected == "failure" and not declared_bad_cases:
        raise ExecutionLedgerError("expected failure requires non-empty required_bad_cases")

    unknown = declared_bad_cases - expected_case_ids
    if unknown:
        raise ExecutionLedgerError(
            "required_bad_cases contains unknown packaged case IDs: "
            + ", ".join(sorted(unknown))
        )
    return declared_bad_cases


def _load_expected_ids(path: Path) -> set[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExecutionLedgerError(f"cannot read expected case IDs {path}: {exc}") from exc
    if not isinstance(data, list) or any(not isinstance(case_id, str) for case_id in data):
        raise ExecutionLedgerError("expected case IDs must be a JSON array of strings")
    case_ids = set(data)
    if len(case_ids) != len(data):
        raise ExecutionLedgerError("expected case IDs contain duplicates")
    if not case_ids:
        raise ExecutionLedgerError("expected case IDs are empty")
    return case_ids


if __name__ == "__main__":
    raise SystemExit(main())
