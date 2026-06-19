# Repo-level convenience targets.
#
# signal_gov — model-internal-signal governance experiment harness.
.PHONY: signal-gov-smoke signal-gov-realcg-smoke signal-gov-external-smoke signal-gov-checkpoint-smoke signal-gov-pilot-assemble signal-gov-cg-pilot signal-gov-run signal-gov-data signal-gov-deps signal-gov-falsify-test signal-gov-falsify signal-gov-d1-test signal-gov-d1 signal-gov-d1-mock signal-gov-diag-test signal-gov-d4 signal-gov-d5

# CI smoke test: deterministic, mock features, validates harness + ablation ordering.
signal-gov-smoke:
	python -m pytest experiments/signal_gov/tests/test_smoke.py -q

# real_cg plumbing validation: runs the LIVE internal-signal path via the
# deterministic StubCGLLMAdapter. No torch/GPU/checkpoint required (numpy + the
# in-repo agentic package only). Skips cleanly if the agentic package is absent.
signal-gov-realcg-smoke:
	python -m pytest experiments/signal_gov/tests/test_realcg_smoke.py -q

# External-benchmark ingestion (AgentDojo / InjecAgent) on tiny offline fixtures.
signal-gov-external-smoke:
	python -m pytest experiments/signal_gov/tests/test_external_loaders.py -q

# Fastest-falsification: fabrication scenarios + conditional decision rule (torch-free).
signal-gov-falsify-test:
	python -m pytest experiments/signal_gov/tests/test_falsification.py -q

# Stock-checkpoint extraction (real_checkpoint_cached) via a torch-free mock backend:
# real logit-entropy + proxy-state vritti/JEPA, cache round-trip, offline C1-C4.
signal-gov-checkpoint-smoke:
	python -m pytest experiments/signal_gov/tests/test_real_checkpoint_cached.py -q

# Assemble the balanced 30-50 scenario pilot set (CPU; no GPU/checkpoint).
# PER_CATEGORY=10 -> 30 scenarios; set PER_CATEGORY=15 for 45.
PER_CATEGORY ?= 10
signal-gov-pilot-assemble:
	python -m experiments.signal_gov.pilot --per-category $(PER_CATEGORY) \
	  --out experiments/signal_gov/data/pilot_30_50.jsonl

# GPU + CG CHECKPOINT REQUIRED — NOT runnable in CI. The first true pilot result.
# See experiments/signal_gov/CG_PILOT_RUNBOOK.md. Requires torch + transformers +
# symbolu_training + a TRAINED CG state-dict. Set CG_STATE_DICT (trained *_model.pt);
# optional CG_BASE_MODEL (default mistral), CG_QUANTIZE (4bit|8bit), CG_DEVICE (auto),
# CG_PILOT_OUT, CG_ALLOW_UNTRAINED=1 (override the fail-closed check; plumbing only).
# Fails closed if the state-dict looks vanilla/untrained. Writes <out>/features.jsonl
# by default for offline `--mode cached` replay.
signal-gov-cg-pilot:
	@test -n "$$CG_STATE_DICT" || { \
	  echo "ERROR: set CG_STATE_DICT=<trained *_model.pt> (+ optional CG_BASE_MODEL). See experiments/signal_gov/CG_PILOT_RUNBOOK.md"; \
	  exit 1; }
	python -m experiments.signal_gov.run_experiment --mode real_cg \
	  --checkpoint "$${CG_BASE_MODEL:-mistralai/Mistral-7B-v0.3}" \
	  --cg-state-dict "$$CG_STATE_DICT" \
	  --cg-quantize "$${CG_QUANTIZE:-4bit}" --cg-device "$${CG_DEVICE:-auto}" \
	  $${CG_ALLOW_UNTRAINED:+--allow-untrained-cg-head} \
	  --scenarios experiments/signal_gov/data/pilot_30_50.jsonl \
	  --out "$${CG_PILOT_OUT:-runs/cg_pilot}"

# GPU + CG CHECKPOINT REQUIRED — the fastest-falsification run. bf16 (no quantize) by
# default to match training precision. Emits a SCALE or KILL/DEPRIORITIZE verdict.
signal-gov-falsify:
	@test -n "$$CG_STATE_DICT" || { \
	  echo "ERROR: set CG_STATE_DICT=<trained *_model.pt> (+ optional CG_BASE_MODEL)."; \
	  exit 1; }
	python -m experiments.signal_gov.falsification.run \
	  --checkpoint "$${CG_BASE_MODEL:-mistralai/Mistral-7B-v0.3}" \
	  --cg-state-dict "$$CG_STATE_DICT" --cg-device "$${CG_DEVICE:-auto}" \
	  $${CG_QUANTIZE:+--cg-quantize $$CG_QUANTIZE} \
	  $${CG_ALLOW_UNTRAINED:+--allow-untrained-cg-head} \
	  --out "$${FALSIFY_OUT:-runs/falsify}"

# Diagnostic D1 — signal-survival ladder. Probe + ladder + every localization branch,
# torch-free (synthetic caches + the torch-free mock backend through the real bridge).
signal-gov-d1-test:
	python -m pytest experiments/signal_gov/tests/test_d1_ladder.py -q

# All diagnostics tests (D1 ladder + D4 collapse + D5 entropy-definition), torch-free.
signal-gov-diag-test:
	python -m pytest experiments/signal_gov/tests/test_d1_ladder.py \
	  experiments/signal_gov/tests/test_d4_d5.py -q

# OFFLINE follow-ups — no GPU, no torch, no model. Consume a D1 cache (d1_cache.npz).
# D4: vritti / component collapse + twin separation + best-dim AUROC over the 32-D state.
# D5: correlation of raw predictive entropy vs entropy_from_sovereign_state.
# Run these AFTER `make signal-gov-d1`; set D1_CACHE to point at the produced npz.
D1_CACHE ?= runs/d1/d1_cache.npz
signal-gov-d4:
	python -m experiments.signal_gov.diagnostics.d4_vritti \
	  --from-cache "$(D1_CACHE)" --out "$${D4_OUT:-runs/d4}"
signal-gov-d5:
	python -m experiments.signal_gov.diagnostics.d5_entropy_def \
	  --from-cache "$(D1_CACHE)" --out "$${D5_OUT:-runs/d5}"

# Diagnostic D1 plumbing run (torch-free, deterministic, LABEL-BLIND mock): exercises
# the full cache -> ladder -> report pipeline. No result claim. -> runs/d1_mock/.
signal-gov-d1-mock:
	python -m experiments.signal_gov.diagnostics.run --mock --out "$${D1_OUT:-runs/d1_mock}"

# GPU + CG CHECKPOINT REQUIRED — the real D1 localization run. One forward pass per
# scenario caches logits + all-layer hidden + the 32-D state; the ladder reports AUROC
# at each rung on the fooled subset and emits a PROJECTION-vs-ENTROPY-DEFINITION verdict
# (which selects R1/R2). Read-only; no retrain, no product-path change, no success claim.
# bf16 by default to match training precision. Set CG_STATE_DICT (trained *_model.pt).
signal-gov-d1:
	@test -n "$$CG_STATE_DICT" || { \
	  echo "ERROR: set CG_STATE_DICT=<trained *_model.pt> (+ optional CG_BASE_MODEL)."; \
	  exit 1; }
	python -m experiments.signal_gov.diagnostics.run \
	  --checkpoint "$${CG_BASE_MODEL:-mistralai/Mistral-7B-v0.3}" \
	  --cg-state-dict "$$CG_STATE_DICT" --cg-device "$${CG_DEVICE:-auto}" \
	  $${CG_QUANTIZE:+--cg-quantize $$CG_QUANTIZE} \
	  $${CG_ALLOW_UNTRAINED:+--allow-untrained-cg-head} \
	  --out "$${D1_OUT:-runs/d1}"

# Full hand-built mini-set run (mock features) -> artifacts under out/mock_handbuilt/.
signal-gov-run:
	python -m experiments.signal_gov.run_experiment --mode mock --dataset handbuilt

# Regenerate the on-disk benchmark JSONL from the source-of-truth scenarios.
signal-gov-data:
	python -m experiments.signal_gov.dataset

# Install the harness dependencies (numpy, matplotlib, pytest).
signal-gov-deps:
	python -m pip install -r experiments/signal_gov/requirements.txt
