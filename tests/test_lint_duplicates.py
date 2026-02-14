from pathlib import Path

import pytest
import yaml

from moo_conformance.lint_duplicates import (
    TestOccurrence as Occurrence,
)
from moo_conformance.lint_duplicates import (
    apply_duplicate_content_cleanup,
    apply_duplicate_semantic_cleanup,
    choose_occurrence_to_keep,
    detect_duplicate_content,
    detect_duplicate_names,
    detect_duplicate_semantic,
    get_semantic_engine_error,
)


def _write_suite(
    path: Path,
    tests: list[dict],
    *,
    setup: dict | None = None,
    teardown: dict | None = None,
) -> None:
    data = {"name": path.stem, "tests": tests}
    if setup is not None:
        data["setup"] = setup
    if teardown is not None:
        data["teardown"] = teardown
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_detect_duplicate_names(tmp_path: Path) -> None:
    _write_suite(
        tmp_path / "one.yaml",
        [
            {"name": "same_name", "code": "1", "expect": {"value": 1}},
            {"name": "unique_name", "code": "2", "expect": {"value": 2}},
        ],
    )
    _write_suite(
        tmp_path / "two.yaml",
        [{"name": "same_name", "code": "3", "expect": {"value": 3}}],
    )

    duplicates = detect_duplicate_names(tmp_path)

    assert set(duplicates) == {"same_name"}
    assert len(duplicates["same_name"]) == 2


def test_detect_duplicate_content_ignores_name_and_description(tmp_path: Path) -> None:
    _write_suite(
        tmp_path / "one.yaml",
        [{"name": "a", "description": "first", "code": "1 + 1", "expect": {"value": 2}}],
    )
    _write_suite(
        tmp_path / "two.yaml",
        [{"name": "b", "description": "second", "code": "1 + 1", "expect": {"value": 2}}],
    )

    duplicates = detect_duplicate_content(tmp_path)

    assert len(duplicates) == 1
    assert len(duplicates[0]) == 2
    assert {item.name for item in duplicates[0]} == {"a", "b"}


def test_detect_duplicate_content_respects_include_description_behavior(tmp_path: Path) -> None:
    _write_suite(
        tmp_path / "one.yaml",
        [{"name": "a", "description": "x", "code": "1 + 1", "expect": {"value": 2}}],
    )
    _write_suite(
        tmp_path / "two.yaml",
        [{"name": "b", "description": "y", "code": "1 + 1", "expect": {"value": 2}}],
    )

    duplicates = detect_duplicate_content(tmp_path, ignored_keys=("name",))

    assert duplicates == []


def test_detect_duplicate_content_includes_suite_setup_context(tmp_path: Path) -> None:
    _write_suite(
        tmp_path / "one.yaml",
        [{"name": "a", "code": "1 + 1", "expect": {"value": 2}}],
        setup={"permission": "wizard", "code": "x = 1;"},
    )
    _write_suite(
        tmp_path / "two.yaml",
        [{"name": "b", "code": "1 + 1", "expect": {"value": 2}}],
        setup={"permission": "wizard", "code": "x = 2;"},
    )

    duplicates = detect_duplicate_content(tmp_path)

    assert duplicates == []


def test_choose_occurrence_to_keep_prefers_most_described() -> None:
    group = [
        Occurrence(file=Path("a.yaml"), index=1, name="short", description=""),
        Occurrence(
            file=Path("b.yaml"),
            index=1,
            name="longer_name",
            description="this has more detail",
        ),
    ]

    keep = choose_occurrence_to_keep(group, keep_strategy="most-described")

    assert keep.file == Path("b.yaml")
    assert keep.name == "longer_name"


def test_apply_duplicate_content_cleanup_removes_extra_definitions(tmp_path: Path) -> None:
    _write_suite(
        tmp_path / "suite_a.yaml",
        [
            {
                "name": "keep_me",
                "description": "canonical",
                "code": "2 + 2",
                "expect": {"value": 4},
            },
            {"name": "unique_a", "code": "5", "expect": {"value": 5}},
        ],
    )
    _write_suite(
        tmp_path / "suite_b.yaml",
        [
            {"name": "drop_me", "description": "", "code": "2 + 2", "expect": {"value": 4}},
            {"name": "unique_b", "code": "6", "expect": {"value": 6}},
        ],
    )

    changed_files, removed_tests, _plans = apply_duplicate_content_cleanup(
        tmp_path, keep_strategy="most-described"
    )

    assert changed_files == 1
    assert removed_tests == 1

    suite_b = yaml.safe_load((tmp_path / "suite_b.yaml").read_text(encoding="utf-8"))
    remaining_names = [item["name"] for item in suite_b["tests"]]
    assert remaining_names == ["unique_b"]


def test_detect_duplicate_semantic_equivalent_code(tmp_path: Path) -> None:
    if get_semantic_engine_error():
        pytest.skip("moo_interp semantic engine unavailable")

    _write_suite(
        tmp_path / "suite_a.yaml",
        [{"name": "a", "code": "1+1", "expect": {"value": 2}}],
    )
    _write_suite(
        tmp_path / "suite_b.yaml",
        [{"name": "b", "code": "1 + 1", "expect": {"value": 2}}],
    )

    duplicates = detect_duplicate_semantic(tmp_path)

    assert len(duplicates) == 1
    assert len(duplicates[0]) == 2
    assert {item.name for item in duplicates[0]} == {"a", "b"}


def test_apply_duplicate_semantic_cleanup_removes_extra_definitions(tmp_path: Path) -> None:
    if get_semantic_engine_error():
        pytest.skip("moo_interp semantic engine unavailable")

    _write_suite(
        tmp_path / "suite_a.yaml",
        [
            {"name": "keep_me", "description": "canonical", "code": "1+1", "expect": {"value": 2}},
            {"name": "unique_a", "code": "5", "expect": {"value": 5}},
        ],
    )
    _write_suite(
        tmp_path / "suite_b.yaml",
        [
            {"name": "drop_me", "description": "", "code": "1 + 1", "expect": {"value": 2}},
            {"name": "unique_b", "code": "6", "expect": {"value": 6}},
        ],
    )

    changed_files, removed_tests, _plans = apply_duplicate_semantic_cleanup(
        tmp_path, keep_strategy="most-described"
    )

    assert changed_files == 1
    assert removed_tests == 1

    suite_b = yaml.safe_load((tmp_path / "suite_b.yaml").read_text(encoding="utf-8"))
    remaining_names = [item["name"] for item in suite_b["tests"]]
    assert remaining_names == ["unique_b"]
