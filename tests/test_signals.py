import os
import signal
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from moo_conformance.runner import AssertionError as RunnerAssertionError
from moo_conformance.runner import YamlTestRunner
from moo_conformance.schema import validate_test_suite
from moo_conformance.server import ManagedServer, ManagedServerLifecycleError


def suite(steps):
    return validate_test_suite({"name": "signals", "tests": [{"name": "case", "steps": steps}]})


def test_signal_step_schema():
    assert suite([{"signal_server": "SIGUSR2"}]).tests[0].steps[0].signal_server == "SIGUSR2"


@pytest.mark.parametrize("name", [
    "SIGHUP", "SIGINT", "SIGQUIT", "SIGILL", "SIGSEGV", "SIGBUS", "SIGFPE",
    "SIGPIPE", "SIGUSR1", "SIGUSR2", "SIGCHLD", "SIGALRM", "SIGVTALRM", "SIGABRT",
])
def test_all_toast_signal_names_load_on_every_host(name):
    assert suite([{"signal_server": name}]).tests[0].steps[0].signal_server == name


@pytest.mark.parametrize("value", ["USR2", "SIGTYPO", 12, True, {}, "SIG_DFL"])
def test_invalid_signal_rejected(value):
    with pytest.raises(ValueError, match="signal_server"):
        suite([{"signal_server": value}])


@pytest.mark.skipif(os.name != "posix", reason="POSIX signal delivery")
def test_signal_targets_only_managed_process(tmp_path):
    server = ManagedServer("unused", tmp_path / "test.db")
    server._process = Mock()
    server._process.poll.return_value = None
    server.send_signal("SIGTERM")
    server._process.send_signal.assert_called_once_with(signal.SIGTERM)


@pytest.mark.skipif(os.name != "posix", reason="POSIX signal delivery")
def test_signal_dead_process_has_first_failure_evidence(tmp_path):
    server = ManagedServer("unused", tmp_path / "test.db")
    server._process = Mock()
    server._process.poll.return_value = -9
    with pytest.raises(ManagedServerLifecycleError, match="return code: -9") as first:
        server.send_signal("SIGTERM")
    with pytest.raises(ManagedServerLifecycleError) as second:
        server.send_signal("SIGTERM")
    assert second.value is first.value
    server._process.send_signal.assert_not_called()


def test_signal_requires_managed_server():
    runner = YamlTestRunner(Mock())
    with pytest.raises(RunnerAssertionError, match="managed server"):
        runner.run_test(suite([{"signal_server": "SIGTERM"}]).tests[0])


def test_observed_exit_can_be_followed_by_restart():
    parsed = suite([
        {"signal_server": "SIGTERM"},
        {"wait_for_server_exit": {"timeout_ms": 1000, "exit_code": 0}},
        {"assert_log": {"contains": "shutdown"}},
        {"restart_server": {"reset_db": True}},
        {"run": "return 42;", "expect": {"value": 42}},
    ])
    assert parsed.tests[0].steps[3].restart_server.reset_db


def test_live_work_after_exit_still_rejected():
    with pytest.raises(ValueError, match="after"):
        suite([
            {"wait_for_server_exit": {"timeout_ms": 1000, "exit_code": 0}},
            {"signal_server": "SIGTERM"},
        ])


@pytest.mark.skipif(os.name != "posix", reason="POSIX inherited signal disposition")
def test_inherited_sighup_survives_exec(tmp_path):
    source = tmp_path / "test.db"
    source.write_text("database")
    code = "import signal; print(signal.getsignal(signal.SIGHUP) == signal.SIG_IGN)"
    import shlex

    server = ManagedServer(shlex.join([sys.executable, "-c", code]), source)
    try:
        server.start(wait_for_port=False, ignore_sighup=True)
        assert server.wait_for_exit(5000) == 0
        assert Path(server.log_path).read_text().strip() == "True"
    finally:
        server.stop()


def test_rename_confined_to_managed_directory(tmp_path):
    (tmp_path / "old.log").write_text("before rotation")
    runner = YamlTestRunner(Mock(), server_dir=str(tmp_path))
    runner.run_test(suite([{"rename_file": {"path": "old.log", "to": "rotated.log"}}]).tests[0])
    assert (tmp_path / "rotated.log").read_text() == "before rotation"
    with pytest.raises(RunnerAssertionError, match="outside|escapes"):
        runner.run_test(suite([
            {"rename_file": {"path": "rotated.log", "to": "../escaped.log"}}
        ]).tests[0])
    assert (tmp_path / "rotated.log").exists()


def test_rename_does_not_overwrite_existing_file(tmp_path):
    (tmp_path / "old").write_text("old")
    (tmp_path / "new").write_text("new")
    runner = YamlTestRunner(Mock(), server_dir=str(tmp_path))
    with pytest.raises(RunnerAssertionError, match="exists"):
        runner.run_test(suite([{"rename_file": {"path": "old", "to": "new"}}]).tests[0])
    assert (tmp_path / "new").read_text() == "new"


def test_windows_rejects_posix_delivery_without_touching_process(monkeypatch, tmp_path):
    from types import SimpleNamespace

    server = ManagedServer("unused", tmp_path / "test.db")
    server._process = Mock()
    monkeypatch.setattr("moo_conformance.server.os", SimpleNamespace(name="nt"))
    with pytest.raises(ValueError, match="POSIX"):
        server.send_signal("SIGTERM")
    server._process.send_signal.assert_not_called()


def test_windows_admission_names_posix_requirement(monkeypatch):
    from types import SimpleNamespace

    from moo_conformance.plugin import moo_config

    monkeypatch.setattr("moo_conformance.plugin.os", SimpleNamespace(name="nt"))
    config = moo_config.__wrapped__(None, None, None, None)
    assert config["posix_signals"] is None
    assert suite([{"signal_server": "SIGHUP"}]).tests[0].steps[0].signal_server == "SIGHUP"


def test_restart_after_observed_exit_reconnects_and_clears_exit_state(tmp_path):
    server = Mock()
    server.db_path = tmp_path / "original.db"
    server.process_log_offset = 12
    server.process_file_snapshot = {}
    runner = YamlTestRunner(Mock(), managed_server=server)
    runner._server_exited = True
    runner._execute_restart_server(0, "case", reset_db=True)
    assert not runner._server_exited
    assert server.restart.call_args.kwargs["db_path"] == server.db_path
    runner.transport.connect.assert_called_once()


@pytest.mark.parametrize("key,value", [("reset_db", 1), ("ignore_sighup", "yes")])
def test_restart_flags_are_boolean(key, value):
    with pytest.raises(ValueError, match="boolean"):
        suite([{"restart_server": {key: value}}])


@pytest.mark.skipif(os.name != "posix", reason="POSIX kernel signal delivery")
def test_real_child_receives_signal_at_managed_pid(tmp_path):
    import shlex
    import time

    source = tmp_path / "test.db"
    source.write_text("database")
    code = (
        "import signal,time; "
        "signal.signal(signal.SIGUSR1, lambda *args: exit(0)); "
        "print('READY', flush=True); time.sleep(30)"
    )
    server = ManagedServer(shlex.join([sys.executable, "-c", code]), source)
    try:
        server.start(wait_for_port=False)
        deadline = time.monotonic() + 5
        while "READY" not in Path(server.log_path).read_text():
            assert time.monotonic() < deadline
            time.sleep(0.01)
        server.send_signal("SIGUSR1")
        assert server.wait_for_exit(5000) == 0
    finally:
        server.stop()


def test_named_log_placeholder_and_admission(tmp_path, monkeypatch):
    from moo_conformance.plugin import moo_config

    source = tmp_path / "test.db"
    source.write_text("database")
    process = Mock()
    process.poll.return_value = None
    popen = Mock(return_value=process)
    monkeypatch.setattr("moo_conformance.server.subprocess.Popen", popen)
    server = ManagedServer("server --log {log} {db}", source)
    try:
        server.start(wait_for_port=False)
        assert popen.call_args.args[0][2] == Path(server.log_path).as_posix()
        assert moo_config.__wrapped__(None, None, None, server)["named_log_file"] == "1"
    finally:
        server.stop()
