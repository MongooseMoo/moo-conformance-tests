import re
from pathlib import Path

import yaml

WORKFLOW_PATH = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "paired-candidates.yml"
)
TOAST_WORKFLOW_PATH = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "toast-conformance.yml"
)
PINNED_ACTION = re.compile(r"^[^@]+@[0-9a-f]{40}$")


def load_workflow() -> dict[str, object]:
    return yaml.load(WORKFLOW_PATH.read_text(), Loader=yaml.BaseLoader)


def load_toast_workflow() -> dict[str, object]:
    return yaml.load(TOAST_WORKFLOW_PATH.read_text(), Loader=yaml.BaseLoader)


def steps_by_name(
    workflow: dict[str, object], job_name: str = "paired"
) -> dict[str, dict[str, object]]:
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    job = jobs[job_name]
    assert isinstance(job, dict)
    steps = job["steps"]
    assert isinstance(steps, list)
    return {step["name"]: step for step in steps}


def test_paired_workflow_uses_default_branch_repository_dispatch() -> None:
    workflow = load_workflow()
    triggers = workflow["on"]
    assert isinstance(triggers, dict)
    dispatch = triggers["repository_dispatch"]
    assert isinstance(dispatch, dict)
    assert dispatch["types"] == ["paired-candidate"]


def test_paired_workflow_requires_complete_toast_admission_for_candidate() -> None:
    workflow = load_workflow()
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)

    toast_admission = jobs["toast-admission"]
    assert toast_admission == {
        "name": "Complete Toast admission",
        "needs": ["validate-inputs"],
        "uses": "./.github/workflows/toast-conformance.yml",
        "with": {
            "conformance_sha": "${{ needs.validate-inputs.outputs.conformance_sha }}"
        },
    }

    paired = jobs["paired"]
    assert isinstance(paired, dict)
    assert paired["needs"] == ["validate-inputs", "toast-admission"]


def test_paired_workflow_validates_refs_before_any_candidate_checkout() -> None:
    workflow = load_workflow()
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    validation = jobs["validate-inputs"]
    assert isinstance(validation, dict)
    assert validation["outputs"] == {
        "barn_sha": "${{ steps.validate.outputs.barn_sha }}",
        "conformance_sha": "${{ steps.validate.outputs.conformance_sha }}",
    }
    steps = steps_by_name(workflow, "validate-inputs")
    validate = steps["Reject mutable or malformed candidate refs"]
    assert validate["id"] == "validate"
    assert "^[0-9a-f]{40}$" in validate["run"]
    assert "printf 'barn_sha=%s\\n' \"$BARN_SHA\"" in validate["run"]
    assert "printf 'conformance_sha=%s\\n' \"$CONFORMANCE_SHA\"" in validate["run"]


def test_toast_workflow_accepts_exact_candidate_and_uses_it_in_every_job() -> None:
    workflow = load_toast_workflow()
    triggers = workflow["on"]
    assert isinstance(triggers, dict)
    workflow_call = triggers["workflow_call"]
    assert workflow_call == {
        "inputs": {
            "conformance_sha": {
                "description": "Exact conformance candidate commit",
                "required": "true",
                "type": "string",
            }
        }
    }

    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    for job_name in ("quality", "full-suite", "execution-ledger"):
        checkout = steps_by_name(workflow, job_name)["Check out conformance candidate"]
        assert checkout["with"] == {
            "ref": "${{ inputs.conformance_sha || github.sha }}",
            "persist-credentials": "false",
        }


def test_paired_workflow_is_read_only_and_pins_every_action() -> None:
    workflow = load_workflow()
    assert workflow["permissions"] == {"contents": "read"}

    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    for job_name, job in jobs.items():
        assert isinstance(job, dict)
        if "uses" in job:
            assert job_name == "toast-admission"
            continue
        for name, step in steps_by_name(workflow, job_name).items():
            action = step.get("uses")
            if action is not None:
                assert PINNED_ACTION.fullmatch(
                    action
                ), f"{job_name}/{name} does not pin an action SHA: {action}"


def test_paired_workflow_checks_out_fixed_repositories_without_credentials() -> None:
    workflow = load_workflow()
    steps = steps_by_name(workflow)

    expected = {
        "Check out Barn candidate": (
            "MongooseMoo/barn",
            "${{ needs.validate-inputs.outputs.barn_sha }}",
            "barn",
        ),
        "Check out conformance candidate": (
            "MongooseMoo/moo-conformance-tests",
            "${{ needs.validate-inputs.outputs.conformance_sha }}",
            "conformance",
        ),
    }
    for name, (repository, ref, path) in expected.items():
        checkout = steps[name]["with"]
        assert checkout == {
            "repository": repository,
            "ref": ref,
            "path": path,
            "persist-credentials": "false",
        }

    validate_step = steps_by_name(workflow, "validate-inputs")[
        "Reject mutable or malformed candidate refs"
    ]
    validate_inputs = validate_step["run"]
    assert "^[0-9a-f]{40}$" in validate_inputs
    assert validate_step["env"] == {
        "BARN_SHA": "${{ github.event.client_payload.barn_sha }}",
        "CONFORMANCE_SHA": "${{ github.event.client_payload.conformance_sha }}",
        "EXPECTED_RESULT": "${{ github.event.client_payload.expected_result }}",
        "REQUIRED_BAD_CASE": "${{ github.event.client_payload.required_bad_case }}",
    }


def test_paired_workflow_runs_complete_strict_suite_and_fails_closed_on_evidence() -> None:
    workflow = load_workflow()
    steps = steps_by_name(workflow)

    run_suite = steps["Run every packaged conformance case against Barn"]["run"]
    assert "--pyargs moo_conformance" in run_suite
    assert "--fail-on-unexpected-skip" in run_suite
    assert "--strict-markers" in run_suite
    assert "--junitxml=" in run_suite
    assert "--moo-suite-path" not in run_suite
    assert "-k " not in run_suite

    validate = steps_by_name(workflow, "verdict")["Validate the expected paired result"][
        "run"
    ]
    assert "python -m moo_conformance.paired_result" in validate
    assert '--expected="$EXPECTED_RESULT"' in validate
    assert '--exit-code="$CONFORMANCE_EXIT"' in validate
    assert '--required-bad-case="$REQUIRED_BAD_CASE"' in validate
    assert '--expected-ids="raw-evidence/expected-case-ids.json"' in validate
    assert "--report=" in validate
    assert "--output=" in validate

    raw_upload = steps["Upload raw paired evidence"]["with"]
    final_upload = steps_by_name(workflow, "verdict")["Upload final paired verdict"]["with"]
    assert raw_upload["if-no-files-found"] == "error"
    assert final_upload["if-no-files-found"] == "error"


def test_candidate_quality_runs_from_the_conformance_repository_root() -> None:
    workflow = load_workflow()
    quality = steps_by_name(workflow)["Run conformance candidate quality gates"]

    assert quality["working-directory"] == "conformance"
    commands = quality["run"]
    assert "pytest tests --strict-markers -q" in commands
    assert "--baseline ci/duplicate-baseline.json" in commands
    assert "ruff check ." in commands
    assert "mypy src/moo_conformance" in commands
    assert "conformance/tests" not in commands
    assert "conformance/ci" not in commands
    assert "conformance/src" not in commands


def test_paired_workflow_records_requested_and_resolved_provenance() -> None:
    workflow = load_workflow()
    record = steps_by_name(workflow)["Record exact candidate provenance"]
    env = record["env"]

    assert env["REQUESTED_BARN_SHA"] == "${{ needs.validate-inputs.outputs.barn_sha }}"
    assert env["REQUESTED_CONFORMANCE_SHA"] == (
        "${{ needs.validate-inputs.outputs.conformance_sha }}"
    )
    assert "git -C barn rev-parse HEAD" in record["run"]
    assert "git -C conformance rev-parse HEAD" in record["run"]

    final_record = steps_by_name(workflow, "verdict")["Record final paired provenance"]
    assert final_record["env"]["WORKFLOW_SHA"] == "${{ github.workflow_sha }}"


def test_verdict_job_uses_trusted_controller_and_no_candidate_code() -> None:
    workflow = load_workflow()
    jobs = workflow["jobs"]
    verdict = jobs["verdict"]
    assert verdict["if"] == "always()"
    assert verdict["needs"] == ["paired"]

    steps = steps_by_name(workflow, "verdict")
    controller = steps["Check out trusted controller"]["with"]
    assert controller == {
        "repository": "MongooseMoo/moo-conformance-tests",
        "ref": "${{ github.workflow_sha }}",
        "path": "controller",
        "persist-credentials": "false",
    }
    assert all(
        "conformance" not in step.get("working-directory", "") for step in steps.values()
    )
