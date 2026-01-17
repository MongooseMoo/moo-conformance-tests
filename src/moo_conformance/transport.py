"""Transport abstraction for executing MOO code.

Provides a socket-based transport for connecting to running MOO servers
and executing code for conformance testing.

Usage:
    with SocketTransport("localhost", 7777) as transport:
        transport.connect("wizard")
        result = transport.execute("1 + 1")
        print(result.value)  # 2
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
import re
import socket

from .moo_types import MooError, ERROR_CODES, is_error_value


@dataclass
class ExecutionResult:
    """Result from executing MOO code."""
    success: bool
    value: Any = None
    error: MooError | None = None
    error_message: str | None = None
    notifications: list[dict] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)


class MooTransport(ABC):
    """Abstract transport for executing MOO code.

    Implementations connect to a MOO server (via socket, in-process, etc.)
    and execute code, returning results.
    """

    @abstractmethod
    def connect(self, user: str = "programmer") -> None:
        """Connect/authenticate as the given user.

        Args:
            user: User level to authenticate as ("wizard", "programmer", etc.)
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the MOO."""
        pass

    @abstractmethod
    def execute(self, code: str) -> ExecutionResult:
        """Execute MOO code and return result.

        Args:
            code: MOO code to execute (expression or statement)

        Returns:
            ExecutionResult with value or error
        """
        pass

    def execute_as(self, user: str | int, code: str) -> ExecutionResult:
        """Execute MOO code as a specific user.

        For multi-user testing. Default implementation raises NotImplementedError.

        Args:
            user: User name or object number
            code: MOO code to execute

        Returns:
            ExecutionResult with value or error
        """
        raise NotImplementedError("execute_as() not supported by this transport")

    def send_command(self, command: str) -> list[str]:
        """Send a raw command (not wrapped as eval) and capture output.

        For testing command parsing and verb dispatch. The command is sent
        as-is without any `;` prefix, so it goes through the normal command
        parser.

        Args:
            command: Raw command text (e.g., "put ball in box")

        Returns:
            List of output lines (notify() messages) from command execution
        """
        raise NotImplementedError("send_command() not supported by this transport")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


class SocketTransport(MooTransport):
    """TCP socket transport for remote MOO server.

    Connects to a running MOO server and executes code via commands.
    This is the primary transport for conformance testing against any
    MOO implementation.

    Example:
        # Start your MOO server on port 7777
        transport = SocketTransport("localhost", 7777)
        transport.connect("wizard")
        result = transport.execute("1 + 1")
        assert result.value == 2
    """

    # Class-level flag to track if standard properties have been set up
    _properties_initialized = False

    def __init__(self, host: str = "localhost", port: int = 7777):
        self.host = host
        self.port = port
        self.sock: socket.socket | None = None
        self.current_user = "programmer"

    def connect(self, user: str = "programmer") -> None:
        """Connect to MOO server and authenticate."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(3)  # 3 second timeout to avoid hanging forever
        self.sock.connect((self.host, self.port))
        self.current_user = user

        # Map user names to actual database users
        # Toast/toastcore has both "Wizard" and "Programmer" players
        # Note: player name is case-sensitive - must be "Wizard" not "wizard"
        user_map = {
            "programmer": "Programmer",
            "wizard": "Wizard",
        }
        login_user = user_map.get(user, user)

        # Send connect command
        self._send(f"connect {login_user}")

        # Consume initial login output (welcome message, room description, etc.)
        # This output is sent before PREFIX/SUFFIX are set, so it has no markers.
        self._consume_login_output()

        # Set up PREFIX/SUFFIX for response parsing
        self._send("PREFIX -=!-^-!=-")
        self._send("SUFFIX -=!-v-!=-")

        # Ensure standard properties exist (only once per test session)
        if not SocketTransport._properties_initialized:
            self._ensure_standard_properties()
            SocketTransport._properties_initialized = True

    def _consume_login_output(self) -> None:
        """Consume and discard initial login output from MOO server.

        After 'connect', the server sends welcome messages, room descriptions,
        and other login output. This must be consumed before PREFIX/SUFFIX
        commands are sent, otherwise the unmarked output will interfere with
        subsequent response parsing.
        """
        if self.sock is None:
            return

        # Wait for login to complete by looking for "*** Connected ***" marker
        # Use a longer timeout since login can take time
        old_timeout = self.sock.gettimeout()
        self.sock.settimeout(2.0)  # 2 second timeout for login

        buffer = b""
        connected = False
        try:
            while True:
                try:
                    data = self.sock.recv(4096)
                    if not data:
                        break
                    # Strip telnet commands
                    clean_data = self._strip_telnet_commands(data)
                    buffer += clean_data

                    # Check for connection success marker
                    if b'*** Connected ***' in buffer or b'Connected' in buffer:
                        connected = True

                    # Once connected, drain remaining output with shorter timeout
                    if connected:
                        self.sock.settimeout(0.1)

                except socket.timeout:
                    # Timeout - either login failed or we've drained all output
                    break
        finally:
            self.sock.settimeout(old_timeout)

    def _ensure_standard_properties(self) -> None:
        """Ensure #0 has standard MOO properties like $object, $anonymous, $sysobj, $anon.

        Uses add_property() to add missing properties. Errors are silently ignored
        since properties may already exist.
        """
        # Properties to add: (name, value)
        properties = [
            ("object", "#1"),      # Root object class
            ("anonymous", "#5"),   # Anonymous class parent
            ("anon", "#5"),        # Alias for anonymous
            ("sysobj", "#0"),      # System object itself
            ("nothing", "#-1"),    # Represents no object
        ]

        for name, value in properties:
            # Try to add property, ignore errors (property may exist)
            # Use {#0, "rc"} for standard read perms
            cmd = f'; try add_property(#0, "{name}", {value}, {{#0, "rc"}}); except (ANY) return 0; endtry'
            self._send(cmd)
            # Read and discard response
            self._receive()

    def switch_user(self, user: str = "programmer") -> None:
        """Switch to a different user by closing and reopening connection.

        Toast doesn't support @quit, so we must close the socket and reconnect.
        """
        if self.current_user == user:
            return  # Already this user

        # Map user names to database users
        user_map = {
            "programmer": "Programmer",
            "wizard": "Wizard",
        }
        login_user = user_map.get(user, user)

        # Close existing connection
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

        # Open new connection
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(3)
        self.sock.connect((self.host, self.port))

        # Log in as new user
        self._send(f"connect {login_user}")
        self._consume_login_output()

        # Set up PREFIX/SUFFIX for response parsing
        self._send("PREFIX -=!-^-!=-")
        self._send("SUFFIX -=!-v-!=-")

        self.current_user = user

    def disconnect(self) -> None:
        """Close socket connection."""
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def execute(self, code: str) -> ExecutionResult:
        """Execute MOO code via socket."""
        if self.sock is None:
            raise RuntimeError("Transport not connected. Call connect() first.")

        # Join multi-line code into single line for socket transport.
        # MOO servers treat each line as a separate command, so multi-line
        # code must be flattened. This matches how Ruby tests work - they
        # send all eval code on a single line.
        code = ' '.join(line.strip() for line in code.strip().split('\n') if line.strip())

        # Send as eval command. Don't wrap with return here - the schema's
        # get_code_to_execute() handles that for expressions. Statements
        # already include their own return.
        cmd = f"; {code}"

        self._send(cmd)
        response = self._receive()
        return self._parse_response(response)

    def send_command(self, command: str) -> list[str]:
        """Send a raw command and capture output lines.

        Unlike execute(), this sends the command as-is without the `;` prefix,
        so it goes through the normal command parser. The output is whatever
        the verb notify()s to the player.

        Args:
            command: Raw command text (e.g., "put ball in box")

        Returns:
            List of output lines from command execution
        """
        if self.sock is None:
            raise RuntimeError("Transport not connected. Call connect() first.")

        # Send raw command (no ; prefix)
        self._send(command)

        # Receive output between PREFIX/SUFFIX markers
        return self._receive_lines()

    def _receive_lines(self) -> list[str]:
        """Receive lines between PREFIX and SUFFIX markers.

        Similar to _receive() but returns list of lines instead of joined string.
        Used for raw command output where we want to preserve line structure.
        """
        if self.sock is None:
            raise RuntimeError("Socket not connected")

        lines: list[str] = []
        state = 'looking'

        buffer = b""
        while state != 'done':
            try:
                data = self.sock.recv(4096)
                if not data:
                    break
                clean_data = self._strip_telnet_commands(data)
                buffer += clean_data

                while b'\n' in buffer:
                    line_bytes, buffer = buffer.split(b'\n', 1)
                    line = line_bytes.decode('utf-8').rstrip('\r')

                    if line == '-=!-^-!=-' and state in ('looking', 'found'):
                        state = 'found'
                        continue
                    if line == '-=!-v-!=-' and state == 'found':
                        # For raw commands, stop even if no output (unlike eval)
                        state = 'done'
                        continue
                    if state == 'found':
                        lines.append(line)
            except socket.timeout:
                break

        return lines

    def _send(self, message: str) -> None:
        """Send a line to the server."""
        if self.sock is None:
            raise RuntimeError("Socket not connected")
        self.sock.sendall((message + "\n").encode('utf-8'))

    @staticmethod
    def _strip_telnet_commands(data: bytes) -> bytes:
        """Remove telnet IAC (Interpret As Command) sequences from data.

        Telnet protocol uses 0xFF (IAC) as an escape byte followed by command bytes.
        MOO servers like ToastStunt send telnet negotiation at connection time.

        IAC sequences:
        - IAC WILL/WONT/DO/DONT option (3 bytes): 0xFF + 0xFB/0xFC/0xFD/0xFE + option
        - IAC SB ... IAC SE (subnegotiation): 0xFF 0xFA ... 0xFF 0xF0
        - IAC command (2 bytes): 0xFF + command (for other commands)
        - IAC IAC (literal 0xFF): 0xFF 0xFF -> 0xFF
        """
        result = bytearray()
        i = 0
        while i < len(data):
            if data[i] == 0xFF:  # IAC
                if i + 1 >= len(data):
                    # Incomplete IAC at end of buffer, skip it
                    break
                cmd = data[i + 1]
                if cmd == 0xFF:
                    # IAC IAC = literal 0xFF
                    result.append(0xFF)
                    i += 2
                elif cmd in (0xFB, 0xFC, 0xFD, 0xFE):
                    # WILL (0xFB), WONT (0xFC), DO (0xFD), DONT (0xFE) + option byte
                    i += 3  # Skip IAC + command + option
                elif cmd == 0xFA:
                    # Subnegotiation start - skip until IAC SE (0xFF 0xF0)
                    i += 2
                    while i + 1 < len(data):
                        if data[i] == 0xFF and data[i + 1] == 0xF0:
                            i += 2  # Skip IAC SE
                            break
                        i += 1
                else:
                    # Other 2-byte commands
                    i += 2
            else:
                result.append(data[i])
                i += 1
        return bytes(result)

    def _receive(self) -> str | None:
        """Receive response between PREFIX and SUFFIX markers.

        Toast sends double PREFIX/SUFFIX markers for eval commands.
        For exec() builtins, an early SUFFIX may appear before data:
          PREFIX, PREFIX, SUFFIX, DATA, SUFFIX

        We handle this by not stopping at SUFFIX until we have data.
        """
        if self.sock is None:
            raise RuntimeError("Socket not connected")

        lines: list[str] = []
        state = 'looking'

        buffer = b""  # Use bytes buffer for telnet handling
        while state != 'done':
            data = self.sock.recv(4096)
            if not data:
                break
            # Strip telnet IAC sequences before decoding
            clean_data = self._strip_telnet_commands(data)
            buffer += clean_data

            while b'\n' in buffer:
                line_bytes, buffer = buffer.split(b'\n', 1)
                line = line_bytes.decode('utf-8').rstrip('\r')

                if line == '-=!-^-!=-' and state in ('looking', 'found'):
                    state = 'found'
                    continue
                if line == '-=!-v-!=-' and state == 'found':
                    # Only stop if we have data - handles exec() early SUFFIX
                    if lines:
                        state = 'done'
                    continue
                if state == 'found':
                    lines.append(line)

        return '\n'.join(lines) if lines else None

    def _parse_response(self, response: str | None) -> ExecutionResult:
        """Parse MOO response into ExecutionResult.

        Toaststunt's eval returns wrapped responses:
        - {0, errors} - parse/compile error
        - {1, value} - success
        - {2, {E_TYPE, message, value}} - runtime error

        Toast also prefixes command results with "=> " which needs to be stripped.
        """
        if response is None:
            return ExecutionResult(success=True, value=None)

        # Strip "=> " prefix that Toast adds to eval results
        # Toast returns raw values (no {status, result} wrapper), so track this
        toast_format = response.startswith('=> ')
        if toast_format:
            response = response[3:]

        # Check for bare error codes (some commands return these directly)
        if response.startswith('E_'):
            error_match = re.match(r'(E_[A-Z]+)', response)
            if error_match:
                error_name = error_match.group(1)
                try:
                    error = MooError(error_name)
                    return ExecutionResult(success=False, error=error)
                except ValueError:
                    pass

        # Parse MOO literal
        value = self._parse_moo_literal(response)

        # Toast returns raw values (already stripped of "=> " prefix above).
        # Don't try to unwrap Toast responses - they're not in {status, result} format.
        if toast_format:
            return ExecutionResult(success=True, value=value)

        # Check for Toast-style error tracebacks (no "=> " prefix)
        # Format: "#-1:Input to EVAL ... line N:  Error message"
        if isinstance(value, str) and value.startswith('#-1:Input to EVAL') and '(End of traceback)' in value:
            # Extract error type from message
            error = self._extract_toast_error(value)
            if error:
                return ExecutionResult(success=False, error=error)
            # Unknown error format, return as error message
            return ExecutionResult(success=False, error_message=value)

        # Unwrap eval response format: {status, result}
        # This format is used by Barn but NOT by Toast.
        if isinstance(value, list) and len(value) == 2 and isinstance(value[0], int):
            status, result = value
            if status == 0:
                # Could be parse/compile error: {0, {line, message, ...}}
                # Or runtime error: {0, E_INVARG} (barn returns this format)
                # Check if result is an error code first
                if isinstance(result, str) and result.startswith('E_'):
                    try:
                        error = MooError(result)
                        return ExecutionResult(success=False, error=error)
                    except ValueError:
                        pass
                # Extract error message from nested structure
                # Barn format: {0, {line, "error message"}}
                error_msg = str(result)
                if isinstance(result, list) and len(result) >= 2:
                    error_msg = str(result[1])  # Extract message from {line, message}
                return ExecutionResult(
                    success=False,
                    error_message=error_msg,
                )
            elif status == 1:
                # Success: {1, actual_value}
                # Note: result can be an error TYPE (like E_PERM) as a VALUE
                # This is different from status==2 where it's an error STATE
                return ExecutionResult(success=True, value=result)
            elif status == 2:
                # Runtime error: {2, {E_TYPE, message, value}}
                if isinstance(result, list) and len(result) >= 1:
                    error_name = result[0] if isinstance(result[0], str) else str(result[0])
                    if error_name.startswith('E_'):
                        try:
                            error = MooError(error_name)
                            return ExecutionResult(success=False, error=error)
                        except ValueError:
                            pass
                return ExecutionResult(
                    success=False,
                    error_message=f"Runtime error: {result}",
                )

        return ExecutionResult(success=True, value=value)

    def _parse_moo_literal(self, text: str) -> Any:
        """Parse a MOO literal value."""
        text = text.strip()

        # Integer
        if re.match(r'^-?\d+$', text):
            return int(text)

        # Float
        if re.match(r'^-?\d+\.\d+([eE][-+]?\d+)?$', text):
            return float(text)

        # Anonymous object - multiple formats:
        # *#N (ToastStunt numbered format)
        # *anonymous* (ToastStunt string format for create($anonymous, 1) return value)
        if re.match(r'^\*#-?\d+$', text) or text == '*anonymous*':
            return text  # Return as-is to preserve type info

        # Object - keep as string with # prefix for type checking
        # Toast may add object name like "#2  (Wizard)" - strip the name part
        obj_match = re.match(r'^(#-?\d+)(?:\s+\(.+\))?$', text)
        if obj_match:
            return obj_match.group(1)  # Return just "#N" without name

        # String
        if text.startswith('"') and text.endswith('"'):
            return self._parse_moo_string(text)

        # Error
        if text.startswith('E_'):
            return text  # Return as string for checking

        # List - proper nested parsing
        if text.startswith('{') and text.endswith('}'):
            inner = text[1:-1].strip()
            if not inner:
                return []
            elements = self._split_moo_elements(inner)
            return [self._parse_moo_literal(e.strip()) for e in elements]

        # Map - proper nested parsing
        if text.startswith('[') and text.endswith(']'):
            inner = text[1:-1].strip()
            if not inner:
                return {}
            return self._parse_moo_map(inner)

        return text

    def _parse_moo_string(self, text: str) -> str:
        """Parse a MOO string literal with escape handling."""
        # Remove surrounding quotes
        inner = text[1:-1]
        result = []
        i = 0
        while i < len(inner):
            if inner[i] == '\\' and i + 1 < len(inner):
                next_char = inner[i + 1]
                if next_char == '"':
                    result.append('"')
                elif next_char == '\\':
                    result.append('\\')
                elif next_char == 'n':
                    result.append('\n')
                elif next_char == 't':
                    result.append('\t')
                elif next_char == 'r':
                    result.append('\r')
                else:
                    result.append(next_char)
                i += 2
            else:
                result.append(inner[i])
                i += 1
        return ''.join(result)

    def _split_moo_elements(self, text: str) -> list[str]:
        """Split MOO elements at top-level commas, respecting nesting."""
        elements = []
        current = []
        depth = 0
        in_string = False
        escape_next = False

        for char in text:
            if escape_next:
                current.append(char)
                escape_next = False
                continue

            if char == '\\' and in_string:
                current.append(char)
                escape_next = True
                continue

            if char == '"' and not escape_next:
                in_string = not in_string
                current.append(char)
                continue

            if not in_string:
                if char in '{[':
                    depth += 1
                elif char in '}]':
                    depth -= 1
                elif char == ',' and depth == 0:
                    elements.append(''.join(current))
                    current = []
                    continue

            current.append(char)

        if current:
            elements.append(''.join(current))

        return elements

    def _parse_moo_map(self, text: str) -> dict:
        """Parse MOO map contents: key -> value, key -> value, ..."""
        result = {}
        elements = self._split_moo_elements(text)

        for element in elements:
            element = element.strip()
            if not element:
                continue
            # Find the -> separator (not inside nested structures)
            arrow_pos = self._find_arrow(element)
            if arrow_pos == -1:
                continue
            key_str = element[:arrow_pos].strip()
            value_str = element[arrow_pos + 2:].strip()
            key = self._parse_moo_literal(key_str)
            value = self._parse_moo_literal(value_str)
            result[key] = value

        return result

    def _find_arrow(self, text: str) -> int:
        """Find -> in text, respecting nesting."""
        depth = 0
        in_string = False
        escape_next = False

        for i, char in enumerate(text):
            if escape_next:
                escape_next = False
                continue

            if char == '\\' and in_string:
                escape_next = True
                continue

            if char == '"':
                in_string = not in_string
                continue

            if not in_string:
                if char in '{[':
                    depth += 1
                elif char in '}]':
                    depth -= 1
                elif char == '-' and depth == 0 and i + 1 < len(text) and text[i + 1] == '>':
                    return i

        return -1

    def _extract_toast_error(self, traceback: str) -> MooError | None:
        """Extract error type from Toast-style error traceback.

        Toast returns errors like:
        "#-1:Input to EVAL (this == #-1), line 3:  Type mismatch"
        "#-1:Input to EVAL (this == #-1), line 3:  Division by zero"
        "#-1:Input to EVAL (this == #-1), line 3:  Permission denied"
        etc.
        """
        # Map Toast error messages to error codes
        error_map = {
            'Type mismatch': 'E_TYPE',
            'Division by zero': 'E_DIV',
            'Permission denied': 'E_PERM',
            'Property not found': 'E_PROPNF',
            'Verb not found': 'E_VERBNF',
            'Invalid argument': 'E_INVARG',
            'Invalid indirection': 'E_INVIND',
            'Resource limit exceeded': 'E_QUOTA',
            'Out of range': 'E_RANGE',
            'Range error': 'E_RANGE',  # Toast variant
            'Second argument must be a list': 'E_ARGS',
            'No object match': 'E_INVARG',
            'Recursive move': 'E_RECMOVE',
            'Illegal object': 'E_INVARG',
            'Maximum object recursion reached': 'E_MAXREC',
            'Number of seconds must be non-negative': 'E_INVARG',
            'Wrong number of arguments': 'E_ARGS',
            'Too many arguments': 'E_ARGS',
            'Not enough arguments': 'E_ARGS',
        }

        for msg, error_code in error_map.items():
            if msg in traceback:
                try:
                    return MooError(error_code)
                except ValueError:
                    pass

        return None
