import json

import pytest

from moo_conformance.profile_gate import ProfileGateError, validate_manifest_paths, validate_profile_pair


def manifest(outbound: bool, fixture: str = "testdb", runtime_os: str = "linux") -> dict:
    return {
        "profile_id": "profile",
        "implementation": "server",
        "runtime_os": runtime_os,
        "database_fixture": fixture,
        "support_status": "supported",
        "features": {
            "option.OUTBOUND_NETWORK": outbound,
        },
    }


def test_validate_profile_pair_rejects_outbound_mismatch():
    with pytest.raises(ProfileGateError, match="invalid-comparison"):
        validate_profile_pair(manifest(True), manifest(False))


def test_validate_profile_pair_accepts_matching_outbound_off():
    validate_profile_pair(manifest(False), manifest(False))


def test_validate_profile_pair_rejects_unsupported_target():
    target = manifest(False)
    target["support_status"] = "unsupported"
    target["unsupported_reason"] = "missing oracle"

    with pytest.raises(ProfileGateError, match="unsupported-profile"):
        validate_profile_pair(manifest(False), target)


def test_validate_profile_pair_rejects_missing_feature():
    target = manifest(False)
    target["features"] = {}

    with pytest.raises(ProfileGateError, match="missing feature option.OUTBOUND_NETWORK"):
        validate_profile_pair(manifest(False), target)


def test_validate_profile_pair_rejects_database_fixture_mismatch():
    with pytest.raises(ProfileGateError, match="database_fixture differs"):
        validate_profile_pair(manifest(False, fixture="mongoose"), manifest(False, fixture="testdb"))


def test_validate_manifest_paths_loads_json(tmp_path):
    oracle = tmp_path / "oracle.json"
    target = tmp_path / "target.json"
    oracle.write_text(json.dumps(manifest(False)), encoding="utf-8")
    target.write_text(json.dumps(manifest(False)), encoding="utf-8")

    validate_manifest_paths(oracle, target)
