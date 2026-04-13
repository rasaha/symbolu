# State Projector Readiness Audit

## Executive Summary

**The state projector is near-initialization because it receives effectively
zero gradient signal during training.** This is not a bug in any single
component — it is a structural gap where no CG loss directly supervises the
32D state output of the projector.

Root cause breakdown:
1. **No CG loss directly supervises the state projector output.** Every CG
   loss supervises downstream modules (token projector, primitive scorers,
   routers, gates) — not the state itself.
2. **Phase 3 (default) explicitly detaches the sovereign state** before
   passing it to governance integration and primitive aux losses, blocking
   gradient flow back to the projector.
3. **The only indirect path** — the ontology-vritti prior — supervises v_ctx
   (the Vritti scorer's context representation), not the state. Gradients
   from the prior flow through bhava→R^T→prior→KL but the KL loss
   backpropagates to v_ctx, with only a weak second-order path to state.
4. **The phase adapter path** (state → delta_bhava → intent_phase → adapter_output
   → hidden + gate*adapter) does connect state to the LM loss, but this path
   is gated by `adapter_gate` which starts near zero (sigmoid(0)=0.5, then
   multiplied by a near-zero adapter output), making the gradient negligible.

**This is a wiring/architecture issue, not a training-duration issue.**
Training longer with the current setup will not meaningfully improve the
state projector.

---

## Projector-Readiness Matrix

| Area | Status | Evidence | Risk |
|------|--------|----------|------|
| Projector trainable | OK | Not in backbone freeze loop (wrapper.py:87-89). `requires_grad=True` by default. | None |
| In optimizer | OK | Included in main param group at base LR (train.py:1492-1494). No separate group. | None |
| Gradients reach projector | **BLOCKED** | Phase 3 detaches `_cg_sov_state` at lines 5006-5007 and 5185-5186. Phase 4 (live gradients) requires `use_field_integrated_softmax=True`, which is not in the training script. | **Critical** |
| CG losses enabled | Partial | Training script sets λ_ont=0.01, λ_vritti=0.005, λ_guna=0.005, etc. But config defaults are all 0.0. | Medium |
| CG losses supervise state | **NO** | All losses supervise token projector, scorers, router, or gate — not the state projector. See loss-by-loss audit below. | **Critical** |
| Loss strength adequate | **N/A** | Even if losses were strong, they don't reach the projector. | Critical |
| Phase adapter gradient | Weak | adapter_gate starts near zero; adapter_output is tiny; LM gradient through this path is negligible. | High |
| Checkpoint maturity | Unknown | No step count in available metadata. Script targets 50K steps. | Medium |
| Logging/observability | Gap | No metric tracks state projector gradient norm, state distribution entropy, or state activation statistics. | Medium |

---

## Loss-by-Loss Audit

### Losses that exist and are enabled in training script

| Loss | Lambda | Supervises | Gradients to state_projector? | Why/why not |
|------|--------|------------|-------------------------------|-------------|
| OntologicalStructureLoss | 0.01 | TokenOntologyProjector (e_w → o_w) | **NO** | Trains token projector, completely separate module from state projector |
| PrimitiveAuxLoss (vritti) | 0.005 | VrittiTokenScorer | **NO (Phase 3)** | T tensor built with detached state in Phase 3 (line 5185-5186) |
| PrimitiveAuxLoss (guna) | 0.005 | GunaTokenScorer | **NO (Phase 3)** | Same: detached state blocks gradient |
| PrimitiveAuxLoss (jepa) | 0.005 | PlausibilityTokenScorer | **NO (Phase 3)** | Same: detached state |
| PrimitiveAuxLoss (csr) | 0.005 | CSRTokenScorer | **NO (Phase 3)** | Same: detached state |
| KoshaRoutingLoss | 0.01 | KoshaPrimitiveRouter | **NO** | Loss on router alpha, not state; also detached in Phase 3 |
| BlissCoherenceLoss | 0.01 | BlissTokenGate | **NO** | Loss on B(w) and D(w), not state |

### Losses that exist but are disabled (lambda=0.0 at default, not in training script)

| Loss | Default Lambda | Would supervise state_projector? |
|------|---------------|----------------------------------|
| OntologyVrittiPrior | 0.0 | **Weak indirect only** — KL(v_ctx \|\| softmax(bhava @ R^T)). Gradients primarily to v_ctx. Bhava path exists but is second-order through log(prior). |
| Vritti entropy reg | disabled | Would regularize vritti distribution entropy, not projector directly |

---

## Gradient Flow Path Analysis

### Path 1: CG losses → state projector (BLOCKED in Phase 3)

```
CG Loss (vritti/guna/kosha/bliss)
  ↑
Primitive scorers / router / gate
  ↑
Token Evaluation Tensor (T)
  ↑
_cg_sov_state.detach()    ← GRADIENT BLOCKED HERE (train.py:5006-5007, 5185-5186)
  ↑
outputs['state']
  ↑
state_projector(pooled_hidden)
  ↑
SovereignStateProjector weights    ← NEVER RECEIVES CG GRADIENTS
```

### Path 2: Phase adapter → LM loss → state projector (WEAK)

```
LM Cross-Entropy Loss
  ↑
logits = backbone.lm_head(hidden + gate * adapter_output)
  ↑                                    ↑
backbone (frozen, no grad)       adapter_output = phase_adapter(intent_phase)
                                       ↑
                                  intent_phase = intent_projector(delta_bhava)
                                       ↑
                                  delta_bhava = bhava - prev_bhava.detach()
                                       ↑
                                  state_projector(pooled_hidden)
```

This path IS live — gradients can flow from LM loss → adapter_output → 
intent_projector → delta_bhava → state_projector. BUT:
- `adapter_gate` is initialized to produce sigmoid(0)=0.5
- `adapter_output` from near-init phase_adapter is tiny
- The product `gate * adapter_output` contributes negligibly to logits
- LM loss gradient through this path is orders of magnitude smaller than direct backbone gradient (which is frozen anyway)
- This path teaches the projector to produce bhava that helps the adapter help the LM head — a very indirect, weak signal

### Path 3: Ontology-Vritti Prior (NOT ENABLED, and weak even if enabled)

```
KL(v_ctx || prior)
  ↑              ↑
v_ctx          prior = softmax(bhava @ R_T / tau)
  ↑              ↑
VrittiScorer   state[0:12] (bhava slice)
               ↑
          state_projector
```

When enabled (`lambda_vritti_ontology_prior > 0`), gradients DO flow to
the state through the bhava→prior path. But:
- The KL divergence `F.kl_div(log_prior, v_ctx)` differentiates primarily
  w.r.t. the first argument (log_prior), not the target (v_ctx)
- `log_prior = log(softmax(bhava @ R_T))` — gradient flows through log,
  softmax, matmul to bhava, then through the state projector
- This IS a valid gradient path, but it's disabled by default (lambda=0.0)
  and not included in the training script

---

## Top Causes (Ranked)

### 1. **CRITICAL: Phase 3 detaches sovereign state from CG losses**
- File: `train.py:5006-5007, 5185-5186`
- `_cg_sov_state.detach()` explicitly cuts gradient flow from all CG losses
  back to the state projector
- This is the single biggest reason the projector stays near-init
- Phase 4 (`use_field_integrated_softmax=True`) removes this detach, but
  Phase 4 is NOT enabled in the training script

### 2. **CRITICAL: No CG loss directly supervises the state**
- All CG losses supervise downstream modules (token projector, scorers, router, gate)
- Even without the Phase 3 detach, the gradient path from CG losses to the
  state projector is indirect (through scorers that take state as input)
- There is no "state reconstruction loss", "state prediction loss", or
  "state alignment loss" that directly compares the 32D state to a target

### 3. **HIGH: Phase adapter gradient path is too weak**
- The only live gradient path to the projector is: LM loss → adapter → 
  intent_projector → delta_bhava → state
- But adapter_gate and adapter_output are near-zero at init, making this
  gradient negligible
- This is a chicken-and-egg problem: the adapter needs meaningful state to
  produce useful corrections, but the state needs meaningful adapter gradients
  to learn

### 4. **MEDIUM: Ontology-Vritti prior is not enabled**
- `lambda_vritti_ontology_prior=0.0` in both default config and training script
- This is the only loss that would provide a (weak) direct gradient to the
  state's bhava slice
- Even if enabled, it only supervises bhava [0:12], not vritti [17:22] or
  guna [22:28] directly

### 5. **LOW: Logging gap**
- No metrics track state projector gradient norms
- No metrics track state distribution entropy or activation statistics
- This means the near-init problem was invisible during training

---

## Recommended Next Action

**Enable Phase 4 gradient flow for the state projector by removing the
`.detach()` on `_cg_sov_state` in the Phase 3 path.**

Specifically, in `train.py` lines 5004-5010, change:

```python
# CURRENT (Phase 3 — detached):
_cg_integ_result = _cg_integ(
    T=_cg_T,
    hidden=_cg_hidden.detach(),
    o_ctx=_cg_sov_state.detach(),     # ← blocks gradient to state_projector
    ...
)
```

to:

```python
# PROPOSED: Keep state live for gradient flow, detach only hidden
_cg_integ_result = _cg_integ(
    T=_cg_T,
    hidden=_cg_hidden.detach(),
    o_ctx=_cg_sov_state,              # ← live gradient to state_projector
    ...
)
```

And similarly at line 5186.

**Why this specific change:**
- It is the minimum change to unblock gradient flow
- It preserves the hidden detach (frozen backbone anyway)
- It lets CG losses (kosha routing, bliss, primitive aux) flow back through
  the scorers/router to the state projector
- The training script already enables CG losses at reasonable lambdas (0.005-0.01)
- No new loss modules or architecture changes needed

**Secondary recommendation:** Also enable `lambda_vritti_ontology_prior=0.01`
in the training script to provide direct bhava supervision.

**Tertiary recommendation:** Add state projector gradient norm logging to
detect this class of issue in future training runs.

---

## What NOT to Do

- Do NOT lower inference gate thresholds — the gates are correct
- Do NOT add more losses without first unblocking the gradient path
- Do NOT switch to Phase 4 (field-integrated softmax) — that is a larger
  architectural change with different training dynamics
- Do NOT increase training duration without fixing gradient flow — it will
  not help with zero gradients
