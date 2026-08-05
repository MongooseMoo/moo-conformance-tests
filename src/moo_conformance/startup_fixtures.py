"""Trusted validation for candidate-owned startup database fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import TypedDict

from .path_confinement import (
    CandidatePathError,
    require_confined_path,
    resolve_candidate_anchor,
)

_MANIFEST_NAME = "startup-fixtures.sha256"
_FIXTURE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*\.db$")
_MANIFEST_LINE = re.compile(
    r"^(?P<sha256>[0-9a-f]{64})  (?P<name>[A-Za-z0-9][A-Za-z0-9_.-]*\.db)$"
)


class StartupFixtureError(RuntimeError):
    """Candidate startup fixtures do not form one exact, confined manifest."""


class FixtureEvidence(TypedDict):
    name: str
    sha256: str
    size: int


class StartupFixtureEvidence(TypedDict):
    schema_version: int
    candidate_anchor: str
    fixture_root: str
    manifest: str
    fixture_count: int
    fixtures: list[FixtureEvidence]


def _is_link_or_junction(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction is not None and is_junction())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_startup_fixtures(
    candidate_root: str | Path,
    fixtures_dir: str | Path,
    manifest_path: str | Path,
) -> StartupFixtureEvidence:
    """Validate one canonical manifest against the exact flat fixture directory."""
    candidate_input = Path(candidate_root)
    fixtures_input = Path(fixtures_dir)
    manifest_input = Path(manifest_path)
    if _is_link_or_junction(candidate_input):
        raise StartupFixtureError(
            f"linked candidate checkout root is not allowed: {candidate_input}"
        )
    if _is_link_or_junction(fixtures_input):
        raise StartupFixtureError(
            f"linked startup fixture directory is not allowed: {fixtures_input}"
        )
    if _is_link_or_junction(manifest_input):
        raise StartupFixtureError(
            f"linked startup fixture manifest is not allowed: {manifest_input}"
        )

    try:
        anchor = resolve_candidate_anchor(candidate_input)
        fixtures = require_confined_path(
            anchor,
            fixtures_input,
            label="startup fixture directory",
            kind="directory",
        )
        manifest = require_confined_path(
            anchor,
            manifest_input,
            label="startup fixture manifest",
            kind="file",
        )
    except CandidatePathError as exc:
        raise StartupFixtureError(str(exc)) from exc

    canonical_manifest = fixtures / _MANIFEST_NAME
    try:
        canonical_resolved = canonical_manifest.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise StartupFixtureError(
            f"canonical startup fixture manifest cannot be resolved: {canonical_manifest}: {exc}"
        ) from exc
    if manifest != canonical_resolved:
        raise StartupFixtureError(
            "manifest must be the canonical startup fixture manifest: "
            f"expected={canonical_resolved}; supplied={manifest}"
        )

    actual_files: dict[str, Path] = {}
    for entry in sorted(fixtures.iterdir(), key=lambda path: path.name):
        if _is_link_or_junction(entry):
            raise StartupFixtureError(f"linked startup fixture entry: {entry.name}")
        if entry.name == _MANIFEST_NAME:
            if not entry.is_file():
                raise StartupFixtureError(
                    f"unexpected startup fixture entry: {entry.name}"
                )
            continue
        if not entry.is_file() or _FIXTURE_NAME.fullmatch(entry.name) is None:
            raise StartupFixtureError(f"unexpected startup fixture entry: {entry.name}")
        actual_files[entry.name] = entry

    try:
        lines = manifest.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise StartupFixtureError(f"cannot read startup fixture manifest: {exc}") from exc
    if not lines:
        raise StartupFixtureError("startup fixture manifest is empty")

    expected: dict[str, str] = {}
    ordered_names: list[str] = []
    for line_number, line in enumerate(lines, start=1):
        match = _MANIFEST_LINE.fullmatch(line)
        if match is None:
            raise StartupFixtureError(
                f"malformed startup fixture manifest line {line_number}: {line!r}"
            )
        name = match.group("name")
        if name in expected:
            raise StartupFixtureError(f"duplicate startup fixture name: {name}")
        ordered_names.append(name)
        expected[name] = match.group("sha256")
    if ordered_names != sorted(ordered_names):
        raise StartupFixtureError(
            "startup fixture manifest entries are not in canonical name order"
        )

    missing = sorted(expected.keys() - actual_files.keys())
    if missing:
        raise StartupFixtureError(
            "missing startup fixture files: " + ", ".join(missing)
        )
    unlisted = sorted(actual_files.keys() - expected.keys())
    if unlisted:
        raise StartupFixtureError(
            "unlisted startup fixture files: " + ", ".join(unlisted)
        )

    evidence: list[FixtureEvidence] = []
    for name in ordered_names:
        path = actual_files[name]
        actual_digest = _sha256(path)
        if actual_digest != expected[name]:
            raise StartupFixtureError(
                "startup fixture checksum mismatch: "
                f"{name}: expected={expected[name]}; actual={actual_digest}"
            )
        evidence.append(
            {
                "name": name,
                "sha256": actual_digest,
                "size": path.stat().st_size,
            }
        )

    return {
        "schema_version": 1,
        "candidate_anchor": str(anchor),
        "fixture_root": str(fixtures),
        "manifest": str(manifest),
        "fixture_count": len(evidence),
        "fixtures": evidence,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", required=True, type=Path)
    parser.add_argument("--fixtures-dir", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        evidence = validate_startup_fixtures(
            args.candidate_root,
            args.fixtures_dir,
            args.manifest,
        )
    except StartupFixtureError as exc:
        parser.error(str(exc))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"validated {evidence['fixture_count']} startup fixtures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
