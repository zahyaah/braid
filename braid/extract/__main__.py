"""Extraction CLI.

    python -m braid.extract build    # NER + SVO patterns over the full corpus -> data/triples.jsonl
    python -m braid.extract sample --n 100 --seed 20260923   # sample sentences for hand-annotation
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

from braid.extract.entities import normalize_triple
from braid.extract.models import Triple
from braid.extract.ner import extract_entities, load_pipeline, peak_rss_mb
from braid.extract.patterns import extract_document
from braid.ingest.freeze import FrozenCorpusError
from braid.ingest.manifest import Manifest, utc_now
from braid.ingest.models import Passage, load_corpus, write_jsonl

DEFAULT_CORPUS = Path("data/corpus.jsonl")
DEFAULT_CORPUS_MANIFEST = Path("data/manifest.json")
DEFAULT_TRIPLES = Path("data/triples.jsonl")
DEFAULT_EXTRACT_MANIFEST = Path("data/extract-manifest.json")
DEFAULT_SAMPLE = Path("data/extract-sample.jsonl")
DEFAULT_SAMPLE_SIZE = 100
DEFAULT_SEED = 20260923


def extract_passage(nlp, passage: Passage) -> list[Triple]:
    """NER + SVO patterns + normalization over one passage's text."""
    doc = nlp(passage.text)
    entities_by_sentence: dict[int, list] = {}
    for index, sent in enumerate(doc.sents):
        entities_by_sentence[index] = extract_entities(sent.as_doc())

    triples = []
    for raw in extract_document(doc):
        sentence_entities = entities_by_sentence.get(raw.sentence_index, [])
        triples.append(normalize_triple(raw, passage, sentence_entities))
    return triples


def cmd_build(args: argparse.Namespace) -> int:
    corpus_manifest = Manifest.read(args.corpus_manifest)
    if not corpus_manifest.frozen:
        raise FrozenCorpusError(
            "corpus is not frozen (decision D6); run: python -m braid.ingest freeze"
        )

    passages = load_corpus(args.corpus)
    print(f"loading {args.model} ...")
    nlp = load_pipeline(args.model)

    started = time.perf_counter()
    all_triples: list[Triple] = []
    for i, passage in enumerate(passages):
        all_triples.extend(extract_passage(nlp, passage))
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(passages)} passages, {len(all_triples)} triples so far")
    elapsed = time.perf_counter() - started

    write_jsonl(args.out, all_triples)

    histogram: dict[str, int] = {}
    for t in all_triples:
        histogram[t.relation] = histogram.get(t.relation, 0) + 1

    manifest = {
        "model": args.model,
        "corpus_hash": corpus_manifest.corpus_hash,
        "passages": len(passages),
        "triples": len(all_triples),
        "relation_histogram": dict(sorted(histogram.items(), key=lambda kv: -kv[1])),
        "peak_rss_mb": peak_rss_mb(),
        "elapsed_seconds": elapsed,
        "created_at": utc_now(),
    }
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    args.manifest_out.write_text(payload, encoding="utf-8")

    print(
        f"{len(all_triples)} triples from {len(passages)} passages in {elapsed:.1f}s "
        f"(peak RSS {manifest['peak_rss_mb']:.0f} MB) -> {args.out}"
    )
    return 0


def cmd_sample(args: argparse.Namespace) -> int:
    """Sample sentences for hand-annotation. Writes passage_id, sentence_index,
    and sentence text only -- no extraction output -- so annotation happens
    before the pipeline's output is consulted (SPEC-extract.md, Task 21).
    """
    passages = load_corpus(args.corpus)
    print(f"loading {args.model} to segment sentences ...")
    nlp = load_pipeline(args.model)

    all_sentences: list[tuple[str, int, str]] = []
    for passage in passages:
        doc = nlp(passage.text)
        for index, sent in enumerate(doc.sents):
            text = sent.text.strip()
            if text:
                all_sentences.append((passage.passage_id, index, text))

    rng = np.random.default_rng(args.seed)
    order = rng.permutation(len(all_sentences))
    chosen = [all_sentences[int(i)] for i in order[: args.n]]

    rows = [
        {"passage_id": pid, "sentence_index": idx, "text": text} for pid, idx, text in chosen
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    print(f"sampled {len(rows)} sentences (seed {args.seed}) -> {args.out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="braid.extract")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--corpus-manifest", type=Path, default=DEFAULT_CORPUS_MANIFEST)
    parser.add_argument("--model", default="en_core_web_trf")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="run NER + patterns over the full corpus")
    build.add_argument("--out", type=Path, default=DEFAULT_TRIPLES)
    build.add_argument("--manifest-out", type=Path, default=DEFAULT_EXTRACT_MANIFEST)
    build.set_defaults(func=cmd_build)

    sample = sub.add_parser("sample", help="sample sentences for hand-annotation")
    sample.add_argument("--n", type=int, default=DEFAULT_SAMPLE_SIZE)
    sample.add_argument("--seed", type=int, default=DEFAULT_SEED)
    sample.add_argument("--out", type=Path, default=DEFAULT_SAMPLE)
    sample.set_defaults(func=cmd_sample)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
