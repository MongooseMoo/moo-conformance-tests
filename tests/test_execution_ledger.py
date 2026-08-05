import json
import os
import subprocess
from pathlib import Path

import pytest

from moo_conformance.execution_ledger import (
    CaseOutcome,
    ExecutionLedgerError,
    enforce_execution_surface,
    load_baseline,
    packaged_case_ids,
    parse_junit_report,
    validate_candidate_inventory,
)


def write_report(path: Path, cases: list[str]) -> None:
    path.write_text(
        "<testsuites><testsuite>" + "".join(cases) + "</testsuite></testsuites>",
        encoding="utf-8",
    )


def case(case_id: str, child: str = "") -> str:
    return (
        '<testcase classname="src.moo_conformance.test_conformance" '
        f'name="test_yaml_conformance[{case_id}]">{child}</testcase>'
    )


def write_suite(root: Path, filename: str, names: list[str]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    tests = "\n".join(
        f"  - name: {name}\n    code: '1'\n    expect:\n      value: 1"
        for name in names
    )
    (root / filename).write_text(f"name: suite\ntests:\n{tests}\n", encoding="utf-8")


def candidate_surface(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    root = tmp_path / "candidate-data"
    tests = root / "src" / "moo_conformance" / "_tests"
    database = root / "src" / "moo_conformance" / "_db" / "Test.db"
    fixtures = database.parent / "startup"
    tests.mkdir(parents=True)
    fixtures.mkdir(parents=True)
    database.write_text("database", encoding="utf-8")
    (fixtures / "fixture.db").write_text("fixture", encoding="utf-8")
    return root, tests, database, fixtures


def symlink_or_skip(link: Path, target: Path | str, *, directory: bool = False) -> None:
    try:
        link.symlink_to(target, target_is_directory=directory)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")


def test_candidate_inventory_allows_additions_but_recomputes_both_surfaces(
    tmp_path: Path,
) -> None:
    trusted = tmp_path / "trusted"
    root, candidate, database, fixtures = candidate_surface(tmp_path)
    write_suite(trusted, "suite.yaml", ["base"])
    write_suite(candidate, "suite.yaml", ["base", "addition"])

    inventory = validate_candidate_inventory(
        root,
        candidate,
        candidate_db_path=database,
        candidate_db_dir=fixtures,
        trusted_tests_dir=trusted,
    )

    assert inventory["schema_version"] == 2
    assert inventory["candidate_anchor"] == str(root.resolve())
    assert inventory["trusted_case_ids"] == ["suite.yaml::base"]
    assert inventory["candidate_case_ids"] == [
        "suite.yaml::addition",
        "suite.yaml::base",
    ]
    assert inventory["additive_case_ids"] == ["suite.yaml::addition"]


def test_candidate_inventory_rejects_yaml_deletion_despite_forged_id_claim(
    tmp_path: Path,
) -> None:
    trusted = tmp_path / "trusted"
    root, candidate, database, fixtures = candidate_surface(tmp_path)
    write_suite(trusted, "suite.yaml", ["required"])
    write_suite(candidate, "suite.yaml", ["other"])
    (candidate / "expected-case-ids.json").write_text(
        json.dumps(["suite.yaml::required"]),
        encoding="utf-8",
    )

    with pytest.raises(ExecutionLedgerError, match="deletes trusted-main identities"):
        validate_candidate_inventory(
            root,
            candidate,
            candidate_db_path=database,
            candidate_db_dir=fixtures,
            trusted_tests_dir=trusted,
        )


def test_candidate_inventory_rejects_relative_tests_directory_symlink_escape(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    trusted = workspace / "controller" / "src" / "moo_conformance" / "_tests"
    write_suite(trusted, "suite.yaml", ["base"])
    root, candidate, database, fixtures = candidate_surface(workspace)
    candidate.rmdir()
    symlink_or_skip(
        candidate,
        "../../../controller/src/moo_conformance/_tests",
        directory=True,
    )

    with pytest.raises(
        ExecutionLedgerError,
        match="candidate suite root (?:escapes|cannot be resolved)",
    ):
        validate_candidate_inventory(
            root,
            candidate,
            candidate_db_path=database,
            candidate_db_dir=fixtures,
            trusted_tests_dir=trusted,
        )


def test_candidate_inventory_rejects_nested_yaml_symlink_escape(tmp_path: Path) -> None:
    trusted = tmp_path / "trusted"
    root, candidate, database, fixtures = candidate_surface(tmp_path)
    outside = tmp_path / "outside.yaml"
    write_suite(trusted, "suite.yaml", ["base"])
    write_suite(outside.parent, outside.name, ["base"])
    symlink_or_skip(candidate / "suite.yaml", outside)

    with pytest.raises(ExecutionLedgerError, match="candidate suite entry escapes"):
        validate_candidate_inventory(
            root,
            candidate,
            candidate_db_path=database,
            candidate_db_dir=fixtures,
            trusted_tests_dir=trusted,
        )


def test_candidate_inventory_rejects_primary_database_symlink_escape(tmp_path: Path) -> None:
    trusted = tmp_path / "trusted"
    root, candidate, database, fixtures = candidate_surface(tmp_path)
    write_suite(trusted, "suite.yaml", ["base"])
    write_suite(candidate, "suite.yaml", ["base"])
    outside = tmp_path / "outside.db"
    outside.write_text("outside", encoding="utf-8")
    database.unlink()
    symlink_or_skip(database, outside)

    with pytest.raises(ExecutionLedgerError, match="candidate primary database escapes"):
        validate_candidate_inventory(
            root,
            candidate,
            candidate_db_path=database,
            candidate_db_dir=fixtures,
            trusted_tests_dir=trusted,
        )


def test_candidate_inventory_rejects_primary_database_link_to_sibling_oracle(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    trusted = workspace / "controller-tests"
    root, candidate, database, fixtures = candidate_surface(workspace)
    write_suite(trusted, "suite.yaml", ["base"])
    write_suite(candidate, "suite.yaml", ["base"])
    oracle_database = workspace / "toaststunt" / "test" / "Test.db"
    oracle_database.parent.mkdir(parents=True)
    oracle_database.write_bytes(database.read_bytes())
    database.unlink()
    relative_oracle = Path(os.path.relpath(oracle_database, database.parent))
    # The former workspace-root topology made the analogous target
    # ../../../toaststunt/test/Test.db appear confined. The fixed sibling
    # topology adds one boundary component and must reject it despite the
    # oracle and candidate blobs being byte-identical.
    assert relative_oracle.as_posix() == "../../../../toaststunt/test/Test.db"
    symlink_or_skip(database, relative_oracle)

    with pytest.raises(ExecutionLedgerError, match="candidate primary database escapes"):
        validate_candidate_inventory(
            root,
            candidate,
            candidate_db_path=database,
            candidate_db_dir=fixtures,
            trusted_tests_dir=trusted,
        )


@pytest.mark.parametrize("surface", ["suite", "database"])
def test_candidate_inventory_rejects_links_to_sibling_generated_paths(
    tmp_path: Path,
    surface: str,
) -> None:
    workspace = tmp_path / "workspace"
    trusted = workspace / "trusted"
    root, candidate, database, fixtures = candidate_surface(workspace)
    write_suite(trusted, "suite.yaml", ["base"])
    write_suite(candidate, "suite.yaml", ["base"])
    generated = workspace / "generated"
    generated.mkdir()
    if surface == "suite":
        outside = generated / "linked.yaml"
        write_suite(generated, outside.name, ["extra"])
        symlink_or_skip(candidate / "linked.yaml", outside)
        message = "candidate suite entry escapes"
    else:
        outside = generated / "linked.db"
        outside.write_text("generated", encoding="utf-8")
        symlink_or_skip(fixtures / "linked.db", outside)
        message = "candidate database fixture entry escapes"

    with pytest.raises(ExecutionLedgerError, match=message):
        validate_candidate_inventory(
            root,
            candidate,
            candidate_db_path=database,
            candidate_db_dir=fixtures,
            trusted_tests_dir=trusted,
        )


def test_candidate_inventory_rejects_fixture_directory_symlink_escape(tmp_path: Path) -> None:
    trusted = tmp_path / "trusted"
    root, candidate, database, fixtures = candidate_surface(tmp_path)
    write_suite(trusted, "suite.yaml", ["base"])
    write_suite(candidate, "suite.yaml", ["base"])
    outside = tmp_path / "outside-fixtures"
    outside.mkdir()
    (fixtures / "fixture.db").unlink()
    fixtures.rmdir()
    symlink_or_skip(fixtures, outside, directory=True)

    with pytest.raises(ExecutionLedgerError, match="candidate database fixture root escapes"):
        validate_candidate_inventory(
            root,
            candidate,
            candidate_db_path=database,
            candidate_db_dir=fixtures,
            trusted_tests_dir=trusted,
        )


def test_candidate_inventory_rejects_individual_database_symlink_escape(tmp_path: Path) -> None:
    trusted = tmp_path / "trusted"
    root, candidate, database, fixtures = candidate_surface(tmp_path)
    write_suite(trusted, "suite.yaml", ["base"])
    write_suite(candidate, "suite.yaml", ["base"])
    outside = tmp_path / "outside.db"
    outside.write_text("outside", encoding="utf-8")
    fixture = fixtures / "fixture.db"
    fixture.unlink()
    symlink_or_skip(fixture, outside)

    with pytest.raises(ExecutionLedgerError, match="candidate database fixture entry escapes"):
        validate_candidate_inventory(
            root,
            candidate,
            candidate_db_path=database,
            candidate_db_dir=fixtures,
            trusted_tests_dir=trusted,
        )


@pytest.mark.skipif(os.name != "nt", reason="Windows junction semantics")
def test_candidate_inventory_rejects_nested_windows_junction_escape(tmp_path: Path) -> None:
    trusted = tmp_path / "trusted"
    root, candidate, database, fixtures = candidate_surface(tmp_path)
    write_suite(trusted, "suite.yaml", ["base"])
    write_suite(candidate, "suite.yaml", ["base"])
    outside = tmp_path / "outside"
    outside.mkdir()
    junction = candidate / "nested"
    created = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
        capture_output=True,
        text=True,
        check=False,
    )
    if created.returncode != 0:
        pytest.skip(f"junctions unavailable: {created.stderr}")

    with pytest.raises(ExecutionLedgerError, match="candidate suite entry escapes"):
        validate_candidate_inventory(
            root,
            candidate,
            candidate_db_path=database,
            candidate_db_dir=fixtures,
            trusted_tests_dir=trusted,
        )


def test_parse_junit_report_records_exact_outcomes(tmp_path: Path) -> None:
    report = tmp_path / "report.xml"
    write_report(
        report,
        [
            case("a.yaml::pass"),
            case("a.yaml::skip", '<skipped message="not supported"/>'),
            case("a.yaml::fail", '<failure message="wrong"/>'),
            case("a.yaml::error", '<error message="boom"/>'),
            '<testcase name="ordinary_unit_test"/>',
        ],
    )

    assert parse_junit_report(report) == {
        "a.yaml::pass": CaseOutcome("passed"),
        "a.yaml::skip": CaseOutcome("skipped", "not supported"),
        "a.yaml::fail": CaseOutcome("failed", "wrong"),
        "a.yaml::error": CaseOutcome("error", "boom"),
    }


def test_parse_junit_report_rejects_duplicate_identity(tmp_path: Path) -> None:
    report = tmp_path / "report.xml"
    write_report(report, [case("same.yaml::case"), case("same.yaml::case")])

    with pytest.raises(ExecutionLedgerError, match="duplicate conformance identity"):
        parse_junit_report(report)


def test_profile_union_requires_every_case_to_pass_once() -> None:
    expected = {"suite.yaml::always", "suite.yaml::variant"}
    reports = {
        "on": {
            "suite.yaml::always": CaseOutcome("passed"),
            "suite.yaml::variant": CaseOutcome("skipped", "off only"),
        },
        "off": {
            "suite.yaml::always": CaseOutcome("passed"),
            "suite.yaml::variant": CaseOutcome("passed"),
        },
    }

    ledger = enforce_execution_surface(reports, expected, {})

    assert ledger["packaged_cases"] == 2
    assert ledger["executed_cases"] == 2
    assert ledger["reviewed_never_executed_cases"] == 0


def test_profile_surface_must_be_exact() -> None:
    reports = {"profile": {"suite.yaml::present": CaseOutcome("passed")}}

    with pytest.raises(ExecutionLedgerError, match="inexact surface"):
        enforce_execution_surface(
            reports,
            {"suite.yaml::present", "suite.yaml::missing"},
            {},
        )


@pytest.mark.parametrize("status", ["failed", "error"])
def test_unsuccessful_case_always_fails(status: str) -> None:
    reports = {"profile": {"suite.yaml::case": CaseOutcome(status, "broken")}}

    with pytest.raises(ExecutionLedgerError, match="unsuccessful cases"):
        enforce_execution_surface(reports, {"suite.yaml::case"}, {})


def test_unreviewed_never_executed_case_fails() -> None:
    reports = {
        "profile": {"suite.yaml::case": CaseOutcome("skipped", "unsupported")}
    }

    with pytest.raises(ExecutionLedgerError, match="absent from the reviewed baseline"):
        enforce_execution_surface(reports, {"suite.yaml::case"}, {})


def test_exact_reviewed_skip_is_allowed() -> None:
    reports = {
        "one": {"suite.yaml::case": CaseOutcome("skipped", "unsupported")},
        "two": {"suite.yaml::case": CaseOutcome("skipped", "unsupported")},
    }

    ledger = enforce_execution_surface(
        reports,
        {"suite.yaml::case"},
        {"suite.yaml::case": "unsupported"},
    )

    assert ledger["reviewed_never_executed_cases"] == 1


def test_skip_reason_drift_fails() -> None:
    reports = {
        "profile": {"suite.yaml::case": CaseOutcome("skipped", "new reason")}
    }

    with pytest.raises(ExecutionLedgerError, match="baseline drift"):
        enforce_execution_surface(
            reports,
            {"suite.yaml::case"},
            {"suite.yaml::case": "reviewed reason"},
        )


def test_stale_baseline_entry_fails_after_case_executes() -> None:
    reports = {"profile": {"suite.yaml::case": CaseOutcome("passed")}}

    with pytest.raises(ExecutionLedgerError, match="stale skip baseline"):
        enforce_execution_surface(
            reports,
            {"suite.yaml::case"},
            {"suite.yaml::case": "unsupported"},
        )


def test_load_baseline_rejects_malformed_shape(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"schema_version": 1, "never_executed": []}))

    with pytest.raises(ExecutionLedgerError, match="never_executed"):
        load_baseline(baseline)


def test_reviewed_toast_baseline_contains_only_packaged_cases() -> None:
    baseline = load_baseline(Path("ci/toast-never-executed.json"))

    assert len(baseline) == 41
    assert baseline["builtins/math.yaml::minint_modulus_edge_case"] == (
        "Pinned 32-bit Toast crashes on -2147483648 % -1"
    )
    assert set(baseline) <= packaged_case_ids()
