"""YAML Conformance Tests.

Discovers and runs all YAML test files bundled in the package.

Run with:
    pytest --pyargs moo_conformance --moo-port=7777
"""

import pytest


_builtin_cache: dict[str, bool] = {}
_feature_cache: set[str] | None = None


def _moo_string_literal(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _has_builtin(runner, builtin: str) -> bool:
    if builtin not in _builtin_cache:
        result = runner.transport.execute(
            f"return function_info({_moo_string_literal(builtin)});"
        )
        _builtin_cache[builtin] = result.success
    return _builtin_cache[builtin]


def _server_features(runner) -> set[str]:
    global _feature_cache
    if _feature_cache is None:
        result = runner.transport.execute('return server_version("features");')
        if result.success and isinstance(result.value, list):
            _feature_cache = {feature for feature in result.value if isinstance(feature, str)}
        else:
            _feature_cache = set()
    return _feature_cache


def _has_feature(runner, feature: str) -> bool:
    return feature in _server_features(runner)


@pytest.mark.conformance
def test_yaml_conformance(runner, yaml_test_case, moo_config):
    """Run a single YAML test case.

    Args:
        runner: YamlTestRunner fixture
        yaml_test_case: (suite, test) tuple from parametrization
        moo_config: dict of available config values for requires.config checks
    """
    suite, test = yaml_test_case

    # Skip tests that are marked as skip
    if test.skip:
        reason = test.skip if isinstance(test.skip, str) else "Test marked as skip"
        pytest.skip(reason)

    # Skip tests based on skip_if condition
    if test.skip_if:
        condition = test.skip_if
        if condition.startswith("not feature."):
            feature = condition[12:]
            if not _has_feature(runner, feature):
                pytest.skip(f"Requires feature: {feature}")
        elif condition.startswith("feature."):
            feature = condition[8:]
            if _has_feature(runner, feature):
                pytest.skip(f"Incompatible with feature: {feature}")
        elif condition.startswith("missing builtin."):
            builtin = condition[16:]
            if not _has_builtin(runner, builtin):
                pytest.skip(f"Requires builtin: {builtin}")
        else:
            pytest.skip(f"Skip condition: {condition}")

    # Skip tests that require config values not provided
    config_option_map = {
        "server_dir": "--moo-server-dir",
        "log_file": "--moo-log-file",
        "managed_server": "--server-command",
    }
    if suite.requires.config:
        for key in suite.requires.config:
            if moo_config.get(key) is None:
                option = config_option_map.get(key, f"--moo-{key.replace('_', '-')}")
                pytest.skip(f"Requires config '{key}' (use {option})")

    # Run suite setup if not already done
    runner.run_suite_setup(suite)

    # Run the test
    runner.run_test(test)
