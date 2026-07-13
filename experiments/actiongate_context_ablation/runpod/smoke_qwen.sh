#!/usr/bin/env bash
# Plumbing smoke test on the REAL 0.5B Qwen. Fails if the mock backend is selected.
set -euo pipefail
cd "$(dirname "$0")"

export MODEL_ID="${MODEL_ID:-Qwen/Qwen2.5-0.5B-Instruct}"
export MODEL_DIR="${MODEL_DIR:-/workspace/models/Qwen2.5-0.5B-Instruct}"
export RESULTS_ROOT="${RESULTS_ROOT:-/workspace/results/actiongate-context-qwen}"
export RUN_KIND="SMOKE_ONLY"
export RUN_ID="${RUN_ID:-smoke_qwen05b}"
export BUDGETS="${BUDGETS:-0.3}"
export METHODS="${METHODS:-original,protected}"
export CONTEXTS_LIMIT="${CONTEXTS_LIMIT:-4}"
export MAX_NEW_TOKENS="${MAX_NEW_TOKENS:-64}"
export DTYPE="${DTYPE:-auto}"
export DEVICE="${DEVICE:-cuda}"
export ALLOW_MOCK=0        # a smoke run must use the real model

echo "[smoke] downloading smoke model"
python3 download_model.py
echo "[smoke] probing (GPU + model required)"
PROBE_REQUIRE_GPU=1 PROBE_REQUIRE_MODEL=1 python3 probe_environment.py
echo "[smoke] running SMOKE_ONLY (${METHODS} @ ${BUDGETS}, ${CONTEXTS_LIMIT} contexts)"
python3 run_benchmark.py

echo "[smoke] validating non-mock generated text + nonzero tokens + parsing"
python3 - <<'PY'
import sys; sys.path.insert(0,".")
import runpod_common as RC
cfg = RC.load_config()
recs = RC.read_records(RC.records_path(cfg))
assert recs, "no records persisted"
assert all(r["run_kind"] == "SMOKE_ONLY" for r in recs), "run not labelled SMOKE_ONLY"
assert all(r["is_real"] for r in recs), "MOCK backend used — smoke must use the real model"
assert any(r["completion_tokens"] > 0 for r in recs), "no tokens generated"
assert any(r["output"].strip() for r in recs), "no non-empty generated text"
print(f"[smoke] OK: {len(recs)} real records, sample output={recs[0]['output'][:60]!r}")
PY
echo "[smoke] PASS"
