# Implementation Decisions — Agent Workforce Composer P1

Conservative, evidence-backed decisions, grounded in the live merged code and the
Phase 0 ADR / boundary contract.

1. **Data-only compiler seam.** The adapter consumes a *serialized* `workflow_ir.v1`
   document rather than importing `ugence_policy_workflow_compiler`, so AWC stays a
   leaf importable outside the monorepo (boundaries.json: "CompilerWorkflowAdapter
   (data-only, versioned)"). Neutral enum mirrors in `contracts.py` reproduce the
   compiler vocabulary by value; the optional `compiler-reference` test proves
   fidelity against the live compiler.

2. **`pydantic` + stdlib only.** The upstream compiler capability uses `pydantic`;
   AWC follows the same convention for frozen, `extra='forbid'`, content-addressed
   models. No other dependency is permitted.

3. **Single `NodeDisposition` enum (8 values).** Merges the Phase 0 five-value
   non-agent outcome set with the adapter's `AI_AGENT_ELIGIBLE`,
   `EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP`, and `UNSUPPORTED_NODE` (plus
   `INVALID_NODE` for fail-closed missing metadata). `NonAgentDisposition` holds any
   value except `AI_AGENT_ELIGIBLE`, giving clean total node accounting.

4. **Agent-eligible surface = advisory, compiler-owned `EVIDENCE_REQUIREMENT`.** In
   the current governance-centric IR, this is the honest set of agent-appropriate
   cognitive nodes; every authoritative/governance/human kind is preserved as
   non-agent work. Human-authority node kinds are classified *before* the generic
   governance-owner rule so a binding approval reads as `HUMAN_AUTHORITY_REQUIRED`.

5. **Role field provenance separation.** Source-derived fields come from the IR node;
   enterprise-policy-derived fields come from an injected `role_overlay` (validated
   against a closed field set); later-phase optimization fields are typed but never
   ranked. The adapter never infers role constraints from free text.

6. **Evidence precedence OBSERVED > MEASURED > DECLARED**, verified against the AWC
   Phase 0 design and Model Selection's source precedence. Declared-only never
   satisfies a MEASURED/OBSERVED hard requirement; expiry is driven by injected
   logical time; evidence is version-pinned.

7. **Complete elimination accounting (no short-circuit by default).** The engine
   accumulates every applicable hard failure so explanations are exhaustive
   (`agent_high_cost` reports all four independent breaches at once).

8. **Fail-closed everywhere.** Unknown IR version, missing source digest, malformed
   graph, undeclared overlay field, snapshot-integrity mismatch, unknown/expired
   evidence — all fail closed. `INDETERMINATE` is only reachable when
   `fail_closed_on_unknown` is explicitly disabled.

9. **No ranking leakage.** No score/rank/winner/recommendation field or function
   exists; asserted by `test_eligibility.py` and `test_public_api.py`.

10. **No H16 change / no facade in P1.** The canonical `AgentProfile` is a distinct
    type; the H16 re-export candidate is deferred (field diff in
    `H16_CANONICALIZATION_MAP.md`).

11. **Branch.** The environment mandates development on
    `claude/agent-workforce-composer-p1-54g1d0`; this supersedes the prompt's
    suggested `chatgpt/awc-p1-eligibility` name. One PR is opened and left unmerged.
