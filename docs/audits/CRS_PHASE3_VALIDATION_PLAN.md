# CRS Phase 3: Validation Plan

**Date:** 2026-04-09
**Prerequisite:** Phase 2 implementation complete, unit tests passing
**Purpose:** Concrete plan to validate CRS vs legacy CSR before any long training commitment

---

## A. Validation Matrix

### Recommended experiment modes

| Mode | Flag | Gate | Anchor | Weights | Question it answers |
|------|------|------|--------|---------|-------------------|
| **A: Legacy CSR** | `use_crs_combined_scorer=False` | N/A | N/A | N/A | Baseline. What does training look like without CRS? |
| **B: Full CRS** | `use_crs_combined_scorer=True` | Active (tau_s=0.45, k_s=10) | Active (alpha_base=0.5) | w_c=0.2, w_r=0.2, w_s=0.6 | Does the full CRS doctrine work? Is semantic authority real? |
| **C: CRS no-gate** | Same as B but `crs_semantic_threshold=0.0, crs_gate_sharpness=0.01` | Effectively disabled (S_gate ≈ 0.5 for all) | Active | Same | Is the gate necessary, or does branch separation alone help? |
| **D: CRS no-anchor** | Same as B but `crs_alpha_base=0.0` | Active | Disabled | Same | Does the base-logit anchor matter for S? Does S learn useful signal without it? |

### Why this matrix

- **A vs B** isolates the total CRS effect (all three branches + gate + anchor).
- **B vs C** isolates the gate effect. If B and C behave similarly, the gate isn't intervening meaningfully. If C is worse, the gate is doing real work.
- **B vs D** isolates the anchor effect. If D shows S_gate saturating near 0.5 in early steps (blind gate) while B does not, the anchor is critical for cold-start.

### Modes NOT recommended for Phase 3

- Equal weights (w_c=w_r=w_s=1/3) — changes two things at once (weight balance + removes semantic emphasis). Test this only if B shows weight-related issues.
- Per-branch auxiliary losses — not implemented in Phase 2. Defer until basic CRS is validated.

### Minimum viable matrix

If time is very constrained, run only **A** and **B**. The ablations C and D are optional but highly informative.

---

## B. Short-Run Validation Plan

### Step 0: Prerequisites (5 minutes)

Verify before any training:
1. Unit tests still pass: `python -m pytest tests/test_crs_combined_scorer.py -v`
2. Existing CG test passes: `python scripts/test_cg_phases.py` (if available and runnable)
3. CRS argparse flags are recognized: `python symbolu_training/training/unified/train.py --help | grep crs`

### Step 1: Checkpoint load/save smoke (10 minutes)

**Goal:** Verify old checkpoints load cleanly with CRS code present but flag off.

```bash
# Load existing checkpoint with flag OFF — must work identically
python symbolu_training/training/unified/train.py \
  --model_type mistral_cg \
  --enable_conscious_generation \
  --use_crs_combined_scorer=False \
  --resume <existing_checkpoint> \
  --max_steps 5 \
  --log_every 1
```

**Check:**
- No `unexpected key` or `missing key` errors for CRS-related parameters
- S_tok buffer not mentioned in load warnings (it's (V,0) when disabled)
- Training produces normal CG log lines

Then test save/load round-trip with CRS ON:

```bash
# Train 5 steps with CRS ON, save checkpoint
python symbolu_training/training/unified/train.py \
  --model_type mistral_cg \
  --enable_conscious_generation \
  --use_crs_combined_scorer \
  --max_steps 5 \
  --save_every 5 \
  --checkpoint_dir /tmp/crs_ckpt_test

# Reload that checkpoint
python symbolu_training/training/unified/train.py \
  --model_type mistral_cg \
  --enable_conscious_generation \
  --use_crs_combined_scorer \
  --resume /tmp/crs_ckpt_test/latest.pt \
  --max_steps 3
```

**Check:** No load errors. CRS parameters (`crs_combined_scorer.*`) present in saved state_dict.

### Step 2: Forward-only batch comparison (10 minutes)

**Goal:** Verify CRS produces different column-3 values than CSR for the same input.

Run both modes for 10 steps on identical data. Compare CG log lines:
- Mode A: column-3 is raw CSR (no CRS line in log)
- Mode B: column-3 is CRS combined (CRS diagnostics line printed)

**Check:**
- CRS log line appears: `CRS: C=... R=... S=... Sg=... ovr=...`
- `semantic_override_rate > 0` (CRS is actually changing rankings)
- `S_gate_mean` is not 0.0 or 1.0 (gate is active, not saturated)

### Step 3: Smoke train — 50 steps (15 minutes)

**Goal:** Verify CRS doesn't crash or diverge in actual training.

```bash
# Mode B: Full CRS
python symbolu_training/training/unified/train.py \
  --model_type mistral_cg \
  --enable_conscious_generation \
  --use_crs_combined_scorer \
  --lambda_csr_token 0.005 \
  --max_steps 50 \
  --log_every 5
```

**Check:**
- Loss does not NaN or spike > 10x baseline
- CRS diagnostics printed every log step
- `C_mean`, `R_mean`, `S_mean` are all non-zero and finite
- `S_gate_mean` is in (0.1, 0.9) — not saturated
- No CUDA OOM (S_tok cache adds ~1.6 MB)

### Step 4: Short-run comparison — 300 steps, 4 modes (1-2 hours)

Run all 4 modes (A, B, C, D) for 300 steps each on the same dataset split:

```bash
for MODE in A B C D; do
  # Mode-specific flags (see matrix above)
  python symbolu_training/training/unified/train.py \
    --model_type mistral_cg \
    --enable_conscious_generation \
    [mode-specific flags] \
    --max_steps 300 \
    --log_every 10 \
    --eval_every 100 \
    --checkpoint_dir checkpoints_crs_validation_${MODE} \
    2>&1 | tee logs_crs_validation_${MODE}.txt
done
```

**After runs, compare:**
1. Loss curves (steps 0-300) — any mode diverge?
2. CRS diagnostics at step 50, 150, 300 — are branches separating?
3. S_gate_mean trajectory — does it start reasonable and stay reasonable?
4. semantic_override_rate — does it settle to a non-trivial value?
5. Column-3 scale — how does CRS column-3 mean compare to CSR column-3 mean?

### Step 5: Diagnostic review and decision (30 minutes)

After Step 4, fill in the validation report template (Section G below). Based on the results:

- **All pass:** Proceed to longer validation (1000-5000 steps) with Mode B.
- **Warnings:** Investigate specific issues. May need hyperparameter tuning (tau_s, k_s, alpha_base) before longer run.
- **Any fail:** Stop. Document failure mode. Return to Phase 2 for targeted fix.

---

## C. Metrics to Track

### Must-have (log every step when CRS is active)

| Metric | Source | What it tells you |
|--------|--------|------------------|
| `train_loss` | Training loop | Overall training health — must not diverge |
| `crs_C_mean` | `crs_branch_data['C'].mean()` | C branch is producing signal (not dead) |
| `crs_R_mean` | `crs_branch_data['R'].mean()` | R branch is producing signal (should match legacy CSR scale) |
| `crs_S_mean` | `crs_branch_data['S'].mean()` | S branch is producing signal (not dead, not dominating) |
| `crs_S_prob_mean` | `crs_branch_data['S_prob'].mean()` | Semantic probability distribution — should be in (0.3, 0.8) |
| `crs_S_gate_mean` | `crs_branch_data['S_gate'].mean()` | Gate activation — must not saturate at 0 or 1 |
| `crs_semantic_override_rate` | `(crs_top1 != r_top1).float().mean()` | How often semantic gating changes the top candidate |
| `crs_col3_mean` | `crs_branch_data['crs_score'].mean()` | Column-3 absolute scale (compare to legacy CSR col3 mean) |

### Nice-to-have (log every N steps, or compute offline)

| Metric | How to compute | What it tells you |
|--------|---------------|------------------|
| `crs_C_std`, `crs_R_std`, `crs_S_std` | `.std()` on branch outputs | Branch spread — if std ≈ 0, branch is collapsed |
| `crs_S_bilinear_mean` | Separate `s_bilinear` from `z_base` in compute_S() | Whether learned bilinear is contributing or dominated by anchor |
| `alpha_col3_mean` | Router weight for column 3: `alpha[..., 3].mean()` | How much the router weights the CRS column |
| `crs_vs_csr_col3_corr` | Run both paths, compute Pearson correlation | How different CRS is from legacy CSR for same inputs |
| `branch_correlation_CR` | `corr(C, R)` across candidates | Should be low — C and R should be decorrelated |
| `branch_correlation_CS` | `corr(C, S)` across candidates | Should be low — C and S measure different things |
| `branch_correlation_RS` | `corr(R, S)` across candidates | Should be low — R is phonemic, S is semantic |

### Manual inspection (one-time or periodic)

| What to inspect | How |
|----------------|-----|
| CRS column-3 histogram | Plot distribution of CRS scores at step 50, 150, 300. Compare to legacy CSR histogram. Check for bimodality (gate creating two populations). |
| S_gate distribution | Plot S_gate values across candidates. Should NOT be all-0 or all-1. Healthy: bimodal (gate clearly passing some, blocking others). |
| Top-1 divergence examples | Sample 10 positions where `crs_top1 != r_top1`. Inspect which token CRS preferred vs R. Verify semantic gating makes intuitive sense. |
| Router weight adaptation | Plot alpha[3] over 300 steps. If it drops to near-zero, the router is learning to ignore CRS. If it spikes, CRS scale is dominating. |

---

## D. Success Criteria

### Pass (green light for longer runs)

| Criterion | Threshold |
|-----------|-----------|
| Legacy path loads and runs | No errors when `use_crs_combined_scorer=False` with CRS code present |
| CRS path runs | No crashes, NaN, or OOM through 300 steps |
| Loss stability | CRS mode loss within 1.5x of legacy mode loss at step 300 |
| Branches alive | `C_mean`, `R_mean`, `S_mean` all have abs > 0.01 and std > 0.005 at step 300 |
| Gate not saturated | `S_gate_mean` ∈ (0.15, 0.85) at step 300 |
| Semantic intervention real | `semantic_override_rate` ∈ (0.05, 0.60) at step 300 |
| S_prob reasonable | `S_prob_mean` ∈ (0.3, 0.8) at step 300 |
| Checkpoint round-trip | Save at step 300, reload, continue 10 steps — no errors |

### Warning (investigate before longer run)

| Criterion | Threshold |
|-----------|-----------|
| Loss elevation | CRS loss is 1.5x–2.0x legacy at step 300 |
| Gate near saturation | `S_gate_mean` < 0.15 OR > 0.85 at step 300 |
| Override rate extreme | `semantic_override_rate` < 0.05 OR > 0.60 at step 300 |
| One branch dominates | One of C/R/S has mean > 5x the others |
| Column-3 scale mismatch | CRS col3_mean is > 10x or < 0.1x legacy CSR col3_mean |
| Router avoids CRS | alpha[3] < 0.05 (router learns to ignore column 3) |
| S_prob near constant | `S_prob_std` < 0.02 (S is not discriminating between candidates) |

### Fail (stop, fix before proceeding)

| Criterion | Threshold |
|-----------|-----------|
| Training diverges | Loss NaN or > 5x baseline within 100 steps |
| Gate fully dead | `S_gate_mean` < 0.01 or > 0.99 after step 50 |
| Branch dead | Any of C/R/S has `abs(mean) < 0.001` AND `std < 0.001` after step 100 |
| Override rate zero | `semantic_override_rate` = 0.0 after step 100 (CRS = pure R) |
| Checkpoint corruption | CRS checkpoint fails to reload |
| Legacy path broken | `use_crs_combined_scorer=False` produces different results than pre-Phase-2 code |

---

## E. Failure Signatures

### 1. CRS is just CSR with extra computation (not real CRS)

**Symptoms:**
- `semantic_override_rate ≈ 0.0` — gate never changes top-1 vs pure R
- `S_gate_mean ≈ 1.0` — gate is fully open, never intervening
- Column-3 values ≈ R values (high correlation, > 0.95)
- `C_mean ≈ 0.0` — cognitive branch contributes nothing due to small-init bilinear

**Root cause:** Gate threshold too low, or S bilinear not learning, or w_s too low to matter.

### 2. Semantic gate kills everything (over-suppression)

**Symptoms:**
- `S_gate_mean < 0.1` — gate blocks nearly all candidates
- `crs_col3_mean` is near zero or negative
- Training loss spikes — model can't score any candidate well
- Router learns alpha[3] → 0 to compensate (ignoring CRS entirely)

**Root cause:** S has poor signal at init (anchor too weak, or bilinear init too aggressive with wrong sign), pushing S_prob below threshold for most candidates.

### 3. S branch collapses into base logits

**Symptoms:**
- `corr(S_raw, base_logits_cand)` stays > 0.9 after 200+ steps
- S_bilinear component stays near zero (anchor dominates)
- `S_prob_mean` tracks base-logit-derived values closely
- S_gate behavior purely reflects base logit ranking

**Root cause:** alpha_base too high (> 0.7), or bilinear learning rate too low, or S_tok projections not receiving gradient.

### 4. Branch scale explosion

**Symptoms:**
- One branch's `abs(mean)` grows > 100x the others over 200 steps
- CRS score oscillates wildly
- Loss instability correlated with CRS diagnostic spikes
- Gradient norms for CRS parameters spike in CG-GRAD log

**Root cause:** Branch weights not normalizing effectively. Raw bilinear scores can grow unbounded during training. May need branch-level gradient clipping or score normalization.

### 5. C branch is permanently dead

**Symptoms:**
- `C_mean ≈ 0.0`, `C_std ≈ 0.0` at all steps
- Removing C (setting w_c=0) produces identical behavior
- A_C / B_C gradient norms near zero

**Root cause:** 10D bilinear with rank 4 and gain=0.3 init may be too small. V_tok and Kosha slices (both softmax-normalized to sum-to-1) have small magnitudes — their dot products through M_C may be vanishingly small. May need higher init gain or larger rank.

### 6. Checkpoint key mismatch

**Symptoms:**
- `RuntimeError: unexpected key 'conscious_gen.crs_combined_scorer.A_C'` when loading CRS checkpoint into non-CRS config
- `RuntimeError: missing key 'conscious_gen.token_cache.S_tok'` when loading old checkpoint into CRS config with strict=True

**Root cause:** Checkpoint saved with CRS enabled, loaded with CRS disabled (or vice versa). Requires `strict=False` loading or explicit key filtering.

---

## F. Recommended Execution Order

1. **Unit tests** — Run `pytest tests/test_crs_combined_scorer.py -v`. Must pass. (2 min)

2. **Argparse check** — Verify `python train.py --help | grep crs` shows all 8 CRS flags. (1 min)

3. **Checkpoint load test (flag off)** — Load existing checkpoint with CRS code present but `use_crs_combined_scorer=False`. Run 5 steps. Verify no errors, no behavior change. (5 min)

4. **Checkpoint round-trip (flag on)** — Train 5 steps with CRS on, save, reload, train 3 more steps. Verify no key errors. (5 min)

5. **Smoke train 50 steps (Mode B)** — Full CRS enabled. Verify: CRS diagnostics appear, loss doesn't diverge, branches are alive, gate is active. (15 min)

6. **Short comparison 300 steps (Mode A vs B)** — Run both modes on same data. Compare loss curves, diagnostics, column-3 scale. (30-60 min)

7. **Diagnostic review** — Fill in validation report template. Evaluate pass/warning/fail. (30 min)

8. **Optional ablations (Modes C, D)** — If Mode B passes, run no-gate and no-anchor ablations for 300 steps each. Compare to Mode B to isolate gate and anchor effects. (30-60 min)

9. **Decision gate** — Based on report: proceed to 1000+ step run, or return to fix issues.

---

## G. Validation Report Template

```
================================================================
CRS VALIDATION REPORT
================================================================
Date:        ____-__-__
Commit:      ________
Dataset:     ________
Base model:  ________

================================================================
MODE A: Legacy CSR (baseline)
================================================================
Steps run:              ___
Loss (start → end):     ___.__ → ___.__
PPL (if available):     ___.__ → ___.__
Col3 mean (step 300):   ___.__
Col3 std (step 300):    ___.__
Notes:                  ________

================================================================
MODE B: Full CRS
================================================================
Steps run:              ___
Loss (start → end):     ___.__ → ___.__
PPL (if available):     ___.__ → ___.__

Branch diagnostics (step 300):
  C_mean:               ___.__
  C_std:                ___.__
  R_mean:               ___.__
  R_std:                ___.__
  S_mean:               ___.__
  S_std:                ___.__

Gate diagnostics (step 300):
  S_prob_mean:          ___.__
  S_gate_mean:          ___.__
  S_gate_std:           ___.__

Integration (step 300):
  Col3 mean:            ___.__
  Col3 std:             ___.__
  semantic_override_rate: ___.__
  alpha[3] mean:        ___.__

Checkpoint test:        PASS / FAIL
Notes:                  ________

================================================================
MODE C: CRS no-gate (optional)
================================================================
Steps run:              ___
Loss (start → end):     ___.__ → ___.__
S_gate_mean:            ___.__ (should be ≈ 0.5)
semantic_override_rate: ___.__
Notes:                  ________

================================================================
MODE D: CRS no-anchor (optional)
================================================================
Steps run:              ___
Loss (start → end):     ___.__ → ___.__
S_gate_mean (step 10):  ___.__ (cold-start quality)
S_gate_mean (step 300): ___.__
Notes:                  ________

================================================================
VERDICT
================================================================
Legacy path intact:     PASS / FAIL
CRS runs cleanly:       PASS / FAIL
Branches alive:         PASS / WARNING / FAIL
Gate active:            PASS / WARNING / FAIL
Override meaningful:    PASS / WARNING / FAIL
Loss stability:         PASS / WARNING / FAIL
Scale compatibility:    PASS / WARNING / FAIL

RECOMMENDATION:         PROCEED / TUNE / FIX / ABORT

Issues found:           ________
Next steps:             ________
================================================================
```

---

*End of Phase 3 validation plan. Run in the order specified in Section F.*
