from pathlib import Path
from io import BytesIO
import os
import subprocess
import stat
from unittest.mock import Mock

import pytest

from moo_conformance.plugin import _load_login_script
from moo_conformance.runner import YamlTestRunner
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

    monkeypatch.setattr("moo_conformance.server.subprocess.Popen", lambda *args, **kwargs: _FakeProcess())
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
