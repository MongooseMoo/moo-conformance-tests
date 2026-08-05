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


def test_toast_pr_check_is_read_only_and_pr_scoped() -> None:
    workflow = load_workflow(TOAST_WORKFLOW_PATH)
    assert workflow["on"]["pull_request"] == ""
    assert "pull_request_target" not in workflow["on"]
    assert workflow["on"]["push"] == {"branches": ["main"]}
    assert workflow["on"]["workflow_call"] == {
        "inputs": {
            "conformance_sha": {
                "description": "Exact conformance candidate commit",
                "required": "true",
                "type": "string",
            }
        }
    }
    assert workflow["permissions"] == {"contents": "read"}
    concurrency = workflow["concurrency"]
    assert "github.event.pull_request.number" in concurrency["group"]
    assert "inputs.conformance_sha" in concurrency["group"]
    assert concurrency["cancel-in-progress"] == (
        "${{ github.event_name == 'pull_request' }}"
    )


def test_toast_workflow_uses_immutable_trusted_and_fork_candidate_checkouts() -> None:
    workflow = load_workflow(TOAST_WORKFLOW_PATH)
    for job_name in ("quality", "full-suite", "execution-ledger"):
        steps = steps_by_name(workflow, job_name)
        trusted = steps["Check out trusted controller"]["with"]
        assert trusted == {
            "repository": "MongooseMoo/moo-conformance-tests",
            "ref": "${{ github.event.pull_request.base.sha || github.workflow_sha }}",
            "path": "trusted-controller",
            "persist-credentials": "false",
        }
        candidate = steps["Check out conformance candidate"]["with"]
        assert candidate == {
            "repository": (
                "${{ github.event.pull_request.head.repo.full_name || github.repository }}"
            ),
            "ref": (
                "${{ inputs.conformance_sha || github.event.pull_request.head.sha || "
                "github.sha }}"
            ),
            "path": "candidate-data",
            "persist-credentials": "false",
        }


def test_toast_workflow_pins_every_action() -> None:
    workflow = load_workflow(TOAST_WORKFLOW_PATH)
    for job_name in workflow["jobs"]:
        for name, step in steps_by_name(workflow, job_name).items():
            action = step.get("uses")
            if action is not None:
                assert PINNED_ACTION.fullmatch(action), f"{job_name}/{name} is not SHA-pinned"


def test_toast_candidate_and_oracle_are_fixed_credentialless_siblings() -> None:
    workflow = load_workflow(TOAST_WORKFLOW_PATH)
    steps = steps_by_name(workflow, "full-suite")
    candidate = steps["Check out conformance candidate"]["with"]
    oracle = steps["Check out pinned Toast oracle"]["with"]

    assert candidate["path"] == "candidate-data"
    assert candidate["persist-credentials"] == "false"
    assert oracle["path"] == "toast-oracle"
    assert oracle["persist-credentials"] == "false"
    assert not oracle["path"].startswith(candidate["path"] + "/")


def test_toast_quality_executes_only_trusted_code_against_candidate_data() -> None:
    steps = steps_by_name(load_workflow(TOAST_WORKFLOW_PATH), "quality")
    assert steps["Install locked trusted controller"]["run"] == (
        "uv sync --project trusted-controller --locked --extra dev"
    )
    quality = steps["Run trusted controller quality gates"]
    assert quality["working-directory"] == "trusted-controller"
    assert "pytest tests --strict-markers" in quality["run"]
    assert "ruff check ." in quality["run"]
    assert "mypy src/moo_conformance" in quality["run"]

    candidate = steps["Validate candidate data with trusted controller"]["run"]
    assert "--project trusted-controller" in candidate
    assert "python -m moo_conformance.paired_inventory" in candidate
    assert "pytest" in candidate and "--collect-only --pyargs moo_conformance" in candidate
    assert "moo-lint-duplicates" in candidate
    assert '--candidate-root="${GITHUB_WORKSPACE}/candidate-data"' in candidate
    assert '--candidate-tests="${GITHUB_WORKSPACE}/candidate-data/' in candidate
    assert '--moo-suite-root="${GITHUB_WORKSPACE}/candidate-data/' in candidate
    assert '--server-db="${GITHUB_WORKSPACE}/candidate-data/' in candidate
    assert '--server-db-dir="${GITHUB_WORKSPACE}/candidate-data/' in candidate
    assert '--tests-dir="${GITHUB_WORKSPACE}/candidate-data/' in candidate
    assert (
        '--baseline="${GITHUB_WORKSPACE}/trusted-controller/ci/duplicate-baseline.json"'
        in candidate
    )


def test_each_toast_profile_stages_admission_before_complete_packaged_surface() -> None:
    steps = steps_by_name(load_workflow(TOAST_WORKFLOW_PATH), "full-suite")
    prepare = steps["Prepare evidence directory"]["run"]
    assert "secrets.token_hex" in prepare
    assert "GITHUB_RUN_ATTEMPT" in prepare
    assert "ADMISSION_CONTEXT" in prepare
    names = list(steps)
    admission_name = "Run canonical capability admission against Toast"
    packaged_name = "Run every packaged conformance case against Toast"
    assert names.index(admission_name) < names.index(packaged_name)
    admission = steps[admission_name]["run"]
    assert '--candidate-root="${GITHUB_WORKSPACE}/candidate-data"' in admission
    assert '--moo-suite-root="${GITHUB_WORKSPACE}/candidate-data/' in admission
    assert '--server-db="${GITHUB_WORKSPACE}/candidate-data/' in admission
    assert '--server-db-dir="${GITHUB_WORKSPACE}/candidate-data/' in admission
    assert "uv run --project trusted-controller --frozen pytest" in admission
    assert "working-directory" not in steps[admission_name]
    assert "${RUNNER_TEMP}/toast-build-${{ matrix.profile }}/moo" in admission
    assert "-m admission" in admission
    assert "--admission-evidence-output=" in admission
    assert "--admission-evidence-context=" in admission
    assert "--junitxml=" in admission
    assert "set +e" not in admission
    packaged = steps[packaged_name]["run"]
    assert '--candidate-root="${GITHUB_WORKSPACE}/candidate-data"' in packaged
    assert '--moo-suite-root="${GITHUB_WORKSPACE}/candidate-data/' in packaged
    assert '--server-db="${GITHUB_WORKSPACE}/candidate-data/' in packaged
    assert '--server-db-dir="${GITHUB_WORKSPACE}/candidate-data/' in packaged
    assert "uv run --project trusted-controller --frozen pytest" in packaged
    assert "working-directory" not in steps[packaged_name]
    assert "${RUNNER_TEMP}/toast-build-${{ matrix.profile }}/moo" in packaged
    assert "-m conformance" in packaged
    assert "--admission-evidence-input=" in packaged
    assert "--admission-evidence-context=" in packaged
    assert "--fail-on-unexpected-skip" in packaged


def test_toast_generated_state_stays_outside_candidate_anchor() -> None:
    workflow = load_workflow(TOAST_WORKFLOW_PATH)
    steps = steps_by_name(workflow, "full-suite")
    prepare = steps["Prepare evidence directory"]["run"]
    assert "UV_PROJECT_ENVIRONMENT" in prepare
    assert "${RUNNER_TEMP}/toast-conformance-venv-${{ matrix.profile }}" in prepare
    build = steps["Build Toast oracle"]["run"]
    assert "${RUNNER_TEMP}/toast-build-${{ matrix.profile }}" in build
    assert "candidate-data" not in build
    boundary = steps["Validate candidate data boundary"]["run"]
    assert "--project trusted-controller" in boundary
    assert "python -m moo_conformance.paired_inventory" in boundary
    assert '--candidate-root="${GITHUB_WORKSPACE}/candidate-data"' in boundary
    assert '--candidate-tests="${GITHUB_WORKSPACE}/candidate-data/' in boundary
    assert '--candidate-db="${GITHUB_WORKSPACE}/candidate-data/' in boundary
    assert '--candidate-db-dir="${GITHUB_WORKSPACE}/candidate-data/' in boundary
    assert '--output="${REPORTS_DIR}/candidate-inventory.json"' in boundary
    assert steps["Verify conformance-owned startup fixtures"]["working-directory"] == (
        "candidate-data/src/moo_conformance/_db/startup"
    )
    fixture_check = steps["Verify conformance-owned startup fixtures"]["run"]
    assert "sha256sum --check" in fixture_check
    assert (
        '"${GITHUB_WORKSPACE}/trusted-controller/'
        "src/moo_conformance/_db/startup/startup-fixtures.sha256\""
        in fixture_check
    )
    assert "sha256sum --check startup-fixtures.sha256" not in fixture_check
    assert "uv " not in fixture_check and "python" not in fixture_check
    profile = steps["Record the exact Toast capability profile"]
    assert "working-directory" not in profile
    assert "uv run --project trusted-controller --frozen python" in profile["run"]
    assert 'Path("candidate-data/src/moo_conformance/_db/Test.db")' in profile["run"]

    ledger_steps = steps_by_name(workflow, "execution-ledger")
    ledger_environment = ledger_steps["Prepare ledger environment"]["run"]
    assert "UV_PROJECT_ENVIRONMENT" in ledger_environment
    assert "${RUNNER_TEMP}/toast-ledger-venv" in ledger_environment
    assert ledger_steps["Download every Toast profile report"]["with"]["path"] == (
        "${{ runner.temp }}/toast-profile-reports"
    )
    inventory = ledger_steps["Recompute trusted candidate inventory"]["run"]
    assert "--project trusted-controller" in inventory
    assert "python -m moo_conformance.paired_inventory" in inventory
    assert '--candidate-root="${GITHUB_WORKSPACE}/candidate-data"' in inventory
    assert '--candidate-tests="${GITHUB_WORKSPACE}/candidate-data/' in inventory
    assert '--candidate-db="${GITHUB_WORKSPACE}/candidate-data/' in inventory
    assert '--candidate-db-dir="${GITHUB_WORKSPACE}/candidate-data/' in inventory
    assert '--output="${RUNNER_TEMP}/toast-candidate-inventory.json"' in inventory
    union = ledger_steps["Enforce exact profile union"]["run"]
    assert "--project trusted-controller" in union
    assert "--project candidate-data" not in union
    assert '--inventory="${RUNNER_TEMP}/toast-candidate-inventory.json"' in union
    assert "--baseline" not in union
    assert "baseline" not in union
    assert "toast-never-executed.json" not in union
    assert "candidate-data/ci" not in union
    assert "${RUNNER_TEMP}/toast-profile-reports" in union
    assert "${RUNNER_TEMP}/toast-execution-ledger.json" in union
    ledger_artifacts = ledger_steps["Upload Toast execution ledger"]["with"]["path"]
    assert "${{ runner.temp }}/toast-candidate-inventory.json" in ledger_artifacts
    assert "${{ runner.temp }}/toast-execution-ledger.json" in ledger_artifacts


def test_toast_jobs_never_execute_or_install_candidate_python() -> None:
    workflow = load_workflow(TOAST_WORKFLOW_PATH)
    workflow_text = TOAST_WORKFLOW_PATH.read_text()
    assert "uv sync --project candidate-data" not in workflow_text
    assert "uv run --project candidate-data" not in workflow_text
    assert "uv sync --project ." not in workflow_text
    assert "uv run --project ." not in workflow_text
    for job_name in workflow["jobs"]:
        for name, step in steps_by_name(workflow, job_name).items():
            working_directory = step.get("working-directory", "")
            if working_directory.startswith("candidate-data"):
                command = step.get("run", "")
                assert "uv " not in command, f"{job_name}/{name} executes candidate Python"
                assert "python" not in command, f"{job_name}/{name} executes candidate Python"


def test_toast_python_setup_is_cacheless_in_every_job() -> None:
    workflow = load_workflow(TOAST_WORKFLOW_PATH)
    for job_name in workflow["jobs"]:
        setup = steps_by_name(workflow, job_name)["Install uv and Python"]
        assert setup["with"]["enable-cache"] == "false"


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


def test_quality_gates_run_only_from_trusted_controller() -> None:
    quality = steps_by_name(load_workflow())["Run trusted controller quality gates"]
    assert quality["working-directory"] == "controller"
    commands = quality["run"]
    assert "pytest tests --strict-markers -q" in commands
    assert "pytest --collect-only --pyargs moo_conformance --strict-markers -q" in commands
    assert "moo-lint-duplicates" in commands
    assert "ruff check ." in commands
    assert "mypy src/moo_conformance" in commands


def test_paired_candidate_checkout_is_data_only_and_inventory_is_trusted() -> None:
    steps = steps_by_name(load_workflow())
    controller = steps["Check out trusted paired controller"]["with"]
    assert controller == {
        "repository": "MongooseMoo/moo-conformance-tests",
        "ref": "${{ github.workflow_sha }}",
        "path": "controller",
        "persist-credentials": "false",
    }
    candidate = steps["Check out candidate conformance data"]["with"]
    assert candidate["ref"] == "${{ needs.validate-inputs.outputs.conformance_sha }}"
    assert candidate["path"] == "candidate-data"
    workflow_text = WORKFLOW_PATH.read_text()
    assert "--project conformance" not in workflow_text
    assert "working-directory: conformance" not in workflow_text
    inventory = steps["Recompute trusted and candidate case inventories"]["run"]
    assert "python -m moo_conformance.paired_inventory" in inventory
    assert '--candidate-root="${GITHUB_WORKSPACE}/candidate-data"' in inventory
    assert "candidate-data/src/moo_conformance/_tests" in inventory
    assert "candidate-data/src/moo_conformance/_db/Test.db" in inventory
    assert "candidate-data/src/moo_conformance/_db/startup" in inventory
    assert "expected-case-ids" not in workflow_text


def test_candidate_run_is_staged_and_packaged_execution_is_success_gated() -> None:
    steps = steps_by_name(load_workflow())
    admission = steps["Run canonical capability admission against Barn"]
    assert admission["id"] == "admission"
    assert admission["env"]["ADMISSION_CONTEXT"] == (
        "${{ steps.trust-context.outputs.admission_context }}"
    )
    assert "-m admission" in admission["run"]
    assert "--admission-evidence-output=" in admission["run"]
    assert "--admission-evidence-context=" in admission["run"]
    assert "--junitxml=" in admission["run"]
    assert "--project controller" in admission["run"]
    assert '--candidate-root="${GITHUB_WORKSPACE}/candidate-data"' in admission["run"]
    assert "--moo-suite-root=" in admission["run"]
    assert "exit 0" in admission["run"]

    packaged = steps["Run every packaged conformance case against Barn"]
    assert packaged["id"] == "packaged"
    assert packaged["env"]["ADMISSION_CONTEXT"] == (
        "${{ steps.trust-context.outputs.admission_context }}"
    )
    assert packaged["if"] == "steps.admission.outputs.exit_code == '0'"
    assert "-m conformance" in packaged["run"]
    assert "--admission-evidence-input=" in packaged["run"]
    assert "--admission-evidence-context=" in packaged["run"]
    assert "--pyargs moo_conformance" in packaged["run"]
    assert "--project controller" in packaged["run"]
    assert '--candidate-root="${GITHUB_WORKSPACE}/candidate-data"' in packaged["run"]
    assert "--moo-suite-root=" in packaged["run"]
    assert "--fail-on-unexpected-skip" in packaged["run"]
    assert "--moo-suite-path" not in packaged["run"]
    assert "-k " not in packaged["run"]


def test_paired_outputs_include_both_phase_exit_codes_and_exact_declaration() -> None:
    outputs = load_workflow()["jobs"]["paired"]["outputs"]
    assert outputs["admission_context"] == (
        "${{ steps.trust-context.outputs.admission_context }}"
    )
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
    assert validate["env"]["ADMISSION_CONTEXT"] == (
        "${{ needs.paired.outputs.admission_context }}"
    )
    command = validate["run"]
    assert "python -m moo_conformance.paired_result" in command
    assert '--admission="raw-evidence/admission.json"' in command
    assert '--admission-report="raw-evidence/admission.xml"' in command
    assert '--admission-context="$ADMISSION_CONTEXT"' in command
    assert '--candidate-root="${GITHUB_WORKSPACE}/candidate-data"' in command
    assert "--candidate-tests=" in command
    assert "--candidate-db=" in command
    assert "--candidate-db-dir=" in command
    assert '--phase="$EXPECTED_PHASE"' in command
    assert '--admission-exit-code="$ADMISSION_EXIT"' in command
    assert '--required-bad-identities="$REQUIRED_BAD_IDENTITIES"' in command
    assert "--report=" in command
    assert "--packaged-exit-code=" in command


def test_schema_v5_provenance_records_trusted_inventory_and_phase_identity_sets() -> None:
    workflow = load_workflow()
    provenance = steps_by_name(workflow, "verdict")["Record final staged provenance"]["run"]
    assert '"schema_version": 5' in provenance
    assert '"phase": result["phase"]' in provenance
    assert '"declared_bad_identities": result["declared_bad_identities"]' in provenance
    assert '"observed_bad_identities": result["observed_bad_identities"]' in provenance
    assert '"admission_context": result["admission"]["context"]' in provenance
    assert '"inventory": result["inventory"]' in provenance
    assert '"candidate_anchor": result["inventory"]["candidate_anchor"]' in provenance
    assert (
        '"candidate_inventory_sha256": result["inventory"]["candidate_identity_sha256"]'
        in provenance
    )
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
    candidate = steps_by_name(workflow, "verdict")[
        "Check out immutable candidate conformance data"
    ]["with"]
    assert candidate["ref"] == "${{ needs.paired.outputs.conformance_sha }}"
    assert candidate["path"] == "candidate-data"


def test_trusted_workflow_context_contains_fresh_run_attempt_nonce_and_immutable_pair() -> None:
    steps = steps_by_name(load_workflow())
    context = steps["Create trusted run-attempt admission context"]
    assert context["id"] == "trust-context"
    script = context["run"]
    assert "secrets.token_hex" in script
    assert "GITHUB_RUN_ID" in script
    assert "GITHUB_RUN_ATTEMPT" in script
    assert 'steps.provenance.outputs.barn_sha' in str(context["env"])
    assert 'steps.provenance.outputs.conformance_sha' in str(context["env"])
