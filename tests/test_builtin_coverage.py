from pathlib import Path

import yaml

from moo_conformance.builtin_coverage import collect_builtin_calls, iter_builtin_calls


def test_iter_builtin_calls_reports_literal_type_shapes() -> None:
    calls = list(
        iter_builtin_calls(
            'return value_hash(1, "sha256", 1.5) && typeof({1, #0, E_ARGS, [1 -> 2]});',
            {"value_hash", "typeof"},
        )
    )

    assert calls == [
        ("value_hash", 3, ("int", "str", "float")),
        ("typeof", 1, ("list",)),
    ]


def test_iter_builtin_calls_marks_variables_unknown() -> None:
    calls = list(iter_builtin_calls("x = 1; return value_hash(x);", {"value_hash"}))

    assert calls == [("value_hash", 1, ("unknown",))]


def test_collect_builtin_calls_sees_expanded_table_rows(tmp_path: Path) -> None:
    suite = {
        "name": "table_builtin_suite",
        "tests": [
            {
                "name": "hash_{kind}",
                "table": {
                    "columns": ["kind", "expr"],
                    "rows": [
                        ["int", "value_hash(1)"],
                        ["str", 'value_hash("x")'],
                    ],
                },
                "code": "{expr}",
                "expect": {"type": "str"},
            }
        ],
    }
    path = tmp_path / "suite.yaml"
    path.write_text(yaml.safe_dump(suite, sort_keys=False), encoding="utf-8")

    calls = collect_builtin_calls(tmp_path, {"value_hash"})

    assert [(call.name, call.arity, call.arg_types, call.context) for call in calls] == [
        ("value_hash", 1, ("int",), "hash_int"),
        ("value_hash", 1, ("str",), "hash_str"),
    ]
