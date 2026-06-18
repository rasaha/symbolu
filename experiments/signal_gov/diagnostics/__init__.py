"""Read-only probe diagnostics for the CG sovereign-state signal (D1-D6).

Isolated subpackage: imports the main harness primitives (Scenario, oracle,
features, metrics, cg_checkpoint) and the fabrication probe set, but MODIFIES none
of them and is wired into NO product path. Per AGENTIC_FRAMEWORK_CG_RESEARCH_PLAN.md
§2, these localize where the predictive-uncertainty signal is lost. D1 (the decisive
diagnostic) is implemented here; it retrains nothing and makes no success claim.
"""
