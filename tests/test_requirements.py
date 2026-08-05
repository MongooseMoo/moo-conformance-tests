from types import SimpleNamespace

import pytest

from moo_conformance import plugin
from moo_conformance.capabilities import CapabilityManager
from moo_conformance.moo_types import MooError
from moo_conformance.schema import (
    MooTestCase,
    MooTestSuite,
    Requirements,
    RestartServer,
)
from moo_conformance.schema import (
    TestStep as MooTestStep,
)
from moo_conformance.test_conformance import (
    CapabilityProbeError,
    _enforce_skip_condition,
    _enforce_suite_requirements,
    _reset_capability_caches_for_tests,
    _snapshot_mutable_capabilities,
)
from moo_conformance.test_conformance import (
    test_yaml_conformance as run_yaml_case,
)
from moo_conformance.transport import ExecutionResult


class QueueTransport:
    def __init__(self, *results: ExecutionResult, current_user: str = "programmer"):
        self.results = list(results)
        self.executed: list[str] = []
        self.executed_as: list[str] = []
        self.current_user = current_user
        self.switches: list[str] = []

    def switch_user(self, user: str) -> None:
        self.switches.append(user)
        self.current_user = user

    def execute(self, code: str) -> ExecutionResult:
        self.executed.append(code)
        self.executed_as.append(self.current_user)
        if not self.results:
            raise AssertionError(f"unexpected capability probe: {code}")
        return self.results.pop(0)


def runner_with(*results: ExecutionResult, current_user: str = "programmer"):
    return SimpleNamespace(
        transport=QueueTransport(*results, current_user=current_user),
        prepare_suite_environment=lambda _suite: None,
    )


@pytest.fixture(autouse=True)
def reset_capability_caches():
    _reset_capability_caches_for_tests()


def test_missing_required_builtin_is_a_declared_skip() -> None:
    suite = MooTestSuite(
        name="requirements",
        requires=Requirements(builtins=["optional_builtin"]),
    )
    runner = runner_with(ExecutionResult(False, error=MooError.E_INVARG))

    with pytest.raises(pytest.skip.Exception, match="Requires builtin: optional_builtin"):
        _enforce_suite_requirements(suite, runner, {})


def test_builtin_probe_error_fails_instead_of_becoming_absence() -> None:
    suite = MooTestSuite(
        name="requirements",
        requires=Requirements(builtins=["function_info"]),
    )
    runner = runner_with(
        ExecutionResult(False, error=MooError.E_PERM, error_message="permission denied")
    )

    with pytest.raises(CapabilityProbeError, match="function_info"):
        _enforce_suite_requirements(suite, runner, {})


def test_missing_required_feature_is_a_declared_skip() -> None:
    suite = MooTestSuite(
        name="requirements",
        requires=Requirements(features=["maps"]),
    )
    runner = runner_with(ExecutionResult(True, value=["tasks"]))

    with pytest.raises(pytest.skip.Exception, match="Requires feature: maps"):
        _enforce_suite_requirements(suite, runner, {})


def test_profile_feature_enables_case_without_runtime_advertisement() -> None:
    suite = MooTestSuite(
        name="requirements",
        requires=Requirements(features=["maps"]),
    )
    runner = runner_with()

    _enforce_suite_requirements(suite, runner, {}, {"feature.maps": True})

    assert runner.transport.executed == []


def test_profile_feature_disables_case_without_runtime_probe() -> None:
    suite = MooTestSuite(
        name="requirements",
        requires=Requirements(features=["maps"]),
    )
    runner = runner_with()

    with pytest.raises(pytest.skip.Exception, match="Requires feature: maps"):
        _enforce_suite_requirements(suite, runner, {}, {"feature.maps": False})

    assert runner.transport.executed == []


@pytest.mark.parametrize("value", [None, 0, 1, "true", [], {}])
def test_profile_feature_rejects_non_boolean_values(value) -> None:
    suite = MooTestSuite(
        name="requirements",
        requires=Requirements(features=["maps"]),
    )
    runner = runner_with()

    with pytest.raises(CapabilityProbeError, match="profile value must be boolean"):
        _enforce_suite_requirements(suite, runner, {}, {"feature.maps": value})

    assert runner.transport.executed == []


def test_feature_probe_error_fails_instead_of_becoming_empty_feature_set() -> None:
    suite = MooTestSuite(
        name="requirements",
        requires=Requirements(features=["maps"]),
    )
    runner = runner_with(
        ExecutionResult(False, error=MooError.E_PERM, error_message="permission denied")
    )

    with pytest.raises(CapabilityProbeError, match="server features"):
        _enforce_suite_requirements(suite, runner, {})


@pytest.mark.parametrize(
    ("probe_results", "expected"),
    [
        (
            [
                ExecutionResult(False, error=MooError.E_INVARG),
                ExecutionResult(True, value="ON"),
            ],
            False,
        ),
        (
            [
                ExecutionResult(False, error=MooError.E_INVARG),
                ExecutionResult(True, value="#-1"),
            ],
            True,
        ),
        (
            [
                ExecutionResult(False, error=MooError.E_INVARG),
                ExecutionResult(True, value="OFF"),
            ],
            True,
        ),
    ],
)
def test_64bit_feature_uses_only_32_bits_option(
    probe_results: list[ExecutionResult], expected: bool
) -> None:
    test = MooTestCase(name="conditional", skip_if="feature.64bit")
    runner = runner_with(*probe_results)

    try:
        _enforce_skip_condition(test, runner, {})
        skipped = False
    except pytest.skip.Exception:
        skipped = True

    assert skipped is expected
    assert runner.transport.executed == [
        'return server_version("options.ONLY_32_BITS");',
        'return server_version("options/ONLY_32_BITS");',
    ]


def test_minimum_version_is_enforced() -> None:
    suite = MooTestSuite(
        name="requirements",
        requires=Requirements(min_version="1.8.1"),
    )
    runner = runner_with(ExecutionResult(True, value="1.7.9 ToastStunt"))

    with pytest.raises(pytest.skip.Exception, match=r"Requires server version >= 1\.8\.1"):
        _enforce_suite_requirements(suite, runner, {})


@pytest.mark.parametrize(
    "result",
    [
        ExecutionResult(False, error=MooError.E_PERM, error_message="permission denied"),
        ExecutionResult(True, value="development build"),
    ],
)
def test_version_probe_errors_fail(result: ExecutionResult) -> None:
    suite = MooTestSuite(
        name="requirements",
        requires=Requirements(min_version="1.8.1"),
    )

    with pytest.raises(CapabilityProbeError, match="server version"):
        _enforce_suite_requirements(suite, runner_with(result), {})


def test_missing_required_config_is_a_declared_skip() -> None:
    suite = MooTestSuite(
        name="requirements",
        requires=Requirements(config=["server_dir"]),
    )

    with pytest.raises(pytest.skip.Exception, match="Requires config 'server_dir'"):
        _enforce_suite_requirements(suite, runner_with(), {"server_dir": None})


def test_canonical_execution_enforces_implicit_managed_restart_requirement() -> None:
    suite = MooTestSuite(name="managed")
    test = MooTestCase(
        name="restart",
        steps=[MooTestStep(restart_server=RestartServer())],
    )

    with pytest.raises(pytest.skip.Exception, match="Requires config 'managed_server'"):
        run_yaml_case(
            runner_with(),
            (suite, test),
            {"managed_server": None},
            {},
        )


@pytest.mark.parametrize(
    ("condition", "probe", "reason"),
    [
        ("feature.maps", ExecutionResult(True, value=["maps"]), "Incompatible with feature: maps"),
        ("not feature.maps", ExecutionResult(True, value=[]), "Requires feature: maps"),
        (
            "missing builtin.optional_builtin",
            ExecutionResult(False, error=MooError.E_INVARG),
            "Requires builtin: optional_builtin",
        ),
        (
            "option.OUTBOUND_NETWORK",
            None,
            "Incompatible with option: OUTBOUND_NETWORK",
        ),
        (
            "not option.OUTBOUND_NETWORK",
            None,
            "Requires option: OUTBOUND_NETWORK",
        ),
    ],
)
def test_supported_skip_conditions_are_enforced(condition, probe, reason) -> None:
    test = MooTestCase(name="conditional", skip_if=condition)
    runner = runner_with(*(() if probe is None else (probe,)))
    profile = {
        "option.OUTBOUND_NETWORK": condition == "option.OUTBOUND_NETWORK",
    }

    with pytest.raises(pytest.skip.Exception, match=reason):
        _enforce_skip_condition(test, runner, profile)


@pytest.mark.parametrize(
    ("probe", "outbound", "reason"),
    [
        (
            ExecutionResult(False, error=MooError.E_INVARG),
            True,
            "Requires builtin: url_encode",
        ),
        (
            ExecutionResult(True, value=["url_encode", 1, 1]),
            False,
            "Requires option: OUTBOUND_NETWORK",
        ),
    ],
)
def test_any_skip_condition_uses_the_matching_exact_reason(
    probe: ExecutionResult,
    outbound: bool,
    reason: str,
) -> None:
    test = MooTestCase(
        name="conditional",
        skip_if="missing builtin.url_encode or not option.OUTBOUND_NETWORK",
    )
    runner = runner_with(probe)

    with pytest.raises(pytest.skip.Exception, match=reason):
        _enforce_skip_condition(
            test,
            runner,
            {"option.OUTBOUND_NETWORK": outbound},
        )

    assert len(runner.transport.executed) == 1


def test_option_probe_error_fails_instead_of_becoming_absence() -> None:
    test = MooTestCase(name="conditional", skip_if="not option.OUTBOUND_NETWORK")
    runner = runner_with(
        ExecutionResult(False, error=MooError.E_PERM, error_message="permission denied")
    )

    with pytest.raises(CapabilityProbeError, match="option OUTBOUND_NETWORK"):
        _enforce_skip_condition(test, runner, {})


def test_missing_option_paths_fail_closed() -> None:
    test = MooTestCase(name="conditional", skip_if="not option.OUTBOUND_NETWORK")
    runner = runner_with(
        ExecutionResult(False, error=MooError.E_INVARG),
        ExecutionResult(False, error=MooError.E_INVARG),
    )

    with pytest.raises(CapabilityProbeError, match="neither supported"):
        _enforce_skip_condition(test, runner, {})

    assert len(runner.transport.executed) == 2


@pytest.mark.parametrize(
    ("semantic_result", "skipped"),
    [
        (0, True),
        (1, False),
    ],
)
def test_promote_numbers_uses_numeric_equality_semantics(
    semantic_result: int, skipped: bool
) -> None:
    test = MooTestCase(name="conditional", skip_if="not option.PROMOTE_NUMBERS")
    runner = runner_with(ExecutionResult(True, value=semantic_result))

    try:
        _enforce_skip_condition(test, runner, {})
        actual_skipped = False
    except pytest.skip.Exception:
        actual_skipped = True

    assert actual_skipped is skipped
    assert runner.transport.executed == ["return 1 == 1.0;"]


@pytest.mark.parametrize(
    "result",
    [
        ExecutionResult(False, error=MooError.E_PERM, error_message="permission denied"),
        ExecutionResult(True, value="unknown"),
    ],
)
def test_promote_numbers_semantic_probe_fails_closed(result: ExecutionResult) -> None:
    test = MooTestCase(name="conditional", skip_if="not option.PROMOTE_NUMBERS")

    with pytest.raises(CapabilityProbeError, match="PROMOTE_NUMBERS"):
        _enforce_skip_condition(test, runner_with(result), {})


def test_canonical_execution_prepares_suite_before_capability_probes() -> None:
    events: list[str] = []

    class PreparedTransport(QueueTransport):
        def execute(self, code: str) -> ExecutionResult:
            assert events == ["prepare"]
            return super().execute(code)

    transport = PreparedTransport(ExecutionResult(True, value=["maps"]))
    runner = SimpleNamespace(
        transport=transport,
        prepare_suite_environment=lambda _suite: events.append("prepare"),
        run_suite_setup=lambda _suite: events.append("setup"),
        run_test=lambda _test: events.append("test"),
    )
    suite = MooTestSuite(
        name="prepared",
        requires=Requirements(features=["maps"]),
    )
    test = MooTestCase(name="case", code="return 1;")

    run_yaml_case(runner, (suite, test), {}, {})

    assert events == ["prepare", "setup", "test"]


@pytest.mark.parametrize(
    "value", [None, 0, 1, True, False, [], {}, "", "UNKNOWN"]
)
def test_option_probe_rejects_malformed_success_values(value) -> None:
    test = MooTestCase(name="conditional", skip_if="option.OUTBOUND_NETWORK")
    runner = runner_with(ExecutionResult(True, value=value))

    with pytest.raises(CapabilityProbeError, match="expected ON, OFF, or #-1"):
        _enforce_skip_condition(test, runner, {})


@pytest.mark.parametrize(
    ("feature", "results"),
    [
        (
            "connectable_listener_port",
            [
                ExecutionResult(False, error=MooError.E_INVARG),
                ExecutionResult(True, value="ON"),
                ExecutionResult(True, value=1),
            ],
        ),
        ("ephemeral_listen", [ExecutionResult(True, value=1)]),
    ],
)
def test_dynamic_admission_uses_wizard_after_programmer_case(
    feature: str,
    results: list[ExecutionResult],
) -> None:
    test = MooTestCase(name="conditional", skip_if=f"not feature.{feature}")
    runner = runner_with(*results, current_user="programmer")

    _enforce_skip_condition(test, runner, {})

    assert runner.transport.executed_as == ["wizard"] * len(results)
    assert runner.transport.current_user == "wizard"


def test_mutable_capabilities_are_snapshotted_before_order_contamination() -> None:
    runner = runner_with(
        ExecutionResult(False, error=MooError.E_INVARG),
        ExecutionResult(True, value="ON"),
        ExecutionResult(True, value=1),
        ExecutionResult(True, value=1),
        ExecutionResult(True, value=0),
    )

    _snapshot_mutable_capabilities(runner, {})
    probe_count = len(runner.transport.executed)
    assert "unlisten(0);" in runner.transport.executed[3]
    runner.transport.results.extend(
        [
            ExecutionResult(False, error=MooError.E_INVARG),
            ExecutionResult(False, error=MooError.E_INVARG),
        ]
    )

    _enforce_skip_condition(
        MooTestCase(name="connectable", skip_if="not feature.connectable_listener_port"),
        runner,
        {},
    )
    _enforce_skip_condition(
        MooTestCase(name="ephemeral", skip_if="not feature.ephemeral_listen"),
        runner,
        {},
    )
    with pytest.raises(pytest.skip.Exception, match="Requires option: PROMOTE_NUMBERS"):
        _enforce_skip_condition(
            MooTestCase(name="promotion", skip_if="not option.PROMOTE_NUMBERS"),
            runner,
            {},
        )

    assert len(runner.transport.executed) == probe_count
    assert len(runner.transport.results) == 2


def test_dynamic_probe_error_fails_instead_of_becoming_absence() -> None:
    test = MooTestCase(name="conditional", skip_if="not feature.ephemeral_listen")
    runner = runner_with(
        ExecutionResult(False, error=MooError.E_PERM, error_message="permission denied")
    )

    with pytest.raises(CapabilityProbeError, match="feature ephemeral_listen"):
        _enforce_skip_condition(test, runner, {})

    assert runner.transport.executed_as == ["wizard"]


@pytest.mark.parametrize("value", [None, True, False, "1", [], {}, 2])
def test_dynamic_probe_rejects_malformed_success_values(value) -> None:
    test = MooTestCase(name="conditional", skip_if="feature.ephemeral_listen")
    runner = runner_with(ExecutionResult(True, value=value))

    with pytest.raises(CapabilityProbeError, match="expected 0 or 1"):
        _enforce_skip_condition(test, runner, {})

    assert runner.transport.executed_as == ["wizard"]


@pytest.mark.parametrize(
    ("requirements", "reason"),
    [
        (Requirements(builtins=["curl"]), "Requires builtin: curl"),
        (Requirements(features=["maps"]), "Requires feature: maps"),
        (Requirements(min_version="1.8.1"), "Requires server version >= 1.8.1"),
        (
            Requirements(config=["server_dir"]),
            "Requires config 'server_dir' (use --moo-server-dir)",
        ),
    ],
)
def test_strict_skip_accounting_authorizes_declared_requirement_skips(
    requirements: Requirements, reason: str
) -> None:
    suite = MooTestSuite(name="requirements", requires=requirements)
    test = MooTestCase(name="case")
    item = SimpleNamespace(
        callspec=SimpleNamespace(params={"yaml_test_case": (suite, test)})
    )
    report = SimpleNamespace(
        skipped=True,
        outcome="skipped",
        longrepr=("test_conformance.py", 1, f"Skipped: {reason}"),
    )

    plugin._reject_unexpected_runtime_skip(item, report)

    assert report.outcome == "skipped"


def test_strict_skip_accounting_does_not_authorize_unrelated_requirement_skip() -> None:
    suite = MooTestSuite(
        name="requirements",
        requires=Requirements(features=["maps"]),
    )
    test = MooTestCase(name="case")
    item = SimpleNamespace(
        callspec=SimpleNamespace(params={"yaml_test_case": (suite, test)})
    )
    report = SimpleNamespace(
        skipped=True,
        outcome="skipped",
        longrepr=("runner.py", 1, "Skipped: Requires feature: tasks"),
    )

    plugin._reject_unexpected_runtime_skip(item, report)

    assert report.outcome == "failed"


def test_strict_skip_accounting_does_not_authorize_reason_prefixes() -> None:
    suite = MooTestSuite(
        name="requirements",
        requires=Requirements(features=["maps"]),
    )
    test = MooTestCase(name="case")
    item = SimpleNamespace(
        callspec=SimpleNamespace(params={"yaml_test_case": (suite, test)})
    )
    report = SimpleNamespace(
        skipped=True,
        outcome="skipped",
        longrepr=("runner.py", 1, "Skipped: Requires feature: maps_extension"),
    )

    plugin._reject_unexpected_runtime_skip(item, report)

    assert report.outcome == "failed"


def test_strict_skip_accounting_authorizes_implicit_managed_requirement() -> None:
    suite = MooTestSuite(name="managed")
    test = MooTestCase(
        name="restart",
        steps=[MooTestStep(restart_server=RestartServer())],
    )
    item = SimpleNamespace(
        callspec=SimpleNamespace(params={"yaml_test_case": (suite, test)})
    )
    report = SimpleNamespace(
        skipped=True,
        outcome="skipped",
        longrepr=(
            "test_conformance.py",
            1,
            "Skipped: Requires config 'managed_server' (use --server-command)",
        ),
    )

    plugin._reject_unexpected_runtime_skip(item, report)

    assert report.outcome == "skipped"


@pytest.mark.parametrize(
    ("state", "owner", "reason"),
    [
        ("no-provider", "test", "assumes 'fork' which has no provider"),
        ("failed", "suite", "assumes 'fork' which failed verification"),
        ("unverified", "test", "assumes 'fork' which is not yet verified"),
    ],
)
def test_strict_skip_accounting_authorizes_current_assumption_reason(
    monkeypatch: pytest.MonkeyPatch,
    state: str,
    owner: str,
    reason: str,
) -> None:
    manager = CapabilityManager()
    if state != "no-provider":
        manager.register_provider("fork", "provider")
    if state == "failed":
        manager.mark_failed("fork", "provider")
    monkeypatch.setattr(plugin, "capability_manager", manager)

    suite = MooTestSuite(
        name="assumptions",
        assumes=["fork"] if owner == "suite" else [],
    )
    test = MooTestCase(
        name="consumer",
        assumes=["fork"] if owner == "test" else [],
    )
    item = SimpleNamespace(
        callspec=SimpleNamespace(params={"yaml_test_case": (suite, test)})
    )
    report = SimpleNamespace(
        skipped=True,
        outcome="skipped",
        longrepr=("plugin.py", 1, f"Skipped: {reason}"),
    )

    plugin._reject_unexpected_runtime_skip(item, report)

    assert report.outcome == "skipped"


@pytest.mark.parametrize(
    "actual_reason",
    [
        "assumes 'tasks' which is not yet verified",
        "assumes 'fork' which failed verification",
    ],
)
def test_strict_skip_accounting_rejects_unrelated_or_stale_assumption_reason(
    monkeypatch: pytest.MonkeyPatch,
    actual_reason: str,
) -> None:
    manager = CapabilityManager()
    manager.register_provider("fork", "provider")
    monkeypatch.setattr(plugin, "capability_manager", manager)

    suite = MooTestSuite(name="assumptions")
    test = MooTestCase(name="consumer", assumes=["fork"])
    item = SimpleNamespace(
        callspec=SimpleNamespace(params={"yaml_test_case": (suite, test)})
    )
    report = SimpleNamespace(
        skipped=True,
        outcome="skipped",
        longrepr=("plugin.py", 1, f"Skipped: {actual_reason}"),
    )

    plugin._reject_unexpected_runtime_skip(item, report)

    assert report.outcome == "failed"
