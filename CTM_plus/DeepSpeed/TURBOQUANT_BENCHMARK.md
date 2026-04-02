# DeepSpeed TurboQuant + CTM+ Integration — Benchmark Results

**Branch:** `claude/deepspeed-turboquant-integration-O9Wqj`  
**Date:** 2026-04-02  
**Mode:** Quick (2 tensor shapes, 50 quality samples, 3 timing runs per config)  
**Platform:** CPU-only simulation (no GPU; NumPy reference implementation)

---

## Overview

This document records the benchmark results for the **TurboQuant + CTM+ offload integration**
added to `ctm_plus_deepspeed`. The integration compresses gradient and optimizer-state tensors
(Adam momentum and variance) before offloading them from GPU to CPU memory, using the same
**PolarQuant + QJL** pipeline as the vLLM KV-cache integration.

The key architectural difference from vLLM:

| Dimension | vLLM | DeepSpeed |
|-----------|------|-----------|
| Target tensors | KV cache key/value vectors | Gradients, Adam momentum, Adam variance |
| Tensor shape | Fixed `(num_heads, head_dim)` | Arbitrary — segmented into `segment_dim` chunks |
| Access pattern | Attention score estimation | Full decode (GPU restore) |
| Primary metric | Dot-product fidelity | Round-trip MSE / cosine similarity |

---

## What Was Measured

Five benchmark sections were run via `run_turboquant_benchmark.py`:

| Section | What it measures |
|---------|-----------------|
| 1. Compression quality | MSE, cosine similarity, SNR across bit-widths × tensor types |
| 2. Throughput | compress / decompress GB/s for realistic layer sizes |
| 3. Memory ratios | Actual heap savings vs theoretical bit-packed savings |
| 4. Offload pipeline | End-to-end register → offload → fetch latency |
| 5. Training simulation | CTM+ eviction + TurboQuant over a synthetic training loop |

---

## Section 1 — Compression Quality

**Test setup:** 50 random vectors × segment dimension 128, three tensor types:
- `gradient` — scale ~0.01 (typical gradient magnitude)
- `adam_momentum` — scale ~0.1 (first Adam moment)
- `adam_variance` — scale ~0.001, always positive (second Adam moment)

### Results

| Config | Bits/elem | Ratio (theory) | Avg cosine | Avg SNR | Avg MSE |
|--------|----------|----------------|-----------|---------|---------|
| **2-bit + QJL** | 3.23 | 9.9× | 0.860 | 5.6 dB | 2.7e-05 |
| **3-bit + QJL** | 4.23 | 7.6× | 0.965 | 11.5 dB | 7.0e-06 |
| **4-bit + QJL** | 5.22 | 6.1× | 0.991 | 17.6 dB | 1.7e-06 |
| **4-bit lossless** (d=256) | 5.11 | 6.3× | 0.995 | 20.4 dB | 8.7e-07 |
| **3-bit no QJL** | 3.23 | 9.9× | 0.966 | 11.8 dB | 6.8e-06 |

Results are consistent across all three tensor types (gradient, momentum, variance) — the
angular distribution after random rotation is statistically similar regardless of the tensor's
scale or sign distribution.

### Key observations

**3-bit is the recommended default for training.**  Cosine similarity of 0.965 and SNR of
11.5 dB are sufficient for gradient-based optimisation; empirical evidence from mixed-precision
training suggests cosine > 0.95 rarely degrades convergence.

**2-bit is too aggressive for training.** Cosine of 0.86 and SNR of 5.6 dB would introduce
significant noise into optimizer updates. It may be acceptable for very late training stages
or non-critical optimizer state compression.

**4-bit lossless (segment_dim=256) achieves the best quality.** SNR of 20.4 dB and cosine
0.995 at 6.3× theoretical compression. Larger segments improve quality because more data
is available for the rotation to distribute energy evenly.

**QJL adds negligible value for full reconstruction.** 3-bit with QJL (cosine 0.965) and
3-bit without QJL (cosine 0.966) are statistically indistinguishable at reconstruction.
QJL corrects dot-product *estimation* bias, not reconstruction error — its value is primarily
for asymmetric attention score computation (KV cache), not for training tensor round-trips.
Consider disabling QJL in DeepSpeed configs to halve the `actual_stored_bytes` overhead from
QJL sign arrays.

---

## Section 2 — Throughput

**Test setup:** 3 timed runs per (tensor, config) pair, reported as GB/s of original data.

| Tensor | Size | Config | Compress | Decompress |
|--------|------|--------|----------|-----------|
| small_linear (768×768) | 2.25 MB | 3-bit | 0.0025 GB/s | 0.0081 GB/s |
| small_linear (768×768) | 2.25 MB | 4-bit | 0.0024 GB/s | 0.0079 GB/s |
| medium_linear (2048×2048) | 16.0 MB | 3-bit | 0.0027 GB/s | 0.0078 GB/s |
| medium_linear (2048×2048) | 16.0 MB | 4-bit | 0.0025 GB/s | 0.0077 GB/s |

### Key observations

Throughput is flat at ~0.0025 GB/s compress / ~0.008 GB/s decompress regardless of tensor
size. This confirms the bottleneck is the **Python-level per-segment loop**, not memory
bandwidth — each of the `n_segments = ceil(n_elements / 128)` segments is compressed
individually in a Python `for` loop.

This is a **simulation artefact**, not an inherent algorithm limitation. A vectorised
implementation (batched NumPy matrix operations across all segments simultaneously, or a
CUDA kernel) would scale throughput proportionally with tensor size.

---

## Section 3 — Memory Ratios

**Distinguishes two different "compression ratio" concepts:**

| Concept | Definition |
|---------|-----------|
| **Actual ratio** | `original_bytes / actual_stored_bytes` — real Python/numpy heap usage. Angle indices stored as `uint8` (1 byte/index), not bit-packed. |
| **Theoretical ratio** | `original_bytes / theoretical_packed_bytes` — if `angle_bits` bits per index were packed into bytes. This is the production target. |

### Results

| Tensor | Config | FP32 | Actual stored | Actual ratio | Theoretical ratio |
|--------|--------|------|--------------|-------------|------------------|
| small_linear (768×768) | 2-bit | 2.25 MB | 1.19 MB | **1.89×** | 9.18× |
| small_linear (768×768) | 3-bit | 2.25 MB | 1.19 MB | **1.89×** | 7.15× |
| small_linear (768×768) | 4-bit | 2.25 MB | 1.19 MB | **1.89×** | 5.85× |
| medium_linear (2048×2048) | 2-bit | 16.0 MB | 8.47 MB | **1.89×** | 9.18× |
| medium_linear (2048×2048) | 3-bit | 16.0 MB | 8.47 MB | **1.89×** | 7.15× |
| medium_linear (2048×2048) | 4-bit | 16.0 MB | 8.47 MB | **1.89×** | 5.85× |

### Key observations

**Actual ratio is fixed at 1.89× regardless of `angle_bits`.** The reason: each angle
index (whether 2-bit, 3-bit, or 4-bit) is stored as a `uint8` numpy array element (1 byte).
The bits above the configured angle width are simply unused. Until bit-packing is implemented,
changing `angle_bits` only affects quality — not actual memory usage.

The 1.89× comes from: `(n_segments * (1 byte radius×8 + (d-1) bytes angles + d bytes QJL signs + 8 bytes scale)) / (n_segments * d * 4 bytes FP32)` where d=128. QJL sign arrays (128 bytes/segment) dominate actual storage. Disabling QJL would improve actual ratio to ~1.0× (the segment carries almost no compression vs FP32 without bit-packing once you store uint8 indices).

**Gap to close: 1.89× actual → 7.15× theoretical for 3-bit.** This requires implementing
bit-packing for the angle index arrays. See roadmap below.

---

## Section 4 — Offload Pipeline Latency

**Test setup:** 10 runs of register → offload(data) → fetch(data), averaged.

| Tensor | Config | Offload | Fetch | Total | Bandwidth |
|--------|--------|---------|-------|-------|-----------|
| small (2.25 MB) | 3-bit TQ | 905 ms | 297 ms | 1,202 ms | 0.004 GB/s |
| small (2.25 MB) | 4-bit TQ | 902 ms | 290 ms | 1,192 ms | 0.004 GB/s |
| small (2.25 MB) | **No TQ (raw)** | **0.27 ms** | **0.006 ms** | **0.27 ms** | **17.2 GB/s** |
| medium (16 MB) | 3-bit TQ | 6,585 ms | 2,166 ms | 8,751 ms | 0.004 GB/s |
| medium (16 MB) | 4-bit TQ | 6,417 ms | 2,082 ms | 8,499 ms | 0.004 GB/s |
| medium (16 MB) | **No TQ (raw)** | **3.8 ms** | **0.006 ms** | **3.8 ms** | **8.7 GB/s** |

### Key observations

The raw (no compression) path uses numpy `array.copy()` which runs at near-memory-bandwidth
speeds (~17 GB/s). The TurboQuant path is ~3,300× slower because of the Python loop overhead.

This gap is **not representative of a production implementation**. A vectorised or CUDA version
of PolarQuant would process all segments in parallel, recovering most of the 4,000× gap.
The benchmark correctly characterises the current state as a CPU reference simulation.

---

## Section 5 — Training Simulation

**Test setup:** 4 layers × (1024×1024) = 4 MB per tensor. Per step: offload gradients and
optimizer states, fetch back for next step. GPU budget: 1 GB (forces frequent eviction).

| Config | Total offload | Total fetch | Actual compression | Theory compression |
|--------|--------------|-------------|-------------------|--------------------|
| No compression (raw) | **9 ms** | **0 ms** | — | — |
| 3-bit TurboQuant | 39,031 ms | 12,841 ms | 1.89× | 7.15× |
| 4-bit TurboQuant | 40,384 ms | 12,958 ms | 1.89× | 5.85× |

24 tensors offloaded and fetched per run. All 24 TurboQuant offloads were compressed
(zero fell through to the raw path), confirming `pin_gradients=False` in `for_training()` is
correctly allowing gradient tensors to reach the compression path.

The 4,000× wall-clock overhead vs raw copy reflects the same Python loop bottleneck as
Section 4. In production (CUDA kernels) the tradeoff would be:
- ~4–5× lower CPU memory consumption for optimizer states
- ~2–4× compression bandwidth overhead from the PolarQuant transform itself

---

## Summary of Findings

### Algorithm quality: ready ✅

The PolarQuant + QJL algorithm produces correct, consistent results across all three tensor
types (gradient, momentum, variance). Quality is monotonically better with more bits.
3-bit with QJL is the right default for training workloads.

### Memory accounting: honest ✅ (fixed in audit)

After audit fixes, `CompressedTensorBuffer` now correctly distinguishes:
- `actual_stored_bytes` — real Python/numpy heap consumption (1.89×)
- `theoretical_packed_bytes` — bit-packed storage target (7.15× at 3-bit)

### Config wiring: working ✅ (fixed in audit)

- `CTMDeepSpeedConfig.to_turboquant_config()` bridges settings automatically
- `enable_turboquant=False` correctly disables compression end-to-end
- `for_training()` preset: `pin_gradients=False` so gradients actually reach the TQ path

### Throughput: simulation only ⚠️

Current implementation is a CPU NumPy reference (~0.003 GB/s). Two engineering investments
are required to move to production:

1. **Bit-packing** — pack `angle_bits`-wide indices into bytes  
   Impact: closes the 1.89× → 7.15× gap in actual memory savings

2. **Vectorised compress/decompress** — eliminate per-segment Python loop  
   Impact: closes the ~3,300× throughput gap vs raw numpy copy

---

## Production Roadmap

| Priority | Work item | Expected impact |
|----------|-----------|----------------|
| P0 | Bit-pack angle indices (`numpy.packbits` or C extension) | Actual ratio: 1.89× → ~6–7× |
| P0 | Vectorise compress: batch all segments as one `(n_segs, d)` matrix op | Throughput: 0.003 → ~0.5–2 GB/s |
| P1 | Disable QJL for training configs (saves ~50% of actual stored bytes) | Actual ratio: ~3.5–4× without bit-packing |
| P1 | CUDA kernel for PolarQuant rotation + quantisation | Throughput: ~10–50 GB/s (GPU-resident) |
| P2 | Async compression pipeline (compress next tensor while current transfers) | Hides compression latency behind PCIe transfer |
| P2 | Wire into DeepSpeed ZeRO-2/3 offload hooks natively | Removes manual `offload()` / `fetch()` calls |

---

## Reproduction

```bash
# Quick run (2 shapes, 50 samples)
cd CTM_plus/DeepSpeed
python run_turboquant_benchmark.py --quick

# Full run (5 shapes, 200 samples)  
python run_turboquant_benchmark.py

# Single section
python run_turboquant_benchmark.py --section 1

# Export results
python run_turboquant_benchmark.py --json my_results.json
```

Results are also saved to `benchmark_results.json` in this directory.
