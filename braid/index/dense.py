"""FAISS dense index builder: BAAI/bge-small-en-v1.5 -> IndexFlatIP.

Grounded (workflow step 5):
- Model card (query-side instruction prefix, no prefix for passages,
  `normalize_embeddings=True`) --
  https://huggingface.co/BAAI/bge-small-en-v1.5
- `faiss.IndexFlatIP`, `faiss.write_index`/`read_index` -- confirmed against
  the installed `faiss` package's own classes/functions; standard, stable
  top-level FAISS API documented at
  https://github.com/facebookresearch/faiss/wiki/Getting-started

`IndexFlatIP` is exact (brute-force) inner-product search -- correct at this
corpus size (500-1,000 passages, SPEC.md) and removes approximate-recall as a
confound from the benchmark entirely (SPEC-index.md).

`ids.json` maps FAISS ordinal position -> passage_id, since FAISS itself only
knows integer ordinals. It is written in the same `save()` call as the index
file, and `load()` asserts their lengths agree -- an ordinal/ID length
mismatch after a bad partial write would otherwise silently return the wrong
passage for a given search hit.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from braid.ingest.models import Passage

MODEL_NAME = "BAAI/bge-small-en-v1.5"
DIMENSION = 384
QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "

DEFAULT_INDEX_PATH = Path("data/dense.faiss")
DEFAULT_IDS_PATH = Path("data/dense-ids.json")


@dataclass(frozen=True)
class SearchHit:
    passage_id: str
    score: float


_model_cache: dict[str, object] = {}


def _model(name: str = MODEL_NAME):
    # Cached at module level: loading a sentence-transformers model is
    # expensive, and build()/add()/search() may all run in the same process.
    if name not in _model_cache:
        from sentence_transformers import SentenceTransformer

        _model_cache[name] = SentenceTransformer(name)
    return _model_cache[name]


def embed_passages(texts: list[str]) -> np.ndarray:
    """No instruction prefix for passages, per the model card."""
    model = _model()
    return np.asarray(model.encode(texts, normalize_embeddings=True), dtype="float32")


def embed_query(text: str) -> np.ndarray:
    """The model card's retrieval instruction prefix, query side only."""
    model = _model()
    vec = model.encode([QUERY_INSTRUCTION + text], normalize_embeddings=True)
    return np.asarray(vec, dtype="float32")


def save(
    index,
    ids: list[str],
    index_path: Path = DEFAULT_INDEX_PATH,
    ids_path: Path = DEFAULT_IDS_PATH,
) -> None:
    import faiss

    index_path.parent.mkdir(parents=True, exist_ok=True)
    ids_path.parent.mkdir(parents=True, exist_ok=True)
    ids_path.write_text(json.dumps(ids), encoding="utf-8")
    faiss.write_index(index, str(index_path))


def load(index_path: Path = DEFAULT_INDEX_PATH, ids_path: Path = DEFAULT_IDS_PATH):
    import faiss

    index = faiss.read_index(str(index_path))
    ids = json.loads(ids_path.read_text(encoding="utf-8"))
    if index.ntotal != len(ids):
        raise ValueError(
            f"FAISS index has {index.ntotal} vectors but ids.json has {len(ids)} entries "
            "-- ordinal-to-passage-id mapping would silently resolve wrong passages"
        )
    return index, ids


def build(
    passages: list[Passage],
    index_path: Path = DEFAULT_INDEX_PATH,
    ids_path: Path = DEFAULT_IDS_PATH,
) -> int:
    import faiss

    vectors = embed_passages([p.text for p in passages])
    index = faiss.IndexFlatIP(DIMENSION)
    index.add(vectors)
    save(index, [p.passage_id for p in passages], index_path, ids_path)
    return index.ntotal


def add(
    passages: list[Passage],
    index_path: Path = DEFAULT_INDEX_PATH,
    ids_path: Path = DEFAULT_IDS_PATH,
) -> int:
    """Incremental add: append new passages' vectors without rebuilding."""
    index, ids = load(index_path, ids_path)
    vectors = embed_passages([p.text for p in passages])
    index.add(vectors)
    ids.extend(p.passage_id for p in passages)
    save(index, ids, index_path, ids_path)
    return index.ntotal


def search(
    query: str, k: int, index_path: Path = DEFAULT_INDEX_PATH, ids_path: Path = DEFAULT_IDS_PATH
) -> list[SearchHit]:
    index, ids = load(index_path, ids_path)
    query_vec = embed_query(query)
    scores, indices = index.search(query_vec, k)
    hits = []
    for score, ordinal in zip(scores[0], indices[0], strict=True):
        if ordinal == -1:  # fewer than k results in the index
            continue
        hits.append(SearchHit(passage_id=ids[ordinal], score=float(score)))
    return hits
