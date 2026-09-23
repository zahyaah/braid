# Spec: `eval`

Module id `eval`. Directory `/eval` → `braid/eval/`. Depends on: `queryset`.

## Objective

Score any object implementing the `Retriever` protocol, stratified by query
category, and attach a 95% confidence interval to every cross-configuration
comparison. This module is written and tested against stub retrievers before
any real retriever exists — that ordering is what makes acceptance criteria 1
and 2 verifiable rather than retrofitted.

## In scope

- Metrics: recall@5, recall@10, nDCG@10, MRR. Computed per query, then
  aggregated. Per-query scores are retained, because the bootstrap resamples
  them.
- nDCG@10 uses **binary gains in every category** (amendment 7, item 4). A
  multi-hop query has several relevant passages, each with gain 1; it does not
  have graded gains. The IDCG is computed from the query's own ideal ranking,
  which for a multi-hop query with n supporting paragraphs is those n passages
  in the top n positions. Ties in retriever scores are broken deterministically
  by passage ID.
- Stratification: every metric reported per category and pooled. A pooled-only
  report fails criterion 1.
- Paired bootstrap: 1,000 resamples over query-level score *differences*,
  resampling queries (not passages), paired by query ID, with a fixed recorded
  seed. Percentile interval at 95%. Applied per category and pooled.
- Comparison table: one table, four configurations x four metrics x three
  categories + pooled, with the criterion-2 differences and their intervals,
  and an explicit "excludes zero: yes/no" column.
- **Criterion 2's "best single-method baseline" is descriptive, per category**
  (amendment 7, item 3): for each category and metric, it is whichever of
  `bm25` or `dense` scores higher on that category, read off the criterion-1
  table. It is not selected after seeing which choice makes the comparison look
  better, and it may differ between categories — exact-term is expected to
  favor `bm25` and paraphrase `dense`, which is the point of the breakout. The
  table names the winning baseline in its own column so the choice is visible
  rather than implied.
- Latency harness (decision D1 thresholds, decision D7 fallbacks):
  - **10 warm-up queries are discarded before timing.** The count is recorded
    in the report, not just in code.
  - **Concurrency 1** for p50 and p95: queries run sequentially, so the
    percentiles describe single-query latency and not queueing.
  - Throughput is reported as queries/sec over the same sequential pass. It is
    a derived figure at concurrency 1, and the report says so — it is not a
    claim about concurrent capacity.
  - **Swap and memory pressure are captured alongside every latency figure**
    (macOS `vm_stat` swapins/swapouts and compressor pages, sampled before and
    after the pass, plus peak RSS). On 8 GiB with two JVMs and a torch process,
    a number that passes D1 while the machine is swapping is not a number that
    will hold, and this makes that visible instead of inferable.
  - Every latency figure records the rerank depth it was measured at (D7).

## Criterion 3: exhaustive count, no subset selection

Criterion 3 is computed over **every** multi-hop query in the evaluation set.
There is no subset selection and no picking five after seeing results. The
reported number is whatever the exhaustive count returns.

**Operational definition in use** (primary, and what the report states):

> Graph beats dense on query *q* if there exists a supporting passage *p* of
> *q* such that *p* appears in `fused` top-10 with non-zero **graph**
> provenance, and *p* does **not** appear in `dense` top-10.

This depends on D5's 3-way fusion. If the author selects 2-way fusion instead,
the alternate definition applies and the report states which was used:

> Graph beats dense on *q* if there exists a supporting passage *p* of *q* such
> that *p* appears in graph-only retrieval's top-10 and not in `dense` top-10.

`reports/graph-vs-vector.md` contains, for every multi-hop query: the query ID,
its supporting passage IDs, each passage's rank under `dense`, its rank and
graph provenance under `fused`, and the resulting per-query verdict. The
summary line is the count of queries meeting the definition, out of the total.
Queries where dense wins and where neither surfaces the passage are listed in
the same table, so the denominator is never hidden.

Criterion 3 asks for at least 5. A count below 5 is reported as the finding it
is, at the same prominence as a passing count, together with the extraction
yield figures from `reports/extraction-quality.md` that most likely explain it.

## Out of scope

Retrieval itself. `eval` imports the `Retriever` protocol, never a concrete
retriever's internals.

## Interface

```python
def evaluate(
    retriever: Retriever,
    queries: list[LabeledQuery],
    k: int = 10,
) -> EvalResult:                       # per-query scores + aggregates
    ...

def compare(
    a: EvalResult, b: EvalResult, *, metric: str, resamples: int = 1000,
    seed: int = 0,
) -> Comparison:                       # diff, ci_low, ci_high, excludes_zero
    ...
```

## Acceptance

- [ ] Metric functions unit-tested against hand-computed values on small
      rankings — values worked out by hand in the test file, not golden files
      generated by this code.
- [ ] Bootstrap tested on synthetic data with known answers: identical inputs
      produce an interval containing zero; a constant offset produces an
      interval excluding zero; the interval narrows as n grows.
- [ ] The bootstrap is *paired*: a test constructs two retrievers that differ
      identically on every query and confirms the paired interval is far
      narrower than an unpaired one on the same data. This catches the most
      likely silent bug in this module.
- [ ] Reruns with a fixed seed reproduce intervals exactly.
- [ ] `evaluate` runs end to end against a stub retriever before any real
      retriever exists.
- [ ] Table generation covers all four configurations and all three categories
      plus pooled, and renders the "excludes zero" column and the
      winning-baseline column.
- [ ] Criterion-3 counting is exhaustive over the multi-hop queries, verified
      by a test asserting that the number of rows in the per-query table equals
      the number of multi-hop queries in the set.
- [ ] Latency report includes warm-up count, concurrency, rerank depth, and the
      swap and memory-pressure samples.

## Verify

`pytest tests/eval -q`, then `python -m braid.eval --all-configs --bootstrap 1000`.

## Risks

This module and `finetune` are where a bug yields a plausible wrong number
instead of a crash. Per the author's workflow step 7, the bootstrap
implementation gets an adversarial review with fresh context before its
numbers are trusted. Specific trap: resampling per-query *scores* of each
configuration independently rather than resampling *queries* and reading both
configurations' scores for the resampled queries. The second is correct; the
first destroys the pairing and inflates the interval.
