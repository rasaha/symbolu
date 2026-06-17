# Repo-level convenience targets.
#
# signal_gov — model-internal-signal governance experiment harness.
.PHONY: signal-gov-smoke signal-gov-realcg-smoke signal-gov-external-smoke signal-gov-checkpoint-smoke signal-gov-run signal-gov-data signal-gov-deps

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

# Stock-checkpoint extraction (real_checkpoint_cached) via a torch-free mock backend:
# real logit-entropy + proxy-state vritti/JEPA, cache round-trip, offline C1-C4.
signal-gov-checkpoint-smoke:
	python -m pytest experiments/signal_gov/tests/test_real_checkpoint_cached.py -q

# Full hand-built mini-set run (mock features) -> artifacts under out/mock_handbuilt/.
signal-gov-run:
	python -m experiments.signal_gov.run_experiment --mode mock --dataset handbuilt

# Regenerate the on-disk benchmark JSONL from the source-of-truth scenarios.
signal-gov-data:
	python -m experiments.signal_gov.dataset

# Install the harness dependencies (numpy, matplotlib, pytest).
signal-gov-deps:
	python -m pip install -r experiments/signal_gov/requirements.txt
