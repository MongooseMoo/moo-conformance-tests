"""Capability system for test dependency management.

Provides a mechanism for tests to declare dependencies on other tests.
Tests can 'provide' capabilities that other tests can 'assume'.

Key concepts:
- provide: A test/suite declares it verifies a capability (e.g., 'fork', 'queued_tasks')
- assume: A test/suite declares it depends on a capability being verified
- Capability states: unverified -> verified (all providers pass) or failed (any provider fails)
- Tests that assume failed capabilities are automatically skipped

This allows tests to declare "I use fork() to observe X" without coupling
to specific fork tests. If fork tests fail, observation tests are skipped.
"""

from enum import Enum
from dataclasses import dataclass, field


class CapabilityState(Enum):
    """State of a capability."""
    UNVERIFIED = "unverified"  # Not yet tested
    VERIFIED = "verified"      # All providers passed
    FAILED = "failed"          # At least one provider failed


@dataclass
class Capability:
    """A capability that can be provided and assumed by tests."""
    name: str
    state: CapabilityState = CapabilityState.UNVERIFIED
    providers: list[str] = field(default_factory=list)  # Test IDs that provide this
    passed_providers: set[str] = field(default_factory=set)  # Providers that passed
    failed_provider: str | None = None  # First provider that failed


class CapabilityManager:
    """Manages capability dependencies between tests.

    Usage:
        # During collection phase
        manager = CapabilityManager()
        manager.register_provider("fork", "test_fork_basic")
        manager.register_provider("fork", "test_fork_with_args")

        # During test execution
        manager.mark_passed("fork", "test_fork_basic")
        manager.mark_passed("fork", "test_fork_with_args")
        # Now 'fork' is VERIFIED

        # Before running consumer test
        can_run, reason = manager.can_run(["fork", "queued_tasks"])
        if not can_run:
            pytest.skip(reason)
    """

    def __init__(self):
        self.capabilities: dict[str, Capability] = {}

    def register_provider(self, capability: str, test_id: str):
        """Register a test as a provider of a capability.

        Args:
            capability: Name of the capability (e.g., 'fork', 'queued_tasks')
            test_id: Unique test identifier (pytest nodeid)
        """
        if capability not in self.capabilities:
            self.capabilities[capability] = Capability(name=capability)
        self.capabilities[capability].providers.append(test_id)

    def mark_passed(self, capability: str, test_id: str):
        """Mark a provider test as passed.

        If all providers for this capability have passed, marks the
        capability as VERIFIED.

        Args:
            capability: Name of the capability
            test_id: Test identifier that passed
        """
        cap = self.capabilities.get(capability)
        if not cap:
            return

        cap.passed_providers.add(test_id)

        # Capability is verified when ALL providers pass
        if len(cap.passed_providers) == len(cap.providers):
            cap.state = CapabilityState.VERIFIED

    def mark_failed(self, capability: str, test_id: str):
        """Mark a provider test as failed.

        Immediately marks the capability as FAILED.

        Args:
            capability: Name of the capability
            test_id: Test identifier that failed
        """
        cap = self.capabilities.get(capability)
        if not cap:
            return

        cap.state = CapabilityState.FAILED
        if cap.failed_provider is None:
            cap.failed_provider = test_id

    def can_run(self, assumes: list[str]) -> tuple[bool, str | None]:
        """Check if a test can run based on assumed capabilities.

        Args:
            assumes: List of capability names the test assumes

        Returns:
            Tuple of (can_run, skip_reason)
            - can_run: True if all assumed capabilities are verified
            - skip_reason: Human-readable reason if can_run is False
        """
        for cap_name in assumes:
            cap = self.capabilities.get(cap_name)

            if not cap:
                return False, f"assumes '{cap_name}' which has no provider"

            if cap.state == CapabilityState.FAILED:
                return False, f"assumes '{cap_name}' which failed verification"

            if cap.state == CapabilityState.UNVERIFIED:
                return False, f"assumes '{cap_name}' which is not yet verified"

        return True, None

    def get_capability_state(self, name: str) -> CapabilityState | None:
        """Get the current state of a capability.

        Args:
            name: Capability name

        Returns:
            CapabilityState if capability exists, None otherwise
        """
        cap = self.capabilities.get(name)
        return cap.state if cap else None

    def get_all_capabilities(self) -> dict[str, Capability]:
        """Get all registered capabilities.

        Returns:
            Dictionary mapping capability names to Capability objects
        """
        return self.capabilities.copy()
