# Video-DiT reused-feature-cache compression — feasibility harness

Pre-registered, two-stage feasibility study for
[`docs/VIDEO_DIT_FEATURE_CACHE_COMPRESSION_FEASIBILITY_PLAN.md`](../../../../docs/VIDEO_DIT_FEATURE_CACHE_COMPRESSION_FEASIBILITY_PLAN.md).
Bounded research decision — **not** a product, **no** novelty/patent/commercial claims before measurement.

> This study evaluates whether **protected compression** improves a **persistent video-DiT cache** under
> the **same compute-skipping policy**. It does not assume novelty, and it does not treat compression as
> an alternative to caching or skipping. It concerns tensors **stored and reused across denoising steps** —
> not weights, one-pass activations, latents, or transient tensors.

## Files
| File | Runs on | What it does |
|---|---|---|
| `dit_cache_lib.py` | CPU | Core: quant/protected/low-rank, structure & redundancy metrics, byte accounting, error gate. Wires the repo's production INT4 quantizer when importable. |
| `analyze_cache_compressibility.py` | CPU | **Stage A** analyzer — reads captured tensors, emits per-cache-object metrics + a provisional verdict (caps at "representation feasibility only"). |
| `verdict.py` | CPU | Deterministic G1–G6 gate logic + **frozen-threshold guard**. |
| `capture_dit_cache.py` | **GPU pod** | **Stage B** capture — read-only forward taps on a diffusers video-DiT (CogVideoX primary); dumps cross-step cache tensors + systems counters. |
| `test_cache_compression_cpu.py` | CPU | 21 unit tests (metadata, quant, protection, byte accounting, metrics, gate, freezing, verdict). |
| `run_commands.sh` | GPU pod | Orchestration: capture → analyze. |

## Two-stage flow

**Stage A (CPU — here, now):** validates the *logic* and, once real tensors are captured, whether the
cache objects are compressible.
```bash
cd scripts/kvpro_video_dit_cache
python -m pytest test_cache_compression_cpu.py -q          # 21/21 must pass
python analyze_cache_compressibility.py --cache <dir-of-captured-.pt>
```
CPU output reaches at most `CONTINUE — representation feasibility only`. **A CPU harness cannot establish
whether the workload is capacity-, bandwidth-, communication-, or compute-bound**, and tensor fidelity is
a proxy for output-video quality — not a substitute.

**Stage B (GPU pod — not yet run):** capture real cross-step cache tensors and systems counters.
```bash
pip install -U "diffusers>=0.31" transformers accelerate imageio imageio-ffmpeg
bash run_commands.sh          # or call capture_dit_cache.py directly (see its header)
python analyze_cache_compressibility.py --cache artifacts/video_dit_cache/capture
```

## Pre-registration discipline (do this before trusting any verdict)
1. **Calibrate** on the pod: estimate baseline run-to-run quality variance, metric noise, model/prompt
   sensitivity, profiling variance (Stage B).
2. **Freeze** thresholds: set `verdict.FROZEN_GATES` from calibration, then
   ```bash
   python -c "import verdict; print(verdict.freeze(verdict.FROZEN_GATES))"
   ```
   Paste the hash into `verdict.FROZEN_SHA256`. `verdict.assert_gates_frozen` then refuses any post-hoc
   threshold edit (and refuses to run while the placeholder hash is in place).
3. **Only then** evaluate the protected-compression variants (baseline ladder C–F). Do not tune
   thresholds after seeing results.

## Baseline ladder (plan §6) — same schedule, only the representation changes
A no-cache · B FP cache · C uniform low-bit · D protected low-bit · E protected + error-gate · F strong
existing method. Report **C−B, D−C, E−D, E-vs-F**.

## Evidence tiers
Every result carries one: `Measured — CPU tensor analysis` · `Measured — GPU profiling` · `Measured —
end-to-end generation` · `Modeled — capacity projection` · `Inferred — not workload validated` · `Not
measured` · `Requires external patent review`. Results sheet:
[`Project_documentation/repository/artifacts/video_dit_cache/RESULTS_TEMPLATE.md`](../../artifacts/video_dit_cache/RESULTS_TEMPLATE.md)
(all fields start `NOT RUN`/`REQUIRES GPU`).

## Scope guard
Does **not** modify KVPro. Does **not** claim support for all video-DiT families (CogVideoX primary,
Wan2.1 secondary). Does **not** draft patent claims — a differentiated verdict only *triggers* a
professional prior-art/patent search.
