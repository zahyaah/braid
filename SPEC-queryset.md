# Spec: `queryset`

Module id `queryset`. Directory `/eval/queryset` → `braid/eval/queryset/`.
Depends on: `ingest`, **and specifically on a frozen corpus** (decision D6).
No query or judgment in this module may be authored before
`manifest.json` reports `frozen: true`.

## Objective

Produce the labeled evaluation set — queries and relevance judgments — and
prove it was written before any retrieval code existed. This module is the
foundation of acceptance criteria 1 through 4; if its labels are unsound, every
number in the project is unsound.

## In scope

- **multi-hop-relational:** taken directly from HotpotQA's labeled questions.
  Relevance = the question's supporting paragraphs, resolved to frozen passage
  IDs. **Binary relevance per supporting paragraph:** each supporting paragraph
  carries gain 1. There are several relevant passages per query, but no graded
  gains (amendment 7, item 4).
- **exact-term:** agent-drafted queries targeting named entities, numbers, or
  terminology appearing verbatim in exactly one sampled passage. Binary
  relevance, one correct passage. **Uniqueness is checked mechanically**
  against the frozen corpus: the target term must occur in exactly one passage.
  A draft whose term occurs in zero or several passages is not labeled around —
  the author picks a term that satisfies the check.
- **paraphrase:** agent-drafted queries describing a passage's content without
  reusing its vocabulary, one per sampled passage. Binary relevance. A drafting
  constraint is enforced mechanically: no content word (non-stopword, after
  lemmatization) may be shared **with the target passage's text only** — the
  check is scoped to that one passage, never to the whole corpus, since a
  corpus-wide ban would make most natural English unwritable.
  A failing draft is rewritten by default. **A reviewer may override a
  mechanically failing draft**, for instance where the only accurate word for a
  concept is the passage's own. The override is data, not prose: it is recorded
  in `review.jsonl` with reviewer, timestamp, and reason, and the validator
  counts overrides and requires each failing query to carry one.
- **Human review (decision D4):** every agent-drafted query is reviewed and
  edited before any retrieval code runs. Review is per category, so one
  category's review can complete and be committed while another is still being
  drafted.
- **Schema validator:** `python -m braid.eval.queryset validate` checks
  structure, category balance, passage-ID resolution, the paraphrase
  vocabulary-overlap constraint, and review coverage.

## Out of scope

Any retrieval, scoring, or metric computation.

## Interface

```python
@dataclass(frozen=True)
class LabeledQuery:
    query_id: str
    text: str
    category: Literal["exact-term", "paraphrase", "multi-hop-relational"]
    relevant: dict[str, int]      # passage_id -> gain (1 binary; graded multi-hop)
    origin: Literal["hotpotqa", "agent-drafted"]
    source_question_id: str | None
```

`relevant` maps passage ID to gain, and every gain is 1 — relevance is binary
in all three categories (amendment 7, item 4). Multi-hop queries simply have
more than one entry.

### Review-record schema

One record per drafted query in `review.jsonl`. Multi-hop queries come from
HotpotQA and are not drafted, so they carry no review record.

```python
@dataclass(frozen=True)
class ReviewRecord:
    query_id: str
    source_passage_id: str          # the passage the draft was written from
    draft_text: str                 # agent's original wording, never overwritten
    final_text: str                 # what ships in queries.jsonl
    reviewer: str
    reviewed_at: str                # ISO 8601, with timezone
    disposition: Literal["accepted", "edited", "rejected"]
    reason: str                     # required for "edited" and "rejected"
    overlap_override: OverlapOverride | None   # paraphrase only

@dataclass(frozen=True)
class OverlapOverride:
    reviewer: str
    overridden_at: str              # ISO 8601, with timezone
    reason: str
    shared_terms: list[str]         # the content words the check flagged
```

`draft_text` is never overwritten by an edit — the point of the record is that
the difference between agent wording and shipped wording stays inspectable.

Stored as `queries.jsonl` + `review.jsonl`, both committed to git. These are
the only files in `data/` that are not gitignored.

## Acceptance

- [ ] Size per decision D3: 180 queries (60/category) target, 90 (30/category)
      minimum. The chosen size is committed and the choice recorded in the
      manifest before any retrieval code is written.
- [ ] Validator passes on the committed set and is itself tested against
      deliberately broken fixtures (missing category, unresolvable passage ID,
      paraphrase sharing content words, unreviewed query).
- [ ] Every query carries a review record with a disposition.
- [ ] Every query is authored against the frozen corpus: the manifest's
      `corpus_hash` at authoring time is recorded in the query set, and the
      validator fails if it disagrees with the current manifest (D6).
- [ ] Ordering guarantee, auditable in git history, in this order: the
      **corpus-freeze commit**, then the commit adding `queries.jsonl` and
      `review.jsonl`, then the first commit of any retrieval code. Both hashes
      are recorded at Checkpoint B. This is the auditable form of "labels
      written first, against a corpus that could not move."
- [ ] The "no retrieval code first" audit **whitelists interface-only commits**
      to `braid/query/`: the `Retriever` Protocol and the `Hit` dataclass shown
      in SPEC.md's Code style, and nothing else. Defining the contract early
      cannot leak retrieval results into label authoring, because it contains
      no retrieval logic. A whitelisted commit must add no function body beyond
      `...`, which is a mechanical check, not a judgment call.
- [ ] No exact-term or paraphrase query has more than one relevant passage, or
      the label explains why.
- [ ] Every mechanically failing paraphrase draft that shipped carries an
      `overlap_override` with reviewer, timestamp, and reason; the validator
      counts them and the README reports the count.

## Verify

`python -m braid.eval.queryset validate` exits 0;
`git log --oneline --diff-filter=A -- braid/eval/queryset/queries.jsonl` predates
the first commit touching `braid/index/` or `braid/query/`.

## Risks

Agent-drafted paraphrase queries may be systematically easier for a dense
retriever than real user paraphrases, which would inflate the dense and fused
numbers in that category. The vocabulary-overlap check reduces lexical leakage
but cannot remove semantic-framing bias. The README states this limitation
directly (decision D4); it is not treated as solved.
