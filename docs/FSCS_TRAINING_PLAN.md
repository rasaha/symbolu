# Text-FSCS §5.5 First Experiment — Alignment-Loss Training Plan

**Date:** 2026-04-11
**Session branch:** `claude/vc-pitch-document-LBYcN`
**Status:** Script implemented and CPU-smoke-tested. **NOT YET run against real Mistral weights.**
**Predecessor measurement:** `docs/FSCS_RSTAR_FIRST_MEASUREMENT.md` (frozen-backbone `r* = 8%`)

---

## Why this experiment exists

The frozen-backbone measurement established that Text-FSCS on
Mistral-7B preserves quality up to `gate_frac ≈ 8%` at the 0.5%
PPL bar and collapses non-linearly above that. The spec §5.4 ablation
row "No alignment loss" predicts this exact behavior: with an
untrained coarse branch, `r*` drops dramatically because the coarse
branch's outputs diverge from what the full branch would produce.

The spec's §5.5 "Recommended First Experiment" prescribes the
opposite configuration — *alignment loss active, coarse branch
trainable, short fine-tune* — and predicts `r*` should rise into
the 15–30% range. This document describes how to run that experiment.

---

## What is now implemented

| Piece | File | Status |
|---|---|---|
| `FSCSCoarseAdapter` — small trainable residual on top of the coarse branch | `symbolu/fscs/core.py` | ✅ Implemented, 4 smoke tests pass |
| Adapter wiring in `FSCSGatedDecoderLayer.forward` | `symbolu/fscs/mistral_gated_layer.py` | ✅ Gated on `cfg.use_coarse_adapter`, default off |
| Per-layer alignment loss accumulation | `FSCSGatedDecoderLayer.get_alignment_loss()` | ✅ Called by the training loop |
| `_sync_fscs_device` handles the adapter | `symbolu_training/training/unified/mistral_fscs_wrapper.py` | ✅ Casts to float32 |
| `FSCSConfig.use_coarse_adapter` + `coarse_adapter_d_inner` | `symbolu/fscs/core.py` | ✅ Defaults to False / 256 |
| Training script | `scripts/train_fscs_alignment.py` | ✅ CLI + real training loop + smoke-test path |
| Smoke test (CPU, 5 steps, synthetic data) | `--smoke-test` flag on the training script | ✅ Passes, proves adapter + loss + optimizer cycle works |
| Adapter-specific unit tests | `tests/test_fscs_core.py::TestCoarseAdapter` | ✅ 4/4 pass, including 10-step training-reduces-loss test |

## Training loop, step by step

1. Load `mistralai/Mistral-7B-v0.3` in bf16 via `MistralFSCSWrapper`
   with `use_coarse_adapter=True`
2. Freeze all 7.25B backbone parameters (`requires_grad=False`)
3. Collect trainable parameters:
   - Per-layer coarse adapter: `LayerNorm → Linear(4096→256) → GELU → Linear(256→4096) + sigmoid-gated residual`
   - Per-layer adapter count: ~2.1M params
   - Across 32 decoder layers: ~67M total trainable params
   - Optional: per-band `τ` and `α` in routing gate (64 params)
4. Initialize AdamW optimizer on trainable params only
5. Load WikiText-103 train split, tokenize to fixed-length chunks
6. Training loop (default 1000 steps):
   - Sample `batch_size` sequences from the tokenized corpus
   - Forward pass through the FSCS-wrapped Mistral — the
     `FSCSGatedDecoderLayer` computes both the full branch and
     the adapted coarse branch, and stores the alignment loss
   - Aggregate the alignment losses across all 32 layers into a
     single scalar
   - Backward → clip → optimizer step
   - Log every `log_every` steps, checkpoint every `save_every`
7. Save final checkpoint (trainable params + optimizer state + metrics
   history + args), write to `results/fscs_alignment/ckpt_latest.pt`

Nothing else is trained. No CE loss. No backbone fine-tune. The
only gradient signal is the alignment loss.

## Recommended invocation

```bash
cd /workspace/symbolu
git checkout claude/vc-pitch-document-LBYcN

# Step 0: verify the CPU smoke test passes
python3 -m pytest tests/test_fscs_core.py::TestCoarseAdapter -v

# Step 1: run the training-script smoke test (no Mistral, ~5s)
python3 scripts/train_fscs_alignment.py --smoke-test

# Step 2: short training run on Mistral (60-120 min on A100-80GB)
python3 scripts/train_fscs_alignment.py \
    --model mistralai/Mistral-7B-v0.3 \
    --quantize bf16 \
    --dataset wikitext103 \
    --seq-len 1024 \
    --batch-size 4 \
    --learning-rate 1e-4 \
    --max-steps 500 \
    --warmup-steps 50 \
    --coarse-window 1024 \
    --coarse-adapter-d-inner 256 \
    --alignment-lambda 1.0 \
    --checkpoint-out results/fscs_alignment/ckpt_step500.pt \
    --log-every 25 \
    --save-every 250

# Step 3 (manual, next session): re-run the r* sweep against the
# checkpoint. Requires a small wrapper modification in r_star_sweep.py
# to load the trainable-parameters checkpoint before the sweep.
# See "Post-training r* re-measurement" below.
```

Estimated wall-clock for Step 2:

| max_steps | batch_size | seq_len | Est. A100-80GB time |
|---|---|---|---|
| 200 | 4 | 1024 | ~25–35 min |
| 500 | 4 | 1024 | ~60–90 min |
| 1000 | 4 | 1024 | ~2–3 hours |
| 2000 | 4 | 1024 | ~4–6 hours |

The dominant per-step cost is the dual-branch forward through Mistral
(same as the r\* sweep), plus gradient computation through the ~67M
adapter parameters (cheap relative to the forward). Memory budget
should be similar to the sweep at batch=16 (~26 GB observed) since
training at batch=4 uses less activation memory than inference at
batch=16.

## Post-training `r*` re-measurement

The training script saves only the trainable params. To re-run the
`r*` sweep against the trained checkpoint:

1. **The quick way:** modify `scripts/r_star_sweep.py` to add a
   `--load-fscs-checkpoint PATH` flag that, after constructing the
   `MistralFSCSWrapper`, loads the checkpoint's `trainable_state_dict`
   into the matching layers. This is a ~20-line addition. **Not yet
   written** — it is the other deliverable the next session should
   produce.

2. **Run the sweep:**
   ```bash
   python3 scripts/r_star_sweep.py \
       --model mistralai/Mistral-7B-v0.3 --quantize bf16 \
       --eval-dataset wikitext2 --seq-len 2048 --max-eval-samples 64 \
       --coarse-window 1024 --eval-batch-size 16 --soft-only \
       --tau-sweep 0.9 0.7 0.5 0.3 0.2 0.1 \
       --load-fscs-checkpoint results/fscs_alignment/ckpt_step500.pt \
       --output results/fscs_rstar/v4_co_trained.json
   ```

3. **Compare:** read `r_star` and the `gate_fraction` column side-by-
   side with `v3_audited.json`. The spec predicts `r*` should rise
   from 8% to 15–30%.

## What success looks like

One of four outcomes, in rough order of likelihood:

### Outcome A — Spec prediction confirmed (target)

`r*` rises from ~8% to somewhere between 15% and 30%, with the
`gate_fraction` curve shifted so that Δppl < 0.5% extends through
higher routing fractions. The verdict flips from NO-GO to MARGINAL
or GO. This would be the fundable first result and the signal that
the architecture actually works as designed.

### Outcome B — Partial improvement

`r*` rises modestly (say from 8% to 11-13%) but does not reach 15%.
The adapter learned *something* but not enough. Diagnoses:
- Training too short → run longer (2000 steps)
- Adapter too small → bump `d_inner` from 256 to 512 or 1024
- Alignment loss insufficient → add a CE auxiliary loss so the
  adapter is pressured by language-modeling quality directly,
  not just output MSE

### Outcome C — No improvement, alignment loss decreases

The training loop reduces the alignment loss (adapter is learning
something) but `r*` does not move. This would mean the adapter
has learned to minimize MSE in a way that does not actually make
the coarse branch safer to route through. Diagnoses:
- The alignment loss is optimizing the wrong objective (MSE is a
  blunt instrument; CE on the final logits might be better)
- The adapter is underfit — the coarse branch's residual error is
  too large for a low-rank linear adapter to correct

### Outcome D — Training diverges

Loss becomes NaN, gradients blow up, or `gate_fraction` goes to 0
or 1 uniformly. This would be a bug in the integration layer rather
than the architecture. Diagnoses:
- Check numerical stability of the bf16 dual-branch forward under
  gradient accumulation
- Verify the stopgrad invariant is actually holding during backward
  (the test `test_stopgrad_on_full_path` proves it holds on
  synthetic tensors, but a real Mistral backbone might expose an
  edge case)
- Lower learning rate by 10x and retry

All four outcomes are informative and each has a concrete next step.

## What this experiment does NOT attempt

- **No backbone fine-tune.** Mistral stays frozen. We are not
  retraining Mistral itself, only the FSCS control plane and
  adapters.
- **No LoRA on Mistral.** Deliberately out of scope because it
  would conflate "FSCS works" with "LoRA fine-tuning helps."
- **No CE loss.** The only loss is the alignment loss. This is the
  cleanest test of whether the alignment-loss mechanism itself can
  push `r*` up.
- **No per-band differentiated coarse operators.** All layers use
  the same sliding-window coarse operator with the adapter on top.
  The spec §9.1 EMA-cache global-band variant is out of scope for
  this first experiment; it is a separate fix if this experiment
  fails with diagnosis C.

## Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Script has an untested integration bug when run against real Mistral | Moderate | CPU smoke test passed, but the real path uses `MistralFSCSWrapper` with `use_coarse_adapter=True` which has not been exercised end-to-end. First run may surface 1-2 small bugs; iterate like the r* sweep did. |
| Gradient through the dual-branch forward produces NaN on bf16 | Low-moderate | Control plane runs in float32 (audit fix). If NaN appears, lower LR and/or move the backbone to float32 (bigger memory, but safer). |
| The adapter architecture is insufficient (low-rank linear cannot approximate full attention) | Moderate | Diagnose C above. The fix is to increase `d_inner` or add more layers to the adapter. ~1 hour of code + 1 hour re-train. |
| Checkpoint format changes before the post-training r* sweep can be wired up | Low | The checkpoint is a plain torch.save dict. Unchanged between this commit and the next-session r* re-measurement work. |
| Training wall-clock exceeds budget | Low | Reduce `max-steps`, `batch-size`, or `seq-len`. 200 steps on 1024 seq × batch 4 should still show a measurable effect. |

## What to tell a VC after the training run completes

**If Outcome A (fundable):**

> "First FSCS alignment-loss co-training experiment on Mistral-7B
> produced r* = X% (up from 8% frozen-backbone), with baseline PPL
> unchanged and training wall-clock under 2 hours on a single A100.
> This confirms the spec §5.5 prediction and is the first quality-
> preserving operating point for attention routing at meaningful
> fractions on a production-scale open-weights model."

**If Outcome B (partial) or C (no-improvement, loss-decreases):**

> "First FSCS alignment-loss co-training experiment produced
> r* = Y%, a modest improvement over the frozen-backbone 8% baseline.
> The training loop successfully reduced the alignment loss, but
> r* did not reach the spec's predicted 15-30% range. Next experiment
> pursues [a larger adapter / CE auxiliary loss / per-band coarse
> operators]."

**If Outcome D (diverges):**

> "Training diverged on bf16; retrying with float32 backbone and
> lower learning rate."

In all three outcomes, the measurement infrastructure and the
integration layer stand unchanged and reusable. The architecture
question — does alignment-loss training push r* past the 8%
frozen-backbone ceiling — is the only open variable.

---

## Files touched this session to enable this experiment

- `symbolu/fscs/core.py` — added `FSCSCoarseAdapter`, config fields
- `symbolu/fscs/__init__.py` — exported the adapter
- `symbolu/fscs/mistral_gated_layer.py` — wired adapter into forward,
  added `get_alignment_loss()`, added `_infer_d_model()`
- `symbolu_training/training/unified/mistral_fscs_wrapper.py` —
  `_sync_fscs_device` now handles the adapter
- `tests/test_fscs_core.py` — 4 new `TestCoarseAdapter` tests
- `scripts/train_fscs_alignment.py` — **new**, this is the training
  script itself, with both real-training and CPU-smoke-test paths
- `docs/FSCS_TRAINING_PLAN.md` — this file

All of the above is on branch `claude/vc-pitch-document-LBYcN` as
of commit `cf3d539` (adapter module) and the follow-up commit that
adds this script and doc.
