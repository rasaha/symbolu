# Directional Model Refinement: JEPA Implementation Roadmap

> **Status:** Proposed | **Scope:** Additive refinement, not rewrite
>
> This roadmap implements the directional causal model across the
> existing JEPA governance architecture. The model separates two axes:
>
> - **Cognitive axis:** Ontology (structural cause) → Vritti (operative mode)
> - **Energetic axis:** CSR (structural cause) → Guna (emergent field)
>
> Reverse influence (Vritti → ontological expression, Guna → CSR
> expression) is bounded, threshold-gated, and governance-controlled.

---

## 1. Executive summary

The current JEPA implementation has the energetic axis (CSR → Guna)
already wired correctly. The cognitive axis is partially directional:
Vritti → expected ontology exists via the R[v,a] coupling matrix, but
Ontology → Vritti causation is absent — both signals are independently
approximated from the same governance inputs (`quality`, `coherence`,
`overall_confidence`) with no cross-influence.

This roadmap adds the missing directional links in five phases:

| Phase | What changes | Behavior change |
|-------|-------------|-----------------|
| **P0: Codify interpretation** | Documentation + naming only | None |
| **P1: Ontology → Vritti prior** | Ontology weights bias vritti approximation | Soft — vritti distribution shifts |
| **P2: Guna → CSR audit signal** | Guna feeds back to CSR as audit-only | None (logging only) |
| **P3: Governance-controlled promotion** | Domain policy controls cross-weights | Bounded — domain-specific |
| **P4: Adaptive feedback (future)** | Threshold-gated reverse reclassification | Conditional — requires evidence |

Each phase is additive. No existing tests break. No existing
thresholds change. Fail-closed defaults are preserved throughout.

---

## 2. Current state: what is wired

### Cognitive axis

| Direction | Wired? | Where | How |
|-----------|--------|-------|-----|
| Ontology → Vritti | **No** | — | Both approximated independently from `quality`, `coherence`, `overall_confidence` in `jepa_governance.py:1291-1354` |
| Vritti → expected Ontology | **Yes** | `coupling.py:78-102` | `get_aspect_weights(vritti_dist)` via R[v,a] matrix multiplication |
| Expected vs actual Ontology | **Yes** | `jepa_governance.py:557-571` | Cosine similarity → alignment score |

**Key observation:** `approximate_layer_weights()` (line 1291) and
`approximate_vritti()` (line 1322) both take the same inputs but
produce outputs independently. There is no path where ontology
weights influence vritti classification or vice versa at construction
time.

### Energetic axis

| Direction | Wired? | Where | How |
|-----------|--------|-------|-----|
| CSR → Guna | **Yes** | `guna_derivation.py:69-131` | `S_raw = C_s * (1-H)`, `T_raw = H * (1-C_s)` |
| Guna → CSR | **No** | — | Explicitly not fed back (`GunaVector` docstring: "Is not fed back") |
| Guna → Intensity | **Yes** | `entropy_modulation_engine.py` | `G = w_S*S + w_R*R + w_T*T` → modulation factor |
| Guna anomalies → Governance | **Yes** | `guna_anomaly_adapter.py:59-109` | Collapse +0.03, oscillation +0.02, max 0.05 |

### Governance parameterization

| Mechanism | Configurable? | Where |
|-----------|--------------|-------|
| JEPA thresholds (`_ALIGNMENT_LOW`, etc.) | Hardcoded | `jepa_governance.py:681-685` |
| Signal adapter penalties | Hardcoded | Each adapter module |
| Cross-signal weighting | Not implemented | Aggregate cap at 0.20, equal implicit weight |
| Domain-specific thresholds | **Yes** | `domain_policy.py:162-190` via `DomainThresholdOverrides` |
| R[v,a] coupling matrix | Hardcoded | `coupling.py:55-62` |

---

## 3. Phased roadmap

### Phase 0: Codify interpretation (no behavior change)

**Objective:** Establish the directional model as the canonical
interpretation of existing code, without changing any runtime behavior.

**What changes:**
- Add docstring annotations to `approximate_layer_weights()` and
  `approximate_vritti()` marking ontology as structurally primary
  and vritti as operative/readout
- Add docstring to `build_jepa_composite()` clarifying that R[v,a]
  is a consistency operator ("given vritti, what ontology do we
  expect?"), not a causal generator ("vritti causes ontology")
- Add docstring to `get_aspect_weights()` in `coupling.py` clarifying
  the coupling is predictive, not generative
- Document the two-axis model in `AGENTIC_ARCHITECTURE.md` under
  the JEPA governance section

**Files involved:**
- `agentic/agentic_framework/jepa_governance.py` — docstrings on
  `approximate_layer_weights`, `approximate_vritti`,
  `build_jepa_composite`
- `agentic/chitta_vritti/coupling.py` — docstring on
  `get_aspect_weights`, module docstring
- `Project_documentation/agentic_framework/agentic/AGENTIC_ARCHITECTURE.md` — new subsection under JEPA
- `agentic/guna_modulation/guna_derivation.py` — docstring noting
  CSR is the structural cause of guna, not vice versa

**Tests:** None needed. No behavior change. Verify existing JEPA
test suite passes unchanged (~100+ tests in `test_jepa_governance.py`).

**Safety:** No risk. Pure documentation.

---

### Phase 1: Soft Ontology → Vritti prior

**Objective:** Wire the missing causal direction on the cognitive axis.
When ontology layer weights are available, they should bias the vritti
approximation — not replace it, but shift its distribution.

**What changes in behavior:**
- `approximate_vritti()` gains an optional `layer_weights` parameter
- When present, ontological layer weights apply a soft prior:
  - High O7_REASONING → boosts pramana probability
  - High O6_AGENCY → boosts viparyaya probability
  - High O5_COGNITION → boosts vikalpa probability
  - High O3_EXECUTION + O8_PURPOSE → boosts smrti probability
  - High O1_POTENTIAL + O12_ABSOLVING → boosts nidra probability
- The prior is blended with the existing signal-based approximation
  using a mixing weight (default conservative, e.g. `alpha=0.2`)
- The mixing weight is NOT configurable at this phase — it is a
  hardcoded default like all other adapter constants

**Precise mechanism:**

```
# Current: vritti = f(quality, coherence, confidence)
# Proposed: vritti = (1-alpha) * f(quality, coherence, confidence)
#                  + alpha * ontology_prior(layer_weights)

def ontology_vritti_prior(layer_weights: Dict[str, float]) -> Dict[str, float]:
    """Derive vritti prior from ontological layer weights.

    This is the Ontology → Vritti causal direction:
    the active ontological layer determines which cognitive
    modes are structurally favored.

    Returns unnormalized vritti tendencies.
    """
    return {
        "pramana":   layer_weights.get("O7_REASONING", 0) * 0.6
                   + layer_weights.get("O9_WITNESSES", 0) * 0.3,
        "viparyaya": layer_weights.get("O6_AGENCY", 0) * 0.5,
        "vikalpa":   layer_weights.get("O5_COGNITION", 0) * 0.5
                   + layer_weights.get("O4_STRUCTURE", 0) * 0.2,
        "smrti":     layer_weights.get("O3_EXECUTION", 0) * 0.4
                   + layer_weights.get("O8_PURPOSE", 0) * 0.4,
        "nidra":     layer_weights.get("O1_POTENTIAL", 0) * 0.5
                   + layer_weights.get("O12_ABSOLVING", 0) * 0.3,
    }
```

**Why these specific couplings:** They are the transpose of the R[v,a]
primary couplings. If pramana → O7_REASONING is the strongest forward
coupling (0.95), then O7_REASONING → pramana is the natural reverse
prior. The weights are deliberately lower (0.3–0.6) because this is
a soft prior, not a deterministic mapping.

**Files involved:**
- `agentic/agentic_framework/jepa_governance.py` —
  - New function: `ontology_vritti_prior(layer_weights)`
  - Modified function: `approximate_vritti()` gains optional
    `layer_weights` kwarg
  - Modified caller: `_run_jepa_check` in `governance_service.py`
    passes layer_weights to vritti resolution
- `agentic/agentic_framework/governance_service.py` —
  - `_resolve_vritti()` passes `layer_weights` when available
- `agentic/agentic_framework/signal_adapters/vritti_adapter.py` —
  - `resolve_vritti_signal()` accepts optional `layer_weights`,
    passes to `approximate_vritti` fallback path only

**What does NOT change:**
- If real `ChittaVrittiResult` is available on the request, it is
  used as-is (no ontology prior applied to real signals)
- The prior only applies to the approximation fallback path
- R[v,a] coupling matrix is unchanged
- All existing thresholds unchanged
- `approximate_layer_weights()` is unchanged — no circular dependency

**Tests needed:**
- `ontology_vritti_prior()` unit tests: known inputs → expected outputs
- `approximate_vritti(layer_weights=...)` vs `approximate_vritti()`:
  verify the prior shifts distribution in the expected direction
- Regression: all existing JEPA tests pass with `layer_weights=None`
  (default path unchanged)
- Integration: `_run_jepa_check` produces a valid assessment when
  layer_weights flows through to vritti
- Edge case: all-zero layer_weights → prior contributes nothing
- Edge case: extreme layer_weights → vritti prior is bounded by alpha

**Safety controls:**
- `alpha=0.2` means ontology prior can shift vritti by at most 20%
- Prior is additive-then-normalized, not multiplicative — cannot
  zero out a vritti mode
- If `layer_weights` is None, behavior is byte-identical to current
- No circular dependency: `approximate_layer_weights` does not call
  `approximate_vritti`, and the prior flows one-way only

**Risk:** Low. The prior is soft, bounded, and only applies to the
approximation fallback. Real vritti signals are unaffected.

---

### Phase 2: Audit-only Guna → CSR feedback signal

**Objective:** Wire the missing reverse direction on the energetic
axis — but as an audit-only signal that is logged and never consumed
by any decision path.

**What changes in behavior:** Nothing in governance decisions. A new
audit field appears in CSR inference output.

**Mechanism:**

```
# After guna derivation, compute what CSR *would* look like
# if guna were feeding back:

def guna_csr_modulation_audit(
    guna: GunaVector,
    current_C_s: float,
    current_H: float,
) -> Dict[str, float]:
    """Audit-only: what CSR expression would be if guna fed back.

    Sattva clarifies (lower H, higher C_s)
    Rajas agitates (higher M, moderate H)
    Tamas dampens (higher H, lower C_s)

    NOT applied to any live signal. Logged for analysis only.
    """
    delta_C_s = (guna.sattva - guna.tamas) * 0.1  # small modulation
    delta_H = (guna.tamas - guna.sattva) * 0.1
    return {
        "modulated_C_s": max(0.0, min(1.0, current_C_s + delta_C_s)),
        "modulated_H": max(0.0, min(1.0, current_H + delta_H)),
        "delta_C_s": delta_C_s,
        "delta_H": delta_H,
        "audit_only": True,
    }
```

**Why audit-only first:**
- The `GunaVector` docstring explicitly says "Is not fed back"
- Changing that contract is a significant architectural decision
- Audit-only lets us observe what WOULD happen before committing
- If the audit signal shows instability (oscillation, amplification),
  we know not to promote it

**Files involved:**
- `agentic/guna_modulation/guna_derivation.py` —
  New function: `guna_csr_modulation_audit()`
- `agentic/guna_modulation/pipeline_integration.py` —
  Call audit function after `derive_guna_vector()`, attach to trace
- `agentic/guna_modulation/types.py` —
  New dataclass: `GunaCsrAuditSignal` (frozen, audit-only)

**What does NOT change:**
- `GunaVector` remains "not fed back" for all live paths
- CSR inference (`csr_inference.py`) is untouched
- No governance penalty changes
- No guna derivation formula changes
- Entropy modulation engine unchanged

**Tests needed:**
- `guna_csr_modulation_audit()` unit tests: known guna + C_s + H →
  expected deltas
- Verify deltas are bounded (max ±0.1 per axis)
- Verify `audit_only=True` is always set
- Regression: full pipeline produces identical guna values
- Integration: audit signal appears in trace output

**Safety controls:**
- Function output is never consumed by any governance path
- `audit_only: True` field is a machine-readable guard
- Deltas are clamped to ±0.1 — cannot produce extreme modulation
- No import of this function from any governance module

**Risk:** Minimal. Pure observability addition.

---

### Phase 3: Governance-controlled cross-weight promotion

**Objective:** Make the Phase 1 mixing weight (`alpha`) and Phase 2
audit signal governable via `DomainProfile` / `DomainThresholdOverrides`.

**What changes in behavior:**
- Domain policies can control how strongly ontology biases vritti
- Domain policies can optionally promote Guna → CSR from audit-only
  to live, with bounded weight
- Default behavior (no domain policy) remains identical to Phase 1

**Mechanism: extend DomainThresholdOverrides**

```python
# In domain_policy.py, add to DomainThresholdOverrides:

@dataclass
class DomainThresholdOverrides:
    # ... existing fields ...

    # Phase 3: Cross-axis governance weights
    ontology_vritti_prior_alpha: Optional[float] = None
    # Default None → uses hardcoded 0.2 from Phase 1
    # Range [0.0, 0.4] — governance cannot set above 0.4

    guna_csr_feedback_mode: Optional[str] = None
    # Default None → "audit_only" (Phase 2 behavior)
    # Options: "audit_only", "live_bounded"
    # "live_bounded" applies the Phase 2 deltas to actual CSR

    guna_csr_feedback_weight: Optional[float] = None
    # Default None → 0.0 (no feedback)
    # Range [0.0, 0.15] — governance cannot set above 0.15
    # Only meaningful when guna_csr_feedback_mode = "live_bounded"
```

**Why these caps:**
- `ontology_vritti_prior_alpha` max 0.4: ontology should never
  dominate vritti classification (it's a prior, not a replacement)
- `guna_csr_feedback_weight` max 0.15: reverse modulation must be
  strictly weaker than forward derivation
- These caps are hardcoded and not overridable — governance controls
  within bounds, not the bounds themselves

**Domain-specific examples:**
- Finance: `ontology_vritti_prior_alpha=0.3` (stronger structural
  prior — in finance, the ontological domain should anchor cognitive
  mode more tightly)
- Finance: `guna_csr_feedback_mode="audit_only"` (no live feedback —
  too risky)
- Creative/exploratory: `ontology_vritti_prior_alpha=0.1` (lighter
  prior — allow more cognitive flexibility)
- Creative: `guna_csr_feedback_mode="live_bounded"`,
  `guna_csr_feedback_weight=0.05` (gentle feedback loop)

**Files involved:**
- `agentic/agentic_framework/domain_policy.py` —
  Extend `DomainThresholdOverrides` with 3 new fields
- `agentic/agentic_framework/jepa_governance.py` —
  `approximate_vritti()` reads alpha from domain context if available
- `agentic/guna_modulation/pipeline_integration.py` —
  Conditionally apply Guna → CSR feedback when domain permits
- `agentic/agentic_framework/governance_service.py` —
  Thread domain policy into vritti resolution and guna paths

**What does NOT change:**
- Default behavior with no domain policy is Phase 1 / Phase 2
- Hardcoded caps cannot be overridden
- R[v,a] coupling matrix unchanged
- Existing domain profiles (finance, devops) unchanged unless
  explicitly updated
- No changes to signal reconciliation (`signal_reconciliation.py`)

**Tests needed:**
- Domain policy with `ontology_vritti_prior_alpha=0.3` produces
  stronger ontology-biased vritti than default `alpha=0.2`
- Domain policy with `guna_csr_feedback_mode="live_bounded"` applies
  modulation; `"audit_only"` does not
- Cap enforcement: `ontology_vritti_prior_alpha=0.9` → clamped to 0.4
- Cap enforcement: `guna_csr_feedback_weight=0.5` → clamped to 0.15
- Default domain (no overrides) → identical to Phase 1/2 behavior
- Finance profile integration: stricter-only enforcement preserved
- No circular update: ontology is computed before vritti, guna before
  CSR feedback, within the same governance pass

**Safety controls:**
- Hardcoded caps (`0.4`, `0.15`) are in the function body, not in
  domain policy — governance cannot bypass them
- `stricter_only` enforcement on `DomainThresholdOverrides` preserved
- Single-pass guarantee: within one `authorize()` call, ontology is
  fixed before vritti is computed, and CSR is fixed before guna
  feedback is applied — no re-entrant updates

**Risk:** Medium. This is the first phase where cross-axis influence
becomes live. The caps and single-pass guarantee bound the risk, but
integration testing across multiple domain profiles is essential.

---

### Phase 4: Adaptive feedback (future, conditional)

**Objective:** Allow reverse-direction influence to modify the base
layer (ontology reclassification from vritti evidence, CSR adjustment
from guna patterns) — but only when persistence and confidence
thresholds are crossed.

**This phase is intentionally underspecified.** It should only be
designed after Phase 3 is deployed and the audit signals from Phase 2
have been analyzed in practice.

**Preconditions before starting Phase 4:**
- Phase 3 deployed and stable for at least one release cycle
- Audit-only Guna → CSR data collected and analyzed
- No oscillation or amplification observed in audit signals
- Clear evidence that reverse reclassification would improve
  governance accuracy (not just theoretical elegance)

**Sketch of mechanism:**

Vritti → Ontology reclassification:
- Track vritti primary mode across N consecutive governance passes
- If the same vritti dominates for N passes AND actual ontology
  alignment is below `_ALIGNMENT_LOW` for the same period:
  - Emit a `RECLASSIFICATION_CANDIDATE` audit event
  - If governance policy permits: adjust ontology prior weights
    toward the vritti-expected ontology
  - Single adjustment per cycle, max delta per layer capped

Guna → CSR adjustment:
- Track guna dominant mode across N consecutive modulation cycles
- If sattva/rajas/tamas dominance persists AND CSR metrics show
  the predicted modulation would improve coherence:
  - Emit a `CSR_ADJUSTMENT_CANDIDATE` audit event
  - If governance policy permits: apply bounded CSR shift

**Key constraint:** Reclassification never happens within the same
governance pass that produced the evidence. It requires cross-pass
persistence. This prevents circular collapse.

**Files likely involved:**
- New module: `agentic/agentic_framework/cross_layer_promotion.py`
- `governance_service.py` — persistence tracking across passes
- `domain_policy.py` — reclassification thresholds per domain

**Risk:** High. This is where circular collapse becomes possible if
implemented carelessly. The persistence requirement and per-cycle caps
are essential safety mechanisms.

---

## 4. File/module targets by phase

| File | P0 | P1 | P2 | P3 | P4 |
|------|----|----|----|----|-----|
| `jepa_governance.py` | docstrings | `ontology_vritti_prior()`, modify `approximate_vritti()` | — | read alpha from domain | — |
| `coupling.py` | docstrings | — | — | — | — |
| `guna_derivation.py` | docstrings | — | `guna_csr_modulation_audit()` | — | — |
| `guna_modulation/types.py` | — | — | `GunaCsrAuditSignal` dataclass | — | — |
| `pipeline_integration.py` | — | — | call audit, attach to trace | apply live feedback if domain permits | — |
| `governance_service.py` | — | pass `layer_weights` to vritti | — | thread domain policy | persistence tracking |
| `signal_adapters/vritti_adapter.py` | — | accept `layer_weights` in fallback | — | — | — |
| `domain_policy.py` | — | — | — | 3 new fields on `DomainThresholdOverrides` | reclassification thresholds |
| `AGENTIC_ARCHITECTURE.md` | new subsection | — | — | — | — |
| New: `cross_layer_promotion.py` | — | — | — | — | persistence + promotion logic |

---

## 5. Validation and test plan by phase

### Phase 0
- Run existing test suite: `pytest agentic/agentic_framework/tests/test_jepa_governance.py` — expect 100+ pass, 0 fail
- No new tests needed

### Phase 1
| Test | Type | What it validates |
|------|------|-------------------|
| `ontology_vritti_prior()` known inputs | Unit | O7=1.0 → pramana dominates; O1=1.0 → nidra dominates |
| `approximate_vritti(layer_weights=None)` unchanged | Regression | Default path byte-identical |
| `approximate_vritti(layer_weights=...)` shifts distribution | Unit | Prior shifts in expected direction |
| Alpha bounding | Unit | Prior contribution ≤ alpha × total |
| Zero layer_weights | Edge case | Prior contributes zero |
| `_run_jepa_check` integration | Integration | Valid assessment when layer_weights flows through |
| Existing JEPA suite | Regression | All 100+ tests pass |

### Phase 2
| Test | Type | What it validates |
|------|------|-------------------|
| `guna_csr_modulation_audit()` known inputs | Unit | Sattva-dominant → positive delta_C_s, negative delta_H |
| Delta bounds | Unit | |delta_C_s| ≤ 0.1, |delta_H| ≤ 0.1 |
| `audit_only=True` always set | Contract | Machine-readable guard |
| Pipeline output unchanged | Regression | Guna values identical with and without audit |
| Audit signal in trace | Integration | Signal appears in pipeline output |

### Phase 3
| Test | Type | What it validates |
|------|------|-------------------|
| Domain alpha override | Unit | `ontology_vritti_prior_alpha=0.3` → stronger bias |
| Cap enforcement | Unit | `alpha=0.9` → clamped to 0.4 |
| Live feedback mode | Integration | `"live_bounded"` applies modulation |
| Audit-only default | Integration | No domain override → audit-only |
| Finance profile | Integration | Stricter-only preserved |
| No circular update | Contract | Ontology fixed before vritti, CSR fixed before guna feedback, within single `authorize()` |

---

## 6. Anti-roadmap: what NOT to do

These are explicit architectural violations. If any implementation
drifts toward these patterns, stop and redesign.

### 6.1 Do not let vritti directly rewrite ontology state

Vritti is an operative readout. It should never set `layer_weights`
on the `OntologySignal`. The R[v,a] matrix produces *expected*
ontology — a prediction used for consistency checking. The actual
ontology comes from the sovereign state or approximation function.

If vritti could rewrite ontology, and ontology biases vritti (Phase 1),
you get: vritti → ontology → vritti → ... in the same pass. This is
circular collapse.

### 6.2 Do not let guna directly rewrite CSR state

Guna is a derived emergent field. It should never modify C_s, M, or H
inside `csr_inference.py`. Phase 2 computes what modulation *would*
look like. Phase 3 may apply bounded modulation downstream. But the
CSR inference module (`EntropySinkInference`, `SynthesisGateInference`)
must remain guna-free.

### 6.3 Do not allow simultaneous bidirectional updates in one pass

Within a single `authorize()` call or pipeline pass:
- Ontology is computed FIRST
- Vritti is computed SECOND (optionally using ontology prior)
- CSR is computed FIRST
- Guna is derived SECOND (from CSR)
- Guna feedback (if live) is applied THIRD

There is no re-entrant step. The updated vritti does not feed back
into ontology within the same pass. The guna-modulated CSR does not
feed back into guna derivation within the same pass.

### 6.4 Do not create uncontrolled parameter explosion

Phase 3 adds exactly 3 governance fields. Do not expand this into:
- per-vritti-mode alpha values (5 parameters)
- per-ontology-layer prior weights (12 parameters)
- per-guna-component feedback weights (3 parameters)
- per-domain × per-axis weight matrices

The cognitive axis has ONE alpha. The energetic axis has ONE weight
and ONE mode switch. That is sufficient. If finer control is ever
needed, it should come from a new phase with its own justification.

### 6.5 Do not hide heuristics behind opaque names

Every cross-axis weight must be:
- Named (what it controls)
- Bounded (hardcoded max)
- Documented (why this value)
- Auditable (appears in trace/audit output)

Do not create functions like `_adjust_cross_signal()` that blend
multiple axes with unlabeled weights. Each axis must be separable
and independently auditable.

### 6.6 Do not treat the directional model as empirically proven

This is a structurally valid modeling paradigm. It is internally
consistent. It may improve governance accuracy. But it has not been
empirically validated against real-world governance outcomes.

Every phase must be reversible. Phase 1 can be disabled by setting
`alpha=0.0`. Phase 2 can be deleted (audit-only). Phase 3 defaults
to Phase 1/2 behavior. No phase should create a hard dependency
that makes rollback impossible.

---

## 7. Best first implementation recommendation

### Start with Phase 0 + Phase 1 together

Phase 0 is documentation-only and should be done alongside Phase 1
(it provides the conceptual framing for the code change).

### Phase 1 implementation target

**One new function:** `ontology_vritti_prior()` in `jepa_governance.py`
— approximately 20 lines.

**One modified function:** `approximate_vritti()` gains one optional
parameter and 5 lines of blending logic.

**One modified caller:** `_resolve_vritti()` passes `layer_weights`
when on the approximation path.

Total code change: ~40 lines of implementation + ~30 lines of tests.

### Best first measurable success criterion

After Phase 1, run this validation:

1. Construct an ontology signal dominated by O7_REASONING (high quality,
   high coherence — an analytical context)
2. Compute vritti with and without the ontology prior
3. **Expected result:** With prior, pramana probability increases by
   5–15% (bounded by alpha). Without prior, distribution unchanged.
4. Run the full JEPA composite: alignment score should increase
   (ontology and vritti are now more coherent because the prior
   nudges vritti toward the direction R[v,a] would predict)

**Measurable criterion:** For the analytical-context test case,
`build_jepa_composite().alignment` with ontology prior ≥
`build_jepa_composite().alignment` without ontology prior.

This is measurable, falsifiable, and directly tests the hypothesis
that the Ontology → Vritti prior improves alignment.

### Biggest architectural risk if done badly

**Circular reclassification.** If Phase 4 is implemented without the
single-pass guarantee and persistence threshold, the system can enter:

```
ontology(t) → biases vritti(t) → expected_ontology(t) misaligns
→ reclassifies ontology(t+1) → biases vritti(t+1) → ...
```

Each pass shifts both signals toward each other until they converge
on an arbitrary fixed point that has nothing to do with the actual
cognitive state. This is the "mutual-influence collapse" the
directional model is designed to prevent.

**Mitigation:** The single-pass guarantee (P1–P3) makes this
impossible within a pass. The persistence threshold (P4) makes it
slow across passes. The hardcoded caps (P1: alpha ≤ 0.4, P3:
feedback ≤ 0.15) make convergence bounded even if it occurs.

All three mechanisms must be present. Removing any one creates the
risk.

---

## 8. Summary of design rules

| Rule | Enforced by |
|------|------------|
| Ontology is structurally primary on cognitive axis | Phase 1: vritti uses ontology as prior, not vice versa |
| Vritti is operative classifier / readout | Phase 1: prior is soft (alpha ≤ 0.4), not deterministic |
| CSR is structurally primary on energetic axis | Phase 2: guna → CSR is audit-only by default |
| Reverse influence is governance-gated | Phase 3: `DomainThresholdOverrides` controls promotion |
| Fail-closed defaults | All phases: None/missing → no cross-influence |
| No circular reclassification in same pass | Phases 1–3: single-pass ordering guarantee |
| Effect-direction starts audit-only | Phase 2: Guna → CSR is audit before live |
| Every parameter is bounded and auditable | Phases 1–3: hardcoded caps, named fields, trace output |
