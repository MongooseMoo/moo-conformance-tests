"""--restart-server-command boots a second engine from the database the first wrote."""
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from moo_conformance.conditions import keeps_database_across_restart
from moo_conformance.moo_types import MooError
from moo_conformance.plugin import RestartEngine
from moo_conformance.runner import YamlTestRunner
from moo_conformance.schema import MooTestCase, MooTestSuite, Requirements, validate_test_suite
from moo_conformance.server import (
    ManagedServer,
    ManagedServerLifecycleError,
    RestartCommandError,
)
from moo_conformance.test_conformance import (
    _reset_capability_caches_for_tests,
)
from moo_conformance.test_conformance import (
    test_yaml_conformance as run_yaml_case,
)
from moo_conformance.transport import ExecutionResult

pytest_plugins = ("pytester",)


class _FakeProcess:
    returncode = None

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = 0

    def wait(self, timeout=None):
        if self.returncode is None:
            raise subprocess.TimeoutExpired("fake-server", timeout)
        return self.returncode


@pytest.fixture
def launches(monkeypatch):
    """Record the executable of every launch instead of starting a process."""
    started: list[str] = []

    def fake_popen(argv, **kwargs):
        started.append(argv[0])
        return _FakeProcess()

    monkeypatch.setattr("moo_conformance.server.subprocess.Popen", fake_popen)
    monkeypatch.setattr(ManagedServer, "_find_free_port", lambda self: 17777)
    monkeypatch.setattr(ManagedServer, "_wait_for_port", lambda self, timeout=30.0: None)
    monkeypatch.setattr(ManagedServer, "_wait_for_port_release", lambda self, timeout=30.0: None)
    return started


def _two_engine_server(tmp_path: Path) -> ManagedServer:
    baseline = tmp_path / "baseline.db"
    baseline.write_text("baseline", encoding="utf-8")
    return ManagedServer(
        "engine-a {db} {port}", baseline, restart_command_template="engine-b {db} {port}"
    )


def test_kept_database_restart_uses_restart_command_on_the_written_database(
    launches, tmp_path: Path
):
    server = _two_engine_server(tmp_path)
    try:
        server.start()
        assert launches == ["engine-a"]
        assert server.on_restart_command is False
        assert server._db_copy_path is not None
        server._db_copy_path.write_text("written by engine a", encoding="utf-8")

        server.restart()

        assert launches == ["engine-a", "engine-b"]
        assert server.on_restart_command is True
        assert server._db_copy_path.read_text(encoding="utf-8") == "written by engine a"
    finally:
        server.stop()


def test_later_kept_database_restarts_stay_on_restart_command(launches, tmp_path: Path):
    server = _two_engine_server(tmp_path)
    try:
        server.start()
        server.restart()
        server.restart(arguments=["--flag"])
        assert launches == ["engine-a", "engine-b", "engine-b"]
        assert server.on_restart_command is True
    finally:
        server.stop()


def test_fresh_database_restart_returns_to_server_command(launches, tmp_path: Path):
    server = _two_engine_server(tmp_path)
    try:
        server.start()
        server.restart()
        assert server._db_copy_path is not None
        server._db_copy_path.write_text("written by engine b", encoding="utf-8")

        server.restart(db_path=server.default_db_path)

        assert launches == ["engine-a", "engine-b", "engine-a"]
        assert server.on_restart_command is False
        assert server._db_copy_path.read_text(encoding="utf-8") == "baseline"
    finally:
        server.stop()


def test_without_restart_command_every_launch_uses_server_command(launches, tmp_path: Path):
    baseline = tmp_path / "baseline.db"
    baseline.write_text("baseline", encoding="utf-8")
    server = ManagedServer("engine-a {db} {port}", baseline)
    try:
        server.start()
        server.restart()
        assert launches == ["engine-a", "engine-a"]
        assert server.on_restart_command is False
    finally:
        server.stop()


def test_restart_command_that_does_not_come_up_fails_without_ending_the_session(
    launches, monkeypatch, tmp_path: Path
):
    server = _two_engine_server(tmp_path)

    def wait_for_port(self, timeout=30.0):
        if self.on_restart_command:
            raise self._record_lifecycle_failure(
                "Managed server exited before accepting connections", returncode=1
            )

    monkeypatch.setattr(ManagedServer, "_wait_for_port", wait_for_port)
    try:
        server.start()
        with pytest.raises(RestartCommandError, match="exited before accepting connections"):
            server.restart()
        assert server.on_restart_command is True

        # Not latched: the next fresh launch starts the --server-command engine.
        server.restart(db_path=server.default_db_path)
        assert launches == ["engine-a", "engine-b", "engine-a"]
        assert server.on_restart_command is False
    finally:
        server.stop()


def test_server_command_that_does_not_come_up_still_latches(launches, monkeypatch, tmp_path: Path):
    server = _two_engine_server(tmp_path)

    def wait_for_port(self, timeout=30.0):
        raise self._record_lifecycle_failure("Managed server exited before accepting connections")

    monkeypatch.setattr(ManagedServer, "_wait_for_port", wait_for_port)
    try:
        with pytest.raises(ManagedServerLifecycleError):
            server.start()
        with pytest.raises(ManagedServerLifecycleError):
            server.start()
        assert launches == ["engine-a"]
    finally:
        server.stop()


def _runner_on(server, tmp_path: Path) -> tuple[YamlTestRunner, Mock]:
    database = tmp_path / "default.db"
    database.write_text("default", encoding="utf-8")
    server.default_db_path = database
    server.db_path = database
    server.process_log_offset = 0
    server.process_file_snapshot = {}
    transport = Mock()
    transport.current_user = "wizard"
    transport.sock = object()
    runner = YamlTestRunner(transport, managed_server=server)
    runner._active_server_db_path = database
    return runner, transport


def test_next_test_leaves_restart_command_for_a_fresh_database(tmp_path: Path):
    server = Mock()
    server.on_restart_command = True
    runner, transport = _runner_on(server, tmp_path)
    runner._suites_setup_done.add("earlier")
    suite = MooTestSuite(name="next", tests=[MooTestCase(name="case", code="return 1;")])

    runner._ensure_suite_server_db(suite)

    transport.disconnect.assert_called_once_with()
    server.restart.assert_called_once_with(db_path=server.default_db_path, wait_for_port=True)
    assert runner._suites_setup_done == set()
    assert runner._process_log_boundary_pending is True


def test_next_test_keeps_server_command_engine_running(tmp_path: Path):
    server = Mock()
    server.on_restart_command = False
    runner, transport = _runner_on(server, tmp_path)
    runner._suites_setup_done.add("earlier")
    suite = MooTestSuite(name="next", tests=[MooTestCase(name="case", code="return 1;")])

    runner._ensure_suite_server_db(suite)

    server.restart.assert_not_called()
    transport.disconnect.assert_not_called()
    assert runner._suites_setup_done == {"earlier"}


def test_failed_restart_command_skips_cleanup_and_next_test_relaunches_fresh(tmp_path: Path):
    server = Mock()
    server.on_restart_command = False
    runner, transport = _runner_on(server, tmp_path)
    suite = validate_test_suite({"name": "crossing", "tests": [{
        "name": "restart",
        "steps": [{"restart_server": {}}, {"run": "return 1;"}],
        "cleanup": [{"run": "return 2;"}],
    }]})

    def fail_restart(**kwargs):
        server.on_restart_command = True
        raise RestartCommandError("native builtin continuation requires conversion")

    server.restart.side_effect = fail_restart
    with pytest.raises(RestartCommandError, match="requires conversion"):
        runner._execute_steps(suite.tests[0])
    transport.execute.assert_not_called()
    transport.connect.assert_not_called()

    server.restart.side_effect = None
    server.restart.reset_mock()
    runner._ensure_suite_server_db(suite)
    server.restart.assert_called_once_with(db_path=server.default_db_path, wait_for_port=True)
    transport.connect.assert_called_once_with("wizard")


def test_restart_command_exit_after_opening_port_carries_the_server_log(launches, tmp_path: Path):
    server = _two_engine_server(tmp_path)
    try:
        server.start()
        assert server.restart_command_exit(timeout=0) is None  # --server-command launch

        server.restart()
        assert server.restart_command_exit(timeout=0) is None  # still running

        assert server._log_file is not None and server._process is not None
        server._log_file.write("native builtin continuation requires conversion\n")
        server._process.returncode = 1
        failure = server.restart_command_exit(timeout=0)

        assert isinstance(failure, RestartCommandError)
        assert "exited after opening its port" in str(failure)
        assert "First process return code: 1" in str(failure)
        assert "native builtin continuation requires conversion" in str(failure)
    finally:
        server.stop()


def test_reconnect_failure_reports_restart_command_exit_and_skips_cleanup(tmp_path: Path):
    server = Mock()
    server.on_restart_command = True
    server.restart_command_exit.return_value = RestartCommandError("exited: requires conversion")
    runner, transport = _runner_on(server, tmp_path)
    transport.connect.side_effect = ConnectionRefusedError("refused")
    suite = validate_test_suite({"name": "crossing", "tests": [{
        "name": "restart",
        "steps": [{"restart_server": {}}],
        "cleanup": [{"run": "return 2;"}],
    }]})

    with pytest.raises(RestartCommandError, match="requires conversion"):
        runner._execute_steps(suite.tests[0])

    transport.execute.assert_not_called()
    assert runner._server_exited is True


def test_reconnect_failure_on_a_running_server_is_reported_unchanged(tmp_path: Path):
    server = Mock()
    server.restart_command_exit.return_value = None
    runner, transport = _runner_on(server, tmp_path)
    transport.connect.side_effect = ConnectionRefusedError("refused")

    with pytest.raises(ConnectionRefusedError, match="refused"):
        runner._execute_restart_server(0, "restart")

    assert runner._server_exited is False


@pytest.mark.parametrize(
    ("steps", "expected"),
    [
        ([{"restart_server": {}}], True),
        ([{"restart_server": {"checkpoint_timeout_ms": 5000}}], True),
        ([{"restart_server": {"reset_db": True}}], False),
        ([{"restart_server": {"reset_db": True}}, {"restart_server": {"wait_ms": 1}}], True),
        ([{"run": "return 1;"}], False),
    ],
)
def test_keeps_database_across_restart(steps, expected):
    suite = validate_test_suite({"name": "s", "tests": [{"name": "t", "steps": steps}]})
    assert keeps_database_across_restart(suite.tests[0]) is expected


class _ProbeTransport:
    """Answer function_info() probes from a fixed set of builtins."""

    def __init__(self, *builtins: str):
        self.builtins = builtins
        self.executed: list[str] = []

    def switch_user(self, user: str) -> None:
        pass

    def execute(self, code: str) -> ExecutionResult:
        self.executed.append(code)
        if any(f'"{name}"' in code for name in self.builtins):
            return ExecutionResult(True, value=[])
        return ExecutionResult(False, error=MooError.E_INVARG)


def _two_engine_case(restart_builtins: tuple[str, ...], steps: list[dict]):
    _reset_capability_caches_for_tests()
    events: list[str] = []
    runner = SimpleNamespace(
        transport=_ProbeTransport("only_here"),
        restart_engine=RestartEngine(
            transport=_ProbeTransport(*restart_builtins), profile_features={}, named_log_file=None
        ),
        prepare_suite_environment=lambda _suite: None,
        run_suite_setup=lambda _suite: None,
        run_test=lambda _test: events.append("ran"),
    )
    suite = validate_test_suite({
        "name": "gated",
        "requires": {"builtins": ["only_here"]},
        "tests": [{"name": "case", "steps": steps}],
    })
    return runner, suite, events


def test_kept_restart_test_is_skipped_when_restart_engine_lacks_a_requirement():
    runner, suite, events = _two_engine_case((), [{"restart_server": {}}])
    try:
        with pytest.raises(pytest.skip.Exception, match="^Requires builtin: only_here$"):
            run_yaml_case(runner, (suite, suite.tests[0]), {"managed_server": "1"}, {})
        assert events == []
        # Each engine answered from its own probe; neither cache served the other.
        assert len(runner.transport.executed) == 1
        assert len(runner.restart_engine.transport.executed) == 1
    finally:
        _reset_capability_caches_for_tests()


def test_kept_restart_test_runs_when_both_engines_meet_the_requirement():
    runner, suite, events = _two_engine_case(("only_here",), [{"restart_server": {}}])
    try:
        run_yaml_case(runner, (suite, suite.tests[0]), {"managed_server": "1"}, {})
        run_yaml_case(runner, (suite, suite.tests[0]), {"managed_server": "1"}, {})
        assert events == ["ran", "ran"]
        # The second run is answered from each engine's own cache.
        assert len(runner.transport.executed) == 1
        assert len(runner.restart_engine.transport.executed) == 1
    finally:
        _reset_capability_caches_for_tests()


def test_test_that_never_reaches_the_restart_engine_ignores_its_capabilities():
    runner, suite, events = _two_engine_case((), [{"restart_server": {"reset_db": True}}])
    try:
        run_yaml_case(runner, (suite, suite.tests[0]), {"managed_server": "1"}, {})
        assert events == ["ran"]
        assert runner.restart_engine.transport.executed == []
    finally:
        _reset_capability_caches_for_tests()


def test_kept_restart_test_requires_named_log_from_the_restart_command_too():
    _reset_capability_caches_for_tests()
    runner = SimpleNamespace(
        transport=_ProbeTransport(),
        restart_engine=RestartEngine(
            transport=_ProbeTransport(), profile_features={}, named_log_file=None
        ),
        prepare_suite_environment=lambda _suite: None,
    )
    suite = MooTestSuite(name="log", requires=Requirements(config=["named_log_file"]))
    test = validate_test_suite(
        {"name": "s", "tests": [{"name": "t", "steps": [{"restart_server": {}}]}]}
    ).tests[0]
    with pytest.raises(pytest.skip.Exception, match="Requires config 'named_log_file'"):
        run_yaml_case(runner, (suite, test), {"managed_server": "1", "named_log_file": "1"}, {})


def _write_suites(pytester, test_body: str):
    """Point the plugin at one three-test suite; return the restore callback."""
    from moo_conformance import plugin

    suites = pytester.path / "suites"
    suites.mkdir()
    (suites / "restarts.yaml").write_text(
        """name: restarts
tests:
  - name: keeps
    steps:
      - restart_server: {}
  - name: resets
    steps:
      - restart_server: {reset_db: true}
  - name: plain
    code: "1"
    expect:
      value: 1
""",
        encoding="utf-8",
    )
    pytester.makeconftest(
        "\n".join(
            [
                "from pathlib import Path",
                "from moo_conformance import plugin",
                f"plugin.get_tests_dir = lambda: Path({str(suites)!r})",
            ]
        )
    )
    pytester.makepyfile(test_body)
    original = plugin.get_tests_dir
    return lambda: setattr(plugin, "get_tests_dir", original)


def test_kept_db_restart_marker_selects_only_kept_database_restart_tests(pytester):
    restore = _write_suites(pytester, "def test_selected(yaml_test_case): pass")
    try:
        result = pytester.runpytest("-v", "--strict-markers", "-m", "kept_db_restart")
    finally:
        restore()
    result.assert_outcomes(passed=1, deselected=2)
    result.stdout.fnmatch_lines(["*restarts.yaml::keeps*PASSED*"])


def test_restart_server_command_requires_server_command(pytester):
    restore = _write_suites(pytester, "def test_selected(yaml_test_case): pass")
    try:
        result = pytester.runpytest("-q", "--restart-server-command", "engine-b {db} {port}")
    finally:
        restore()
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*--restart-server-command requires --server-command*"])


def test_restart_engine_fixture_probes_restart_command_on_its_own_fresh_database(
    launches, monkeypatch, pytester, tmp_path: Path
):
    from moo_conformance import plugin

    connected = []

    class FakeTransport:
        def __init__(self, host, port, **kwargs):
            pass

        def connect(self, user):
            connected.append(user)

        def disconnect(self):
            connected.append("disconnect")

    monkeypatch.setattr(plugin, "SocketTransport", FakeTransport)
    database = tmp_path / "default.db"
    database.write_text("default", encoding="utf-8")
    restore = _write_suites(
        pytester,
        """
        def test_probe_target(restart_engine, managed_server):
            assert restart_engine.named_log_file == "1"
            assert restart_engine.profile_features == {}
            assert managed_server.on_restart_command is False
        """,
    )
    try:
        result = pytester.runpytest(
            "-q",
            "--server-command", "engine-a {db} {port}",
            "--restart-server-command", "engine-b --log {log} {db} {port}",
            "--server-db", str(database),
        )
    finally:
        restore()
    result.assert_outcomes(passed=1)
    assert launches == ["engine-a", "engine-b"]
    assert connected == ["wizard", "disconnect"]
