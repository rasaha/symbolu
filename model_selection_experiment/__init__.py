"""model_selection_experiment package.

RESEARCH IMPLEMENTATION — intentionally SEPARATE from the canonical Model Selection
product core (``ugence_model_selection`` / distribution ``ugence-model-selection``).

This is a self-contained synthetic benchmark/ablation harness for the Model Selection
policy. It carries its OWN dict-based selection engine (``policy.route`` over JSON
registry/task/telemetry structures) plus a simulator, oracle, baselines, and metrics.
Its I/O contract and multi-source quality fusion differ from the canonical core's
dataclass API, so it is classified — per the migration's disposition rules — as a
genuinely different *research algorithm*, not a copy of the canonical engine. It is NOT
folded into, nor exported from, the canonical package: unifying the two would change
selection behaviour, which this behaviour-preserving migration does not do. The
canonical core is the production-shaped source (formerly ``execution_gate``); this
package remains research. See ``docs/migrations/model_selection/RESEARCH_SEPARATION.md``.
"""
