import json

import pytest

from moo_conformance.admission import (
    ADMISSION_PROBE_INVENTORY,
    AdmissionEvidenceError,
    CapabilityProbeError,
    CapabilityProbeFailure,
    load_admission_evidence,
    run_capability_admission,
    validate_admission_evidence,
    write_admission_evidence,
)

pytest_plugins = ("pytester",)
TEST_CONTEXT = "test:admission-context"


def probe_results(**overrides):
    results = {identity: True for identity in ADMISSION_PROBE_INVENTORY}
    results.update(overrides)

    def probe(identity):
        result = results[identity]
        if isinstance(result, Exception):
            raise result
        return result

    return probe


def test_admission_success_records_complete_canonical_inventory(tmp_path) -> None:
    evidence = run_capability_admission(probe_results(), context=TEST_CONTEXT)
    path = tmp_path / "admission.json"
    write_admission_evidence(path, evidence)

    loaded = load_admission_evidence(path, expected_context=TEST_CONTEXT)

    assert loaded == evidence
    assert evidence["schema_version"] == 2
    assert evidence["phase"] == "admission"
    assert evidence["context"] == TEST_CONTEXT
    assert [probe["identity"] for probe in evidence["probes"]] == list(
        ADMISSION_PROBE_INVENTORY
    )
    assert {probe["status"] for probe in evidence["probes"]} == {"passed"}
    assert all(probe["prerequisite_blocked_by"] == [] for probe in evidence["probes"])


def test_admission_failure_blocks_only_its_declared_dependent() -> None:
    evidence = run_capability_admission(
        probe_results(
            **{
                "admission::option.OUTBOUND_NETWORK": CapabilityProbeFailure(
                    "permission denied"
                )
            }
        ),
        context=TEST_CONTEXT,
    )

    probes = {probe["identity"]: probe for probe in evidence["probes"]}
    assert probes["admission::option.OUTBOUND_NETWORK"]["status"] == "failed"
    assert probes["admission::feature.connectable_listener_port"] == {
        "identity": "admission::feature.connectable_listener_port",
        "status": "blocked",
        "prerequisite_blocked_by": ["admission::option.OUTBOUND_NETWORK"],
    }
    assert probes["admission::feature.ephemeral_listen"]["status"] == "passed"
    assert probes["admission::option.PROMOTE_NUMBERS"]["status"] == "passed"


def test_admission_error_is_distinct_from_probe_failure() -> None:
    evidence = run_capability_admission(
        probe_results(
            **{
                "admission::feature.ephemeral_listen": CapabilityProbeError(
                    "malformed result"
                )
            }
        ),
        context=TEST_CONTEXT,
    )

    probes = {probe["identity"]: probe for probe in evidence["probes"]}
    assert probes["admission::feature.ephemeral_listen"]["status"] == "error"
    assert probes["admission::feature.ephemeral_listen"]["detail"] == "malformed result"


@pytest.mark.parametrize(
    "mutator",
    [
        lambda evidence: evidence.update(schema_version=1),
        lambda evidence: evidence.update(phase="packaged"),
        lambda evidence: evidence.update(context=""),
        lambda evidence: evidence["probes"].pop(),
        lambda evidence: evidence["probes"].append(dict(evidence["probes"][0])),
        lambda evidence: evidence["probes"][0].update(identity="admission::unknown"),
        lambda evidence: evidence["probes"][0].update(status="skipped"),
        lambda evidence: evidence["probes"][0].update(unexpected=True),
        lambda evidence: evidence["probes"][1].update(
            status="blocked", prerequisite_blocked_by=[]
        ),
    ],
)
def test_admission_evidence_rejects_malformed_or_inexact_inventory(mutator) -> None:
    evidence = run_capability_admission(probe_results(), context=TEST_CONTEXT)
    mutator(evidence)

    with pytest.raises(AdmissionEvidenceError):
        validate_admission_evidence(evidence)


def test_load_admission_evidence_rejects_invalid_json(tmp_path) -> None:
    path = tmp_path / "admission.json"
    path.write_text("not json")

    with pytest.raises(AdmissionEvidenceError, match="cannot read admission evidence"):
        load_admission_evidence(path)


def test_load_admission_evidence_rejects_mismatched_context(tmp_path) -> None:
    path = tmp_path / "admission.json"
    write_admission_evidence(
        path,
        run_capability_admission(probe_results(), context=TEST_CONTEXT),
    )

    with pytest.raises(AdmissionEvidenceError, match="context mismatch"):
        load_admission_evidence(path, expected_context="other-context")


def test_write_admission_evidence_refuses_malformed_data(tmp_path) -> None:
    path = tmp_path / "admission.json"
    evidence = run_capability_admission(probe_results(), context=TEST_CONTEXT)
    evidence["probes"][0]["status"] = "unknown"

    with pytest.raises(AdmissionEvidenceError):
        write_admission_evidence(path, evidence)

    assert not path.exists()


def test_admission_evidence_json_is_stable_and_schema_versioned(tmp_path) -> None:
    path = tmp_path / "admission.json"
    evidence = run_capability_admission(probe_results(), context=TEST_CONTEXT)

    write_admission_evidence(path, evidence)

    assert json.loads(path.read_text()) == evidence
    assert path.read_text().endswith("\n")


def test_unfiltered_pytest_stops_before_packaged_items_when_admission_fails(
    pytester, tmp_path
) -> None:
    packaged_marker = tmp_path / "packaged-ran"
    pytester.makepyfile(
        f"""
        from pathlib import Path
        import pytest

        @pytest.mark.conformance
        def test_packaged():
            Path({str(packaged_marker)!r}).write_text("ran")

        @pytest.mark.admission
        def test_admission():
            pytest.fail("probe failed")
        """
    )

    result = pytester.runpytest("-q", "--strict-markers")

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.assert_outcomes(failed=1)
    assert not packaged_marker.exists()


def test_unfiltered_pytest_stops_before_packaged_items_when_admission_skips(
    pytester, tmp_path
) -> None:
    packaged_marker = tmp_path / "packaged-ran"
    pytester.makepyfile(
        f"""
        from pathlib import Path
        import pytest

        @pytest.mark.conformance
        def test_packaged():
            Path({str(packaged_marker)!r}).write_text("ran")

        @pytest.mark.admission
        def test_capability_admission():
            pytest.skip("probe unavailable")
        """
    )

    result = pytester.runpytest("-q", "--strict-markers")

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.assert_outcomes(skipped=1)
    assert not packaged_marker.exists()


def test_unfiltered_pytest_runs_packaged_items_after_admission_succeeds(
    pytester, tmp_path
) -> None:
    packaged_marker = tmp_path / "packaged-ran"
    pytester.makepyfile(
        f"""
        from pathlib import Path
        import pytest

        @pytest.mark.conformance
        def test_packaged():
            Path({str(packaged_marker)!r}).write_text("ran")

        @pytest.mark.admission
        def test_admission():
            pass
        """
    )

    result = pytester.runpytest("-q", "--strict-markers")

    result.assert_outcomes(passed=2)
    assert packaged_marker.read_text() == "ran"


def _write_successful_admission(path, context=TEST_CONTEXT) -> None:
    write_admission_evidence(
        path,
        run_capability_admission(probe_results(), context=context),
    )


def _make_packaged_probe(pytester, launched, executed) -> None:
    pytester.makepyfile(
        f"""
        from pathlib import Path
        import pytest

        @pytest.fixture
        def managed_server_probe():
            Path({str(launched)!r}).write_text("launched")

        @pytest.mark.conformance
        def test_packaged(managed_server_probe):
            Path({str(executed)!r}).write_text("executed")
        """
    )


def test_marker_filtered_packaged_run_requires_and_validates_admission_artifact(
    pytester, tmp_path
) -> None:
    launched = tmp_path / "launched"
    executed = tmp_path / "executed"
    evidence = tmp_path / "admission.json"
    _write_successful_admission(evidence)
    _make_packaged_probe(pytester, launched, executed)

    result = pytester.runpytest(
        "-q",
        "--strict-markers",
        "-m",
        "conformance",
        f"--admission-evidence-input={evidence}",
        f"--admission-evidence-context={TEST_CONTEXT}",
    )

    result.assert_outcomes(passed=1, deselected=0)
    assert launched.read_text() == "launched"
    assert executed.read_text() == "executed"


def test_k_filter_cannot_remove_admission_and_execute_packaged_items(
    pytester, tmp_path
) -> None:
    launched = tmp_path / "launched"
    executed = tmp_path / "executed"
    _make_packaged_probe(pytester, launched, executed)
    pytester.makepyfile(
        test_capability_admission="""
        import pytest

        @pytest.mark.admission
        def test_capability_admission():
            pass
        """
    )

    result = pytester.runpytest(
        "-q", "--strict-markers", "-k", "not capability_admission"
    )

    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*selected packaged conformance requires*"])
    assert not launched.exists()
    assert not executed.exists()


@pytest.mark.parametrize(
    "artifact", ["missing-option", "missing", "malformed", "mismatch", "unsuccessful"]
)
def test_invalid_external_admission_fails_before_packaged_server_or_case(
    pytester, tmp_path, artifact
) -> None:
    launched = tmp_path / "launched"
    executed = tmp_path / "executed"
    evidence = tmp_path / "admission.json"
    _make_packaged_probe(pytester, launched, executed)
    arguments = ["-q", "--strict-markers", "-m", "conformance"]
    if artifact == "missing":
        arguments.extend(
            [
                f"--admission-evidence-input={evidence}",
                f"--admission-evidence-context={TEST_CONTEXT}",
            ]
        )
    elif artifact == "malformed":
        evidence.write_text("not json")
        arguments.extend(
            [
                f"--admission-evidence-input={evidence}",
                f"--admission-evidence-context={TEST_CONTEXT}",
            ]
        )
    elif artifact == "mismatch":
        _write_successful_admission(evidence, context="other-context")
        arguments.extend(
            [
                f"--admission-evidence-input={evidence}",
                f"--admission-evidence-context={TEST_CONTEXT}",
            ]
        )
    elif artifact == "unsuccessful":
        write_admission_evidence(
            evidence,
            run_capability_admission(
                probe_results(
                    **{
                        "admission::option.OUTBOUND_NETWORK": CapabilityProbeFailure(
                            "denied"
                        )
                    }
                ),
                context=TEST_CONTEXT,
            ),
        )
        arguments.extend(
            [
                f"--admission-evidence-input={evidence}",
                f"--admission-evidence-context={TEST_CONTEXT}",
            ]
        )

    result = pytester.runpytest(*arguments)

    assert result.ret == pytest.ExitCode.USAGE_ERROR
    assert not launched.exists()
    assert not executed.exists()
