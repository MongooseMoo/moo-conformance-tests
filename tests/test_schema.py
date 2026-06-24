import pytest

from moo_conformance.schema import validate_test_suite


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
