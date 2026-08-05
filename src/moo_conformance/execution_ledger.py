"""Fail-closed accounting for conformance execution across target profiles."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, TypedDict

from .path_confinement import (
    CandidatePathError,
    require_confined_path,
    resolve_candidate_anchor,
    validate_confined_tree,
)
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
    candidate_anchor: str
    trusted_case_ids: list[str]
    candidate_case_ids: list[str]
    additive_case_ids: list[str]
    candidate_identity_sha256: str


def packaged_case_ids(
    tests_dir: str | Path | None = None,
    *,
    candidate_root: str | Path | None = None,
) -> set[str]:
    tests_dir = Path(tests_dir).resolve() if tests_dir is not None else get_tests_dir()
    return {
        conformance_case_id(path, test, tests_dir)
        for path, _suite, test in discover_yaml_tests(
            test_dir=tests_dir,
            candidate_root=candidate_root,
        )
    }


def validate_candidate_inventory(
    candidate_root: str | Path,
    candidate_tests_dir: str | Path,
    *,
    candidate_db_path: str | Path,
    candidate_db_dir: str | Path,
    trusted_tests_dir: str | Path | None = None,
) -> CandidateInventory:
    """Recompute trusted and candidate identities and reject candidate deletions."""
    try:
        anchor = resolve_candidate_anchor(candidate_root)
        tests = validate_confined_tree(
            anchor,
            candidate_tests_dir,
            root_label="candidate suite root",
            entry_label="candidate suite entry",
        )
        require_confined_path(
            anchor,
            candidate_db_path,
            label="candidate primary database",
            kind="file",
        )
        validate_confined_tree(
            anchor,
            candidate_db_dir,
            root_label="candidate database fixture root",
            entry_label="candidate database fixture entry",
        )
        trusted = packaged_case_ids(trusted_tests_dir)
        candidate = packaged_case_ids(tests, candidate_root=anchor)
    except (CandidatePathError, ValueError) as exc:
        raise ExecutionLedgerError(str(exc)) from exc
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
    candidate_identities = sorted(candidate)
    digest = hashlib.sha256(("\n".join(candidate_identities) + "\n").encode()).hexdigest()
    return {
        "schema_version": 2,
        "candidate_anchor": str(anchor),
        "trusted_case_ids": sorted(trusted),
        "candidate_case_ids": candidate_identities,
        "additive_case_ids": sorted(candidate - trusted),
        "candidate_identity_sha256": digest,
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


def enforce_execution_surface(
    reports: dict[str, dict[str, CaseOutcome]],
    expected_case_ids: set[str],
) -> dict[str, object]:
    if not reports:
        raise ExecutionLedgerError("no profile reports were supplied")
    if not expected_case_ids:
        raise ExecutionLedgerError("packaged conformance collection is empty")

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
    if never_executed:
        raise ExecutionLedgerError(
            "cases never executed by any Toast profile: "
            + ", ".join(sorted(never_executed))
        )

    return {
        "schema_version": 2,
        "packaged_cases": len(expected_case_ids),
        "executed_cases": len(executed),
        "profiles": profile_counts,
        "executed_case_ids": sorted(executed),
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
        )
    except ExecutionLedgerError as exc:
        parser.error(str(exc))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"Toast profile union executed {ledger['executed_cases']} of "
        f"{ledger['packaged_cases']} packaged cases"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
