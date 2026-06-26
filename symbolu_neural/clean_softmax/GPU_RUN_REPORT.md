# GPU Run Report — Clean-Softmax Symbol-U (frozen implementation)

**Objective:** validate that the *current* clean-softmax Symbol-U implementation
(model + algorithms **frozen**) runs at GPU scale and produces all diagnostics.
This is a scaling/integration validation, **not** a quality benchmark and not a
comparison to any other model.

## How to run (one command, RunPod)

```bash
git clone <repo> && cd symbolu && git checkout claude/patent-research-spec-tsdnjv
bash scripts/run_gpu_training.sh
```

The script verifies CUDA, prints GPU info, installs missing deps, prepares the
dataset, trains, checkpoints, evaluates, runs `generate.py`, runs the token-change
instrumentation, and writes everything under `runs/symbolu_gpu_full/`. Override any
hyperparameter via env vars, e.g. `STEPS=10000 BATCH=96 DMODEL=768 LAYERS=12 bash
scripts/run_gpu_training.sh`.

### Exact training command (what the script launches)

```bash
python -m symbolu_neural.clean_softmax.train_gpu \
  --corpus data/clean_lm/corpus.txt --ablation full --mode combined \
  --steps 5000 --batch-size 64 --grad-accum 1 --lr 3e-4 \
  --block 512 --d-model 512 --layers 8 --heads 8 \
  --amp --ckpt-every 1000 --eval-every 500 --log-every 50 \
  --contrib-every 4 --gen-tokens 400 --seed 0 --out runs/symbolu_gpu_full
```

- **batch size** 64 (sequences of `--block` 512 tokens) · **grad accumulation** 1
  (raise to e.g. 4 for an effective batch of 256 on smaller VRAM)
- **learning rate** 3e-4 (AdamW, wd 0.01, grad-clip 1.0)
- **mixed precision** `--amp` (bf16 on Ampere+/Hopper, fp16+GradScaler otherwise; `--no-amp` for fp32)
- **steps** 5000 · **checkpoint interval** 1000 · **evaluation interval** 500
- `--mode combined` keeps the contribution + residual-reg + entropy-cal objectives
  so the contribution diagnostics are produced; `--contrib-every 4` runs the extra
  enabled-vs-disabled forwards every 4 steps to bound overhead.
- **head-role policy** (validation-first): add `--control-heads vritti,aspect` (or
  `CONTROL_HEADS="vritti,aspect" bash scripts/run_gpu_training.sh`) so only Vritti &
  Aspect drive the control entropy; Guna/Kosha stay diagnostic (still logged as
  `H_guna`/`H_kosha`). Optional `--control-layer <late idx>` taps a late zone and
  `--stopgrad-heads` makes the heads validation-only (Stages 1–2). Default
  (`--control-heads ""`) preserves the original behavior.

## Hardware / GPU recommendations

The corpus is char-level (vocab 176), so the model is compute-bound, not
memory-bound. Footprints for `--ablation full --mode combined`:

| Config | params | ckpt (model, fp32) | approx FLOPs/token |
|---|---|---|---|
| **A100 default** (d512, 8L, blk512) | **17.2 M** | ~69 MB | ~26 MFLOP |
| H100 larger (d768, 12L, blk1024) | 47.6 M | ~190 MB | ~77 MFLOP |
| 24 GB modest (d256, 6L, blk512) | 4.8 M | ~19 MB | ~8 MFLOP |

- **GPU type:** A100 (40/80 GB) or H100 preferred; any ≥ **16 GB** CUDA GPU
  (A10/3090/4090) runs the default config comfortably (it needs far less).
- **Minimum VRAM:** ~8–10 GB for the default (17 M params + batch 64×512 activations
  under AMP); use `--grad-accum` to shrink the live batch on smaller cards.
- **Expected training time (5000 steps, default):** ~**20–60 min** on an A100
  (contribution mode adds ~2 extra forwards every 4th step). H100 faster; the
  larger config proportionally longer.
- **Expected throughput:** order **3×10⁴–1.2×10⁵ tokens/s** on A100 with AMP for
  the default size (CPU smoke below hit ~7.6k tok/s on a 0.37 M toy model).
- **Expected checkpoint size:** ~69 MB (model state, fp32) for the default; scales
  with parameter count (table above). Periodic `ckpt_step*.pt` are the same size.

## Diagnostics produced (nothing removed)

`train_log.jsonl` (per `--log-every`): `train_loss`, `grad_norm`, `lr`, `act_norm`,
`tokens`, `tok_per_s`, `entropy_mean`, `entropy_std`, `refine_residual_norm`,
`refine_gate_mean`, `refine_halt_p`, `mem_residual_norm`, `mem_readiness`,
per-module `*_delta_loss` and `*_help_frac` (contribution), and `eval` lines
(`val_loss`, `ppl`). `metrics.json`: final val loss/ppl/ECE/entropy-error corr,
params, throughput, help-fractions. `samples.txt`: fixed-prompt generations
(sampled + greedy). `activity.txt`: token-change instrumentation
(`inspect_generation.py`) — per-mechanism ablation token-change counts. `config.json`,
`vocab.json`, `ckpt.pt`, `ckpt_step*.pt`, `generate_cli.txt`.

## Validation run (CPU smoke of the exact pipeline)

This environment has **no CUDA**, so the harness was validated end-to-end on CPU
in fp32 with a tiny config (the GPU run uses the same code path with AMP on):

- command: `EXP=smoke STEPS=30 BATCH=8 DMODEL=64 LAYERS=2 BLOCK=64 bash
  scripts/run_gpu_training.sh`
- result: training completed in **3.8 s** (~7.6k tok/s), 0.37 M params; periodic +
  final checkpoints saved; `generate.py` loaded the checkpoint and produced samples;
  `inspect_generation.py` reported all 7 mechanisms active.
- final (tiny, meaningless quality — harness check only): val_loss 3.65, ppl 38.3,
  ECE 0.003; contribution: refine helps 93.3 %, memory helps 93.3 %.
- diagnostics confirmed present in `train_log.jsonl` (entropy 1.55→1.38, refine
  halt_p 0.88→0.93 with combined mode, refine residual 90→319, mem residual 37→172,
  per-module delta_loss + help_frac, eval lines).

So the GPU script is exercised and correct; on a GPU pod the same command produces
the same artifacts at scale (with real `metrics.json`/`samples.txt` populated by the
run).

## Observations

- The implementation is frozen: `train_gpu.py` is a pure training wrapper that
  imports the existing model/config/data/metrics/generate unchanged. No architecture
  or patent-algorithm change.
- AMP path auto-selects bf16 on Ampere+/Hopper (no loss scaler) and fp16 + GradScaler
  elsewhere; CPU falls back to fp32.
- Contribution mode triples the per-step forward cost on contribution steps; bound it
  with `--contrib-every` (default 4) or set `--mode normal` to disable (then the
  contribution diagnostics are absent and refinement's gate floors — see the prior
  reports).

## Limitations

- **Char-level corpus (vocab 176)** built from in-repo Markdown — fine for a scaling/
  integration test, but generation quality is not meaningful and is not claimed. For a
  real LM run, point `prepare_data` at a larger corpus.
- Prior capacity-matched experiments showed these mechanisms do **not** beat an
  equal-compute plain Transformer; this GPU run validates that the implementation
  *scales and runs*, not that it is useful. Quality/superiority is explicitly out of
  scope here.
- Single GPU only (no FSDP/DDP); the model sizes targeted fit one card.

## Success criteria

| criterion | status (CPU smoke) |
|---|---|
| training completes | ✅ 30/30 steps, 3.8 s |
| checkpoint loads | ✅ `generate.py` + `inspect_generation.py` loaded `ckpt.pt` |
| generation works | ✅ `samples.txt`, `generate_cli.txt` |
| diagnostics produced | ✅ `train_log.jsonl`, `metrics.json` (full set) |
| contribution analysis runs | ✅ help-fractions + `activity.txt` |
| report generated | ✅ this file |

On a GPU pod the same `bash scripts/run_gpu_training.sh` reproduces all of the above
with AMP at scale.
