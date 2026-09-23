"""spaCy NER over the corpus.

Runs offline, as a batch, with no OpenSearch/Neo4j containers up (SPEC.md
Hardware: en_core_web_trf and the databases are never resident at the same
time on 8 GiB). Peak RSS is recorded so that constraint is a measured number,
not an assumption.
"""

from __future__ import annotations

import resource
from dataclasses import dataclass

MODEL_NAME = "en_core_web_trf"


@dataclass(frozen=True)
class Entity:
    text: str
    label: str
    start_char: int  # offset into the passage's normalized text
    end_char: int


def load_pipeline(model_name: str = MODEL_NAME):
    """Load the spaCy pipeline. A separate call from `extract_entities` so a
    caller processing many passages loads the (expensive, transformer-backed)
    pipeline once.
    """
    import spacy

    return spacy.load(model_name)


def extract_entities(doc) -> list[Entity]:
    """Named entities from an already-parsed spaCy Doc, as char-span records
    into that Doc's text.
    """
    return [
        Entity(text=ent.text, label=ent.label_, start_char=ent.start_char, end_char=ent.end_char)
        for ent in doc.ents
    ]


def peak_rss_mb() -> float:
    """Peak resident set size of this process so far, in MB.

    `ru_maxrss` is bytes on Linux, kilobytes on macOS/BSD -- resource module
    docs are silent on this and it is a well-known platform inconsistency, so
    this branches on `sys.platform` rather than guessing.
    """
    import sys

    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return raw / (1024 * 1024)
    return raw / 1024
