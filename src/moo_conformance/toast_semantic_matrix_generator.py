"""Generate source-derived Toast semantic conformance matrices."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = REPO_ROOT / "src" / "moo_conformance" / "_tests"
GENERATOR = "python -m moo_conformance.toast_semantic_matrix_generator"
EXPECTED_ROW_COUNT = 1122


@dataclass(frozen=True)
class Value:
    name: str
    expr: str
    ci_group: str
    cs_group: str
    kind: str
    order: int | float | str | None = None


VALUES = (
    Value("int_neg", "-1", "int_neg", "int_neg", "int", -1),
    Value("int_zero", "0", "zero", "zero", "int", 0),
    Value("int_one", "1", "one", "one", "int", 1),
    Value("int_two", "2", "int_two", "int_two", "int", 2),
    Value("bool_false", "false", "zero", "zero", "bool", False),
    Value("bool_true", "true", "one", "one", "bool", True),
    Value("float_neg_zero", "-0.0", "float_zero", "float_zero", "float", -0.0),
    Value("float_zero", "0.0", "float_zero", "float_zero", "float", 0.0),
    Value("float_one", "1.0", "float_one", "float_one", "float", 1.0),
    Value("str_empty", '""', "str_empty", "str_empty", "str", ""),
    Value("str_lower", '"alpha"', "str_alpha", "str_lower", "str", "alpha"),
    Value("str_upper", '"ALPHA"', "str_alpha", "str_upper", "str", "ALPHA"),
    Value("str_other", '"beta"', "str_beta", "str_beta", "str", "beta"),
    Value("obj_nothing", "#-1", "obj_nothing", "obj_nothing", "obj", -1),
    Value("obj_zero", "#0", "obj_zero", "obj_zero", "obj", 0),
    Value("obj_one", "#1", "obj_one", "obj_one", "obj", 1),
    Value("err_none", "E_NONE", "err_none", "err_none", "err", 0),
    Value("err_type", "E_TYPE", "err_type", "err_type", "err", 1),
    Value("err_div", "E_DIV", "err_div", "err_div", "err", 2),
    Value("list_empty", "{}", "list_empty", "list_empty", "list"),
    Value("list_int", "{1}", "list_int", "list_int", "list"),
    Value("list_lower", '{"alpha"}', "list_alpha", "list_lower", "list"),
    Value("list_upper", '{"ALPHA"}', "list_alpha", "list_upper", "list"),
    Value("map_empty", "[]", "map_empty", "map_empty", "map"),
    Value(
        "map_lower",
        '["alpha" -> {1}]',
        "map_alpha",
        "map_lower",
        "map",
    ),
    Value(
        "map_upper",
        '["ALPHA" -> {1}]',
        "map_alpha",
        "map_upper",
        "map",
    ),
)
VALUE_BY_NAME = {value.name: value for value in VALUES}


CONTAINERS = (
    ("empty", ()),
    ("scalar_forward", tuple(value.name for value in VALUES[:19])),
    ("scalar_reverse", tuple(value.name for value in reversed(VALUES[:19]))),
    (
        "bool_int_interleave",
        ("int_zero", "bool_false", "int_one", "bool_true", "int_two", "int_neg"),
    ),
    ("string_case_order", ("str_upper", "str_other", "str_lower", "str_upper")),
    (
        "numeric_type_boundaries",
        (
            "float_neg_zero",
            "float_zero",
            "float_one",
            "int_zero",
            "int_one",
            "bool_false",
            "bool_true",
        ),
    ),
    (
        "objects_errors",
        ("obj_one", "obj_zero", "obj_nothing", "err_div", "err_type", "err_none"),
    ),
    (
        "collections",
        (
            "list_empty",
            "list_int",
            "list_lower",
            "list_upper",
            "map_empty",
            "map_lower",
            "map_upper",
        ),
    ),
    ("nested_case_order", ("list_upper", "list_lower", "map_upper", "map_lower")),
    ("all_values", tuple(value.name for value in VALUES)),
)


STRING_PAIRS = (
    ("bananana_ana", "bananana", "ana"),
    ("mixed_foobar_o", "FoObAr", "o"),
    ("repeated_a", "aaaa", "aa"),
    ("overlap_aba", "abababa", "aba"),
    ("alpha_case", "alphaALPHA", "ALPHA"),
    ("prefix_suffix_fix", "prefix-suffix", "fix"),
    ("mississippi_issi", "mississippi", "issi"),
    ("xyz_case", "xyzxyz", "XYZ"),
)


def scalar(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def unordered_pairs(values: tuple[Value, ...]) -> Iterable[tuple[Value, Value]]:
    for left_index, left in enumerate(values):
        for right in values[left_index:]:
            yield left, right


def equality_expected(left: Value, right: Value) -> list[int]:
    ci_equal = int(left.ci_group == right.ci_group)
    cs_equal = int(left.cs_group == right.cs_group)
    return [ci_equal, 1 - ci_equal, ci_equal, cs_equal, cs_equal]


def comparison(left: Value, right: Value) -> int | str:
    if left.kind != right.kind or left.kind in {"list", "map"}:
        return "E_TYPE"
    if left.kind == "bool":
        # Toast execute.cc falls through its same-type scalar switch for BOOL.
        return 0
    if isinstance(left.order, str):
        assert isinstance(right.order, str)
        left_order = left.order.lower()
        right_order = right.order.lower()
        return (left_order > right_order) - (left_order < right_order)
    assert isinstance(left.order, (int, float))
    assert isinstance(right.order, (int, float))
    return (left.order > right.order) - (left.order < right.order)


def directional_relations(comparison_result: int | str) -> list[int | str]:
    if isinstance(comparison_result, str):
        assert comparison_result == "E_TYPE"
        return ["E_TYPE"] * 4
    return [
        int(comparison_result < 0),
        int(comparison_result <= 0),
        int(comparison_result > 0),
        int(comparison_result >= 0),
    ]


def relational_expected(left: Value, right: Value) -> list[int | str]:
    forward = comparison(left, right)
    reverse = comparison(right, left)
    return directional_relations(forward) + directional_relations(reverse)


def first_member(probe: Value, members: tuple[Value, ...], *, case_sensitive: bool) -> int:
    probe_group = probe.cs_group if case_sensitive else probe.ci_group
    for index, member in enumerate(members, start=1):
        member_group = member.cs_group if case_sensitive else member.ci_group
        if probe_group == member_group:
            return index
    return 0


def string_index(source: str, needle: str, case_sensitive: bool, offset: int) -> int:
    if offset > len(source):
        return 0
    haystack = source[offset:]
    if not case_sensitive:
        haystack = haystack.lower()
        needle = needle.lower()
    found = haystack.find(needle)
    return found + 1 if found >= 0 else 0


def string_rindex(source: str, needle: str, case_sensitive: bool, offset: int) -> int:
    retained = len(source) + offset
    if retained < 0:
        return 0
    haystack = source[:retained]
    if not case_sensitive:
        haystack = haystack.lower()
        needle = needle.lower()
    found = haystack.rfind(needle)
    return found + 1 if found >= 0 else 0


def render_rows(rows: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for row in rows:
        lines.append(f"        - case: {scalar(row['case'])}")
        for key, value in row.items():
            if key != "case":
                lines.append(f"          {key}: {scalar(value)}")
    return "\n".join(lines)


def header(name: str, description: str, builtins: tuple[str, ...]) -> list[str]:
    lines = [
        f"# Generated by {GENERATOR}; DO NOT EDIT BY HAND.",
        f"name: {name}",
        f"description: {scalar(description)}",
    ]
    if builtins:
        lines.extend(
            [
                "requires:",
                "  builtins:",
                *(f"    - {builtin}" for builtin in builtins),
            ]
        )
    lines.append("tests:")
    return lines


def render_equality() -> tuple[str, int]:
    rows = []
    for left, right in unordered_pairs(VALUES):
        rows.append(
            {
                "case": f"{left.name}__{right.name}",
                "lhs": left.expr,
                "rhs": right.expr,
                "expected": equality_expected(left, right),
            }
        )
    lines = header(
        "toast_equality_matrix",
        "Source-derived pairwise equality, symmetry, and case-mode contracts.",
        ("equal",),
    )
    lines.extend(
        [
            "  - name: equality_{case}",
            "    table:",
            "      rows:",
            render_rows(rows),
            "    code: >-",
            "      {{lhs} == {rhs}, {lhs} != {rhs}, {rhs} == {lhs},",
            "       equal({lhs}, {rhs}), equal({rhs}, {lhs})}",
            "    expect:",
            '      value: "{expected}"',
        ]
    )
    return "\n".join(lines) + "\n", len(rows)


def render_relational() -> tuple[str, int]:
    rows = []
    for left, right in unordered_pairs(VALUES):
        rows.append(
            {
                "case": f"{left.name}__{right.name}",
                "lhs": left.expr,
                "rhs": right.expr,
                "expected": relational_expected(left, right),
            }
        )
    lines = header(
        "toast_relational_matrix",
        "Source-derived scalar ordering and exact relational E_TYPE boundaries.",
        (),
    )
    lines.extend(
        [
            "  - name: relational_{case}",
            "    table:",
            "      rows:",
            render_rows(rows),
            "    code: >-",
            "      {`{lhs} < {rhs} ! ANY', `{lhs} <= {rhs} ! ANY',",
            "       `{lhs} > {rhs} ! ANY', `{lhs} >= {rhs} ! ANY',",
            "       `{rhs} < {lhs} ! ANY', `{rhs} <= {lhs} ! ANY',",
            "       `{rhs} > {lhs} ! ANY', `{rhs} >= {lhs} ! ANY'}",
            "    expect:",
            '      value: "{expected}"',
        ]
    )
    return "\n".join(lines) + "\n", len(rows)


def render_membership() -> tuple[str, int]:
    rows = []
    for container_name, member_names in CONTAINERS:
        members = tuple(VALUE_BY_NAME[name] for name in member_names)
        container_expr = "{" + ", ".join(member.expr for member in members) + "}"
        for probe in VALUES:
            ci_position = first_member(probe, members, case_sensitive=False)
            cs_position = first_member(probe, members, case_sensitive=True)
            rows.append(
                {
                    "case": f"{container_name}__{probe.name}",
                    "probe": probe.expr,
                    "container": container_expr,
                    "expected": [ci_position, cs_position, ci_position],
                }
            )
    lines = header(
        "toast_membership_matrix",
        "First-position, type-boundary, recursive, and case-mode membership contracts.",
        ("is_member",),
    )
    lines.extend(
        [
            "  - name: membership_{case}",
            "    table:",
            "      rows:",
            render_rows(rows),
            "    code: >-",
            "      {{probe} in {container}, is_member({probe}, {container}),",
            "       is_member({probe}, {container}, 0)}",
            "    expect:",
            '      value: "{expected}"',
        ]
    )
    return "\n".join(lines) + "\n", len(rows)


def render_string_offsets() -> tuple[str, int]:
    rows = []
    for pair_name, source, needle in STRING_PAIRS:
        length = len(source)
        for case_sensitive in (False, True):
            mode = "cs" if case_sensitive else "ci"
            for offset in (0, 1, length // 2, length, length + 2):
                rows.append(
                    {
                        "case": f"index__{pair_name}__{mode}__{offset}",
                        "expr": (
                            f"index({scalar(source)}, {scalar(needle)}, "
                            f"{int(case_sensitive)}, {offset})"
                        ),
                        "expected": string_index(source, needle, case_sensitive, offset),
                    }
                )
            for offset in (0, -1, -(length // 2), -length, -(length + 2)):
                offset_name = str(offset).replace("-", "neg_")
                rows.append(
                    {
                        "case": f"rindex__{pair_name}__{mode}__{offset_name}",
                        "expr": (
                            f"rindex({scalar(source)}, {scalar(needle)}, "
                            f"{int(case_sensitive)}, {offset})"
                        ),
                        "expected": string_rindex(source, needle, case_sensitive, offset),
                    }
                )
    lines = header(
        "toast_string_search_offset_matrix",
        "Source-derived index/rindex case and asymmetric offset contracts.",
        ("index", "rindex"),
    )
    lines.extend(
        [
            "  - name: string_search_{case}",
            "    table:",
            "      rows:",
            render_rows(rows),
            '    code: "{expr}"',
            "    expect:",
            '      value: "{expected}"',
        ]
    )
    return "\n".join(lines) + "\n", len(rows)


def build_outputs() -> tuple[dict[Path, str], dict[str, int]]:
    rendered = {
        TEST_ROOT / "language" / "toast_equality_matrix.yaml": render_equality(),
        TEST_ROOT / "language" / "toast_relational_matrix.yaml": render_relational(),
        TEST_ROOT / "language" / "toast_membership_matrix.yaml": render_membership(),
        TEST_ROOT / "builtins" / "toast_string_search_offset_matrix.yaml": (
            render_string_offsets()
        ),
    }
    counts = {path.name: count for path, (_, count) in rendered.items()}
    outputs = {path: content for path, (content, _) in rendered.items()}
    assert sum(counts.values()) == EXPECTED_ROW_COUNT
    return outputs, counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if checked-in generated YAML differs",
    )
    args = parser.parse_args(argv)
    outputs, counts = build_outputs()
    stale: list[str] = []
    for path, expected in outputs.items():
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != expected:
                stale.append(str(path.relative_to(REPO_ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(expected, encoding="utf-8", newline="\n")
    if stale:
        print("Generated semantic matrices are stale:")
        for stale_path in stale:
            print(f"- {stale_path}")
        return 1
    action = "Verified" if args.check else "Generated"
    print(f"{action} {sum(counts.values())} semantic matrix tests:")
    for name, count in counts.items():
        print(f"- {name}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
