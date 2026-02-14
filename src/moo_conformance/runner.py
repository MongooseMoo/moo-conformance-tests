"""Test execution engine for YAML conformance tests.

Executes test cases defined in YAML format against a MOO transport.
"""

import re
from typing import Any

from .transport import MooTransport, ExecutionResult, TestConnection
from .schema import MooTestSuite, MooTestCase, Expectation, TestStep
from .moo_types import MooError, TYPE_NAMES


class AssertionError(Exception):
    """Test assertion failed."""
    pass


class YamlTestRunner:
    """Executes YAML-defined test cases."""

    def __init__(self, transport: MooTransport):
        self.transport = transport
        self._suites_setup_done: set[str] = set()

    def run_suite_setup(self, suite: MooTestSuite) -> None:
        """Run suite-level setup.

        Note: Setup errors are NOT fatal, matching Ruby test framework behavior.
        This is because setup code may include add_property calls that fail
        if properties already exist (E_INVARG), but that's OK - we just
        want to ensure properties exist with correct values.
        """
        if suite.setup and suite.name not in self._suites_setup_done:
            # Switch user for suite setup if permission specified
            if suite.setup.permission:
                self.transport.switch_user(suite.setup.permission)
            # Execute setup code as individual statements to match Ruby behavior
            # Ruby calls evaluate() separately for each statement, ignoring errors
            code = suite.setup.code if isinstance(suite.setup.code, str) else "\n".join(suite.setup.code)
            if code.strip():
                # Split into individual statements and execute each separately
                # This matches Ruby's evaluate() calls which ignore errors
                for stmt in code.strip().split('\n'):
                    stmt = stmt.strip()
                    if stmt:
                        # Execute statement (errors ignored to match Ruby behavior)
                        self.transport.execute(stmt)
            self._suites_setup_done.add(suite.name)

    def run_suite_teardown(self, suite: MooTestSuite) -> None:
        """Run suite-level teardown."""
        if suite.teardown:
            # REMOVED: Connection is now session-scoped (managed by fixture)
            # self.transport.connect(suite.teardown.permission)
            # Run teardown code as a single block (may contain multi-line constructs)
            code = suite.teardown.code if isinstance(suite.teardown.code, str) else "\n".join(suite.teardown.code)
            if code.strip():
                # Best effort - don't fail on teardown errors
                self.transport.execute(code)
            self._suites_setup_done.discard(suite.name)

    def run_test(self, test: MooTestCase) -> None:
        """Run a single test case.

        Args:
            test: The test case to run

        Raises:
            AssertionError: If the test expectation is not met
        """
        # Switch to required user for this test
        if test.permission:
            self.transport.switch_user(test.permission)

        try:
            # Check if this is a multi-step test
            if test.has_steps():
                self._execute_steps(test)
            else:
                # Traditional single-execution test
                # Build combined code: setup + test
                # This keeps variables from setup available in test code
                code_parts = []

                # Add test setup code
                if test.setup:
                    for setup_code in test.setup.code_lines:
                        code_parts.append(setup_code)

                # Add the actual test code
                test_code = test.get_code_to_execute()
                code_parts.append(test_code)

                # Combine into single execution
                combined_code = "\n".join(code_parts)
                result = self.transport.execute(combined_code)

                # Verify expectations
                self._verify_expectations(test, result)

        finally:
            # Run test teardown (always, even on failure)
            if test.teardown:
                for code in test.teardown.code_lines:
                    self.transport.execute(code)

    def _execute_steps(self, test: MooTestCase) -> None:
        """Execute a multi-step test.

        Args:
            test: The test case with steps

        Raises:
            AssertionError: If any step's expectation is not met
        """
        variables: dict[str, Any] = {}
        connections: dict[str, TestConnection] = {}

        try:
            for step in test.steps:
                # Switch permission if step specifies different one
                if step.as_:
                    self.transport.switch_user(step.as_)

                # Handle new_connection step
                if step.new_connection:
                    conn = self.transport.open_connection()
                    connections[step.new_connection.capture] = conn
                    continue

                # Handle send step
                if step.send:
                    conn_name = step.send.connection
                    if conn_name not in connections:
                        raise AssertionError(
                            f"Unknown connection '{conn_name}'. Available: {list(connections.keys())}"
                        )
                    text = self._substitute_variables(step.send.text, variables)
                    output_lines = connections[conn_name].send(text)

                    if step.capture:
                        variables[step.capture] = output_lines

                    if step.expect and step.expect.output:
                        self._verify_output(step.expect.output, output_lines, f"send on '{conn_name}'")
                    continue

                # Handle close_connection step
                if step.close_connection:
                    conn_name = step.close_connection
                    if conn_name in connections:
                        connections[conn_name].close()
                        del connections[conn_name]
                    continue

                # Check if this is a verb_setup step
                if step.verb_setup:
                    result = self._execute_verb_setup(step.verb_setup, variables)
                    # Capture result if requested
                    if step.capture:
                        if result.success:
                            variables[step.capture] = result.value
                        else:
                            variables[step.capture] = result.error
                    # Verify expectation if present
                    if step.expect:
                        step_desc = f"verb_setup '{step.verb_setup.name}'"
                        self._verify_expectation(step.expect, result, step_desc)

                elif step.command:
                    # Raw command step - for testing command parser
                    command = self._substitute_variables(step.command, variables)
                    output_lines = self.transport.send_command(command)

                    # Note: command output is captured as list of lines, not as result value
                    # Capture is not typically used for commands, but we could capture output
                    if step.capture:
                        variables[step.capture] = output_lines

                    # Verify output expectation if present
                    if step.expect and step.expect.output:
                        step_desc = f"command '{step.command[:30]}...'"
                        self._verify_output(step.expect.output, output_lines, step_desc)

                else:
                    # Execute the step (run field)
                    code = self._substitute_variables(step.run, variables)

                    # Wrap as expression if it doesn't look like a statement
                    # Check if code contains 'return' anywhere (for multi-line code)
                    stripped = code.strip()
                    has_return = 'return ' in stripped or stripped.startswith('return')
                    is_statement = any(stripped.startswith(kw) for kw in ('if', 'for', 'while', 'try'))

                    if not has_return and not is_statement:
                        if not stripped.endswith(';'):
                            code = f"return {stripped};"
                        else:
                            code = f"return {stripped}"

                    result = self.transport.execute(code)

                    # Capture result if requested
                    if step.capture:
                        if result.success:
                            variables[step.capture] = result.value
                        else:
                            # Capture error for later use
                            variables[step.capture] = result.error

                    # Verify expectation if present
                    if step.expect:
                        step_desc = f"step '{step.run[:30]}...'"
                        self._verify_expectation(step.expect, result, step_desc)

        finally:
            # Run cleanup steps (always, even on failure)
            for cleanup_step in test.cleanup:
                # Switch permission if cleanup step specifies different one
                if cleanup_step.as_:
                    self.transport.switch_user(cleanup_step.as_)

                cleanup_code = self._substitute_variables(cleanup_step.run, variables)
                # Best effort - don't fail on cleanup errors
                self.transport.execute(cleanup_code)

            # Close any remaining connections
            for conn in connections.values():
                try:
                    conn.close()
                except Exception:
                    pass

    def _substitute_variables(self, code: str, variables: dict[str, Any]) -> str:
        """Substitute {varname} placeholders with captured values.

        Args:
            code: MOO code with {varname} placeholders
            variables: Dict of captured variable values

        Returns:
            Code with placeholders replaced by MOO literals
        """
        from .schema import _value_to_moo

        result = code
        for name, value in variables.items():
            placeholder = f"{{{name}}}"
            if placeholder in result:
                result = result.replace(placeholder, _value_to_moo(value))
        return result

    def _execute_verb_setup(self, vs: Any, variables: dict) -> ExecutionResult:
        """Create a verb on an object.

        Args:
            vs: VerbSetup instance with object, name, args, and code
            variables: Dict of captured variable values for substitution

        Returns:
            ExecutionResult from set_verb_code (last operation)
        """
        obj = self._substitute_variables(vs.object, variables)
        name = vs.name
        args_str = '{' + ', '.join(f'"{a}"' for a in vs.args) + '}'

        # Convert code to list of lines (set_verb_code requires a list)
        # Split on newlines and escape each line for MOO string
        code_lines = vs.code.split('\n')
        code_list_items = []
        for line in code_lines:
            # Escape backslashes and quotes for MOO string literal
            escaped = line.replace('\\', '\\\\').replace('"', '\\"')
            code_list_items.append(f'"{escaped}"')
        code_list_str = '{' + ', '.join(code_list_items) + '}'

        # Execute both add_verb and set_verb_code in ONE statement
        # This is necessary because MOO doesn't maintain variable scope between executions
        # Use return on set_verb_code to capture its result (empty list on success)
        combined_code = (
            f'add_verb({obj}, {{player, "xd", "{name}"}}, {args_str}); '
            f'return set_verb_code({obj}, "{name}", {code_list_str});'
        )
        return self.transport.execute(combined_code)

    def _verify_expectation(self, expect: Expectation, result: ExecutionResult, context: str) -> None:
        """Verify a single expectation against a result.

        Args:
            expect: The expectation to verify
            result: The execution result
            context: Context string for error messages (e.g., test name or step description)
        """
        # Check for expected error
        if expect.error:
            self._verify_error(expect.error, result, context)
            return

        # Check for expected match pattern (can match on error messages too)
        if expect.match:
            # If we got an error, check if the pattern matches the error message
            if not result.success and result.error_message:
                self._verify_match(expect.match, result.error_message, context)
                return
            # Otherwise expect success and check value
            if not result.success:
                raise AssertionError(
                    f"{context} expected success but got error: "
                    f"{result.error or result.error_message}"
                )
            self._verify_match(expect.match, result.value, context)
            return

        # If we got here, we expect success
        if not result.success:
            raise AssertionError(
                f"{context} expected success but got error: "
                f"{result.error or result.error_message}"
            )

        # Check value expectation
        if expect.value is not None:
            self._verify_value(expect.value, result.value, context)

        # Check type expectation
        if expect.type:
            self._verify_type(expect.type, result.value, context)

    def _verify_expectations(self, test: MooTestCase, result: ExecutionResult) -> None:
        """Verify test result against expectations.

        Args:
            test: The test case with expectations
            result: The execution result to verify

        Raises:
            AssertionError: If any expectation is not met
        """
        expect = test.expect

        # Check for expected error
        if expect.error:
            self._verify_error(expect.error, result, test.name)
            return

        # Check for expected match pattern (can match on error messages too)
        if expect.match:
            # If we got an error, check if the pattern matches the error message
            if not result.success and result.error_message:
                self._verify_match(expect.match, result.error_message, test.name)
                return
            # Otherwise expect success and check value
            if not result.success:
                raise AssertionError(
                    f"Test '{test.name}' expected success but got error: "
                    f"{result.error or result.error_message}"
                )
            self._verify_match(expect.match, result.value, test.name)
            return

        # If we got here, we expect success
        if not result.success:
            raise AssertionError(
                f"Test '{test.name}' expected success but got error: "
                f"{result.error or result.error_message}"
            )

        # Check value expectation
        if expect.value is not None:
            self._verify_value(expect.value, result.value, test.name)

        # Check type expectation
        if expect.type:
            self._verify_type(expect.type, result.value, test.name)

        # Check contains expectation
        if expect.contains is not None:
            self._verify_contains(expect.contains, result.value, test.name)

        # Check range expectation
        if expect.range:
            self._verify_range(expect.range, result.value, test.name)

        # Check notifications expectation
        if expect.notifications:
            self._verify_notifications(expect.notifications, result.notifications, test.name)

    def _verify_error(self, expected_error: str, result: ExecutionResult, test_name: str) -> None:
        """Verify that an error was returned."""
        if result.success:
            raise AssertionError(
                f"Test '{test_name}' expected error {expected_error}, "
                f"but got success with value: {result.value!r}"
            )

        if result.error is None:
            raise AssertionError(
                f"Test '{test_name}' expected error {expected_error}, "
                f"but got non-MOO error: {result.error_message}"
            )

        # Compare error codes
        actual_error = result.error.value if isinstance(result.error, MooError) else str(result.error)
        if actual_error != expected_error:
            raise AssertionError(
                f"Test '{test_name}' expected error {expected_error}, "
                f"but got {actual_error}"
            )

    def _verify_value(self, expected: Any, actual: Any, test_name: str) -> None:
        """Verify exact value match."""
        if not self._values_equal(expected, actual):
            raise AssertionError(
                f"Test '{test_name}' expected value {expected!r}, "
                f"but got {actual!r}"
            )

    def _values_equal(self, expected: Any, actual: Any) -> bool:
        """Compare values with type flexibility.

        Handles:
        - Exact matches
        - Float comparison with tolerance
        - List/dict comparison
        - Error code comparisons (string vs MooError enum)
        """
        # Handle None
        if expected is None and actual is None:
            return True

        # Handle error comparison: "E_PERM" (string) should equal MooError.E_PERM
        if isinstance(expected, str) and expected.startswith("E_"):
            if isinstance(actual, MooError):
                return expected == actual.value
            if isinstance(actual, str) and actual.startswith("E_"):
                return expected == actual

        # Reverse: MooError vs string
        if isinstance(actual, str) and actual.startswith("E_"):
            if isinstance(expected, MooError):
                return actual == expected.value

        # Handle ObjNum comparison: "#2" (string) should equal 2 (int from ObjNum)
        if isinstance(expected, str) and expected.startswith("#"):
            try:
                expected_num = int(expected[1:])
                if isinstance(actual, int):
                    return expected_num == actual
            except ValueError:
                pass

        # Reverse: int vs "#N" string
        if isinstance(actual, str) and actual.startswith("#"):
            try:
                actual_num = int(actual[1:])
                if isinstance(expected, int):
                    return expected == actual_num
            except ValueError:
                pass

        # Handle floats with tolerance
        if isinstance(expected, float) and isinstance(actual, (int, float)):
            return abs(expected - actual) < 1e-9

        # Handle int/float comparison
        if isinstance(expected, int) and isinstance(actual, float):
            return expected == actual

        # Handle lists
        if isinstance(expected, list) and isinstance(actual, list):
            if len(expected) != len(actual):
                return False
            return all(self._values_equal(e, a) for e, a in zip(expected, actual))

        # Handle dicts
        if isinstance(expected, dict) and isinstance(actual, dict):
            if len(expected) != len(actual):
                return False
            # Build key mapping to handle error keys (string "E_ARGS" == MooError.E_ARGS)
            for exp_key in expected:
                # Find matching actual key
                actual_key = None
                for ak in actual:
                    if self._keys_equal(exp_key, ak):
                        actual_key = ak
                        break
                if actual_key is None:
                    return False
                if not self._values_equal(expected[exp_key], actual[actual_key]):
                    return False
            return True

        # Direct comparison
        return expected == actual

    def _keys_equal(self, expected_key: Any, actual_key: Any) -> bool:
        """Compare dict keys with error handling."""
        # Handle error: "E_ARGS" == MooError.E_ARGS
        if isinstance(expected_key, str) and expected_key.startswith("E_"):
            if isinstance(actual_key, MooError):
                return expected_key == actual_key.value
            if isinstance(actual_key, str):
                return expected_key == actual_key
        if isinstance(actual_key, str) and actual_key.startswith("E_"):
            if isinstance(expected_key, MooError):
                return actual_key == expected_key.value

        # Handle ObjNum: "#2" == 2
        if isinstance(expected_key, str) and expected_key.startswith("#"):
            try:
                expected_num = int(expected_key[1:])
                if isinstance(actual_key, int):
                    return expected_num == actual_key
            except ValueError:
                pass
        if isinstance(actual_key, str) and actual_key.startswith("#"):
            try:
                actual_num = int(actual_key[1:])
                if isinstance(expected_key, int):
                    return expected_key == actual_num
            except ValueError:
                pass

        return expected_key == actual_key

    def _verify_type(self, expected_type: str, actual: Any, test_name: str) -> None:
        """Verify value type."""
        actual_type = self._get_moo_type(actual)
        if actual_type != expected_type:
            raise AssertionError(
                f"Test '{test_name}' expected type {expected_type}, "
                f"but got {actual_type} (value: {actual!r})"
            )

    def _get_moo_type(self, value: Any) -> str:
        """Get MOO type name for a value."""
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "float"
        if isinstance(value, str):
            # Check if it's an anonymous object (*#N format - ToastStunt style)
            if value.startswith("*#") and len(value) > 2:
                try:
                    int(value[2:])
                    return "anon"
                except ValueError:
                    pass
            # Check if it's an anonymous object (anon:#N format - alternate)
            if value.startswith("anon:#"):
                return "anon"
            # Check if it's anonymous object (*anonymous* format - Toast return)
            if value == "*anonymous*":
                return "anon"
            # Check if it's a regular object (#N format)
            if value.startswith("#") and len(value) > 1:
                # Verify it's a valid object number format
                try:
                    int(value[1:])
                    return "obj"
                except ValueError:
                    pass
            # Check if it's an error value
            if value.startswith("E_"):
                return "err"
            return "str"
        if isinstance(value, list):
            return "list"
        if isinstance(value, dict):
            return "map"
        return "unknown"

    def _verify_match(self, pattern: str, actual: Any, test_name: str) -> None:
        """Verify regex match on string result.

        For strings: pattern must match somewhere in the string.
        For lists: pattern must match in at least one element (converted to string).
        """
        if isinstance(actual, list):
            # Check if pattern matches any element in the list
            for item in actual:
                if re.search(pattern, str(item)):
                    return  # Found a match
            raise AssertionError(
                f"Test '{test_name}' pattern {pattern!r} not found in any element of {actual!r}"
            )
        elif not isinstance(actual, str):
            raise AssertionError(
                f"Test '{test_name}' expected string or list for match, "
                f"but got {type(actual).__name__}: {actual!r}"
            )
        elif not re.search(pattern, actual):
            raise AssertionError(
                f"Test '{test_name}' pattern {pattern!r} not found in {actual!r}"
            )

    def _verify_contains(self, expected: Any, actual: Any, test_name: str) -> None:
        """Verify that actual contains expected value."""
        if isinstance(actual, list):
            if expected not in actual:
                raise AssertionError(
                    f"Test '{test_name}' expected list to contain {expected!r}, "
                    f"but list is {actual!r}"
                )
        elif isinstance(actual, dict):
            if expected not in actual:
                raise AssertionError(
                    f"Test '{test_name}' expected map to contain key {expected!r}, "
                    f"but map is {actual!r}"
                )
        elif isinstance(actual, str):
            if expected not in actual:
                raise AssertionError(
                    f"Test '{test_name}' expected string to contain {expected!r}, "
                    f"but string is {actual!r}"
                )
        else:
            raise AssertionError(
                f"Test '{test_name}' contains check requires list, map, or string, "
                f"but got {type(actual).__name__}"
            )

    def _verify_range(self, expected_range: list[float], actual: Any, test_name: str) -> None:
        """Verify value is within range [min, max]."""
        if not isinstance(actual, (int, float)):
            raise AssertionError(
                f"Test '{test_name}' range check requires numeric value, "
                f"but got {type(actual).__name__}: {actual!r}"
            )

        min_val, max_val = expected_range
        if not (min_val <= actual <= max_val):
            raise AssertionError(
                f"Test '{test_name}' expected value in range [{min_val}, {max_val}], "
                f"but got {actual}"
            )

    def _verify_notifications(
        self, expected: list[str], actual: list[dict], test_name: str
    ) -> None:
        """Verify expected notifications were sent."""
        actual_msgs = [n.get("message", "") for n in actual]

        for expected_msg in expected:
            found = False
            for actual_msg in actual_msgs:
                if expected_msg in actual_msg:
                    found = True
                    break

            if not found:
                raise AssertionError(
                    f"Test '{test_name}' expected notification {expected_msg!r}, "
                    f"but only got: {actual_msgs}"
                )

    def _verify_output(self, expected: Any, actual: list[str], context: str) -> None:
        """Verify output from raw command matches expectation.

        Args:
            expected: OutputExpect with exact, match, or contains
            actual: List of output lines from command
            context: Context string for error messages
        """
        # Import here to avoid circular dependency
        from .schema import OutputExpect

        if not isinstance(expected, OutputExpect):
            raise AssertionError(f"{context} invalid output expectation type: {type(expected)}")

        # Join lines for matching
        joined = "\n".join(actual)

        if expected.exact is not None:
            # Exact match
            if isinstance(expected.exact, list):
                if actual != expected.exact:
                    raise AssertionError(
                        f"{context} expected output lines {expected.exact!r}, "
                        f"but got {actual!r}"
                    )
            else:
                # Single string - match against joined output
                if joined != expected.exact:
                    raise AssertionError(
                        f"{context} expected output {expected.exact!r}, "
                        f"but got {joined!r}"
                    )
            return

        if expected.match is not None:
            # Regex match on joined output
            if not re.search(expected.match, joined):
                raise AssertionError(
                    f"{context} pattern {expected.match!r} not found in output {joined!r}"
                )
            return

        if expected.contains is not None:
            # Substring match on joined output
            if expected.contains not in joined:
                raise AssertionError(
                    f"{context} expected output to contain {expected.contains!r}, "
                    f"but got {joined!r}"
                )
