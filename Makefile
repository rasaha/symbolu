# Repo-level convenience targets.
#
# signal_gov — model-internal-signal governance experiment harness.
.PHONY: signal-gov-smoke signal-gov-run signal-gov-data signal-gov-deps

# CI smoke test: deterministic, mock features, validates harness + ablation ordering.
signal-gov-smoke:
	python -m pytest experiments/signal_gov/tests/test_smoke.py -q

# Full hand-built mini-set run (mock features) -> artifacts under out/mock_handbuilt/.
signal-gov-run:
	python -m experiments.signal_gov.run_experiment --mode mock --dataset handbuilt

# Regenerate the on-disk benchmark JSONL from the source-of-truth scenarios.
signal-gov-data:
	python -m experiments.signal_gov.dataset

# Install the harness dependencies (numpy, matplotlib, pytest).
signal-gov-deps:
	python -m pip install -r experiments/signal_gov/requirements.txt
