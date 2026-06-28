"""Inventory Toast builtin call-shape coverage in YAML suites."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

import yaml

from .builtin_io_generator import BuiltinSpec, extract_builtin_specs
from .schema import MooTestCase, MooTestSuite, SetupTeardown, TestStep, validate_test_suite


@dataclass(frozen=True, order=True)
class BuiltinCall:
    name: str
    arity: int
    arg_types: tuple[str, ...]
    path: str
    context: str


@dataclass(frozen=True, order=True)
class RequiredShape:
    arity: int
    arg_types: tuple[str, ...]


@dataclass
class BuiltinCoverage:
    spec: BuiltinSpec
    required_shapes: list[RequiredShape]
    calls_by_shape: dict[RequiredShape, list[BuiltinCall]] = field(default_factory=dict)
    unknown_calls_by_arity: dict[int, list[BuiltinCall]] = field(default_factory=dict)

    @property
    def covered_shapes(self) -> list[RequiredShape]:
        return [shape for shape in self.required_shapes if self.calls_by_shape.get(shape)]

    @property
    def missing_shapes(self) -> list[RequiredShape]:
        return [shape for shape in self.required_shapes if not self.calls_by_shape.get(shape)]


def generate_builtin_coverage_report(
    toast_src: str | Path,
    tests_dir: str | Path,
    out_path: str | Path,
) -> Path:
    """Write a Markdown checklist for current Toast builtin call-shape coverage."""
    toast_path = Path(toast_src)
    tests_path = Path(tests_dir)
    output_path = Path(out_path)

    specs = extract_builtin_specs(toast_path, include_excluded=True)
    calls = collect_builtin_calls(tests_path, {spec.name for spec in specs})
    coverage = build_coverage(specs, calls)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_markdown_report(toast_path, tests_path, coverage),
        encoding="utf-8",
    )
    return output_path


def collect_builtin_calls(test_root: Path, builtin_names: set[str]) -> list[BuiltinCall]:
    """Collect builtin calls from expanded YAML suites."""
    calls: list[BuiltinCall] = []
    for path in sorted(test_root.rglob("*.yaml")):
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                continue
            suite = validate_test_suite(raw)
        except Exception as exc:
            raise RuntimeError(f"Failed to load YAML suite for builtin coverage: {path}") from exc

        rel_path = path.relative_to(test_root).as_posix()
        for context, code in _suite_code_fragments(suite):
            for name, arity, arg_types in iter_builtin_calls(code, builtin_names):
                calls.append(
                    BuiltinCall(
                        name=name,
                        arity=arity,
                        arg_types=arg_types,
                        path=rel_path,
                        context=context,
                    )
                )
    return calls


def build_coverage(
    specs: Iterable[BuiltinSpec],
    calls: Iterable[BuiltinCall],
) -> list[BuiltinCoverage]:
    calls_by_name: dict[str, list[BuiltinCall]] = {}
    for call in calls:
        calls_by_name.setdefault(call.name, []).append(call)

    items: list[BuiltinCoverage] = []
    for spec in sorted(specs, key=lambda item: item.name):
        item = BuiltinCoverage(spec=spec, required_shapes=required_shapes(spec))
        for call in calls_by_name.get(spec.name, []):
            if "unknown" in call.arg_types:
                item.unknown_calls_by_arity.setdefault(call.arity, []).append(call)
                continue
            shape = RequiredShape(call.arity, call.arg_types)
            item.calls_by_shape.setdefault(shape, []).append(call)
        items.append(item)
    return items


def render_markdown_report(
    toast_src: Path,
    tests_dir: Path,
    coverage: list[BuiltinCoverage],
) -> str:
    total = sum(len(item.required_shapes) for item in coverage)
    covered = sum(len(item.covered_shapes) for item in coverage)
    missing_items = [item for item in coverage if item.missing_shapes]
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    lines = [
        "# Toast Builtin Call-Shape Coverage",
        "",
        f"- generated_at: `{timestamp}`",
        f"- toast_source: `{toast_src}`",
        f"- conformance_tests: `{tests_dir}`",
        "- generator_command: "
        "`uv run moo-conformance --generate-builtin-coverage-report --toast-src <toast> "
        "--tests-dir <tests> --out <report>`",
        f"- builtins: `{len(coverage)}`",
        f"- required_call_shapes: `{total}`",
        f"- covered_call_shapes: `{covered}`",
        f"- missing_call_shapes: `{total - covered}`",
        "",
        "A call shape is a builtin arity plus concrete argument types. `TYPE_ANY`",
        "and `TYPE_NUMERIC` registrations expand into concrete type permutations.",
        "Calls through variables or complex expressions are listed as unknown and",
        "do not count as covering a concrete type permutation.",
        "",
        "Variadic signatures (`maxargs == -1`) currently require the minimum arity",
        "and one extra arity as a smoke sample; behavior-specific variadic expansion",
        "still needs explicit human review.",
        "",
        "## Missing Call-Shape Checklist",
        "",
    ]

    if not missing_items:
        lines.extend(["All required call shapes have at least one YAML call.", ""])
    else:
        for item in missing_items:
            lines.append(f"- `{item.spec.name}` signature `{_signature(item.spec)}`")
            for shape in item.missing_shapes:
                lines.append(f"  - [ ] `{_format_shape(item.spec.name, shape)}`")
        lines.append("")

    lines.extend(["## Full Builtin Checklist", ""])
    for item in coverage:
        lines.append(f"### `{item.spec.name}`")
        lines.append("")
        lines.append(f"- signature: `{_signature(item.spec)}`")
        lines.append(f"- source: `{Path(item.spec.registration_file).name}`")
        for shape in item.required_shapes:
            checked = "x" if item.calls_by_shape.get(shape) else " "
            sites = _format_sites(item.calls_by_shape.get(shape, []))
            lines.append(f"- [{checked}] `{_format_shape(item.spec.name, shape)}` {sites}".rstrip())
        for arity, calls in sorted(item.unknown_calls_by_arity.items()):
            lines.append(
                f"- [?] `{item.spec.name}/{arity}` unknown argument types "
                f"{_format_sites(calls)}".rstrip()
            )
        lines.append("")

    return "\n".join(lines)


def iter_builtin_calls(
    code: str,
    builtin_names: set[str],
) -> Iterable[tuple[str, int, tuple[str, ...]]]:
    """Yield builtin calls with arity and literal argument types."""
    index = 0
    while index < len(code):
        char = code[index]
        if char == '"':
            index = _skip_string(code, index + 1)
            continue
        if _is_ident_start(char):
            start = index
            index += 1
            while index < len(code) and _is_ident_part(code[index]):
                index += 1
            name = code[start:index]
            open_paren = _skip_ws(code, index)
            if name in builtin_names and open_paren < len(code) and code[open_paren] == "(":
                close_paren = _find_matching_paren(code, open_paren)
                if close_paren is not None:
                    args = _split_args(code[open_paren + 1:close_paren])
                    yield name, len(args), tuple(_infer_arg_type(arg) for arg in args)
                    index = close_paren + 1
                    continue
            continue
        index += 1


def required_shapes(spec: BuiltinSpec) -> list[RequiredShape]:
    """Return the required concrete call shapes for a Toast builtin signature."""
    if spec.maxargs < 0:
        arities = [spec.minargs, spec.minargs + 1]
    else:
        arities = list(range(spec.minargs, spec.maxargs + 1))

    shapes: list[RequiredShape] = []
    for arity in arities:
        patterns: list[tuple[str, ...]] = [()]
        for index in range(arity):
            token = spec.prototype_tokens[index] if index < len(spec.prototype_tokens) else "TYPE_ANY"
            patterns = [
                pattern + (type_name,)
                for pattern in patterns
                for type_name in _concrete_types(token)
            ]
        shapes.extend(RequiredShape(arity, pattern) for pattern in patterns)
    return shapes


def _suite_code_fragments(suite: MooTestSuite) -> Iterable[tuple[str, str]]:
    yield from _setup_teardown_fragments("suite.setup", suite.setup)
    yield from _setup_teardown_fragments("suite.teardown", suite.teardown)
    for test in suite.tests:
        yield from _test_code_fragments(test)


def _test_code_fragments(test: MooTestCase) -> Iterable[tuple[str, str]]:
    yield from _setup_teardown_fragments(f"{test.name}.setup", test.setup)
    yield from _setup_teardown_fragments(f"{test.name}.teardown", test.teardown)
    if test.code or test.statement or test.verb:
        try:
            yield test.name, test.get_code_to_execute()
        except ValueError:
            pass
    if test.expect.satisfies:
        yield f"{test.name}.expect.satisfies", test.expect.satisfies
    for index, step in enumerate(test.steps):
        yield from _step_code_fragments(f"{test.name}.steps[{index}]", step)
    for index, step in enumerate(test.cleanup):
        yield from _step_code_fragments(f"{test.name}.cleanup[{index}]", step)


def _setup_teardown_fragments(prefix: str, item: SetupTeardown | None) -> Iterable[tuple[str, str]]:
    if item is None:
        return
    for index, line in enumerate(item.code_lines):
        yield f"{prefix}[{index}]", line


def _step_code_fragments(prefix: str, step: TestStep) -> Iterable[tuple[str, str]]:
    if step.run:
        yield prefix, step.run
    if step.command:
        yield f"{prefix}.command", step.command
    if step.verb_setup:
        yield f"{prefix}.verb_setup", step.verb_setup.code
    if step.expect and step.expect.satisfies:
        yield f"{prefix}.expect.satisfies", step.expect.satisfies


def _concrete_types(token: str) -> list[str]:
    if token == "TYPE_ANY":
        return ["int", "float", "obj", "str", "err", "list", "map"]
    if token == "TYPE_NUMERIC":
        return ["int", "float"]
    return {
        "TYPE_INT": ["int"],
        "TYPE_OBJ": ["obj"],
        "TYPE_ERR": ["err"],
        "TYPE_BOOL": ["bool"],
        "TYPE_STR": ["str"],
        "_TYPE_STR": ["str"],
        "TYPE_LIST": ["list"],
        "_TYPE_LIST": ["list"],
        "TYPE_FLOAT": ["float"],
        "_TYPE_FLOAT": ["float"],
        "TYPE_MAP": ["map"],
        "_TYPE_MAP": ["map"],
        "TYPE_ANON": ["anon"],
        "_TYPE_ANON": ["anon"],
        "TYPE_WAIF": ["waif"],
        "_TYPE_WAIF": ["waif"],
        "TYPE_ITER": ["iter"],
        "_TYPE_ITER": ["iter"],
    }.get(token, ["unknown"])


def _signature(spec: BuiltinSpec) -> str:
    maxargs = "*" if spec.maxargs < 0 else str(spec.maxargs)
    return f"{spec.minargs}..{maxargs} ({', '.join(spec.prototype_names)})"


def _format_shape(name: str, shape: RequiredShape) -> str:
    if not shape.arg_types:
        return f"{name}/0 ()"
    return f"{name}/{shape.arity} ({', '.join(shape.arg_types)})"


def _format_sites(calls: list[BuiltinCall]) -> str:
    if not calls:
        return ""
    sites = [f"`{call.path}`" for call in sorted(calls)[:3]]
    suffix = "" if len(calls) <= 3 else f" and {len(calls) - 3} more"
    return "covered by " + ", ".join(sites) + suffix


def _infer_arg_type(arg: str) -> str:
    value = arg.strip()
    if not value:
        return "unknown"
    if value.startswith('"') and value.endswith('"'):
        return "str"
    if value.startswith("#") and _is_int(value[1:]):
        return "obj"
    if value.startswith("E_") and value.replace("_", "").isalnum():
        return "err"
    if value.startswith("{") and value.endswith("}"):
        return "list"
    if value.startswith("[") and value.endswith("]"):
        return "map"
    if _is_int(value):
        return "int"
    if _is_float(value):
        return "float"
    return "unknown"


def _split_args(arg_text: str) -> list[str]:
    if not arg_text.strip():
        return []

    args: list[str] = []
    start = 0
    depth = 0
    index = 0
    while index < len(arg_text):
        char = arg_text[index]
        if char == '"':
            index = _skip_string(arg_text, index + 1)
            continue
        if char in "({[":
            depth += 1
        elif char in ")}]":
            depth -= 1
        elif char == "," and depth == 0:
            args.append(arg_text[start:index].strip())
            start = index + 1
        index += 1
    args.append(arg_text[start:].strip())
    return args


def _is_ident_start(char: str) -> bool:
    return char.isalpha() or char == "_"


def _is_ident_part(char: str) -> bool:
    return char.isalnum() or char == "_"


def _skip_ws(code: str, index: int) -> int:
    while index < len(code) and code[index].isspace():
        index += 1
    return index


def _skip_string(code: str, index: int) -> int:
    while index < len(code):
        if code[index] == "\\":
            index += 2
            continue
        if code[index] == '"':
            return index + 1
        index += 1
    return index


def _find_matching_paren(code: str, open_index: int) -> int | None:
    depth = 0
    index = open_index
    while index < len(code):
        char = code[index]
        if char == '"':
            index = _skip_string(code, index + 1)
            continue
        if char in "({[":
            depth += 1
        elif char in ")}]":
            depth -= 1
            if depth == 0 and char == ")":
                return index
        index += 1
    return None


def _is_int(value: str) -> bool:
    if value.startswith(("-", "+")):
        value = value[1:]
    return value.isdigit()


def _is_float(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return any(char in value for char in ".eE")
