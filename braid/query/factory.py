"""Factory for constructing named retriever configurations (SPEC-query.md).

One factory constructs every named configuration so `eval` and the CLI
are guaranteed to call the identical retrieval code path.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from braid.query.base import Retriever

SUPPORTED_CONFIGS: tuple[str, ...] = (
    "bm25",
    "dense",
    "fused",
    "fused-rerank",
    "fused-rerank-ft",
)

# The fine-tuned cross-encoder checkpoint produced by `python -m braid.finetune`
# (Task 37). `fused-rerank-ft` reranks with this model instead of the pretrained
# `ms-marco-MiniLM-L-6-v2` that `fused-rerank` uses.
# Resolved against the repo root, not the working directory: a relative path
# would fail (or, worse, resolve to a Hugging Face Hub repo id) whenever the
# process is started from another directory.
FINETUNED_MODEL_PATH = str(Path(__file__).resolve().parents[2] / "models" / "ce-braid")

_REGISTRY: dict[str, Callable[..., Retriever]] = {}


def register_retriever(name: str, factory_fn: Callable[..., Retriever]) -> None:
    """Register a retriever constructor for a configuration name."""
    _REGISTRY[name] = factory_fn


def unregister_retriever(name: str) -> None:
    """Unregister a retriever constructor (primarily for tests)."""
    _REGISTRY.pop(name, None)


def create_retriever(name: str, **kwargs: Any) -> Retriever:
    """Construct a Retriever by its canonical configuration name.

    Parameters
    ----------
    name : str
        One of ("bm25", "dense", "fused", "fused-rerank", "fused-rerank-ft").
    **kwargs : Any
        Configuration-specific options passed to the underlying constructor.

    Returns
    -------
    Retriever
        A retriever instance satisfying the Retriever Protocol.

    Raises
    ------
    ValueError
        If `name` is not one of the supported configuration names.
    NotImplementedError
        If the configuration name is recognized but not yet implemented or registered.
    """
    if name not in SUPPORTED_CONFIGS:
        raise ValueError(
            f"Unknown retriever configuration '{name}'. "
            f"Supported configurations are: {SUPPORTED_CONFIGS}"
        )

    if name in _REGISTRY:
        return _REGISTRY[name](**kwargs)

    # Built-in dispatch for implemented modules
    if name == "bm25":
        try:
            from braid.query.sparse import BM25Retriever

            return BM25Retriever(**kwargs)
        except ImportError as err:
            raise NotImplementedError(
                f"Configuration '{name}' is not yet implemented (Task 28)."
            ) from err

    if name == "dense":
        try:
            from braid.query.dense import DenseRetriever

            return DenseRetriever(**kwargs)
        except ImportError as err:
            raise NotImplementedError(
                f"Configuration '{name}' is not yet implemented (Task 29)."
            ) from err

    if name == "fused":
        try:
            from braid.query.fusion import FusedRetriever

            return FusedRetriever(**kwargs)
        except ImportError as err:
            raise NotImplementedError(
                f"Configuration '{name}' is not yet implemented (Task 31)."
            ) from err

    if name in ("fused-rerank", "fused-rerank-ft"):
        try:
            from braid.query.rerank import RerankRetriever

            if name == "fused-rerank-ft":
                kwargs.setdefault("model_name", FINETUNED_MODEL_PATH)
            return RerankRetriever(name=name, **kwargs)
        except ImportError as err:
            raise NotImplementedError(
                f"Configuration '{name}' is not yet implemented (Task 32)."
            ) from err

    raise NotImplementedError(f"Retriever configuration '{name}' is not registered.")
