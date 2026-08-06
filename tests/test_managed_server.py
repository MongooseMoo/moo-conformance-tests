import os
import stat
import subprocess
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

import pytest

from moo_conformance.plugin import _load_login_script
from moo_conformance.runner import YamlTestRunner
from moo_conformance.schema import MooTestCase, MooTestSuite
from moo_conformance.server import ManagedServer, ManagedServerLifecycleError
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


def test_failed_database_restart_preserves_previous_runner_cache(tmp_path: Path):
    default_db = tmp_path / "default.db"
    selected_db = tmp_path / "selected.db"
    default_db.write_text("default", encoding="utf-8")
    selected_db.write_text("selected", encoding="utf-8")

    transport = Mock()
    transport.sock = object()
    server = Mock()
    server.default_db_path = default_db
    server.db_path = default_db

    def fail_restart(**_kwargs) -> None:
        server.db_path = selected_db
        raise ManagedServerLifecycleError("database copy failed")

    server.restart.side_effect = fail_restart
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

    with pytest.raises(ManagedServerLifecycleError, match="database copy failed"):
        runner.prepare_suite_environment(suite)
    with pytest.raises(ManagedServerLifecycleError, match="database copy failed"):
        runner.prepare_suite_environment(suite)

    assert runner._active_server_db_path == default_db
    assert server.restart.call_count == 2


def test_missing_database_fixture_fails_before_disconnect(tmp_path: Path):
    default_db = tmp_path / "default.db"
    default_db.write_text("default", encoding="utf-8")

    transport = Mock()
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
        name="missing",
        server_db="missing.db",
        tests=[MooTestCase(name="case", code="return 1;")],
    )

    with pytest.raises(ManagedServerLifecycleError, match="missing.db"):
        runner.prepare_suite_environment(suite)

    transport.disconnect.assert_not_called()
    server.restart.assert_not_called()


def test_cached_database_requires_live_server_before_transport_connect(tmp_path: Path):
    default_db = tmp_path / "default.db"
    default_db.write_text("default", encoding="utf-8")

    transport = Mock()
    transport.sock = None
    server = Mock()
    server.default_db_path = default_db
    server.db_path = default_db
    server.require_transport.side_effect = ManagedServerLifecycleError(
        "server exited",
        returncode=17,
        log_tail="root failure",
    )
    runner = YamlTestRunner(transport, managed_server=server)
    suite = MooTestSuite(
        name="default",
        tests=[MooTestCase(name="case", code="return 1;")],
    )

    with pytest.raises(ManagedServerLifecycleError, match="server exited"):
        runner.prepare_suite_environment(suite)

    assert runner._active_server_db_path is None
    transport.connect.assert_not_called()


def test_failed_restart_preserves_managed_server_database_state(monkeypatch, tmp_path: Path):
    baseline = tmp_path / "baseline.db"
    baseline.write_text("baseline", encoding="utf-8")

    monkeypatch.setattr(
        "moo_conformance.server.subprocess.Popen", lambda *args, **kwargs: _FakeProcess()
    )
    monkeypatch.setattr(ManagedServer, "_find_free_port", lambda self: 17777)
    monkeypatch.setattr(ManagedServer, "_wait_for_port", lambda self, timeout=30.0: None)

    server = ManagedServer("fake-server {db} {port}", baseline)
    server.start()
    original_copy = server._db_copy_path
    assert original_copy is not None

    with pytest.raises(ManagedServerLifecycleError, match="missing.db"):
        server.restart(db_path=tmp_path / "missing.db")

    assert server.db_path == baseline
    assert server._db_copy_path == original_copy
    assert original_copy.read_text(encoding="utf-8") == "baseline"


def test_expected_exit_becomes_failure_only_when_transport_is_required(
    monkeypatch, tmp_path: Path
):
    baseline = tmp_path / "baseline.db"
    baseline.write_text("baseline", encoding="utf-8")

    class _ExitedProcess(_FakeProcess):
        def __init__(self):
            super().__init__()
            self.returncode = 17

        def poll(self):
            return self.returncode

        def terminate(self):
            pass

    process = _ExitedProcess()

    def fake_popen(*args, **kwargs):
        kwargs["stdout"].write("early output\nfinal diagnostic\n")
        kwargs["stdout"].flush()
        return process

    monkeypatch.setattr("moo_conformance.server.subprocess.Popen", fake_popen)
    monkeypatch.setattr(ManagedServer, "_find_free_port", lambda self: 17777)

    server = ManagedServer("fake-server {db} {port}", baseline)
    server.start(wait_for_port=False)

    with pytest.raises(ManagedServerLifecycleError) as first:
        server.require_transport()

    process.returncode = 99
    assert server.log_path is not None
    Path(server.log_path).write_text("replacement output", encoding="utf-8")

    with pytest.raises(ManagedServerLifecycleError) as repeated:
        server.require_transport()

    assert first.value is repeated.value
    assert first.value.returncode == 17
    assert "final diagnostic" in first.value.log_tail
    assert "replacement output" not in first.value.log_tail


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
    server.require_transport.assert_not_called()
    transport.connect.assert_not_called()


def test_candidate_suite_server_db_cannot_escape_fixture_root(tmp_path: Path):
    runner = YamlTestRunner(
        Mock(),
        managed_server=Mock(),
        server_db_dir=str(tmp_path / "fixtures"),
    )
    suite = MooTestSuite(
        name="escape",
        server_db="../outside.db",
        tests=[MooTestCase(name="case", code="return 1;")],
    )

    with pytest.raises(ValueError, match="escapes the configured fixture directory"):
        runner.prepare_suite_environment(suite)


def test_candidate_suite_server_db_symlink_cannot_escape_candidate_anchor(tmp_path: Path):
    anchor = tmp_path / "candidate-data"
    fixtures = anchor / "src" / "moo_conformance" / "_db" / "startup"
    fixtures.mkdir(parents=True)
    outside = tmp_path / "outside.db"
    outside.write_text("outside", encoding="utf-8")
    linked = fixtures / "linked.db"
    try:
        linked.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    runner = YamlTestRunner(
        Mock(),
        managed_server=Mock(),
        server_db_dir=str(fixtures),
        candidate_root=str(anchor),
    )
    suite = MooTestSuite(name="linked", server_db="linked.db", tests=[])

    with pytest.raises(ValueError, match="escapes"):
        runner._resolve_suite_server_db(suite)


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
