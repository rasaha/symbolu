# Trust Observable Architecture — Closeout Summary

Branch `claude/trust-observables-phase2-swbwe2`. Everything below is shipped, tested, and
pushed. The throughline: **a typed trust kernel that runs in shadow, is proven at parity, and
is opt-in authoritative for one narrow safe path — with zero production behaviour change by
default.**

---

## 1. Phase 1 — completed (trust kernel)

- `trust/observables.py` — the taxonomy: `ObservableType` (HARD_VETO / VALIDATOR / TRUST_SIGNAL
  / ADVISORY) × `EvidenceStatus` (PROVEN / PROVISIONAL / RESEARCH), `Verdict` (SAFE/UNSURE/
  UNSAFE), `TrustDecision` (ALLOW/CONFIRM/BLOCK), `Observation`.
- `trust/decision.py` — `decide()`: weakest-link combiner; PROVISIONAL caps at CONFIRM;
  RESEARCH never affects the decision; every outcome carries an ordered driver trace (ALLOW
  lists cleared gates too).
- `trust/registry.py` — maps the already-proven gateway signals onto observations (no new ML,
  no CG research).
- Asymmetry rule (claims can't raise trust) and CG signals decision-gated/off by default.

## 2. Phase 1.5 / 1.5A / 1.5B — completed (shadow → parity → opt-in authoritative)

- **Shadow core** (`trust/parity.py`): `trust_mode` LEGACY/SHADOW/TRUST_CORE (default LEGACY);
  `AuthorityPolicy` PARITY vs REVIEWED (JEPA→confirm-only; default PARITY).
- **Durable persistence**: `trust_shadow` (decision/legacy/mismatch/class/drivers/reason)
  embedded in the tamper-evident `GovernanceAuditStore` canonical event; entropy/gap provenance
  persisted; driver attribution (`shadow_jepa_derived` / `shadow_semantic_derived`).
- **Reporting**: `shadow_report.py` (match rate, mismatch class, by driver/risk/tool,
  entropy/gap slices, READY/NOT-READY verdict).
- **Parity completion**: forbidden-capability mapped as PROVEN HARD_VETO; shadow
  intermediate-containment parity bug fixed; AgentDojo/InjecAgent external coverage;
  105-scenario `shadow_volume_validation` (READY FOR REVIEW).
- **Docs**: authority review, flip-readiness package, canary runbook, migration plan.
- **1.5B**: trust_core authoritative JEPA-relax path made a supported control + a correctness
  fix (`human_confirmed` propagation on an approved relax).

**Standing parity evidence (offline):** 0 unintended, 0 unsafe_relaxation, 3 intended JEPA
demotions, hash chain valid.

## 3. Trust-core flip status

**Implemented and validated; NOT flipped in production.** It is a supported opt-in
(`trust_mode="trust_core"`, `trust_authority_policy="reviewed"`), default LEGACY/PARITY. Scope
is narrow: a **JEPA-sole BLOCK → human CONFIRM** (deny→ESCALATE, approve→ALLOWED +
`human_confirmed`); domain/shadow/forbidden/floor blocks remain blocks; **no silent ALLOW
exists**. Two independent rollbacks (mode→shadow/legacy, policy→parity), instant, no migration.

## 4. Operational SHADOW / canary commands

```python
from agentic.agentic_framework.trust.runtime_config import build_shadow_gateway, build_canary_gateway
shadow = build_shadow_gateway(mcp_client=c, audit_db_path="/var/data/governance_audit.db")          # prod SHADOW/REVIEWED
canary = build_canary_gateway(mcp_client=c, audit_db_path="/var/data/governance_audit_canary.db")    # opt-in, NOT default
# env: TRUST_MODE / TRUST_AUTHORITY_POLICY / GOVERNANCE_AUDIT_DB → gateway_from_env(mcp_client=c)
```
```bash
make trust-shadow-report DB=/var/data/governance_audit.db        # flip-gate: exit != 0 on unsafe/unintended
make trust-canary-report DB=/var/data/governance_audit_canary.db # approve/deny + safety
```

## 5. Phase 2 observables completed (4)

Permission Overclaim · Outcome Reputation · Hallucinated Capability · Plan-Action Consistency —
all VALIDATOR/PROVISIONAL, advisory/confirm-only, shadow-recorded, **inert by default**.

## 6. Per-observable detail

| Observable | Authority (now → on promotion) | Production impact | Validation corpus result | Promotion criteria |
|---|---|---|---|---|
| **Permission Overclaim** | VALIDATOR/PROVISIONAL (confirm-only) → PROVEN can BLOCK severe | None (inert without `permission_context`) | 6 kinds → intended; 2 controls → match; **0 unintended / 0 unsafe** | 0 unsafe/unintended on real traffic; trusted grant provenance; per-kind audit; sign-offs |
| **Outcome Reputation** | VALIDATOR/PROVISIONAL (confirm-only) → PROVEN can BLOCK egregious | None (gateway flag off by default) | 4 scenarios → 2 intended (denied/violations), 2 match (good/new); **0/0** | min per-action volume; threshold calibration on real traffic (still fixed constants); shadow review + feedback-loop guard; sign-offs |
| **Hallucinated Capability** | VALIDATOR/PROVISIONAL (confirm-only) → PROVEN can BLOCK impossible | None (inert without `capability_context`) | 5 scenarios → 3 intended, 2 match (valid + alias); **0/0** | **registry provenance** is the central gate; false-positive review; min shadow volume; sign-offs |
| **Plan-Action Consistency** | VALIDATOR/PROVISIONAL (confirm-only) → **PROVEN stays confirm-only** (heuristic) | None (inert without `plan_action_context`) | 5 scenarios → 4 intended (each mismatch kind), 1 control match; **0/0** | precision review (FP ceiling); coverage per kind; trusted plan provenance; sign-offs. Promotion does **not** unlock blocking |

Common: stricter-only escalations classified `intended` (never `unsafe_relaxation`); each
persists its driver into `trust_shadow` and aggregates in `shadow_report`. Forbidden-capability
remains the only PROVEN HARD_VETO; domain/shadow remain PROVEN blocking; JEPA under REVIEWED is
PROVISIONAL.

## 7. Remaining risks

- **Offline ≠ production:** all "0/0" evidence is on synthetic/benchmark corpora; the
  real-traffic distribution is unproven.
- **Dormant context producers:** permission/capability/plan-action contexts are wired but have
  **no upstream producer yet** — they only fire when a caller populates them. Real value needs
  those producers.
- **Reputation needs volume + calibration:** thresholds are placeholders; thin history is inert
  by design.
- **Heuristic false positives:** plan-action keyword matching will over/under-fire until
  calibrated.
- **Confirm-flow load:** the canary adds human confirmations on JEPA-flagged traffic; capacity
  must hold.
- **Schema gap:** `canary_report` can't separate denied vs timeout (both counted as denied)
  without a small persistence enrichment.
- **Pre-existing repo noise:** the broad agentic sweep has ~20 pre-existing cross-file-pollution
  failures unrelated to this work (focused suites are green).

## 8. What requires real production traffic

The **decisions**, not the code: (1) the flip — a representative SHADOW/REVIEWED window with
`unsafe_relaxation==0 / unintended==0`; (2) the JEPA authority call — canary approve/deny rate
(keep confirm-only / demote further / re-promote); (3) every observable promotion — volume,
calibration, false-positive review; (4) wiring the observable contexts from real
plan/grant/registry sources.

## 9. What should NOT be built next

- Widening trust_core authority beyond the JEPA-sole relax (wait for canary data).
- ML / injection classifier / groundedness models; hidden-state uncertainty head; **D1**.
- CG-as-governance-signal (keep research-only/off).
- Platform abstraction (no second consumer — YAGNI).
- VC brief. Promoting any observable PROVISIONAL→PROVEN before calibration.

## 10. Recommended next 30 days

1. **Wire one real context producer** (start with capability/permission from the live registry
   — deterministic, highest precision) so shadow data is meaningful.
2. **Run production SHADOW under REVIEWED** with the durable store; read `make
   trust-shadow-report` on a schedule; confirm 0 unsafe/0 unintended on real traffic.
3. **If clean + sign-offs:** enable the **canary** on a small cohort; watch `make
   trust-canary-report` approve/deny + latency.
4. **Accumulate per-observable shadow volume**; begin threshold calibration for reputation.
   **Promote nothing yet.**
5. Optional small enrichment: persist the escalation reason so `canary_report` can split denied
   vs timeout.

## 11. PR readiness

This is a coherent, self-contained increment: shadow-only/opt-in, **no production behaviour
change by default**, focused suites green (latest combined sweep 335 passed), parity harness and
105-scenario validation clean, every change documented (architecture notes + runbooks + ops).
The production flip and all observable promotions are **not** included and remain
evidence-gated.
