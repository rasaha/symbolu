# Minimum Safe Alignment Spec: Mistral CG ↔ Directional Model

**Date:** 2026-04-07
**Type:** Design evaluation (no implementation)
**Scope:** Mistral CG training + inference paths only

---

## 1. Executive Summary

The Mistral CG stack is **already closer to directional alignment than
it appears**. The key finding is that the VrittiTokenScorer already
consumes ontological state (`o_ctx`) as a direct input during training,
creating implicit Ontology → Vritti structural causation. The agentic
side has an explicit `ontology_vritti_prior()` (Phase 1 of the
directional model roadmap, already implemented). These are architecturally
analogous mechanisms operating at different abstraction levels.

**The minimum safe alignment patch is: no inference-side changes are
needed beyond the existing Vritti gate.** The single highest-value
next step is a training-side-only soft ontological prior over Vritti
targets, making the implicit coupling explicit and learnable.

---

## 2. Signal-by-Signal Alignment Table

| Signal | Directional role | Current training role | Current inference role | Desired minimum role | Change needed? |
|--------|-----------------|----------------------|-----------------------|---------------------|----------------|
| **Bhava** | Not on either axis (phase/binding) | Primary: state_projector → intent_projector → phase_adapter → logit residual | Direct: phase adapter modulates logits | Stays as-is | **No** |
| **Vritti** | Cognitive axis: operative readout (downstream of ontology) | VrittiTokenScorer consumes `[hidden; o_ctx]` → 5D softmax; contrastive loss via `lambda_vritti_token` | Bounded sampling gate: temperature-only, cool-only, off by default | Training: make ontology→vritti coupling explicit. Inference: stays as-is. | **Training-side only** |
| **Ontological** | Cognitive axis: structural cause (upstream of vritti) | OntologyCompatibilityScorer scores token-ontology alignment; `compute_ontological_loss` on token embeddings | Not on live path. TwoStageGenerator dormant. | Training: explicitly provide ontological prior to vritti scorer. Inference: stays off live path. | **Training-side only** |
| **Guna** | Energetic axis: emergent field (downstream of CSR) | GunaTokenScorer consumes `[hidden; o_ctx]` → 3D softmax; contrastive loss via `lambda_guna_token` | Not on live path. Carried in state but not consumed. | Stays audit-only at inference. No change needed. | **No** |
| **CSR** | Energetic axis: structural cause (upstream of guna) | Dual paths: standalone spatial grounding (`enable_csr`) + token scorer (`lambda_csr_token`). Both off by default. | Not wired to MistralCGAdapter. | Stays off live generation path. | **No** |

---

## 3. Gap Analysis

### 3.1 Cognitive Axis: Ontology → Vritti

**What the directional model requires:**
- Ontology is structurally primary
- Vritti is an operative readout biased by ontological position
- Reverse direction (Vritti → expected ontology) is a consistency check only

**What the Mistral CG training path has:**

| Mechanism | Status | Evidence |
|-----------|--------|----------|
| VrittiTokenScorer receives `o_ctx` as input | **Implicit coupling exists** | `vritti_scorer.py:90` — `combined = torch.cat([hidden, o_ctx], dim=-1)` |
| Ontology and Vritti scored over same candidates | **Architectural coupling exists** | `primitives/__init__.py:170` — stacked into T ∈ ℝ^{K×6} |
| Both supervised via same auxiliary loss framework | **Training coupling exists** | `primitive_auxiliary.py` — independent contrastive losses per primitive |
| Explicit ontology-derived prior over Vritti targets | **Missing** | No mechanism biases Vritti loss targets based on ontological position |
| R[v,a] consistency check at training time | **Missing** | R[v,a] exists in `coupling.py` but is only used on the agentic/JEPA side |

**Assessment:** The implicit coupling (VrittiTokenScorer consuming `o_ctx`)
means the model *can* learn that ontological position influences cognitive
mode. But this is learned indirectly through gradient flow — the training
signal does not explicitly encode the Ontology → Vritti causal direction.
The model has to discover this relationship rather than being told it.

**Is this a real gap?** Yes, but a small one. The learned projection
`context_proj: (embed_dim + state_dim) → 5` has the capacity to implement
the ontology→vritti prior implicitly. Whether it actually does depends on
the training data and loss landscape. An explicit prior would make the
directionality structural rather than emergent.

### 3.2 Energetic Axis: CSR → Guna

**What the directional model requires:**
- CSR is structurally primary
- Guna is derived from CSR deterministically
- Reverse direction is audit-only by default

**What the Mistral CG training path has:**

| Mechanism | Status | Evidence |
|-----------|--------|----------|
| CSR → Guna derivation | **Not applicable** (Mistral CG path) | `guna_derivation.py` formulas exist on agentic side only |
| GunaTokenScorer receives `o_ctx` (not CSR) | **Structural parallel, not match** | `guna_scorer.py:95` — same `[hidden; o_ctx]` pattern as Vritti |
| CSR and Guna are independent scorers | **Correct** | `primitives/__init__.py` — no cross-interaction between columns |
| Guna → CSR audit signal | **Exists on agentic side** | `guna_csr_modulation_audit()` in `guna_derivation.py` |

**Assessment:** The energetic axis is architecturally different between
the agentic/JEPA path and the Mistral CG training path. On the agentic
side, CSR→Guna is a deterministic derivation (formulas). On the training
side, CSR and Guna are independent learned scorers that both consume
`[hidden; o_ctx]`. This is a **structural divergence**, not a gap that
needs fixing — the training side uses learned representations while the
agentic side uses explicit formulas. They serve different purposes at
different abstraction levels.

**No change needed.** Forcing the training-side Guna scorer to depend on
CSR would couple two independent learned representations without clear
benefit. The agentic-side formula-based derivation already handles the
directional semantics at inference time.

### 3.3 Bhava (Off-Axis)

Bhava is not on either directional axis. It is the phase/binding signal
that feeds the `IntentPhaseProjector`. No alignment gap exists.

---

## 4. Minimum Safe Patch Recommendation

### What should change in training

**One item: explicit ontology-conditioned Vritti soft prior.**

Mechanism (conceptual — not implementation):
- During training, when computing the Vritti contrastive loss, derive a
  soft target distribution from the current ontological state
- Use the R[v,a] matrix transpose to compute: given the dominant
  ontological layers in `o_ctx`, which Vritti modes are structurally
  expected?
- Blend this prior with the standard contrastive loss target using a
  small mixing weight (analogous to `alpha=0.2` on the agentic side)
- This makes the Ontology → Vritti direction explicit in the training
  signal, not just implicit in the input features

Why this is safe:
- It is a **loss regularizer**, not an architectural change
- It biases Vritti learning toward the directional model's causal
  structure without modifying the scorer architecture
- The R[v,a] matrix is already defined and validated
- A small alpha (0.1–0.2) means the prior is soft — the model can
  still learn data-driven Vritti distributions that diverge from the
  prior when the evidence is strong
- It is training-only — no inference path is affected
- It can be ablated by setting alpha=0.0

Why this is the minimum:
- The VrittiTokenScorer already consumes `o_ctx` — the architectural
  coupling exists. What's missing is the explicit *training signal*
  that encodes the causal direction.
- Without this, the model may or may not learn the Ontology → Vritti
  relationship depending on training dynamics. With this, the
  relationship is structurally encouraged.

### What should change in inference

**Nothing beyond the existing Vritti gate.**

Rationale:
- Bhava is already direct and correctly wired
- The Vritti gate is bounded, cool-only, and off by default
- Guna stays audit-only (carried in state, not consumed)
- CSR stays off the generation path
- Ontology stays off the live inference path (consistent with the
  directional model: ontology is a structural prior, not a generation
  controller)

The agentic/JEPA side already has `ontology_vritti_prior()` wired into
`approximate_vritti()` for the governance path. The Mistral CG inference
path reads only the 32D state output from the model — if training
correctly learns the Ontology → Vritti relationship, the state
projector's Vritti output will already reflect ontological influence.
No separate inference-time prior is needed.

### What should remain audit-only or deferred

| Item | Disposition | Reason |
|------|------------|--------|
| Guna live inference gate | Deferred | No clear use case; energetic axis less mature |
| CSR inference promotion | Deferred | Off the generation path by design |
| TwoStageGenerator activation | Deferred | Requires separate design review |
| R[v,a] consistency check at training time | Deferred | Would be Phase 2 — audit the learned coupling before adding more structure |
| Ontology live inference control | Deferred | Ontology is a prior, not a controller |
| Kosha depth control (Mistral path) | Deferred | Lower priority than cognitive axis alignment |

---

## 5. Special Attention: Ontology → Vritti

### Is the minimum safe alignment patch a soft ontology-derived prior during training?

**Yes.** This is the right framing for three reasons:

1. **Structural match with agentic side.** The agentic `ontology_vritti_prior()`
   uses R[v,a] transpose to bias `approximate_vritti()`. The training-side
   equivalent would use the same R[v,a] to bias the Vritti contrastive target.
   Same matrix, same direction, different abstraction level.

2. **Fills the only real gap.** The VrittiTokenScorer already has the
   *capacity* to learn ontology→vritti coupling (it receives `o_ctx` as input).
   The prior adds a *structural signal* that this is the intended direction.
   Without it, the relationship is emergent. With it, the relationship is
   encouraged.

3. **Low risk.** A loss-level regularizer at alpha=0.1–0.2 is the least
   invasive change possible. It doesn't modify the scorer architecture,
   doesn't change inference, and can be disabled by setting alpha=0.

### Should it be a live ontology gate?

**No.** Ontology is a structural cause, not a generation-time gate. The
Vritti gate already provides the operative readout function. Adding a
separate ontology gate would:
- Expand inference scope (violates constraint)
- Create a second control surface competing with Vritti gate
- Not match the directional model (ontology is upstream, not a controller)

### Should it be a separate inference controller?

**No.** The directional model is clear: ontology influences vritti at
construction time (training or governance approximation), and vritti
is the operative signal that affects generation. There is no design
justification for ontology to directly influence token selection at
inference time in the Mistral CG path.

---

## 6. Anti-Roadmap: What NOT to Add

| Do not... | Why |
|-----------|-----|
| Promote CSR into live inference first | CSR is a structural cause on the energetic axis, not an operative controller. Its role is to influence Guna during training/governance, not to gate generation. |
| Promote Guna into live inference yet | The energetic axis is less mature than the cognitive axis. Guna is correctly audit-only. Premature promotion would add a second inference control surface without clear benefit. |
| Widen phase-adapter input from 12D Bhava to 32D | The V11.0.0 narrowing to Bhava-only was intentional — control signals belong in the control plane, not phase rotation. Reversing this architectural decision has high risk and no alignment justification. |
| Activate all dormant CG primitive heads at inference | The primitives are training-time scoring mechanisms. Their role is to shape the learned representations, not to re-rank at inference. TwoStageGenerator exists for that purpose but requires separate design review. |
| Force full training/inference symmetry | The agentic/JEPA side uses explicit formulas (CSR→Guna derivation, R[v,a] coupling). The training side uses learned representations. These are different mechanisms serving the same directional semantics. Forcing code-level symmetry would be a category error. |
| Add an ontology live inference gate | Ontology is structurally upstream. It should influence Vritti at training time, not compete with it at inference time. |
| Implement Phase 4 (adaptive feedback / reclassification) | The directional model roadmap explicitly says Phase 4 requires Phase 3 deployed and stable first, plus audit data analysis. There is no justification for reclassification on the Mistral CG side. |
| Couple CSR and Guna scorers at training time | They are architecturally independent learned representations. The agentic-side formula-based CSR→Guna derivation handles the directional semantics. Coupling the training scorers would create a dependency without clear benefit. |

---

## 7. Final Recommendation

The Mistral CG stack is already conceptually aligned with the directional
model on 4 of 5 signals. Bhava is correctly direct. Vritti has a bounded
live gate. Guna is correctly audit-only. CSR is correctly off the live
path. The only genuine alignment gap is that the Ontology → Vritti causal
direction is implicit (via `o_ctx` input to VrittiTokenScorer) rather
than explicit (via a training-time prior). **No inference-side change
beyond the existing Vritti gate is needed now.** The single highest-value
next patch is a soft ontology-derived prior over Vritti contrastive targets
during training — a loss regularizer using the existing R[v,a] matrix,
bounded by a small alpha, with no inference-path impact. This is a
training-only, low-risk, ablatable change that structurally encodes the
directional model's cognitive axis without broadening inference scope.
