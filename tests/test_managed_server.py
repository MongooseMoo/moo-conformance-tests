import os
import stat
import subprocess
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

import pytest

from moo_conformance.plugin import _load_login_script
from moo_conformance.runner import AssertionError as RunnerAssertionError
from moo_conformance.runner import YamlTestRunner
from moo_conformance.schema import (
    FileAssertion,
    MooTestCase,
    MooTestSuite,
    WaitForServerExit,
)
from moo_conformance.schema import (
    TestStep as MooTestStep,
)
from moo_conformance.server import ManagedServer
from moo_conformance.transport import SocketTransport


class _FakeProcess:
    def __init__(self):
        self.returncode = None
        self.stdin = BytesIO()

    def poll(self):
        return None

    def terminate(self):
        self.returncode = 0

    def wait(self, timeout=None):
        return 0


def test_restart_preserves_working_db_copy(monkeypatch, tmp_path: Path):
    baseline = tmp_path / "baseline.db"
    baseline.write_text("baseline", encoding="utf-8")

    created = []

    def fake_popen(*args, **kwargs):
        created.append((args, kwargs))
        return _FakeProcess()

    monkeypatch.setattr("moo_conformance.server.subprocess.Popen", fake_popen)
    monkeypatch.setattr(ManagedServer, "_find_free_port", lambda self: 17777)
    monkeypatch.setattr(ManagedServer, "_wait_for_port", lambda self, timeout=30.0: None)

    server = ManagedServer("fake-server {db} {port}", baseline)
    server.start()

    assert server._db_copy_path is not None
    assert server._db_copy_path.read_text(encoding="utf-8") == "baseline"

    server._db_copy_path.write_text("checkpointed", encoding="utf-8")
    server.restart()

    assert server._db_copy_path.read_text(encoding="utf-8") == "checkpointed"
    assert len(created) == 2


def test_restart_waits_before_transport_reconnect(monkeypatch):
    events = []
    transport = Mock()
    transport.current_user = "wizard"
    transport.disconnect.side_effect = lambda: events.append("disconnect")
    transport.connect.side_effect = lambda user: events.append(("connect", user))
    server = Mock()
    server.host = "localhost"
    server.port = 17777
    server.restart.side_effect = lambda down_ms=0: events.append(("restart", down_ms))
    monkeypatch.setattr(
        "moo_conformance.runner.time.sleep",
        lambda seconds: events.append(("sleep", seconds)),
    )

    runner = YamlTestRunner(transport, managed_server=server)
    runner._execute_restart_server(wait_ms=500, test_name="restart", down_ms=250)

    assert events == [
        "disconnect",
        ("restart", 250),
        ("sleep", 0.5),
        ("connect", "wizard"),
    ]


def test_wait_for_server_exit_accepts_exact_natural_exit_code():
    transport = Mock()
    server = Mock()
    server.wait_for_exit.return_value = 0
    runner = YamlTestRunner(transport, managed_server=server)
    runner._log_offset = 99

    runner._execute_wait_for_server_exit(2500, 0, "natural-exit")

    server.wait_for_exit.assert_called_once_with(2500)
    transport.disconnect.assert_called_once_with()
    server.stop.assert_not_called()
    assert runner._log_offset == 0


def test_wait_for_server_exit_fails_on_timeout_without_stopping_process():
    transport = Mock()
    server = Mock()
    server.wait_for_exit.side_effect = TimeoutError("still running")
    runner = YamlTestRunner(transport, managed_server=server)

    with pytest.raises(RunnerAssertionError, match="still running"):
        runner._execute_wait_for_server_exit(2500, 0, "hung-exit")

    server.stop.assert_not_called()
    transport.disconnect.assert_not_called()


def test_wait_for_server_exit_fails_on_wrong_exit_code():
    transport = Mock()
    server = Mock()
    server.wait_for_exit.return_value = 7
    runner = YamlTestRunner(transport, managed_server=server)

    with pytest.raises(RunnerAssertionError, match="expected exit code 0, got 7"):
        runner._execute_wait_for_server_exit(2500, 0, "wrong-exit")

    server.stop.assert_not_called()


def test_cleanup_cannot_turn_wait_for_server_exit_timeout_into_pass():
    transport = Mock()
    transport.sock = object()
    transport.current_user = "wizard"
    server = Mock()
    server.wait_for_exit.side_effect = TimeoutError("still running")
    runner = YamlTestRunner(transport, managed_server=server)
    test = MooTestCase(
        name="timeout-with-cleanup",
        permission="wizard",
        steps=[
            MooTestStep(
                wait_for_server_exit=WaitForServerExit(timeout_ms=2500, exit_code=0)
            )
        ],
        cleanup=[MooTestStep(run="return 0;")],
    )

    with pytest.raises(RunnerAssertionError, match="still running"):
        runner.run_test(test)

    transport.execute.assert_called_once_with("return 0;")
    server.stop.assert_not_called()


def test_assert_file_byte_compare_rejects_false_positive_text_match(tmp_path: Path):
    server_dir = tmp_path / "server"
    fixture_dir = tmp_path / "fixtures"
    server_dir.mkdir()
    fixture_dir.mkdir()
    (server_dir / "out.db").write_bytes(b"1 suspended tasks\nmissing locals\n")
    (fixture_dir / "expected.db").write_bytes(b"1 suspended tasks\nexact WAIF ANON locals\n")
    runner = YamlTestRunner(
        Mock(), server_dir=str(server_dir), server_db_dir=str(fixture_dir)
    )

    with pytest.raises(RunnerAssertionError, match="first mismatch offset"):
        runner._execute_assert_file(
            FileAssertion(
                path="out.db",
                contains="1 suspended tasks",
                equals_file="expected.db",
            ),
            "false-positive-task-count",
        )


@pytest.mark.parametrize(
    ("dump_text", "expected_fragment"),
    [
        (
            "1 suspended tasks\nstate local omitted\n",
            "state\n4\n2\n13\nc 0\n9\n3\n0\n-1\n.\n12\n10",
        ),
        (
            "1 suspended tasks\nstate\n4\n2\n13\nc 0\n9\n8\n0\n-1\n.\n12\n10\n",
            "state\n4\n2\n13\nc 0\n9\n3\n0\n-1\n.\n12\n10",
        ),
        (
            "1 suspended tasks\n#10\n\n0\n8\n1\n-1\n",
            "#10\n\n0\n3\n1\n-1",
        ),
    ],
    ids=["locals-missing", "waif-owner-corrupt", "anonymous-owner-corrupt"],
)
def test_assert_file_rejects_task_count_without_exact_live_root_locals(
    tmp_path: Path, dump_text: str, expected_fragment: str
):
    server_dir = tmp_path / "server"
    server_dir.mkdir()
    (server_dir / "panic.db").write_text(dump_text, encoding="utf-8")
    runner = YamlTestRunner(Mock(), server_dir=str(server_dir))
    with pytest.raises(RunnerAssertionError, match="but it was not found"):
        runner._execute_assert_file(
            FileAssertion(path="panic.db", contains=expected_fragment),
            "exact-suspended-live-roots",
        )


def test_prepare_suite_environment_switches_database_before_reconnecting(tmp_path: Path):
    default_db = tmp_path / "default.db"
    selected_db = tmp_path / "selected.db"
    default_db.write_text("default", encoding="utf-8")
    selected_db.write_text("selected", encoding="utf-8")

    events: list[object] = []
    transport = Mock()
    transport.current_user = "wizard"
    transport.sock = object()

    def disconnect() -> None:
        events.append("disconnect")
        transport.sock = None

    def connect(user: str) -> None:
        events.append(("connect", user))
        transport.sock = object()

    def restart(**kwargs) -> None:
        events.append(("restart", kwargs))

    transport.disconnect.side_effect = disconnect
    transport.connect.side_effect = connect
    server = Mock()
    server.default_db_path = default_db
    server.db_path = default_db
    server.restart.side_effect = restart

    runner = YamlTestRunner(
        transport,
        managed_server=server,
        server_db_dir=str(tmp_path),
    )
    suite = MooTestSuite(
        name="selected",
        server_db=selected_db.name,
        tests=[MooTestCase(name="case", code="return 1;")],
    )

    runner.prepare_suite_environment(suite)

    assert events == [
        "disconnect",
        ("restart", {"db_path": selected_db, "wait_for_port": True}),
        ("connect", "wizard"),
    ]


def test_prepare_exit_only_suite_does_not_connect(tmp_path: Path):
    default_db = tmp_path / "default.db"
    selected_db = tmp_path / "selected.db"
    default_db.write_text("default", encoding="utf-8")
    selected_db.write_text("selected", encoding="utf-8")

    transport = Mock()
    transport.current_user = "wizard"
    transport.sock = object()
    server = Mock()
    server.default_db_path = default_db
    server.db_path = default_db

    runner = YamlTestRunner(
        transport,
        managed_server=server,
        server_db_dir=str(tmp_path),
    )
    suite = MooTestSuite(
        name="exit-only",
        server_db=selected_db.name,
        tests=[MooTestCase(name="inspect-output")],
    )

    runner.prepare_suite_environment(suite)

    server.restart.assert_called_once_with(db_path=selected_db, wait_for_port=False)
    transport.connect.assert_not_called()


def test_command_template_supports_manifest_and_server_dir(monkeypatch, tmp_path: Path):
    baseline = tmp_path / "baseline.db"
    baseline.write_text("baseline", encoding="utf-8")

    created = []

    def fake_popen(*args, **kwargs):
        created.append((args, kwargs))
        return _FakeProcess()

    monkeypatch.setattr("moo_conformance.server.subprocess.Popen", fake_popen)
    monkeypatch.setattr(ManagedServer, "_find_free_port", lambda self: 17777)
    monkeypatch.setattr(ManagedServer, "_wait_for_port", lambda self, timeout=30.0: None)

    server = ManagedServer(
        "fake-server --db {db} --port {port} --manifest {manifest} --dir {server_dir}",
        baseline,
    )
    server.start()

    command_args = created[0][0][0]
    assert "--manifest" in command_args
    manifest_arg = command_args[command_args.index("--manifest") + 1]
    assert manifest_arg.endswith("/profile.json")
    assert "--dir" in command_args
    server_dir_arg = command_args[command_args.index("--dir") + 1]
    assert server_dir_arg == server.manifest_path.parent.as_posix()


def test_managed_server_installs_exec_fixtures(monkeypatch, tmp_path: Path):
    baseline = tmp_path / "baseline.db"
    baseline.write_text("baseline", encoding="utf-8")

    monkeypatch.setattr(
        "moo_conformance.server.subprocess.Popen", lambda *args, **kwargs: _FakeProcess()
    )
    monkeypatch.setattr(ManagedServer, "_find_free_port", lambda self: 17777)
    monkeypatch.setattr(ManagedServer, "_wait_for_port", lambda self, timeout=30.0: None)

    server = ManagedServer("fake-server {db} {port}", baseline)
    try:
        server.start()

        assert server._temp_dir is not None
        fixture = Path(server._temp_dir) / "executables" / "test_io"
        assert fixture.read_text(encoding="utf-8").startswith("#!/bin/sh")
        windows_fixture = Path(server._temp_dir) / "executables" / "test_io.bat"
        assert windows_fixture.read_text(encoding="utf-8").startswith("@echo off")
        if os.name != "nt":
            assert fixture.stat().st_mode & stat.S_IXUSR
    finally:
        server.stop()


def test_managed_server_opens_process_stdin_pipe(monkeypatch, tmp_path: Path):
    baseline = tmp_path / "baseline.db"
    baseline.write_text("baseline", encoding="utf-8")

    created = []

    def fake_popen(*args, **kwargs):
        created.append((args, kwargs))
        return _FakeProcess()

    monkeypatch.setattr("moo_conformance.server.subprocess.Popen", fake_popen)
    monkeypatch.setattr(ManagedServer, "_find_free_port", lambda self: 17777)
    monkeypatch.setattr(ManagedServer, "_wait_for_port", lambda self, timeout=30.0: None)

    server = ManagedServer("fake-server {db} {port}", baseline)
    server.start()

    assert created[0][1]["stdin"] == subprocess.PIPE


def test_managed_server_write_stdin(monkeypatch, tmp_path: Path):
    baseline = tmp_path / "baseline.db"
    baseline.write_text("baseline", encoding="utf-8")

    process = _FakeProcess()

    monkeypatch.setattr("moo_conformance.server.subprocess.Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(ManagedServer, "_find_free_port", lambda self: 17777)
    monkeypatch.setattr(ManagedServer, "_wait_for_port", lambda self, timeout=30.0: None)

    server = ManagedServer("fake-server {db} {port}", baseline)
    server.start()
    server.write_stdin("payload\n")

    assert process.stdin.getvalue() == b"payload\n"


class _FakeConfig:
    def __init__(self, env_name):
        self.env_name = env_name

    def getoption(self, name):
        if name == "--moo-login-script-env":
            return self.env_name
        raise AssertionError(name)


class _FakeRequest:
    def __init__(self, env_name):
        self.config = _FakeConfig(env_name)


def test_load_login_script_from_env(monkeypatch):
    monkeypatch.setenv("MOO_LOGIN_SCRIPT_TEST", "connect {user}\n")

    assert _load_login_script(_FakeRequest("MOO_LOGIN_SCRIPT_TEST")) == [
        "connect {user}"
    ]


def test_load_login_script_env_requires_value(monkeypatch):
    monkeypatch.delenv("MOO_LOGIN_SCRIPT_TEST", raising=False)

    with pytest.raises(pytest.UsageError):
        _load_login_script(_FakeRequest("MOO_LOGIN_SCRIPT_TEST"))


def test_socket_transport_can_skip_standard_property_initialization():
    transport = SocketTransport(ensure_standard_properties=False)

    assert transport.ensure_standard_properties is False


def test_static_login_script_rejects_user_switch():
    transport = SocketTransport(login_script=["connect FixedUser"])
    transport.current_user = "wizard"

    with pytest.raises(RuntimeError, match="static login script"):
        transport.switch_user("programmer")


def test_login_script_substitutes_requested_user(monkeypatch):
    transport = SocketTransport(login_script=["connect {user}"])
    sent = []

    monkeypatch.setattr(transport, "_send", sent.append)
    monkeypatch.setattr(transport, "_consume_login_output", lambda: None)

    transport._login("Programmer")

    assert sent == ["connect Programmer"]
