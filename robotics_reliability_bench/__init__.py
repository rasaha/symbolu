"""Robotics reliability redesign — evaluation-only benchmark harness.

This package is EVALUATION-ONLY. It imports the real production BCVF
implementations (``symbolu_robotics.formulas.bcvf`` and
``symbolu_robotics.bcvf_autonomous``) but MUST NOT be imported by any
production path. It exists to produce the evidence artifacts required by
the robotics-reliability redesign milestone:

  * Part 1 — action-scorer counterexamples (``run_action_counterexamples.py``)
  * Part 2 — predictor-trust kernel audit (``run_kernel_audit.py``)
  * Part 3 — deterministic baselines (``action_baselines.py``,
             ``predictor_trust_baseline.py``)
  * Part 4 — incremental-value study (``run_incremental_value.py``)

Nothing here mutates production code. All results are written under
``robotics_reliability_bench/results/`` as machine-readable JSON.
"""
