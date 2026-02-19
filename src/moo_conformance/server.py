"""Managed MOO server lifecycle for conformance testing.

Starts and stops a MOO server subprocess automatically when
--server-command is provided. When omitted, tests use an
externally managed server (the existing behavior).
"""

import os
import shlex
import shutil
import socket
import subprocess
import tempfile
import time
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
        self.db_path = db_path
        self.host = host
        self._requested_port = port
        self._port: int | None = None
        self._process: subprocess.Popen | None = None
        self._temp_dir: str | None = None
        self._log_path: str | None = None
        self._log_file = None

    @property
    def port(self) -> int:
        if self._port is None:
            raise RuntimeError("Server not started")
        return self._port

    @property
    def log_path(self) -> str | None:
        return self._log_path

    def start(self) -> None:
        """Start the server subprocess and wait for it to accept connections."""
        # Pick a port
        if self._requested_port is not None:
            self._port = self._requested_port
        else:
            self._port = self._find_free_port()

        # Create temp directory and copy database into it
        self._temp_dir = tempfile.mkdtemp(prefix="moo_conformance_")
        db_dest = Path(self._temp_dir, self.db_path.name)
        shutil.copy2(self.db_path, db_dest)

        # Use forward slashes so shlex.split doesn't eat backslashes
        db_posix = db_dest.as_posix()

        # Substitute placeholders in command template
        command = self.command_template.format(
            port=self._port,
            db=db_posix,
        )

        # Open log file for server output
        self._log_path = os.path.join(self._temp_dir, "server.log")
        self._log_file = open(self._log_path, "w")

        # Start server process
        self._process = subprocess.Popen(
            shlex.split(command),
            stdout=self._log_file,
            stderr=subprocess.STDOUT,
            cwd=self._temp_dir,
        )

        # Wait for the server to accept connections
        self._wait_for_port(timeout=30.0)

    def stop(self) -> None:
        """Stop the server and clean up temp directory."""
        if self._process is not None:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
            self._process = None

        if self._log_file is not None:
            self._log_file.close()
            self._log_file = None

        if self._temp_dir is not None:
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None

    def _find_free_port(self) -> int:
        """Find an available TCP port."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            return s.getsockname()[1]

    def _wait_for_port(self, timeout: float = 30.0) -> None:
        """Poll until the server port accepts connections."""
        assert self._port is not None
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            # Check if process died
            if self._process is not None and self._process.poll() is not None:
                raise RuntimeError(
                    f"Server process exited with code {self._process.returncode} "
                    f"before accepting connections. Log: {self._log_path}"
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
