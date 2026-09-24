"""CLI for the finetune module: ``python -m braid.finetune --out models/ce-braid``.

Builds the disjoint training pairs (``braid.finetune.pairs``) and then fine-tunes
the cross-encoder (``braid.finetune.train``), writing ``reports/finetune.md``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from braid.finetune.pairs import (
    DEFAULT_NUM_TRAIN_QUESTIONS,
    FINETUNE_SEED,
    build_pairs_from_disk,
)
from braid.finetune.train import (
    BATCH_SIZE,
    DEFAULT_OUTPUT,
    EPOCHS,
    LEARNING_RATE,
    TRAIN_SEED,
    render_report,
    train,
)

REPORT_PATH = Path("reports/finetune.md")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m braid.finetune",
        description="Build disjoint training pairs and fine-tune the cross-encoder.",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="model output dir")
    parser.add_argument("--pairs-seed", type=int, default=FINETUNE_SEED, help="pairs draw seed")
    parser.add_argument(
        "--num-questions", type=int, default=DEFAULT_NUM_TRAIN_QUESTIONS, help="training questions"
    )
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--learning-rate", type=float, default=LEARNING_RATE)
    parser.add_argument("--train-seed", type=int, default=TRAIN_SEED, help="train/dev split seed")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    pairs, pair_report = build_pairs_from_disk(
        seed=args.pairs_seed, num_questions=args.num_questions
    )
    training = train(
        pairs,
        output_dir=args.out,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        train_seed=args.train_seed,
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(render_report(pair_report, training), encoding="utf-8")
    print(f"report -> {REPORT_PATH}")
    print(f"model -> {args.out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
