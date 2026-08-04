from copy import deepcopy

import pytest

from moo_conformance.schema import validate_test_suite


def _minimal_suite() -> dict:
    return {
        "name": "strict_schema",
        "tests": [
            {
                "name": "one",
                "code": "1",
                "expect": {"value": 1},
            }
        ],
    }


def _mapping_at(data: dict, path: tuple[str | int, ...]) -> dict:
    current = data
    for part in path:
        current = current[part]
    return current


@pytest.mark.parametrize(
    ("path", "addition"),
    [
        pytest.param((), {}, id="suite"),
        pytest.param(("requires",), {"requires": {}}, id="requirements"),
        pytest.param(("setup",), {"setup": {"code": "return 1;"}}, id="suite-setup"),
        pytest.param(
            ("tests", 0, "teardown"),
            {"tests": [{"name": "one", "code": "1", "teardown": {"code": "return 1;"}}]},
            id="test-teardown",
        ),
        pytest.param(("tests", 0), {}, id="test"),
        pytest.param(("tests", 0, "expect"), {}, id="expectation"),
        pytest.param(
            ("tests", 0, "steps", 0, "expect", "output"),
            {
                "tests": [
                    {
                        "name": "one",
                        "steps": [{"command": "look", "expect": {"output": {}}}],
                    }
                ]
            },
            id="output-expectation",
        ),
        pytest.param(
            ("tests", 0, "table"),
            {
                "tests": [
                    {
                        "name": "row_{value}",
                        "table": {"rows": [{"value": 1}]},
                        "code": "{value}",
                    }
                ]
            },
            id="table",
        ),
        pytest.param(
            ("tests", 0, "table", "product", 0),
            {
                "tests": [
                    {
                        "name": "row_{value}",
                        "table": {"product": [{"rows": [{"value": 1}]}]},
                        "code": "{value}",
                    }
                ]
            },
            id="table-product-axis",
        ),
        pytest.param(
            ("tests", 0, "steps", 0),
            {"tests": [{"name": "one", "steps": [{"run": "return 1;"}]}]},
            id="step",
        ),
    ],
)
def test_unknown_fields_are_rejected_at_closed_schema_boundaries(
    path: tuple[str | int, ...], addition: dict
) -> None:
    data = _minimal_suite()
    data.update(deepcopy(addition))
    _mapping_at(data, path)["unexpected"] = True

    with pytest.raises(ValueError, match=r"Unknown field.*unexpected"):
        validate_test_suite(data)


@pytest.mark.parametrize(
    ("action", "payload"),
    [
        (
            "verb_setup",
            {
                "object": "#0",
                "name": "v",
                "args": ["this", "none", "this"],
                "code": "return 1;",
            },
        ),
        ("allocate_port", {"capture": "port"}),
        ("new_connection", {"capture": "conn", "port": 7777}),
        ("send", {"text": "look", "connection": "conn"}),
        ("send_bytes", {"hex": "00", "connection": "conn"}),
        ("read_connection", {"connection": "conn"}),
        ("assert_log", {"contains": "ready"}),
        ("assert_file", {"path": "out.txt", "exists": True, "contains": "ready"}),
        ("write_file", {"path": "in.txt", "content": "data"}),
        ("write_stdin", {"text": "quit\n"}),
        ("restart_server", {"wait_ms": 1, "down_ms": 1}),
    ],
)
def test_unknown_fields_are_rejected_in_structured_actions(
    action: str, payload: dict
) -> None:
    payload = {**payload, "unexpected": True}
    data = {
        "name": "strict_action",
        "tests": [{"name": "one", "steps": [{action: payload}]}],
    }

    with pytest.raises(ValueError, match=r"Unknown field.*unexpected"):
        validate_test_suite(data)


def test_table_row_variable_mappings_remain_open() -> None:
    data = {
        "name": "open_rows",
        "tests": [
            {
                "name": "row_{agent_defined_variable}",
                "table": {"rows": [{"agent_defined_variable": 1}]},
                "code": "{agent_defined_variable}",
                "expect": {"value": 1},
            }
        ],
    }

    suite = validate_test_suite(data)

    assert suite.tests[0].name == "row_1"


def _suite_with_assert_log(assert_log: dict) -> dict:
    return {
        "name": "schema_assert_log",
        "tests": [
            {
                "name": "assert_log_step",
                "steps": [
                    {
                        "assert_log": assert_log,
                    },
                ],
            },
        ],
    }


@pytest.mark.parametrize(
    "assert_log",
    [
        {},
        {"contain": "misspelled predicate"},
    ],
)
def test_assert_log_requires_recognized_predicate(assert_log):
    with pytest.raises(ValueError, match="assert_log"):
        validate_test_suite(_suite_with_assert_log(assert_log))


@pytest.mark.parametrize(
    "assert_log",
    [
        {"contains": "checkpoint complete"},
        {"not_contains": "context deadline exceeded"},
    ],
)
def test_assert_log_accepts_known_predicates(assert_log):
    suite = validate_test_suite(_suite_with_assert_log(assert_log))

    parsed_assertion = suite.tests[0].steps[0].assert_log
    assert parsed_assertion is not None
    assert parsed_assertion.contains == assert_log.get("contains")
    assert parsed_assertion.not_contains == assert_log.get("not_contains")


def test_table_expands_dict_rows_into_concrete_tests() -> None:
    suite = validate_test_suite(
        {
            "name": "table_suite",
            "tests": [
                {
                    "name": "sqrt_{case}",
                    "table": {
                        "rows": [
                            {"case": "zero", "expr": "sqrt(0.0)", "expected": 0.0},
                            {"case": "four", "expr": "sqrt(4.0)", "expected": 2.0},
                        ],
                    },
                    "code": "{expr}",
                    "expect": {"value": "{expected}"},
                }
            ],
        }
    )

    assert [test.name for test in suite.tests] == ["sqrt_zero", "sqrt_four"]
    assert [test.code for test in suite.tests] == ["sqrt(0.0)", "sqrt(4.0)"]
    assert [test.expect.value for test in suite.tests] == [0.0, 2.0]


def test_table_expands_column_rows_into_concrete_tests() -> None:
    suite = validate_test_suite(
        {
            "name": "table_suite",
            "tests": [
                {
                    "name": "typeof_{kind}_{index}",
                    "table": {
                        "columns": ["kind", "expr", "expected"],
                        "rows": [
                            ["int", "typeof(1)", 0],
                            ["str", 'typeof("x")', 2],
                        ],
                    },
                    "code": "{expr}",
                    "expect": {"value": "{expected}"},
                }
            ],
        }
    )

    assert [test.name for test in suite.tests] == ["typeof_int_0", "typeof_str_1"]
    assert [test.code for test in suite.tests] == ["typeof(1)", 'typeof("x")']
    assert [test.expect.value for test in suite.tests] == [0, 2]


def test_table_expands_product_rows_into_concrete_tests() -> None:
    suite = validate_test_suite(
        {
            "name": "table_suite",
            "tests": [
                {
                    "name": "pair_{left_kind}_{right_kind}_{index}",
                    "table": {
                        "product": [
                            {
                                "columns": ["left_kind", "left_expr"],
                                "rows": [
                                    ["int", "1"],
                                    ["str", '"x"'],
                                ],
                            },
                            {
                                "rows": [
                                    {"right_kind": "err", "right_expr": "E_ARGS"},
                                    {"right_kind": "list", "right_expr": "{}"},
                                ],
                            },
                        ],
                    },
                    "code": "pair({left_expr}, {right_expr})",
                    "expect": {"error": "E_TYPE"},
                }
            ],
        }
    )

    assert [test.name for test in suite.tests] == [
        "pair_int_err_0",
        "pair_int_list_1",
        "pair_str_err_2",
        "pair_str_list_3",
    ]
    assert [test.code for test in suite.tests] == [
        "pair(1, E_ARGS)",
        "pair(1, {})",
        'pair("x", E_ARGS)',
        'pair("x", {})',
    ]


def test_table_expands_steps_and_cleanup() -> None:
    suite = validate_test_suite(
        {
            "name": "table_suite",
            "tests": [
                {
                    "name": "step_{case}",
                    "table": {
                        "rows": [
                            {"case": "one", "expr": "1", "expected": 1},
                        ],
                    },
                    "steps": [
                        {"run": "{expr}", "capture": "value"},
                        {"run": "{value}", "expect": {"value": "{expected}"}},
                    ],
                    "cleanup": [{"run": "typeof({expr})"}],
                }
            ],
        }
    )

    test = suite.tests[0]
    assert test.name == "step_one"
    assert test.steps[0].run == "1"
    assert test.steps[1].expect.value == 1
    assert test.cleanup[0].run == "typeof(1)"


def test_write_stdin_step_accepts_scalar_text() -> None:
    suite = validate_test_suite(
        {
            "name": "stdin_suite",
            "tests": [
                {
                    "name": "send_process_stdin",
                    "steps": [
                        {"write_stdin": "hello\n"},
                    ],
                }
            ],
        }
    )

    step = suite.tests[0].steps[0]
    assert step.write_stdin is not None
    assert step.write_stdin.text == "hello\n"


def test_write_stdin_step_accepts_mapping_text() -> None:
    suite = validate_test_suite(
        {
            "name": "stdin_suite",
            "tests": [
                {
                    "name": "send_process_stdin",
                    "steps": [
                        {"write_stdin": {"text": "mapped\n"}},
                    ],
                }
            ],
        }
    )

    step = suite.tests[0].steps[0]
    assert step.write_stdin is not None
    assert step.write_stdin.text == "mapped\n"


def test_table_product_rejects_duplicate_variables() -> None:
    with pytest.raises(ValueError, match="Product table variables must be unique: kind"):
        validate_test_suite(
            {
                "name": "table_suite",
                "tests": [
                    {
                        "name": "bad",
                        "table": {
                            "product": [
                                {"rows": [{"kind": "int", "expr": "1"}]},
                                {"rows": [{"kind": "str", "other": '"x"'}]},
                            ],
                        },
                        "code": "1",
                        "expect": {"value": 1},
                    }
                ],
            }
        )


def test_table_rejects_list_rows_without_columns() -> None:
    with pytest.raises(ValueError, match="List table rows require string columns"):
        validate_test_suite(
            {
                "name": "table_suite",
                "tests": [
                    {
                        "name": "bad",
                        "table": {"rows": [["x"]]},
                        "code": "1",
                        "expect": {"value": 1},
                    }
                ],
            }
        )
