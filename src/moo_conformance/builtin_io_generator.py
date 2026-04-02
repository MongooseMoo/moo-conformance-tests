"""Generate builtin I/O YAML inventories from Toast source."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import ast
import re

from pycparser import c_ast, c_parser
import yaml


TYPE_NAME_MAP = {
    "TYPE_ANY": "any",
    "TYPE_NUMERIC": "numeric",
    "TYPE_INT": "int",
    "TYPE_OBJ": "obj",
    "_TYPE_STR": "str",
    "TYPE_STR": "str",
    "TYPE_ERR": "err",
    "_TYPE_LIST": "list",
    "TYPE_LIST": "list",
    "_TYPE_FLOAT": "float",
    "TYPE_FLOAT": "float",
    "_TYPE_MAP": "map",
    "TYPE_MAP": "map",
    "_TYPE_ITER": "iter",
    "TYPE_ITER": "iter",
    "_TYPE_ANON": "anon",
    "TYPE_ANON": "anon",
    "_TYPE_WAIF": "waif",
    "TYPE_WAIF": "waif",
    "TYPE_BOOL": "bool",
}

TYPE_CODE_MAP = {
    "TYPE_ANY": -1,
    "TYPE_NUMERIC": -2,
    "TYPE_INT": 0,
    "TYPE_OBJ": 1,
    "_TYPE_STR": 2,
    "TYPE_STR": 2,
    "TYPE_ERR": 3,
    "_TYPE_LIST": 4,
    "TYPE_LIST": 4,
    "_TYPE_FLOAT": 9,
    "TYPE_FLOAT": 9,
    "_TYPE_MAP": 10,
    "TYPE_MAP": 10,
    "_TYPE_ITER": 11,
    "TYPE_ITER": 11,
    "_TYPE_ANON": 12,
    "TYPE_ANON": 12,
    "_TYPE_WAIF": 13,
    "TYPE_WAIF": 13,
    "TYPE_BOOL": 14,
}

VAR_HELPER_TYPES = {
    "VAR_NEW_INT": "int",
    "VAR_NEW_FLOAT": "float",
    "VAR_NEW_OBJ": "obj",
    "VAR_NEW_ANON": "anon",
    "VAR_NEW_WAIF": "waif",
    "VAR_NEW_BOOL": "bool",
    "new_waif": "waif",
    "new_list": "list",
    "new_map": "map",
    "str_dup_to_var": "str",
    "str_ref_to_var": "str",
}

VALID_WITNESS_MAP = {
    "TYPE_ANY": "1",
    "TYPE_NUMERIC": "1",
    "TYPE_INT": "1",
    "TYPE_OBJ": "#0",
    "_TYPE_STR": '"x"',
    "TYPE_STR": '"x"',
    "TYPE_ERR": "E_ARGS",
    "_TYPE_LIST": "{}",
    "TYPE_LIST": "{}",
    "_TYPE_FLOAT": "1.5",
    "TYPE_FLOAT": "1.5",
    "_TYPE_MAP": "[1 -> 2]",
    "TYPE_MAP": "[1 -> 2]",
}

INVALID_WITNESS_MAP = {
    "TYPE_NUMERIC": '"x"',
    "TYPE_INT": '"x"',
    "TYPE_OBJ": '"x"',
    "_TYPE_STR": "1",
    "TYPE_STR": "1",
    "TYPE_ERR": "1",
    "_TYPE_LIST": "1",
    "TYPE_LIST": "1",
    "_TYPE_FLOAT": '"x"',
    "TYPE_FLOAT": '"x"',
    "_TYPE_MAP": "1",
    "TYPE_MAP": "1",
}

MOO_TYPE_CONST_MAP = {
    "int": "INT",
    "float": "FLOAT",
    "obj": "OBJ",
    "anon": "ANON",
    "waif": "WAIF",
    "str": "STR",
    "err": "ERR",
    "list": "LIST",
    "map": "MAP",
    "bool": "BOOL",
}

EXCLUDED_SOURCE_ONLY_BUILTINS = {
    "anon",
    "background_test",
    "curl",
    "finished_tasks",
    "malloc_stats",
    "read_stdin",
    "spellcheck",
    "url_decode",
    "url_encode",
}

EXCLUDED_GENERATED_BUILTINS = {
    "chparent",
    "chparents",
    "generate_json",
    "shutdown",
    "simplex_noise",
}

EXCLUDED_RUNTIME_OUTCOME_BUILTINS = {
    "add_property",
    "clear_property",
    "delete_property",
    "delete_verb",
    "kill_task",
    "resume",
    "set_connection_option",
    "set_property_info",
    "set_verb_args",
    "set_verb_info",
    "unlisten",
}


@dataclass
class BuiltinSpec:
    """Extracted builtin signature and inferred output metadata."""

    name: str
    implementation: str
    registration_kind: str
    minargs: int
    maxargs: int
    prototype_tokens: list[str]
    prototype_names: list[str]
    prototype_codes: list[int]
    registration_file: str
    success_types: list[str] = field(default_factory=list)
    raised_errors: list[str] = field(default_factory=list)
    unresolved_returns: list[str] = field(default_factory=list)
    implementation_file: str | None = None


def generate_builtin_io_yamls(
    toast_src: str | Path,
    out_dir: str | Path,
    *,
    overwrite: bool = False,
) -> list[Path]:
    """Generate one runnable YAML conformance suite per builtin."""
    source_root = _resolve_toast_src(Path(toast_src))
    output_root = Path(out_dir)

    if output_root.exists() and any(output_root.iterdir()) and not overwrite:
        raise FileExistsError(f"Output directory is not empty: {output_root}")

    output_root.mkdir(parents=True, exist_ok=True)

    specs = extract_builtin_specs(source_root)
    generated: list[Path] = []

    for spec in specs:
        yaml_path = output_root / f"{spec.name}.yaml"
        yaml_path.write_text(render_builtin_yaml(spec), encoding="utf-8")
        generated.append(yaml_path)

    return generated


def extract_builtin_specs(source_root: str | Path) -> list[BuiltinSpec]:
    """Extract builtin registrations and emitted type metadata."""
    root = _resolve_toast_src(Path(source_root))
    source_files = _source_files(root)
    implementations = _collect_implementations(source_files)
    specs: list[BuiltinSpec] = []

    for path in source_files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for kind, call_text in _find_registration_calls(text):
            spec = _parse_registration(path, kind, call_text, implementations)
            if spec is not None:
                if spec.name in EXCLUDED_SOURCE_ONLY_BUILTINS:
                    continue
                if spec.name in EXCLUDED_GENERATED_BUILTINS:
                    continue
                specs.append(spec)

    specs.sort(key=lambda item: item.name)
    return specs


def render_builtin_yaml(spec: BuiltinSpec) -> str:
    """Render one generated YAML conformance suite."""
    suite = {
        "name": f"generated_builtin_signature_{spec.name}",
        "description": (
            f"Generated conformance tests for {spec.name}() builtin signature, "
            f"derived from Toast source."
        ),
        "requires": {"builtins": ["function_info", spec.name]},
        "tests": _build_tests(spec),
    }
    header = (
        f"# Generated from actual Toast source for builtin {spec.name}().\n"
        "# This file is a runnable moo-conformance suite.\n"
        "# Registration signatures are parsed with pycparser from Toast register_function(...) calls.\n"
        f"# registration_kind: {spec.registration_kind}\n"
        f"# registration_file: {spec.registration_file}\n"
        f"# implementation: {spec.implementation}\n"
        f"# implementation_file: {spec.implementation_file}\n"
        f"# arg_type_tokens: {spec.prototype_tokens}\n"
        f"# arg_type_names: {spec.prototype_names}\n"
        f"# arg_type_codes: {spec.prototype_codes}\n"
        f"# inferred_success_type_names: {spec.success_types}\n"
        f"# inferred_raised_error_codes: {spec.raised_errors}\n"
        f"# unresolved_returns: {spec.unresolved_returns}\n"
    )
    return header + yaml.safe_dump(suite, sort_keys=False, allow_unicode=False)


def _build_tests(spec: BuiltinSpec) -> list[dict[str, object]]:
    tests: list[dict[str, object]] = [
        {
            "name": f"{spec.name}_function_info_signature_matches_source",
            "permission": "wizard",
            "code": f'function_info("{spec.name}")',
            "expect": {
                "value": [spec.name, spec.minargs, spec.maxargs, spec.prototype_codes],
            },
        }
    ]

    if spec.minargs > 0:
        tests.append(
            {
                "name": f"{spec.name}_too_few_args",
                "permission": "wizard",
                "code": _call_expr(spec.name, []),
                "expect": {"error": "E_ARGS"},
            }
        )

    if spec.maxargs >= 0:
        too_many_args = _build_valid_args(spec, spec.maxargs)
        if too_many_args is not None:
            too_many_args.append("1")
            tests.append(
                {
                    "name": f"{spec.name}_too_many_args",
                    "permission": "wizard",
                    "code": _call_expr(spec.name, too_many_args),
                    "expect": {"error": "E_ARGS"},
                }
            )

    for index, token in enumerate(spec.prototype_tokens):
        if token == "TYPE_ANY":
            continue
        invalid = INVALID_WITNESS_MAP.get(token)
        if invalid is None:
            continue
        argc = max(spec.minargs, index + 1)
        args = _build_valid_args(spec, argc)
        if args is None:
            continue
        args[index] = invalid
        tests.append(
            {
                "name": f"{spec.name}_arg_{index + 1}_rejects_wrong_type",
                "permission": "wizard",
                "code": _call_expr(spec.name, args),
                "expect": {"error": "E_TYPE"},
            }
        )

    runtime_test = _build_runtime_outcome_test(spec)
    if runtime_test is not None:
        tests.append(runtime_test)

    return tests


def _build_runtime_outcome_test(spec: BuiltinSpec) -> dict[str, object] | None:
    if spec.name in EXCLUDED_RUNTIME_OUTCOME_BUILTINS:
        return None
    if not spec.success_types:
        return None
    if any(type_name not in MOO_TYPE_CONST_MAP for type_name in spec.success_types):
        return None

    args = _build_valid_args(spec, spec.minargs)
    if args is None:
        return None

    success_checks = " || ".join(
        f"typeof(result) == {MOO_TYPE_CONST_MAP[type_name]}"
        for type_name in spec.success_types
    )
    error_codes = [code for code in spec.raised_errors if code.startswith("E_")]

    lines = [
        "try",
        f"  result = {_call_expr(spec.name, args)};",
        f"  return {success_checks};",
    ]
    if error_codes:
        codes = ", ".join(error_codes)
        lines.extend(
            [
                f"except e ({codes})",
                "  return 1;",
            ]
        )
    else:
        lines.extend(
            [
                "except e (ANY)",
                "  return 0;",
            ]
        )
    lines.append("endtry")

    return {
        "name": f"{spec.name}_runtime_outcome_matches_inferred_types",
        "permission": "wizard",
        "statement": "\n".join(lines) + "\n",
        "expect": {"value": 1},
    }


def _build_valid_args(spec: BuiltinSpec, argc: int) -> list[str] | None:
    args: list[str] = []
    for index in range(argc):
        token = spec.prototype_tokens[index] if index < len(spec.prototype_tokens) else "TYPE_ANY"
        witness = VALID_WITNESS_MAP.get(token)
        if witness is None:
            return None
        args.append(witness)
    return args


def _call_expr(name: str, args: list[str]) -> str:
    return f"{name}(" + ", ".join(args) + ")"


def _resolve_toast_src(path: Path) -> Path:
    if path.name == "src" and path.is_dir():
        return path
    candidate = path / "src"
    if candidate.is_dir():
        return candidate
    raise FileNotFoundError(f"Could not find Toast src directory under {path}")


def _source_files(source_root: Path) -> list[Path]:
    files: list[Path] = []
    for path in source_root.rglob("*"):
        if path.suffix not in {".cc", ".c"}:
            continue
        if any(part in {"dependencies", "include"} for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def _find_registration_calls(text: str) -> list[tuple[str, str]]:
    calls: list[tuple[str, str]] = []
    pattern = re.compile(r"\b(register_function(?:_with_read_write)?)\s*\(")
    for match in pattern.finditer(text):
        open_paren = match.end() - 1
        close_paren = _find_matching(text, open_paren, "(", ")")
        call_text = match.group(1) + "(" + text[open_paren + 1:close_paren] + ")"
        calls.append((match.group(1), call_text))
    return calls


def _parse_registration(
    path: Path,
    kind: str,
    call_text: str,
    implementations: dict[str, tuple[str, str]],
) -> BuiltinSpec | None:
    parser = c_parser.CParser()
    try:
        ast_root = parser.parse(_registration_translation_unit(call_text))
    except Exception:
        return None

    visitor = _RegistrationVisitor()
    visitor.visit(ast_root)
    if len(visitor.calls) != 1:
        return None

    call = visitor.calls[0]
    spec = BuiltinSpec(
        name=call["name"],
        implementation=call["implementation"],
        registration_kind=kind,
        minargs=call["minargs"],
        maxargs=call["maxargs"],
        prototype_tokens=call["prototype_tokens"],
        prototype_names=[_type_name(token) for token in call["prototype_tokens"]],
        prototype_codes=[_type_code(token) for token in call["prototype_tokens"]],
        registration_file=str(path),
    )

    implementation = implementations.get(spec.implementation)
    if implementation is None:
        spec.unresolved_returns = ["implementation body not found"]
        return spec

    spec.implementation_file = implementation[0]
    spec.success_types, spec.raised_errors, spec.unresolved_returns = _infer_body_effects(
        implementation[1]
    )
    return spec


def _registration_translation_unit(call_text: str) -> str:
    return (
        "typedef int Byte; typedef int Objid; typedef int Var; typedef int package;\n"
        "int TYPE_ANY; int TYPE_NUMERIC; int TYPE_INT; int TYPE_OBJ; int _TYPE_STR; int TYPE_STR;\n"
        "int TYPE_ERR; int _TYPE_LIST; int TYPE_LIST; int _TYPE_FLOAT; int TYPE_FLOAT;\n"
        "int _TYPE_MAP; int TYPE_MAP; int _TYPE_ITER; int TYPE_ITER; int _TYPE_ANON; int TYPE_ANON;\n"
        "int _TYPE_WAIF; int TYPE_WAIF; int TYPE_BOOL;\n"
        "package register_function(); package register_function_with_read_write();\n"
        "void probe(void) { " + call_text + "; }\n"
    )


class _RegistrationVisitor(c_ast.NodeVisitor):
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def visit_FuncCall(self, node: c_ast.FuncCall) -> None:
        if not isinstance(node.name, c_ast.ID):
            return
        if node.name.name not in {"register_function", "register_function_with_read_write"}:
            return
        args = node.args.exprs if isinstance(node.args, c_ast.ExprList) else []
        if node.name.name == "register_function":
            if len(args) < 4:
                return
            type_start = 4
        else:
            if len(args) < 6:
                return
            type_start = 6

        self.calls.append(
            {
                "name": _string_literal(args[0]),
                "minargs": _int_literal(args[1]),
                "maxargs": _int_literal(args[2]),
                "implementation": _expr_text(args[3]),
                "prototype_tokens": [_expr_text(arg) for arg in args[type_start:]],
            }
        )


def _collect_implementations(source_files: list[Path]) -> dict[str, tuple[str, str]]:
    implementations: dict[str, tuple[str, str]] = {}
    for path in source_files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for name, body in _find_function_bodies(text):
            implementations.setdefault(name, (str(path), body))
    return implementations


def _find_function_bodies(text: str) -> list[tuple[str, str]]:
    bodies: list[tuple[str, str]] = []
    pattern = re.compile(r"\b(bf_[A-Za-z_]\w*)\s*\(")
    for match in pattern.finditer(text):
        open_paren = match.end() - 1
        close_paren = _find_matching(text, open_paren, "(", ")")
        brace_pos = _skip_ws(text, close_paren + 1)
        if brace_pos >= len(text) or text[brace_pos] != "{":
            continue
        close_brace = _find_matching(text, brace_pos, "{", "}")
        bodies.append((match.group(1), text[brace_pos + 1:close_brace]))
    return bodies


def _infer_body_effects(body: str) -> tuple[list[str], list[str], list[str]]:
    tracker = _BodyTracker()
    parser = c_parser.CParser()

    for statement in _candidate_statements(body):
        normalized = _normalize_statement(statement)
        try:
            ast_root = parser.parse(_statement_translation_unit(normalized))
        except Exception:
            tracker.unresolved_returns.add(statement.strip())
            continue
        tracker.visit(ast_root)

    return (
        sorted(tracker.success_types),
        sorted(tracker.raised_errors),
        sorted(tracker.unresolved_returns),
    )


def _candidate_statements(body: str) -> list[str]:
    patterns = [
        r"(?:^|[\r\n])[ \t]*(?:if\s*\([^;{}]*\)\s*)?return\s+.*?;",
        r"(?:^|[\r\n])[ \t]*[A-Za-z_]\w*\.type\s*=\s*[A-Z_][A-Z0-9_]*\s*;",
        r"(?:^|[\r\n])[ \t]*(?:[A-Za-z_]\w*\s+)?[A-Za-z_]\w*\s*=\s*(?:new_list|new_map|str_dup_to_var|str_ref_to_var|Var::new_[A-Za-z_]+|new_waif)\s*\(.*?\)\s*;",
    ]
    statements: list[str] = []
    for pattern in patterns:
        statements.extend(match.group(0).strip() for match in re.finditer(pattern, body, flags=re.S))
    deduped: list[str] = []
    seen: set[str] = set()
    for statement in statements:
        if statement not in seen:
            seen.add(statement)
            deduped.append(statement)
    return deduped


def _normalize_statement(statement: str) -> str:
    normalized = statement
    normalized = normalized.replace("nullptr", "0")
    normalized = re.sub(r"\bVar::new_(int|float|obj|anon|waif|bool)\s*\(", lambda m: f"VAR_NEW_{m.group(1).upper()}(", normalized)
    return normalized


def _statement_translation_unit(statement: str) -> str:
    return (
        "typedef int Var; typedef int package; typedef int Byte; typedef int Objid;\n"
        "int TYPE_ANY; int TYPE_NUMERIC; int TYPE_INT; int TYPE_OBJ; int TYPE_STR; int TYPE_ERR;\n"
        "int TYPE_LIST; int TYPE_FLOAT; int TYPE_MAP; int TYPE_ITER; int TYPE_ANON; int TYPE_WAIF; int TYPE_BOOL;\n"
        "int E_NONE; int E_TYPE; int E_DIV; int E_PERM; int E_PROPNF; int E_VERBNF; int E_VARNF; int E_INVIND;\n"
        "int E_RECMOVE; int E_MAXREC; int E_RANGE; int E_ARGS; int E_NACC; int E_INVARG; int E_QUOTA; int E_FLOAT;\n"
        "int E_FILE; int E_EXEC; int E_INTRPT;\n"
        "package make_var_pack(); package make_int_pack(); package make_float_pack(); package no_var_pack();\n"
        "package make_error_pack(); package make_raise_pack(); package make_x_not_found_pack();\n"
        "Var new_list(); Var new_map(); Var str_dup_to_var(); Var str_ref_to_var(); Var var_ref(); Var new_waif();\n"
        "Var VAR_NEW_INT(); Var VAR_NEW_FLOAT(); Var VAR_NEW_OBJ(); Var VAR_NEW_ANON(); Var VAR_NEW_WAIF(); Var VAR_NEW_BOOL();\n"
        "int zero; int nothing;\n"
        "void probe(void) { " + statement + " }\n"
    )


class _BodyTracker(c_ast.NodeVisitor):
    def __init__(self) -> None:
        self.assignments: dict[str, set[str]] = {"zero": {"int"}, "nothing": {"obj"}}
        self.success_types: set[str] = set()
        self.raised_errors: set[str] = set()
        self.unresolved_returns: set[str] = set()

    def visit_Decl(self, node: c_ast.Decl) -> None:
        if node.init is not None and isinstance(node.name, str):
            inferred = self._infer_value_type(node.init)
            if inferred is not None:
                self.assignments.setdefault(node.name, set()).add(inferred)
        self.generic_visit(node)

    def visit_Assignment(self, node: c_ast.Assignment) -> None:
        if isinstance(node.lvalue, c_ast.StructRef) and node.lvalue.type == ".":
            if isinstance(node.lvalue.name, c_ast.ID) and isinstance(node.lvalue.field, c_ast.ID):
                if node.lvalue.field.name == "type":
                    inferred = self._type_from_expr(node.rvalue)
                    if inferred is not None:
                        self.assignments.setdefault(node.lvalue.name.name, set()).add(inferred)
        elif isinstance(node.lvalue, c_ast.ID):
            inferred = self._infer_value_type(node.rvalue)
            if inferred is not None:
                self.assignments.setdefault(node.lvalue.name, set()).add(inferred)
        self.generic_visit(node)

    def visit_Return(self, node: c_ast.Return) -> None:
        if node.expr is None:
            return
        if not isinstance(node.expr, c_ast.FuncCall):
            self.unresolved_returns.add(_expr_text(node.expr))
            return
        func_name = _call_name(node.expr)
        if func_name == "make_var_pack":
            arg = _first_call_arg(node.expr)
            inferred = self._infer_value_type(arg)
            if inferred is None:
                self.unresolved_returns.add(_expr_text(node.expr))
            else:
                self.success_types.add(inferred)
        elif func_name == "make_int_pack" or func_name == "no_var_pack":
            self.success_types.add("int")
        elif func_name == "make_float_pack":
            self.success_types.add("float")
        elif func_name in {"make_error_pack", "make_raise_pack", "make_x_not_found_pack"}:
            arg = _first_call_arg(node.expr)
            error_name = _expr_text(arg)
            if error_name.startswith("E_"):
                self.raised_errors.add(error_name)
            else:
                self.unresolved_returns.add(_expr_text(node.expr))
        else:
            self.unresolved_returns.add(_expr_text(node.expr))

    def _infer_value_type(self, expr: c_ast.Node | None) -> str | None:
        if expr is None:
            return None
        if isinstance(expr, c_ast.ID):
            values = self.assignments.get(expr.name)
            if values and len(values) == 1:
                return next(iter(values))
            return None
        if isinstance(expr, c_ast.Constant):
            if expr.type == "string":
                return "str"
            if expr.type in {"int", "char"}:
                return "int"
            if expr.type in {"double", "float"}:
                return "float"
        if isinstance(expr, c_ast.FuncCall):
            func_name = _call_name(expr)
            if func_name == "var_ref":
                return self._infer_value_type(_first_call_arg(expr))
            return VAR_HELPER_TYPES.get(func_name)
        return None

    def _type_from_expr(self, expr: c_ast.Node) -> str | None:
        token = _expr_text(expr)
        if token in TYPE_NAME_MAP:
            return TYPE_NAME_MAP[token]
        return None


def _call_name(node: c_ast.FuncCall) -> str:
    if isinstance(node.name, c_ast.ID):
        return node.name.name
    return _expr_text(node.name)


def _first_call_arg(node: c_ast.FuncCall) -> c_ast.Node | None:
    if isinstance(node.args, c_ast.ExprList) and node.args.exprs:
        return node.args.exprs[0]
    return None


def _string_literal(node: c_ast.Node) -> str:
    if isinstance(node, c_ast.Constant) and node.type == "string":
        return ast.literal_eval(node.value)
    raise ValueError(f"Expected string literal, got {_expr_text(node)}")


def _int_literal(node: c_ast.Node) -> int:
    if isinstance(node, c_ast.Constant) and node.type == "int":
        return int(node.value, 0)
    if isinstance(node, c_ast.UnaryOp) and node.op == "-" and isinstance(node.expr, c_ast.Constant):
        return -int(node.expr.value, 0)
    raise ValueError(f"Expected int literal, got {_expr_text(node)}")


def _expr_text(node: c_ast.Node | None) -> str:
    if node is None:
        return ""
    if isinstance(node, c_ast.ID):
        return node.name
    if isinstance(node, c_ast.Constant):
        return node.value
    if isinstance(node, c_ast.UnaryOp):
        return node.op + _expr_text(node.expr)
    if isinstance(node, c_ast.StructRef):
        return _expr_text(node.name) + node.type + _expr_text(node.field)
    if isinstance(node, c_ast.FuncCall):
        args = []
        if isinstance(node.args, c_ast.ExprList):
            args = [_expr_text(expr) for expr in node.args.exprs]
        return f"{_expr_text(node.name)}(" + ", ".join(args) + ")"
    if isinstance(node, c_ast.Cast):
        return _expr_text(node.expr)
    return type(node).__name__


def _type_name(token: str) -> str:
    return TYPE_NAME_MAP.get(token, token.lower())


def _type_code(token: str) -> int:
    if token not in TYPE_CODE_MAP:
        raise ValueError(f"Unknown type token: {token}")
    return TYPE_CODE_MAP[token]


def _skip_ws(text: str, index: int) -> int:
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def _find_matching(text: str, start: int, open_char: str, close_char: str) -> int:
    depth = 0
    mode = "code"
    index = start
    while index < len(text):
        char = text[index]
        nxt = text[index + 1] if index + 1 < len(text) else ""
        if mode == "line_comment":
            if char == "\n":
                mode = "code"
        elif mode == "block_comment":
            if char == "*" and nxt == "/":
                mode = "code"
                index += 1
        elif mode == "string":
            if char == "\\":
                index += 1
            elif char == '"':
                mode = "code"
        elif mode == "char":
            if char == "\\":
                index += 1
            elif char == "'":
                mode = "code"
        else:
            if char == "/" and nxt == "/":
                mode = "line_comment"
                index += 1
            elif char == "/" and nxt == "*":
                mode = "block_comment"
                index += 1
            elif char == '"':
                mode = "string"
            elif char == "'":
                mode = "char"
            elif char == open_char:
                depth += 1
            elif char == close_char:
                depth -= 1
                if depth == 0:
                    return index
        index += 1
    raise ValueError(f"Unmatched {open_char} in source text")
