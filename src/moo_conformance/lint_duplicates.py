"""Lint utility for detecting duplicate conformance tests."""

from __future__ import annotations

import argparse
import json
import warnings
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .plugin import get_tests_dir

DEFAULT_IGNORED_KEYS = ("name", "description")
SEMANTIC_CODE_KEYS = {"code", "statement", "run"}
SEMANTIC_ENGINE_ERROR: str | None = None
SEMANTIC_ENGINE: tuple[Any, Any, Any] | None = None


@dataclass(frozen=True)
class TestOccurrence:
    """Single test occurrence in a YAML file."""

    file: Path
    index: int
    name: str
    description: str = ""


def _normalize(value: Any, ignored_keys: set[str]) -> Any:
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key in sorted(value.keys(), key=str):
            if isinstance(key, str) and key in ignored_keys:
                continue
            normalized[str(key)] = _normalize(value[key], ignored_keys)
        return normalized
    if isinstance(value, list):
        return [_normalize(item, ignored_keys) for item in value]
    if isinstance(value, bytes):
        return {"__bytes__": list(value)}
    return value


def _normalize_semantic_value(value: Any) -> Any:
    """Normalize runtime objects from moo_interp into stable JSON-like values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return {"__bytes__": list(value)}
    if isinstance(value, Enum):
        return {"__enum__": f"{value.__class__.__name__}.{value.name}"}
    if isinstance(value, list):
        return [_normalize_semantic_value(item) for item in value]
    if isinstance(value, tuple):
        return {"__tuple__": [_normalize_semantic_value(item) for item in value]}
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key in sorted(value.keys(), key=str):
            normalized[str(key)] = _normalize_semantic_value(value[key])
        return normalized
    if hasattr(value, "value"):
        return {
            "__class__": value.__class__.__name__,
            "value": _normalize_semantic_value(getattr(value, "value")),
        }
    if hasattr(value, "__dict__"):
        data = {
            key: _normalize_semantic_value(val)
            for key, val in sorted(vars(value).items(), key=lambda kv: kv[0])
        }
        return {"__class__": value.__class__.__name__, "data": data}
    return repr(value)


def _get_semantic_engine() -> tuple[Any, Any, Any] | None:
    """Load moo_interp parse/compile functions lazily."""
    global SEMANTIC_ENGINE, SEMANTIC_ENGINE_ERROR
    if SEMANTIC_ENGINE is not None:
        return SEMANTIC_ENGINE
    if SEMANTIC_ENGINE_ERROR is not None:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from moo_interp.builtin_functions import BuiltinFunctions
            from moo_interp.moo_ast import compile as moo_compile
            from moo_interp.moo_ast import parse as moo_parse
        SEMANTIC_ENGINE = (moo_parse, moo_compile, BuiltinFunctions())
        return SEMANTIC_ENGINE
    except Exception as exc:  # pragma: no cover - exercised via integration
        SEMANTIC_ENGINE_ERROR = (
            "Semantic checks require `moo-interp`; failed to import parser/compiler: "
            f"{exc}"
        )
        return None


def get_semantic_engine_error() -> str | None:
    """Return human-readable semantic engine error, if any."""
    _get_semantic_engine()
    return SEMANTIC_ENGINE_ERROR


@lru_cache(maxsize=16384)
def _compile_moo_for_semantics(text: str, key: str) -> dict[str, Any]:
    """Compile code/statement-like text and return a canonical bytecode model."""
    engine = _get_semantic_engine()
    source = text.strip()
    if key == "code":
        if source.startswith("return "):
            compiled_source = source if source.endswith(";") else source + ";"
        else:
            compiled_source = f"return {source};"
    else:
        compiled_source = source if source.endswith(";") else source + ";"

    if engine is None:
        return {"kind": "raw", "source": source}

    moo_parse, moo_compile, bi_funcs = engine
    try:
        frame = moo_compile(moo_parse(compiled_source), bi_funcs=bi_funcs)
    except Exception:
        return {"kind": "raw", "source": source}

    instructions: list[dict[str, Any]] = []
    for inst in frame.stack:
        opcode = getattr(inst.opcode, "name", inst.opcode)
        model: dict[str, Any] = {"opcode": _normalize_semantic_value(opcode)}
        for attr_name in (
            "operand",
            "label",
            "loop_var",
            "loop_index",
            "jump_target",
            "handler_offset",
            "error_codes",
            "error_vars",
            "scatter_pattern",
        ):
            attr_value = getattr(inst, attr_name, None)
            if attr_value is not None:
                model[attr_name] = _normalize_semantic_value(attr_value)
        instructions.append(model)

    return {
        "kind": "compiled",
        "instructions": instructions,
    }


def _semanticize(node: Any, key: str | None = None) -> Any:
    """Replace runnable MOO code snippets with semantic bytecode fingerprints."""
    if isinstance(node, dict):
        return {k: _semanticize(v, k) for k, v in node.items()}
    if isinstance(node, list):
        return [_semanticize(item, key) for item in node]
    if isinstance(node, str) and key in SEMANTIC_CODE_KEYS:
        return _compile_moo_for_semantics(node, key=key)
    return node


def _iter_yaml_files(test_dir: Path) -> list[Path]:
    return sorted(path for path in test_dir.rglob("*.yaml") if path.is_file())


def _load_tests_from_file(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    tests = data.get("tests", [])
    if not isinstance(tests, list):
        return []
    return [test for test in tests if isinstance(test, dict)]


def _load_suite_context_and_tests(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Load suite-level setup/teardown context plus tests from a YAML file."""
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    tests = data.get("tests", [])
    if not isinstance(tests, list):
        return {"suite_setup": data.get("setup"), "suite_teardown": data.get("teardown")}, []
    parsed_tests = [test for test in tests if isinstance(test, dict)]
    suite_context = {
        "suite_setup": data.get("setup"),
        "suite_teardown": data.get("teardown"),
    }
    return suite_context, parsed_tests


def detect_duplicate_names(test_dir: Path) -> dict[str, list[TestOccurrence]]:
    """Find duplicate test names across all YAML files."""
    by_name: dict[str, list[TestOccurrence]] = defaultdict(list)

    for path in _iter_yaml_files(test_dir):
        tests = _load_tests_from_file(path)
        for index, test in enumerate(tests, start=1):
            name = str(test.get("name", f"<unnamed_{index}>"))
            by_name[name].append(TestOccurrence(path, index, name))

    return {name: occurrences for name, occurrences in by_name.items() if len(occurrences) > 1}


def detect_duplicate_content(
    test_dir: Path, ignored_keys: tuple[str, ...] = DEFAULT_IGNORED_KEYS
) -> list[list[TestOccurrence]]:
    """Find test definitions that are structurally identical."""
    fingerprints: dict[str, list[TestOccurrence]] = defaultdict(list)
    ignored = set(ignored_keys)

    for path in _iter_yaml_files(test_dir):
        suite_context, tests = _load_suite_context_and_tests(path)
        for index, test in enumerate(tests, start=1):
            fingerprint_payload = {
                "suite_setup": suite_context["suite_setup"],
                "test": test,
                "suite_teardown": suite_context["suite_teardown"],
            }
            normalized = _normalize(fingerprint_payload, ignored)
            fingerprint = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
            name = str(test.get("name", f"<unnamed_{index}>"))
            description = str(test.get("description", ""))
            fingerprints[fingerprint].append(
                TestOccurrence(path, index, name, description=description)
            )

    groups = [occurrences for occurrences in fingerprints.values() if len(occurrences) > 1]
    groups.sort(key=lambda group: (-len(group), group[0].name))
    return groups


def detect_duplicate_semantic(
    test_dir: Path, ignored_keys: tuple[str, ...] = DEFAULT_IGNORED_KEYS
) -> list[list[TestOccurrence]]:
    """Find semantic-lite duplicates using moo_interp compilation fingerprints."""
    fingerprints: dict[str, list[TestOccurrence]] = defaultdict(list)
    ignored = set(ignored_keys)

    for path in _iter_yaml_files(test_dir):
        suite_context, tests = _load_suite_context_and_tests(path)
        for index, test in enumerate(tests, start=1):
            fingerprint_payload = {
                "suite_setup": suite_context["suite_setup"],
                "test": test,
                "suite_teardown": suite_context["suite_teardown"],
            }
            normalized = _normalize(fingerprint_payload, ignored)
            semantic = _semanticize(normalized)
            fingerprint = json.dumps(semantic, sort_keys=True, separators=(",", ":"))
            name = str(test.get("name", f"<unnamed_{index}>"))
            description = str(test.get("description", ""))
            fingerprints[fingerprint].append(
                TestOccurrence(path, index, name, description=description)
            )

    groups = [occurrences for occurrences in fingerprints.values() if len(occurrences) > 1]
    groups.sort(key=lambda group: (-len(group), group[0].name))
    return groups


def _format_occurrence(item: TestOccurrence, base_dir: Path) -> str:
    try:
        rel_path = item.file.relative_to(base_dir).as_posix()
    except ValueError:
        rel_path = item.file.as_posix()
    return f"{rel_path}::#{item.index} ({item.name})"


def choose_occurrence_to_keep(
    occurrences: list[TestOccurrence], keep_strategy: str = "most-described"
) -> TestOccurrence:
    """Choose the canonical test from a duplicate-content group."""
    if keep_strategy == "first":
        return min(occurrences, key=lambda item: (item.file.as_posix(), item.index))
    if keep_strategy == "last":
        return max(occurrences, key=lambda item: (item.file.as_posix(), item.index))
    if keep_strategy == "longest-name":
        max_name_len = max(len(item.name) for item in occurrences)
        candidates = [item for item in occurrences if len(item.name) == max_name_len]
        return min(candidates, key=lambda item: (item.file.as_posix(), item.index))
    if keep_strategy == "most-described":
        max_desc_len = max(len(item.description.strip()) for item in occurrences)
        candidates = [item for item in occurrences if len(item.description.strip()) == max_desc_len]
        max_name_len = max(len(item.name) for item in candidates)
        candidates = [item for item in candidates if len(item.name) == max_name_len]
        return min(candidates, key=lambda item: (item.file.as_posix(), item.index))
    raise ValueError(f"Unknown keep strategy: {keep_strategy}")


def _build_cleanup_plan(
    groups: list[list[TestOccurrence]],
    *,
    keep_strategy: str = "most-described",
) -> list[tuple[TestOccurrence, list[TestOccurrence]]]:
    """Build a cleanup plan as (keep, remove[]) tuples per duplicate group."""
    plans: list[tuple[TestOccurrence, list[TestOccurrence]]] = []
    for group in groups:
        keep = choose_occurrence_to_keep(group, keep_strategy=keep_strategy)
        remove = [item for item in group if item != keep]
        plans.append((keep, remove))
    return plans


def plan_duplicate_content_cleanup(
    test_dir: Path,
    *,
    ignored_keys: tuple[str, ...] = DEFAULT_IGNORED_KEYS,
    keep_strategy: str = "most-described",
) -> list[tuple[TestOccurrence, list[TestOccurrence]]]:
    """Build a cleanup plan as (keep, remove[]) tuples per duplicate-content group."""
    groups = detect_duplicate_content(test_dir, ignored_keys=ignored_keys)
    return _build_cleanup_plan(groups, keep_strategy=keep_strategy)


def plan_duplicate_semantic_cleanup(
    test_dir: Path,
    *,
    ignored_keys: tuple[str, ...] = DEFAULT_IGNORED_KEYS,
    keep_strategy: str = "most-described",
) -> list[tuple[TestOccurrence, list[TestOccurrence]]]:
    """Build a cleanup plan as (keep, remove[]) tuples per semantic duplicate group."""
    groups = detect_duplicate_semantic(test_dir, ignored_keys=ignored_keys)
    return _build_cleanup_plan(groups, keep_strategy=keep_strategy)


def _apply_cleanup_plan(
    plans: list[tuple[TestOccurrence, list[TestOccurrence]]],
) -> tuple[int, int]:
    """Apply a cleanup plan and return (changed_files, removed_tests)."""
    removals_by_file: dict[Path, set[int]] = defaultdict(set)

    for _keep, remove_items in plans:
        for item in remove_items:
            removals_by_file[item.file].add(item.index)

    changed_files = 0
    removed_tests = 0

    for path, remove_indexes in removals_by_file.items():
        with path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        tests = data.get("tests", [])
        if not isinstance(tests, list):
            continue
        filtered = [test for idx, test in enumerate(tests, start=1) if idx not in remove_indexes]
        removed_here = len(tests) - len(filtered)
        if removed_here <= 0:
            continue
        data["tests"] = filtered
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        changed_files += 1
        removed_tests += removed_here

    return changed_files, removed_tests


def apply_duplicate_content_cleanup(
    test_dir: Path,
    *,
    ignored_keys: tuple[str, ...] = DEFAULT_IGNORED_KEYS,
    keep_strategy: str = "most-described",
) -> tuple[int, int, list[tuple[TestOccurrence, list[TestOccurrence]]]]:
    """Remove duplicate-content tests in-place and return cleanup stats."""
    plans = plan_duplicate_content_cleanup(
        test_dir, ignored_keys=ignored_keys, keep_strategy=keep_strategy
    )
    changed_files, removed_tests = _apply_cleanup_plan(plans)

    return changed_files, removed_tests, plans


def apply_duplicate_semantic_cleanup(
    test_dir: Path,
    *,
    ignored_keys: tuple[str, ...] = DEFAULT_IGNORED_KEYS,
    keep_strategy: str = "most-described",
) -> tuple[int, int, list[tuple[TestOccurrence, list[TestOccurrence]]]]:
    """Remove semantic duplicate tests in-place and return cleanup stats."""
    plans = plan_duplicate_semantic_cleanup(
        test_dir, ignored_keys=ignored_keys, keep_strategy=keep_strategy
    )
    changed_files, removed_tests = _apply_cleanup_plan(plans)

    return changed_files, removed_tests, plans


def run_duplicate_lint(
    test_dir: Path,
    *,
    check_names: bool = True,
    check_content: bool = True,
    check_semantic: bool = False,
    ignored_keys: tuple[str, ...] = DEFAULT_IGNORED_KEYS,
    fix_content: bool = False,
    fix_semantic: bool = False,
    keep_strategy: str = "most-described",
) -> int:
    """Run duplicate detection and return process exit code."""
    yaml_files = _iter_yaml_files(test_dir)
    test_count = sum(len(_load_tests_from_file(path)) for path in yaml_files)

    print(f"Scanned {len(yaml_files)} YAML files and {test_count} tests in {test_dir.as_posix()}")

    failed = False

    if check_names:
        name_dups = detect_duplicate_names(test_dir)
        if not name_dups:
            print("No duplicate test names found.")
        else:
            failed = True
            print(f"Duplicate test names found: {len(name_dups)} groups")
            for name, occurrences in sorted(name_dups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
                print(f"- {name} ({len(occurrences)} occurrences)")
                for item in occurrences:
                    print(f"  {_format_occurrence(item, test_dir)}")

    if check_content:
        content_dups = detect_duplicate_content(test_dir, ignored_keys=ignored_keys)
        if not content_dups:
            print("No duplicate test content found.")
        else:
            print(f"Duplicate test content found: {len(content_dups)} groups")
            plans = plan_duplicate_content_cleanup(
                test_dir, ignored_keys=ignored_keys, keep_strategy=keep_strategy
            )
            for keep, group_remove in plans:
                group = [keep, *group_remove]
                print(f"- {len(group)} identical definitions")
                print(f"  keep: {_format_occurrence(keep, test_dir)}")
                for item in group_remove:
                    print(f"  {_format_occurrence(item, test_dir)}")

            if fix_content:
                changed_files, removed_tests, _ = apply_duplicate_content_cleanup(
                    test_dir, ignored_keys=ignored_keys, keep_strategy=keep_strategy
                )
                print(
                    f"Applied cleanup with strategy '{keep_strategy}': "
                    f"removed {removed_tests} tests across {changed_files} files."
                )
                remaining = detect_duplicate_content(test_dir, ignored_keys=ignored_keys)
                if remaining:
                    failed = True
                    print(f"{len(remaining)} duplicate-content groups remain after cleanup.")
                else:
                    print("No duplicate test content found after cleanup.")
            else:
                failed = True

    if check_semantic:
        semantic_engine_error = get_semantic_engine_error()
        if semantic_engine_error:
            failed = True
            print(semantic_engine_error)
        else:
            semantic_dups = detect_duplicate_semantic(test_dir, ignored_keys=ignored_keys)
            if not semantic_dups:
                print("No semantic duplicate test content found.")
            else:
                print(f"Semantic duplicate test content found: {len(semantic_dups)} groups")
                plans = plan_duplicate_semantic_cleanup(
                    test_dir, ignored_keys=ignored_keys, keep_strategy=keep_strategy
                )
                for keep, group_remove in plans:
                    group = [keep, *group_remove]
                    print(f"- {len(group)} semantic-equivalent definitions")
                    print(f"  keep: {_format_occurrence(keep, test_dir)}")
                    for item in group_remove:
                        print(f"  {_format_occurrence(item, test_dir)}")

                if fix_semantic:
                    changed_files, removed_tests, _ = apply_duplicate_semantic_cleanup(
                        test_dir, ignored_keys=ignored_keys, keep_strategy=keep_strategy
                    )
                    print(
                        f"Applied semantic cleanup with strategy '{keep_strategy}': "
                        f"removed {removed_tests} tests across {changed_files} files."
                    )
                    remaining = detect_duplicate_semantic(test_dir, ignored_keys=ignored_keys)
                    if remaining:
                        failed = True
                        print(f"{len(remaining)} semantic duplicate groups remain after cleanup.")
                    else:
                        print("No semantic duplicate test content found after cleanup.")
                else:
                    failed = True

    if failed:
        print("Duplicate lint failed.")
        return 1

    print("Duplicate lint passed.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Detect duplicate conformance tests.")
    parser.add_argument(
        "--tests-dir",
        type=Path,
        default=get_tests_dir(),
        help="Directory containing YAML test files (default: bundled tests).",
    )
    parser.add_argument(
        "--only",
        choices=("names", "content", "semantic"),
        help="Run only one type of duplicate check.",
    )
    parser.add_argument(
        "--semantic",
        action="store_true",
        help="Also run semantic-lite duplicate checks using moo_interp compilation.",
    )
    parser.add_argument(
        "--include-description",
        action="store_true",
        help="Include test descriptions when checking duplicate content.",
    )
    parser.add_argument(
        "--fix-content",
        action="store_true",
        help="Remove duplicate-content tests in-place.",
    )
    parser.add_argument(
        "--fix-semantic",
        action="store_true",
        help="Remove semantic duplicate tests in-place (requires --semantic or --only semantic).",
    )
    parser.add_argument(
        "--keep-strategy",
        choices=("first", "last", "longest-name", "most-described"),
        default="most-described",
        help="How to choose the test to keep when removing duplicates.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    check_names = args.only in (None, "names")
    check_content = args.only in (None, "content")
    check_semantic = args.only == "semantic" or args.semantic or args.fix_semantic

    if args.only == "semantic":
        check_names = False
        check_content = False

    ignored_keys = ("name",)
    if not args.include_description:
        ignored_keys = ("name", "description")

    return run_duplicate_lint(
        args.tests_dir,
        check_names=check_names,
        check_content=check_content,
        check_semantic=check_semantic,
        ignored_keys=ignored_keys,
        fix_content=args.fix_content,
        fix_semantic=args.fix_semantic,
        keep_strategy=args.keep_strategy,
    )


if __name__ == "__main__":
    raise SystemExit(main())
