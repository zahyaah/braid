#!/usr/bin/env bash
# Reproduce every number reported in README.md from a clean checkout.
#
# Usage:
#   ./scripts/reproduce.sh
#
# Requires: docker (OpenSearch + Neo4j), a Python 3.10 venv at .venv with the
# dependencies installed (see README.md), and a HuggingFace cache with the
# en_core_web_trf model and cross-encoder/ms-marco-MiniLM-L-6-v2 checkpoint.
#
# This is the one script behind acceptance criterion 6: every metric, CI,
# criterion-3 count, latency number, and both generated reports are produced
# here, with every random seed pinned and echoed.

set -euo pipefail

cd "$(dirname "$0")/.."

# ---------------------------------------------------------------------------
# Pinned seeds (echoed so a reviewer can confirm none drift across runs).
# ---------------------------------------------------------------------------
INGEST_SEED=20260923
EXTRACT_SEED=20260923
PAIRS_SEED=20260924
TRAIN_SEED=20260925

echo "== Braid reproduction run =="
echo "ingest seed   : ${INGEST_SEED}"
echo "extract seed  : ${EXTRACT_SEED}"
echo "pairs seed    : ${PAIRS_SEED}"
echo "train seed    : ${TRAIN_SEED}"

PY=".venv/bin/python"
[ -x "${PY}" ] || { echo "ERROR: .venv/bin/python not found; create the venv first." >&2; exit 1; }

# ---------------------------------------------------------------------------
# Services (OpenSearch + Neo4j). Fail loudly if they cannot come up.
# ---------------------------------------------------------------------------
echo "== Starting services =="
docker compose up -d >/dev/null

# Give the containers a moment, then verify all three stores report healthy.
# Services only: on a clean checkout the dense index file does not exist yet,
# and "down" there is expected, not an error (it is built in step 4).
if ! "${PY}" -m braid.index health --services-only; then
  echo "ERROR: OpenSearch or Neo4j is not reachable." >&2
  echo "       Run 'docker compose up -d' and 'python -m braid.index health' to diagnose." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# 1. Ingest (build corpus + questions + manifest), then freeze and verify.
# ---------------------------------------------------------------------------
echo "== Ingest =="
"${PY}" -m braid.ingest build --seed "${INGEST_SEED}" --target 1000 --split validation
"${PY}" -m braid.ingest freeze
"${PY}" -m braid.ingest verify

# ---------------------------------------------------------------------------
# 2. Corpus-hash gate: the freshly built corpus must match the queryset the
#    eval set was locked against (decision D3). Abort before evaluating if not.
# ---------------------------------------------------------------------------
echo "== Corpus-hash gate =="
EXPECTED_HASH=$("${PY}" -c "import json;print(json.load(open('braid/eval/queryset/queryset-manifest.json'))['corpus_hash'])")
ACTUAL_HASH=$("${PY}" -c "import json;print(json.load(open('data/manifest.json'))['corpus_hash'])")
if [ "${ACTUAL_HASH}" != "${EXPECTED_HASH}" ]; then
  echo "ERROR: corpus_hash mismatch -- queryset locked to ${EXPECTED_HASH} but built ${ACTUAL_HASH}." >&2
  exit 1
fi
echo "corpus_hash ${ACTUAL_HASH} matches committed queryset."

# ---------------------------------------------------------------------------
# 3. Extract (triples + 100-sentence annotation sample + quality report).
# ---------------------------------------------------------------------------
echo "== Extract =="
# (--corpus/--corpus-manifest are top-level flags, not `build` flags; defaults apply.)
"${PY}" -m braid.extract build \
  --out data/triples.jsonl \
  --manifest-out data/extract-manifest.json
"${PY}" -m braid.extract sample --n 100 --seed "${EXTRACT_SEED}" --out data/extract-sample.jsonl
"${PY}" -m braid.extract quality

# ---------------------------------------------------------------------------
# 4. Index (OpenSearch BM25 + FAISS dense + Neo4j graph).
# ---------------------------------------------------------------------------
echo "== Index =="
"${PY}" -m braid.index build --all
"${PY}" -m braid.index health

# ---------------------------------------------------------------------------
# 5. Validate the committed queryset.
# ---------------------------------------------------------------------------
echo "== Queryset =="
"${PY}" -m braid.eval.queryset validate

# ---------------------------------------------------------------------------
# 6. Fine-tune the cross-encoder (produces models/ce-braid + reports/finetune.md).
#    Must run BEFORE the final evaluation so the before/after section includes
#    the fine-tuned configuration (fused-rerank-ft).
# ---------------------------------------------------------------------------
echo "== Fine-tune =="
"${PY}" -m braid.finetune --out models/ce-braid \
  --pairs-seed "${PAIRS_SEED}" --train-seed "${TRAIN_SEED}"

# ---------------------------------------------------------------------------
# 7. Evaluate: criterion-1 table, criterion-2 bootstrap CIs, before/after
#    comparison, criterion-3 exhaustive count, and D1 latency.
# ---------------------------------------------------------------------------
echo "== Evaluate =="
"${PY}" -m braid.eval --all-configs --bootstrap 1000
"${PY}" -m braid.eval --criterion3
"${PY}" -m braid.eval --latency --config fused-rerank

echo "== Done. See reports/ for every reproduced number. =="
