# Video-DiT Cache-Compression Feasibility — RESULTS TEMPLATE

Pre-registered results sheet for `VIDEO_DIT_FEATURE_CACHE_COMPRESSION_FEASIBILITY_PLAN.md`. **Every field
below is initialized to `NOT RUN` / `NOT MEASURED` / `REQUIRES GPU`.** Fill a field only with a value
carrying its evidence tier (plan §13). Do not overwrite a `REQUIRES GPU` field with a CPU number.

Evidence tiers: `Measured — CPU tensor analysis` · `Measured — GPU profiling` · `Measured — end-to-end
generation` · `Modeled — capacity projection` · `Inferred — not workload validated` · `Not measured` ·
`Requires external patent review`.

---

## 0. Run metadata
| Field | Value | Evidence tier |
|---|---|---|
| Primary model | `NOT RUN` (plan: CogVideoX-2b/5b) | Not measured |
| Secondary model | `NOT RUN` (plan: Wan2.1 T2V-1.3B) | Not measured |
| Prompt / seed set | `NOT RUN` | Not measured |
| Scheduler / steps / cache schedule | `NOT RUN` | Not measured |
| Resolution / num_frames | `NOT RUN` | Not measured |
| Gates frozen (hash) | `NOT FROZEN` (placeholder) | Not measured |
| Commit hash of harness | see completion report | — |

## 1. Calibration phase (freeze thresholds BEFORE protected-compression eval)
| Field | Value | Evidence tier |
|---|---|---|
| Baseline run-to-run quality variance (VBench/FVD) | `REQUIRES GPU` | Requires GPU |
| Metric noise (quality) | `REQUIRES GPU` | Requires GPU |
| Model/prompt sensitivity | `REQUIRES GPU` | Requires GPU |
| Profiling measurement variance | `REQUIRES GPU` | Requires GPU |
| Frozen G3 quality margin | `NOT SET` (from calibration) | Not measured |

## 2. Stage A — representation feasibility (CPU) — per cache object
Fill one block per `cache_object` (residual_block, hidden_states, attn_out, cross_attn_out,
temporal_attn_out, feature_delta, predicted_residual). **Do not average across objects.**

| Metric | Value | Evidence tier |
|---|---|---|
| Tensor dims (T,N,C) by layer | `NOT RUN` | Measured — CPU tensor analysis |
| Bytes per cached object | `NOT RUN` | Measured — CPU tensor analysis |
| Total persistent cache residency | `NOT RUN` | Modeled — capacity projection |
| Delta magnitude between reusable steps | `NOT RUN` | Measured — CPU tensor analysis |
| Channel-wise outlier concentration | `NOT RUN` | Measured — CPU tensor analysis |
| Token-wise outlier concentration | `NOT RUN` | Measured — CPU tensor analysis |
| Spatial redundancy (low-rank energy) | `NOT RUN` | Measured — CPU tensor analysis |
| Temporal redundancy (consecutive cosine/delta) | `NOT RUN` | Measured — CPU tensor analysis |
| Entropy / dynamic range | `NOT RUN` | Measured — CPU tensor analysis |
| Per-channel vs per-block quant error | `NOT RUN` | Measured — CPU tensor analysis |
| Uniform INT8 / INT4 reconstruction error | `NOT RUN` | Measured — CPU tensor analysis |
| Protected-channel reconstruction error | `NOT RUN` | Measured — CPU tensor analysis |
| Low-rank residual reconstruction error | `NOT RUN` | Measured — CPU tensor analysis |
| Error accumulation over repeated reuse | `NOT RUN` | Measured — CPU tensor analysis |
| Gate admission / rejection rate | `NOT RUN` | Measured — CPU tensor analysis |
| Dominant object (residency/bandwidth/quality) | `NOT RUN` | Measured — CPU / REQUIRES GPU (bandwidth) |

## 3. Stage B — systems feasibility (GPU / end-to-end)
| Metric | Value | Evidence tier |
|---|---|---|
| Peak HBM | `REQUIRES GPU` | Measured — GPU profiling |
| Persistent cache HBM | `REQUIRES GPU` | Measured — GPU profiling |
| Cache read/write bytes | `REQUIRES GPU` | Measured — GPU profiling |
| HBM-bandwidth utilization | `REQUIRES GPU` | Measured — GPU profiling |
| Compression/decompression latency | `REQUIRES FUSED-KERNEL PROTOTYPE` | Not measured (emulated ≠ fused) |
| Kernel time | `REQUIRES GPU` | Measured — GPU profiling |
| End-to-end generation time | `REQUIRES GPU` | Measured — end-to-end generation |
| PCIe / NVLink transfer volume | `REQUIRES GPU` | Measured — GPU profiling |
| Max frames / resolution / batch | `REQUIRES GPU` | Measured — GPU profiling |
| Cache hit / reuse rate | `REQUIRES GPU` | Measured — GPU profiling |
| VBench / FVD / task quality | `REQUIRES GPU` | Measured — end-to-end generation |
| Human-visible temporal artifacts | `NOT MEASURED` | Not measured |

## 4. Baseline ladder deltas
| Delta | Value | Evidence tier |
|---|---|---|
| C − B (ordinary compression benefit / quality loss) | `NOT RUN` | REQUIRES GPU (quality) / Measured — CPU (bytes) |
| D − C (protected representation value) | `NOT RUN` | Measured — CPU (proxy) / REQUIRES GPU (quality) |
| E − D (reconstruction-gate value) | `NOT RUN` | REQUIRES GPU |
| E vs F (value vs strong baseline) | `NOT RUN` | REQUIRES GPU |

## 5. Gate outcomes
| Gate | Pass? | Evidence tier |
|---|---|---|
| G1 cache materiality | `REQUIRES GPU` (bound-ness) / `NOT RUN` (capacity) | Measured — GPU / Modeled |
| G2 net compression | `NOT RUN` | Measured — CPU tensor analysis |
| G3 quality | `NOT RUN` (CPU proxy) / `REQUIRES GPU` (output) | Measured — CPU / REQUIRES GPU |
| G4 systems value | `REQUIRES GPU` | Measured — GPU / end-to-end |
| G5 protected-method value | `NOT RUN` | Measured — CPU tensor analysis |
| G6 strong-baseline value | `REQUIRES GPU` | Measured — end-to-end |

## 6. VERDICT
`NOT RUN` — one of: STOP–cache not material · STOP–material but not compressible · STOP–uniform
sufficient · STOP–protected fails quality · STOP–overhead erases systems benefit · CONTINUE–representation
feasibility only · CONTINUE–systems feasibility demonstrated · CONTINUE–differentiated result requiring
prior-art and patent review.

> Reminder: CPU evidence alone can reach at most **CONTINUE — representation feasibility only**. The two
> stronger CONTINUE verdicts require Stage-B GPU/e2e evidence. A differentiated result triggers a
> **professional prior-art and patent review** — it does not substitute for one.
