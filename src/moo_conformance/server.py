"""Managed MOO server lifecycle for conformance testing.

Starts and stops a MOO server subprocess automatically when
--server-command is provided. When omitted, tests use an
externally managed server (the existing behavior).
"""

import os
import shlex
import shutil
import socket
import stat
import subprocess
import tempfile
import time
from importlib import resources
from pathlib import Path


class ManagedServer:
    """Manages a MOO server subprocess for the duration of a test session."""

    def __init__(
        self,
        command_template: str,
        db_path: Path,
        port: int | None = None,
        host: str = "localhost",
    ):
        self.command_template = command_template
        self._default_db_path = db_path
        self.db_path = db_path
        self.host = host
        self._requested_port = port
        self._port: int | None = None
        self._process: subprocess.Popen | None = None
        self._temp_dir: str | None = None
        self._log_path: str | None = None
        self._log_file = None
        self._db_copy_path: Path | None = None
        self._manifest_path: Path | None = None

    @property
    def port(self) -> int:
        if self._port is None:
            raise RuntimeError("Server not started")
        return self._port

    @property
    def log_path(self) -> str | None:
        return self._log_path

    @property
    def default_db_path(self) -> Path:
        return self._default_db_path

    @property
    def manifest_path(self) -> Path:
        if self._manifest_path is None:
            raise RuntimeError("Server not started")
        return self._manifest_path

    def start(self, db_path: Path | None = None, wait_for_port: bool = True) -> None:
        """Start the server subprocess.

        When wait_for_port is False, the process is started and may exit on its
        own after startup repair / dump processing without ever accepting a
        socket connection.
        """
        if db_path is not None:
            self.db_path = db_path

        # Pick a port once (or use explicitly requested port).
        if self._port is None:
            if self._requested_port is not None:
                self._port = self._requested_port
            else:
                self._port = self._find_free_port()

        # Create temp directory and copy the selected database into it.
        if self._temp_dir is None:
            self._temp_dir = tempfile.mkdtemp(prefix="moo_conformance_")
            self._db_copy_path = Path(self._temp_dir, self.db_path.name)
        else:
            if self._db_copy_path is None:
                raise RuntimeError("Managed server temp directory exists but DB copy path is missing")
            if db_path is not None:
                new_db_copy_path = Path(self._temp_dir, self.db_path.name)
                if new_db_copy_path != self._db_copy_path and self._db_copy_path.exists():
                    try:
                        self._db_copy_path.unlink()
                    except OSError:
                        pass
                self._db_copy_path = new_db_copy_path

        if self._db_copy_path is None:
            raise RuntimeError("Managed server DB copy path is missing")
        self._manifest_path = Path(self._temp_dir, "profile.json")
        # ToastStunt resolves file I/O paths under FILE_SUBDIR, which is "files".
        Path(self._temp_dir, "files").mkdir(exist_ok=True)
        self._install_exec_fixtures()

        # On the initial start, or when explicitly switching suites to a
        # different source database, refresh the managed working copy from the
        # selected input DB. A plain restart should preserve the current working
        # copy so restart-based persistence tests observe the checkpointed state.
        if self._temp_dir is None or db_path is not None or not self._db_copy_path.exists():
            shutil.copy2(self.db_path, self._db_copy_path)
        db_dest = self._db_copy_path

        # Use forward slashes so shlex.split doesn't eat backslashes
        db_posix = db_dest.as_posix()

        # Substitute placeholders in command template
        command = self.command_template.format(
            port=self._port,
            db=db_posix,
            manifest=self._manifest_path.as_posix(),
            server_dir=Path(self._temp_dir).as_posix(),
        )

        # Open log file for server output
        self._log_path = os.path.join(self._temp_dir, "server.log")
        self._log_file = open(self._log_path, "a")

        # Start server process
        self._process = subprocess.Popen(
            shlex.split(command),
            stdin=subprocess.PIPE,
            stdout=self._log_file,
            stderr=subprocess.STDOUT,
            cwd=self._temp_dir,
        )

        # Some canned DB fixtures are intended to start, repair, dump, and exit
        # without staying up long enough for a socket handshake.
        if wait_for_port:
            self._wait_for_port(timeout=30.0)

    def stop(self, preserve_temp: bool = False) -> None:
        """Stop the server and optionally clean up temp directory."""
        if self._process is not None:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
            except OSError:
                try:
                    self._process.wait(timeout=5)
                except Exception:
                    pass
            self._process = None

        if self._log_file is not None:
            self._log_file.close()
            self._log_file = None

        if not preserve_temp and self._temp_dir is not None:
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None
            self._db_copy_path = None
            self._manifest_path = None

    def write_stdin(self, text: str) -> None:
        """Write text to the managed server process stdin."""
        if self._process is None:
            raise RuntimeError("Server not started")
        if self._process.stdin is None:
            raise RuntimeError("Server process stdin is not writable")
        if self._process.poll() is not None:
            raise RuntimeError(
                f"Server process exited with code {self._process.returncode}"
            )

        self._process.stdin.write(text.encode("utf-8"))
        self._process.stdin.flush()

    def restart(self, db_path: Path | None = None, wait_for_port: bool = True, down_ms: int = 0) -> None:
        """Restart the server process in-place, preserving the working database.

        down_ms keeps the process fully stopped for that long before starting
        it back up, simulating genuine offline downtime (e.g. between a
        checkpoint and the next boot) -- unlike a post-restart wait, which
        only delays after the new process is already up and reconnected.
        """
        self.stop(preserve_temp=True)
        if down_ms > 0:
            time.sleep(down_ms / 1000.0)
        if db_path is None:
            self._sync_checkpoint_output()
            self.start(wait_for_port=wait_for_port)
        else:
            self.start(db_path=db_path, wait_for_port=wait_for_port)

    def _sync_checkpoint_output(self) -> None:
        """Adopt common external checkpoint outputs back into the input DB path.

        Some servers (e.g., ToastStunt) write checkpoints to a separate output
        file (often `{db}.out` or `{db}.new`) rather than replacing the input DB in-place.
        For restart-based persistence tests, promote the newest known output
        file to the managed input DB path if present.
        """
        if self._db_copy_path is None:
            return

        src = self._db_copy_path
        candidates = [
            Path(str(src) + ".out"),
            Path(str(src) + ".new"),
            src.with_suffix(src.suffix + ".new"),
            src.with_suffix(".out.db"),
            src.with_suffix(".new.db"),
        ]

        best: Path | None = None
        best_mtime = -1.0
        for cand in candidates:
            if not cand.exists() or cand.is_dir():
                continue
            mtime = cand.stat().st_mtime
            if mtime > best_mtime:
                best = cand
                best_mtime = mtime

        if best is not None:
            shutil.copy2(best, src)

    def _find_free_port(self) -> int:
        """Find an available TCP port."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            return s.getsockname()[1]

    def _install_exec_fixtures(self) -> None:
        """Install packaged exec() fixtures into the managed server directory."""
        if self._temp_dir is None:
            raise RuntimeError("Managed server temp directory is missing")

        fixture_root = resources.files("moo_conformance") / "_exec_fixtures"
        if not fixture_root.is_dir():
            return

        exec_dir = Path(self._temp_dir, "executables")
        exec_dir.mkdir(exist_ok=True)

        for fixture in fixture_root.iterdir():
            if not fixture.is_file():
                continue
            target = exec_dir / fixture.name
            with fixture.open("rb") as source, target.open("wb") as dest:
                shutil.copyfileobj(source, dest)
            target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    def _wait_for_port(self, timeout: float = 30.0) -> None:
        """Poll until the server port accepts connections."""
        assert self._port is not None
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            # Check if process died
            if self._process is not None and self._process.poll() is not None:
                # Read log before raising so it's in the error message
                log_content = ""
                if self._log_path and os.path.exists(self._log_path):
                    try:
                        with open(self._log_path) as f:
                            log_content = f.read()
                    except OSError:
                        log_content = "(could not read log)"
                raise RuntimeError(
                    f"Server process exited with code {self._process.returncode} "
                    f"before accepting connections. Log: {self._log_path}\n"
                    f"--- server output ---\n{log_content}\n--- end server output ---"
                )

            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1.0)
                    s.connect((self.host, self._port))
                    return  # Connection succeeded
            except (ConnectionRefusedError, OSError):
                time.sleep(0.5)

        raise RuntimeError(
            f"Server did not start accepting connections on port {self._port} "
            f"within {timeout}s. Log: {self._log_path}"
        )
