# Phase 6M.5 / 6M.6 / 6F — Throughput-recovery test & design plan

> **Status: PLAN ONLY — no implementation, no optimization, no kernel/quant
> changes.** Three **gated, cheapest-first** tests to decide *whether and how* to
> recover int4_protected decode throughput. Test 1 gates the rest. Companion to
> `PHASE_6M_ATTRIBUTION_FINDINGS.md` (attribution) and
> `PHASE_6F_KERNEL_OPT_DESIGN.md` (the read-path kernel design this gates into).

## 0. Why this plan exists (the measured starting point)

Phase 6L proved density (**1.83× net seq/GB**, quality locked) but measured a
**throughput tax at saturation: 0.22× bf16 aggregate tok/s** (~9× slower/user).
Phase 6M attributed it:

- **6M.4 (long-context, decisive):** at the real operating point int4 decode is
  **GPU-work-bound (~77% GPU-busy)**, NOT host/sync-bound. Host syncs amortize to
  <1%. The int4-specific tax is **genuine reconstruction**: decode-attention
  kernel ~29% + paged gather/copy **~19.5% (measured)**.
- **6F design doc:** the int4 attention kernel is **~118× slower per call** than
  bf16's (`~825 µs` vs `~7 µs`), localized to `int4_packed_load_{K,V}_block` +
  `int4_quant_dequant_{K,V}_block`.
- **The unmeasured unknown:** *is that kernel compute-bound or bandwidth-bound?*
  ncu was **blocked on the prior pod** (`ERR_NVGPUCTRPERM`), so we never split it.
  **This unknown gates every downstream decision** — a kernel rewrite (6F) only
  helps if compute/coalescing-bound; raw HBM bandwidth only helps if
  bandwidth-bound.

**Ceiling reminder (honest):** int4 *fundamentally* reads packed KV + scale +
xmin + protected and dequants every token. No test below reaches bf16 parity; the
realistic software ceiling is **~0.22× → ~0.27–0.30×**. The point of these tests
is to decide if even that bounded gain is worth funding, and via which lever.

---

## Test 1 — Roofline: compute-bound vs bandwidth-bound (Phase 6M.5)

**THE GATE. Cheapest. Run first.** ~1 pod-day.

### Goal
Classify the int4 decode-attention kernel (and the gather) as **compute-bound**,
**memory-bandwidth-bound**, or **latency/occupancy-bound** — the single fact that
decides whether 6F (kernel work), H100/H200 (Test 2), or an HBM-level change is
the right lever.

### Method (reuse existing tooling; needs an ncu-unlocked pod)
- Driver: `bench_phase6_d_profile_gpu.py --cell int4_captured` (and `bf16_stock`)
  at the saturation operating point: `--max-model-len 8192 --batch-size 48
  --max-tokens 96 --prompt-frac 0.95` (long-context; matches 6M.4).
- Profiler: **ncu** with `--section SpeedOfLight --section MemoryWorkloadAnalysis
  --section ComputeWorkloadAnalysis --section Occupancy --section LaunchStats`,
  NVTX-scoped to `phase6d_step/`.
- **Pod precondition:** ncu needs `NVreg_RestrictProfilingToAdminUsers=0` (or a
  privileged container). The prior pod returned `ERR_NVGPUCTRPERM`; **a pod where
  the §9 ncu probe succeeds is a hard prerequisite** — confirm before booking GPU.

### Read these metrics (on the int4 attention kernel)
| Metric | Compute-bound | Bandwidth-bound |
|---|---|---|
| SpeedOfLight: SM% vs DRAM% | **SM% ≫ DRAM%** | **DRAM% ≫ SM%** |
| DRAM throughput (% of peak) | low | **near 100%** |
| Memory: sector/req (coalescing) | n/a | **low → uncoalesced gather** |
| Achieved occupancy | may be high | n/a |

### Decision outputs (what Test 1 hands the rest)
- **Compute-bound** → 6F kernel work (Test 3) is viable; **HBM bandwidth won't
  help**; H100's *native INT4* is the hardware lever (not its bandwidth).
- **Bandwidth-bound, uncoalesced** (low sectors/req) → the lever is a **layout /
  coalescing fix** (software, inside 6F) — *not* raw bandwidth. **This is the most
  likely + most actionable HBM-level answer (see §HBM).**
- **Bandwidth-bound, coalesced, DRAM≈100%** → raw HBM bandwidth is the wall →
  H200's HBM3e (Test 2) is the lever; 6F kernel work has a low ceiling.

### Acceptance
A recorded `PHASE_6M5_ROOFLINE_FINDINGS.md` with the SoL split + the
bound-classification verdict. **No code changed.**

---

## Test 2 — Newer-silicon hardware test (Phase 6M.6)

~1 pod-day per GPU. Run after (or alongside) Test 1.

### Goal
Does newer hardware close the gap **for free** (no code), and **by which axis**?

### Critical confound (why Test 1 must be read alongside)
H100→H200 changes **two things at once**: (a) **native low-precision compute**
(Hopper has INT/FP低-precision tensor paths A100 lacks) and (b) **HBM bandwidth**
(A100 ~2.0 TB/s → H100 ~3.35 TB/s → H200 HBM3e ~4.8 TB/s). **A throughput gain on
H200 alone cannot tell you which axis caused it.** Test 1's bound-classification
is what attributes the Test-2 gain to compute vs bandwidth. Run **both** Test 1
and Test 2; read together.

### Method (no code changes — same scripts, new hardware)
1. `phase6l_capacity_demo.py --compare --mml 8192 --max-tokens 512 --b-list 96,128`
   → does the **0.22× aggregate ratio** improve on H100? on H200?
2. `bench_phase6_d_profile_gpu.py` + `analyze_phase6d_profile.py` at the long
   config → does the **~29% attention + ~19.5% gather** share shrink?
3. If ncu is unlocked on the H100 pod, repeat Test 1's roofline there → confirms
   whether native INT4 moved the kernel off the compute wall.

### Decision outputs
- **Ratio improves materially on H100 AND Test 1 said compute-bound** → native
  low-precision is the lever; "deploy on Hopper" is a zero-NRE throughput answer.
- **Improves only on H200 (not H100)** → it was **HBM bandwidth**, not compute →
  the gap is bandwidth-bound; weigh H200 deployment vs the §HBM levers.
- **No material improvement** → throughput is structural to the int4 algorithm;
  **stop** — batch/offline density is the position, full stop.

### Acceptance
`PHASE_6M6_HARDWARE_FINDINGS.md` with the per-GPU ratio table + the
compute-vs-bandwidth attribution (cross-referenced to Test 1). **No code changed.**

---

## Test 3 — Read-path kernel fusion (Phase 6F)

**Multi-week CUDA work. GATED on Test 1 = compute- or coalescing-bound.** This is
the "fund interactive" arm. Full design already exists in
`PHASE_6F_KERNEL_OPT_DESIGN.md`; this section only sets the **entry gate, ceiling,
and guardrails** — do not start without the Test-1 green light.

### Entry gate (all must hold)
1. Test 1 verdict ∈ {compute-bound, bandwidth-bound-uncoalesced}. *(If
   bandwidth-bound-coalesced, 6F has a low ceiling — prefer Test 2 / §HBM.)*
2. The bounded ceiling (~0.27–0.30×) clears the product bar you're funding for.
3. A correctness oracle is in place (byte-eq + cosine ≥ 0.999; see Guardrails).

### Scope (per the 6F design)
Optimize the int4_packed path in the vendored `vllm-flash-attn-dev` fork: fuse the
paged gather + sidecar (scale/xmin) read + protected-K splice **into** the
attention kernel (kill the separate ~19.5% gather/copy pass), and tighten the
in-kernel dequant. **Read-path only** — the writer is already at its lower bound
(`382db51` +27%; "vectorization at lower bound, read path now bottleneck").

### Ceiling & non-goals
- **Realistic: ~0.22× → ~0.27–0.30×. NOT bf16 parity** (int4 reads more per token
  + dequants — irreducible).
- **NOT** int8-V, `n_protect` reduction, predicted-/symmetric-xmin, sidecar diet —
  all **RED for Qwen-7B** (Phase 6G.2, track CLOSED). This is orchestration/kernel
  data-movement only, never a quality/compression change.

### Acceptance metrics
- Profiler: int4-only gather/copy bucket → ≤ ~1/3 of its pre-6F share.
- End-to-end: protected agg-tps ratio improves toward the ~0.3× ceiling.
- **Correctness UNCHANGED**: byte-eq suite (`verify_phase6e_*_byte_eq`) GREEN;
  COLLAPSE=0; hard-needle (`phase6k12`) + token-agreement (`phase6j`) within noise.

### Failure risks / rollback
- Kernel surgery breaks byte-eq → **rollback** (the fork change is isolated behind
  `PHASE6E_FUSED_WRITER`-style flag; revert the kernel commit).
- Gain < ~0.05× absolute after weeks → **stop**, record, fall back to batch/offline.
- Graph-capture of the fused path is **not** required (6M.3: graphs ~neutral at
  saturation) — do not couple 6F to graph work.

---

## §HBM — "should the change be at the HBM level directly?" (the user's question)

Honest answer: **only if Test 1 says bandwidth-bound — and even then the
*actionable* HBM lever is a software layout change, not new memory hardware.**

**First, "bandwidth-bound" has two distinct meanings**, and they point at very
different fixes:

1. **Raw bandwidth saturated** (DRAM ≈ 100% of peak). *Unlikely here:* int4 reads
   roughly **half the KV bytes** of bf16 (4-bit packing) yet runs slower — if it
   were raw-bandwidth-bound it would be *faster*, not slower. So total-bytes
   pressure is probably not the wall.
2. **Effective bandwidth wasted by access pattern** (DRAM% moderate but
   **sectors/request low** → uncoalesced/scattered paged gather + sidecar reads).
   *Plausible* — the paged gather scatters across blocks and reads three separate
   sidecar tensors. Test 1's MemoryWorkloadAnalysis distinguishes (1) vs (2).

**The HBM-level levers, ranked by realism:**

| Lever | Helps if | Reality |
|---|---|---|
| **Data-layout / coalescing** (interleave nibbles + scale + xmin + protected so each block read is one contiguous, coalesced transaction) | bandwidth-bound-uncoalesced (case 2) | **The real "HBM-level" answer** — but it's a **software** change in 6F's read path, *no new hardware*. Highest-ROI if Test 1 implicates case 2. |
| **More raw HBM bandwidth** (HBM3e on H200, ~4.8 TB/s) | bandwidth-bound-coalesced (case 1) | Off-the-shelf, zero-NRE — **already covered by Test 2's H200 leg.** No custom work. |
| **HBM-PIM / processing-in-memory** (compute the dequant inside the memory stack) | compute+movement-bound, durable format | **Option-4 category** (you ruled this out): exotic, multi-year, requires the same ASIC-scale commitment; not available off-the-shelf; bets the whole stack on int4_protected being the durable KV format. **Not a near-term lever.** |

**So, directly answering "changes at the HBM level":**
- The **useful** HBM-level change is **how the bytes are laid out** so reads
  coalesce — and that lives in **software (6F)**, gated by Test 1 finding case 2.
- The **hardware** HBM change that helps is just **more bandwidth (H200 HBM3e)** —
  **already a Test-2 leg**, no custom effort.
- **HBM-PIM** is the same multi-year/$M moonshot as the custom chip you correctly
  set aside; record it as a far-horizon note, not a plan.

**Crucial gating:** none of this is actionable until Test 1 says
**bandwidth-bound**. If Test 1 says **compute-bound** (dequant arithmetic on the
SMs), *no HBM-level change helps at all* — the lever is faster low-precision
compute (H100 native INT4, Test 2) or in-kernel dequant tightening (6F). **Do not
pursue any HBM-level change before Test 1.**

---

## Ordered plan & decision tree

```
Test 1 (6M.5 roofline, ~1 pod-day, ncu-unlocked pod)   ← run first, gates all
   ├─ compute-bound ───────────────► Test 2 (H100 native INT4) + consider 6F (Test 3)
   ├─ bandwidth-bound, uncoalesced ─► 6F read-path LAYOUT/coalescing (software §HBM)
   └─ bandwidth-bound, coalesced ───► Test 2 (H200 HBM3e); 6F low ceiling

Test 2 (6M.6 hardware, ~1 pod-day/GPU)  ← read WITH Test 1 to attribute the axis
   ├─ improves (compute axis) ──────► deploy Hopper; 6F optional
   ├─ improves (bandwidth axis) ────► H200 deploy vs §HBM layout fix
   └─ no improvement ───────────────► STOP — batch/offline density is the position

Test 3 / 6F (multi-week CUDA)  ← ONLY if Test 1 greenlights + ceiling worth it
   └─ success ≤ ~0.30× ceiling, correctness GREEN ─► interactive-viable-ish; else STOP
```

## Guardrails (apply to all three)

- **No optimization is authorized by this plan.** Each test produces a recorded
  finding; funding Test 3 (6F) is a separate decision after Tests 1–2.
- **Correctness is non-negotiable**: any kernel/layout change must keep byte-eq +
  COLLAPSE=0 + needle/token-agreement within noise. A faster-but-wrong gather is a
  failure, not a win.
- **Closed tracks stay closed**: no int8-V, `n_protect`↓, xmin removal, sidecar
  diet (6G.2 RED). Throughput work is data-movement/compute only.
- **Density + quality are the proven product** regardless of outcome; throughput
  recovery is upside, and bounded (< bf16 parity by design).

## Cost summary

| Test | Effort | Prereq | Output |
|---|---|---|---|
| 1 — roofline (6M.5) | ~1 pod-day | ncu-unlocked pod | bound classification (THE gate) |
| 2 — hardware (6M.6) | ~1 pod-day / GPU | H100 and/or H200 pod | per-GPU ratio + axis attribution |
| 3 — kernel fusion (6F) | multi-week CUDA | Test 1 green + ceiling worth it | ~0.3× (not parity), correctness GREEN |

## §9 — ncu unlock probe (run before booking Test 1)

```bash
ncu --metrics sm__throughput.avg.pct_of_peak_sustained_elapsed \
    python -c "import torch; x=torch.randn(4096,4096,device='cuda'); \
torch.cuda.synchronize(); (x@x).sum().item(); torch.cuda.synchronize()" 2>&1 | tail -5
# metrics table  -> ncu works; Test 1 is runnable
# ERR_NVGPUCTRPERM -> counters locked; get a privileged pod FIRST (else Test 1 can't run)
```
