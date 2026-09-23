# Extraction pipeline

Named entities (spaCy NER) plus `(entity, relation, entity)` triples from
dependency-parse SVO patterns, over the frozen corpus. Runs offline, as a
batch, with no OpenSearch/Neo4j containers up (SPEC.md Hardware).

## Pattern list

Fixed and enumerated here per SPEC-extract.md — changing it is a spec change,
not a code change. Confirmed empirically against both `en_core_web_sm` and
`en_core_web_trf`: identical dependency label scheme (`nsubj`, `nsubjpass`,
`dobj`, `pobj`, `agent`, `attr`, `prep`, `conj`, `cc`, `compound`).

| # | Pattern | Shape | Example |
|---|---|---|---|
| 1 | Active SVO | `nsubj --VERB--> dobj` | "Scott Derrickson directed Sinister." → (Scott Derrickson, direct, Sinister) |
| 2 | Passive | `nsubjpass` + `agent`→`pobj` | "The film was directed by Scott Derrickson." → (Scott Derrickson, direct, film) |
| 3 | Copular | `nsubj --be--> attr` | "Scott Derrickson is a director." → (Scott Derrickson, be, director) |
| 4 | Verb-attached prepositional object | `nsubj --VERB--prep--> pobj` (no `dobj`) | "Scott Derrickson worked in Denver." → (Scott Derrickson, work in, Denver) |
| 5 | Conjunction expansion | applied to 1–4 | "X and Y wrote the film." → two triples, not one compound-subject triple |

Implementation: [`patterns.py`](patterns.py). Pattern 5 is not a standalone
extractor — it is `_conjuncts()`, applied inside patterns 1–4 wherever a
subject or object is checked.

## What is *not* extracted

- **Passives with no agent phrase** ("The film was directed.") — no
  recoverable subject, nothing is emitted rather than guessing one.
- **Interrogative sentences** ("Who directed Sinister?") — a wh-word subject
  parses with the identical `nsubj`/`dobj` shape as a genuine declarative
  sentence, so nothing in the tree itself marks it as a question. Detected by
  a trailing `?` and skipped before any pattern runs. HotpotQA passages are
  prose, so this never fires on the real corpus; it exists for the documented
  negative fixture.
- Sentence fragments, list headers, and anything else the parser can't find
  an `nsubj` for simply produce no matches — there is no separate fragment
  detector, because the patterns are inherently conservative (SPEC-extract.md:
  "errs toward flagging" is the paraphrase checker's rule, but the symmetric
  rule here is "errs toward silence" — a pattern that doesn't clearly match
  emits nothing rather than a speculative triple).

## Object span extraction

An object's (or subject's) full noun phrase is its own subtree extent —
*excluding* anything reached through a `cc` or `conj` edge. Using plain
`token.left_edge`/`right_edge` pulls an entire conjunction into the first
conjunct's span ("Scott Derrickson and Ethan Cross" all attaching to
"Derrickson"'s subtree) — the classic spaCy conjunction-span gotcha. See
`_span_bounds()` in `patterns.py`.

An NP-internal prepositional phrase attached to the object noun itself (not
to the verb) stays part of the object span: "wrote the film about war" →
object text `"film about war"`, not `"film"`. This is deliberate — it is part
of the entity's own phrase, and pattern 4 correctly does not *also* fire for
the same verb once pattern 1 (the `dobj`) has matched.
