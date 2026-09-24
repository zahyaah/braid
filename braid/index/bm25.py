"""OpenSearch BM25 index builder.

Client API calls, grounded in official docs and the installed client's own
signatures (workflow step 5):
- Client instantiation (no-auth, local) --
  https://docs.opensearch.org/latest/clients/python-low-level/
- `client.indices.create(index=, body=)` / `.delete()` / `.exists()` --
  signatures confirmed against the installed opensearchpy.client.indices.IndicesClient.
- `opensearchpy.helpers.bulk(client, actions)` -- confirmed against the
  installed opensearchpy.helpers.actions.bulk docstring; each action is
  `{"_index":.., "_id":.., "_source":{...}}`, the standard elasticsearch-py-
  derived bulk action shape.
- `client.count(index=)` and `client.search(index=, body=)` with a `match`
  query -- https://github.com/opensearch-project/opensearch-py/blob/main/USER_GUIDE.md

Analyzer settings are stated explicitly, not left to the implicit default,
because BM25 numbers depend on them (SPEC-index.md, Task 23) -- a future
reader must be able to see exactly what tokenization produced the reported
scores without having to know OpenSearch's current default.
"""

from __future__ import annotations

from dataclasses import dataclass

from braid.ingest.models import Passage

INDEX_NAME = "braid-passages"

# Standard analyzer: lowercase + Unicode-aware word-boundary tokenization, no
# stemming or stopword removal. Stated explicitly (not the implicit default)
# per the module docstring above.
MAPPING = {
    "settings": {
        "analysis": {
            "analyzer": {
                "braid_text": {
                    "type": "standard",
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "title": {"type": "text", "analyzer": "braid_text"},
            "text": {"type": "text", "analyzer": "braid_text"},
        }
    },
}


@dataclass(frozen=True)
class BuildReport:
    indexed: int
    errors: list[dict]


@dataclass(frozen=True)
class SearchHit:
    passage_id: str
    score: float


def _client(host: str = "localhost", port: int = 9200):
    from opensearchpy import OpenSearch

    return OpenSearch(hosts=[{"host": host, "port": port}], use_ssl=False, verify_certs=False)


def _action(passage: Passage, index_name: str) -> dict:
    # passage_id as the document _id (Task 23 acceptance), not a separate
    # field -- so a repeat build with the same passages overwrites in place
    # rather than accumulating duplicates.
    return {
        "_index": index_name,
        "_id": passage.passage_id,
        "_source": {"title": passage.title, "text": passage.text},
    }


def build(passages: list[Passage], client=None, index_name: str = INDEX_NAME) -> BuildReport:
    """Create the index (dropping any existing one with the same name) and
    bulk-index every passage. Idempotent: rerunning replaces the index.

    `index_name` defaults to the real deliverable index -- tests must pass a
    distinct name (see tests/index/conftest.py's `test_index_name` fixture).
    Every test in this project used to default here, which meant running the
    test suite silently overwrote the real corpus-scale index with whatever
    small fixture the last test happened to build -- found by running
    `python -m braid.index health` after a full test run and seeing document
    counts drop from 1000 to 15.
    """
    from opensearchpy.helpers import bulk

    client = client or _client()
    if client.indices.exists(index=index_name):
        client.indices.delete(index=index_name)
    client.indices.create(index=index_name, body=MAPPING)

    actions = (_action(p, index_name) for p in passages)
    success, errors = bulk(client, actions, stats_only=False, raise_on_error=False)
    client.indices.refresh(index=index_name)
    return BuildReport(indexed=success, errors=list(errors) if errors else [])


def add(passages: list[Passage], client=None, index_name: str = INDEX_NAME) -> BuildReport:
    """Incremental add: index new passages without dropping the existing index."""
    from opensearchpy.helpers import bulk

    client = client or _client()
    actions = (_action(p, index_name) for p in passages)
    success, errors = bulk(client, actions, stats_only=False, raise_on_error=False)
    client.indices.refresh(index=index_name)
    return BuildReport(indexed=success, errors=list(errors) if errors else [])


def doc_count(client=None, index_name: str = INDEX_NAME) -> int:
    client = client or _client()
    return client.count(index=index_name)["count"]


def search(query: str, k: int, client=None, index_name: str = INDEX_NAME) -> list[SearchHit]:
    client = client or _client()
    body = {"size": k, "query": {"match": {"text": query}}}
    response = client.search(index=index_name, body=body)
    return [
        SearchHit(passage_id=hit["_id"], score=hit["_score"])
        for hit in response["hits"]["hits"]
    ]
