# ActionGate vNext — Deterministic Remediation Guidance (design only)

**Design-only milestone. No code.** How ActionGate should emit machine-readable remediation
guidance while keeping the decision a pure function of
`(envelope, signed_policy, evidence, approvals, state)` — LLMs stay outside the trust boundary.

Grounded in the reference gate (`../action_gate_ref/`: gate.py, policy.py, projection.py,
evidence.py, approval.py, audit.py, errors.py, schema.py). Nothing here is implemented.

| document | covers (milestone questions) |
|---|---|
| `ACTIONGATE_REMEDIATION_DESIGN.md` | thesis + invariants; `required_changes[]` (Q1); `all_unmet_conditions[]` (Q2); seventh outcome (Q9); the five conclusion answers |
| `ACTIONGATE_REQUIRED_CHANGES_SCHEMA.md` | concrete schema, `remediation_class` enum, reason codes, per-operator `required` payloads, worked examples |
| `ACTIONGATE_RETRY_ARCHITECTURE.md` | retry classification matrix (Q3); retry governance (Q5); action-hash evolution & replay-impossibility (Q6); external planner sequence diagrams (Q10) |
| `ACTIONGATE_THREAT_MODEL_REMEDIATION.md` | disclosure levels FULL/STANDARD/MINIMAL/NONE (Q4); new attack surfaces (Q7) |
| `ACTIONGATE_COMPATIBILITY_REVIEW.md` | SDK/CLI/MCP/schema/conformance/versioning (Q8); additive-MINOR recommendation |
| `ACTIONGATE_REMEDIATION_ROADMAP.md` | phased, invariant-gated rollout + the five conclusion answers |

## Implementation
- `r1/` — **R1 (implemented):** additive remediation projection (opt-in, default OFF).
  Code: `../action_gate_ref/remediation.py`, CLI `decide --remediation-mode`, tests
  `../tests/test_remediation.py`. See `r1/R1_IMPLEMENTATION_README.md`.

## Headline recommendations
1. `required_changes[]` — **implement** (deterministic, audit-neutral, additive).
2. `all_unmet_conditions[]` — **expose, disclosure-gated to FULL**; keep `dispositive_rules` as the single audit anchor.
3. Six outcomes — **keep unchanged**.
4. Seventh outcome — **no** (payload enrichment only; Recommendation A).
5. Roadmap — additive, disclosure-defaulted, invariant-gated phases; no hashed surface touched.
