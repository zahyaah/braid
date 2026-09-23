"""The corpus freeze (decision D6).

The pipeline order is ingest -> dedupe -> manifest with content hash -> freeze
-> author queries and judgments. Once frozen, a relevance judgment can never
drift underneath a corpus change, because the corpus cannot move.

Remapping a gold passage after the freeze is a judgment change, not an ingest
fix, and is ask-first under SPEC.md Boundaries. This module makes doing it
silently impossible rather than merely discouraged.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from braid.ingest.manifest import Manifest, utc_now
from braid.ingest.models import Passage

_FIELD = b"\x00"
_RECORD = b"\x1e"


class FrozenCorpusError(RuntimeError):
    """Raised when an operation would modify a passage in a frozen corpus."""


def corpus_hash(passages: list[Passage]) -> str:
    """sha256 over the sorted sequence of (passage_id, text) pairs.

    Covers content, not just ids, so an edit that preserves ids still changes
    the hash. Passages are sorted by id, so the hash does not depend on file
    order.
    """
    digest = hashlib.sha256()
    for passage in sorted(passages, key=lambda p: p.passage_id):
        digest.update(passage.passage_id.encode("utf-8"))
        digest.update(_FIELD)
        digest.update(passage.text.encode("utf-8"))
        digest.update(_RECORD)
    return digest.hexdigest()


def ensure_mutable(manifest: Manifest, action: str) -> None:
    """Guard every write path that could change an existing passage."""
    if manifest.frozen:
        raise FrozenCorpusError(
            f"corpus is frozen (frozen_at={manifest.frozen_at}); refusing to {action}. "
            "Changing a frozen passage is a judgment change and is ask-first under "
            "SPEC.md Boundaries."
        )


def freeze(manifest_path: Path, passages: list[Passage]) -> Manifest:
    """Record the content hash and set frozen=True. Idempotent only if nothing changed."""
    manifest = Manifest.read(manifest_path)
    digest = corpus_hash(passages)
    if manifest.frozen:
        if manifest.corpus_hash != digest:
            raise FrozenCorpusError(
                "corpus is frozen but its content hash has changed: "
                f"manifest={manifest.corpus_hash} actual={digest}"
            )
        return manifest
    manifest.corpus_hash = digest
    manifest.frozen = True
    manifest.frozen_at = utc_now()
    manifest.write(manifest_path)
    return manifest


def verify(manifest_path: Path, passages: list[Passage]) -> None:
    """Fail loudly if the corpus on disk no longer matches the frozen hash."""
    manifest = Manifest.read(manifest_path)
    if not manifest.frozen:
        raise FrozenCorpusError("corpus is not frozen; nothing to verify")
    digest = corpus_hash(passages)
    if digest != manifest.corpus_hash:
        raise FrozenCorpusError(
            f"corpus hash mismatch: manifest={manifest.corpus_hash} actual={digest}"
        )
