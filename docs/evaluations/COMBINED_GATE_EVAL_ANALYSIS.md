# Combined Gate Evaluation Analysis

**Date:** 2026-04-08
**Checkpoint:** `/workspace/symbolu/checkpoints_mistral_cg/best_model.pt`
**GPU:** NVIDIA A100 80GB PCIe
**Quantize:** 4bit | **Temp:** 0.7 | **Max tokens:** 256
**Prompts:** 15 | **Modes:** 4 (baseline, Vritti, Guna, both)

## Executive Summary

Neither gate fired. Not once, across 60 generations (15 prompts x 4 modes).
The state projector is near-initialization and produces near-uniform Vritti
distributions and sigmoid-midpoint Guna values. The gates are correctly
implemented but the signal they read is not yet meaningful.

**Decision: Outcome D — No meaningful value from gates at current checkpoint quality.**

## Q1: Are the gates alive?

**No.** Zero firings across all modes and categories.

| Mode | V-Fires | G-Fires | V-Rate | G-Rate |
|------|---------|---------|--------|--------|
| A_baseline | 0 | 0 | 0% | 0% |
| B_vritti_only | 0 | 0 | 0% | 0% |
| C_guna_only | 0 | 0 | 0% | 0% |
| D_both_gates | 0 | 0 | 0% | 0% |

### Root cause: state projector is near-initialization

Manual application of the trained state_projector to random hidden vectors:

| Sample | Vritti (softmax) | error_risk | Guna (sigmoid) | turbulence |
|--------|-----------------|------------|----------------|------------|
| 0 | [0.17, 0.23, 0.14, 0.25, 0.21] | 0.27 | [0.50, 0.54, 0.47, 0.48, 0.47, 0.42] | 0.50 |
| 1 | [0.18, 0.18, 0.15, 0.30, 0.19] | 0.23 | [0.38, 0.51, 0.51, 0.48, 0.42, 0.49] | 0.48 |
| 2 | [0.19, 0.17, 0.27, 0.19, 0.19] | 0.25 | [0.44, 0.55, 0.56, 0.48, 0.60, 0.53] | 0.54 |

**Vritti:** Near-uniform (perfect uniform = 0.20 each). No cognitive mode
dominates. The error_risk formula (`vritti[1] + 0.3 * vritti[2]`) produces
~0.23-0.27, well below the 0.5 threshold.

**Guna:** All sigmoid values cluster in [0.38, 0.60] — the midpoint region
that sigmoid produces when raw inputs are near zero. The turbulence formula
produces ~0.48-0.54, just below the 0.6 threshold.

**Weight statistics:**
- `projector.0.weight`: std=0.009 (near Xavier init ~0.016)
- `projector.3.weight`: std=0.022 (near Xavier init ~0.044)
- Layer norm: weight~1.0, bias~0.0 (default init)

The projector has moved slightly from initialization but not enough to
produce differentiated signals.

## Q2: Does either gate help more than it harms?

**Moot.** Neither gate ever activated, so output is identical across all
4 modes. Average output length is 947.8 characters in all modes.

## Q3: Do the two gates compose safely?

**Moot.** No interaction occurred (overlap rate = 0%).

## Q4: Which gate carries value?

**Neither.** Both read the same near-uniform state projector output.

Note: the Guna turbulence values (0.48-0.54) are closer to their threshold
(0.6) than the Vritti error_risk values (0.23-0.27) are to theirs (0.5).
If the projector trains further, Guna may fire first.

## Q5: Agentic integration?

**No.** Gate events are empty. No interpretive value.

## Decision

**Outcome D — No meaningful value.**

The gate implementation is correct (validated by 26 unit tests). The issue
is upstream: the state projector has not been trained enough to produce
differentiated Vritti/Guna signals.

## Single Follow-Up Action

**Keep as-is.** No threshold tweak or gate redesign is warranted.

Rationale:
- The gates cannot be meaningfully evaluated until the state projector
  produces differentiated signals
- Lowering thresholds would be calibrating to noise
- The gate logic is sound and will activate automatically once the
  projector learns to distinguish cognitive/energetic states
- Training the state projector further is the correct next step, not
  modifying inference-side gates

## What Would Make the Gates Fireable

For the Vritti gate to fire, the projector needs to produce Vritti
distributions where ERROR > 0.35 (so `error_risk = 0.35 + 0.3*IMAG > 0.5`).
Currently ERROR hovers at ~0.18-0.23.

For the Guna gate to fire, the projector needs ACTIVITY, VELOCITY, or ACCEL
sigmoid values > 0.7 (so the weighted sum crosses 0.6). Currently they
hover at ~0.42-0.60.

Both require the state projector to train further — specifically, the
CG training losses (ontological structure, primitive scoring, governance)
need to push the projector away from near-uniform output.

## Recommendations for Training

1. Check that the ontological/primitive losses are actually backpropagating
   through the state projector (gradient flow)
2. Consider increasing `lambda_ont` or primitive loss weights if they are
   too small relative to the LM loss
3. Verify that training ran long enough for CG modules to converge
   (the near-init weights suggest early stopping or very low learning rate
   on CG modules)
4. After more training, re-run this same eval harness — no code changes needed

## Anti-Recommendations

Do NOT:
- Lower gate thresholds to force firing on near-uniform signals
- Enable gates by default
- Integrate gates into agentic governance
- Add complexity to the gate logic
- Interpret the current zero-firing as a gate design flaw
