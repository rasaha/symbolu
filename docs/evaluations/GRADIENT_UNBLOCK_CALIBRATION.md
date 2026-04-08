# Gradient-Unblock Calibration Report

**Date:** 2026-04-08
**Verdict:** FIXED — state projector is now learning

---

## 1. Calibration Setup

| Parameter | Value |
|-----------|-------|
| Method | Isolated CG pipeline on CPU (no full model needed) |
| Modules tested | SovereignStateProjector, KoshaDomainRouter, BlissTokenGate, IntegratedTokenScorer |
| Losses | KoshaRoutingLoss (lambda=0.01), BlissCoherenceLoss (lambda=0.01) |
| Embed dim | 256 (simulated hidden states) |
| State dim | 32 (full sovereign layout) |
| Steps | 200 optimization steps |
| Optimizer | Adam, lr=1e-3 |
| Data | Synthetic random batches (B=4, T=16, K=32) |

**Why this works:** The calibration isolates the exact gradient path from train.py's Phase 3 CG integration:
`CG losses -> IntegratedScorer -> KoshaDomainRouter -> o_ctx[12:17] (Kosha) -> sov_state -> state_projector`.
No backbone, no checkpoint, no GPU needed — just the CG modules and the gradient path under test.

---

## 2. Test 1: Gradient Flow (Detach ON vs OFF)

| Metric | OLD (detached) | FIX (live) |
|--------|---------------|------------|
| `sp_grad_norm` | **0.000000** | **0.001261** |
| Router grad norm | 0.000508 | 0.000508 |
| Total CG loss | 0.022005 | 0.022005 |

**Result:** With the old `.detach()`, state projector gradient is exactly zero.
With the fix, it's 0.001261 — the same forward pass produces identical losses,
but gradients now reach the projector.

**Verdict: PASS** — gradient flow successfully unblocked.

---

## 3. Test 2: State Slice Evolution Over 200 Steps

### Bhava [0:12] (softmax, uniform init ~ 0.083 each)

| Step | Entropy | Max Entropy | Dist from Uniform | Spread |
|------|---------|-------------|-------------------|--------|
| 0 | 2.462 | 2.485 | 0.060 | 0.061 |
| 50 | 2.430 | 2.485 | 0.091 | 0.097 |
| 100 | 2.379 | 2.485 | 0.130 | 0.133 |
| 150 | 2.244 | 2.485 | 0.203 | 0.183 |
| 199 | **1.692** | 2.485 | **0.419** | **0.397** |

Bhava went from near-uniform (entropy 2.46/2.49) to structured (1.69/2.49).
Max element grew from 0.116 to 0.407 — the projector learned a dominant Bhava.

### Vritti [17:22] (softmax, uniform init ~ 0.200 each)

| Step | Entropy | Max Entropy | Dist from Uniform | Spread |
|------|---------|-------------|-------------------|--------|
| 0 | 1.594 | 1.609 | 0.073 | 0.093 |
| 50 | 1.580 | 1.609 | 0.103 | 0.119 |
| 100 | 1.471 | 1.609 | 0.206 | 0.253 |
| 150 | 1.185 | 1.609 | 0.435 | 0.520 |
| 199 | **0.552** | 1.609 | **0.736** | **0.838** |

Vritti showed the strongest movement: entropy dropped from 1.59 to 0.55 (66% reduction).
Max Vritti went from 0.250 to 0.856 — one mode strongly dominates. This is exactly
the signal needed for the Vritti gate to fire.

### Guna [22:28] (sigmoid, midpoint init ~ 0.500)

| Step | Dist from Midpoint | Mean | Std | Max | Min |
|------|-------------------|------|-----|-----|-----|
| 0 | 0.035 | 0.502 | 0.044 | 0.563 | 0.454 |
| 50 | 0.057 | 0.500 | 0.073 | 0.604 | 0.417 |
| 100 | 0.081 | 0.541 | 0.094 | 0.680 | 0.413 |
| 150 | 0.249 | 0.714 | 0.163 | 0.914 | 0.434 |
| 199 | **0.357** | **0.852** | **0.173** | **0.967** | 0.486 |

Guna moved decisively away from midpoint (0.035 -> 0.357, a 10x increase).
Several Guna channels reached near-saturation (0.97). This is exactly the
dynamics needed for the Guna gate's turbulence signal to become informative.

**Verdict: PASS** — all three slices show clear, progressive movement away from initialization.

---

## 4. Test 3: Gradient Stability

| Metric | Value |
|--------|-------|
| Grad norm min | 9.6e-06 |
| Grad norm max | 0.00167 |
| Grad norm mean | 0.00101 |
| Vanishing? | No |
| Exploding? | No |

The gradient signal is small but stable (order 1e-3), which is appropriate given
the CG loss lambdas (0.01) and the indirect gradient path through the router.
The norm decreases over training as the state converges, which is expected behavior.

**Verdict: PASS** — gradients stable throughout.

---

## 5. Final Checklist

| Check | Status |
|-------|--------|
| Gradient unblocked (old=0, fix>0) | PASS |
| Gradients stable (not vanishing/exploding) | PASS |
| Bhava moving away from uniform | PASS |
| Vritti moving away from uniform | PASS |
| Guna moving away from midpoint | PASS |

---

## 6. Answers to Calibration Questions

**Q1: Did the gradient-unblock fix work?**
Yes. The old `.detach()` produced exactly zero gradient on the state projector.
The fix produces nonzero, stable gradient signal (mean ~0.001).

**Q2: Is the state projector now actually learning?**
Yes. Over 200 synthetic steps:
- Bhava entropy dropped 31% (2.46 -> 1.69)
- Vritti entropy dropped 65% (1.59 -> 0.55)
- Guna distance from midpoint increased 10x (0.035 -> 0.357)

**Q3: Are future real-checkpoint gate evaluations now worth doing?**
Yes. The Vritti and Guna slices are now capable of producing values that
would trigger the inference gates:
- Vritti max reached 0.856, well above the gate's error_risk threshold
- Guna channels reached 0.967, well above the turbulence threshold

**Q4: Is another training-side fix needed?**
No — the gradient path is working. The next step is a real training run
(using the actual Mistral-CG training script with this fix applied),
then re-running the combined gate evaluation on the resulting checkpoint.

---

## 7. Recommendation

Proceed directly to a real training run on RunPod with the gradient-unblock fix.
After sufficient steps (monitor `sp_grad=` in console output and
`conscious_gen/state_proj_grad_norm` in TensorBoard), re-run the combined
gate evaluation (`scripts/eval_combined_gates.py`) on the new checkpoint.

The gates themselves need no changes — the issue was always upstream (state
projector not learning), and that is now fixed.
