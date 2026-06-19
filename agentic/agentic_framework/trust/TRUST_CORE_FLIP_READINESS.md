# trust_core Flip-Readiness Package

**Status:** evidence assembled; **flip NOT taken.** This document states whether `trust_core`
can become authoritative, the exact conditions to meet first, the precise code path that
changes, how to roll back, and what stays in Phase 2.

**Scope of "the flip" (be precise).** Today the only authoritative behaviour the flip enables
is **narrow and safe**: with `trust_mode=TRUST_CORE` **and** the `REVIEWED` authority policy,
a **JEPA-sole** block (a block driven *only* by the JEPA heuristic, not by domain / shadow /
forbidden-capability / confidence-floor) is **relaxed from BLOCK to a human CONFIRM** routed
through the existing async confirmation flow. It is **never** a silent allow. Every other
authority — domain policy, shadow AI, the forbidden-capability HARD_VETO, the confidence
floor, approval/gap — is **unchanged**. This is the Phase 1.5B mechanism; it is not a
wholesale handover of the decision to the trust core.

---

## 1. Flip-readiness summary

The trust core reproduces the legacy gateway decision across every mapped authority and the
forbidden-capability hard pre-gate, with the only divergences being **reviewed, intended**
JEPA demotions. Current evidence (this branch, all offline):

| Evidence | Result |
|---|---|
| Parity harness — in-scope (28), PARITY | 28/28 match |
| Parity harness — in-scope (28), REVIEWED | 25 match + **3 intended**, 0 unintended, 0 unsafe_relaxation |
| External fixtures (AgentDojo/InjecAgent, 12) | 12/12 clean |
| Strict pre-gate (forbidden HARD_VETO) | clean (`--strict-pregate` exit 0) |
| Real SHADOW-volume validation (105 scenarios) | 102 match + **3 intended**, 0 unintended, 0 unsafe_relaxation |
| unsafe_relaxation (all cohorts) | **0** |
| unintended (all cohorts) | **0** |
| intended | **3** — JEPA demotions: `jepa_ro`, `jepa_w`, `jepa_write` |
| Audit hash chain | **verified** |

**Verdict: READY FOR REVIEW on the offline corpus.** The remaining gate is the *same property
holding over real production SHADOW traffic*, plus operator sign-off on the one reviewed
behaviour change. **No flip is performed by this document.**

---

## 2. Risk checklist

- [ ] **No silent allow.** Confirmed by construction: the relax sets `force_confirm=True` and
      routes to the human-confirmation gate; a denied/timed-out confirmation returns ESCALATE,
      never ALLOW (`mcp_gateway.py` JEPA-relax path + the `force_confirm` execution gate).
- [ ] **Hard authorities preserved.** Domain BLOCK, shadow BLOCK/QUARANTINE, the
      forbidden-capability HARD_VETO, and the confidence floor still block under TRUST_CORE.
      Only `not domain_overrode` JEPA-sole blocks relax.
- [ ] **Forbidden veto unoverridable.** PROVEN HARD_VETO → BLOCK terminal; high confidence /
      raw entropy / gap cannot lower it (regression-tested).
- [ ] **Policy is explicit.** Flip requires *both* `TRUST_CORE` and `REVIEWED`; either alone is
      inert (TRUST_CORE under PARITY behaves as SHADOW; REVIEWED under SHADOW only records).
- [ ] **Intended set is exactly the JEPA demotions** — reviewed in `AUTHORITY_REVIEW.md`
      (JEPA = heuristic, unproven thresholds → confirm-only, never advisory yet).
- [ ] **Zero unintended / zero unsafe_relaxation** over the offline corpus **and** over the
      production window (to be confirmed — §5).
- [ ] **Auditability intact.** Every decision persists `trust_shadow` (decision, drivers,
      mismatch class) into the tamper-evident store; chain verifies.
- [ ] **Rollback rehearsed.** Flipping the flag back to SHADOW/LEGACY restores legacy with no
      data migration (§6).
- [ ] **Blast radius bounded.** Flip is per-`SafeMCPGateway` instance via constructor/flag;
      can be enabled for a canary cohort first.

---

## 3. Required operator sign-offs

| Owner | Sign-off |
|---|---|
| Governance / safety owner | Accepts JEPA-sole BLOCK → human-CONFIRM as the only behaviour change; confirms `AUTHORITY_REVIEW.md` JEPA demotion rationale. |
| Audit / compliance owner | Confirms production hash chain verifies and `trust_shadow` is persisted over the evaluation window. |
| Service / on-call owner | Confirms the rollback flag path and that the human-confirmation flow has capacity for the added CONFIRMs. |
| Product owner | Accepts the (small) increase in human confirmations on JEPA-flagged traffic. |

A flip proceeds only with **all four** sign-offs recorded against a specific production
evaluation window that meets §5.

---

## 4. Exact command — run on the production / live SHADOW audit store

**Pre-req:** production must run `trust_mode=SHADOW` with the **REVIEWED** authority policy so
the recorded `trust_shadow` reflects the *flip candidate* (default production policy is PARITY,
which would record legacy-identical decisions and is not the candidate). Then read the live
store read-only:

```bash
# Flip-gate report over the LIVE production audit store (read-only; no flip):
PYTHONPATH="$(pwd)" python3 -m experiments.trust_signal.shadow_report \
    --store /var/data/governance_audit.db --entropy --fail-on-unintended

# Or against an exported JSONL snapshot:
PYTHONPATH="$(pwd)" python3 -m experiments.trust_signal.shadow_report \
    --jsonl /var/data/governance_audit_export.jsonl --entropy --fail-on-unintended
```

Exit code is the gate: **non-zero on any `unsafe_relaxation`**, and (with
`--fail-on-unintended`) **non-zero on any `unintended`**. The offline 105-scenario rehearsal is
`python3 -m experiments.trust_signal.shadow_volume_validation`.

---

## 5. Required thresholds (all must hold over the production window)

| Threshold | How checked |
|---|---|
| `unsafe_relaxation == 0` | `shadow_report` count == 0 (hard gate; non-zero exit otherwise) |
| `unintended == 0` | `shadow_report` count == 0 (`--fail-on-unintended`) |
| intended mismatches **reviewed** | every `intended` row's drivers are JEPA-only and accepted per `AUTHORITY_REVIEW.md` |
| hash chain **valid** | `GovernanceAuditStore.verify_chain().valid is True` |
| sufficient volume & coverage | window spans real traffic across the live risk levels / tools (not a thin slice) |

Only when **all** hold over the live window, with §3 sign-offs, may the flip be scheduled.

---

## 6. Rollback plan

The `trust_mode` flag is a 3-position switch on `SafeMCPGateway` (default **LEGACY**):

- **LEGACY** — trust core not computed; pure legacy behaviour (the original baseline).
- **SHADOW** — trust core computed + recorded; **legacy still acts**. Safe at any volume.
- **TRUST_CORE** — authoritative relax (JEPA-sole BLOCK → human-CONFIRM) under REVIEWED.

Rollback = set the flag back to **SHADOW** (keep collecting evidence) or **LEGACY** (full stop).

- **Instant & total:** a config/flag change per gateway; no data migration, no schema change.
- **No lost audit:** SHADOW keeps persisting `trust_shadow`; the chain is continuous.
- **Canary-first:** enable TRUST_CORE on a subset of gateways; widen only after the live report
  stays clean.
- **Inert combinations remain safe:** TRUST_CORE+PARITY behaves as SHADOW; REVIEWED+SHADOW only
  records — so a partial/mis-set flip cannot silently relax anything.

---

## 7. Code path changed during the flip

**Configuration only — no code edit is required to flip; it is a supported flag + policy
selection** (both now first-class constructor controls; no private-state poking):

- `SafeMCPGateway(..., trust_mode="trust_core", trust_authority_policy="reviewed")`.
- Reverting is the same control: `trust_mode="shadow"` or `"legacy"` (or
  `trust_authority_policy="parity"`) — either disables the relax instantly.

> **Enablement status:** the authoritative relax is now a **supported, validated opt-in**
> (constructor control + tests), and a correctness fix landed so a relaxed-then-**approved**
> JEPA block records `human_confirmed=True` and audits as CONFIRM (legacy=confirm/trust=confirm
> = `match`) rather than a spurious `unintended`. The **production flip is still NOT taken**:
> default remains `LEGACY`/`PARITY`, and enabling it in production still requires §5 thresholds
> over real traffic + §3 sign-offs.

**The single behavioural branch this activates** (already present, currently inert):

- `_jepa_relax = (trust_mode == TRUST_CORE and policy.jepa != PROVEN)` →
  in the `regime != NORMAL` block, when `_jepa_relax and not domain_overrode and
  merged_decision in ("DENY","DEFER")`: set `force_confirm=True`, `merged_decision="ALLOW"`
  (skip the JEPA block returns), and enforce a human confirmation at the execution-permission
  gate. (`agentic/agentic_framework/mcp_gateway.py`, JEPA-relax path.)

**Unchanged code paths:** forbidden-capability pre-gate, domain enforcement (NORMAL and
non-NORMAL), shadow enforcement, confidence-floor block, approval/gap confirmation, and all
audit/persistence. Net behavioural delta = **JEPA-sole BLOCK → human-CONFIRM** on the small
set of JEPA-flagged calls (the 3 intended classes in evidence).

---

## 8. What remains Phase 2 (after this flip)

This flip closes Phase 1.5; it does **not** start Phase 2. Still explicitly deferred:

- **Broaden trust_core authority** beyond the JEPA-sole relax (e.g. trust core authoritative
  for more decision classes) — each step parity-gated and separately reviewed.
- **Shadow derived-escalation demotion** — the `shadow_jepa_derived` / `shadow_semantic_derived`
  attributions exist for measurement; demoting them is a future, evidence-gated decision.
- **Input-risk / prompt-injection / manipulation classifier** (a real observable, not the
  structural fixture mapping used for parity stress).
- **Hidden-state uncertainty / trust-mismatch head**; **D1** (hidden_probe vs raw_entropy gate).
- **CG wrapper** (Bhava→phase / CSR) changes; **VC brief** update.
- **Phase 2 supervised observables** of any kind; **ML / calibrated scoring** on the `severity`
  seam.
- **Larger platform abstraction** (GovernedAction / ObservableSource / Enforcer / AuditSink) —
  deferred until a second real consumer exists (YAGNI).

Constraints honoured by this package: no flip, no policy demotion beyond the already-reviewed
JEPA confirm-only, no new observables, no ML, no D1, no CG wrapper, no VC brief.
