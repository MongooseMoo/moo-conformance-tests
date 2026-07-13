import json

import pytest

from moo_conformance.profile_gate import ProfileGateError, validate_manifest_paths, validate_profile_pair


def manifest(
    outbound: bool,
    promotion: bool = True,
    fixture: str = "testdb",
    checksum: str = "sha256:fixture",
    runtime_os: str = "linux",
) -> dict:
    return {
        "profile_id": "profile",
        "implementation": "server",
        "runtime_os": runtime_os,
        "database_fixture": fixture,
        "database_checksum": checksum,
        "support_status": "supported",
        "features": {
            "option.OUTBOUND_NETWORK": outbound,
            "option.PROMOTE_NUMBERS": promotion,
        },
    }


def test_validate_profile_pair_rejects_outbound_mismatch():
    with pytest.raises(ProfileGateError, match="invalid-comparison"):
        validate_profile_pair(manifest(True), manifest(False))


def test_validate_profile_pair_accepts_matching_outbound_off_and_promotion_on():
    validate_profile_pair(manifest(False, promotion=True), manifest(False, promotion=True))


def test_validate_profile_pair_accepts_diagnostic_status():
    oracle = manifest(False)
    target = manifest(False)
    oracle["support_status"] = "diagnostic"
    target["support_status"] = "diagnostic"

    validate_profile_pair(oracle, target)


@pytest.mark.parametrize("unsupported_side", ["oracle", "target"])
def test_validate_profile_pair_rejects_unsupported_status(unsupported_side):
    oracle = manifest(False)
    target = manifest(False)
    unsupported = oracle if unsupported_side == "oracle" else target
    unsupported["support_status"] = "unsupported"
    unsupported["unsupported_reason"] = "missing oracle"

    with pytest.raises(ProfileGateError, match="unsupported-profile"):
        validate_profile_pair(oracle, target)


@pytest.mark.parametrize("missing_side", ["oracle", "target"])
def test_validate_profile_pair_rejects_missing_support_status(missing_side):
    oracle = manifest(False)
    target = manifest(False)
    missing = oracle if missing_side == "oracle" else target
    del missing["support_status"]

    with pytest.raises(ProfileGateError, match="support_status"):
        validate_profile_pair(oracle, target)


@pytest.mark.parametrize("invalid_side", ["oracle", "target"])
def test_validate_profile_pair_rejects_unknown_support_status(invalid_side):
    oracle = manifest(False)
    target = manifest(False)
    invalid = oracle if invalid_side == "oracle" else target
    invalid["support_status"] = "experimental"

    with pytest.raises(ProfileGateError, match="invalid support_status"):
        validate_profile_pair(oracle, target)


def test_validate_profile_pair_rejects_missing_feature():
    target = manifest(False)
    target["features"] = {}

    with pytest.raises(ProfileGateError, match="missing feature option.OUTBOUND_NETWORK"):
        validate_profile_pair(manifest(False), target)


@pytest.mark.parametrize("missing_side", ["oracle", "target"])
def test_validate_profile_pair_rejects_missing_promotion(missing_side):
    oracle = manifest(False)
    target = manifest(False)
    missing = oracle if missing_side == "oracle" else target
    del missing["features"]["option.PROMOTE_NUMBERS"]

    with pytest.raises(ProfileGateError, match="missing feature option.PROMOTE_NUMBERS"):
        validate_profile_pair(oracle, target)


def test_validate_profile_pair_rejects_promotion_mismatch():
    with pytest.raises(ProfileGateError, match="option.PROMOTE_NUMBERS differs"):
        validate_profile_pair(manifest(False, promotion=True), manifest(False, promotion=False))


@pytest.mark.parametrize("manifest_side", ["oracle", "target"])
@pytest.mark.parametrize("feature", ["option.OUTBOUND_NETWORK", "option.PROMOTE_NUMBERS"])
def test_validate_profile_pair_rejects_non_boolean_option_values(manifest_side, feature):
    oracle = manifest(True)
    target = manifest(True)
    non_boolean = oracle if manifest_side == "oracle" else target
    non_boolean["features"][feature] = 1

    with pytest.raises(ProfileGateError, match=f"feature {feature} must be a JSON boolean"):
        validate_profile_pair(oracle, target)


def test_validate_profile_pair_rejects_database_fixture_mismatch():
    with pytest.raises(ProfileGateError, match="database_fixture differs"):
        validate_profile_pair(manifest(False, fixture="oracle-db"), manifest(False, fixture="testdb"))


@pytest.mark.parametrize("missing_side", ["oracle", "target"])
def test_validate_profile_pair_rejects_missing_database_checksum(missing_side):
    oracle = manifest(False)
    target = manifest(False)
    missing = oracle if missing_side == "oracle" else target
    del missing["database_checksum"]

    with pytest.raises(ProfileGateError, match="missing field database_checksum"):
        validate_profile_pair(oracle, target)


def test_validate_profile_pair_rejects_database_checksum_mismatch():
    with pytest.raises(ProfileGateError, match="database_checksum differs"):
        validate_profile_pair(
            manifest(False, checksum="sha256:oracle"),
            manifest(False, checksum="sha256:target"),
        )


def test_validate_manifest_paths_loads_json(tmp_path):
    oracle = tmp_path / "oracle.json"
    target = tmp_path / "target.json"
    oracle.write_text(json.dumps(manifest(False)), encoding="utf-8")
    target.write_text(json.dumps(manifest(False)), encoding="utf-8")

    validate_manifest_paths(oracle, target)
