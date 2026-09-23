"""SVO relation extraction by dependency-parse patterns.

The pattern list is fixed and documented here (also summarized in
braid/extract/README.md, per SPEC-extract.md); changing it is a spec change.
Confirmed empirically against both en_core_web_sm and en_core_web_trf (same
ClearNLP-derived label scheme: nsubj, nsubjpass, dobj, pobj, agent, attr,
prep, conj, cc, compound -- identical across both models for the constructions
below).

Patterns, in the order they are tried per sentence:

1. **Active SVO**: nsubj --VERB--> dobj.
   "Scott Derrickson directed Sinister." -> (Scott Derrickson, directed, Sinister)

2. **Passive** (nsubjpass + agent): the surface subject is the semantic
   object; the real subject is the pobj of the verb's "agent" child (the
   "by" phrase). Both must be present, or nothing is emitted -- a passive
   with no agent phrase has no recoverable subject.
   "The film was directed by Scott Derrickson." -> (Scott Derrickson, directed, film)

3. **Copular** (nsubj + attr, "be"-family head): "X is Y" -> (X, is, Y).
   "Scott Derrickson is a director." -> (Scott Derrickson, is, director)

4. **Verb-attached prepositional object**: nsubj --VERB--prep--> pobj, for
   verbs with no dobj (dobj already covered by pattern 1). The relation is
   "verb preposition", e.g. "worked in".
   "Scott Derrickson worked in Denver." -> (Scott Derrickson, worked in, Denver)

5. **Conjunction expansion**: applied to patterns 1-4. A conjoined subject or
   object ("X and Y directed the film") expands into one triple per
   conjunct, not one triple with a compound entity string.
   "Scott Derrickson and Ethan Cross wrote the film." ->
     (Scott Derrickson, wrote, film), (Ethan Cross, wrote, film)
"""

from __future__ import annotations

from braid.extract.models import RawTriple

_BE_LEMMAS = {"be"}
_LEADING_STRIP_POS = {"DET"}
# Relative/interrogative pronoun subjects ("which", "who", "that" as a relative
# pronoun -- WDT/WP, distinct from demonstrative "that", tagged DT) have no
# antecedent resolvable at the pattern-matching stage: "which" in "the movie,
# which aired on ABC" refers to "movie", not to the passage title (the only
# antecedent entities.py's pronoun substitution knows how to supply). Left
# unfiltered, these produced literal, nonsensical triples like
# (which, air on, ABC) -- found by inspecting real extraction output while
# building the extraction-quality report, not a hypothetical. Skipped
# entirely (no triple emitted) rather than guessing an antecedent, matching
# this module's existing "err toward silence" rule for interrogatives.
_WH_PRONOUN_TAGS = {"WDT", "WP"}


_CONJUNCTION_EDGES = {"cc", "conj"}


def _span_bounds(token) -> tuple[int, int]:
    """The token's own noun-phrase extent: its subtree, but never descending
    through a 'cc' or 'conj' edge. Plain left_edge/right_edge would pull a
    whole conjunction into the *first* conjunct's span ("Scott Derrickson and
    Ethan Cross wrote..." -> "Derrickson".left_edge/right_edge spans the
    entire subject including "and Ethan Cross"), which is exactly wrong when
    pattern 5 needs each conjunct's own span.
    """
    indices = {token.i}
    stack = [child for child in token.children if child.dep_ not in _CONJUNCTION_EDGES]
    while stack:
        current = stack.pop()
        indices.add(current.i)
        stack.extend(child for child in current.children if child.dep_ not in _CONJUNCTION_EDGES)
    return min(indices), max(indices)


def _span_text(token) -> str:
    """The full phrase around a token (its own conjunct-excluded subtree),
    with a leading determiner trimmed ("a director" -> "director").
    """
    start, end = _span_bounds(token)
    while start <= end and token.doc[start].pos_ in _LEADING_STRIP_POS:
        start += 1
    if start > end:
        start = token.i
    return token.doc[start : end + 1].text


def _conjuncts(token):
    """token plus every token conjoined to it via 'conj', so a conjoined
    subject or object expands into one entry per conjunct (pattern 5).
    """
    yield token
    for child in token.children:
        if child.dep_ == "conj":
            yield from _conjuncts(child)


def _sentence_index(sent, doc) -> int:
    """Which sentence (0-indexed) `sent` is within `doc`."""
    for index, candidate in enumerate(doc.sents):
        if candidate.start == sent.start:
            return index
    return -1


def _active_svo(sent, sentence_index: int) -> list[RawTriple]:
    triples = []
    for token in sent:
        if token.dep_ != "nsubj" or token.tag_ in _WH_PRONOUN_TAGS:
            continue
        verb = token.head
        if verb.pos_ != "VERB":
            continue
        dobjs = [child for child in verb.children if child.dep_ == "dobj"]
        if not dobjs:
            continue
        for subj in _conjuncts(token):
            for dobj in dobjs:
                for obj in _conjuncts(dobj):
                    triples.append(
                        RawTriple(
                            subject_text=_span_text(subj),
                            relation=verb.lemma_,
                            object_text=_span_text(obj),
                            sentence_index=sentence_index,
                            pattern="active_svo",
                        )
                    )
    return triples


def _passive(sent, sentence_index: int) -> list[RawTriple]:
    triples = []
    for token in sent:
        if token.dep_ != "nsubjpass" or token.tag_ in _WH_PRONOUN_TAGS:
            continue
        verb = token.head
        if verb.pos_ != "VERB":
            continue
        agents = [child for child in verb.children if child.dep_ == "agent"]
        if not agents:
            continue  # no recoverable subject; nothing emitted
        for agent in agents:
            subjects = [child for child in agent.children if child.dep_ == "pobj"]
            for subj_head in subjects:
                for subj in _conjuncts(subj_head):
                    for obj in _conjuncts(token):
                        triples.append(
                            RawTriple(
                                subject_text=_span_text(subj),
                                relation=verb.lemma_,
                                object_text=_span_text(obj),
                                sentence_index=sentence_index,
                                pattern="passive",
                            )
                        )
    return triples


def _copular(sent, sentence_index: int) -> list[RawTriple]:
    triples = []
    for token in sent:
        if token.dep_ != "nsubj" or token.tag_ in _WH_PRONOUN_TAGS:
            continue
        verb = token.head
        if verb.lemma_ not in _BE_LEMMAS:
            continue
        attrs = [child for child in verb.children if child.dep_ == "attr"]
        if not attrs:
            continue
        for subj in _conjuncts(token):
            for attr in attrs:
                for obj in _conjuncts(attr):
                    triples.append(
                        RawTriple(
                            subject_text=_span_text(subj),
                            relation=verb.lemma_,
                            object_text=_span_text(obj),
                            sentence_index=sentence_index,
                            pattern="copular",
                        )
                    )
    return triples


def _prep_object(sent, sentence_index: int) -> list[RawTriple]:
    triples = []
    for token in sent:
        if token.dep_ != "nsubj" or token.tag_ in _WH_PRONOUN_TAGS:
            continue
        verb = token.head
        if verb.pos_ != "VERB":
            continue
        if any(child.dep_ == "dobj" for child in verb.children):
            continue  # pattern 1 already covers verbs with a direct object
        for prep in (child for child in verb.children if child.dep_ == "prep"):
            pobjs = [child for child in prep.children if child.dep_ == "pobj"]
            if not pobjs:
                continue
            # prep.text keeps its surface case; a sentence-initial fronted PP
            # ("With her approach, Kamen became...") left a capitalized
            # preposition in the relation string ("become With") -- found in
            # the same real-output inspection as the WH-pronoun issue above.
            relation = f"{verb.lemma_} {prep.text.lower()}"
            for subj in _conjuncts(token):
                for pobj in pobjs:
                    for obj in _conjuncts(pobj):
                        triples.append(
                            RawTriple(
                                subject_text=_span_text(subj),
                                relation=relation,
                                object_text=_span_text(obj),
                                sentence_index=sentence_index,
                                pattern="prep_object",
                            )
                        )
    return triples


_EXTRACTORS = (_active_svo, _passive, _copular, _prep_object)


def extract_sentence(sent, doc) -> list[RawTriple]:
    """Run every pattern over one spaCy sentence Span.

    Interrogative sentences are skipped entirely: "Who directed Sinister?"
    parses with the identical nsubj/dobj shape as a genuine declarative SVO
    sentence ("Who" is a syntactically ordinary nsubj), so nothing in the
    dependency tree itself distinguishes a question from a fact. A question
    has no answerable subject and must not be mined (SPEC-extract.md negative
    fixture). HotpotQA passages are prose, not questions, so this never fires
    on the real corpus -- it exists for the documented negative fixture.
    """
    text = sent.text.rstrip()
    if text.endswith("?"):
        return []
    sentence_index = _sentence_index(sent, doc)
    triples: list[RawTriple] = []
    for extractor in _EXTRACTORS:
        triples.extend(extractor(sent, sentence_index))
    return triples


def extract_document(doc) -> list[RawTriple]:
    """Run every pattern over every sentence in a parsed spaCy Doc."""
    triples: list[RawTriple] = []
    for sent in doc.sents:
        triples.extend(extract_sentence(sent, doc))
    return triples
