# Spec: `extract`

Module id `extract`. Directory `/extract` → `braid/extract/`. Depends on:
`ingest`.

## Objective

Produce `(entity, relation, entity)` triples from the corpus, and measure the
extraction's precision and recall against a hand-checked sample rather than
assuming it correct.

## In scope

- NER with spaCy `en_core_web_trf` over each passage.
- Relation extraction by dependency-parse patterns: subject-verb-object, with
  documented handling of passive voice (`nsubjpass` + `agent`), copular
  constructions, prepositional objects attached to the verb, and conjunction
  expansion. The pattern list is fixed, enumerated in the module README, and
  changing it is a spec change.
- Entity normalization: alias resolution against passage titles, case folding,
  and a documented rule for coreference within a passage (first-mention title
  substitution for pronouns; no cross-passage coreference).
- Output `data/triples.jsonl`: subject, relation, object, passage_id, sentence
  index, character spans, entity types, confidence-carrying fields where the
  parser provides them.
- **Quality report** (`reports/extraction-quality.md`): a random sample of 100
  sentences is hand-checked. Precision = fraction of extracted triples judged
  correct. Recall = fraction of triples a human found in those sentences that
  the pipeline also found — so the sample must be annotated independently of
  the pipeline output, or recall is unmeasurable. Both reported with a 95%
  binomial (Wilson) interval, because 100 samples is a small sample.

## Out of scope

General-purpose extraction beyond this corpus. Cross-passage coreference.
Graph loading (that is `index`).

## Interface

```python
@dataclass(frozen=True)
class Triple:
    subject: str
    relation: str
    object: str
    passage_id: str
    sentence_index: int
    subject_type: str | None
    object_type: str | None

def extract(passages: Iterable[Passage]) -> Iterator[Triple]: ...
```

## Acceptance

- [ ] Pattern coverage unit-tested: one fixture sentence per documented
      pattern, with the expected triple asserted.
- [ ] Negative fixtures: sentences that must yield no triple (fragments,
      questions, list headers).
- [ ] `reports/extraction-quality.md` exists with precision, recall, and Wilson
      intervals over a sample annotated *before* the pipeline output was
      consulted for that sample.
- [ ] Triple count and per-relation histogram recorded, so sparsity is visible
      as a number.
- [ ] Runs offline as a batch with no database containers running (8 GiB
      constraint, SPEC.md Hardware).

## Verify

`pytest tests/extract -q`, then
`python -m braid.extract --corpus data/corpus.jsonl --out data/triples.jsonl`
and read the generated report.

## Risks

This is the known risk named in SPEC.md. Encyclopedic prose may yield few
usable triples, threatening criterion 3. The quality report surfaces that here,
at extraction time, with a number. If yield is too low the response is a
documented pattern expansion or a reported negative finding — never a quietly
loosened criterion 3.
