import pytest

from moo_conformance.schema import validate_test_suite


def _suite(test: dict) -> dict:
    return {"name": "expectation schema", "tests": [{"name": "case", **test}]}


@pytest.mark.parametrize(
    ("test", "message"),
    [
        (
            {"code": "1", "expect": {"output": "line"}},
            "does not support output",
        ),
        (
            {"steps": [{"run": "1"}], "expect": {"value": 1}},
            "multi-step test cannot have a top-level expectation",
        ),
        (
            {"steps": [{"run": "1", "expect": {"output": "line"}}]},
            "run does not support output",
        ),
        (
            {"steps": [{"command": "look", "expect": {"value": 1}}]},
            "command only supports output",
        ),
        (
            {"steps": [{"wait": 0, "expect": {"value": 1}}]},
            "wait does not produce an expectation result",
        ),
        (
            {
                "code": "1",
                "cleanup": [{"run": "1", "expect": {"value": 1}}],
            },
            "cleanup steps cannot have expectations",
        ),
    ],
)
def test_invalid_expectation_contracts_fail_closed(test: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_test_suite(_suite(test))


def test_satisfies_must_reference_the_reserved_actual_binding() -> None:
    with pytest.raises(ValueError, match="must reference __actual__"):
        validate_test_suite(_suite({"code": "1", "expect": {"satisfies": "1"}}))


def test_compatible_result_assertions_are_preserved() -> None:
    suite = validate_test_suite(
        _suite({"code": "1", "expect": {"value": 1, "type": "int"}})
    )

    assert suite.tests[0].expect.value == 1
    assert suite.tests[0].expect.type == "int"


@pytest.mark.parametrize(
    ("declared", "field", "expected"),
    [
        ({"exact": ["room"]}, "exact", ["room"]),
        ({"match": "roo."}, "match", "roo."),
        ({"contains": "oom"}, "contains", "oom"),
    ],
)
def test_each_output_assertion_is_preserved(
    declared: dict, field: str, expected: object
) -> None:
    suite = validate_test_suite(
        _suite(
            {
                "steps": [
                    {
                        "command": "look",
                        "expect": {"output": declared},
                    }
                ]
            }
        )
    )

    output = suite.tests[0].steps[0].expect.output
    assert output is not None
    assert getattr(output, field) == expected


@pytest.mark.parametrize(
    "action",
    [
        {"allocate_port": {"capture": "port"}},
        {"new_connection": {"capture": "conn"}},
        {"close_connection": "conn"},
        {"wait": 0},
        {"assert_log": {"contains": "ready"}},
        {"assert_file": {"path": "out.txt", "exists": True}},
        {"write_file": {"path": "in.txt", "content": "data"}},
        {"write_stdin": "quit\n"},
        {"restart_server": {}},
    ],
)
def test_every_non_result_action_rejects_expectations(action: dict) -> None:
    action["expect"] = {"value": 1}

    with pytest.raises(ValueError, match="does not produce an expectation result"):
        validate_test_suite(_suite({"steps": [action]}))


@pytest.mark.parametrize(
    "action",
    [
        {"command": "look"},
        {"send": {"connection": "conn", "text": "look"}},
        {"send_bytes": {"connection": "conn", "hex": "00"}},
        {"read_connection": {"connection": "conn"}},
    ],
)
def test_every_raw_output_action_accepts_only_output(action: dict) -> None:
    accepted = {**action, "expect": {"output": []}}
    suite = validate_test_suite(_suite({"steps": [accepted]}))
    assert suite.tests[0].steps[0].expect.output.exact == []

    rejected = {**action, "expect": {"value": 1}}
    with pytest.raises(ValueError, match="only supports output"):
        validate_test_suite(_suite({"steps": [rejected]}))
