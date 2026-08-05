"""Regression coverage for exact suite selection and strict skip handling."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from moo_conformance import cli, plugin

pytest_plugins = ("pytester",)


def _write_suite(path: Path, suite_name: str, test_name: str, *, skip: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    skip_line = f"    skip: {skip!r}\n" if skip is not None else ""
    path.write_text(
        f"""name: {suite_name}
tests:
  - name: {test_name}
{skip_line}    code: "1"
    expect:
      value: 1
""",
        encoding="utf-8",
    )


def test_cli_forwards_exact_file_and_directory_selectors(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []

    def capture(args: list[str]) -> int:
        captured.extend(args)
        return 0

    monkeypatch.setattr(cli.pytest, "main", capture)

    result = cli.main(
        [
            "src/moo_conformance/_tests/basic/one.yaml",
            "-q",
            "src/moo_conformance/_tests/language",
        ]
    )

    assert result == 0
    assert captured == [
        "--pyargs",
        "moo_conformance",
        "--moo-suite-path=basic/one.yaml",
        "--moo-suite-path=language",
        "-q",
    ]


def test_exact_yaml_file_does_not_collect_another(tmp_path: Path) -> None:
    tests_dir = tmp_path / "_tests"
    _write_suite(tests_dir / "basic" / "one.yaml", "one", "only_one")
    _write_suite(tests_dir / "basic" / "two.yaml", "two", "not_selected")

    discovered = plugin.discover_yaml_tests(tests_dir, ["basic/one.yaml"])

    assert [(path.name, test.name) for path, _suite, test in discovered] == [
        ("one.yaml", "only_one")
    ]


def test_directory_collects_every_and_only_descendant_suite(tmp_path: Path) -> None:
    tests_dir = tmp_path / "_tests"
    _write_suite(tests_dir / "selected" / "one.yaml", "one", "first")
    _write_suite(tests_dir / "selected" / "nested" / "two.yaml", "two", "second")
    _write_suite(tests_dir / "other" / "three.yaml", "three", "outside")

    discovered = plugin.discover_yaml_tests(tests_dir, ["selected"])

    assert {(path.name, test.name) for path, _suite, test in discovered} == {
        ("one.yaml", "first"),
        ("two.yaml", "second"),
    }


@pytest.mark.parametrize(
    ("contents", "error"),
    [
        pytest.param("name: [", "line 1", id="malformed"),
        pytest.param("", "empty", id="empty"),
        pytest.param("- name: not-a-mapping\n", "mapping", id="non-mapping"),
        pytest.param("tests: []\n", "name", id="invalid-schema"),
        pytest.param("name: missing-tests\n", "tests", id="missing-tests"),
        pytest.param("name: invalid-tests\ntests: {}\n", "list", id="non-list-tests"),
    ],
)
def test_invalid_yaml_suite_fails_discovery_with_source_path(
    tmp_path: Path, contents: str, error: str
) -> None:
    tests_dir = tmp_path / "_tests"
    suite_path = tests_dir / "broken.yaml"
    tests_dir.mkdir()
    suite_path.write_text(contents, encoding="utf-8")

    with pytest.raises(pytest.UsageError) as exc_info:
        plugin.discover_yaml_tests(tests_dir)

    message = str(exc_info.value)
    assert str(suite_path) in message
    assert error in message


def test_invalid_yaml_suite_makes_pytest_collection_exit_nonzero(pytester) -> None:
    suites = pytester.path / "suites"
    suites.mkdir()
    broken = suites / "broken.yaml"
    broken.write_text("name: [", encoding="utf-8")
    pytester.makeconftest(
        "\n".join(
            [
                "from pathlib import Path",
                "from moo_conformance import plugin",
                f"plugin.get_tests_dir = lambda: Path({str(suites)!r})",
            ]
        )
    )
    pytester.makepyfile(
        """
        def test_yaml_conformance(yaml_test_case):
            assert yaml_test_case
        """
    )

    original_get_tests_dir = plugin.get_tests_dir
    try:
        result = pytester.runpytest("-q")
    finally:
        plugin.get_tests_dir = original_get_tests_dir

    assert result.ret != pytest.ExitCode.OK
    result.stdout.fnmatch_lines([f"*{broken}*"])


def test_literal_yaml_skip_remains_allowed(tmp_path: Path) -> None:
    tests_dir = tmp_path / "_tests"
    _write_suite(tests_dir / "literal.yaml", "literal", "allowed", skip="documented")
    [(_path, suite, test)] = plugin.discover_yaml_tests(tests_dir, ["literal.yaml"])
    item = SimpleNamespace(
        callspec=SimpleNamespace(params={"yaml_test_case": (suite, test)})
    )
    report = SimpleNamespace(
        skipped=True,
        outcome="skipped",
        longrepr=("test_conformance.py", 1, "Skipped: documented"),
    )

    plugin._reject_unexpected_runtime_skip(item, report)

    assert report.outcome == "skipped"


@pytest.mark.parametrize(
    ("suite_skip", "test_skip", "reason"),
    [
        (False, "test reason", "test reason"),
        (False, True, "Test marked as skip"),
        ("suite reason", False, "suite reason"),
        (True, False, "Suite marked as skip"),
        ("suite reason", "test reason", "test reason"),
    ],
)
def test_strict_accounting_authorizes_only_emitted_literal_skip_reason(
    suite_skip, test_skip, reason: str
) -> None:
    suite = SimpleNamespace(skip=suite_skip)
    test = SimpleNamespace(skip=test_skip, skip_if=None)
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


@pytest.mark.parametrize("actual_reason", ["other reason", "documented extension"])
def test_literal_skip_does_not_authorize_mismatched_or_prefixed_reason(
    actual_reason: str,
) -> None:
    suite = SimpleNamespace(skip=False)
    test = SimpleNamespace(skip="documented", skip_if=None)
    item = SimpleNamespace(
        callspec=SimpleNamespace(params={"yaml_test_case": (suite, test)})
    )
    report = SimpleNamespace(
        skipped=True,
        outcome="skipped",
        longrepr=("runner.py", 1, f"Skipped: {actual_reason}"),
    )

    plugin._reject_unexpected_runtime_skip(item, report)

    assert report.outcome == "failed"


def test_literal_skip_does_not_authorize_unreachable_requirement_reason() -> None:
    suite = SimpleNamespace(
        skip=False,
        requires=SimpleNamespace(
            builtins=[],
            features=["maps"],
            min_version=None,
            config=[],
        ),
    )
    test = SimpleNamespace(skip="documented", skip_if=None)
    item = SimpleNamespace(
        callspec=SimpleNamespace(params={"yaml_test_case": (suite, test)})
    )
    report = SimpleNamespace(
        skipped=True,
        outcome="skipped",
        longrepr=("runner.py", 1, "Skipped: Requires feature: maps"),
    )

    plugin._reject_unexpected_runtime_skip(item, report)

    assert report.outcome == "failed"


def test_suite_literal_skip_is_collected_as_declared_runtime_skips(pytester) -> None:
    suites = pytester.path / "suites"
    suites.mkdir()
    suite_path = suites / "suite_skip.yaml"
    suite_path.write_text(
        """name: suite_skip
skip: suite is intentionally disabled
tests:
  - name: first
    code: "1"
    expect:
      value: 1
  - name: second
    code: "2"
    expect:
      value: 2
""",
        encoding="utf-8",
    )
    pytester.makeconftest(
        "\n".join(
            [
                "from pathlib import Path",
                "import pytest",
                "from moo_conformance import plugin",
                f"plugin.get_tests_dir = lambda: Path({str(suites)!r})",
                "@pytest.fixture",
                "def runner(): return object()",
                "@pytest.fixture",
                "def moo_config(): return {}",
                "@pytest.fixture",
                "def profile_metadata_gate(): return {}",
            ]
        )
    )
    pytester.makepyfile(
        """
        from moo_conformance.test_conformance import test_yaml_conformance as run_yaml_case

        def test_selected_suite(runner, yaml_test_case, moo_config, profile_metadata_gate):
            run_yaml_case(runner, yaml_test_case, moo_config, profile_metadata_gate)
        """
    )

    original_get_tests_dir = plugin.get_tests_dir
    try:
        result = pytester.runpytest("-q", "--fail-on-unexpected-skip")
    finally:
        plugin.get_tests_dir = original_get_tests_dir

    result.assert_outcomes(skipped=2)


def test_test_literal_skip_reason_takes_precedence_over_suite_skip() -> None:
    suite = SimpleNamespace(skip="suite reason")
    test = SimpleNamespace(skip="test reason")

    with pytest.raises(pytest.skip.Exception, match="test reason"):
        plugin._skip_declared_yaml_case(suite, test)


def test_matching_declared_conditional_skip_remains_allowed() -> None:
    suite = SimpleNamespace(skip=False)
    test = SimpleNamespace(skip=False, skip_if="missing builtin.background_test")
    item = SimpleNamespace(
        callspec=SimpleNamespace(params={"yaml_test_case": (suite, test)})
    )
    report = SimpleNamespace(
        skipped=True,
        outcome="skipped",
        longrepr=("test_conformance.py", 127, "Skipped: Requires builtin: background_test"),
    )

    plugin._reject_unexpected_runtime_skip(item, report)

    assert report.outcome == "skipped"


def test_any_declared_condition_authorizes_its_exact_runtime_reason() -> None:
    suite = SimpleNamespace(skip=False, requires=None)
    test = SimpleNamespace(
        skip=False,
        skip_if="missing builtin.url_encode or not option.OUTBOUND_NETWORK",
        steps=[],
        cleanup=[],
    )
    item = SimpleNamespace(
        callspec=SimpleNamespace(params={"yaml_test_case": (suite, test)})
    )
    report = SimpleNamespace(
        skipped=True,
        outcome="skipped",
        longrepr=("test_conformance.py", 127, "Skipped: Requires option: OUTBOUND_NETWORK"),
    )

    plugin._reject_unexpected_runtime_skip(item, report)

    assert report.outcome == "skipped"


def test_declared_conditional_skip_does_not_allow_unrelated_runtime_skip() -> None:
    suite = SimpleNamespace(skip=False)
    test = SimpleNamespace(skip=False, skip_if="missing builtin.background_test")
    item = SimpleNamespace(
        callspec=SimpleNamespace(params={"yaml_test_case": (suite, test)})
    )
    report = SimpleNamespace(
        skipped=True,
        outcome="skipped",
        longrepr=("runner.py", 1, "Skipped: runtime condition"),
    )

    plugin._reject_unexpected_runtime_skip(item, report)

    assert report.outcome == "failed"


@pytest.mark.parametrize(
    ("reason", "when"),
    [
        ("fixture unavailable", "setup"),
        ("profile unavailable", "setup"),
        ("capability unavailable", "setup"),
        ("runtime condition", "call"),
    ],
)
def test_nonliteral_skip_categories_fail(reason: str, when: str) -> None:
    suite = SimpleNamespace(skip=False)
    test = SimpleNamespace(skip=False, skip_if=None)
    item = SimpleNamespace(
        callspec=SimpleNamespace(params={"yaml_test_case": (suite, test)})
    )
    report = SimpleNamespace(skipped=True, outcome="skipped", longrepr=reason, when=when)

    plugin._reject_unexpected_runtime_skip(item, report)

    assert report.outcome == "failed"
    assert reason in report.longrepr


def test_collection_skip_fails() -> None:
    report = SimpleNamespace(skipped=True, outcome="skipped", longrepr="collection condition")

    plugin._UnexpectedCollectionSkipPlugin().pytest_collectreport(report)

    assert report.outcome == "failed"
    assert "collection condition" in report.longrepr


def test_invalid_skip_condition_makes_packaged_collection_exit_nonzero(pytester) -> None:
    suites = pytester.path / "suites"
    suites.mkdir()
    invalid = suites / "invalid_condition.yaml"
    invalid.write_text(
        """name: invalid_condition
tests:
  - name: invalid
    skip_if: "transport == 'direct'"
    code: "1"
    expect:
      value: 1
""",
        encoding="utf-8",
    )
    pytester.makeconftest(
        "\n".join(
            [
                "from pathlib import Path",
                "from moo_conformance import plugin",
                f"plugin.get_tests_dir = lambda: Path({str(suites)!r})",
            ]
        )
    )
    pytester.makepyfile(
        """
        def test_yaml_conformance(yaml_test_case):
            assert yaml_test_case
        """
    )

    original_get_tests_dir = plugin.get_tests_dir
    try:
        result = pytester.runpytest("-q")
    finally:
        plugin.get_tests_dir = original_get_tests_dir

    assert result.ret != pytest.ExitCode.OK
    result.stdout.fnmatch_lines(["*skip_if*transport == 'direct'*"])


def test_requirement_skip_is_allowed_by_strict_packaged_runner(pytester) -> None:
    suites = pytester.path / "suites"
    suites.mkdir()
    suite_path = suites / "requires_feature.yaml"
    suite_path.write_text(
        """name: requires_feature
requires:
  features: [maps]
tests:
  - name: guarded
    code: "1"
    expect:
      value: 1
""",
        encoding="utf-8",
    )
    pytester.makeconftest(
        "\n".join(
            [
                "from pathlib import Path",
                "from types import SimpleNamespace",
                "import pytest",
                "from moo_conformance import plugin",
                "from moo_conformance.transport import ExecutionResult",
                f"plugin.get_tests_dir = lambda: Path({str(suites)!r})",
                "class FakeTransport:",
                "    def switch_user(self, user): self.current_user = user",
                "    def execute(self, code): return ExecutionResult(True, value=[])",
                "@pytest.fixture",
                "def runner():",
                "    return SimpleNamespace(",
                "        transport=FakeTransport(),",
                "        prepare_suite_environment=lambda suite: None,",
                "    )",
                "@pytest.fixture",
                "def moo_config(): return {}",
                "@pytest.fixture",
                "def profile_metadata_gate(): return {}",
            ]
        )
    )
    pytester.makepyfile(
        """
        from moo_conformance.test_conformance import test_yaml_conformance as run_yaml_case

        def test_selected_suite(runner, yaml_test_case, moo_config, profile_metadata_gate):
            run_yaml_case(runner, yaml_test_case, moo_config, profile_metadata_gate)
        """
    )

    original_get_tests_dir = plugin.get_tests_dir
    try:
        result = pytester.runpytest("-q", "--fail-on-unexpected-skip")
    finally:
        plugin.get_tests_dir = original_get_tests_dir

    result.assert_outcomes(skipped=1)
