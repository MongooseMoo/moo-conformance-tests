"""Resolved-path confinement for candidate-owned conformance data."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator


class CandidatePathError(ValueError):
    """Candidate data resolves outside its independently supplied checkout anchor."""


def resolve_candidate_anchor(path: str | Path) -> Path:
    """Resolve an independently supplied candidate checkout directory."""
    anchor = _resolve_existing(path, "candidate checkout root")
    if not anchor.is_dir():
        raise CandidatePathError(f"candidate checkout root is not a directory: {path}")
    return anchor


def require_confined_path(
    candidate_anchor: str | Path,
    path: str | Path,
    *,
    label: str,
    kind: str | None = None,
) -> Path:
    """Resolve a path and require it to remain under the resolved candidate anchor."""
    anchor = resolve_candidate_anchor(candidate_anchor)
    resolved = _resolve_existing(path, label)
    try:
        resolved.relative_to(anchor)
    except ValueError as exc:
        raise CandidatePathError(f"{label} escapes candidate checkout root: {path}") from exc
    if kind == "file" and not resolved.is_file():
        raise CandidatePathError(f"{label} is not a file: {path}")
    if kind == "directory" and not resolved.is_dir():
        raise CandidatePathError(f"{label} is not a directory: {path}")
    return resolved


def iter_confined_files(
    candidate_anchor: str | Path,
    tree_root: str | Path,
    *,
    root_label: str,
    entry_label: str,
) -> Iterator[Path]:
    """Validate a tree without following linked directories and yield its files."""
    anchor = resolve_candidate_anchor(candidate_anchor)
    root = require_confined_path(anchor, tree_root, label=root_label, kind="directory")
    for current, directory_names, file_names in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        for name in list(directory_names):
            entry = current_path / name
            require_confined_path(anchor, entry, label=entry_label, kind="directory")
            if _is_link_or_junction(entry):
                directory_names.remove(name)
        for name in file_names:
            entry = current_path / name
            require_confined_path(anchor, entry, label=entry_label, kind="file")
            yield entry


def validate_confined_tree(
    candidate_anchor: str | Path,
    tree_root: str | Path,
    *,
    root_label: str,
    entry_label: str,
) -> Path:
    """Validate every reachable entry in a candidate tree."""
    root = require_confined_path(
        candidate_anchor,
        tree_root,
        label=root_label,
        kind="directory",
    )
    list(
        iter_confined_files(
            candidate_anchor,
            root,
            root_label=root_label,
            entry_label=entry_label,
        )
    )
    return root


def _resolve_existing(path: str | Path, label: str) -> Path:
    try:
        return Path(path).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise CandidatePathError(f"{label} cannot be resolved: {path}: {exc}") from exc


def _is_link_or_junction(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction is not None and is_junction())
