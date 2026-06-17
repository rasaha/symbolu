"""
signal_gov — Minimum experiment harness for the question:

    Do model-internal signals (entropy, coherence, vritti, JEPA disagreement)
    improve governance decisions over text-level governance?

The harness compares four *nested-ablation* governance scoring configurations
as detectors of unsafe tool calls:

    C1  approval only
    C2  approval + risk taxonomy
    C3  C2 + text-level confidence
    C4  C3 + internal model signals

It is deliberately small, deterministic, and reviewer-friendly. See README.md
for the methodology, the pre-registered benchmark schema, and the (pre-registered)
success/failure criteria.

IMPORTANT: this package ships a *reproducible harness and a smoke test*, not a
proven result. The `mock` feature mode uses synthetic, constructed-to-be-informative
features purely to validate the plumbing in CI. Scientific conclusions require the
`real_cg` feature mode, the full balanced benchmark, and a held-out evaluation.
"""

from experiments.signal_gov.dataset import (
    Scenario,
    SCHEMA_FIELDS,
    BENCHMARK_CATEGORIES,
    RISK_LEVELS,
    load_handbuilt,
    load_smoke,
)

__all__ = [
    "Scenario",
    "SCHEMA_FIELDS",
    "BENCHMARK_CATEGORIES",
    "RISK_LEVELS",
    "load_handbuilt",
    "load_smoke",
]
