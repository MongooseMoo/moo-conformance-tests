"""Keep regenerated conformance data deterministic and independently asserted."""

from moo_conformance.schema import validate_test_suite
from moo_conformance.semantic_edges_generator import outputs


def test_semantic_edges_are_distinct_asserted_cases():
    first = outputs()
    assert first == outputs()
    assert {name: len(cases) for name, cases in first.items()} == {
        "semantic_edges_scatter": 324,
        "semantic_edges_range_write": 432,
        "semantic_edges_short_circuit": 264,
        "semantic_edges_finally": 75,
    }
    statements = set()
    names = set()
    for name, cases in first.items():
        suite = validate_test_suite({"name": name, "tests": cases})
        for case in suite.tests:
            assert case.name not in names
            assert case.statement not in statements
            assert case.expect.value is not None
            names.add(case.name)
            statements.add(case.statement)
    assert len(statements) == 1095
