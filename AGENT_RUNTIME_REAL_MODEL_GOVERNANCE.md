# Agent Runtime — Real-Model Governance Containment (Deliverable 5)

Governance containment for real-model proposals (§7). Labels: `FACT` · `INTERPRETATION`.

## Status: real-model containment `BLOCKED_NO_REAL_MODEL`; structural containment HOLDS
`FACT`. Containment with LIVE-model proposals cannot be evidenced (no model). What IS proven, and is
input-source-agnostic (it contains ANY malformed/unsafe proposal regardless of who produced it):
- trusted registry supplies risk class; model risk/authorization/eligibility fields ignored
  (`test_inv1_*`, `test_inv2_*`, `test_model_cannot_self_classify_risk`);
- malformed output fails closed before execution, incl. over a real HTTP adapter
  (`test_malformed_real_output_fails_closed`);
- ActionGate denial and ACP hold prevent execution; stale state → new observation/CER; modified action
  → new CER identity; no consequential tool reaches a handler; no fallback bypasses the governed
  executor (`test_phase2_security_and_replan`, `AGENT_RUNTIME_BYPASS_AUDIT.md`);
- no fabricated-success observation: the runner flags any case where a non-PROCEED composed outcome is
  reported as `executed` (0 such cases in the deterministic runs).

## Interpretation
`INTERPRETATION`. The containment MECHANISM is proven to hold against adversarial/malformed inputs —
which is exactly the class of output a poor real model would produce. But the milestone requires this
be exercised with actual real-model proposals; that step is blocked. The Phase-3 real-model
containment verdict is therefore **blocked**, while the structural boundary remains intact (0 boundary
violations across all deterministic runs). A live-model run will exercise it directly using the ready
runner.
