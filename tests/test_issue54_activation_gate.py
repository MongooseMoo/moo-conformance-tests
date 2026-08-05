from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "issue-54-activation-gate.yml"

HEAD_BRANCH = "agent/issue-54-staged-ci-workflow"
HEAD_SHA = "${{ github.event.pull_request.head.sha }}"
SCOPE = (
    "github.event.pull_request.head.repo.full_name == github.repository && "
    f"github.event.pull_request.head.ref == '{HEAD_BRANCH}'"
)
REPORT_IF = f"always() && {SCOPE}"


def load_workflow() -> dict[str, object]:
    return yaml.load(WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_gate_uses_only_pull_request_target_for_main() -> None:
    workflow = load_workflow()

    assert workflow["on"] == {"pull_request_target": {"branches": ["main"]}}


def test_gate_runs_exact_same_repository_activation_branch_only() -> None:
    workflow = load_workflow()
    jobs = workflow["jobs"]

    assert jobs["toast-conformance"]["if"] == SCOPE
    assert jobs["report-quality"]["if"] == REPORT_IF
    assert jobs["report-full-suite"]["if"] == REPORT_IF


def test_gate_calls_base_local_full_toast_workflow_for_exact_head_sha() -> None:
    job = load_workflow()["jobs"]["toast-conformance"]

    assert job == {
        "name": "Run base-owned Toast conformance",
        "if": SCOPE,
        "uses": "./.github/workflows/toast-conformance.yml",
        "permissions": {"contents": "read"},
        "with": {"conformance_sha": HEAD_SHA},
    }


def test_reporters_depend_on_conformance_and_fail_closed() -> None:
    jobs = load_workflow()["jobs"]
    for job_name in ("report-quality", "report-full-suite"):
        job = jobs[job_name]
        assert job["needs"] == "toast-conformance"
        assert job["if"] == REPORT_IF
        assert job["with"]["conclusion"] == (
            "${{ needs.toast-conformance.result == 'success' "
            "&& 'success' || 'failure' }}"
        )


def test_reporters_use_exact_required_names_and_pr_head_sha() -> None:
    jobs = load_workflow()["jobs"]
    expected = {
        "report-quality": "Harness, schema, duplicates, types, and lint",
        "report-full-suite": "Full suite",
    }

    for job_name, check_name in expected.items():
        job = jobs[job_name]
        assert job["uses"] == "./.github/workflows/trusted-head-check.yml"
        assert job["with"]["check_name"] == check_name
        assert job["with"]["head_sha"] == HEAD_SHA


def test_gate_is_read_only_except_for_reporter_check_writes() -> None:
    workflow = load_workflow()
    jobs = workflow["jobs"]

    assert workflow["permissions"] == {"contents": "read"}
    assert jobs["toast-conformance"]["permissions"] == {"contents": "read"}
    assert jobs["report-quality"]["permissions"] == {"checks": "write"}
    assert jobs["report-full-suite"]["permissions"] == {"checks": "write"}

    text = WORKFLOW_PATH.read_text(encoding="utf-8").lower()
    assert "actions/checkout" not in text
    assert "secrets:" not in text
    assert "steps:" not in text
    assert "run:" not in text
    assert "gh api" not in text
