# Authority Review — JEPA / Domain Policy / Shadow AI (pre-flip)

**Status:** audit + policy decision. **No behavior change in this document.**
**Purpose:** classify the three governance authorities and decide whether each should
remain *blocking*, become *confirm-only*, become *advisory/log-only*, or stay
*research/provisional* — **before** any `trust_core` flip.

Scope guardrails honored: no new observables, no ML, no D1, no CG wrapper, no VC brief,
**no flip**, no behavior change. All findings below are from reading the current code on
this branch.

> **Update — reporting-only patch implemented.** The §6 patch is now in `parity.py`:
> a shadow CONFIRM/BLOCK caused *solely* by the JEPA-regime (Step 6) or semantic-mismatch
> (Step 5) escalation is attributed to a distinct driver — `shadow_jepa_derived` /
> `shadow_semantic_derived` — instead of the generic `shadow`. When any deterministic /
> policy-backed rule co-fires (`RULE:` / `FAIL_CLOSED:` / `EXCEEDS_MAX_RISK:` /
> `BLOCKED_CAPABILITY:`), it stays `shadow` (conservative). This is **driver-name only**:
> verdict, evidence/authority, and the ALLOW/CONFIRM/BLOCK decision are unchanged — proven
> by `test_trust_parity.py` (decision + mismatch-class invariant) and an identical parity
> harness (PARITY 15/15; REVIEWED 14 match / 1 intended / 0 unintended / 0 unsafe_relaxation).
> The persisted `trust_shadow.drivers` now make a future shadow demotion measurable. The
> `unresolved → unsafe_relaxation` comment drift is also fixed. **No demotion / flip done.**

---

## 1. Inspection findings

### 1.1 JEPA heuristic (residual governor)

| Aspect | Finding |
|---|---|
| Computed in | `jepa_governance.py` — `assess_governance()` (`:940`) → `_classify_regime()` (`:866`). A composite latent state (ontology × vritti via the R[v,a] coupling matrix) vs runtime process → a **residual**, classified into a regime by **hand-tuned thresholds**. |
| Affects decision in | `mcp_gateway.py` `if regime != NORMAL` block (`:1346–1461`): `DUAL_ANOMALY/UNKNOWN/HALT → DENY` (BLOCK); `PROCESS_DRIFT/SEMANTIC_SHIFT → DEFER` (BLOCK if not read-only, ESCALATE if read-only). Also feeds a confidence penalty and shadow's `semantic_mismatch`. |
| Current legacy authority | **Blocking.** A non-NORMAL regime can hard-block before any other layer runs. |
| Trust parity mapping | `parity.py` `_jepa_verdict()` (`:99`): dual_anomaly/unknown → UNSAFE; drift/shift → UNSAFE (non-RO) / UNSURE (RO). Authority = `policy.jepa` — **PROVEN** under `PARITY_POLICY`, **PROVISIONAL** under `REVIEWED_POLICY`. |
| Audit fields | `jepa_regime`, `jepa_recommended_action`, `jepa_reason_codes`, `jepa_confidence_adjustment`, `jepa_execution_mode_override`, `jepa_escalation_override`, `jepa_overrode`. |
| Nature | **Heuristic.** Deterministic *function* of its inputs, but the cut points (`integrated_confidence < 0.05`, `alignment < critical`, `coherence/semantic < 0.4–0.5`, `residual > 0.4`) are **unvalidated, hand-tuned thresholds** — no training, no calibration, no labeled ground truth. Reproducible ≠ proven. |

### 1.2 Domain Policy (semantic policy layer)

| Aspect | Finding |
|---|---|
| Computed in | `domain_policy.py` — `resolve_domain_policy()` evaluates an **ordered list of named `DomainCoherenceRule`s** against a configured `DomainProfile`; **fail-closed** `default_mode = BLOCKED` (`:223`); `DomainActionMode` carries an explicit integer **severity** for stricter-only merges (`:49–102`). |
| Affects decision in | `mcp_gateway.py` two enforcement sites: merged with JEPA when `regime != NORMAL` (`:1365–1373`), and a dedicated **NORMAL-regime enforcement** block (`:1468–1553`). `BLOCKED → block`; `CONFIRM_REQUIRED/SANDBOX_ONLY/MEMORY_WRITE_DENIED → confirm`; `READ_ONLY/DRAFT_ONLY → block non-read-only`. |
| Current legacy authority | **Blocking** (always evaluated, in both NORMAL and non-NORMAL paths). |
| Trust parity mapping | `parity.py` `_domain_verdict()` (`:109`): `BLOCKED → UNSAFE`; `severity ≥ CONFIRM_REQUIRED → UNSURE`. Authority = `policy.domain` — **PROVEN** in both PARITY and REVIEWED. |
| Audit fields | `domain_policy` (full `to_audit_dict`: fired rules, rule modes, reason codes, effective mode), `domain_overrode`. |
| Nature | **Policy-configured + deterministic.** Explicit rules with named provenance (`fired_rules`), severity-ordered modes, fail-closed default. This is exactly the "explicit configured domain rules" category. |

### 1.3 Shadow AI control layer

| Aspect | Finding |
|---|---|
| Computed in | `shadow_ai.py` — `resolve_shadow_policy()` (`:603`) via `safe_resolve_shadow_policy()` (fail-closed wrapper). Steps: registry lookup → provenance/trust classification (fail-closed `SHADOW/UNTRUSTED` for unknown) → **named declarative rules** (Rules 1–10, `:402–492`) merged stricter-only → registry `max_risk`/`blocked_capabilities` escalations → **Step 5 semantic-mismatch escalation** (score `≥0.4 → REQUIRE_CONFIRMATION`, `:775`) → **Step 6 JEPA-regime escalation** (`dual_anomaly/unknown → QUARANTINED`, `:786`) → fail-closed provenance defaults. |
| Affects decision in | `mcp_gateway.py` (`:1602–1652`): `shadow_containment_to_governance()` maps `BLOCKED/QUARANTINED → DENY` (block), all intermediate modes → `DEFER` (confirm). Evaluated **after** JEPA and domain. |
| Current legacy authority | **Blocking.** |
| Trust parity mapping | `parity.py` `_shadow_verdict()` (`:121`): `blocked/quarantined → UNSAFE`; `require_confirmation → UNSURE`. Authority = `policy.shadow` — **PROVEN** in both PARITY and REVIEWED. **Treated as one opaque authority** — the parity mapping does not distinguish *why* shadow escalated. |
| Audit fields | `shadow_assessment` (full `to_audit_dict`: provenance, trust, containment_mode, `fired_rules`, reason codes, composite risk), `shadow_overrode`. |
| Nature | **Hybrid.** Mostly **deterministic + policy-backed** (registry provenance, named rules, fail-closed defaults). But two escalation paths are **derived/heuristic**: Step 5 (a raw score threshold) and Step 6 (**re-applies JEPA's heuristic regime** as a shadow block). `composite_score` is computed but used **only for rationale text**, not the decision. |

---

## 2. Authority classification

| Authority | Classification | Why |
|---|---|---|
| **JEPA** | **PROVISIONAL confirm-only validator** | Unvalidated hand-tuned thresholds; no learning/calibration/ground truth. It carries real signal (worth a human check) but has not earned veto authority. Matches `EvidenceStatus.PROVISIONAL` = "advise/log, never block." |
| **Domain Policy** | **PROVEN blocking validator** | Explicit configured rules, named provenance, severity-ordered, fail-closed. Deterministic and policy-backed — the textbook case for a retained veto. |
| **Shadow AI** | **Split:** **PROVEN blocking validator** for its registry/provenance/named-rule containment; **PROVISIONAL confirm-only** for its JEPA-derived (Step 6) and pure-score (Step 5) escalations | The deterministic, policy-backed core deserves blocking authority. The two derived escalations inherit JEPA's heuristic status (or a bare threshold) and should not independently produce a *hard* block. |

`composite_score`, CG-derived signals: **RESEARCH** (recorded, never authoritative) — already gated; unchanged here.

---

## 3. Recommended future authority

| Authority | Recommendation | Notes |
|---|---|---|
| **JEPA** | **Demote to confirm-only** (already the `REVIEWED_POLICY` direction) | Do **not** go full advisory/log-only yet — **needs more data**. Keep it escalating to a human; revisit advisory once shadow-volume data shows JEPA-only blocks are reliably noise. |
| **Domain Policy** | **Keep blocking** | Hard rules (`result_mode = BLOCKED`) remain vetoes. No change. |
| **Shadow AI** | **Keep blocking for the deterministic/policy-backed paths; the JEPA-derived (Step 6) and semantic-mismatch (Step 5) escalations should not independently hard-block** — at most confirm | This is consistent with the JEPA demotion: a heuristic signal should have the same authority no matter which layer surfaces it. **Reporting/attribution fix first** (§6), behavior change only after shadow-volume evidence. |

This aligns with the stated default policy: JEPA → provisional/confirm; Domain → keep blocking (configured rules); Shadow → don't silently block unless deterministic/policy-backed, else confirm/advisory.

---

## 4. Differential impact plan (using persisted `trust_shadow`)

The durable store now persists `request_snapshot["trust_shadow"]` =
`{decision, legacy_decision, mismatch, mismatch_class, drivers, reason}` for every
shadow/trust_core call. Measure each proposed change by running it as an
**authority-policy variant in SHADOW** (legacy still acts) and aggregating:

| Metric | Source | Target |
|---|---|---|
| mismatch count | count where `mismatch == true` | tracked, not gated |
| intended mismatch | `mismatch_class == "intended"` (reviewed demotion explains it; PARITY would match legacy) | all demotion-driven mismatches must land here |
| unintended mismatch | `mismatch_class == "unintended"` (mapping gap, PARITY also mismatches) | **must be 0** |
| unsafe relaxation | `mismatch_class == "unsafe_relaxation"` (BLOCK/CONFIRM → ALLOW) | **must be 0 — hard gate** |
| over-block reduction | legacy `BLOCK` count − trust `BLOCK` count among `intended` | the intended benefit; quantify |
| affected scenario type | group `intended`/`unintended` by `drivers` (e.g. `jepa`, `domain`, `shadow`) | locate which authority drives each change |
| audit driver comparison | diff `drivers` legacy-vs-trust per request | confirm relaxed blocks become **confirm**, never **allow** |

Per proposed change:

- **JEPA → confirm-only:** expect `intended` mismatches keyed on `drivers ⊇ {jepa}` where legacy was BLOCK and trust is CONFIRM; expect **0** `unsafe_relaxation`. Over-block reduction = JEPA-sole legacy blocks now confirm. (Today the harness shows exactly one: `jepa_sole_block`, `intended`.)
- **Shadow JEPA-derived escalation → confirm-only:** **cannot be measured today** — the parity mapping collapses shadow into one driver, so a JEPA-laundered shadow block is attributed to `shadow`, not `jepa`. The §6 reporting patch is the prerequisite to measure it.

---

## 5. Safety rules (hard)

1. **No change may turn a legacy BLOCK into ALLOW without explicit review.** A demotion may only relax BLOCK → **CONFIRM** (human in the loop), never BLOCK → ALLOW.
2. **No provisional/research authority may veto.** JEPA (provisional) and any score/CG-derived signal can escalate to CONFIRM at most.
3. **Any demotion runs in SHADOW first** and must show **`unsafe_relaxation == 0`** and **`unintended == 0`** over the corpus before it may become authoritative.
4. **Domain policy hard rules remain vetoes** (`result_mode = BLOCKED` and `default_mode = BLOCKED` fail-closed).
5. **The flip gate is unchanged:** `trust_core` may flip only when `unintended == 0` **and** `unsafe_relaxation == 0`; intended demotions must be individually reviewed and recorded.
6. Relaxed blocks route through the **existing** confirmation flow (`force_confirm`), never a silent allow — and the gateway still lets **domain / shadow / confidence-floor** block independently afterward (defense in depth).

---

## 6. Output: decision + smallest safe patch plan

### Authority table

| Authority | Nature | Earned authority |
|---|---|---|
| JEPA | heuristic (unvalidated thresholds) | PROVISIONAL |
| Domain Policy | policy-configured + deterministic | PROVEN |
| Shadow AI (registry/provenance/named rules) | policy-configured + deterministic | PROVEN |
| Shadow AI (Step 5 score / Step 6 JEPA-derived) | heuristic / derived | PROVISIONAL |

### Current behavior table (legacy = today)

| Authority | ALLOW | CONFIRM | BLOCK |
|---|---|---|---|
| JEPA | NORMAL | drift/shift on read-only | dual_anomaly/unknown/halt; drift/shift on non-read-only |
| Domain | mode ALLOW | CONFIRM_REQUIRED / SANDBOX / MEMORY_WRITE_DENIED | BLOCKED; READ_ONLY/DRAFT_ONLY on non-read-only |
| Shadow | containment ALLOW | intermediate modes (→ DEFER) | BLOCKED / QUARANTINED |

### Recommended behavior table (post-review target, **not yet applied**)

| Authority | ALLOW | CONFIRM | BLOCK |
|---|---|---|---|
| JEPA | NORMAL | **all non-NORMAL regimes** | **(none — demoted)** |
| Domain | mode ALLOW | confirm modes | **BLOCKED / read-only-violation (unchanged)** |
| Shadow (deterministic) | containment ALLOW | intermediate modes | **BLOCKED / QUARANTINED (unchanged)** |
| Shadow (JEPA-derived / score) | — | **escalation (≤ confirm)** | **(none — demoted, consistent with JEPA)** |

### Risk analysis

- **Primary risk — JEPA laundering through Shadow (Step 6).** When JEPA is demoted but shadow still escalates `dual_anomaly/unknown → QUARANTINED → BLOCK`, the same heuristic re-blocks under a different name. *Currently this is defense-in-depth (safe direction)* and only reachable on the `trust_core` relax path, since legacy JEPA blocks before shadow runs. But it makes the demotion **non-transparent**: the persisted `drivers` attribute the block to `shadow`, hiding that JEPA's heuristic caused it. **This blocks honest measurement of the shadow demotion and must be made visible before that demotion is considered.**
- **Over-block vs under-block.** Demoting JEPA trades fewer hard blocks for more human confirmations. Acceptable per safety rule #1 (BLOCK→CONFIRM only). Quantify over-block reduction from `trust_shadow` before/after.
- **Mapping completeness.** `unintended` must stay 0; today it is 0 on the focused corpus but the corpus is small (15 scenarios) — see §4 / the broader-corpus follow-up.
- **Doc drift (cosmetic).** `mcp_gateway.py:343` comment lists `…|unresolved`; the live classification is `…|unsafe_relaxation` (`parity.py:256`). Harmless, worth a one-line comment fix.

### Exact tests / harness commands

```bash
# Parity differential (BEFORE/AFTER, prints match/intended/unintended/unsafe_relaxation)
PYTHONPATH="$(pwd)" python3 experiments/trust_signal/parity_harness.py

# Focused suites — run standalone (combined runs hit the known cross-file asyncio pollution)
python3 -m pytest tests/unit/agentic_framework/test_trust_shadow.py -q
python3 -m pytest tests/unit/agentic_framework/test_trust_observables.py -q
python3 -m pytest tests/unit/agentic_framework/test_trust_parity.py -q
python3 -m pytest agentic/ledger/tests/test_governance_audit_store.py -q
python3 -m pytest agentic/agentic_framework/tests/test_mcp_gateway.py -q
python3 -m pytest agentic/agentic_framework/tests/test_jepa_governance.py -q

# Shadow-volume mismatch aggregation (read the persisted trust_shadow):
#   store.export_jsonl(path)  →  group request_snapshot.trust_shadow.mismatch_class
#   and .drivers; assert unintended==0 and unsafe_relaxation==0 before any flip.
```

### Is a code change recommended now?

**No behavior change now.** The review confirms the existing `REVIEWED_POLICY`
(JEPA → confirm-only) is the right direction and is already safely gated behind
`trust_core`. Domain stays blocking; shadow's deterministic core stays blocking.

**One no-behavior-change reporting improvement was recommended and is now IMPLEMENTED**
(see the update note at the top) because it is the **prerequisite to measure the shadow
demotion** and to keep the flip decision honest. The plan that was carried out:

**Smallest safe patch plan (reporting only, zero decision change):**
1. In `parity.py`, when building the `shadow` observation, inspect the already-present
   `shadow_assessment.reason_codes` (the durable audit field; `ShadowAssessment` exposes
   `reason_codes`, not a `fired_rules` attribute). If containment came (only) from
   `JEPA_REGIME_ESCALATION` / `SEMANTIC_MISMATCH_ESCALATION` — with no deterministic
   `RULE:` / `FAIL_CLOSED:` / `EXCEEDS_MAX_RISK:` / `BLOCKED_CAPABILITY:` code present —
   name the observation `shadow_jepa_derived` / `shadow_semantic_derived`
   **without changing its verdict or evidence** — so the persisted `drivers` distinguish
   deterministic shadow blocks from JEPA-laundered ones.
2. Add a parity unit test asserting the attribution split on a crafted
   `dual_anomaly` + unknown-asset case, and asserting the **decision is byte-identical**
   to today (pure reporting).
3. Optional one-liner: fix the `mcp_gateway.py:343` `unresolved` → `unsafe_relaxation`
   comment drift.

Everything beyond step 1–3 (actually demoting shadow's derived escalation to confirm-only)
is a **behavior change** and stays gated behind a future `REVIEWED`-policy extension +
shadow-volume evidence + differential check — **not in scope now.**
