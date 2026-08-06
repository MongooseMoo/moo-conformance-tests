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
from typing import TextIO


class ManagedServerLifecycleError(RuntimeError):
    """Terminal managed-server failure with stable first-failure evidence."""

    def __init__(
        self,
        message: str,
        *,
        returncode: int | None = None,
        log_path: str | None = None,
        log_tail: str = "",
    ) -> None:
        details = [message]
        if returncode is not None:
            details.append(f"First process return code: {returncode}")
        if log_path is not None:
            details.append(f"Server log: {log_path}")
        if log_tail:
            details.append(
                f"--- server log tail ---\n{log_tail}\n--- end server log tail ---"
            )
        super().__init__("\n".join(details))
        self.returncode = returncode
        self.log_path = log_path
        self.log_tail = log_tail


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
        self._log_file: TextIO | None = None
        self._db_copy_path: Path | None = None
        self._manifest_path: Path | None = None
        self._lifecycle_failure: ManagedServerLifecycleError | None = None

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
        if self._lifecycle_failure is not None:
            raise self._lifecycle_failure

        selected_db_path = db_path if db_path is not None else self.db_path
        previous_db_copy_path = self._db_copy_path
        pending_copy_path: Path | None = None

        try:
            # Pick a port once (or use explicitly requested port).
            if self._port is None:
                if self._requested_port is not None:
                    self._port = self._requested_port
                else:
                    self._port = self._find_free_port()

            # Create temp directory and copy the selected database into it.
            created_temp_dir = self._temp_dir is None
            if created_temp_dir:
                self._temp_dir = tempfile.mkdtemp(prefix="moo_conformance_")
            if self._temp_dir is None:
                raise RuntimeError("Managed server temp directory is missing")

            if previous_db_copy_path is None or db_path is not None:
                db_copy_path = Path(self._temp_dir, selected_db_path.name)
            else:
                db_copy_path = previous_db_copy_path

            manifest_path = Path(self._temp_dir, "profile.json")
            # ToastStunt resolves file I/O paths under FILE_SUBDIR, which is "files".
            Path(self._temp_dir, "files").mkdir(exist_ok=True)
            self._install_exec_fixtures()

            # On the initial start, or when explicitly switching suites to a
            # different source database, refresh the managed working copy from the
            # selected input DB. Stage the copy first so a missing source cannot
            # overwrite the last successfully selected working database.
            if created_temp_dir or db_path is not None or not db_copy_path.exists():
                pending_copy_path = db_copy_path.with_name(db_copy_path.name + ".pending")
                pending_copy_path.unlink(missing_ok=True)
                shutil.copy2(selected_db_path, pending_copy_path)
                os.replace(pending_copy_path, db_copy_path)
                pending_copy_path = None
            db_dest = db_copy_path

            # Use forward slashes so shlex.split doesn't eat backslashes
            db_posix = db_dest.as_posix()

            # Substitute placeholders in command template
            command = self.command_template.format(
                port=self._port,
                db=db_posix,
                manifest=manifest_path.as_posix(),
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
            # without staying up long enough for a socket handshake. Their exit is
            # only a failure if a later operation requires a live transport.
            if wait_for_port:
                self._wait_for_port(timeout=30.0)

            self.db_path = selected_db_path
            self._db_copy_path = db_copy_path
            self._manifest_path = manifest_path
            if (
                previous_db_copy_path is not None
                and previous_db_copy_path != db_copy_path
                and previous_db_copy_path.exists()
            ):
                previous_db_copy_path.unlink()
        except ManagedServerLifecycleError:
            self.stop(preserve_temp=True)
            raise
        except Exception as exc:
            if pending_copy_path is not None:
                pending_copy_path.unlink(missing_ok=True)
            failure = self._record_lifecycle_failure(
                f"Managed server start failed for database {selected_db_path}: "
                f"{type(exc).__name__}: {exc}"
            )
            self.stop(preserve_temp=True)
            raise failure from exc

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
            raise RuntimeError(f"Server process exited with code {self._process.returncode}")

        self._process.stdin.write(text.encode("utf-8"))
        self._process.stdin.flush()

    def require_transport(self) -> None:
        """Fail with stable evidence if a live managed transport is unavailable."""
        if self._lifecycle_failure is not None:
            raise self._lifecycle_failure
        if self._process is None:
            raise self._record_lifecycle_failure(
                "Managed server is not running while a live transport is required"
            )
        returncode = self._process.poll()
        if returncode is not None:
            raise self._record_lifecycle_failure(
                "Managed server exited unexpectedly while a live transport is required",
                returncode=returncode,
            )

    def restart(
        self, db_path: Path | None = None, wait_for_port: bool = True, down_ms: int = 0
    ) -> None:
        """Restart the server process in-place, preserving the working database.

        down_ms keeps the process fully stopped for that long before starting
        it back up, simulating genuine offline downtime (e.g. between a
        checkpoint and the next boot) -- unlike a post-restart wait, which
        only delays after the new process is already up and reconnected.
        """
        if self._lifecycle_failure is not None:
            raise self._lifecycle_failure
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
                raise self._record_lifecycle_failure(
                    "Managed server exited before accepting connections",
                    returncode=self._process.returncode,
                )

            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1.0)
                    s.connect((self.host, self._port))
                    return  # Connection succeeded
            except (ConnectionRefusedError, OSError):
                time.sleep(0.5)

        raise self._record_lifecycle_failure(
            f"Managed server did not accept connections on port {self._port} "
            f"within {timeout}s"
        )

    def _record_lifecycle_failure(
        self,
        message: str,
        *,
        returncode: int | None = None,
    ) -> ManagedServerLifecycleError:
        """Latch and return the first root lifecycle failure."""
        if self._lifecycle_failure is None:
            if returncode is None and self._process is not None:
                returncode = self._process.poll()
            self._lifecycle_failure = ManagedServerLifecycleError(
                message,
                returncode=returncode,
                log_path=self._log_path,
                log_tail=self._read_log_tail(),
            )
        return self._lifecycle_failure

    def _read_log_tail(self, limit: int = 8192) -> str:
        if self._log_file is not None:
            try:
                self._log_file.flush()
            except OSError:
                pass
        if self._log_path is None or not os.path.exists(self._log_path):
            return ""
        try:
            with open(self._log_path, encoding="utf-8", errors="replace") as log:
                return log.read()[-limit:]
        except OSError as exc:
            return f"(could not read server log: {exc})"
