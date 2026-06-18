# Repo-level convenience targets.
#
# signal_gov — model-internal-signal governance experiment harness.
.PHONY: signal-gov-smoke signal-gov-realcg-smoke signal-gov-external-smoke signal-gov-checkpoint-smoke signal-gov-pilot-assemble signal-gov-cg-pilot signal-gov-run signal-gov-data signal-gov-deps signal-gov-falsify-test signal-gov-falsify

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

# Full hand-built mini-set run (mock features) -> artifacts under out/mock_handbuilt/.
signal-gov-run:
	python -m experiments.signal_gov.run_experiment --mode mock --dataset handbuilt

# Regenerate the on-disk benchmark JSONL from the source-of-truth scenarios.
signal-gov-data:
	python -m experiments.signal_gov.dataset

# Install the harness dependencies (numpy, matplotlib, pytest).
signal-gov-deps:
	python -m pip install -r experiments/signal_gov/requirements.txt
