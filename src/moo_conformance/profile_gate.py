"""Profile metadata gate for managed Toast/Barn comparisons."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ProfileGateError(RuntimeError):
    """Raised when two profile manifests cannot be compared."""


REQUIRED_FEATURE_KEYS = ("option.OUTBOUND_NETWORK", "option.PROMOTE_NUMBERS")
REQUIRED_TOP_LEVEL_KEYS = ("database_fixture", "database_checksum", "runtime_os")
ACCEPTED_SUPPORT_STATUSES = frozenset({"supported", "diagnostic"})


def load_manifest(path: str | Path) -> dict[str, Any]:
    manifest_path = Path(path)
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProfileGateError(f"profile manifest not found: {manifest_path}") from exc
    except json.JSONDecodeError as exc:
        raise ProfileGateError(f"profile manifest is not valid JSON: {manifest_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ProfileGateError(f"profile manifest must be a JSON object: {manifest_path}")
    return data


def validate_profile_pair(oracle: dict[str, Any], target: dict[str, Any]) -> None:
    for manifest, label in ((oracle, "oracle"), (target, "target")):
        status = manifest.get("support_status")
        if status == "unsupported":
            reason = manifest.get("unsupported_reason") or "no reason provided"
            raise ProfileGateError(
                f"unsupported-profile: {manifest.get('profile_id', '<unknown>')}: {reason}"
            )
        if status not in ACCEPTED_SUPPORT_STATUSES:
            raise ProfileGateError(
                f"invalid-comparison: {label} manifest has invalid support_status {status!r}"
            )

    oracle_features = _features(oracle, "oracle")
    target_features = _features(target, "target")

    for key in REQUIRED_FEATURE_KEYS:
        oracle_value = _required_feature(oracle_features, key, "oracle")
        target_value = _required_feature(target_features, key, "target")
        if not isinstance(oracle_value, bool):
            raise ProfileGateError(f"oracle manifest feature {key} must be a JSON boolean")
        if not isinstance(target_value, bool):
            raise ProfileGateError(f"target manifest feature {key} must be a JSON boolean")
        if oracle_value != target_value:
            raise ProfileGateError(
                "invalid-comparison: feature "
                f"{key} differs: oracle={oracle_value!r} target={target_value!r}"
            )

    for key in REQUIRED_TOP_LEVEL_KEYS:
        oracle_value = _required_top_level(oracle, key, "oracle")
        target_value = _required_top_level(target, key, "target")
        if oracle_value != target_value:
            raise ProfileGateError(
                "invalid-comparison: manifest "
                f"{key} differs: oracle={oracle_value!r} target={target_value!r}"
            )


def validate_manifest_paths(oracle_path: str | Path, target_path: str | Path) -> None:
    validate_profile_pair(load_manifest(oracle_path), load_manifest(target_path))


def _features(manifest: dict[str, Any], label: str) -> dict[str, Any]:
    features = manifest.get("features")
    if not isinstance(features, dict):
        raise ProfileGateError(f"{label} manifest missing object features")
    return features


def _required_feature(features: dict[str, Any], key: str, label: str) -> Any:
    if key not in features:
        raise ProfileGateError(f"{label} manifest missing feature {key}")
    return features[key]


def _required_top_level(manifest: dict[str, Any], key: str, label: str) -> Any:
    if key not in manifest:
        raise ProfileGateError(f"{label} manifest missing field {key}")
    return manifest[key]
