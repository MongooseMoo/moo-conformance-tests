import re
from pathlib import Path

import yaml

WORKFLOW_PATH = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "paired-candidates.yml"
)
TOAST_WORKFLOW_PATH = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "toast-conformance.yml"
)
PINNED_ACTION = re.compile(r"^[^@]+@[0-9a-f]{40}$")


def load_workflow(path=WORKFLOW_PATH):
    return yaml.load(path.read_text(), Loader=yaml.BaseLoader)


def steps_by_name(workflow, job_name="paired"):
    return {step["name"]: step for step in workflow["jobs"][job_name]["steps"]}


def test_paired_workflow_uses_default_branch_repository_dispatch() -> None:
    assert load_workflow()["on"]["repository_dispatch"]["types"] == ["paired-candidate"]


def test_complete_three_profile_toast_admission_remains_unconditional() -> None:
    workflow = load_workflow()
    assert workflow["jobs"]["toast-admission"] == {
        "name": "Complete Toast admission",
        "needs": ["validate-inputs"],
        "uses": "./.github/workflows/toast-conformance.yml",
        "with": {"conformance_sha": "${{ needs.validate-inputs.outputs.conformance_sha }}"},
    }
    assert workflow["jobs"]["paired"]["needs"] == ["validate-inputs", "toast-admission"]


def test_toast_workflow_uses_exact_candidate_in_every_profile_job() -> None:
    workflow = load_workflow(TOAST_WORKFLOW_PATH)
    assert workflow["on"]["workflow_call"] == {
        "inputs": {
            "conformance_sha": {
                "description": "Exact conformance candidate commit",
                "required": "true",
                "type": "string",
            }
        }
    }
    for job_name in ("quality", "full-suite", "execution-ledger"):
        checkout = steps_by_name(workflow, job_name)["Check out conformance candidate"]
        assert checkout["with"]["ref"] == "${{ inputs.conformance_sha || github.sha }}"
        assert checkout["with"]["persist-credentials"] == "false"


def test_each_toast_profile_stages_admission_before_complete_packaged_surface() -> None:
    steps = steps_by_name(load_workflow(TOAST_WORKFLOW_PATH), "full-suite")
    names = list(steps)
    admission_name = "Run canonical capability admission against Toast"
    packaged_name = "Run every packaged conformance case against Toast"
    assert names.index(admission_name) < names.index(packaged_name)
    admission = steps[admission_name]["run"]
    assert "-m admission" in admission
    assert "--admission-evidence-output=" in admission
    assert "--junitxml=" in admission
    assert "set +e" not in admission
    packaged = steps[packaged_name]["run"]
    assert "-m conformance" in packaged
    assert "--fail-on-unexpected-skip" in packaged


def test_input_validation_requires_explicit_phase_and_exact_identity_array() -> None:
    workflow = load_workflow()
    validation = workflow["jobs"]["validate-inputs"]
    assert validation["outputs"] == {
        "barn_sha": "${{ steps.validate.outputs.barn_sha }}",
        "conformance_sha": "${{ steps.validate.outputs.conformance_sha }}",
        "expected_phase": "${{ steps.validate.outputs.expected_phase }}",
        "required_bad_identities": "${{ steps.validate.outputs.required_bad_identities }}",
    }
    validate = steps_by_name(workflow, "validate-inputs")[
        "Reject mutable or malformed candidate inputs"
    ]
    assert validate["env"] == {
        "BARN_SHA": "${{ github.event.client_payload.barn_sha }}",
        "CONFORMANCE_SHA": "${{ github.event.client_payload.conformance_sha }}",
        "EXPECTED_RESULT": "${{ github.event.client_payload.expected_result }}",
        "EXPECTED_PHASE": "${{ github.event.client_payload.expected_phase }}",
        "REQUIRED_BAD_IDENTITIES": (
            "${{ toJSON(github.event.client_payload.required_bad_identities) }}"
        ),
    }
    script = validate["run"]
    assert "expected_phase must be admission or packaged" in script
    assert "expected success requires packaged phase" in script
    assert "required_bad_identities must be a JSON array" in script
    assert "required_bad_identities contains duplicates" in script
    for identity in (
        "admission::option.OUTBOUND_NETWORK",
        "admission::feature.connectable_listener_port",
        "admission::feature.ephemeral_listen",
        "admission::option.PROMOTE_NUMBERS",
    ):
        assert identity in script


def test_paired_workflow_is_read_only_and_pins_every_action() -> None:
    workflow = load_workflow()
    assert workflow["permissions"] == {"contents": "read"}
    for job_name, job in workflow["jobs"].items():
        if "uses" in job:
            assert job_name == "toast-admission"
            continue
        for name, step in steps_by_name(workflow, job_name).items():
            action = step.get("uses")
            if action is not None:
                assert PINNED_ACTION.fullmatch(action), f"{job_name}/{name} is not SHA-pinned"


def test_candidate_quality_gates_run_from_candidate_root() -> None:
    quality = steps_by_name(load_workflow())["Run conformance candidate quality gates"]
    assert quality["working-directory"] == "conformance"
    commands = quality["run"]
    assert "pytest tests --strict-markers -q" in commands
    assert "pytest --collect-only --pyargs moo_conformance --strict-markers -q" in commands
    assert "moo-lint-duplicates" in commands
    assert "ruff check ." in commands
    assert "mypy src/moo_conformance" in commands


def test_candidate_run_is_staged_and_packaged_execution_is_success_gated() -> None:
    steps = steps_by_name(load_workflow())
    admission = steps["Run canonical capability admission against Barn"]
    assert admission["id"] == "admission"
    assert "-m admission" in admission["run"]
    assert "--admission-evidence-output=" in admission["run"]
    assert "--junitxml=" in admission["run"]
    assert "exit 0" in admission["run"]

    packaged = steps["Run every packaged conformance case against Barn"]
    assert packaged["id"] == "packaged"
    assert packaged["if"] == "steps.admission.outputs.exit_code == '0'"
    assert "-m conformance" in packaged["run"]
    assert "--pyargs moo_conformance" in packaged["run"]
    assert "--fail-on-unexpected-skip" in packaged["run"]
    assert "--moo-suite-path" not in packaged["run"]
    assert "-k " not in packaged["run"]


def test_paired_outputs_include_both_phase_exit_codes_and_exact_declaration() -> None:
    outputs = load_workflow()["jobs"]["paired"]["outputs"]
    assert outputs["admission_exit"] == "${{ steps.admission.outputs.exit_code }}"
    assert outputs["packaged_exit"] == "${{ steps.packaged.outputs.exit_code }}"
    assert outputs["expected_phase"] == "${{ needs.validate-inputs.outputs.expected_phase }}"
    assert outputs["required_bad_identities"] == (
        "${{ needs.validate-inputs.outputs.required_bad_identities }}"
    )


def test_trusted_controller_validates_phase_appropriate_raw_evidence() -> None:
    validate = steps_by_name(load_workflow(), "verdict")[
        "Validate the expected staged result"
    ]
    assert validate["env"]["EXPECTED_PHASE"] == "${{ needs.paired.outputs.expected_phase }}"
    assert validate["env"]["REQUIRED_BAD_IDENTITIES"] == (
        "${{ needs.paired.outputs.required_bad_identities }}"
    )
    command = validate["run"]
    assert "python -m moo_conformance.paired_result" in command
    assert '--admission="raw-evidence/admission.json"' in command
    assert '--phase="$EXPECTED_PHASE"' in command
    assert '--admission-exit-code="$ADMISSION_EXIT"' in command
    assert '--required-bad-identities="$REQUIRED_BAD_IDENTITIES"' in command
    assert "--report=" in command
    assert "--packaged-exit-code=" in command


def test_schema_v3_provenance_records_declared_and_observed_phase_identity_sets() -> None:
    workflow = load_workflow()
    provenance = steps_by_name(workflow, "verdict")["Record final staged provenance"]["run"]
    assert '"schema_version": 3' in provenance
    assert '"phase": result["phase"]' in provenance
    assert '"declared_bad_identities": result["declared_bad_identities"]' in provenance
    assert '"observed_bad_identities": result["observed_bad_identities"]' in provenance
    summary = steps_by_name(workflow, "verdict")["Publish staged result summary"]["run"]
    assert "Declared bad identities" in summary
    assert "Observed bad identities" in summary


def test_workflow_has_no_legacy_case_only_failure_declaration() -> None:
    text = WORKFLOW_PATH.read_text()
    assert "required_bad_identities" in text
    assert "expected_phase" in text
    assert "required_bad_cases" not in text


def test_verdict_uses_trusted_default_branch_controller() -> None:
    workflow = load_workflow()
    verdict = workflow["jobs"]["verdict"]
    assert verdict["if"] == "always()"
    assert verdict["needs"] == ["paired"]
    checkout = steps_by_name(workflow, "verdict")["Check out trusted controller"]["with"]
    assert checkout == {
        "repository": "MongooseMoo/moo-conformance-tests",
        "ref": "${{ github.workflow_sha }}",
        "path": "controller",
        "persist-credentials": "false",
    }
