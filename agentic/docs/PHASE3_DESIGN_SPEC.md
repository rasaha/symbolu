# Phase 3 Design Spec: Governance-Controlled Energetic Promotion

> **Status:** Design spec only — NOT approved for implementation
>
> **Prerequisite:** P0 (codified), P1 (implemented + calibrated), P2 (implemented + usefulness-evaluated)
>
> **Scope:** Narrowest safe first-promotion path for the P2 audit-only Guna → CSR signal

---

## A. Executive summary

Phase 3 promotes the P2 audit-only energetic signal from pure
diagnostic to bounded live influence on **confidence scoring only**.

It does NOT rewrite CSR state, change regime classification, alter
action eligibility, or introduce free-running energetic feedback.
The promotion is off by default, opt-in via domain policy, bounded
by hardcoded caps, and fully auditable.

**What Phase 3 IS:**
- A confidence-only modulation path gated by domain policy
- Bounded to ±0.03 confidence adjustment (within the existing 0.20 sovereign penalty cap)
- Off by default — zero behavioral change unless explicitly enabled
- Fully reversible — setting the flag to false restores P2 audit-only behavior

**What Phase 3 is NOT:**
- Not a CSR rewrite
- Not a regime influence
- Not a direct action eligibility change
- Not an adaptive feedback loop
- Not Phase 4

---

## B. Promotion target comparison

Five possible promotion targets, ranked safest to riskiest:

### B1. Audit-label enrichment only (SAFEST)

**What it would do:** Add P2 dominant tendency (clarify/agitate/dampen)
and net_coherence_delta as named fields in the governance audit
snapshot. No behavioral change.

**Safety:** Zero risk. Pure observability.

**Assessment:** Already partially achieved — P2 signal exists and can
be computed at any call site. This target adds value but is not truly
a "promotion" since nothing changes in live governance. Useful as a
prerequisite step within Phase 3, not as the sole deliverable.

**In scope for Phase 3:** Yes, as a mandatory prerequisite.

### B2. Confidence adjustment only (RECOMMENDED)

**What it would do:** The P2 net_coherence_delta contributes a small,
bounded confidence penalty/bonus within the existing sovereign penalty
aggregation. Dampen-dominant states slightly reduce confidence;
clarify-dominant states slightly reduce the penalty (but never
increase confidence above baseline).

**Safety:** Low risk. The existing sovereign penalty aggregation
already caps total penalty at 0.20. Adding a bounded P2 term within
that cap cannot exceed existing bounds. The influence is small
(max ±0.03), symmetric in mechanism, and follows the established
signal-adapter penalty pattern.

**Why safe:**
- Follows the exact same pattern as guna_anomaly_resolution,
  entropy_resolution, and 6 other sovereign signal adapters
- Bounded within the existing aggregate cap (0.20)
- Cannot increase confidence above baseline (penalty floor = 0.0)
- Off by default

**In scope for Phase 3:** Yes — this is the recommended first target.

### B3. Confirmation-threshold modulation (MODERATE RISK)

**What it would do:** Agitate-dominant states lower the threshold at
which confirmation is requested; clarify-dominant states raise it.

**Safety:** Moderate risk. Threshold modulation changes the
confirmation boundary, which can affect user experience and
safety-critical decisions. Harder to reason about than additive
confidence adjustment.

**In scope for Phase 3:** No. Defer to Phase 3b or later.

### B4. Regime influence (HIGH RISK)

**What it would do:** P2 signal contributes to regime classification
(e.g., dampen-dominant biases toward PROCESS_DRIFT).

**Safety:** High risk. Regime changes cascade to recommended_action,
execution_mode_override, and escalation_override. A small P2 signal
could trigger regime transitions with outsized downstream effects.

**In scope for Phase 3:** No. Explicitly excluded.

### B5. Direct CSR state rewrite (HIGHEST RISK)

**What it would do:** Guna feeds back into live C_s, M, H values.

**Safety:** Highest risk. Violates anti-roadmap rule 6.2. Creates
potential for circular amplification within a single pass.

**In scope for Phase 3:** No. Violates design rules. Reserved for
Phase 4 if ever.

---

## C. Recommended Phase 3 scope

### First-scope target: opt-in confidence modulation only

Phase 3 first implementation should do exactly two things:

1. **Audit-label enrichment:** Compute the P2 audit signal during
   governance evaluation and record `p2_dominant_tendency`,
   `p2_net_coherence_delta`, and `p2_confidence_penalty` in the
   audit snapshot (`request_snapshot` dict in `governance_service.py`).
   This happens unconditionally — it is pure observability.

2. **Confidence penalty contribution:** When enabled by domain
   policy, convert the P2 net_coherence_delta into a small confidence
   penalty that participates in the existing sovereign penalty
   aggregation (the `min(0.20, sum(...))` block at
   `governance_service.py:1477–1493`).

### Confidence penalty formula

```
# Only when p2_modulation_enabled=True in domain policy:

if net_coherence_delta >= 0:
    # Clarify-dominant or neutral: no penalty
    p2_penalty = 0.0
else:
    # Dampen-dominant: small confidence reduction
    p2_penalty = min(P2_CONFIDENCE_CAP, abs(net_coherence_delta))
```

**P2_CONFIDENCE_CAP = 0.03** (hardcoded, not configurable)

### Design decisions

**Why penalty-only, not bonus:**
- The existing sovereign penalty system is subtractive-only (penalties
  reduce confidence, nothing increases it above baseline)
- Adding a bonus path would break the monotonic-reduction invariant
- Clarify-dominant states already have high integrated_confidence
  (r=0.87 correlation from P2 eval) — boosting confidence would
  double-count an already-present signal
- Penalty-only means P2 can make things stricter but never looser

**Why cap at 0.03:**
- The existing guna_anomaly adapter caps at 0.05 for actual anomalies
  (collapse, oscillation)
- P2 is a directional tendency, not an anomaly — it should be weaker
- 0.03 is ~15% of the aggregate sovereign cap (0.20)
- Even at maximum, it shifts confidence by less than one threshold
  boundary in typical scenarios

**Why within the existing aggregate cap:**
- The aggregate cap of 0.20 is not expanded
- P2 competes with other sovereign signals for budget within that cap
- This prevents compound over-penalization from stacking many small
  signals

---

## D. Governance integration point

### Where the P2 signal enters the governance flow

The promoted signal enters at the **sovereign penalty aggregation**
in `governance_service.py:1477–1493`. This is the established
integration point for all signal-adapter penalties.

### Current flow (simplified)

```
gate_decision.confidence.overall          # raw gate confidence
+ jepa_assessment.confidence_adjustment   # JEPA regime penalty (≤0)
- sovereign_penalty                       # sum of adapter penalties (capped 0.20)
= effective_confidence                    # final confidence (floored at 0.0)
```

### Proposed flow (Phase 3)

```
sovereign_penalty = min(0.20,
    entropy_resolution.confidence_penalty
    + insight_resolution.confidence_penalty
    + guna_anomaly_resolution.confidence_penalty
    + core_coherence_resolution.confidence_penalty
    + ucf_resolution.confidence_penalty
    + predictive_resolution.confidence_penalty
    + ontology_balance_signal.confidence_penalty
    + plasticity_resolution.confidence_penalty
    + p2_energetic_penalty,                         # <-- NEW
)
```

The `p2_energetic_penalty` is 0.0 when:
- `p2_modulation_enabled` is False (default), OR
- net_coherence_delta >= 0 (clarify-dominant or neutral)

The `p2_energetic_penalty` is `min(0.03, abs(net_coherence_delta))` when:
- `p2_modulation_enabled` is True, AND
- net_coherence_delta < 0 (dampen-dominant)

### File-level integration map

| File | Change | Purpose |
|------|--------|---------|
| `governance_service.py:~1477` | Add `p2_energetic_penalty` to sovereign sum | Live confidence influence |
| `governance_service.py:~1380` | Compute P2 audit signal alongside JEPA check | Signal computation |
| `governance_service.py:~1937` | Add P2 fields to audit snapshot | Observability |
| `domain_policy.py:~162` | Add `p2_modulation_enabled` to `DomainThresholdOverrides` | Policy control |
| `guna_derivation.py` | No change — `guna_csr_modulation_audit()` already exists | — |
| `types.py` | No change — `GunaCsrAuditSignal` already exists | — |

### What is NOT an integration point

- `jepa_governance.py` — P2 does not enter JEPA assessment or regime classification
- `confidence_gate.py` — P2 does not modify raw gate evaluation
- `csr_inference.py` — P2 does not modify CSR state
- `guna_derivation.py` (forward path) — P2 does not modify CSR→Guna derivation
- `signal_reconciliation.py` — P2 does not participate in signal reconciliation
- `compute_residual()` — P2 does not affect residual magnitude

---

## E. Policy / control surface

### Minimal governance controls (2 fields total)

Add to `DomainThresholdOverrides` in `domain_policy.py`:

```python
@dataclass(frozen=True)
class DomainThresholdOverrides:
    # ... existing 5 fields ...

    # Phase 3: Energetic modulation promotion
    p2_modulation_enabled: bool = False
    # Default False → P2 remains audit-only (Phase 2 behavior).
    # When True, dampen-dominant P2 signal contributes a small
    # confidence penalty (max 0.03) within sovereign penalty cap.

    p2_confidence_cap: Optional[float] = None
    # Default None → uses hardcoded P2_CONFIDENCE_CAP (0.03).
    # Domain policy can set a LOWER cap (stricter), never higher.
    # Effective cap = min(P2_CONFIDENCE_CAP, domain_override).
```

### Why only 2 fields

The original roadmap proposed 3 fields (alpha override, feedback mode,
feedback weight). This spec reduces to 2 because:

1. **`ontology_vritti_prior_alpha` override is deferred.** P1 alpha is
   hardcoded at 0.2 and calibrated. Domain-specific alpha tuning is a
   separate concern from P2 promotion. It can be added independently
   if evidence supports it, but it is not part of P2 promotion.

2. **Mode switch (`audit_only` vs `live_bounded`) is replaced by a
   boolean.** The P2 signal is always computed (audit). The boolean
   controls whether its penalty enters the sovereign sum. Simpler.

3. **Weight parameter is replaced by a cap.** The P2 formula directly
   uses `net_coherence_delta` (which is bounded by `_AUDIT_MAX_DELTA`
   = 0.10). The cap limits how much of that signal translates to
   confidence penalty. Effective range: [0.0, 0.03]. One parameter,
   not two.

### What is NOT in the control surface

- No per-vritti-mode controls
- No per-guna-component weights
- No mode allowlist/denylist
- No energetic threshold for "when to matter"
- No P2 escalation bias controls

These are all deferred. If Phase 3 demonstrates value with 2 fields,
finer controls can be considered. If it does not, fewer controls are
better.

---

## F. Safety constraints

These are non-negotiable requirements for any Phase 3 implementation.

### F1. Off by default

`p2_modulation_enabled` defaults to `False`. No domain profile ships
with it enabled. Zero behavioral change until an operator explicitly
opts in.

### F2. Bounded effect

The confidence penalty from P2 is capped at `P2_CONFIDENCE_CAP = 0.03`
(hardcoded constant, not configurable upward). Domain policy can only
reduce this cap, never increase it.

### F3. Within existing aggregate cap

The P2 penalty participates in the existing `min(0.20, sum(...))`
sovereign penalty aggregation. It does not add a separate penalty
channel. Total sovereign penalty including P2 cannot exceed 0.20.

### F4. No direct CSR rewrite

P2 does not modify C_s, M, or H in `csr_inference.py` or anywhere
else. The CSR inference module remains guna-free. (Anti-roadmap 6.2)

### F5. No regime changes

P2 does not participate in `_classify_regime()`. It does not affect
alignment, semantic_consistency, or action_state_coherence. Regime
classification is unchanged by P2 promotion.

### F6. No same-pass recursive updates

Within a single `authorize()` call:
- CSR is computed first
- Guna is derived from CSR second
- P2 audit signal is computed third
- P2 penalty enters sovereign aggregation fourth

There is no re-entrant step. The P2 penalty does not feed back into
CSR or guna within the same pass. (Anti-roadmap 6.3)

### F7. Weak/ambiguous signals default to zero

When `net_coherence_delta >= 0` (clarify-dominant or neutral), the
P2 penalty is 0.0. Only dampen-dominant states produce nonzero
penalty. Mixed or balanced guna states produce near-zero
net_coherence_delta and therefore near-zero penalty.

### F8. Full audit visibility

Every governance evaluation must record in the audit snapshot:
- `p2_dominant_tendency`: str (clarify/agitate/dampen/neutral)
- `p2_net_coherence_delta`: float
- `p2_confidence_penalty`: float (0.0 when disabled or non-negative)
- `p2_modulation_enabled`: bool

These fields are always present regardless of whether modulation
is enabled. This ensures observability even in audit-only mode.

### F9. Deterministic

Same inputs must always produce the same P2 penalty. No randomness,
no hysteresis, no state carried across governance passes.

### F10. Reversible

Setting `p2_modulation_enabled = False` must restore exact P2
audit-only behavior. No persistent state from previous enabled
periods affects future evaluations.

---

## G. Failure modes and risks

### G1. Hidden double-counting with integrated_confidence

**Risk:** P2 net_coherence_delta correlates with integrated_confidence
at r=0.87. If P2 penalty stacks on top of JEPA confidence_adjustment
(which is also driven by alignment/confidence), the same underlying
signal may be penalized twice.

**Mitigation:** The P2 cap (0.03) is deliberately small relative to
JEPA confidence_adjustment range (0 to -0.50). At worst, a
dampen-dominant state adds 0.03 on top of whatever JEPA already
penalized. The aggregate cap (0.20) prevents compound runaway.

**Monitoring requirement:** Track correlation between
`jepa_confidence_adjustment` and `p2_confidence_penalty` in audit
data. If they are >0.9 correlated, P2 is redundant and should be
disabled.

### G2. Over-penalizing already-weak states

**Risk:** Low-quality, low-coherence states already receive JEPA
confidence_adjustment of -0.15 to -0.50 and sovereign penalties up
to 0.20. Adding P2 penalty could push effective_confidence to 0.0
more often, making the system overly restrictive.

**Mitigation:** P2 penalty (max 0.03) is small. Effective_confidence
is floored at 0.0 regardless. But the real mitigation is the
aggregate cap: if other sovereign penalties already consume 0.17+
of the 0.20 budget, P2's 0.03 contributes at most 0.03 and the
total stays at 0.20.

### G3. Making energetic labels look causal

**Risk:** Once P2 influences confidence, operators may treat
"dampen" / "agitate" / "clarify" as causal explanations for
governance decisions rather than diagnostic tendencies.

**Mitigation:** Documentation and audit labels must always include
`audit_only: True` (for the underlying signal) and clearly state
that P2 is a tendency indicator, not a causal explanation. The
confidence penalty is a risk-averse response to dampen-dominance,
not a claim that tamas "caused" low quality.

### G4. Policy confusion from too many knobs

**Risk:** Adding P2 controls to DomainThresholdOverrides (already
5 fields) risks operator confusion.

**Mitigation:** Phase 3 adds exactly 2 fields. Both have obvious
defaults (False, None). The cap field is optional and only relevant
when modulation is enabled. No interaction effects with existing
threshold fields.

### G5. Circular promotion creep

**Risk:** Phase 3 success creates pressure to expand: "if 0.03
works, why not 0.10?" "if confidence works, why not regime?"
Each expansion weakens the safety guarantees.

**Mitigation:** The hardcoded cap (0.03) is in the function body,
not in domain policy. Raising it requires a code change with review,
not a configuration change. Phase 4 is a separate design exercise
with its own justification threshold.

---

## H. Validation plan for future implementation

Before Phase 3 implementation can be considered safe, the following
must be demonstrated:

### H1. Bounded confidence shift

For every scenario in the P2 evaluation set (17 scenarios):
- With `p2_modulation_enabled=True`: effective_confidence must change
  by at most 0.03 compared to `p2_modulation_enabled=False`
- Effective_confidence must never go negative (floored at 0.0)

### H2. No regime churn

For every scenario: governance regime with P2 enabled must be
identical to regime with P2 disabled. P2 does not enter regime
classification.

### H3. No instability under perturbation

Rerun stability analysis from P2 evaluation (eps=0.02 perturbation)
with P2 penalty active. Max confidence shift from perturbation must
be < 0.001 (same order as current stability).

### H4. Domain-level evaluation

Test with at least 2 domain profiles:
- Finance domain with `p2_modulation_enabled=True`: verify stricter-
  only enforcement preserved, no relaxation of existing thresholds
- Default domain (no overrides): verify zero behavioral change

### H5. Operator visibility / traceability

Audit snapshot must contain all 4 P2 fields (Section F8). An operator
reading the audit log must be able to determine:
- Whether P2 modulation was enabled
- What the P2 signal was
- How much confidence penalty was applied
- Whether it was within the aggregate cap

### H6. Ablation against baseline

Compare governance outcomes across the full evaluation scenario set:
- Baseline (P2 disabled)
- P2 enabled, default cap (0.03)
- P2 enabled, reduced cap (0.01)

Measure: number of decision changes, direction of changes (stricter
vs looser), correlation with existing penalties.

### H7. No existing test regressions

All existing tests (120+ in test_jepa_governance.py, plus broader
suite) must pass with P2 modulation disabled (default). With P2
enabled, only confidence values may change, within bounds.

---

## I. Explicit non-goals

Phase 3 first implementation must NOT:

1. **Modify CSR state** — no changes to C_s, M, H values anywhere
2. **Influence regime classification** — no changes to
   `_classify_regime()` inputs or thresholds
3. **Change action eligibility** — no direct ALLOW/DENY/CONFIRM
   decisions based on P2 signal
4. **Add escalation bias** — no escalation_level bumps from P2
5. **Modify execution mode** — no execution_mode_override from P2
6. **Create cross-pass persistence** — no tracking of P2 signal
   history across governance calls
7. **Override the P1 alpha** — ontology_vritti_prior_alpha stays
   hardcoded at 0.2; domain-specific alpha is a separate concern
8. **Add per-vritti or per-guna controls** — no fine-grained
   per-mode configuration
9. **Boost confidence** — P2 can only penalize (reduce confidence),
   never increase it above baseline
10. **Participate in signal reconciliation** — P2 is not a
    reconciled signal; it enters only as a sovereign penalty term

---

## J. Final recommendation

### Implement Phase 3 later — when a concrete use case appears

**Rationale:**

P2 is proven to be interpretable, stable, and incrementally useful
as a diagnostic signal. The design for safe promotion is
straightforward (confidence penalty, 2 domain fields, within
existing aggregate cap). The implementation would be small (~30
lines of logic + ~20 lines of domain policy + ~40 lines of tests).

However, there is no current evidence that the P2 confidence
penalty would change any governance decision in a way that matters.
The P2 eval showed all 17 scenarios produce `regime=normal` and
`recommended_action=ALLOW`. A 0.03 confidence penalty on
dampen-dominant states would reduce confidence from, say, 0.238 to
0.208 — both well above any decision threshold.

**The honest assessment:** P2's value is currently diagnostic, not
decisional. The confidence penalty is defensible but unlikely to
cross any threshold in practice. Implementing it now would add
code and policy surface for zero observable behavioral change.

**Recommendation:** Keep P2 audit-only for now. Implement Phase 3
when either:

1. **A domain-specific use case appears** where dampen-dominant
   states need to reduce confidence (e.g., a high-risk domain where
   tamas-tendency should trigger extra caution)

2. **Confidence thresholds tighten** such that a 0.03 penalty
   could meaningfully affect decisions

3. **An operator requests** energetic modulation influence on
   governance behavior

Until then, P2 as audit-only is the right level. The spec is ready
for when implementation is justified.

---

*Design spec complete. No implementation changes made.*