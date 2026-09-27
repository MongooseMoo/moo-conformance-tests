"""Reproduce the September 2026 scatter, nested-write, and evaluation-order corpus.

Expectations are calculated before running Toast. See the coverage ledger for
the source branches and the pre-campaign inventory.
"""

from __future__ import annotations

import argparse
import copy
import itertools
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "src/moo_conformance/_tests/language"


def literal(value):
    if isinstance(value, list):
        return "{" + ", ".join(literal(item) for item in value) + "}"
    return json.dumps(value)


def case(name, statement, value):
    return {"name": name, "statement": statement, "expect": {"value": value}}


def scatter_cases():
    # r=required, d=optional with observing default, o=optional preserving old
    # binding, s=rest. Exercise all three-slot layouts, not renamed copies.
    cases = []
    for layout in itertools.product("rdos", repeat=3):
        if layout.count("s") > 1:
            continue
        targets = []
        for i, (name, kind) in enumerate(zip("abc", layout), 1):
            targets.append(
                {
                    "r": name,
                    "o": "?" + name,
                    "s": "@" + name,
                    "d": f"?{name} = {{(trace = {{@trace, {i}}}), {{a, b, c}}}}[2]",
                }[kind]
            )
        for length in range(6):
            rhs = [101 + 11 * i for i in range(length)]
            values = [-11, -22, -33]
            trace = []
            result = "unassigned"
            nreq = layout.count("r")
            error = length < nreq or ("s" not in layout and length > 3)
            if not error:
                available = length - nreq
                rest = max(0, length - 2) if "s" in layout else 0
                cursor = 0
                defaults = []
                for i, kind in enumerate(layout):
                    if kind == "s":
                        values[i] = rhs[cursor : cursor + rest]
                        cursor += rest
                    elif kind == "r" or available > 0:
                        values[i] = rhs[cursor]
                        cursor += 1
                        if kind != "r":
                            available -= 1
                    elif kind == "d":
                        defaults.append(i)
                # VM binds supplied targets first, then executes default code.
                for i in defaults:
                    trace.append(i + 1)
                    values[i] = copy.deepcopy(values)
                result = rhs
            code = (
                'a = -11; b = -22; c = -33; trace = {}; result = "unassigned"; '
                "status = E_NONE;\ntry\n"
                f"  result = ({{{', '.join(targets)}}} = {literal(rhs)});\n"
                "except ex (ANY)\n  status = ex[1];\nendtry\n"
                "return {status, {a, b, c}, trace, result};"
            )
            cases.append(
                case(
                    f"scatter_binding_{''.join(layout)}_rhs_{length}",
                    code,
                    ["E_ARGS" if error else "E_NONE", values, trace, result],
                )
            )
    return cases


# Boundary positions relative to the fixed four-element source. These include
# independent clamps, overlap duplication, insertion and both rejection branches.
BOUNDS = (
    ("negative_start", -2, 2),
    ("zero_start", 0, 2),
    ("both_zero", 0, 0),
    ("prepend", 1, 0),
    ("interior_insert", 2, 1),
    ("overlap", 4, 1),
    ("middle_replace", 2, 3),
    ("whole_replace", 1, 4),
    ("append", 5, 4),
    ("append_past_end", 5, 7),
    ("delete_past_end", 1, 8),
    ("start_past_end", 6, 4),
    ("negative_end", 2, -1),
    ("both_invalid", 6, -1),
    ("tail_replace", 3, 4),
    ("head_replace", 1, 2),
    ("duplicate_whole", 5, 0),
    ("single_middle", 2, 2),
)


def range_cases():
    cases = []
    for kind, source, replacements in (
        ("list", [11, 22, 33, 44], [[], [91], [91, 92, 93]]),
        ("string", "aBcD", ["", "X", "xYz"]),
    ):
        for shape, wrap, path in (
            ("root", "SOURCE", ""),
            ("list", "{SOURCE, SOURCE}", "[1]"),
            ("map", '["left" -> SOURCE, "right" -> SOURCE]', '["left"]'),
            ("mixed", '{["slot" -> {SOURCE, SOURCE}], SOURCE}', '[1]["slot"][1]'),
        ):
            base = wrap.replace("SOURCE", "leaf")
            for label, start, end in BOUNDS:
                for size, replacement in enumerate(replacements):
                    error = start > len(source) + 1 or end < 0
                    new = (
                        source
                        if error
                        else (source[: max(0, start - 1)] + replacement + source[end:])
                    )
                    original_root = wrap.replace("SOURCE", literal(source))
                    expected_root = wrap.replace("SOURCE", literal(new), 1).replace(
                        "SOURCE", literal(source)
                    )
                    code = (
                        f"leaf = {literal(source)}; root = {base}; "
                        'alias = root; result = "unassigned"; status = E_NONE;\n'
                        "try\n"
                        f"  result = (root{path}[{start}..{end}] = {literal(replacement)});\n"
                        "except ex (ANY)\n  status = ex[1];\nendtry\n"
                    )
                    expected = [
                        "E_RANGE" if error else "E_NONE",
                        new,
                        1,
                        1,
                        "unassigned" if error else replacement,
                        1,
                    ]
                    if kind == "string" and start < 0:
                        # EOP_RANGESET compares Num against uint32_t memo_strlen.
                        # Signed int32 converts to unsigned; int64 does not.
                        # Select by independent build metadata, never by whether
                        # the operation happened to return an error.
                        code = (
                            'width = server_version("options/ONLY_32_BITS");\n'
                            'if (!equal(width, {0}) && !equal(width, #-1))\n'
                            '  raise(E_INVARG, "Unknown ONLY_32_BITS setting");\nendif\n'
                            'narrow = equal(width, {0});\n'
                            + code
                            + f"return {{status == (narrow ? E_RANGE | E_NONE), "
                            f"equal(root{path}, (narrow ? {literal(source)} | {literal(new)})), "
                            f"equal(alias, {original_root}), equal(leaf, {literal(source)}), "
                            f'equal(result, (narrow ? "unassigned" | {literal(replacement)})), '
                            f"equal(root, (narrow ? {original_root} | {expected_root}))}};"
                        )
                        expected = [1, 1, 1, 1, 1, 1]
                    else:
                        code += (
                            f"return {{status, root{path}, equal(alias, {original_root}), "
                            f"equal(leaf, {literal(source)}), result, "
                            f"equal(root, {expected_root})}};"
                        )
                    cases.append(
                        case(
                            f"range_write_{kind}_{shape}_{label}_replacement_{size}",
                            code,
                            expected,
                        )
                    )
    return cases


TRUTH_VALUES = (
    ("zero", "0", False),
    ("positive", "7", True),
    ("negative", "-7", True),
    ("false", "false", False),
    ("true", "true", True),
    ("float_zero", "0.0", False),
    ("float_negative_zero", "-0.0", False),
    ("float_positive", "0.5", True),
    ("float_negative", "-0.5", True),
    ("empty_string", '""', False),
    ("string_zero", '"0"', True),
    ("string_space", '" "', True),
    ("empty_list", "{}", False),
    ("list_zero", "{0}", True),
    ("list_empty", "{{}}", True),
    ("empty_map", "[]", False),
    ("map_zero", "[0 -> 0]", True),
    ("map_empty", '["" -> {}]', True),
    ("nothing", "#-1", False),
    ("system_object", "#0", False),
    ("error_none", "E_NONE", False),
    ("error_type", "E_TYPE", False),
)


def short_circuit_cases():
    cases = []
    first = '{(trace = {@trace, 1}), "first"}[2]'
    second = '{(trace = {@trace, 2}), {"second"}}[2]'
    poison = "{(trace = {@trace, 3}), 1 / 0}[2]"
    for name, value, truth in TRUTH_VALUES:
        patterns = (
            ("and", f"v && {first}", '"first"' if truth else value, [1] if truth else []),
            ("or", f"v || {first}", value if truth else '"first"', [] if truth else [1]),
            (
                "ternary",
                f"v ? {first} | {second}",
                '"first"' if truth else '{"second"}',
                [1] if truth else [2],
            ),
            ("not_and", f"!v && {first}", "0" if truth else '"first"', [] if truth else [1]),
            ("not_or", f"!v || {first}", '"first"' if truth else "1", [1] if truth else []),
            (
                "and_or",
                f"(v && {first}) || {second}",
                '"first"' if truth else '{"second"}',
                [1] if truth else [2],
            ),
            ("or_and", f"(v || {first}) && {second}", '{"second"}', [2] if truth else [1, 2]),
            (
                "and_false_or",
                f"(v && {{(trace = {{@trace, 1}}), 0}}[2]) || {second}",
                '{"second"}',
                [1, 2] if truth else [2],
            ),
            (
                "or_true_and",
                f"(v || {{(trace = {{@trace, 1}}), 1}}[2]) && {second}",
                '{"second"}',
                [2] if truth else [1, 2],
            ),
            (
                "and_caught_poison",
                f'`v && {poison} ! E_DIV => "caught"\'',
                '"caught"' if truth else value,
                [3] if truth else [],
            ),
            (
                "or_caught_poison",
                f'`v || {poison} ! E_DIV => "caught"\'',
                value if truth else '"caught"',
                [] if truth else [3],
            ),
            (
                "conditional_poison",
                f'`(v ? {poison} | {second}) ! E_DIV => "caught"\'',
                '"caught"' if truth else '{"second"}',
                [3] if truth else [2],
            ),
        )
        for label, expr, expected, trace in patterns:
            code = (
                f"v = {value}; trace = {{}}; result = ({expr});\n"
                f"return {{equal(result, {expected}), "
                f"typeof(result) == typeof({expected}), trace}};"
            )
            cases.append(case(f"lazy_effects_{name}_{label}", code, [1, 1, trace]))
    return cases


def finally_cases():
    cases = []
    actions = {
        "normal": "0;",
        "break": "break;",
        "continue": "continue;",
        "return": 'return {"body-return", trace};',
        "error": "raise(E_INVARG);",
    }
    for pending, final, depth in itertools.product(actions, actions, range(1, 4)):
        final_code = (
            actions[final].replace("body-return", "final-return").replace("E_INVARG", "E_DIV")
        )
        body = (
            "try\ntrace = {@trace, i};\n"
            + actions[pending]
            + "\nfinally\ntrace = {@trace, 10 + i};\n"
            + final_code
            + "\nendtry"
        )
        for level in range(2, depth + 1):
            body = f"try\n{body}\nfinally\ntrace = {{@trace, {10 * level} + i}};\nendtry"
        code = (
            "trace = {};\ntry\nfor i in [1..2]\n" + body + "\ntrace = {@trace, 100 + i};\nendfor\n"
            'except ex (ANY)\nreturn {"error", ex[1], trace};\nendtry\n'
            'return {"done", trace};'
        )
        trace = []
        expected = None
        for i in (1, 2):
            trace.append(i)
            returned = ["body-return", trace.copy()] if pending == "return" else None
            trace.append(10 + i)
            if final == "return":
                returned = ["final-return", trace.copy()]
            transfer = pending if final == "normal" else final
            for level in range(2, depth + 1):
                trace.append(10 * level + i)
            if transfer == "return":
                expected = returned
                break
            if transfer == "error":
                expected = ["error", "E_DIV" if final == "error" else "E_INVARG", trace]
                break
            if transfer == "break":
                break
            if transfer == "normal":
                trace.append(100 + i)
        if expected is None:
            expected = ["done", trace]
        # A return snapshots the local trace before unwinding. Also inspect a
        # property after the call, so skipped outer finalizers cannot pass.
        verb_lines = code.replace("trace", "this.trace").splitlines()
        statement = (
            "probe = create(#-1);\ntry\n"
            '  add_property(probe, "trace", {}, {player, "rw"});\n'
            '  add_verb(probe, {player, "xd", "run"}, {"this", "none", "this"});\n'
            f'  errors = set_verb_code(probe, "run", {literal(verb_lines)});\n'
            '  if (errors)\n    return {"compile-error", errors};\n  endif\n'
            "  result = probe:run();\n  observed = probe.trace;\n"
            "finally\n  recycle(probe);\nendtry\nreturn {result, observed};"
        )
        test = case(
            f"finally_transfer_{pending}_then_{final}_depth_{depth}", statement, [expected, trace]
        )
        test["permission"] = "wizard"
        cases.append(test)
    return cases


def outputs():
    return {
        "semantic_edges_scatter": scatter_cases(),
        "semantic_edges_range_write": range_cases(),
        "semantic_edges_short_circuit": short_circuit_cases(),
        "semantic_edges_finally": finally_cases(),
    }


class Dumper(yaml.SafeDumper):
    pass


def represent_string(dumper, value):
    return dumper.represent_scalar(
        "tag:yaml.org,2002:str", value, style="|" if "\n" in value else None
    )


Dumper.add_representer(str, represent_string)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    total = 0
    for name, cases in outputs().items():
        data = {
            "name": name,
            "description": "September 2026 semantic interaction coverage.",
            "tests": cases,
        }
        text = "# Generated by python -m moo_conformance.semantic_edges_generator\n" + yaml.dump(
            data, Dumper=Dumper, sort_keys=False, width=100
        )
        path = OUTPUT / (name + ".yaml")
        if args.check:
            if path.read_text(encoding="utf-8") != text:
                raise SystemExit(f"Generated file drift: {path}")
        else:
            path.write_text(text, encoding="utf-8")
        print(f"{name}: {len(cases)}")
        total += len(cases)
    print(f"Total: {total}")


if __name__ == "__main__":
    main()
