import pytest

from moo_conformance.moo_types import MooError
from moo_conformance.runner import AssertionError as RunnerAssertionError
from moo_conformance.runner import YamlTestRunner
from moo_conformance.schema import Expectation, MooTestCase, OutputExpect, validate_test_suite
from moo_conformance.schema import TestStep as MooTestStep
from moo_conformance.transport import ExecutionResult


class FakeTransport:
    def __init__(self, results: list[ExecutionResult]) -> None:
        self.results = iter(results)
        self.executed: list[str] = []
        self.sock: object | None = object()
        self.current_user = "programmer"

    def connect(self, user: str = "programmer") -> None:
        self.current_user = user
        self.sock = object()

    def disconnect(self) -> None:
        self.sock = None

    def switch_user(self, user: str = "programmer") -> None:
        self.current_user = user

    def execute(self, code: str) -> ExecutionResult:
        self.executed.append(code)
        return next(self.results)


def test_declared_statement_forces_database_statement_mode() -> None:
    transport = FakeTransport([ExecutionResult(success=True, value=1)])
    runner = YamlTestRunner(transport)  # type: ignore[arg-type]

    runner.run_test(
        MooTestCase(
            name="statement mode",
            statement="value = 1; return value;",
            expect=Expectation(value=1),
        )
    )

    assert transport.executed == ["; value = 1; return value;"]


def test_multistatement_run_step_forces_database_statement_mode() -> None:
    transport = FakeTransport([ExecutionResult(success=True, value=1)])
    runner = YamlTestRunner(transport)  # type: ignore[arg-type]

    runner.run_test(
        MooTestCase(
            name="step statement mode",
            steps=[
                MooTestStep(
                    run="value = 1; return value;",
                    expect=Expectation(value=1),
                )
            ],
        )
    )

    assert transport.executed == ["; value = 1; return value;"]


@pytest.mark.parametrize(
    ("expectation", "result", "message"),
    [
        (
            Expectation(contains="needle"),
            ExecutionResult(success=True, value=["other"]),
            "expected list to contain",
        ),
        (
            Expectation(range=[1, 10]),
            ExecutionResult(success=True, value=11),
            "expected value in range",
        ),
        (
            Expectation(notifications=["expected notice"]),
            ExecutionResult(success=True, value=1, notifications=[]),
            "expected notification",
        ),
    ],
)
def test_run_step_enforces_every_result_expectation(
    expectation: Expectation,
    result: ExecutionResult,
    message: str,
) -> None:
    transport = FakeTransport([result])
    runner = YamlTestRunner(transport)  # type: ignore[arg-type]
    test = MooTestCase(
        name="step expectation",
        steps=[MooTestStep(run="1", expect=expectation)],
    )

    with pytest.raises(RunnerAssertionError, match=message):
        runner.run_test(test)


@pytest.mark.parametrize("as_step", [False, True])
def test_satisfies_rejects_false_predicate_for_both_execution_paths(as_step: bool) -> None:
    transport = FakeTransport(
        [
            ExecutionResult(success=True, value=[1, 2]),
            ExecutionResult(success=True, value=0),
        ]
    )
    runner = YamlTestRunner(transport)  # type: ignore[arg-type]
    expectation = Expectation(satisfies="length(__actual__) == 3")
    test = (
        MooTestCase(
            name="step satisfies",
            steps=[MooTestStep(run="{1, 2}", expect=expectation)],
        )
        if as_step
        else MooTestCase(name="test satisfies", code="{1, 2}", expect=expectation)
    )

    with pytest.raises(RunnerAssertionError, match="satisf"):
        runner.run_test(test)


def test_satisfies_substitutes_the_result_as_a_moo_literal() -> None:
    transport = FakeTransport(
        [
            ExecutionResult(success=True, value=['a"b', [1, 2]]),
            ExecutionResult(success=True, value=1),
        ]
    )
    runner = YamlTestRunner(transport)  # type: ignore[arg-type]
    test = MooTestCase(
        name="serialize satisfies value",
        code='{"a\\"b", {1, 2}}',
        expect=Expectation(satisfies="length(__actual__) == 2"),
    )

    runner.run_test(test)

    assert transport.executed == [
        'return {"a\\"b", {1, 2}};',
        '__actual__ = {"a\\"b", {1, 2}}; return !(!(length(__actual__) == 2));',
    ]


def test_satisfies_reports_predicate_execution_errors() -> None:
    transport = FakeTransport(
        [
            ExecutionResult(success=True, value=3),
            ExecutionResult(success=False, error_message="predicate exploded"),
        ]
    )
    runner = YamlTestRunner(transport)  # type: ignore[arg-type]
    test = MooTestCase(
        name="predicate error",
        code="3",
        expect=Expectation(satisfies="broken(__actual__)"),
    )

    with pytest.raises(RunnerAssertionError, match="predicate exploded"):
        runner.run_test(test)


def test_satisfies_predicate_is_not_rewritten_by_a_table_value_column() -> None:
    suite = validate_test_suite(
        {
            "name": "table satisfies",
            "tests": [
                {
                    "name": "row {value}",
                    "code": "{value}",
                    "expect": {"satisfies": "__actual__ == 3"},
                    "table": {"rows": [{"value": 3}]},
                }
            ],
        }
    )

    assert suite.tests[0].expect.satisfies == "__actual__ == 3"


def test_satisfies_rejects_anonymous_values_that_cannot_be_round_tripped() -> None:
    transport = FakeTransport([ExecutionResult(success=True, value="*#12")])
    runner = YamlTestRunner(transport)  # type: ignore[arg-type]
    test = MooTestCase(
        name="anonymous satisfies",
        code="create($nothing, 1)",
        expect=Expectation(satisfies="typeof(__actual__) == ANON"),
    )

    with pytest.raises(RunnerAssertionError, match="cannot be round-tripped"):
        runner.run_test(test)

    assert transport.executed == ["return create($nothing, 1);"]


def test_match_does_not_suppress_notification_verification() -> None:
    transport = FakeTransport([ExecutionResult(success=True, value="ok", notifications=[])])
    runner = YamlTestRunner(transport)  # type: ignore[arg-type]
    test = MooTestCase(
        name="combined result assertions",
        code='"ok"',
        expect=Expectation(match="ok", notifications=["missing"]),
    )

    with pytest.raises(RunnerAssertionError, match="expected notification"):
        runner.run_test(test)


def test_error_and_match_do_not_suppress_notification_verification() -> None:
    transport = FakeTransport(
        [
            ExecutionResult(
                success=False,
                error=MooError.E_TYPE,
                error_message="type exploded",
                notifications=[],
            )
        ]
    )
    runner = YamlTestRunner(transport)  # type: ignore[arg-type]
    test = MooTestCase(
        name="combined error assertions",
        code="1 / 0",
        expect=Expectation(
            error="E_TYPE",
            match="exploded",
            notifications=["missing"],
        ),
    )

    with pytest.raises(RunnerAssertionError, match="expected notification"):
        runner.run_test(test)


def test_match_cannot_hide_an_error_when_a_success_assertion_is_present() -> None:
    transport = FakeTransport(
        [ExecutionResult(success=False, error_message="matched error text")]
    )
    runner = YamlTestRunner(transport)  # type: ignore[arg-type]
    test = MooTestCase(
        name="match plus type",
        code='"value"',
        expect=Expectation(match="matched", type="str"),
    )

    with pytest.raises(RunnerAssertionError, match="expected success"):
        runner.run_test(test)


def test_output_enforces_every_configured_assertion_mode() -> None:
    runner = YamlTestRunner(FakeTransport([]))  # type: ignore[arg-type]

    with pytest.raises(RunnerAssertionError, match="expected output to contain"):
        runner._verify_output(
            OutputExpect(exact="actual", contains="missing"),
            ["actual"],
            "combined output assertions",
        )


def test_exact_empty_output_is_line_precise() -> None:
    runner = YamlTestRunner(FakeTransport([]))  # type: ignore[arg-type]
    expectation = OutputExpect(exact=[])

    runner._verify_output(expectation, [], "empty output")
    with pytest.raises(RunnerAssertionError, match="expected output lines"):
        runner._verify_output(expectation, [""], "empty output")


@pytest.mark.parametrize(
    "step",
    [
        MooTestStep(wait=0, expect=Expectation(value=1)),
        MooTestStep(command="look", expect=Expectation(value=1)),
        MooTestStep(run="1", expect=Expectation(output=OutputExpect(exact="line"))),
    ],
)
def test_direct_steps_cannot_bypass_expectation_route_validation(step: MooTestStep) -> None:
    runner = YamlTestRunner(FakeTransport([]))  # type: ignore[arg-type]

    with pytest.raises(RunnerAssertionError):
        runner.run_test(MooTestCase(name="direct route", steps=[step]))
