# CLI option selector repair

## Producer and cause

Actual supplied argument:

`--moo-suite-root=/mnt/c/Users/Q/code/moo-conformance-tests/src/moo_conformance/_tests`

`_normalize_suite_selector` scanned every argument as a path. It found `_tests` at the end of this option and returned `.`, causing `_split_suite_selectors` to remove the option and add the full-suite selector. The same defect occurs with the joined Windows spelling.

## RED

Command (Windows, isolated environment outside checkout):

`UV_PROJECT_ENVIRONMENT=C:/Users/Q/.cache/moo-cli-option-windows uv run --frozen pytest tests/test_cli_file_selection.py -k 'test_cli_forwards_option_paths_without_adding_suite_selectors or test_cli_keeps_absolute_bare_suite_selectors' -q`

Raw relevant output:

```text
collected 36 items / 32 deselected / 4 selected
tests\test_cli_file_selection.py FF.. [100%]
At index 2 diff: '--moo-suite-path=.' != '--moo-suite-root=/mnt/c/Users/Q/code/moo-conformance-tests/src/moo_conformance/_tests'
At index 2 diff: '--moo-suite-path=.' != '--moo-suite-root=C:\\Users\\Q\\code\\moo-conformance-tests\\src\\moo_conformance\\_tests'
2 failed, 2 passed, 32 deselected in 0.25s
```

## Change

Return `None` immediately for option tokens starting `-`, preserving their exact spelling and order for pytest. The tests capture `pytest.main` arguments; they do not collect YAML or start a server. Bare absolute POSIX and Windows suite paths remain covered.

## GREEN

Same command after the two-line production fix:

```text
platform win32 -- Python 3.14.8, pytest-9.0.2, pluggy-1.6.0
collected 36 items / 32 deselected / 4 selected
tests\test_cli_file_selection.py .... [100%]
4 passed, 32 deselected in 0.07s
```

Final source/test diff inspected. `git diff --check` produced no output. Two production lines and four parametrized test instances added.

## Limits

This addresses joined option tokens from the real invocation. It does not add a parser for separately valued pytest options. No publication or broad local tests performed.
