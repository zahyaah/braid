"""braid/query/base.py must stay interface-only: the whitelisted exception to
Checkpoint B's "no retrieval code before review" rule requires every function
body to be exactly `...` (amendment 7, item 1). This is a mechanical check.
"""

import ast
from pathlib import Path


def test_base_module_contains_no_function_bodies_beyond_ellipsis():
    source = Path("braid/query/base.py").read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert len(node.body) == 1, f"{node.name} has more than one statement"
            stmt = node.body[0]
            is_ellipsis = isinstance(stmt, ast.Expr) and isinstance(
                stmt.value, ast.Constant
            ) and stmt.value.value is Ellipsis
            assert is_ellipsis, f"{node.name} body is not '...'"


def test_hit_and_retriever_are_importable():
    from braid.query.base import Hit, Retriever

    hit = Hit(passage_id="p1", score=1.0, rank=1, provenance={"bm25": 1.0})
    assert hit.passage_id == "p1"
    assert hasattr(Retriever, "search")
