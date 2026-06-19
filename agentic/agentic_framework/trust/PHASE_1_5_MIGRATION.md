# Phase 1.5 — Migration: from parallel formalization to canonical trust core

**Status:** Planning doc (no code). Precondition for Phase 2 (supervised observables).
Scope is **migration + hardening only** — no new observables, no ML, no CG research.

## 1. Current state (after Phase 1)

- The trust module (`agentic/agentic_framework/trust/`) exists: a typed taxonomy
  (`observables.py`), a pure decision model (`decision.py`), and a registry that maps
  the **proven** signals onto observations (`registry.py`). It is unit-tested
  (`tests/unit/agentic_framework/test_trust_observables.py`).
- **`SafeMCPGateway` does NOT call it.** Verified: `mcp_gateway.py` has zero imports of
  `agentic_framework.trust`. The gateway still runs its **legacy decision pipeline**.
- Therefore the trust module is **not yet production-authoritative** — it is a parallel,
  tested formalization and an integration seam, not the live decision core. Today it
  governs nothing in production.

## 2. What remains OUTSIDE `trust/decision.py`

The trust module currently represents only the *uncertainty/validator* slice (raw
entropy, confidence-risk gap, approval, action-risk, tool validity). The gateway's
decision authority that is **not** yet represented:

- **Base ConfidenceGate** — `gate_decision.confidence.overall`, `execution.can_execute`,
  `escalation` (the primary gate, from quality/coherence/risk). Not represented at all.
- **`min_confidence` threshold** — `effective_confidence < tool_def.min_confidence → BLOCK`.
- **`effective_confidence` math** — `gate.overall + jepa.conf_adj − raw_entropy_penalty −
  cg_entropy_penalty`.
- **JEPA heuristic** — regime → `apply_jepa_override` → DENY/DEFER (block/escalate). Only
  its CG-input gating exists today; the heuristic itself is not modeled or demoted.
- **Domain Semantic Policy** — `resolve_domain_policy`, `DomainActionMode` BLOCKED/CONFIRM.
- **Shadow AI** — `shadow_assessment` and its override.
- **Escalation / human confirmation** — the async confirmation request and denied/timeout
  handling (the pure `decide()` deliberately excludes I/O).
- **Execution outcome states** — TIMEOUT / ERROR.
- **Audit schema** — `AuditEntry` records components but has no single authoritative
  "what drove THIS decision" trace; ALLOW is under-explained.
- **Note:** `budget_gate` exists in the trust registry as a forward-looking slot; the
  gateway has **no budget controller** today (only `min_confidence`).

## 3. Phase 1.5 goal

Migrate from the parallel formalization to **`trust/decision.py` as the canonical
decision core** of `SafeMCPGateway`, **at behavior parity first**:

- **No new observables.**
- **No ML.**
- **No CG research features.**

Policy changes (e.g. demoting the JEPA/domain/shadow heuristics to advisory per the
architecture doc) are made **only after parity is achieved**, each as an explicit,
differential-checked change — not as a side effect of the migration.

## 4. Required steps

1. **Fix test isolation first.** The broad agentic sweep shows 69 pre-existing failures
   from cross-file async pollution (+ missing optional deps `fastapi`/`pydantic`).
   Quarantine/repair these (async teardown, shared state; register the `asyncio`
   marker) so a real regression is distinguishable from noise. *Gates everything else.*
2. **Build a differential/parity harness.** Run **both** decision cores (legacy gateway
   vs `trust/decision.py`) on a shared corpus — the gateway scenarios + the signal_gov
   benchmarks + the confident-unsafe twins — and assert **identical ALLOW/CONFIRM/BLOCK**,
   logging every mismatch with both rationales.
3. **Map remaining gateway authorities into observables** (base ConfidenceGate,
   `min_confidence`, JEPA, domain policy, shadow AI, approval/escalation), each tagged
   `{HARD_VETO | VALIDATOR | ADVISORY} × {PROVEN | PROVISIONAL | RESEARCH}`, reaching
   **parity with current behavior** (no policy change yet).
4. **Shadow-run legacy vs trust core behind a flag.** Compute both, **act on legacy**,
   log mismatches. The parallel decision + legacy mismatch are now persisted **durably**
   into the tamper-evident audit store (`request_snapshot["trust_shadow"]`), not just the
   in-memory `AuditEntry` — so mismatch data survives for at-volume analysis. Flip the
   gateway to the trust core only when mismatches are zero/reviewed.
5. **Unify audit on the trust driver trace.** Make `TrustOutcome.to_audit()` (decision +
   ordered drivers + all observations) the canonical decision section of `AuditEntry`,
   so **ALLOW, CONFIRM, and BLOCK are all explained** by the same structure.
6. **Add a CG decision-gate regression test.** Craft a CG state that *would* trip JEPA
   into a non-NORMAL regime; assert it flips the decision **only** when
   `enable_cg_state_signals=True`, and is inert-but-recorded when `False`.
7. **Flip only after zero unreviewed mismatches** (and the suite is isolation-clean).

## 5. Exit criteria (Phase 1.5 → Phase 2)

- Gateway decisions route through `trust/decision.py` **behind a flag**.
- **Zero unreviewed differential mismatches** between legacy and trust core (each
  intended difference reviewed and recorded).
- Audit **explains every outcome** — ALLOW / CONFIRM / BLOCK — via the trust driver trace.
- **CG-derived signals remain decision-gated** when `enable_cg_state_signals=False`
  (resolved + recorded for audit, but not driving the decision), proven by the
  regression test in step 6.
- The **full focused gateway suite is clean** (test isolation fixed; no new failures
  attributable to the migration).

## 6. Explicitly deferred (NOT in Phase 1.5)

- Input-risk / injection / manipulation classifier.
- Hidden-state uncertainty / trust-mismatch head.
- D1 (the hidden_probe-vs-raw_entropy gate stays parked until a hidden head is on the
  roadmap).
- CG wrapper (Bhava→phase / CSR) changes.
- VC brief update.
- Phase 2 supervised observables of any kind.

Phase 1.5 is purely about making the *already-proven* decision logic canonical,
auditable, and safe to extend — before any new signal is added.
