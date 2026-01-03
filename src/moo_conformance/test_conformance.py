"""YAML Conformance Tests.

Discovers and runs all YAML test files bundled in the package.

Run with:
    pytest --pyargs moo_conformance --moo-port=7777
"""

import pytest


@pytest.mark.conformance
def test_yaml_conformance(runner, yaml_test_case):
    """Run a single YAML test case.

    Args:
        runner: YamlTestRunner fixture
        yaml_test_case: (suite, test) tuple from parametrization
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
            pytest.skip(f"Requires feature: {feature}")
        elif condition.startswith("feature."):
            feature = condition[8:]
            pytest.skip(f"Incompatible with feature: {feature}")
        elif condition.startswith("missing builtin."):
            builtin = condition[16:]
            pytest.skip(f"Requires builtin: {builtin}")
        else:
            pytest.skip(f"Skip condition: {condition}")

    # Run suite setup if not already done
    runner.run_suite_setup(suite)

    # Run the test
    runner.run_test(test)
