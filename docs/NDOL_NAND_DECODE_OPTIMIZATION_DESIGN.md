# Design Document — NAND Acceleration via LLM-Decoding Optimization Primitives

**Working Title:** NAND-Decode Optimization Layer (NDOL)
**Author:** Rakesh Mohan, Cognade Labs
**Status:** Draft v0.3 (engineering design, pre-prototype) — re-anchored on int4_protected / prot-int8
**Scope:** Apply five LLM decoding-acceleration techniques (PAT, EQSPEC/EXSPEC speculative decoding, KVzip/FastKV, LycheeDecode, EVA) as NAND-flash storage primitives. This is a **design document**, not a patent draft — claims here are engineering hypotheses with explicit assumptions and falsifiable success criteria.

> **Changelog v0.2 → v0.3**
> - **§9 re-anchored** from the deprecated CTM+/PCAM tier-hint framing onto the shipped **int4_protected / prot-int8** KV stack. Adds the primitive→signal mapping (read-skip retained block-ids drive VSP/INCS; the protect mask drives LMTP; int4_protected blocks are the QACC payload), the write-once-read-many NAND fit, and an honest novelty position.
> - **§9.3 firmed up with a prior-art sweep (2026-06-12):** W2 (KV-on-flash + FTL) is **anticipated** (InstInfer, HiFC — do not claim); W1 (exact selection) is partially anticipated (LOUVER/vAttention are threshold-/bounded-exact, not bit-identical); **W3 (quantization-protection-structured NAND tiering) is the open, strongest wedge.** The survivable claim is the combination, led by W3 + the strict bit-identical guarantee.
> - **§8 novelty bullet rewritten** accordingly: KV-on-flash is prior art; the claim is the W3 protection-structured tiering + strict `gather == full-read`.

> **Changelog v0.1 → v0.2**
> - **§3.1 MDPC corrected.** The original `t_R + N·t_xfer` same-die formula assumed one array-sense could serve N distinct pages. It cannot. MDPC is now split into three physically-distinct mechanisms (page-dedup, multi-plane, cross-die interleave) with separate, correct formulas. The headline 4.9× now applies only to page-dedup, which is a workload property, not a free win.
> - **§2.1 added.** Explicit *operating-regime* model. Techniques do not co-apply on one workload; they win in different queue-depth regimes. This resolves the v0.1 internal contradiction where MDPC/VSP ("spare bandwidth is free") fought the "NAND is bandwidth-bound" premise.
> - **§3.2 VSP reconciled** with the random-access target workloads in §8.
> - **§3.4 LMTP**: differentiability of the HardKuma gate is now justified or dropped; baseline corrected from uniform-TLC strawman to SLC-cache heuristic.
> - **§3.5 INCS-CR corrected.** Added the missing `ops_per_byte` term; the v0.1 example silently assumed zero-cost compute and inverts to a *slowdown* once a realistic op count is applied.
> - **§5 relabeled** as a routing (best-fit) model, not a composition model.
> - **§6.5 added.** USE (Universal Synchronization Engine) integration for decentralized cross-die bus scheduling — the one place the phase-coherence formalism genuinely fits, in its *repulsive* (splay-state) form.

-----

## 0. Honest Framing

Every speedup formula in this document is **a model**, not a measurement. The constants (t_R, BW_bus, hit-rate α, compression-ratio CR, ops/byte) are realistic order-of-magnitude values from public NAND datasheets and ONFI specs, not vendor-confirmed silicon numbers. The model is meant to identify where the architectural win lives, not to predict a final benchmark. A prototype on real NAND will move every constant by 1.2–3× in either direction.

Three things this document **does not** do:

- It does not claim novelty against the in-storage-processing (ISP) prior art (Samsung SmartSSD, Eideticom NoLoad, NGD Catalina, ScaleFlux). The technical mapping is the contribution; the broader category is not.
- It does not assume a specific NAND generation. The model is parameterized so 3D-TLC, QLC, and emerging PLC-class media can be slotted in.
- It does not promise the speedups stack multiplicatively, or even that they co-apply. Composition and regime-exclusivity are addressed in §2.1 and §5 with explicit conflict analysis.

-----

## 1. The Underlying Symmetry (and its limits)

LLM decoding and NAND access share four structural properties:

| Property | LLM Decoding | NAND Access |
|---|---|---|
| **Fixed setup cost** | KV-cache fetch per step | Array read latency t_R (~25–100 μs) |
| **Bandwidth-bound** | HBM bandwidth saturates compute | ONFI bus saturates die-internal output |
| **Page-granular** | Block-paged KV (vLLM, PagedAttention) | NAND page (4–16 KB), block (multi-MB) |
| **Predictable access pattern** | Causal token order | Sequential or workload-stationary LBAs |

**Honest limit on the symmetry.** These four properties are shared by *any* memory-bound system with a setup cost — DRAM row activation, CDN cache fills, disk seeks. The symmetry is real but close to tautological: it is a *unifying lens for the Cognade portfolio* (§9), not a generator of mechanisms you couldn't reach from the NAND side directly. Accordingly, three of the five ports below (QACC, LMTP, INCS-CR) are re-derivations of pre-existing SSD techniques through an LLM vocabulary; their LLM origin is a naming overlay. The two genuinely novel angles — **codebook-reuse-with-amortization (EVA→INCS-CR)** and **learned tier placement (LycheeDecode→LMTP)** — are flagged as such throughout and are the only candidates for IP.

-----

## 2. Baseline NAND Read Model

This is the reference equation every speedup is measured against.

```
t_read_single = t_R + (P / BW_bus)
```

| Symbol | Meaning | Typical Value |
|---|---|---|
| `t_R` | NAND array read time (cells → page register) | 25 μs (SLC), 50–75 μs (TLC), 100 μs (QLC) |
| `P` | Page size (bytes transferred per read) | 4–16 KB |
| `BW_bus` | ONFI bus bandwidth per channel | 1.2–2.4 GB/s (ONFI 4.x/5.x) |
| `t_xfer` | `P / BW_bus` | ~3–10 μs |

So a single TLC read at 16 KB pages, ONFI 4.x: `t_read = 50 + 8 = 58 μs`, dominated by `t_R`.

**The key insight.** Every technique below either (a) amortizes `t_R` across more useful work or (b) replaces the read with computation closer to the data.

### 2.1 Operating Regimes (new — resolves the v0.1 contradiction)

`t_R ≫ t_xfer` always (50 µs vs 5 µs at TLC). What changes with load is *which resource is scarce*:

| Regime | Condition | Scarce resource | What wins |
|---|---|---|---|
| **Latency-bound** | low queue depth, dies idle | array time `t_R` | MDPC interleave, VSP (spare bandwidth is genuinely free here) |
| **Bandwidth-bound** | high queue depth, bus saturated | ONFI bus `BW_bus` | QACC (compress the bus), INCS-CR (don't ship raw bytes), MDPC page-dedup |

**This is the correction to v0.1.** MDPC cross-die interleave and VSP *require spare bus/die bandwidth* — they win in the latency-bound regime. QACC and INCS-CR win in the bandwidth-bound regime. They do **not** all stack on one workload at one queue depth; a speculative prefetch issued into a saturated bus *increases* mean latency. The classifier in §4 must therefore route on observed queue depth, not just access pattern. Any composite speedup claim is bounded by this: you get the latency-bound *or* the bandwidth-bound win, not both.

-----

## 3. Technique-by-Technique Design

### 3.1 PAT → Multi-Die Page Coalescing (MDPC) — **corrected**

**LLM origin:** PAT (Prefix-Aware Attention) batches queries sharing a KV prefix, using a multi-tile kernel and multi-stream forwarding to eliminate redundant KV loads.

**The v0.1 error.** The original `t_MDPC(N_same) = t_R + N_same·t_xfer` (→ 4.9×) assumed one array-sense could serve N *distinct* pages on the same die. It cannot: each distinct page requires its own `t_R`. The best a single plane offers is **cache read**, which pipelines the next array sense behind the current transfer — and since `t_R ≫ t_xfer`, that pipeline is array-bound, yielding ≈ `t_R·N`, i.e. *no speedup*. MDPC must be split into three physically-distinct mechanisms:

#### 3.1.a — Page-dedup coalescing (true sharing)

Applies only when N concurrent requests target the **same physical page**. One read serves all N (the request is deduplicated at the reorder buffer):

```
t_dedup(N) = t_R + t_xfer        (independent of N)
S_dedup    = N · (t_R + t_xfer) / (t_R + t_xfer) = N
```

At N=8 this is **8×** — but only when 8 requests genuinely want the same page. This is a *workload property* (e.g. hot metadata pages, shared RAG index blocks), not a free architectural win. Honest expectation: dedup-eligible fraction is small (<5%) on most workloads, high on read-heavy shared-index workloads (which are exactly the §8 targets — see §3.2).

#### 3.1.b — Multi-plane parallel read (N ≤ planes_per_die, typically 2–4)

When N distinct pages map to N distinct planes of one die, the die senses them in parallel (one shared `t_R`), then transfers serially:

```
t_mplane(N_p) = t_R + N_p · t_xfer        for N_p ≤ planes_per_die (2–4)
S_mplane(N_p) = N_p · (t_R + t_xfer) / (t_R + N_p · t_xfer)
```

At `N_p=4`, `t_R=50`, `t_xfer=5`: `S = 4·55 / (50+20) = 220/70 ≈ 3.1×`. **This is the formula v0.1 mislabeled as "same-die" — it is correct only up to the plane count (2–4), not arbitrary N.**

#### 3.1.c — Cross-die multi-stream interleave (the scalable mechanism)

N distinct pages on N distinct dies; `t_R` on die_i is hidden behind `t_xfer` on die_j:

```
t_interleave(N_dies) = t_R + (N_dies − 1) · t_xfer    if t_xfer ≥ t_R / N_dies
```

The condition `t_xfer ≥ t_R / N_dies` is the **die-saturation point**: above it, `t_R` is fully hidden and throughput is bus-limited. With `t_R=50 µs`, `t_xfer=5 µs`, you need `N_dies ≥ 10` to fully hide `t_R`. Realistic at SSD-class parallelism (16–32 dies), unmet at single-chip embedded NAND.

Below saturation (`N_dies < t_R/t_xfer`), the interleave is array-bound:

```
t_interleave(N_dies) = N_dies · t_R / N_dies + t_xfer ≈ t_R + t_xfer   per-request amortized
```

**Scheduling note:** the cross-die interleave is fundamentally a *phase-staggering* problem — keep each die's transfer window from colliding on the shared bus. This is where USE applies (§6.5). It is the one MDPC sub-mechanism with a real phase-coherence mapping.

**Implementation:**
- Controller-side request reorder buffer keyed on `(die_id, plane_id, block_id, page_addr)`. The `page_addr` key is what enables 3.1.a dedup.
- Coalescing window: 10–50 μs (a fraction of `t_R`), tunable per QoS tier.
- Falls back to single-issue under low load.

**Design risk:** Coalescing introduces head-of-line latency for the first request in the window. Mitigate with a hard deadline (release immediately if window expires).

-----

### 3.2 EQSPEC/EXSPEC → Verified Speculative Prefetch (VSP)

**LLM origin:** A small draft model generates K candidate tokens; the main model verifies them in parallel. EQSPEC guarantees output-equivalence under batching.

**NAND analog:** A lightweight predictor (n-gram on LBAs, or an ML stride detector) issues prefetch reads for the next K LBAs. When the real request arrives, the controller checks if the requested LBA is in the prefetch buffer; if yes, serve from buffer; if no, fall through to normal read.

**Formula 3.2.1 — Expected read latency** (valid only in the latency-bound regime, §2.1, where prefetch transfer is hidden on idle dies):

```
E[t_VSP] = α · t_xfer + (1 − α) · (t_R + t_xfer) = t_xfer + (1 − α) · t_R
```

where `α` = prefetch hit rate.

**Speedup vs. baseline:**

```
S_VSP = (t_R + t_xfer) / [t_xfer + (1 − α) · t_R]
```

At α=0.7: **2.75×**; α=0.9: **5.5×**; α=0.5: **1.83×**.

**Reconciliation with §8 target workloads (new).** α=0.7–0.9 is a *sequential/strided* hit rate. The §8 targets — vector search, RAG retrieval, encrypted search — are **random-access** at the LBA level, where a stride predictor collapses to α≈0.1–0.3 (→ S_VSP ≈ 1.1×). VSP is therefore **not** a general primitive for those workloads. It applies to the sequential sub-streams only (log scans, columnar block sweeps, prefetchable index walks). **Crucially**, the random-access shared-index workloads where VSP *fails* are exactly where MDPC-3.1.a page-dedup *succeeds* (many queries hitting the same hot index pages) — the two techniques are complementary across the workload, not competing on it.

The EQSPEC equivalence guarantee translates to a **data-integrity invariant**: the controller must verify the prefetched LBA matches the requested LBA before serving (1-cycle comparator). On mismatch, discard buffer and issue real read — no correctness compromise, only wasted bandwidth.

**Cross-die scheduling trick:** Issue speculative reads only to idle dies, never blocking a real request — the direct analog of EQSPEC's cross-batch scheduling trick. Wasted speculative work is bounded by idle-die bandwidth. **But note (§2.1):** "idle-die bandwidth is free" holds *only* in the latency-bound regime. Under bus saturation there are no idle dies and VSP must be throttled to zero. The §6.5 USE scheduler enforces this automatically (speculative reads are soft oscillators that only fill bus gaps).

**Design risk:** Bad predictor wastes bandwidth and increases write-disturb on prefetched blocks. Cap speculative issue rate at idle-die capacity; demote predictor when α drops below threshold.

-----

### 3.3 KVzip / FastKV → Query-Agnostic On-Controller Compression (QACC)

**LLM origin:** KVzip compresses KV cache to support any future query (query-agnostic), achieving 3–4× reduction.

**NAND analog:** Compression on write, decompression in the controller's hardware path on read. The novelty is **query-agnostic block-level compression with preserved random access** — most existing SSD compression assumes sequential workloads.

**Formula 3.3.1 — Effective bandwidth:** `BW_eff = BW_bus · CR`

**Formula 3.3.2 — Net read latency (controller decompression in pipeline):**

```
t_QACC = t_R + (P / (BW_bus · CR)) + t_decompress + t_indirect
       = t_R + t_xfer / CR + t_decompress + t_indirect
```

**New term `t_indirect`.** Variable-length compressed blocks break fixed page alignment, so random access needs a logical→physical indirection lookup. If that lookup misses the controller's mapping cache it costs an extra metadata sense (~`t_R`). Budget `t_indirect ≈ 0` on mapping-cache hit, `≈ t_R` on miss. v0.1 omitted this; it is the reason naïve compression hurts random-access workloads.

**Net win condition:** `t_decompress + t_indirect < t_xfer · (1 − 1/CR)`.

At CR=3, t_xfer=10 µs: decompress+indirect budget = `10·(2/3) = 6.7 µs`. Achievable with an LZ4/Zstd hardware decompressor (~1–3 µs/16 KB page) *only if* the indirection stays cache-resident.

**Speedup:** `S_QACC = (t_R + t_xfer) / (t_R + t_xfer/CR + t_decompress + t_indirect)`. At t_R=50, t_xfer=10, CR=3, t_decompress=3, t_indirect=0: `S = 60/56.3 ≈ 1.07×`.

**Honest read (unchanged from v0.1):** Compression dominates only when `t_R` is small (SLC) or `P` is large. QACC's real value is **density and endurance** (fewer P/E cycles per logical byte), not latency — exactly KVzip's lesson in the LLM context. **No USE mapping.**

-----

### 3.4 LycheeDecode → Learnable Multi-Tier Placement (LMTP) — **baseline & gate corrected**

**LLM origin:** LycheeDecode uses a HardKuma-gated mechanism to partition attention heads into "retrieval" vs "sparse" roles.

**NAND analog:** SLC/TLC/QLC tier placement, learned per-LBA-range. Hot retrieval-heavy ranges → SLC; cold sparse ranges → QLC.

**Formula 3.4.1 — Expected access time:**

```
E[t_LMTP] = p_hot · (t_R^SLC + t_xfer) + (1 − p_hot) · (t_R^QLC + t_xfer)
```

**Corrected baseline.** v0.1 compared against *uniform TLC* (E=55 µs) and claimed 1.05×. No shipping SSD is uniform-TLC; they all run an SLC cache with heuristics (recent/small writes, LRU). The honest baseline is that heuristic, which already captures most of the tier gap. The defensible claim is therefore **not** a latency multiple over uniform-TLC, but a **marginal hit-rate lift of the learned gate over the heuristic** — currently unquantified and the single most important thing P1 must measure. Provisional target: ≥3% absolute lift in `p_hot` at fixed SLC capacity.

**Formula 3.4.2 — gate.** v0.1 specified a differentiable HardKuma gate but *also* mitigated cost by training **offline** and shipping parameters monthly. If training is offline-batch, differentiability buys nothing at inference — and a 2-parameter-per-range HardKuma is strictly weaker than a gradient-boosted classifier on the same access features. **Decision: drop HardKuma; use an offline-trained GBDT/logistic gate** over features `{recency, read/write ratio, access entropy, range size}`:

```
g(LBA_range) = classifier(features) ∈ [0,1];   place in SLC iff g > θ_tier,  s.t. Σ size ≤ SLC_capacity
```

Retain HardKuma **only if** P1 shows a need for *online, in-firmware* adaptation (where the differentiable, annealed gate earns its keep); otherwise it is aesthetic symmetry, the same mistake §1 warns against. **No USE mapping** (this is classification, not phase alignment).

**Design risk:** Online training in firmware is expensive. Mitigation: train offline on telemetry, ship gate parameters as a workload profile, update monthly.

-----

### 3.5 EVA → In-NAND Computational Storage with Codebook Reuse (INCS-CR) — **compute term corrected**

**LLM origin:** EVA transforms memory-bound GEMV into amortized GEMM by reusing a codebook for vector quantization (11.17× speedup, 7.17× energy efficiency).

**NAND analog:** Push filter/scan/aggregate into the controller's compute fabric. Keep a small codebook (predicate LUT, hash buckets, quantization centroids) in controller SRAM. Stream pages through the codebook; return only the result, never the raw page.

**Formula 3.5.1 — Without ISP:** `t_no_ISP = (D_total / BW_bus) + t_compute_host`

**Formula 3.5.2 — With INCS-CR (corrected):**

```
t_INCS = max( t_compute_NAND , D_total / BW_internal ) + (D_result / BW_bus)

where  t_compute_NAND = D_total · ops_per_byte / GOPS_fabric      ← the term v0.1 omitted
```

**Why this matters.** v0.1 set `t_compute_NAND = D_total / 8 GB/s = 125 ms`, which assumes the fabric keeps pace with an 8 GB/s stream at **zero ops/byte**. But the spec'd fabric is **1–10 GOPS**, and a real filter/distance/scan is several ops/byte. Re-running the 1 GB scan with `ops_per_byte = 4`, `GOPS_fabric = 10`:

```
t_compute_NAND = 1e9 · 4 / 10e9 = 400 ms
t_INCS = max(400, 125) + 5 = 405 ms
t_no_ISP = 500 + 50 = 550 ms
S_INCS = 550 / 405 ≈ 1.36×        (not 4.2×)
```

And at `ops_per_byte ≥ 5.5`, `t_compute_NAND > t_no_ISP` and INCS-CR becomes a **net slowdown**. So the correct statement is sharper than v0.1's: **INCS-CR wins only when the per-byte op count is low enough that the fabric out-streams the host bus** — i.e. cheap predicates and codebook lookups, not arithmetic-heavy kernels. The codebook-reuse insight is precisely what *keeps `ops_per_byte` low* (replace per-element compute with one SRAM lookup), so the corrected model actually strengthens the EVA framing — but the win is `≈1.3–2×` on cheap-op scans, `4×+` only when `ops_per_byte ≤ 1` AND the host is genuinely bandwidth-starved. The unbounded-`A_BW` aggregate case (scalar result) survives intact.

**Bandwidth amplification factor:** `A_BW = D_total / D_result` (filter keeping 1% → 100; scalar aggregate → effectively unbounded). This is the real lever; the compute bound above is the gate on whether you get to pull it.

**Codebook-reuse insight (unchanged):** keep the lookup structure resident, amortize across many pages. With 1–10 MB SRAM, codebooks of that size serve vector-search (centroid distance), JSON filter (path→offset table), encrypted-search (Bloom over ciphertext digests).

**Design risk:** Programmability/ABI. Target the **NVMe Computational Storage** spec; expect 18 months of standards lag vs. a Cognade-specific interface. **No USE mapping.**

-----

## 4. Combined Architecture

```
                   ┌───────────────────────────────────────────────────┐
                   │              Host / NVMe Submission Q             │
                   └─────────────────────┬─────────────────────────────┘
                                         ▼
              ┌──────────────────────────────────────────────────────┐
              │              NAND-Decode Optimization Layer          │
              │  ┌────────────────────────────────────────────────┐  │
              │  │ Request Classifier (telemetry + QUEUE DEPTH)   │  │  ← routes on regime (§2.1)
              │  └─────┬───────────┬───────────┬──────────┬───────┘  │
              │        ▼           ▼           ▼          ▼          │
              │   ┌────────┐  ┌────────┐  ┌────────┐ ┌────────┐     │
              │   │  MDPC  │  │  VSP   │  │  LMTP  │ │ INCS-CR│     │
              │   │ (PAT)  │  │(EQSPEC)│  │(Lychee)│ │ (EVA)  │     │
              │   └───┬────┘  └───┬────┘  └───┬────┘ └───┬────┘     │
              │       └────────┬──┴───────────┴──────────┘           │
              │                ▼                                      │
              │  ┌────────────────────────────────────────────────┐  │
              │  │ USE phase scheduler (splay-state die arbiter)  │  │  ← §6.5, repulsive Kuramoto
              │  └────────────────────────────────────────────────┘  │
              │  ┌────────────────────────────────────────────────┐  │
              │  │  QACC compression/decompression pipeline       │  │
              │  └────────────────────────────────────────────────┘  │
              └─────────────────────┬─────────────────────────────────┘
                                    ▼
              ┌──────────────────────────────────────────────────────┐
              │       NAND Die Array (multi-die, multi-plane)        │
              └──────────────────────────────────────────────────────┘
```

The classifier routes each request to the techniques that benefit it *and the regime it observes*. Routes are largely mutually exclusive (a request served from VSP buffer skips MDPC). The few that compose: LMTP+QACC always compose; INCS-CR composes with QACC iff compute reads from the decompressed buffer.

-----

## 5. Routing Model (renamed — this is not a composition model)

For a workload with mixed access patterns, the expected per-request latency under **best-fit routing**:

```
t_avg = p_dedup     · t_dedup
      + p_interleave · t_interleave
      + p_spec       · E[t_VSP]
      + p_compute    · t_INCS
      + p_remainder  · (t_R + t_xfer/CR + t_decompress + t_indirect)    ← LMTP-routed, QACC-compressed
```

with `Σ p_i = 1`, each `p_i` learned from telemetry. **This is a partition/routing model: each request takes exactly one path. It does NOT model composition** (e.g. VSP and MDPC contending for die-time — §6.6/§7-Q6). True interaction is captured only by the USE scheduler's contention term, not by this weighted sum. Rename accordingly in any external deck.

**Honest envelope:** No combination exceeds the EVA-class ceiling, and the corrected §3.5 lowers even that. Realistic end-to-end:
- INCS-CR-heavy, cheap-op, bandwidth-starved host: **2–3×** (was 3–5×).
- I/O workloads, latency-bound, with page-dedup opportunity: **2–4×** dominated by MDPC-3.1.a + interleave.
- I/O workloads, no dedup, no compute pushdown: **1.3–2×**.

-----

## 6. Validation Plan

| Phase | Vehicle | Success Criterion | Time |
|---|---|---|---|
| **P0** | Pure analytical model, vary all constants | Identify (workload, NAND-gen) combos where each technique wins by ≥1.5×; confirm corrected §3.1/§3.5 break-even points | 2 weeks |
| **P1** | Trace-driven simulator (FEMU or MQSim) | Reproduce per-technique speedups within ±20% of analytical model; **measure LMTP lift over SLC-cache heuristic** | 6 weeks |
| **P2** | FPGA prototype on Xilinx Versal + NAND emulator | End-to-end at 1 GB/s sustained, ≥2× vs. baseline on selected workloads; USE scheduler holds p99 bus-collision rate <1% | 6 months |
| **P3** | Partnership with SmartSSD vendor (NoLoad / ScaleFlux) | Real-NAND validation | 12+ months |

**Hard kill criteria at P1:** if simulator shows <1.3× on any technique under realistic α, p_hot, CR, ops_per_byte → drop from combined design. Specifically: drop INCS-CR if `ops_per_byte` for target workloads exceeds the break-even of §3.5; drop VSP if random-access α < 0.4.

### 6.5 USE Integration — Decentralized Cross-Die Bus Scheduling (new)

**This is the one place the Universal Synchronization Engine formulas genuinely apply.** Of the five techniques, only MDPC's cross-die interleave (§3.1.c) — and, via the same machinery, the §7-Q6 VSP↔MDPC arbiter — is a *phase-alignment* problem. QACC, LMTP, and INCS-CR are not, and forcing them onto the phase formalism would be the aesthetic-symmetry error §1 warns against.

**The mapping (with the necessary sign flip).** Model each of N dies as an oscillator. Its phase `φ_i ∈ [0, 2π)` is its position within its read cycle of period `T = t_R + t_xfer`. The die's **transfer window** — when it contends for the shared ONFI bus — occupies a fraction `δ = t_xfer / T` of the cycle. Bus collision occurs when two transfer windows overlap.

The optimal schedule spreads the windows evenly so the bus is continuously utilized but never contended: the **splay state**, `φ_i = 2πi/N`. Crucially, the splay state is the state of **minimum** phase coherence (order parameter `r → 0`). USE's engine *maximizes* coherence (U2), so the die scheduler runs USE **in reverse — repulsive coupling**:

| USE primitive | Original (coherence-max) | NDOL die scheduler (collision-min) |
|---|---|---|
| **U1** Pairwise correlation | `C[i,j] = (1/W)·Σ_k cos(φ_i(t-k) − φ_j(t-k))` | identical — measures how often die i and j share bus-phase |
| **U2** Total objective | maximize `C_total = Σ_{i<j} C[i,j]` | **minimize** `C_total` (spread the windows) |
| **U3** Gradient | `∂C_total/∂φ_i = −Σ_{j≠i} sin(φ_i − φ_j)` | identical gradient, opposite step |
| **U4** Update | `Δφ_i = α·(−Σ_{j≠i} sin(φ_i − φ_j))` (ascent) | **`Δφ_i = +α·Σ_{j≠i} sin(φ_i − φ_j)`** (descent → splay) |
| **U5** Convergence | `\|ΔC_total\| < ε` for T iters | identical — "schedule stabilized" |

The repulsive update's stable fixed point under all-to-all coupling is exactly the even-spaced splay state `φ_i = 2πi/N` — which is the optimal interleave schedule of §3.1.c. Convergence (U5, `ε=0.001`, T=10) maps directly to "the die-issue schedule has settled."

**Why use USE here instead of round-robin?** For small, static, homogeneous N, round-robin (`φ_i = 2πi/N` by construction) is simpler and you do **not** need gradient descent. USE earns its place precisely when:
1. **Dies are heterogeneous** — mixed SLC/QLC tiers (per §3.4) have different `T_i`, so equal phase spacing is *not* equal window spacing. The coupling weights become `w_ij ∝ δ_i·δ_j` and the fixed point is a *weighted* splay the closed form doesn't give you.
2. **The workload is dynamic** — dies enter/leave the active set as ranges heat/cool; USE re-converges continuously without recomputing a global schedule.
3. **The controller is itself multi-channel/peer-to-peer** — USE's defining property (U4: "no master-slave, fully peer-to-peer") matches a controller where each channel sequencer adjusts its own phase from local pairwise observations, with no central arbiter. This is the genuine architectural fit.

**Resolving §7-Q6 (VSP↔MDPC contention) with the same field.** Add speculative reads as *soft* oscillators with reduced coupling weight `w_spec ≪ w_real`. They are repelled out of real transfer windows but free to occupy the gaps — i.e. they automatically fill idle bus-phase and yield instantly under saturation (§2.1). This is the arbiter §7-Q6 asked for, and it is the EQSPEC "schedule speculation only on idle dies" trick expressed as a phase constraint.

**Honest caveats.** (a) The continuous-phase relaxation assumes windows small vs. cycle (`δ < 1/N`); for `δ·N > 1` the bus is fundamentally oversubscribed and no scheduler helps — that is the §2.1 bandwidth-bound wall, correctly. (b) Heterogeneous-weight convergence is not proven stable; it is a P1 research item analogous to LMTP's HardKuma stability (§7-Q4). (c) The USE port is the **only** cross-portfolio formula reuse claimed here; do not over-extend it.

### 6.6 Composition conflicts (was §7-Q6, now scheduled)

VSP's speculative reads compete with MDPC's coalescing window for die-time. **Resolved by §6.5**: both are oscillators in one phase field; the repulsive coupling + soft-weight speculation gives a single decentralized arbiter rather than two competing schedulers.

-----

## 7. Open Questions / Honest Unknowns

1. **MDPC coalescing window vs. tail-latency.** What window keeps p99 acceptable while still capturing 3.1.a dedup and 3.1.b multi-plane opportunities? Empirical; needs trace data.
2. **VSP predictor on random access.** On §8 targets, can any predictor lift random-LBA α above 0.4? If not, VSP is sequential-substream-only and MDPC-3.1.a carries the shared-index case.
3. **QACC at QLC/PLC density.** With `t_R → 150 µs`, even CR=4 yields no latency win. Confirmed density-only play below TLC.
4. **LMTP gate choice & training stability.** Does the offline GBDT gate (§3.4) beat the SLC-cache heuristic by the ≥3% target? Only revert to online HardKuma if firmware-side adaptation proves necessary — then solve gate-collapse with annealing + capacity-aware regularization.
5. **INCS-CR ABI + ops/byte profiling.** Measure real `ops_per_byte` for vector-search/JSON-filter/encrypted-search; confirm they sit below the §3.5 break-even. Target NVMe Computational Storage interface despite the standards lag.
6. **USE scheduler stability under heterogeneous dies.** §6.5(b) — prove or bound convergence of the weighted repulsive coupling.

-----

## 8. What This Does Not Claim

- Not that combining all five achieves the product of individual speedups. Composition is sublinear, regime-exclusive (§2.1), and conflict-bound (§6.5).
- Not novelty over the ISP category, the generic primitives, or KV-on-flash itself. MDPC/VSP/QACC as *generic* storage techniques are prior art (FTL scheduling, ML-prefetch, ScaleFlux inline compression), and **KV offload to a flash/FTL tier is anticipated by InstInfer and HiFC** (see §9.3 W2 — do not claim it). The defensible novelty (if pursued for IP) is the **W3 wedge foregrounded in §9.3**: *quantization-protection-structured KV placement across NAND tiers (protected channels → SLC, 4-bit bulk → QLC), co-designed with a strict bit-identical `gather == full-read` read-skip* — the protection-structured tiering had no direct prior art in the 2026-06-12 sweep, and the strict bit-identical selection is stronger than the threshold-exact forms (LOUVER, vAttention). The USE→splay scheduler is novel cross-portfolio reuse, not a novel scheduler per se (repulsive Kuramoto / desynchronization splay states are known — cf. DESYNC, IPSN'07).
- Not any specific NAND vendor controller. Assumes a programmable-controller class (NVMe Computational Storage compliant) with 1–10 MB SRAM and 1–10 GOPS compute fabric.
- Not a market commitment. Best-fit: vector search, RAG retrieval, columnar analytics scan, encrypted search — not transactional OLTP, not bulk media.
- **Best-fit workloads carry an important asymmetry**: they are random-access (VSP-hostile) *and* shared-index (MDPC-dedup-friendly). Design accordingly.

-----

## 9. Connection to Cognade Symbol-U Portfolio — anchored on int4_protected / prot-int8

This is a **storage-layer extension anchored on the shipped int4_protected KV-cache stack.** The earlier CTM+/PCAM tier-hint framing is deprecated and explicitly *not* the anchor here.

- **Compute:** USE (synchronization), SCC (coherence), BCVF (control)
- **Cache:** **int4_protected / prot-int8** — quality-preserving KV quantization (1.78–1.83× density, bf16-parity, greedy bit-identical across Llama-3.1-8B / Qwen2.5-7B / Mistral-7B-v0.3) **+ attention-guided read-skip** (bounded retained block-set; `gather == full-read`, output-identical, GPU-verified)
- **Storage:** *gap — this document fills it*

**Why int4_protected is the right anchor.** It already supplies the two signals a NAND tier needs and that a generic block device cannot derive from LBA traces:

1. **A model-internal access signal** — read-skip's attention-guided **retained block-ids**: which KV blocks decode will actually gather next.
2. **A correctness invariant** — `gather == full-read`, **bit-identical**. This is the true EQSPEC port: verified speculation backed by a *proven output-equivalence guarantee*, not best-effort prefetch with a comparator.

It also has a media-friendly physical shape: KV is laid out in **fixed blocks (≈1280 B) with a per-block dequant sidecar, ×32 layers**, tens of thousands of blocks — already page-like.

### 9.1 Primitive → int4_protected signal mapping

| NDOL primitive | int4_protected / prot-int8 signal that drives it | Notes |
|---|---|---|
| **QACC** (§3.3) | Store the **int4_protected blocks themselves** on NAND; the per-block dequant sidecar is the indirection metadata | Not generic zlib — quality-preserving KV quant at 1.78× with bf16-parity. Compression *with a correctness guarantee*. |
| **LMTP** (§3.4) | **Protected channels → fast tier (SLC); 4-bit/8-bit bulk → dense tier (QLC)**, keyed on the per-model calibration mask | The protect mask *is* the learned tier signal; replaces the deprecated HOT/WARM/COLD hint source. |
| **VSP** (§3.2) | **read-skip retained block-ids → prefetch exactly those blocks** | α is attention-driven, not stride-driven; inherits `gather == full-read` → *verified* speculative storage. |
| **INCS-CR** (§3.5) | Push the **read-skip gather into the storage layer** — emit only retained blocks across the bus | The retained-index is the EVA "codebook." A_BW ≈ full-attention / retained-set (≈16× at 32K, ~94% skip). |
| **MDPC** (§3.1) | Batch per-layer / per-head block reads | Mechanical; no novelty. |

### 9.2 Why KV-on-NAND is a good media fit

KV-cache is **write-once at prefill, read-many at decode** — no random writes, low write-amplification, low P/E wear. NAND's worst property (write endurance) is precisely the one this workload does not stress, which is why a flash KV tier is more defensible here than for general storage. (Contrast: the DRAM/CPU-offload literature ignores flash physics entirely.)

### 9.3 Honest novelty position (prior-art search done — read before any IP filing)

Long-context KV offload is a **crowded** arena. A targeted prior-art sweep (2026-06-12) assessed three candidate wedges. Summary: **one is dead, one is partial, one is open — and the only survivable claim is their combination, foregrounding W3.**

**W1 — exact / output-equivalent attention-guided selection (`gather == full-read`).** *Partially anticipated (med confidence).* The mainstream KV-sparsity work is explicitly **approximate** and accepts accuracy loss — Quest (ICML'24), InfiniGen (OSDI'24), H2O (NeurIPS'23), SnapKV, Scissorhands, ShadowKV. "Exact-via-selection" is now an active idea but in weaker forms: **LOUVER** (sparse attention as range search, *threshold*-exact / zero-false-negative w.r.t. a similarity threshold — not bit-identical), **vAttention "Verified Sparse Attention"** (bounded-error/statistical verification), RetrievalAttention / PQCache / VeriCache (exact attention over an *approximately* selected subset). **A strict bit-identical `gather == full-read` selection was not found published as such** — this strict form is the differentiator, but it is a narrow gap.

**W2 — KV offload to NAND/flash with FTL / flash-physics co-design.** ***Anticipated — near-exact hits, high confidence. Do NOT claim this.*** **InstInfer** (arXiv 2409.04992) does in-storage attention on flash with a KV-oriented FTL; **HiFC** stores KV in **pseudo-SLC** regions for ~8× endurance. Also KVNAND, HILOS, Dual-Blade. (Mooncake/LMCache use SSD as opaque blocks — not flash-physics — so they are *not* the threat here; InstInfer/HiFC are.) The flash + FTL + endurance + SLC-tiering frame is firmly prior art.

**W3 — tiering KV by quantization-PROTECTION structure across SLC/TLC/QLC.** ***Open / weakly anticipated — the strongest wedge (med confidence).*** Two adjacent literatures exist but were **not found combined**: (a) precision-/channel-sensitivity-aware KV quant that splits high-precision channels from low-bit bulk — MixKVQ, KVmix, KIVI, ShadowKV's BF16 outlier channels — but places everything in HBM/DRAM; (b) flash tiering by access *temperature* (InstInfer, HiFC hot/warm/cold) — but **not** by protection structure. Mapping *protected channels → reliable tier, 4-bit bulk → dense QLC* has no direct prior art found.

*W3 has two halves, quantified in `ndol/sim/`:*
- *Capacity (robust, unconditional).* Analytical density model: int4_protected (~1.8× over bf16) × QLC bulk packing ⇒ **~1.23× more KV tokens on top of int4_protected, ~2.22× vs bf16-on-TLC** at preserved quality (φ=0.25 protected bit-fraction). Monotone in bulk fraction; no access-pattern dependence. **This is W3's real value.**
- *Latency (conditional).* MQSim-measured: protect-mask tiering is a latency win **only when protected/hot reads dominate read volume** (measured 1.33× hot-dominated; 0.79× — a loss — bulk-dominated). Do not claim a tiering latency speedup unconditionally.
- *Nuance:* for capacity the protected bits want **TLC** (SLC's 1 bit/cell wastes density); for latency the hot reads want **SLC**. The protect mask is the placement *signal*; the target tier depends on the objective. The objective-independent win is **bulk → QLC**.

**Narrowest defensible claim:** the **combination** — *precision-protection-structured KV placement across NAND tiers (W3), co-designed with a strict bit-identical (not threshold-approximate) read-skip gather (W1), on a flash/FTL tier (W2).* Lead with **W3 + the strict bit-identical guarantee**; W2 alone is dead (InstInfer/HiFC), W1's threshold-exact form is taken (LOUVER/vAttention). No single paper hits the full W1+W2+W3 combination.

*Caveat: several citations rest on abstracts/landing pages (arXiv full-text 403'd during the sweep) and the newest preprints are arXiv-only; have counsel verify InstInfer's FTL claims and W3's absence against full text before filing.*

*Sources: InstInfer (2409.04992), HiFC (OpenReview 2024), KVNAND (2512.03608), HILOS (2502.09921), Dual-Blade (2604.26557), InfiniGen (OSDI'24), Quest (2406.10774), ShadowKV (2410.21465), Mooncake (2407.00079), LOUVER (2605.06763), vAttention (2510.05688), RetrievalAttention (2409.10516), VeriCache (2605.17613), MixKVQ (2512.19206), KVmix (2506.08018).*

### 9.4 USE → die scheduler (unchanged)

The peer-to-peer USE phase-synchronization engine is reused, in its repulsive/splay form, as the decentralized cross-die bus arbiter (§6.5) — the first time a USE primitive reaches the storage tier.

**Architectural value beyond per-technique speedups:** NDOL turns the **int4_protected block + read-skip retained-set + protect mask** into the unifying access vocabulary across the memory hierarchy, with the USE phase formalism as the shared scheduler — extending a *shipped, quality-preserving* KV stack down to NAND rather than re-deriving generic SSD techniques.

-----

*End of design document v0.3. Next iteration after P0 analytical sweep.*
