"""Classify candidate changes for staged trusted-controller conformance CI."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

_DATA_TESTS_PREFIX = "src/moo_conformance/_tests/"
_DATA_DB_PREFIX = "src/moo_conformance/_db/"
_DATA_EXEC_PREFIX = "src/moo_conformance/_exec_fixtures/"
_CONTROLLER_PREFIXES = (
    ".github/",
    "tests/",
)
_CONTROLLER_FILES = {
    ".gitattributes",
    ".gitignore",
    ".python-version",
    "pyproject.toml",
    "setup.cfg",
    "setup.py",
    "tox.ini",
    "uv.lock",
}


class ChangeBoundaryError(RuntimeError):
    """A candidate tree cannot be admitted to a staged CI lane."""


@dataclass(frozen=True)
class ChangeBoundary:
    schema_version: int
    mode: str
    changed_paths: tuple[str, ...]
    controller_paths: tuple[str, ...]
    data_paths: tuple[str, ...]
    neutral_paths: tuple[str, ...]


def _require_canonical_path(path: str) -> str:
    parsed = PurePosixPath(path)
    if (
        not path
        or "\\" in path
        or parsed.is_absolute()
        or parsed.as_posix() != path
        or any(part in {"", ".", ".."} for part in parsed.parts)
    ):
        raise ChangeBoundaryError(
            f"changed path is not a canonical repository-relative POSIX path: {path!r}"
        )
    return path


def _path_kind(path: str) -> str:
    if path.startswith(_DATA_TESTS_PREFIX):
        if path.endswith(".yaml"):
            return "data"
        if path.endswith(".py"):
            return "controller"
        return "unknown"
    if path.startswith(_DATA_DB_PREFIX):
        if path.endswith((".db", ".sha256")):
            return "data"
        return "unknown"
    if path.startswith(_DATA_EXEC_PREFIX):
        return "data"
    if path == "ci/duplicate-baseline.json":
        return "data"
    if path in _CONTROLLER_FILES or path.startswith(_CONTROLLER_PREFIXES):
        return "controller"
    if path.startswith("src/moo_conformance/") and path.endswith(".py"):
        return "controller"
    if path == "src/moo_conformance":
        return "controller"
    if path == "LICENSE" or path.endswith(".md"):
        return "neutral"
    if path.startswith(("ci/", "src/")):
        return "unknown"
    return "unknown"


def classify_changed_paths(paths: Iterable[str]) -> ChangeBoundary:
    """Classify canonical tracked paths and reject mixed or unknown semantic changes."""
    changed = tuple(sorted({_require_canonical_path(path) for path in paths}))
    grouped: dict[str, list[str]] = {
        "controller": [],
        "data": [],
        "neutral": [],
        "unknown": [],
    }
    for path in changed:
        grouped[_path_kind(path)].append(path)

    if grouped["unknown"]:
        raise ChangeBoundaryError(
            "unclassified semantic paths: " + ", ".join(grouped["unknown"])
        )
    if grouped["controller"] and grouped["data"]:
        raise ChangeBoundaryError(
            "candidate mixes controller and data changes; land controller changes first, "
            "then add dependent conformance data after that controller is trusted on main: "
            "controller="
            + ", ".join(grouped["controller"])
            + "; data="
            + ", ".join(grouped["data"])
        )

    if grouped["controller"]:
        mode = "controller"
    elif grouped["data"]:
        mode = "data"
    else:
        mode = "neutral"
    return ChangeBoundary(
        schema_version=1,
        mode=mode,
        changed_paths=changed,
        controller_paths=tuple(grouped["controller"]),
        data_paths=tuple(grouped["data"]),
        neutral_paths=tuple(grouped["neutral"]),
    )


def _tracked_tree(root: str | Path) -> dict[str, tuple[str, str]]:
    checkout = Path(root).resolve()
    if not checkout.is_dir():
        raise ChangeBoundaryError(f"tracked-tree root is not a directory: {checkout}")
    process = subprocess.run(
        ["git", "ls-files", "--stage", "-z"],
        cwd=checkout,
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        error = process.stderr.decode("utf-8", errors="replace").strip()
        raise ChangeBoundaryError(f"cannot enumerate tracked tree {checkout}: {error}")

    entries: dict[str, tuple[str, str]] = {}
    for raw_entry in process.stdout.split(b"\0"):
        if not raw_entry:
            continue
        metadata, separator, raw_path = raw_entry.partition(b"\t")
        fields = metadata.split(b" ")
        if not separator or len(fields) != 3:
            raise ChangeBoundaryError(f"malformed git index entry in {checkout}")
        raw_mode, raw_object_id, raw_stage = fields
        if raw_stage != b"0":
            raise ChangeBoundaryError(f"unmerged git index entry in {checkout}")
        try:
            path = _require_canonical_path(raw_path.decode("utf-8"))
            mode = raw_mode.decode("ascii")
            object_id = raw_object_id.decode("ascii")
        except UnicodeDecodeError as exc:
            raise ChangeBoundaryError(f"non-UTF-8 git index entry in {checkout}") from exc
        if path in entries:
            raise ChangeBoundaryError(f"duplicate git index path in {checkout}: {path}")
        entries[path] = (mode, object_id)
    if not entries:
        raise ChangeBoundaryError(f"tracked tree is empty: {checkout}")
    return entries


def classify_candidate_change(
    trusted_root: str | Path,
    candidate_root: str | Path,
) -> ChangeBoundary:
    """Compare exact tracked Git trees and classify their changed paths."""
    trusted = _tracked_tree(trusted_root)
    candidate = _tracked_tree(candidate_root)
    changed = {
        path
        for path in trusted.keys() | candidate.keys()
        if trusted.get(path) != candidate.get(path)
    }
    return classify_changed_paths(changed)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trusted-root", required=True, type=Path)
    parser.add_argument("--candidate-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        result = classify_candidate_change(args.trusted_root, args.candidate_root)
    except ChangeBoundaryError as exc:
        parser.error(str(exc))

    payload = asdict(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"change boundary: {result.mode}; "
        f"controller={len(result.controller_paths)}; "
        f"data={len(result.data_paths)}; neutral={len(result.neutral_paths)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
