from pathlib import Path

from moo_conformance.server import ManagedServer


class _FakeProcess:
    def __init__(self):
        self.returncode = None

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
