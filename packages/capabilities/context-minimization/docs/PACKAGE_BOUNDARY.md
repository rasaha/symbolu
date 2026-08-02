# Package boundary

## The core is a leaf

`ugence-context-minimization` imports **only the Python standard library**. This is
enforced by an AST-based import-boundary test (`tests/boundaries/test_import_boundaries.py`)
that fails the build if any module imports anything outside the stdlib + itself.

## Forbidden imports (core must never import)

ActionGate (`action_gate_ref`, `action_gateway`), Action Clearance, TAP, Decision
Authority, Governance Provider Framework, Code Governance, Governance Contracts,
Agent Runtime, StoryGraph, AI Hiring, model selection, Hybrid LLM, robotics,
`cer_v0_*`, Console API, products, experiments, Hugging Face, PyTorch, model APIs,
cloud/database clients, tokenizers.

Concrete adapters (e.g. an ActionGate-derived oracle) **may** import the core; the
core imports **none** of them. Dependencies point inward only.

## Why no Governance Contracts dependency

The neutral `InvarianceOracle` returns a self-contained `OracleEvaluation` whose
`equivalence_key` is an opaque string. The core needs nothing from the governance
contract layer to compare keys, so it takes no dependency on it — keeping the leaf
truly stdlib-only. An integration adapter that also speaks governance contracts is
free to depend on both.

## Not in the wheel

Model weights, benchmark corpora/results, RunPod scripts, plots, detector-training
code, and large corpora are **never** shipped in the core wheel. The isolated-install
verifier asserts the wheel contains only `ugence_context_minimization/` (+ `py.typed`)
and its dist-info, with no foreign top-level package.
