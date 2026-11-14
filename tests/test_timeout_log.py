from pathlib import Path
from unittest.mock import Mock

import pytest

from moo_conformance.runner import YamlTestRunner
from moo_conformance.schema import MooTestCase


def _runner_whose_command_times_out(log_path: Path | None, logged: str) -> YamlTestRunner:
    transport = Mock()
    transport.sock = object()

    def no_reply(_code: str) -> None:
        if log_path is not None and logged:
            with log_path.open("a", encoding="utf-8") as log:
                log.write(logged)
        raise TimeoutError("timed out")

    transport.execute.side_effect = no_reply
    return YamlTestRunner(transport, log_file_path=None if log_path is None else str(log_path))


def test_command_timeout_carries_the_server_log_written_during_the_test(tmp_path: Path):
    log_path = tmp_path / "server.log"
    log_path.write_text("before the test\n", encoding="utf-8")
    runner = _runner_whose_command_times_out(log_path, "CHECKPOINTING on db.new\n")

    with pytest.raises(TimeoutError) as raised:
        runner.run_test(MooTestCase(name="case", code="return 1;"))

    message = str(raised.value)
    assert message.startswith("timed out\n")
    assert "CHECKPOINTING on db.new" in message
    assert "before the test" not in message


def test_command_timeout_keeps_only_the_end_of_a_long_log(tmp_path: Path):
    log_path = tmp_path / "server.log"
    log_path.write_text("", encoding="utf-8")
    runner = _runner_whose_command_times_out(log_path, "x" * 5000 + "LAST LINE\n")

    with pytest.raises(TimeoutError) as raised:
        runner.run_test(MooTestCase(name="case", code="return 1;"))

    message = str(raised.value)
    assert "last 4000 characters" in message
    assert message.endswith("LAST LINE\n")
    assert len(message) < 4200


def test_command_timeout_says_when_nothing_was_logged(tmp_path: Path):
    log_path = tmp_path / "server.log"
    log_path.write_text("before the test\n", encoding="utf-8")
    runner = _runner_whose_command_times_out(log_path, "")

    with pytest.raises(TimeoutError, match="Server log since test start: empty."):
        runner.run_test(MooTestCase(name="case", code="return 1;"))


def test_command_timeout_says_when_no_log_file_is_configured():
    runner = _runner_whose_command_times_out(None, "")

    with pytest.raises(TimeoutError, match="no log file is configured"):
        runner.run_test(MooTestCase(name="case", code="return 1;"))
