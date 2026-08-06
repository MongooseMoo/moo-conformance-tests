import json
import subprocess
from pathlib import Path

import pytest

from moo_conformance.change_boundary import (
    ChangeBoundaryError,
    classify_candidate_change,
    classify_changed_paths,
    main,
)


def test_controller_only_change_is_admitted() -> None:
    result = classify_changed_paths(
        {
            ".github/workflows/toast-conformance.yml",
            "src/moo_conformance/_exec_fixtures/echo",
            "src/moo_conformance/runner.py",
            "tests/test_runner.py",
            "pyproject.toml",
            "uv.lock",
        }
    )

    assert result.mode == "controller"
    assert result.data_paths == ()
    assert result.neutral_paths == ()


def test_data_only_change_is_admitted() -> None:
    result = classify_changed_paths(
        {
            "ci/duplicate-baseline.json",
            "src/moo_conformance/_db/Test.db",
            "src/moo_conformance/_db/startup/startup-fixtures.sha256",
            "src/moo_conformance/_tests/basic/arithmetic.yaml",
        }
    )

    assert result.mode == "data"
    assert result.controller_paths == ()
    assert result.neutral_paths == ()


def test_neutral_only_change_is_admitted() -> None:
    result = classify_changed_paths({"LICENSE", "README.md", "docs/design.md"})

    assert result.mode == "neutral"
    assert result.neutral_paths == ("LICENSE", "README.md", "docs/design.md")


def test_python_under_packaged_test_tree_is_controller_code() -> None:
    result = classify_changed_paths({"src/moo_conformance/_tests/command/__init__.py"})

    assert result.mode == "controller"


def test_mixed_controller_and_data_change_fails_closed() -> None:
    with pytest.raises(ChangeBoundaryError, match="mixes controller and data changes"):
        classify_changed_paths(
            {
                "src/moo_conformance/schema.py",
                "src/moo_conformance/_tests/features/steps_basic.yaml",
            }
        )


def test_executable_fixture_mixed_with_test_data_fails_closed() -> None:
    with pytest.raises(ChangeBoundaryError, match="mixes controller and data changes"):
        classify_changed_paths(
            {
                "src/moo_conformance/_exec_fixtures/echo",
                "src/moo_conformance/_tests/features/steps_basic.yaml",
            }
        )


@pytest.mark.parametrize(
    "path",
    [
        "ci/unclassified.json",
        "scripts/generate.py",
        "src/another_package/runtime.py",
        "src/moo_conformance/schema.json",
        "src/moo_conformance/_tests/basic/unexpected.txt",
        "src/moo_conformance/_db/startup/fixture.bin",
        "unexpected.txt",
    ],
)
def test_unknown_semantic_path_fails_closed(path: str) -> None:
    with pytest.raises(ChangeBoundaryError, match="unclassified semantic paths"):
        classify_changed_paths({path})


def test_duplicate_and_noncanonical_paths_fail_closed() -> None:
    with pytest.raises(ChangeBoundaryError, match="canonical repository-relative POSIX path"):
        classify_changed_paths({"src/moo_conformance/../runner.py"})
    with pytest.raises(ChangeBoundaryError, match="canonical repository-relative POSIX path"):
        classify_changed_paths({"tests\\test_runner.py"})


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def _tracked_repo(root: Path, files: dict[str, str]) -> Path:
    root.mkdir()
    _git(root, "init", "--quiet")
    for relative, contents in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
    _git(root, "add", "--all")
    return root


def test_candidate_change_compares_exact_tracked_git_trees(tmp_path: Path) -> None:
    trusted = _tracked_repo(
        tmp_path / "trusted",
        {
            "README.md": "same\n",
            "src/moo_conformance/runner.py": "old\n",
            "src/moo_conformance/_tests/basic/value.yaml": "same\n",
        },
    )
    candidate = _tracked_repo(
        tmp_path / "candidate",
        {
            "README.md": "same\n",
            "src/moo_conformance/runner.py": "new\n",
            "src/moo_conformance/_tests/basic/value.yaml": "same\n",
        },
    )

    result = classify_candidate_change(trusted, candidate)

    assert result.mode == "controller"
    assert result.changed_paths == ("src/moo_conformance/runner.py",)


def test_candidate_change_requires_repository_top_level(tmp_path: Path) -> None:
    trusted = _tracked_repo(
        tmp_path / "trusted",
        {"src/moo_conformance/runner.py": "old\n"},
    )
    candidate = _tracked_repo(
        tmp_path / "candidate",
        {"src/moo_conformance/runner.py": "new\n"},
    )

    with pytest.raises(
        ChangeBoundaryError,
        match="tracked-tree root must be the repository top-level",
    ):
        classify_candidate_change(trusted / "src", candidate)


@pytest.mark.parametrize("mode", ["100755", "120000"])
def test_candidate_change_rejects_non_regular_index_modes(
    tmp_path: Path,
    mode: str,
) -> None:
    trusted = _tracked_repo(tmp_path / "trusted", {"README.md": "same\n"})
    candidate = _tracked_repo(tmp_path / "candidate", {"README.md": "same\n"})
    object_id = _git(candidate, "rev-parse", ":README.md").strip()
    _git(
        candidate,
        "update-index",
        "--add",
        "--cacheinfo",
        f"{mode},{object_id},unsafe-entry",
    )

    with pytest.raises(
        ChangeBoundaryError,
        match=rf"unsupported git index mode.*unsafe-entry: {mode}",
    ):
        classify_candidate_change(trusted, candidate)


def test_cli_writes_canonical_evidence(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    trusted = _tracked_repo(tmp_path / "trusted", {"README.md": "old\n"})
    candidate = _tracked_repo(tmp_path / "candidate", {"README.md": "new\n"})
    output = tmp_path / "boundary.json"

    assert (
        main(
            [
                "--trusted-root",
                str(trusted),
                "--candidate-root",
                str(candidate),
                "--output",
                str(output),
            ]
        )
        == 0
    )

    assert json.loads(output.read_text(encoding="utf-8")) == {
        "changed_paths": ["README.md"],
        "controller_paths": [],
        "data_paths": [],
        "mode": "neutral",
        "neutral_paths": ["README.md"],
        "schema_version": 1,
    }
    assert "change boundary: neutral" in capsys.readouterr().out
