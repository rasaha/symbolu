"""internal_policy_controller v2 — a FAITHFUL redo of the draft->policy->final test.

Fixes the v1 defects exposed by IMPLEMENTATION_FORENSIC_REVIEW.md:
- a REAL LLM generates the draft and rewrites the final answer (no templates/regex);
- the FULL available Symbol-U state is computed (Vritti/Guna/Kosha/Aspect/Resonance/PSE),
  not one phonological backend;
- an EXPLICIT, label-semantic policy-translation layer (not a learned 5-label clf);
- INDEPENDENT LLM-judge evaluation on a rubric (no circular keyword markers, no
  regex deletion, no oracle sentiment lexicon);
- relabel/shuffle controls that actually change the policy (no linear tautology).

Isolated. No older file modified or deleted. Reuses only complementarity_probe and
symbolu_core.formulas to compute Symbol-U state.

ENVIRONMENT NOTE: no LLM API key is available in this sandbox, so the decisive run
cannot execute here. The harness is wired for anthropic/mistral; the mock backend
is PLUMBING-ONLY and yields NO scientific verdict. See V2 report for commands.
"""
