# Enforcement-Promotion Checklist — Composite Sequence-Risk Analyzer

**Enforcement is prohibited** until every criterion below is demonstrated on a
**frozen** workflow. There is **no global enforcement switch**: promotion is
always scoped. In the current phase the analyzer runs advisory / shadow only, and
this checklist is the gate that a future phase must pass before any binding
consequence is enabled.

## Preconditions (all required, on a frozen workflow)

- [ ] Trusted identity and approval evidence are available (verified providers,
      not self-declared purpose).
- [ ] False-escalation rate is within a **pre-registered** operational threshold.
- [ ] Human review volume is sustainable (review-burden metrics acceptable).
- [ ] Entity linkage is sufficiently reliable (labeled linkage error rate within
      threshold).
- [ ] Ordering ambiguity is handled safely (ambiguous/conflicting order does not
      silently satisfy strict-ordering recipes).
- [ ] State exhaustion is fail-visible (`UNAVAILABLE`/eviction audited, never
      silent loss).
- [ ] Deterministic replay matches live findings (replay determinism confirmed).
- [ ] At least one shadow pilot has completed with a recorded verdict.
- [ ] The policy owner approves a **specific** recipe and workflow.
- [ ] Rollback behavior is tested (enforcement can be withdrawn cleanly).

## Scope of any promotion (all dimensions must be pinned)

A promotion authorizes enforcement for a specific tuple only:

| Dimension | Value |
|-----------|-------|
| Tenant | _…_ |
| Workflow | _…_ |
| Environment | _…_ |
| Action type | _…_ |
| Recipe (`recipe_id@version`) | _…_ |
| Severity | _…_ |
| Policy version | _…_ |

## Consequence mapping under promotion

Even when promoted, the analyzer remains advisory (`OBSERVE`/`ESCALATE`/
`UNAVAILABLE`). Only the **authoritative policy** binds a consequence:

- `ESCALATE` → `HOLD_FOR_REVIEW` (default) or, for a pre-approved high-consequence
  tuple, `BLOCK`.
- `UNAVAILABLE` → `HOLD_FOR_REVIEW` for high-consequence workflows.

`BLOCK` requires an explicit, separately-approved high-confidence condition for
the pinned tuple. Nothing here enables enforcement outside the pinned scope.

## Prohibited in this phase

- Any global or default-on enforcement.
- `BLOCK` on any workflow without a pinned, policy-owner-approved promotion.
- Treating synthetic-corpus or historical-replay results as live-enforcement
  evidence.
- Any "production ready" claim.
