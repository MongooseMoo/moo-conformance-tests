"""Closed grammar and skip reasons for conformance admission conditions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_CONDITION_RE = re.compile(
    r"^(?:(?P<not>not )?(?P<presence>feature|option)|missing (?P<missing>builtin))\."
    r"(?P<name>[A-Za-z0-9][A-Za-z0-9_]*)$"
)
_VERSION_RE = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)$")

SUPPORTED_CONFIG_REQUIREMENTS = frozenset(
    {"server_dir", "log_file", "managed_server", "server_db_dir"}
)
CONFIG_OPTION_MAP = {
    "server_dir": "--moo-server-dir",
    "log_file": "--moo-log-file",
    "managed_server": "--server-command",
    "server_db_dir": "--server-db-dir",
}


@dataclass(frozen=True)
class SkipCondition:
    target: str
    name: str
    skip_when_present: bool

    @property
    def skip_reason(self) -> str:
        if self.skip_when_present:
            return f"Incompatible with {self.target}: {self.name}"
        return f"Requires {self.target}: {self.name}"


def parse_skip_condition(value: Any) -> SkipCondition:
    """Parse the complete supported ``skip_if`` grammar or fail closed."""
    if not isinstance(value, str):
        raise ValueError("skip_if must be a string")
    match = _CONDITION_RE.fullmatch(value)
    if match is None:
        raise ValueError(f"unsupported or malformed skip_if condition: {value!r}")

    target = match.group("presence") or match.group("missing")
    skip_when_present = match.group("missing") is None and match.group("not") is None
    return SkipCondition(
        target=target,
        name=match.group("name"),
        skip_when_present=skip_when_present,
    )


def parse_skip_conditions(value: Any) -> tuple[SkipCondition, ...]:
    """Parse one or more atomic conditions joined by the exact ``or`` operator."""
    if not isinstance(value, str):
        raise ValueError("skip_if must be a string")
    alternatives = value.split(" or ")
    if any(not alternative for alternative in alternatives):
        raise ValueError(f"unsupported or malformed skip_if condition: {value!r}")
    return tuple(parse_skip_condition(alternative) for alternative in alternatives)


def parse_min_version(value: Any) -> tuple[int, int, int]:
    """Parse the closed ``major.minor.patch`` requirement format."""
    if not isinstance(value, str):
        raise ValueError("min_version must be a string in major.minor.patch form")
    match = _VERSION_RE.fullmatch(value)
    if match is None:
        raise ValueError("min_version must use major.minor.patch numeric form")
    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
    )


def config_skip_reason(key: str) -> str:
    return f"Requires config '{key}' (use {CONFIG_OPTION_MAP[key]})"


def declared_literal_skip_reason(suite, test) -> str | None:
    """Return the one literal skip reason the canonical runner would emit."""
    test_skip = getattr(test, "skip", False)
    if test_skip:
        return test_skip if isinstance(test_skip, str) else "Test marked as skip"

    suite_skip = getattr(suite, "skip", False)
    if suite_skip:
        return suite_skip if isinstance(suite_skip, str) else "Suite marked as skip"

    return None


def declared_runtime_skip_reasons(suite, test) -> set[str]:
    """Return exact runtime skip reasons authorized by YAML declarations."""
    reasons: set[str] = set()
    literal_reason = declared_literal_skip_reason(suite, test)
    if literal_reason is not None:
        return {literal_reason}

    skip_if = getattr(test, "skip_if", None)
    if skip_if is not None:
        reasons.update(condition.skip_reason for condition in parse_skip_conditions(skip_if))

    requirements = getattr(suite, "requires", None)
    if requirements is not None:
        reasons.update(f"Requires builtin: {name}" for name in requirements.builtins)
        reasons.update(f"Requires feature: {name}" for name in requirements.features)
        if requirements.min_version is not None:
            reasons.add(f"Requires server version >= {requirements.min_version}")
        reasons.update(config_skip_reason(key) for key in requirements.config)

    steps = [*getattr(test, "steps", ()), *getattr(test, "cleanup", ())]
    if any(getattr(step, "restart_server", None) is not None for step in steps):
        reasons.add(config_skip_reason("managed_server"))
    return reasons
