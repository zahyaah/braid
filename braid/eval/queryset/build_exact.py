"""Draft exact-term queries: agent-drafted, targeting a term unique to one passage.

Each drafted query targets a named entity, a number, or terminology that
appears verbatim in exactly one passage (checked mechanically against the
frozen corpus). A term occurring in zero or several passages is never labeled
around — a different candidate is picked instead (SPEC-queryset.md, Task 9).

Output is agent-drafted and unreviewed: it lands in queries.jsonl with
origin="agent-drafted", and Task 10's human review is a separate step. The
validator will flag these queries as missing a review record until that step
runs, which is intended — it is the same signal decision D4 requires.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

from braid.eval.queryset.schema import (
    MANIFEST_FILE,
    QUERIES_FILE,
    QUERYSET_DIR,
    RELEVANT_GAIN,
    LabeledQuery,
    QuerySetManifest,
    read_queries,
    write_queries,
)
from braid.eval.queryset.uniqueness import Candidate, extract_candidates, is_unique
from braid.ingest.freeze import FrozenCorpusError
from braid.ingest.manifest import Manifest
from braid.ingest.models import Passage, load_corpus

DEFAULT_CORPUS = Path("data/corpus.jsonl")
DEFAULT_CORPUS_MANIFEST = Path("data/manifest.json")
QUERY_ID_PREFIX = "et"
DEFAULT_SEED = 20260923

_PHRASE_TEMPLATES = [
    "What is {term} associated with in {title}?",
    "Which passage discusses {term}?",
    "Where does {term} appear in connection with {title}?",
]
_YEAR_TEMPLATES = [
    "What happened in {term} according to the article on {title}?",
    "What event tied to {title} occurred in {term}?",
]
_NUMBER_TEMPLATES = [
    "What is the figure {term} referring to in the context of {title}?",
    "Which article on {title} mentions the number {term}?",
]

_TEMPLATES = {"phrase": _PHRASE_TEMPLATES, "year": _YEAR_TEMPLATES, "number": _NUMBER_TEMPLATES}


def pick_unique_term(passage: Passage, corpus: list[Passage]) -> Candidate | None:
    """The first candidate from this passage that is unique across the corpus.

    Candidates are tried in extraction order (roughly: longest, most specific
    phrases first), so ties resolve deterministically and a rerun on the same
    corpus picks the same term for the same passage.
    """
    for candidate in extract_candidates(passage):
        if is_unique(candidate.term, corpus):
            return candidate
    return None


def draft_query(passage: Passage, candidate: Candidate, template_index: int) -> str:
    templates = _TEMPLATES[candidate.kind]
    template = templates[template_index % len(templates)]
    return template.format(term=candidate.term, title=passage.title)


def build(
    corpus: list[Passage],
    limit: int,
    seed: int = DEFAULT_SEED,
) -> tuple[list[LabeledQuery], int]:
    """Draft up to `limit` exact-term queries. Returns (queries, passages_without_a_unique_term)."""
    order = np.random.default_rng(seed).permutation(len(corpus))
    queries: list[LabeledQuery] = []
    skipped = 0
    for template_index, index in enumerate(order):
        if len(queries) >= limit:
            break
        passage = corpus[int(index)]
        candidate = pick_unique_term(passage, corpus)
        if candidate is None:
            skipped += 1
            continue
        text = draft_query(passage, candidate, template_index)
        queries.append(
            LabeledQuery(
                query_id=f"{QUERY_ID_PREFIX}-{passage.passage_id}",
                text=text,
                category="exact-term",
                relevant={passage.passage_id: RELEVANT_GAIN},
                origin="agent-drafted",
            )
        )
    return queries, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="braid.eval.queryset.build_exact")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--corpus-manifest", type=Path, default=DEFAULT_CORPUS_MANIFEST)
    parser.add_argument("--dir", type=Path, default=QUERYSET_DIR)
    parser.add_argument("--limit", type=int, default=60)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args(argv)

    corpus_manifest = Manifest.read(args.corpus_manifest)
    if not corpus_manifest.frozen:
        raise FrozenCorpusError(
            "corpus is not frozen; judgments may not be authored yet (decision D6). "
            "Run: python -m braid.ingest freeze"
        )

    corpus = load_corpus(args.corpus)
    built, skipped = build(corpus, limit=args.limit, seed=args.seed)

    queries_path = args.dir / QUERIES_FILE
    existing = read_queries(queries_path) if queries_path.exists() else []
    kept = [query for query in existing if query.category != "exact-term"]
    write_queries(queries_path, kept + built)

    manifest_path = args.dir / MANIFEST_FILE
    manifest = QuerySetManifest.read(manifest_path)
    manifest.corpus_hash = corpus_manifest.corpus_hash
    manifest.counts["exact-term"] = len(built)
    manifest.write(manifest_path)

    print(
        f"exact-term queries: {len(built)} drafted (target {args.limit}, "
        f"{skipped} passages skipped for lacking a unique candidate term); "
        f"corpus_hash {manifest.corpus_hash}"
    )
    if len(built) < args.limit:
        print(
            f"WARNING: only {len(built)}/{args.limit} drafted; "
            "widen the sample or the extraction patterns"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
