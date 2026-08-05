"""YAML Conformance Tests.

Discovers and runs all YAML test files bundled in the package.

Run with:
    pytest --pyargs moo_conformance --moo-port=7777
"""

import re

import pytest

from .conditions import config_skip_reason, parse_min_version, parse_skip_condition
from .moo_types import MooError
from .plugin import _skip_declared_yaml_case

_builtin_cache: dict[str, bool] = {}
_feature_cache: set[str] | None = None
_dynamic_feature_cache: dict[str, bool] = {}
_option_cache: dict[str, bool] = {}
_version_cache: tuple[int, int, int] | None = None


class CapabilityProbeError(RuntimeError):
    """A capability could not be determined reliably."""


def _probe_failure(capability: str, result) -> CapabilityProbeError:
    detail = result.error_message or result.error or "unsuccessful execution"
    return CapabilityProbeError(f"Failed to probe {capability}: {detail}")


def _execute_probe(runner, capability: str, code: str):
    """Execute one admission probe as wizard or fail with probe context."""
    switch_user = getattr(runner.transport, "switch_user", None)
    if not callable(switch_user):
        raise CapabilityProbeError(
            f"Failed to probe {capability}: transport cannot select wizard identity"
        )
    try:
        switch_user("wizard")
        return runner.transport.execute(code)
    except CapabilityProbeError:
        raise
    except Exception as exc:
        raise CapabilityProbeError(f"Failed to probe {capability}: {exc}") from exc


def _reset_capability_caches_for_tests() -> None:
    global _feature_cache, _version_cache
    _builtin_cache.clear()
    _feature_cache = None
    _dynamic_feature_cache.clear()
    _option_cache.clear()
    _version_cache = None


def _moo_string_literal(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _has_builtin(runner, builtin: str) -> bool:
    if builtin not in _builtin_cache:
        result = _execute_probe(
            runner,
            f"builtin {builtin} via function_info()",
            f"return function_info({_moo_string_literal(builtin)});"
        )
        if result.success:
            _builtin_cache[builtin] = True
        elif result.error == MooError.E_INVARG:
            _builtin_cache[builtin] = False
        else:
            raise _probe_failure(f"builtin {builtin} via function_info()", result)
    return _builtin_cache[builtin]


def _server_features(runner) -> set[str]:
    global _feature_cache
    if _feature_cache is None:
        result = _execute_probe(
            runner, "server features", 'return server_version("features");'
        )
        if not result.success:
            raise _probe_failure("server features", result)
        if not isinstance(result.value, list) or any(
            not isinstance(feature, str) for feature in result.value
        ):
            raise CapabilityProbeError(
                f"Failed to probe server features: expected a list of strings, got {result.value!r}"
            )
        _feature_cache = set(result.value)
    return _feature_cache


def _has_feature(
    runner,
    feature: str,
    profile_features: dict[str, object] | None = None,
) -> bool:
    profile_key = f"feature.{feature}"
    if profile_features is not None and profile_key in profile_features:
        value = profile_features[profile_key]
        if not isinstance(value, bool):
            raise CapabilityProbeError(
                f"Failed to probe feature {feature}: profile value must be boolean, "
                f"got {value!r}"
            )
        return value
    if feature == "64bit":
        return not _has_option(runner, "ONLY_32_BITS", profile_features)
    if feature == "connectable_listener_port":
        if not _has_option(runner, "OUTBOUND_NETWORK", profile_features):
            return False
        return _dynamic_feature(feature, runner, """
            available = listeners();
            if (length(available) == 0)
              return 0;
            endif
            port = available[1]["port"];
            conn = open_network_connection("localhost", port);
            boot_player(conn);
            return 1;
        """)
    if feature == "ephemeral_listen":
        return _dynamic_feature(feature, runner, """
            port = listen(player, 0, ["print-messages" -> 1]);
            unlisten(0);
            return 1;
        """)
    return feature in _server_features(runner)


def _dynamic_feature(feature: str, runner, statement: str) -> bool:
    """Probe runtime capabilities that are not advertised by server_version()."""
    if feature not in _dynamic_feature_cache:
        result = _execute_probe(runner, f"feature {feature}", statement)
        if not result.success:
            raise _probe_failure(f"feature {feature}", result)
        if type(result.value) is not int or result.value not in (0, 1):
            raise CapabilityProbeError(
                f"Failed to probe feature {feature}: expected 0 or 1, got {result.value!r}"
            )
        _dynamic_feature_cache[feature] = result.value == 1
    return _dynamic_feature_cache[feature]


def _snapshot_mutable_capabilities(
    runner, profile_features: dict[str, object] | None = None
) -> None:
    """Resolve state-sensitive admission facts before any case mutates the server."""
    for feature in ("connectable_listener_port", "ephemeral_listen"):
        _has_feature(runner, feature, profile_features)
    _has_option(runner, "PROMOTE_NUMBERS", profile_features)


def _has_option(runner, option: str, profile_features: dict[str, object] | None = None) -> bool:
    profile_key = f"option.{option}"
    if profile_features is not None and profile_key in profile_features:
        value = profile_features[profile_key]
        if not isinstance(value, bool):
            raise CapabilityProbeError(
                f"Failed to probe option {option}: profile value must be boolean, got {value!r}"
            )
        return value

    if option == "PROMOTE_NUMBERS":
        if option not in _option_cache:
            result = _execute_probe(
                runner,
                f"option {option} via numeric equality semantics",
                "return 1 == 1.0;",
            )
            if not result.success:
                raise _probe_failure(
                    f"option {option} via numeric equality semantics", result
                )
            if type(result.value) is not int or result.value not in (0, 1):
                raise CapabilityProbeError(
                    f"Failed to probe option {option}: expected semantic result 0 or 1, "
                    f"got {result.value!r}"
                )
            _option_cache[option] = result.value == 1
        return _option_cache[option]

    if option not in _option_cache:
        for key in (f"options.{option}", f"options/{option}"):
            result = _execute_probe(
                runner,
                f"option {option}",
                f"return server_version({_moo_string_literal(key)});"
            )
            if not result.success:
                if result.error == MooError.E_INVARG:
                    continue
                raise _probe_failure(f"option {option}", result)
            if result.value == "ON":
                _option_cache[option] = True
            elif result.value in ("OFF", "#-1"):
                _option_cache[option] = False
            else:
                raise CapabilityProbeError(
                    f"Failed to probe option {option}: expected ON, OFF, or #-1, "
                    f"got {result.value!r}"
                )
            break
        else:
            raise CapabilityProbeError(
                f"Failed to probe option {option}: neither supported server_version "
                "option path is available"
            )
    return _option_cache[option]


def _server_version(runner) -> tuple[int, int, int]:
    global _version_cache
    if _version_cache is None:
        result = _execute_probe(runner, "server version", "return server_version();")
        if not result.success:
            raise _probe_failure("server version", result)
        if not isinstance(result.value, str):
            raise CapabilityProbeError(
                f"Failed to probe server version: expected a string, got {result.value!r}"
            )
        match = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:\D|$)", result.value)
        if match is None:
            raise CapabilityProbeError(
                f"Failed to probe server version: unrecognized value {result.value!r}"
            )
        _version_cache = (
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
        )
    return _version_cache


def _enforce_suite_requirements(
    suite,
    runner,
    moo_config,
    profile_features: dict[str, object] | None = None,
) -> None:
    for builtin in suite.requires.builtins:
        if not _has_builtin(runner, builtin):
            pytest.skip(f"Requires builtin: {builtin}")
    for feature in suite.requires.features:
        if not _has_feature(runner, feature, profile_features):
            pytest.skip(f"Requires feature: {feature}")
    if suite.requires.min_version is not None:
        required = parse_min_version(suite.requires.min_version)
        if _server_version(runner) < required:
            pytest.skip(f"Requires server version >= {suite.requires.min_version}")
    for key in suite.requires.config:
        if moo_config.get(key) is None:
            pytest.skip(config_skip_reason(key))


def _enforce_skip_condition(test, runner, profile_features) -> None:
    if test.skip_if is None:
        return
    condition = parse_skip_condition(test.skip_if)
    if condition.target == "feature":
        present = _has_feature(runner, condition.name, profile_features)
    elif condition.target == "builtin":
        present = _has_builtin(runner, condition.name)
    else:
        present = _has_option(runner, condition.name, profile_features)
    if present == condition.skip_when_present:
        pytest.skip(condition.skip_reason)


def _uses_managed_restart(test) -> bool:
    return any(step.restart_server is not None for step in [*test.steps, *test.cleanup])


@pytest.fixture(scope="session", autouse=True)
def mutable_capability_snapshot(runner, profile_metadata_gate) -> None:
    """Snapshot mutable runtime capabilities on the pristine managed server."""
    _snapshot_mutable_capabilities(runner, profile_metadata_gate)


@pytest.mark.conformance
def test_yaml_conformance(runner, yaml_test_case, moo_config, profile_metadata_gate):
    """Run a single YAML test case.

    Args:
        runner: YamlTestRunner fixture
        yaml_test_case: (suite, test) tuple from parametrization
        moo_config: dict of available config values for requires.config checks
    """
    suite, test = yaml_test_case

    _skip_declared_yaml_case(suite, test)

    runner.prepare_suite_environment(suite)
    _enforce_suite_requirements(suite, runner, moo_config, profile_metadata_gate)
    _enforce_skip_condition(test, runner, profile_metadata_gate)

    if _uses_managed_restart(test) and moo_config.get("managed_server") is None:
        pytest.skip(config_skip_reason("managed_server"))

    # Run suite setup if not already done
    runner.run_suite_setup(suite)

    # Run the test
    runner.run_test(test)
