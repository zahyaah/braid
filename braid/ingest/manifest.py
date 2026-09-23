"""The corpus manifest: what was built, from what, with which seed, and whether it is frozen.

Every later report cites this file. It is also where decision D6's freeze state
lives, so it is the single thing that says whether judgments may be authored.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MANIFEST_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


@dataclass
class Manifest:
    dataset: str
    config: str
    split: str
    datasets_version: str
    seed: int
    target_passages: int
    questions_sampled: int
    questions_out: int
    passages_before_dedupe: int
    passages_after_dedupe: int
    dedupe: dict[str, Any]
    remap: dict[str, Any]
    manifest_version: int = MANIFEST_VERSION
    created_at: str = field(default_factory=utc_now)
    git_commit: str | None = field(default_factory=git_commit)
    corpus_hash: str | None = None
    frozen: bool = False
    frozen_at: str | None = None
    # Appended on every post-freeze incremental add: {"at", "before", "after", "added"}.
    hash_history: list[dict[str, Any]] = field(default_factory=list)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @classmethod
    def read(cls, path: Path) -> Manifest:
        return cls(**json.loads(path.read_text(encoding="utf-8")))
