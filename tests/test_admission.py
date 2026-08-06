import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import moo_conformance.test_conformance as canonical_tests
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
from moo_conformance.plugin import (
    _admission_runtime_state,
    _record_canonical_admission_report,
    _record_managed_lifecycle_failure,
)
from moo_conformance.server import ManagedServerLifecycleError

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


def _canonical_item():
    return SimpleNamespace(
        module=canonical_tests,
        obj=canonical_tests.test_capability_admission,
        name="test_capability_admission",
        config=SimpleNamespace(),
        session=SimpleNamespace(shouldfail=False),
    )


def test_failed_exact_canonical_admission_never_authorizes_packaged_runtime() -> None:
    item = _canonical_item()
    _record_canonical_admission_report(
        item,
        SimpleNamespace(when="setup", passed=True, failed=False, skipped=False),
    )
    _record_canonical_admission_report(
        item,
        SimpleNamespace(when="call", passed=False, failed=True, skipped=False),
    )

    assert not _admission_runtime_state(item.config).authorized
    assert "did not pass" in item.session.shouldfail


def test_skipped_exact_canonical_admission_never_authorizes_packaged_runtime() -> None:
    item = _canonical_item()
    _record_canonical_admission_report(
        item,
        SimpleNamespace(when="setup", passed=False, failed=False, skipped=True),
    )

    assert not _admission_runtime_state(item.config).authorized
    assert "did not pass" in item.session.shouldfail


def test_exact_canonical_admission_authorizes_only_after_successful_teardown() -> None:
    item = _canonical_item()
    for when in ("setup", "call"):
        _record_canonical_admission_report(
            item,
            SimpleNamespace(when=when, passed=True, failed=False, skipped=False),
        )
        assert not _admission_runtime_state(item.config).authorized

    _record_canonical_admission_report(
        item,
        SimpleNamespace(when="teardown", passed=True, failed=False, skipped=False),
    )

    assert _admission_runtime_state(item.config).authorized


def test_packaged_lifecycle_failure_stops_remaining_packaged_execution() -> None:
    item = SimpleNamespace(
        module=canonical_tests,
        obj=canonical_tests.test_yaml_conformance,
        name="test_yaml_conformance[fixture]",
        session=SimpleNamespace(shouldfail=False),
    )
    failure = ManagedServerLifecycleError(
        "server died",
        returncode=17,
        log_tail="first diagnostic",
    )

    _record_managed_lifecycle_failure(
        item,
        SimpleNamespace(excinfo=SimpleNamespace(value=failure)),
        SimpleNamespace(failed=True),
    )

    assert "managed server lifecycle failed" in item.session.shouldfail
    assert "17" in item.session.shouldfail


def test_ordinary_packaged_failure_does_not_stop_the_session() -> None:
    item = SimpleNamespace(
        module=canonical_tests,
        obj=canonical_tests.test_yaml_conformance,
        name="test_yaml_conformance[ordinary]",
        session=SimpleNamespace(shouldfail=False),
    )

    _record_managed_lifecycle_failure(
        item,
        SimpleNamespace(excinfo=SimpleNamespace(value=AssertionError("mismatch"))),
        SimpleNamespace(failed=True),
    )

    assert item.session.shouldfail is False


def _write_successful_admission(path, context=TEST_CONTEXT) -> None:
    write_admission_evidence(
        path,
        run_capability_admission(probe_results(), context=context),
    )


def _make_packaged_probe(pytester, launched, executed) -> Path:
    return pytester.makepyfile(
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


def test_fake_admission_marker_cannot_authorize_packaged_runtime(
    pytester, tmp_path
) -> None:
    launched = tmp_path / "launched"
    executed = tmp_path / "executed"
    _make_packaged_probe(pytester, launched, executed)
    pytester.makepyfile(
        test_fake_admission="""
        def test_fake_admission_item():
            pass
        """
    )
    pytester.makeconftest(
        """
        import pytest

        @pytest.hookimpl(tryfirst=True)
        def pytest_collection_modifyitems(items):
            for item in items:
                if item.name == "test_fake_admission_item":
                    item.add_marker(pytest.mark.admission)
        """
    )

    result = pytester.runpytest("-q", "--strict-markers")

    assert result.ret != pytest.ExitCode.OK
    assert not launched.exists()
    assert not executed.exists()


def test_post_collection_hookwrapper_removal_cannot_authorize_packaged_runtime(
    pytester, tmp_path
) -> None:
    launched = tmp_path / "launched"
    executed = tmp_path / "executed"
    packaged_file = _make_packaged_probe(pytester, launched, executed)
    pytester.makeconftest(
        """
        import pytest

        @pytest.hookimpl(hookwrapper=True)
        def pytest_collection_modifyitems(items):
            yield
            items[:] = [
                item
                for item in items
                if not (
                    item.name == "test_capability_admission"
                    and item.module.__name__ == "moo_conformance.test_conformance"
                )
            ]
        """
    )

    result = pytester.runpytest(
        "-q",
        "--strict-markers",
        "-k",
        "capability_admission or packaged",
        str(Path(canonical_tests.__file__).resolve()),
        str(packaged_file),
    )

    assert result.ret != pytest.ExitCode.OK
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
