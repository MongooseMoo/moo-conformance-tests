import hashlib
import json
import os
from pathlib import Path

import pytest

from moo_conformance.startup_fixtures import (
    StartupFixtureError,
    main,
    validate_startup_fixtures,
)


def _digest(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def _fixture_tree(
    root: Path,
    files: dict[str, bytes] | None = None,
    manifest_lines: list[str] | None = None,
) -> tuple[Path, Path]:
    fixtures = root / "src" / "moo_conformance" / "_db" / "startup"
    fixtures.mkdir(parents=True)
    payloads = files or {"Alpha.db": b"alpha", "Beta.db": b"beta"}
    for name, contents in payloads.items():
        (fixtures / name).write_bytes(contents)
    lines = manifest_lines or [
        f"{_digest(contents)}  {name}" for name, contents in sorted(payloads.items())
    ]
    manifest = fixtures / "startup-fixtures.sha256"
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return fixtures, manifest


def test_repository_startup_fixture_manifest_is_exact() -> None:
    root = Path(__file__).resolve().parents[1]
    fixtures = root / "src" / "moo_conformance" / "_db" / "startup"

    evidence = validate_startup_fixtures(
        root,
        fixtures,
        fixtures / "startup-fixtures.sha256",
    )

    assert evidence["schema_version"] == 1
    assert evidence["fixture_count"] == 11
    assert [fixture["name"] for fixture in evidence["fixtures"]] == [
        "Anon1.db",
        "Anon2.db",
        "Anon3.db",
        "Anon4.db",
        "Anon5.db",
        "Anon6.db",
        "Broken1.db",
        "Broken2.db",
        "Broken3.db",
        "Broken4.db",
        "Broken5.db",
    ]


def test_candidate_manifest_produces_canonical_evidence(tmp_path: Path) -> None:
    fixtures, manifest = _fixture_tree(tmp_path)

    evidence = validate_startup_fixtures(tmp_path, fixtures, manifest)

    assert evidence == {
        "schema_version": 1,
        "candidate_anchor": str(tmp_path.resolve()),
        "fixture_root": str(fixtures.resolve()),
        "manifest": str(manifest.resolve()),
        "fixture_count": 2,
        "fixtures": [
            {"name": "Alpha.db", "sha256": _digest(b"alpha"), "size": 5},
            {"name": "Beta.db", "sha256": _digest(b"beta"), "size": 4},
        ],
    }


@pytest.mark.parametrize(
    ("manifest_lines", "message"),
    [
        (["not-a-digest  Alpha.db"], "malformed startup fixture manifest line"),
        ([f"{'0' * 64}  ../Alpha.db"], "malformed startup fixture manifest line"),
        ([f"{'0' * 64}  nested/Alpha.db"], "malformed startup fixture manifest line"),
        ([f"{'0' * 64}  Alpha.txt"], "malformed startup fixture manifest line"),
        ([""], "malformed startup fixture manifest line"),
    ],
)
def test_manifest_syntax_fails_closed(
    tmp_path: Path,
    manifest_lines: list[str],
    message: str,
) -> None:
    fixtures, manifest = _fixture_tree(
        tmp_path,
        files={"Alpha.db": b"alpha"},
        manifest_lines=manifest_lines,
    )

    with pytest.raises(StartupFixtureError, match=message):
        validate_startup_fixtures(tmp_path, fixtures, manifest)


def test_duplicate_manifest_name_fails_closed(tmp_path: Path) -> None:
    line = f"{_digest(b'alpha')}  Alpha.db"
    fixtures, manifest = _fixture_tree(
        tmp_path,
        files={"Alpha.db": b"alpha"},
        manifest_lines=[line, line],
    )

    with pytest.raises(StartupFixtureError, match="duplicate startup fixture name"):
        validate_startup_fixtures(tmp_path, fixtures, manifest)


def test_noncanonical_manifest_order_fails_closed(tmp_path: Path) -> None:
    fixtures, manifest = _fixture_tree(
        tmp_path,
        manifest_lines=[
            f"{_digest(b'beta')}  Beta.db",
            f"{_digest(b'alpha')}  Alpha.db",
        ],
    )

    with pytest.raises(StartupFixtureError, match="canonical name order"):
        validate_startup_fixtures(tmp_path, fixtures, manifest)


def test_checksum_mismatch_fails_closed(tmp_path: Path) -> None:
    fixtures, manifest = _fixture_tree(
        tmp_path,
        files={"Alpha.db": b"alpha"},
        manifest_lines=[f"{'0' * 64}  Alpha.db"],
    )

    with pytest.raises(StartupFixtureError, match="checksum mismatch.*Alpha.db"):
        validate_startup_fixtures(tmp_path, fixtures, manifest)


@pytest.mark.parametrize(
    ("files", "manifest_names", "message"),
    [
        (
            {"Alpha.db": b"alpha", "Extra.db": b"extra"},
            ["Alpha.db"],
            "unlisted startup fixture files: Extra.db",
        ),
        (
            {"Alpha.db": b"alpha"},
            ["Alpha.db", "Missing.db"],
            "missing startup fixture files: Missing.db",
        ),
    ],
)
def test_manifest_and_fixture_set_must_match_exactly(
    tmp_path: Path,
    files: dict[str, bytes],
    manifest_names: list[str],
    message: str,
) -> None:
    lines = [f"{_digest(files.get(name, b'missing'))}  {name}" for name in manifest_names]
    fixtures, manifest = _fixture_tree(tmp_path, files=files, manifest_lines=lines)

    with pytest.raises(StartupFixtureError, match=message):
        validate_startup_fixtures(tmp_path, fixtures, manifest)


def test_unexpected_entry_in_fixture_directory_fails_closed(tmp_path: Path) -> None:
    fixtures, manifest = _fixture_tree(tmp_path, files={"Alpha.db": b"alpha"})
    (fixtures / "unexpected.txt").write_text("unexpected", encoding="utf-8")

    with pytest.raises(StartupFixtureError, match="unexpected startup fixture entry"):
        validate_startup_fixtures(tmp_path, fixtures, manifest)


def test_nested_directory_in_fixture_directory_fails_closed(tmp_path: Path) -> None:
    fixtures, manifest = _fixture_tree(tmp_path, files={"Alpha.db": b"alpha"})
    (fixtures / "nested").mkdir()

    with pytest.raises(StartupFixtureError, match="unexpected startup fixture entry"):
        validate_startup_fixtures(tmp_path, fixtures, manifest)


def test_linked_fixture_fails_closed(tmp_path: Path) -> None:
    fixtures, manifest = _fixture_tree(tmp_path, files={"Alpha.db": b"alpha"})
    target = fixtures / "Alpha.db"
    link = fixtures / "Linked.db"
    try:
        os.symlink(target, link)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    manifest.write_text(
        manifest.read_text(encoding="utf-8")
        + f"{_digest(b'alpha')}  Linked.db\n",
        encoding="utf-8",
    )

    with pytest.raises(StartupFixtureError, match="linked startup fixture entry"):
        validate_startup_fixtures(tmp_path, fixtures, manifest)


def test_manifest_must_be_canonical_file_in_fixture_directory(tmp_path: Path) -> None:
    fixtures, _manifest = _fixture_tree(tmp_path, files={"Alpha.db": b"alpha"})
    other = tmp_path / "other.sha256"
    other.write_text(f"{_digest(b'alpha')}  Alpha.db\n", encoding="utf-8")

    with pytest.raises(StartupFixtureError, match="canonical startup fixture manifest"):
        validate_startup_fixtures(tmp_path, fixtures, other)


def test_cli_writes_fixture_evidence(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fixtures, manifest = _fixture_tree(tmp_path, files={"Alpha.db": b"alpha"})
    output = tmp_path / "evidence.json"

    assert (
        main(
            [
                "--candidate-root",
                str(tmp_path),
                "--fixtures-dir",
                str(fixtures),
                "--manifest",
                str(manifest),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert evidence["fixture_count"] == 1
    assert evidence["fixtures"][0]["name"] == "Alpha.db"
    assert "validated 1 startup fixtures" in capsys.readouterr().out
