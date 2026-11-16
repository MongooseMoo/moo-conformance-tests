from pathlib import Path

import yaml

from moo_conformance.builtin_coverage import _concrete_types
from moo_conformance.builtin_io_generator import extract_builtin_specs, render_builtin_yaml

FLAG_SOURCE = """
static package
bf_sort(Var arglist, Byte next, void *vdata, Objid progr)
{
    return background_thread(sort_callback, &arglist);
}

void
register_list(void)
{
    register_function("sort", 1, 4, bf_sort, TYPE_LIST, TYPE_LIST, TYPE_FLAG, TYPE_FLAG);
}
"""


def _flag_spec(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "list.cc").write_text(FLAG_SOURCE, encoding="utf-8")
    [spec] = extract_builtin_specs(tmp_path)
    return spec


def test_type_flag_registration_reports_function_info_code(tmp_path: Path) -> None:
    spec = _flag_spec(tmp_path)

    assert spec.prototype_tokens == ["TYPE_LIST", "TYPE_LIST", "TYPE_FLAG", "TYPE_FLAG"]
    assert spec.prototype_names == ["list", "list", "flag", "flag"]
    assert spec.prototype_codes == [4, 4, -3, -3]


def test_type_flag_position_gets_witness_tests(tmp_path: Path) -> None:
    suite = yaml.safe_load(render_builtin_yaml(_flag_spec(tmp_path)))
    tests = {test["name"]: test for test in suite["tests"]}

    assert tests["sort_function_info_signature_matches_source"]["expect"]["value"] == [
        "sort",
        1,
        4,
        [4, 4, -3, -3],
    ]
    assert tests["sort_too_many_args"]["code"] == "sort({}, {}, 1, 1, 1)"
    assert tests["sort_arg_3_rejects_wrong_type"]["code"] == 'sort({}, {}, "x")'
    assert tests["sort_arg_4_rejects_wrong_type"]["code"] == 'sort({}, {}, 1, "x")'


def test_type_flag_coverage_admits_int_and_bool() -> None:
    assert _concrete_types("TYPE_FLAG") == ["int", "bool"]
