"""Fail-closed accounting for conformance execution across target profiles."""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, TypedDict

from .plugin import conformance_case_id, discover_yaml_tests, get_tests_dir

_CASE_NAME = re.compile(r"^test_yaml_conformance\[(.*)]$")


class ExecutionLedgerError(RuntimeError):
    """A profile report does not prove the complete conformance surface."""


@dataclass(frozen=True)
class CaseOutcome:
    status: str
    reason: str | None = None


class CandidateInventory(TypedDict):
    schema_version: int
    trusted_case_ids: list[str]
    candidate_case_ids: list[str]
    additive_case_ids: list[str]


def packaged_case_ids(tests_dir: str | Path | None = None) -> set[str]:
    tests_dir = Path(tests_dir).resolve() if tests_dir is not None else get_tests_dir()
    return {
        conformance_case_id(path, test, tests_dir)
        for path, _suite, test in discover_yaml_tests(test_dir=tests_dir)
    }


def validate_candidate_inventory(
    candidate_tests_dir: str | Path,
    *,
    trusted_tests_dir: str | Path | None = None,
) -> CandidateInventory:
    """Recompute trusted and candidate identities and reject candidate deletions."""
    trusted = packaged_case_ids(trusted_tests_dir)
    candidate = packaged_case_ids(candidate_tests_dir)
    if not trusted:
        raise ExecutionLedgerError("trusted-main packaged conformance inventory is empty")
    if not candidate:
        raise ExecutionLedgerError("candidate packaged conformance inventory is empty")
    missing = trusted - candidate
    if missing:
        raise ExecutionLedgerError(
            "candidate conformance data deletes trusted-main identities: "
            + ", ".join(sorted(missing))
        )
    return {
        "schema_version": 1,
        "trusted_case_ids": sorted(trusted),
        "candidate_case_ids": sorted(candidate),
        "additive_case_ids": sorted(candidate - trusted),
    }


def parse_junit_report(path: str | Path) -> dict[str, CaseOutcome]:
    report_path = Path(path)
    try:
        root = ET.parse(report_path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise ExecutionLedgerError(f"cannot read JUnit report {report_path}: {exc}") from exc

    outcomes: dict[str, CaseOutcome] = {}
    for testcase in root.iter("testcase"):
        name = testcase.attrib.get("name", "")
        match = _CASE_NAME.fullmatch(name)
        if match is None:
            continue
        case_id = match.group(1)
        if case_id in outcomes:
            raise ExecutionLedgerError(
                f"duplicate conformance identity in {report_path}: {case_id}"
            )

        failure = testcase.find("failure")
        error = testcase.find("error")
        skipped = testcase.find("skipped")
        if failure is not None:
            outcomes[case_id] = CaseOutcome("failed", _element_reason(failure))
        elif error is not None:
            outcomes[case_id] = CaseOutcome("error", _element_reason(error))
        elif skipped is not None:
            outcomes[case_id] = CaseOutcome("skipped", _element_reason(skipped))
        else:
            outcomes[case_id] = CaseOutcome("passed")
    return outcomes


def _element_reason(element: ET.Element) -> str:
    return element.attrib.get("message") or (element.text or "").strip()


def load_baseline(path: str | Path) -> dict[str, str]:
    baseline_path = Path(path)
    try:
        data = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExecutionLedgerError(f"cannot read skip baseline {baseline_path}: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ExecutionLedgerError("skip baseline must be an object with schema_version 1")
    entries = data.get("never_executed")
    if not isinstance(entries, dict) or any(
        not isinstance(case_id, str) or not isinstance(reason, str) or not reason
        for case_id, reason in entries.items()
    ):
        raise ExecutionLedgerError("skip baseline never_executed must map case IDs to reasons")
    return entries


def enforce_execution_surface(
    reports: dict[str, dict[str, CaseOutcome]],
    expected_case_ids: set[str],
    baseline: dict[str, str],
) -> dict[str, object]:
    if not reports:
        raise ExecutionLedgerError("no profile reports were supplied")
    if not expected_case_ids:
        raise ExecutionLedgerError("packaged conformance collection is empty")

    unknown_baseline = set(baseline) - expected_case_ids
    if unknown_baseline:
        raise ExecutionLedgerError(
            "skip baseline contains unknown case IDs: " + ", ".join(sorted(unknown_baseline))
        )

    profile_counts: dict[str, dict[str, int]] = {}
    executed: set[str] = set()
    for profile, outcomes in sorted(reports.items()):
        missing = expected_case_ids - set(outcomes)
        extra = set(outcomes) - expected_case_ids
        if missing or extra:
            details: list[str] = []
            if missing:
                details.append("missing=" + ", ".join(sorted(missing)))
            if extra:
                details.append("unknown=" + ", ".join(sorted(extra)))
            detail = "; ".join(details)
            raise ExecutionLedgerError(
                f"profile {profile} has an inexact surface: {detail}"
            )

        bad = {
            case_id: outcome
            for case_id, outcome in outcomes.items()
            if outcome.status in {"failed", "error"}
        }
        if bad:
            rendered = ", ".join(
                f"{case_id} ({outcome.status}: {outcome.reason})"
                for case_id, outcome in sorted(bad.items())
            )
            raise ExecutionLedgerError(f"profile {profile} has unsuccessful cases: {rendered}")

        executed.update(
            case_id for case_id, outcome in outcomes.items() if outcome.status == "passed"
        )
        profile_counts[profile] = {
            status: sum(outcome.status == status for outcome in outcomes.values())
            for status in ("passed", "skipped", "failed", "error")
        }

    never_executed = expected_case_ids - executed
    unreviewed = never_executed - set(baseline)
    stale = set(baseline) - never_executed
    if unreviewed:
        raise ExecutionLedgerError(
            "cases never executed by any profile and absent from the reviewed baseline: "
            + ", ".join(sorted(unreviewed))
        )
    if stale:
        raise ExecutionLedgerError(
            "stale skip baseline entries executed by at least one profile: "
            + ", ".join(sorted(stale))
        )

    for case_id, expected_reason in sorted(baseline.items()):
        for profile, outcomes in sorted(reports.items()):
            outcome = outcomes[case_id]
            if outcome.status != "skipped" or outcome.reason != expected_reason:
                raise ExecutionLedgerError(
                    f"baseline drift for {case_id} in {profile}: expected skipped with "
                    f"{expected_reason!r}, got {outcome.status} with {outcome.reason!r}"
                )

    return {
        "schema_version": 1,
        "packaged_cases": len(expected_case_ids),
        "executed_cases": len(executed),
        "reviewed_never_executed_cases": len(baseline),
        "profiles": profile_counts,
        "executed_case_ids": sorted(executed),
        "reviewed_never_executed": baseline,
    }


def _parse_report_arguments(values: Iterable[str]) -> dict[str, Path]:
    reports: dict[str, Path] = {}
    for value in values:
        profile, separator, raw_path = value.partition("=")
        if not separator or not profile or not raw_path:
            raise ExecutionLedgerError(f"report must use PROFILE=PATH: {value!r}")
        if profile in reports:
            raise ExecutionLedgerError(f"duplicate profile report argument: {profile}")
        reports[profile] = Path(raw_path)
    return reports


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="append", required=True, metavar="PROFILE=PATH")
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        report_paths = _parse_report_arguments(args.report)
        reports = {
            profile: parse_junit_report(path) for profile, path in report_paths.items()
        }
        ledger = enforce_execution_surface(
            reports,
            packaged_case_ids(),
            load_baseline(args.baseline),
        )
    except ExecutionLedgerError as exc:
        parser.error(str(exc))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"Toast profile union executed {ledger['executed_cases']} of "
        f"{ledger['packaged_cases']} packaged cases; "
        f"{ledger['reviewed_never_executed_cases']} reviewed skips remain"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
