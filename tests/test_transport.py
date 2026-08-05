"""Socket response parsing regressions."""

from moo_conformance.moo_types import MooError
from moo_conformance.transport import SocketTransport


def test_toast_incorrect_number_of_arguments_traceback_is_e_args() -> None:
    response = """#-1:Input to EVAL (this == #-1), line 65:  Incorrect number of arguments (expected 1; got 0)
... called from built-in function eval()
... called from #58:eval_cmd_string, line 20
... called from #58:eval*-d @eval, line 14
(End of traceback)"""

    result = SocketTransport()._parse_response(response)

    assert result.success is False
    assert result.error is MooError.E_ARGS
    assert result.error_message is None


def test_toast_eval_separates_notifications_from_the_result() -> None:
    result = SocketTransport()._parse_response("first notice\nsecond notice\n=> {1, 2}")

    assert result.success is True
    assert result.value == [1, 2]
    assert result.notifications == [
        {"message": "first notice"},
        {"message": "second notice"},
    ]


def test_toast_eval_separates_notifications_from_a_traceback() -> None:
    response = """notice before failure
#-1:Input to EVAL (this == #-1), line 1:  Division by zero
(End of traceback)"""

    result = SocketTransport()._parse_response(response)

    assert result.success is False
    assert result.error is MooError.E_DIV
    assert result.notifications == [{"message": "notice before failure"}]


def test_wrapped_eval_separates_notifications_from_the_result() -> None:
    result = SocketTransport()._parse_response("wrapped notice\n{1, 7}")

    assert result.success is True
    assert result.value == 7
    assert result.notifications == [{"message": "wrapped notice"}]
