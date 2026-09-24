"""health() distinguishes container-down, reachable-but-empty, and
populated-with-N. The "down" tests run unconditionally (an unreachable
host/port is unreachable regardless of whether Docker is up); the
empty/populated tests are integration tests that skip cleanly when the real
containers aren't up (see conftest.py).
"""

from braid.index.health import StoreHealth, check_neo4j, check_opensearch, health


def test_opensearch_down_when_unreachable():
    # A port nothing listens on is reliably unreachable, unlike depending on
    # whether the real Docker stack happens to be up when this test runs.
    result = check_opensearch(host="localhost", port=1)
    assert result.state == "down"
    assert result.count is None
    assert result.name == "opensearch"


def test_neo4j_down_when_unreachable():
    result = check_neo4j(uri="neo4j://localhost:1")
    assert result.state == "down"
    assert result.count is None
    assert result.name == "neo4j"


def test_health_returns_both_stores_in_fixed_order():
    results = health()
    assert [r.name for r in results] == ["opensearch", "neo4j"]
    assert all(isinstance(r, StoreHealth) for r in results)


# ---- integration tests: skip cleanly when containers are down ----

def test_opensearch_empty_index_reports_zero(require_opensearch):
    result = check_opensearch(index="braid-passages-nonexistent-test-index")
    assert result.state == "empty"
    assert result.count == 0


def test_neo4j_reachable_reports_a_count(require_neo4j):
    result = check_neo4j()
    assert result.state in ("empty", "populated")
    assert result.count is not None
