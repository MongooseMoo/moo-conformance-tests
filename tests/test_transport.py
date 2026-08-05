"""Socket response parsing regressions."""

from moo_conformance.moo_types import MooError
from moo_conformance.transport import SocketTransport


def test_toast_incorrect_number_of_arguments_traceback_is_e_args() -> None:
    response = (
        "#-1:Input to EVAL (this == #-1), line 65:  Incorrect number of arguments "
        "(expected 1; got 0)\n"
        "... called from built-in function eval()\n"
        "... called from #58:eval_cmd_string, line 20\n"
        "... called from #58:eval*-d @eval, line 14\n"
        "(End of traceback)"
    )

    result = SocketTransport()._parse_response(response)

    assert result.success is False
    assert result.error is MooError.E_ARGS
    assert result.error_message is None
