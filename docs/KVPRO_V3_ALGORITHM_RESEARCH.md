# KVPro V3 — Decode-Throughput Algorithm Research (ranking, not implementation)

> **Status:** research + ranking only. **No production code changed.** Awaiting approval before any
> implementation (Phase E plans included for the top picks only).
> **Honesty:** there is **no GPU in this analysis environment**, so **every throughput number here is
> MODELED** (roofline / first-principles) and labeled as such. The one empirical anchor is the
> **prior MEASURED decode attribution (Phase 6M.4)** cited below; it is not re-derived. No fabricated
> GPU results. Every recommendation ends in a **RunPod-measurable** benchmark (Phase E).
> This is an internal engineering document (kernel-level detail), not investor-facing material.

---

## Executive summary (read this first)

Two of the eight proposed ideas are **already shipped** in the current design — the analysis below
shows why — so implementing them would be wasted weeks. Of the rest, only the ideas that **remove
overhead the kernel does not need to do** can move throughput; ideas that **trade quality for marginal
instruction savings** are low-value given KVPro's quality-first positioning.

**Recommended to implement (top 2, unified by one principle):**
1. **In-kernel paged gather ("true" direct packed attention)** — fold the host-side paged gather +
   splice into the decode kernel (the `USE_GATHER` path already exists as a prototype). This is
   **exactly how vanilla bf16 paged attention already works**; KVPro's host-side gather-into-contiguous-
   buffers is the anomaly. Attacks the **measured ~25% "paged gather"** slice + the temp-tensor round-trip.
2. **Store-as-consumed block layout (no decode-time repack)** — lay out written pages so the kernel
   reads bytes exactly as stored (cacheline-aligned, coalesced), eliminating the per-step splice
   re-quant and scattered metadata gathers. Synergistic with #1.

Both are instances of the governing principle **"migrate query-independent work to write time"** (idea 8).

**Optional 3rd (only if B=1 latency is the commercial target):** a **B=1-specialized decode kernel**.

**Do NOT implement:** protected-K-only (**already the design** — V is unprotected), symmetric INT4
(quality risk contradicts KIVI/KVQuant; KVPro's moat is quality), layer-adaptive precision (a
density/quality knob, not a throughput lever), static protection layout (modest gain, real quality risk).

**Ceiling reminder:** the bounded decode ceiling is **~0.27–0.30× of full precision (never parity)**.
These ideas lift *toward* it; none reach parity. Strategically, KVPro's value is **capacity/quality**,
not speed — throughput work de-risks the "too slow to deploy" objection and widens the routable-workload
envelope; it does not change the core $/request-via-density story. Invest only in the best effort/gain
ideas (1, 6).

---

## Phase A — Architecture review: where decode time actually goes

### A.1 The shipped decode read path (grounded in code)
`phase5b_backend_install._read_decode_packed_batched` (B>1) and `_read_decode_packed_one` (B=1):

```
DECODE STEP (per layer, per forward)  ── query-DEPENDENT unless noted
────────────────────────────────────────────────────────────────────────────────
 1  page lookup        block_table[:, :n_blocks] slice; per-seq metadata tensors
                        (n_blocks_per_seq, last_block_idx, active_mask)           [host/meta]
 2  gather             writer.get_packed_view_batched(): ONE advanced-index gather
                        of packed K/V nibbles + sidecars from PAGED HBM into
                        CONTIGUOUS buffers (k_int4,k_scale,k_xmin,k_protect,v_*)   [HBM read+WRITE]
 3  splice (tail)      _splice_k_partial_tail_batched: RE-QUANTIZE the staging
                        buffer into the last block every step                     [compute, query-INDEP*]
 4  backing            get_bf16_backing_*: STUB (1,1,H,D) in skip mode (default)  [~free, already skipped]
 5  kernel prep        cache_seqlens int32, protect_mask_bhd, V-mode select       [host/meta]
 6  KERNEL             flash_attn_with_int4_kvcache(q, <stub bf16>, ...,
                        k_packed_int4/scale/xmin/protect_bf16, v_packed_*):
                        in registers → unpack nibbles → scale·code+xmin →
                        protect overlay → tl.dot(QKᵀ) → softmax → tl.dot(PV)      [HBM read + compute]
 7  writeback          attention output → activations                            [HBM write, small]
```

`*` The splice re-quantizes tokens already written on prior steps — **redundant recompute**; only the
newest token is genuinely new.

### A.2 Key already-shipped facts (these kill two ideas)
- **`PHASE6C_BF16_BACKING_SKIP=1` is the DEFAULT.** No full bf16 KV is reconstructed; the kernel
  **already dequantizes INT4 in-register** (Marlin-style). So the "eliminate reconstructed bf16 KV"
  half of Idea 1 is **done**. What remains is stage-2 (host gather).
- **V is never protected** (no `v_protect` anywhere). V is **already plain grouped INT4**. Idea 2
  ("protected-K only, V plain") is **the current design**, not a change.
- **In-kernel gather exists** as a Triton prototype (`USE_GATHER`, `gather_idx`) but is **not** the
  shipped decode path — the shipped path does the host gather (stage 2) instead.

### A.3 Cost model (MODELED — roofline, D=128, BS=32, bf16 sidecars)
Bytes read from HBM per prior position, per KV-head, per decode step:

| Component | Bytes/pos/head | Notes |
|---|---:|---|
| packed K nibbles | 64 | D/2, contiguous ✅ |
| packed V nibbles | 64 | D/2, contiguous ✅ |
| K scale+xmin | ~16 | (H,D) per block, amortized /BS; **asymmetric ⇒ 2 values** |
| K protect (bf16) | ~10 | n_protect≈4%·D per position; **scattered** ⚠️ |
| V scale+xmin | ~8–32 | per-token grouped; **asymmetric ⇒ 2 values** |
| **KVPro total** | **~160–185** | vs **bf16 K+V = 512** |

**The paradox that sets the whole agenda:** KVPro moves **~1/3 the KV bytes** yet runs **0.13–0.67×**
(slower). A pure-bandwidth kernel moving 1/3 the bytes should be ~3× *faster*. It is not, because:
- **(overhead 1) host gather round-trip** — stage 2 reads paged KV and **writes** contiguous buffers,
  which the kernel then **re-reads**: a full extra HBM round-trip of ~170 B/pos. This is the measured
  **~25% "paged gather"** slice, plus temp-tensor allocation churn.
- **(overhead 2) work-per-byte** — every element is unpacked, `code·scale+xmin`, protect-overlaid
  **before** `tl.dot`, vs bf16's load-and-MAC. Extra ALU + register pressure. Dominates at **B=1 /
  short context** where the kernel is **overhead/latency-bound, not bandwidth-bound**.
- **(overhead 3) scattered metadata** — scale/xmin/protect are small, poorly-coalesced reads
  interleaved with the contiguous nibble stream → wasted memory transactions.

### A.4 The measured anchor (Phase 6M.4 — MEASURED previously, cited, not re-derived)
GPU-work-bound: **paged gather ~25% + decode attention ~21%**, host syncs **<1%**. CUDA graphs neutral
at saturation (ruled out). The remaining ~54% is stages 3/5/7 + softmax + temp/metadata.
**Consequence for ranking:** host-sync elimination is a non-lever (<1%). The levers are stage-2 traffic
(overhead 1), work-per-byte (overhead 2), and scattered metadata (overhead 3).

### A.5 Two regimes (a recommendation must say which it targets)
- **Long context / saturation (bandwidth-bound):** per-token read of all prior KV dominates → reduce
  **bytes and transactions**. (worst case 0.22×.)
- **B=1 / short gen (overhead/latency-bound):** launch overhead + per-byte compute + temp allocation
  dominate → reduce **kernels, temporaries, instructions**. (short-gen 0.54×.)

---

## Phase B — Ranking the eight ideas

Scores are **0–10**. **Perf** = expected TPS gain (10 = large). **Effort** = engineering cost
(**10 = trivial/cheap**, 0 = very hard). **Rec** = overall recommendation (10 = do it). All MODELED.

### 1. Direct packed attention — **realizable form = in-kernel paged gather**
The dequant-inline half is **already shipped** (A.2). The remaining, high-value form is folding the
**host paged gather + splice** (stage 2/3) into the kernel via the existing `USE_GATHER` path, so the
kernel streams packed nibbles + sidecars **straight from paged HBM** with no contiguous intermediate.
- Throughput: **high** — removes overhead-1 (the ~25% round-trip) + temp churn; enables coalesced,
  single-pass access. Helps **both** regimes.
- Quality risk: **none** (bit-identical math; only *where* the gather happens changes).
- Compat: KVPro ✅ (same data), paged attention ✅ (this **is** how bf16 paged attn works).
- Metadata cost: **none** added (removes intermediates).
- Maintainability: medium (one Triton kernel becomes the single decode path; fewer host code paths).
- **Perf 8 · Effort 4 · Rec 9.**

### 2. Protected-K only (V plain/grouped INT4)
**Already the shipped design** — V is never protected (A.2). Nothing to build; no bandwidth left to
recover here. Included only to correct the premise.
- **Perf 1 · Effort 10 (done) · Rec 1** (no-op; do not schedule work).

### 3. Static protection layout (fixed per-head / per-layer)
Removes the per-channel `protect_slot` load + per-channel branch. But protect metadata is small and
loaded once/head (cached); decode is **not** branch-bound (A.3). Real **quality risk**: per-channel
outlier selection is the point (cf. KVQuant); coarsening to per-head/per-layer likely drops hard-tail
quality — attacks KVPro's moat for a modest kernel simplification.
- Throughput: **low** (attacks overhead-3 only, marginally). Quality risk **high**.
- **Perf 3 · Effort 6 · Rec 3.**

### 4. Layer-adaptive precision (K8/V4 · protected-K4/V4 · plain-K4/V4 per layer)
This is a **quality↔density knob**, not a throughput lever. TPS effect is **second-order and
ambiguous**: dropping protection on "robust" layers saves some sidecar bandwidth, but K8 layers
**double** K traffic; net can go either way and is model-specific. High complexity (per-layer format
dispatch, multiple kernel specializations, per-model tuning) and added metadata.
- Throughput: **low/ambiguous**. Effort: **high**.
- **Perf 3 · Effort 3 · Rec 3** (as a throughput idea; revisit only under a *density* mandate).

### 5. Symmetric INT4 (drop xmin)
Genuine throughput merit: removes the per-element `+xmin` FMA (→ single multiply) and **halves scale/xmin
metadata traffic** (attacks overhead-2/3). **But** symmetric quant on KV is a known **quality regression**:
KIVI and KVQuant both find KV distributions are **asymmetric** and per-channel/per-token **asymmetric**
scaling matters — symmetric throws that away. KVPro's entire value is quality-at-density.
- Throughput: **medium**. Quality risk: **high** (contradicts the literature *and* the product thesis).
- **Perf 5 · Effort 6 · Rec 4** — quality-gated: only if a needle/hard-needle study proves symmetric holds.

### 6. Block metadata redesign — store-as-consumed (no decode-time repack)
Lay out written pages so the kernel consumes bytes **exactly as stored**: cacheline-aligned, nibble +
sidecar interleaving matched to the kernel's access pattern, and the partial-tail already in final form
so **stage-3 splice re-quant disappears**. Attacks overhead-1 (fewer transactions), overhead-3
(coalesced metadata), and the redundant splice recompute.
- Throughput: **medium-high**; strongly **synergistic with #1** (in-kernel gather wants store-as-consumed
  to be coalesced).
- Quality risk: **none** (same values, new byte layout). Metadata cost: **neutral/lower**.
- Compat: paged attention ✅ (page = block, unchanged); requires a **snapshot/format version bump**
  (WarmTier + tier5b) — manageable.
- **Perf 7 · Effort 5 · Rec 8.**

### 7. Separate decode kernels (B=1 · low-batch · saturation)
The universal kernel compromises regimes (A.5). A **B=1-specialized** kernel (minimal launch/register
footprint, possibly persistent-kernel to amortize launch) can lift the **worst cases** (B=1 long-gen
0.22×). The saturation path already has split-K + GQA. Real but **bounded and regime-specific**, and it
multiplies kernels to maintain.
- Throughput: **medium** (targeted at the worst regime). Effort: medium (kernel proliferation).
- **Perf 5 · Effort 4 · Rec 6** — do **after** #1/#6, or as the "3rd pick" if B=1 latency is the priority.

### 8. Decode pipeline simplification — migrate query-independent work to write time
Not a distinct kernel; the **governing principle** behind #1 and #6. Concrete target: the **stage-3
splice re-quant runs every step but recomputes already-written tokens** — pure redundant work.
Amortization argument (satisfies "reduce work, don't move it"): each KV entry is **written once, read
O(gen_len) times**; moving a per-read op to write time is ~gen_len× cheaper in aggregate. Scale/xmin and
protect decisions are **already** write-time; the splice is the remaining offender.
- Throughput: **medium** (eliminates a per-step recompute). Quality risk: none.
- **Perf 6 · Effort 6 · Rec 7** — implement **as part of** #1/#6 (kill the splice), not standalone.

---

## Phase C — Literature review

| Idea | Prior art | Verdict |
|---|---|---|
| 1 In-kernel paged gather | **FlashAttention/FlashDecoding paged KV** (vLLM bf16 does exactly this in-kernel); **Marlin / QServe / Atom** fuse dequant-in-kernel for weight-quant GEMM | **Known & proven pattern**, simply not yet applied to KVPro's int4+protect+paged decode path → **high confidence it works**, low novelty, high value |
| 2 Protected-K only | **KIVI** (per-channel K, per-token V asymmetry); **KVQuant** (per-channel K) | **Already standard & already shipped** here (V unprotected). No-op |
| 3 Static protection | **KVQuant** dense-and-sparse **outlier isolation is per-channel/dynamic** | Coarsening to static per-head/layer is a **known-worse** quality trade; unlikely to be worth it |
| 4 Layer-adaptive precision | Mixed-precision KV appears in **KVQuant / “not-all-layers-equal” lines** | **Partially explored**; a density/quality knob, throughput effect unproven/second-order |
| 5 Symmetric INT4 | **KIVI/KVQuant both rely on asymmetry**; symmetric is the classic accuracy-loser for KV | **Known to be quality-risky**; contradicts the literature and the moat |
| 6 Store-as-consumed layout | Standard **kernel/data-layout co-design** (Marlin’s packed layout, FlashAttn tiling) | **Known technique**, novel *here* because KVPro currently repacks at decode; high value |
| 7 Specialized kernels | **FlashDecoding** (decode-specialized), persistent-kernel B=1 patterns | **Known**; bounded, engineering-heavy |
| 8 Write-time migration | General systems principle; **read-amortization** | **Known principle**; concretely valuable via the splice elimination |
| — CacheGen | **Storage/transport codec** (arithmetic-coded, warm-tier) | **Orthogonal** to decode throughput — not a decode-attention lever; ignore for this axis |
| — SAW-INT4 / TurboQuant | Internal comparators; SAW lost the hard tail, TurboQuant a durable negative | Confirm symmetric/aggressive-quant **quality** risk (supports skepticism on #5) |

---

## Phase D — Recommendation (ranked)

| Rank | Idea | Perf (MODELED) | Effort (10=easy) | Quality risk | Novelty | Recommendation |
|---:|---|:---:|:---:|:---:|:---:|---|
| 1 | **In-kernel paged gather** (direct packed, fold host gather+splice) | **8** | 4 | none | low (proven in bf16 PA) | **IMPLEMENT** |
| 2 | **Store-as-consumed layout** (kill decode-time repack) | **7** | 5 | none | med | **IMPLEMENT** |
| 3 | B=1-specialized kernel | 5 | 4 | none | low | **Optional** (only if B=1 latency is the target) |
| 4 | Write-time migration (splice kill) | 6 | 6 | none | — | **Fold into 1+2** (not standalone) |
| 5 | Symmetric INT4 | 5 | 6 | **high** | low | Defer — quality-gated study first |
| 6 | Static protection | 3 | 6 | **high** | low | **Do not** |
| 7 | Layer-adaptive precision | 3 | 3 | med | med | **Do not** (throughput); density-only |
| 8 | Protected-K only | 1 | 10 | — | none | **N/A — already shipped** |

**Implement only #1 and #2** (with #8's splice-kill folded in). Consider **#3** as a third *iff* the
commercial priority is B=1/interactive latency. Everything else: do not schedule.

---

## Phase E — Implementation plans (top picks only; NO code until approved)

### E.1 In-kernel paged gather (direct packed attention)

**Architecture**
```
BEFORE:  paged HBM ──host gather──▶ contiguous buffers ──▶ kernel(reads buffers) ──▶ dequant/attn
AFTER:   paged HBM ─────────────────────────────────────▶ kernel(gathers + dequant + attn in one pass)
```
- API changes: decode read passes `block_table` + writer sidecar **base pointers/strides** to the
  kernel instead of a materialized `view` dict; retire `get_packed_view_batched` + the batched splice
  from the hot path (keep for CPU reference/tests). `USE_GATHER=True` becomes the shipped path.
- Kernel changes: extend the existing `fused_protected_k_decode_attention_gather` (`gather_idx`) to
  gather packed K/V nibbles **and** the 5 sidecars per split directly from paged tensors; keep the
  in-register unpack→scale→protect→`tl.dot` math **bit-identical** to the CPU reference
  (`phase6f_read_fusion` is the oracle — reuse it for byte-eq).
- Storage changes: none (consumes existing pages). Pairs naturally with E.2.
- Benchmark plan (RunPod): `bench_phase6_batched_throughput.py` B∈{1,8,32} at mml∈{4k,16k,32k},
  int4 vs bf16 ratio via `bench_phase6_b4`; **byte-eq gate** vs the CPU reference before any timing.
- Expected GPU metrics (MODELED): DRAM read bytes/token ↓ (no contiguous-buffer round-trip); temp
  allocations →0; `nsys` "paged gather" slice (measured 25%) collapses into the attention kernel;
  achieved-occupancy stable. **Target: lift the worst-case 0.22× toward the ~0.27–0.30× ceiling — not
  parity.**
- Failure modes: (a) uncoalesced sidecar gathers if pages aren't store-as-consumed (⇒ do E.2 first or
  together); (b) register spill from gathering 5 sidecars in-kernel (mitigate: split-K tiling, load
  scale/xmin once per block into shared mem); (c) Triton int4 gather correctness — guard with the
  existing byte-eq oracle; (d) CUDA-graph capture (already eager-only; unchanged).

### E.2 Store-as-consumed block layout

**Architecture:** write path emits each page in the **exact byte order the kernel reads** —
nibble-and-sidecar interleave aligned to 128-B cachelines, partial tail already finalized (no
decode-time re-quant).
- API changes: internal writer layout + a `page_format_version`; **snapshot/WarmTier bump**
  (`tier5b_snapshot` gains versioned read; `restore_prefix` refuses mismatched versions — the guard
  already exists).
- Kernel changes: read pages as contiguous, coalesced loads; **delete the stage-3 splice** (idea 8).
- Storage changes: new on-page layout; **migration**: re-derivable from a re-prefill, or a one-time
  converter for stored WarmTier snapshots (version-gated; byte-clean verified by the tier5b gate).
- Benchmark plan (RunPod): same throughput harness + the **`verify_kvpro_snapshot_roundtrip.py`
  byte-gate** on the new format; ablate splice-kill separately to attribute its share.
- Expected GPU metrics (MODELED): higher L2/DRAM read efficiency (fewer, larger coalesced
  transactions); stage-3 CPU/GPU time →0; per-step instruction count ↓.
- Failure modes: (a) format migration bugs — gate on byte-clean roundtrip; (b) alignment padding
  could *raise* bytes/token if over-padded (measure bytes/token, keep ≤ current); (c) interaction with
  chunked-prefill/APC write paths — must emit the same layout on every write path (add a write-path
  byte-eq test like `verify_phase6e`).

### E.3 (Optional) B=1-specialized decode kernel
- Only if B=1 interactive latency is the priority. Plan: a minimal-footprint kernel (single query row,
  no batch machinery, persistent-kernel to amortize launch), sharing the E.1 in-kernel gather; A/B vs
  the universal kernel at B=1 across context lengths. Expected: lift B=1 long-gen (0.22×) most. Failure
  mode: maintenance cost of a second kernel — justify with a measured B=1 delta before committing.

---

## What I am NOT recommending, and why (explicit)
- **Protected-K only (2):** already the design (V unprotected) — zero work, zero gain.
- **Symmetric INT4 (5):** real throughput merit but **quality-risky** (KIVI/KVQuant asymmetry; KVPro's
  moat) — do a quality study *first*; do not implement blind.
- **Static protection (3)** and **layer-adaptive precision (4):** low/ambiguous throughput, quality or
  complexity cost; #4 is a density knob mislabeled as a throughput idea.

## Bottom line
Implement **in-kernel paged gather (#1)** and **store-as-consumed layout (#2)** — together they attack
the measured ~25% gather slice, the temp-tensor round-trip, the scattered-metadata transactions, and the
redundant per-step splice, and they are the only ideas that **remove GPU work KVPro doesn't need to do**
while touching **zero** quality. Add the **B=1 kernel (#3)** only if interactive latency is the goal.
Ceiling stays **~0.27–0.30×, never parity**. Awaiting approval before writing any kernel/storage code.
