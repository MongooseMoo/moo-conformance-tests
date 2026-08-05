import pytest

from moo_conformance.runner import AssertionError as RunnerAssertionError
from moo_conformance.runner import YamlTestRunner
from moo_conformance.schema import Expectation, MooTestCase, TestStep as MooTestStep
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
    expectation = Expectation(satisfies="length({value}) == 3")
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
        expect=Expectation(satisfies="length({value}) == 2"),
    )

    runner.run_test(test)

    assert transport.executed == [
        'return {"a\\"b", {1, 2}};',
        'return !(!(length({"a\\"b", {1, 2}}) == 2));',
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
        expect=Expectation(satisfies="broken({value})"),
    )

    with pytest.raises(RunnerAssertionError, match="predicate exploded"):
        runner.run_test(test)
