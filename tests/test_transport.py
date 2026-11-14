"""Socket response parsing and raw-read timing regressions."""

import socket
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from moo_conformance import transport as transport_module
from moo_conformance.moo_types import MooError
from moo_conformance.transport import SocketTransport


def raw_connection(port: int) -> transport_module.TestConnection:
    """Open a raw harness connection to a scripted server."""
    connection = transport_module.TestConnection("127.0.0.1", port)
    connection.sock = socket.create_connection(("127.0.0.1", port))
    return connection


@contextmanager
def scripted_server(script: Callable[[socket.socket], None]) -> Iterator[int]:
    """Serve one connection on localhost with `script`, yielding the port."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    stop = threading.Event()

    def serve() -> None:
        conn, _ = listener.accept()
        with conn:
            try:
                script(conn)
            except OSError:
                return  # The client closed first; that ends the script.
            stop.wait(5)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        stop.set()
        thread.join(5)
        listener.close()


def test_expected_read_waits_past_the_silence_window_for_its_output() -> None:
    def script(conn: socket.socket) -> None:
        time.sleep(0.8)
        conn.sendall(b"late line\r\n")

    with scripted_server(script) as port:
        connection = raw_connection(port)
        try:
            lines = connection.read(until=lambda lines: lines == ["late line"])
        finally:
            connection.close()

    assert lines == ["late line"]


def test_expected_read_still_collects_output_right_after_the_match() -> None:
    def script(conn: socket.socket) -> None:
        conn.sendall(b"first\r\n")
        time.sleep(0.03)
        conn.sendall(b"second\r\n")

    with scripted_server(script) as port:
        connection = raw_connection(port)
        try:
            lines = connection.read(until=lambda lines: "first" in lines)
        finally:
            connection.close()

    assert lines == ["first", "second"]


def test_expected_read_returns_what_arrived_at_the_deadline() -> None:
    def script(conn: socket.socket) -> None:
        conn.sendall(b"other\r\n")

    with scripted_server(script) as port:
        connection = raw_connection(port)
        try:
            started = time.monotonic()
            lines = connection.read(until=lambda lines: lines == ["never"], deadline=0.7)
            elapsed = time.monotonic() - started
        finally:
            connection.close()

    assert lines == ["other"]
    assert elapsed >= 0.7


def test_expectation_met_by_silence_keeps_the_silence_window() -> None:
    def script(conn: socket.socket) -> None:
        time.sleep(0.3)
        conn.sendall(b"unexpected\r\n")

    with scripted_server(script) as port:
        connection = raw_connection(port)
        try:
            lines = connection.read(until=lambda lines: lines == [])
        finally:
            connection.close()

    assert lines == ["unexpected"]


def test_read_without_expectation_still_stops_at_silence() -> None:
    def script(conn: socket.socket) -> None:
        time.sleep(0.8)
        conn.sendall(b"late line\r\n")

    with scripted_server(script) as port:
        connection = raw_connection(port)
        try:
            lines = connection.read()
        finally:
            connection.close()

    assert lines == []


def test_login_returns_at_the_connected_marker() -> None:
    def script(conn: socket.socket) -> None:
        conn.recv(4096)
        conn.sendall(b"*** Connected ***\r\n")
        # Output that keeps trickling must not hold the login open.
        for _ in range(40):
            time.sleep(0.05)
            conn.sendall(b"room description\r\n")

    with scripted_server(script) as port:
        transport = SocketTransport("127.0.0.1", port, ensure_standard_properties=False)
        transport.sock = socket.create_connection(("127.0.0.1", port))
        try:
            started = time.monotonic()
            transport._login("Wizard")
            elapsed = time.monotonic() - started
        finally:
            transport.disconnect()

    assert elapsed < 1.0


def test_toast_incorrect_number_of_arguments_traceback_is_e_args() -> None:
    response = (
        "#-1:Input to EVAL (this == #-1), line 65:  Incorrect number of arguments "
        "(expected 1; got 0)\n"
        "... called from built-in function eval()\n"
        "... called from #58:eval_cmd_string, line 20\n"
        "... called from #58:eval*-d @eval, line 14\n"
        "(End of traceback)"
    )

    result = SocketTransport()._parse_response(response)

    assert result.success is False
    assert result.error is MooError.E_ARGS
    assert result.error_message is None


def test_toast_eval_separates_notifications_from_the_result() -> None:
    result = SocketTransport()._parse_response("first notice\nsecond notice\n=> {1, 2}")

    assert result.success is True
    assert result.value == [1, 2]
    assert result.notifications == [
        {"message": "first notice"},
        {"message": "second notice"},
    ]


def test_toast_eval_separates_notifications_from_a_traceback() -> None:
    response = """notice before failure
#-1:Input to EVAL (this == #-1), line 1:  Division by zero
(End of traceback)"""

    result = SocketTransport()._parse_response(response)

    assert result.success is False
    assert result.error is MooError.E_DIV
    assert result.notifications == [{"message": "notice before failure"}]


def test_wrapped_eval_separates_notifications_from_the_result() -> None:
    result = SocketTransport()._parse_response("wrapped notice\n{1, 7}")

    assert result.success is True
    assert result.value == 7
    assert result.notifications == [{"message": "wrapped notice"}]
