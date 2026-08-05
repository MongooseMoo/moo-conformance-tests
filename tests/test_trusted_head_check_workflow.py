from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REPORTER_PATH = ROOT / ".github" / "workflows" / "trusted-head-check.yml"
PROBE_PATH = ROOT / ".github" / "workflows" / "trusted-head-check-probe.yml"


def _load(path: Path) -> dict[str, object]:
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_reporter_is_reusable_only_and_accepts_exact_evidence() -> None:
    workflow = _load(REPORTER_PATH)

    assert workflow["on"] == {
        "workflow_call": {
            "inputs": {
                "check_name": {"required": "true", "type": "string"},
                "head_sha": {"required": "true", "type": "string"},
                "conclusion": {"required": "true", "type": "string"},
                "summary": {"required": "true", "type": "string"},
            }
        }
    }
    assert workflow["permissions"] == {}


def test_reporter_has_only_check_write_and_executes_no_candidate_content() -> None:
    workflow = _load(REPORTER_PATH)
    job = workflow["jobs"]["report"]

    assert job["permissions"] == {"checks": "write"}
    assert "uses" not in job
    steps = job["steps"]
    assert len(steps) == 1
    step = steps[0]
    assert step["env"] == {
        "GH_TOKEN": "${{ github.token }}",
        "CHECK_NAME": "${{ inputs.check_name }}",
        "TARGET_SHA": "${{ inputs.head_sha }}",
        "CONCLUSION": "${{ inputs.conclusion }}",
        "SUMMARY": "${{ inputs.summary }}",
    }
    command = step["run"]
    assert "candidate" not in command.lower()
    assert "checkout" not in command.lower()
    assert "secrets." not in str(job)
    assert "^[0-9a-f]{40}$" in command
    assert "success|failure|neutral|cancelled|timed_out|action_required|skipped" in command
    assert "|stale|" not in command
    assert "jq -n" in command
    assert "gh api --method POST" in command
    assert "gh api --method PATCH" in command
    assert 'repos/${GITHUB_REPOSITORY}/check-runs' in command
    assert '"head_sha":$head_sha' in command
    assert '"status":"completed"' in command
    assert '"conclusion":"failure"' in command
    assert '"conclusion":$conclusion' in command
    assert '.app.slug == "github-actions"' in command
    assert '.head_sha == $sha' in command
    assert '.name == $name' in command
    assert '.conclusion == "failure"' in command
    assert '.conclusion == $conclusion' in command


def test_probe_is_base_owned_and_reports_success_on_exact_pr_head() -> None:
    workflow = _load(PROBE_PATH)

    assert workflow["on"] == {"pull_request_target": ""}
    assert workflow["permissions"] == {}
    assert workflow["concurrency"] == {
        "group": "trusted-head-check-probe-${{ github.event.pull_request.number }}",
        "cancel-in-progress": "true",
    }
    job = workflow["jobs"]["report"]
    assert job == {
        "name": "Report trusted PR head status probe",
        "uses": "./.github/workflows/trusted-head-check.yml",
        "permissions": {"checks": "write"},
        "with": {
            "check_name": "Trusted PR head status probe",
            "head_sha": "${{ github.event.pull_request.head.sha }}",
            "conclusion": "success",
            "summary": "Base-owned workflow reported on the exact pull request head.",
        },
    }
    assert "candidate" not in PROBE_PATH.read_text(encoding="utf-8").lower()
