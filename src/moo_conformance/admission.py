"""Canonical capability-admission evidence for staged conformance runs."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

ADMISSION_PROBE_INVENTORY = (
    "admission::option.OUTBOUND_NETWORK",
    "admission::feature.connectable_listener_port",
    "admission::feature.ephemeral_listen",
    "admission::option.PROMOTE_NUMBERS",
)

ADMISSION_PREREQUISITES = {
    "admission::option.OUTBOUND_NETWORK": (),
    "admission::feature.connectable_listener_port": (
        "admission::option.OUTBOUND_NETWORK",
    ),
    "admission::feature.ephemeral_listen": (),
    "admission::option.PROMOTE_NUMBERS": (),
}

_STATUSES = {"passed", "failed", "error", "blocked"}


class AdmissionEvidenceError(RuntimeError):
    """Admission evidence is missing, malformed, or internally inconsistent."""


class CapabilityProbeError(RuntimeError):
    """A capability probe could not produce a well-formed result."""


class CapabilityProbeFailure(CapabilityProbeError):
    """A capability probe was executed but the server rejected it."""


def run_capability_admission(
    probe: Callable[[str], bool],
    *,
    context: str,
) -> dict[str, object]:
    """Run every canonical probe and retain a complete, dependency-aware inventory."""
    _validate_context(context, label="admission context")
    probes: list[dict[str, object]] = []
    statuses: dict[str, str] = {}

    for identity in ADMISSION_PROBE_INVENTORY:
        blocked_by = [
            prerequisite
            for prerequisite in ADMISSION_PREREQUISITES[identity]
            if statuses.get(prerequisite) in {"failed", "error", "blocked"}
        ]
        if blocked_by:
            outcome: dict[str, object] = {
                "identity": identity,
                "status": "blocked",
                "prerequisite_blocked_by": blocked_by,
            }
        else:
            try:
                value = probe(identity)
                if type(value) is not bool:
                    raise CapabilityProbeError(
                        f"probe {identity} returned non-boolean value {value!r}"
                    )
                outcome = {
                    "identity": identity,
                    "status": "passed",
                    "value": value,
                    "prerequisite_blocked_by": [],
                }
            except CapabilityProbeFailure as exc:
                outcome = {
                    "identity": identity,
                    "status": "failed",
                    "detail": str(exc),
                    "prerequisite_blocked_by": [],
                }
            except Exception as exc:
                outcome = {
                    "identity": identity,
                    "status": "error",
                    "detail": str(exc),
                    "prerequisite_blocked_by": [],
                }
        statuses[identity] = str(outcome["status"])
        probes.append(outcome)

    evidence: dict[str, object] = {
        "schema_version": 2,
        "phase": "admission",
        "context": context,
        "probes": probes,
    }
    validate_admission_evidence(evidence)
    return evidence


def validate_admission_evidence(evidence: object) -> dict[str, object]:
    """Validate the exact admission schema, inventory, and dependency evidence."""
    if not isinstance(evidence, dict) or set(evidence) != {
        "schema_version",
        "phase",
        "context",
        "probes",
    }:
        raise AdmissionEvidenceError(
            "admission evidence must contain exactly schema_version, phase, context, and probes"
        )
    if evidence["schema_version"] != 2 or evidence["phase"] != "admission":
        raise AdmissionEvidenceError(
            "admission evidence must use schema_version 2 and phase 'admission'"
        )
    _validate_context(evidence["context"], label="admission evidence context")

    probes = evidence["probes"]
    if not isinstance(probes, list) or len(probes) != len(ADMISSION_PROBE_INVENTORY):
        raise AdmissionEvidenceError("admission evidence has an incomplete probe inventory")

    observed_identities: list[str] = []
    observed_statuses: dict[str, str] = {}
    for index, probe in enumerate(probes):
        if not isinstance(probe, dict):
            raise AdmissionEvidenceError(f"admission probe {index} must be an object")
        identity = probe.get("identity")
        status = probe.get("status")
        blocked_by = probe.get("prerequisite_blocked_by")
        if not isinstance(identity, str) or status not in _STATUSES:
            raise AdmissionEvidenceError(f"admission probe {index} has invalid identity or status")
        if not isinstance(blocked_by, list) or any(
            not isinstance(prerequisite, str) for prerequisite in blocked_by
        ):
            raise AdmissionEvidenceError(
                f"admission probe {identity} has malformed prerequisite evidence"
            )

        if status == "passed":
            expected_keys = {
                "identity",
                "status",
                "value",
                "prerequisite_blocked_by",
            }
            if type(probe.get("value")) is not bool or blocked_by:
                raise AdmissionEvidenceError(
                    f"passed admission probe {identity} must have a boolean value and no blockers"
                )
        elif status in {"failed", "error"}:
            expected_keys = {
                "identity",
                "status",
                "detail",
                "prerequisite_blocked_by",
            }
            detail = probe.get("detail")
            if not isinstance(detail, str) or not detail or blocked_by:
                raise AdmissionEvidenceError(
                    f"unsuccessful admission probe {identity} must have detail and no blockers"
                )
        else:
            expected_keys = {"identity", "status", "prerequisite_blocked_by"}
            if not blocked_by:
                raise AdmissionEvidenceError(
                    f"blocked admission probe {identity} must name its prerequisites"
                )

        if set(probe) != expected_keys:
            raise AdmissionEvidenceError(
                f"admission probe {identity} has fields incompatible with status {status}"
            )
        observed_identities.append(identity)
        observed_statuses[identity] = status

    if tuple(observed_identities) != ADMISSION_PROBE_INVENTORY:
        raise AdmissionEvidenceError(
            "admission evidence identities must exactly equal the canonical ordered inventory"
        )

    for probe in probes:
        identity = str(probe["identity"])
        blocked_by = probe["prerequisite_blocked_by"]
        expected_blockers = [
            prerequisite
            for prerequisite in ADMISSION_PREREQUISITES[identity]
            if observed_statuses[prerequisite] in {"failed", "error", "blocked"}
        ]
        if blocked_by != expected_blockers:
            raise AdmissionEvidenceError(
                f"admission probe {identity} has inexact prerequisite-blocked evidence"
            )
        if expected_blockers and probe["status"] != "blocked":
            raise AdmissionEvidenceError(
                f"admission probe {identity} executed despite a failed prerequisite"
            )
        if not expected_blockers and probe["status"] == "blocked":
            raise AdmissionEvidenceError(
                f"admission probe {identity} is blocked without an unsuccessful prerequisite"
            )

    return evidence


def _validate_context(context: object, *, label: str) -> str:
    if not isinstance(context, str) or not context or context != context.strip():
        raise AdmissionEvidenceError(
            f"{label} must be a non-empty string without surrounding whitespace"
        )
    return context


def load_admission_evidence(
    path: str | Path,
    *,
    expected_context: str | None = None,
) -> dict[str, object]:
    evidence_path = Path(path)
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AdmissionEvidenceError(
            f"cannot read admission evidence {evidence_path}: {exc}"
        ) from exc
    validated = validate_admission_evidence(evidence)
    if expected_context is not None:
        _validate_context(expected_context, label="expected admission context")
        if validated["context"] != expected_context:
            raise AdmissionEvidenceError(
                "admission evidence context mismatch: "
                f"expected {expected_context!r}, observed {validated['context']!r}"
            )
    return validated


def write_admission_evidence(path: str | Path, evidence: object) -> None:
    validated = validate_admission_evidence(evidence)
    evidence_path = Path(path)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        json.dumps(validated, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def admission_bad_identities(evidence: dict[str, object]) -> set[str]:
    probes = evidence["probes"]
    assert isinstance(probes, list)
    return {
        str(probe["identity"])
        for probe in probes
        if isinstance(probe, dict) and probe.get("status") in {"failed", "error"}
    }


def admission_blocked_identities(evidence: dict[str, object]) -> set[str]:
    probes = evidence["probes"]
    assert isinstance(probes, list)
    return {
        str(probe["identity"])
        for probe in probes
        if isinstance(probe, dict) and probe.get("status") == "blocked"
    }


def admission_counts(evidence: dict[str, object]) -> dict[str, int]:
    probes = evidence["probes"]
    assert isinstance(probes, list)
    return {
        status: sum(
            isinstance(probe, dict) and probe.get("status") == status for probe in probes
        )
        for status in ("passed", "failed", "error", "blocked")
    }
