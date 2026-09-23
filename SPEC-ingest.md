# Spec: `ingest`

Module id `ingest` (capability map). Directory `/ingest` → package
`braid/ingest/`. Depends on: nothing.

## Objective

Turn the HotpotQA distractor validation split into a normalized, deduplicated
passage corpus with stable IDs, plus the question records that `queryset` and
`finetune` sample from. Every downstream module addresses passages by the IDs
this module mints, so the IDs must be stable across reruns.

## In scope

- Load HotpotQA distractor validation split via `datasets`.
- Sample questions with a recorded seed until the pulled paragraph set reaches
  the target corpus size (500–1,000 passages). Sampling starts from questions,
  so every sampled question's gold *and* distractor paragraphs enter the
  corpus and no multi-hop question is left with missing evidence.
- Normalize text: unicode NFKC, whitespace collapse, strip HotpotQA's
  per-sentence list structure into a single passage string while retaining
  sentence offsets as metadata.
- Dedupe: exact SHA-256 on normalized text, then near-duplicate detection at
  Jaccard >= 0.9 over word 3-gram shingles. Both passes are recorded in the
  manifest with counts and examples.

  **Implementation note, deviating from Build Spec v2's "MinHash/LSH".** The
  near-duplicate pass computes *exact* Jaccard, not a MinHash estimate.
  `jaccard(A, B) >= t` implies `min(|A|,|B|) / max(|A|,|B|) >= t`, so sorting
  passages by shingle-set size and comparing only within that size band prunes
  almost every pair while discarding no true duplicate. At 500-1,000 passages
  this runs in well under a second. It removes an approximation, removes a
  dependency, and makes the pass exactly reproducible. MinHash/LSH earns its
  place at a corpus size this project's non-goals rule out.

  **The choice is scale-dependent, and that is the honest caveat.** The band
  scan is O(n * b), where b is the number of passages falling inside a given
  size band. It stays cheap while the corpus is a manageable subset and gets
  expensive somewhere past ~10^5 passages, where band occupancy grows and the
  quadratic term starts to bite. If Braid's corpus ever grows past the 500-1,000
  target, MinHash/LSH comes back — not because the exact version is wrong, but
  because it stops being affordable.
- Mint passage IDs: `sha256(normalized_title + "\u0000" + normalized_text)[:16]`.
  Content-addressed, so a rerun on the same source yields identical IDs and an
  unchanged passage keeps its ID when the corpus is extended.
- Emit `data/corpus.jsonl`, `data/questions.jsonl`, `data/manifest.json`.
- **Every removal is recorded by title, not just counted.** The manifest's
  `dedupe.removals` lists each dropped passage with its title, the title of the
  passage that survived in its place, and the Jaccard similarity that triggered
  the removal. The list is not truncated: a reviewer needs to see what left the
  corpus, not only how much did. The ingest CLI prints the same lines.
- **Freeze the corpus (decision D6).** The pipeline order is
  ingest -> dedupe -> manifest with content hash -> freeze -> author queries
  and judgments. `corpus_hash` is `sha256` over the sorted sequence of
  `(passage_id, text)` pairs, so it covers content, not just IDs. `braid.ingest
  freeze` sets `frozen: true` and `frozen_at` in the manifest and records the
  hash. The freeze commit is a distinct, single-purpose commit, because
  Checkpoint B audits its hash.

## Out of scope

- Sub-paragraph chunking. One HotpotQA paragraph = one passage = one chunk
  (SPEC.md assumption 2).
- Any embedding, indexing, or extraction.

## Interface

```python
@dataclass(frozen=True)
class Passage:
    passage_id: str
    title: str
    text: str
    sentence_spans: list[tuple[int, int]]   # char offsets into text
    source: str                              # "hotpotqa/distractor/validation"

@dataclass(frozen=True)
class Question:
    question_id: str                 # HotpotQA `_id`, verbatim
    text: str
    answer: str
    supporting_passage_ids: list[str]        # resolved to our passage IDs
    supporting_sentences: list[tuple[str, int]]   # (passage_id, sentence index)

def load_corpus(path: Path) -> list[Passage]: ...
def load_questions(path: Path) -> list[Question]: ...
```

`manifest.json` records: dataset name and split, `datasets` version, seed,
question count, passage count before and after each dedupe pass, target size,
timestamp, the git commit, `corpus_hash`, `frozen`, and `frozen_at`. Every
later report cites this manifest.

## The freeze, and what it forbids

Once `frozen: true`, the corpus is immutable for the life of the evaluation.
Judgments are authored against frozen passage IDs, so a label can never drift
underneath a corpus change.

- Any command that would alter an existing passage in a frozen corpus aborts.
- Incremental `add` of *new* passages after a freeze is permitted, since it
  cannot change an existing ID, but it advances `corpus_hash` and the manifest
  records both the pre-add and post-add hash.
- **Remapping a gold passage after the freeze is a judgment change**, not an
  ingest fix, and is "ask first" under SPEC.md Boundaries. The remap-or-drop
  logic in Task 4 therefore runs strictly before the freeze; afterwards, the
  same situation is escalated to the author rather than resolved in code.

## Acceptance

- [ ] Corpus size within the 500–1,000 target; manifest states the exact number.
- [ ] Rerunning with the same seed produces byte-identical `corpus.jsonl`.
- [ ] Every `Question.supporting_passage_ids` entry resolves to a passage that
      exists in the corpus. A question whose gold paragraph was removed as a
      near-duplicate is either remapped to the surviving duplicate or dropped,
      and the manifest counts which happened. Silent dangling references fail
      the build.
- [ ] **A question whose gold paragraphs collapse into one is dropped, not
      remapped.** If two of a question's supporting paragraphs turn out to be
      duplicates of each other, remapping would leave a 2-hop question with one
      piece of evidence — no longer multi-hop, and quietly wrong in the
      multi-hop category. The manifest counts these separately
      (`questions_dropped_collapsed`) from questions dropped for missing
      evidence (`questions_dropped_missing`). **Both counters are printed and
      written to the manifest even when zero**, so "no questions were dropped"
      is a visible statement in the reproduce output rather than an absence.
- [ ] Incremental add: ingesting a second sample into an existing corpus adds
      only new passages and changes no existing ID.
- [ ] `corpus_hash` is stable across reruns and changes if any passage text
      changes; tested both ways.
- [ ] A write that would modify an existing passage in a frozen corpus aborts;
      tested against a frozen fixture.
- [ ] The freeze commit contains only the manifest freeze, so its hash is
      unambiguous in the Checkpoint B audit.
- [ ] Dedupe verified on fixtures: identical text, whitespace-only difference,
      one-sentence difference (must *not* dedupe at threshold), and a true
      near-duplicate.

## Verify

`pytest tests/ingest -q`, then `python -m braid.ingest --out data/corpus.jsonl`
twice and diff the outputs.

## Risks

Near-duplicate removal that deletes a gold supporting paragraph would silently
corrupt multi-hop ground truth. The remap-or-drop check above is the guard, and
it is an assertion, not a log line.
