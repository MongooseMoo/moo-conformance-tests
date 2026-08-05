import json
import os
import subprocess
from pathlib import Path

import pytest

from moo_conformance import execution_ledger
from moo_conformance.execution_ledger import (
    CaseOutcome,
    ExecutionLedgerError,
    candidate_identity_digest,
    enforce_execution_surface,
    load_baseline,
    load_candidate_inventory,
    main,
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
        f"  - name: {name}\n    code: '1'\n    expect:\n      value: 1" for name in names
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


def inventory_data(
    *,
    trusted: list[object] | None = None,
    candidate: list[object] | None = None,
    additive: list[object] | None = None,
) -> dict[str, object]:
    trusted_ids = ["suite.yaml::base"] if trusted is None else trusted
    candidate_ids = ["suite.yaml::addition", "suite.yaml::base"] if candidate is None else candidate
    additive_ids = ["suite.yaml::addition"] if additive is None else additive
    strings = sorted(case_id for case_id in candidate_ids if isinstance(case_id, str))
    digest = candidate_identity_digest(strings)
    return {
        "schema_version": 2,
        "candidate_anchor": "C:/immutable/candidate",
        "trusted_case_ids": trusted_ids,
        "candidate_case_ids": candidate_ids,
        "additive_case_ids": additive_ids,
        "candidate_identity_sha256": digest,
    }


def write_inventory(path: Path, data: object) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


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


def test_load_candidate_inventory_accepts_exact_schema_v2(tmp_path: Path) -> None:
    inventory_path = tmp_path / "paired-inventory.json"
    expected = inventory_data()
    write_inventory(inventory_path, expected)

    assert load_candidate_inventory(inventory_path) == expected


def test_candidate_identity_digest_distinguishes_embedded_newlines() -> None:
    assert candidate_identity_digest(["a.yaml::a\nb.yaml::b"]) != (
        candidate_identity_digest(["a.yaml::a", "b.yaml::b"])
    )


def test_load_candidate_inventory_rejects_former_newline_digest_collision(
    tmp_path: Path,
) -> None:
    inventory_path = tmp_path / "paired-inventory.json"
    combined = "a.yaml::a\nb.yaml::b"
    data = inventory_data(trusted=[combined], candidate=[combined], additive=[])
    data["trusted_case_ids"] = ["a.yaml::a", "b.yaml::b"]
    data["candidate_case_ids"] = ["a.yaml::a", "b.yaml::b"]
    write_inventory(inventory_path, data)

    with pytest.raises(ExecutionLedgerError, match="candidate_identity_sha256 mismatch"):
        load_candidate_inventory(inventory_path)


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        ("not JSON", "cannot read paired inventory"),
        (json.dumps([]), "must be a JSON object"),
    ],
)
def test_load_candidate_inventory_rejects_malformed_json_or_root_type(
    tmp_path: Path,
    contents: str,
    message: str,
) -> None:
    inventory_path = tmp_path / "paired-inventory.json"
    inventory_path.write_text(contents, encoding="utf-8")

    with pytest.raises(ExecutionLedgerError, match=message):
        load_candidate_inventory(inventory_path)


def test_load_candidate_inventory_normalizes_invalid_utf8(tmp_path: Path) -> None:
    inventory_path = tmp_path / "paired-inventory.json"
    inventory_path.write_bytes(b"\xff")

    with pytest.raises(ExecutionLedgerError, match="cannot read paired inventory"):
        load_candidate_inventory(inventory_path)


def test_load_candidate_inventory_rejects_duplicate_json_key(tmp_path: Path) -> None:
    inventory_path = tmp_path / "paired-inventory.json"
    serialized = json.dumps(inventory_data())
    inventory_path.write_text(
        serialized.replace('"schema_version": 2', '"schema_version": 2, "schema_version": 2'),
        encoding="utf-8",
    )

    with pytest.raises(ExecutionLedgerError, match="duplicate JSON key: schema_version"):
        load_candidate_inventory(inventory_path)


@pytest.mark.parametrize("mutation", ["missing", "unknown"])
def test_load_candidate_inventory_requires_exact_keys(
    tmp_path: Path,
    mutation: str,
) -> None:
    inventory_path = tmp_path / "paired-inventory.json"
    data = inventory_data()
    if mutation == "missing":
        del data["candidate_anchor"]
    else:
        data["untrusted_extension"] = True
    write_inventory(inventory_path, data)

    with pytest.raises(ExecutionLedgerError, match="exactly the schema-v2 keys"):
        load_candidate_inventory(inventory_path)


@pytest.mark.parametrize("schema_version", [1, "2", True])
def test_load_candidate_inventory_requires_integer_schema_v2(
    tmp_path: Path,
    schema_version: object,
) -> None:
    inventory_path = tmp_path / "paired-inventory.json"
    data = inventory_data()
    data["schema_version"] = schema_version
    write_inventory(inventory_path, data)

    with pytest.raises(ExecutionLedgerError, match="schema_version must be 2"):
        load_candidate_inventory(inventory_path)


@pytest.mark.parametrize("candidate_anchor", [None, ""])
def test_load_candidate_inventory_requires_nonempty_string_anchor(
    tmp_path: Path,
    candidate_anchor: object,
) -> None:
    inventory_path = tmp_path / "paired-inventory.json"
    data = inventory_data()
    data["candidate_anchor"] = candidate_anchor
    write_inventory(inventory_path, data)

    with pytest.raises(ExecutionLedgerError, match="candidate_anchor"):
        load_candidate_inventory(inventory_path)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("trusted_case_ids", {}, "must be an array"),
        ("candidate_case_ids", [], "must not be empty"),
        ("trusted_case_ids", [], "must not be empty"),
        ("candidate_case_ids", [""], "non-empty string"),
        ("trusted_case_ids", [3], "non-empty string"),
        ("additive_case_ids", [""], "non-empty string"),
        (
            "candidate_case_ids",
            ["suite.yaml::base", "suite.yaml::base"],
            "duplicate case IDs",
        ),
        (
            "trusted_case_ids",
            ["suite.yaml::base", "suite.yaml::base"],
            "duplicate case IDs",
        ),
        (
            "additive_case_ids",
            ["suite.yaml::addition", "suite.yaml::addition"],
            "duplicate case IDs",
        ),
    ],
)
def test_load_candidate_inventory_rejects_bad_identity_lists(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    inventory_path = tmp_path / "paired-inventory.json"
    data = inventory_data()
    data[field] = value
    write_inventory(inventory_path, data)

    with pytest.raises(ExecutionLedgerError, match=message):
        load_candidate_inventory(inventory_path)


def test_load_candidate_inventory_rejects_trusted_identity_missing_from_candidate(
    tmp_path: Path,
) -> None:
    inventory_path = tmp_path / "paired-inventory.json"
    data = inventory_data(trusted=["suite.yaml::missing"])
    write_inventory(inventory_path, data)

    with pytest.raises(ExecutionLedgerError, match="not a subset"):
        load_candidate_inventory(inventory_path)


@pytest.mark.parametrize(
    "additive",
    [[], ["suite.yaml::addition", "suite.yaml::base"]],
)
def test_load_candidate_inventory_rejects_additive_identity_mismatch(
    tmp_path: Path,
    additive: list[object],
) -> None:
    inventory_path = tmp_path / "paired-inventory.json"
    write_inventory(inventory_path, inventory_data(additive=additive))

    with pytest.raises(ExecutionLedgerError, match="additive_case_ids mismatch"):
        load_candidate_inventory(inventory_path)


def test_load_candidate_inventory_allows_no_additions(tmp_path: Path) -> None:
    inventory_path = tmp_path / "paired-inventory.json"
    data = inventory_data(
        candidate=["suite.yaml::base"],
        additive=[],
    )
    write_inventory(inventory_path, data)

    assert load_candidate_inventory(inventory_path) == data


def test_load_candidate_inventory_rejects_candidate_digest_tampering(
    tmp_path: Path,
) -> None:
    inventory_path = tmp_path / "paired-inventory.json"
    data = inventory_data()
    data["candidate_identity_sha256"] = "0" * 64
    write_inventory(inventory_path, data)

    with pytest.raises(ExecutionLedgerError, match="candidate_identity_sha256 mismatch"):
        load_candidate_inventory(inventory_path)


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
    reports = {"profile": {"suite.yaml::case": CaseOutcome("skipped", "unsupported")}}

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
    reports = {"profile": {"suite.yaml::case": CaseOutcome("skipped", "new reason")}}

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


def test_cli_uses_inventory_candidate_surface_instead_of_local_packages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inventory_path = tmp_path / "paired-inventory.json"
    report = tmp_path / "report.xml"
    baseline = tmp_path / "baseline.json"
    output = tmp_path / "ledger.json"
    candidate_id = "suite.yaml::candidate"
    write_inventory(
        inventory_path,
        inventory_data(
            trusted=[candidate_id],
            candidate=[candidate_id],
            additive=[],
        ),
    )
    write_report(report, [case(candidate_id)])
    write_inventory(baseline, {"schema_version": 1, "never_executed": {}})

    def reject_local_discovery(*args: object, **kwargs: object) -> set[str]:
        raise AssertionError("local packaged identities must not be consulted")

    monkeypatch.setattr(execution_ledger, "packaged_case_ids", reject_local_discovery)

    result = main(
        [
            "--report",
            f"toast={report}",
            "--baseline",
            str(baseline),
            "--inventory",
            str(inventory_path),
            "--output",
            str(output),
        ]
    )

    assert result == 0
    assert json.loads(output.read_text(encoding="utf-8"))["executed_case_ids"] == [candidate_id]


def test_cli_without_inventory_preserves_local_packaged_surface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = tmp_path / "report.xml"
    baseline = tmp_path / "baseline.json"
    output = tmp_path / "ledger.json"
    local_id = "suite.yaml::local"
    write_report(report, [case(local_id)])
    write_inventory(baseline, {"schema_version": 1, "never_executed": {}})
    monkeypatch.setattr(execution_ledger, "packaged_case_ids", lambda: {local_id})

    def reject_inventory_load(path: str | Path) -> object:
        raise AssertionError(f"unexpected inventory load: {path}")

    monkeypatch.setattr(execution_ledger, "load_candidate_inventory", reject_inventory_load)

    assert (
        main(
            [
                "--report",
                f"toast={report}",
                "--baseline",
                str(baseline),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert json.loads(output.read_text(encoding="utf-8"))["executed_case_ids"] == [local_id]


def test_cli_fails_closed_on_tampered_inventory(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inventory_path = tmp_path / "paired-inventory.json"
    report = tmp_path / "report.xml"
    baseline = tmp_path / "baseline.json"
    output = tmp_path / "ledger.json"
    data = inventory_data()
    data["candidate_identity_sha256"] = "tampered"
    write_inventory(inventory_path, data)
    write_report(report, [case("suite.yaml::base"), case("suite.yaml::addition")])
    write_inventory(baseline, {"schema_version": 1, "never_executed": {}})

    with pytest.raises(SystemExit, match="2"):
        main(
            [
                "--report",
                f"toast={report}",
                "--baseline",
                str(baseline),
                "--inventory",
                str(inventory_path),
                "--output",
                str(output),
            ]
        )

    assert "candidate_identity_sha256 mismatch" in capsys.readouterr().err
    assert not output.exists()


def test_reviewed_toast_baseline_is_empty() -> None:
    baseline = load_baseline(Path("ci/toast-never-executed.json"))

    assert baseline == {}
