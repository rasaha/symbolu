# KVPro — Sidecar Tax & Protected‑Channel Speed Mitigation (technical addendum)

**Audience:** internal engineering / technical due‑diligence under NDA. **Not** investor‑facing
(kernel‑level detail). **Companion to:** `KVPRO_V3_ALGORITHM_RESEARCH.md`,
`experiments/kvpro_v3_symmetric_residual/SPEC.md`, Phase 6N prot‑int8.
**Every number labeled:** MEASURED · MODELED (roofline/accounting) · SHIPPED · PROPOSED.

> **Why this doc exists.** Two questions must be answered before the density and throughput numbers
> can be trusted: (1) **the "sidecar tax"** — why pure INT4 should give 4× but KVPro nets ~1.8×; and
> (2) **the speed cost of storing the top‑k% key channels in bf16**, and what actually mitigates it.

---

## 1. The sidecar tax, defined

Pure 4‑bit KV *should* be **4×** smaller than bf16. KVPro nets **~1.8×**. The gap is two erosion
layers:

- **Layer 1 — metadata/sidecar bytes (this doc):** the per‑block scales, per‑block/per‑token
  minimums (`xmin`), and the higher‑precision protected‑channel store ride alongside the 4‑bit
  codes. These erode **4× → ~3×** at the bytes‑per‑token level.
- **Layer 2 — system/allocation overhead:** paged‑block padding, over‑provisioning, and the fact
  that freed HBM is shared with weights/activations erode **~3× → ~1.8× net** (the deployed number).

This addendum attacks Layer 1 and the speed penalty; Layer 2 is a serving‑allocation matter.

---

## 2. Quantified breakdown (MODELED — accounting; D=128, BS=32, 4% protect, bf16 sidecars)

Bytes per token, per KV‑head, per layer (corroborated by `KVPRO_V3_ALGORITHM_RESEARCH.md` §A.3 and
the `symmetric_residual` SPEC's 172 B affine baseline):

| Component | Bytes | Note |
|---|---:|---|
| Packed K nibbles | 64 | D/2, contiguous ✅ |
| Packed V nibbles | 64 | D/2, contiguous ✅ |
| K scale + K xmin | ~16 | per‑block; **asymmetric ⇒ 2 values** |
| V scale + V xmin | ~16 | per‑token, per‑group; **un‑amortized** |
| K protect (bf16, ~4%) | ~10 | **scattered ⚠️** |
| **KVPro total** | **~170** | vs **bf16 K+V = 512** |

**The sidecar tax ≈ 42 B** — about **25% of KVPro's footprint**, or **+33% on top of the bare
codes**. Two structural offenders:
- **`xmin` (asymmetry):** doubles the scale metadata. Dropping both `xmin` streams removes **~9.3%**
  of read bandwidth (`symmetric_residual` SPEC: 172 → 156 B; one `xmin` alone ≈ 4.65%). MODELED.
- **The protected bf16 channels:** small in *bytes* (~10 B) but **scattered** across ~4% of
  channels — so they cost far more in memory **transactions/latency** than their byte count implies.
  This is the crux of the speed question (§4).

---

## 3. Why the protected bf16 channels hurt *speed* more than *size*

KVPro moves ~1/3 the bytes of bf16 yet decodes at **0.13–0.67× bf16** (MEASURED). A pure‑bandwidth
kernel moving 1/3 the bytes should be ~3× *faster*. It isn't, because the protected‑bf16 path adds
three overheads (attribution MEASURED in Phase 6M.4; ranking MODELED):

1. **Scattered metadata (overhead‑3):** the ~4% protected channels and their sidecars are
   poorly‑coalesced reads interleaved with the contiguous nibble stream → wasted memory
   transactions.
2. **Work‑per‑byte (overhead‑2):** every element is unpacked, `code·scale + xmin`, then
   **overlay‑selected** (`where(mask, protected_bf16, dequant)`) *before* the matmul — extra ALU +
   register pressure. Dominates at B=1 / short context (latency‑bound).
3. **Host gather round‑trip (overhead‑1, ~25% MEASURED):** the current path gathers paged KV +
   protected channels into contiguous buffers that the kernel then re‑reads — a full extra HBM
   round‑trip.

So the bf16 top‑k% is not primarily a *bandwidth* cost; it is a **transaction‑pattern and
work‑per‑byte** cost. Mitigations must target those, not just byte count.

---

## 4. Mitigations — reduce the sidecar tax (bytes)

| Mechanism | Effect on tax | Status | Quality risk |
|---|---|---|---|
| **prot‑int8** — store protected channels int8, not bf16, via calibration‑derived static per‑channel asymmetric scale (`(kmax−kmin)/255`, margin‑widened) | protect sidecar **10 B → 5 B** | **SHIPPED** (flag; Phase 6N) — greedy **bit‑identical** flag‑ON vs OFF on Llama‑3.1‑8B / Qwen2.5‑7B / Mistral‑7B | **None measured** |
| **Symmetric residual** — drop `xmin`, keep protected channels exact | **−9.3%** bytes (both `xmin`); −4.65% (one) | PROPOSED (`symmetric_residual`) | **Real** — KIVI/KVQuant show KV is asymmetric; **quality‑gate first** |
| **Lower protect fraction** (4% → 2%) | halves protect sidecar **and** its scattered bandwidth | Calibration‑tunable | Model‑specific; re‑run needle gate per model |
| **Coarser V scale grouping / larger K block (BS)** | amortizes scale/`xmin` over more tokens (V per‑token is the un‑amortized stream) | PROPOSED | Coarser scale ⇒ more quant error; quality‑gate |

**Recommended tax cut:** ship **prot‑int8** (already validated, zero quality cost) and treat
symmetric/coarser‑scale as quality‑gated options. prot‑int8 alone: ~170 → ~165 B; + symmetric:
~165 → ~149 B (MODELED) — pushing net density from ~1.8× toward ~1.9–2.0× *and* shrinking the
scattered stream.

---

## 5. Mitigations — recover the *speed* lost to bf16 top‑k%

Ranked by value (from `KVPRO_V3_ALGORITHM_RESEARCH.md` Phase D + one addition):

| Mechanism | What it attacks | Status | Quality risk |
|---|---|---|---|
| **In‑kernel paged gather** — fold host gather+splice into the kernel; stream nibbles + protected channels + sidecars straight from paged HBM | overhead‑1 (~25% round‑trip) + temp churn | PROPOSED (V3 #1; prototype `USE_GATHER` exists) | **None** (bit‑identical; only *where* the gather happens changes) |
| **Store‑as‑consumed layout** — write pages in the exact byte order the kernel reads (cacheline‑aligned; nibble+sidecar interleave; partial tail pre‑finalized) | overhead‑3 (coalescing) + kills the per‑step splice re‑quant | PROPOSED (V3 #6; needs snapshot/format version bump) | **None** (same values, new layout) |
| **★ Contiguous‑protected permutation** — apply a fixed per‑(layer,head) permutation of the head‑dim that clusters the selected protected channels into a contiguous range, so the bf16/int8 protect store becomes a **dense coalesced block** instead of scattered | overhead‑3 (turns scattered reads into one coalesced read) | PROPOSED (new; see §6) | **None if applied identically to post‑RoPE Q and K** — see invariance argument §6 |
| **Load scale/xmin/protect once per block into shared memory** | overhead‑2 (redundant per‑element loads) | PROPOSED (kernel) | None |
| **B=1‑specialized kernel** (minimal launch/register footprint, persistent kernel) | overhead‑2 at B=1/short‑gen (worst regime, 0.22×) | PROPOSED (V3 #3) | None |
| Static per‑head/layer protection layout | overhead‑3 (removes per‑channel branch) — **marginal** | NOT RECOMMENDED (V3 #3) | **High** — per‑channel selection is the quality lever (KVQuant) |

**Ceiling reminder (MODELED):** even with all of the above, bounded decode is **~0.27–0.30× of
bf16 — never parity.** Throughput work **de‑risks the "too slow to deploy" objection and widens the
routable‑workload envelope**; it does not change KVPro's core value, which is **capacity + quality**,
not raw speed.

---

## 6. The contiguous‑protected permutation (detail + why it's quality‑neutral)

**Idea.** Calibration already selects *which* channels to protect (top‑k% by magnitude). Add one
step: emit a fixed permutation `π_{l,h}` of the head‑dimension that maps the selected protected
indices to a **contiguous block** at one end of the axis. Store K (and present Q) in permuted order.
Then the ~4% protected channels — and their higher‑precision store — are a single **coalesced**
region instead of ~5 scattered singletons, collapsing overhead‑3 for the protect stream.

**Why it does not change the result.** Attention uses `Q·Kᵀ = Σ_d Q_d K_d`. A fixed permutation `π`
applied **identically to both Q and K** only reorders the terms of that sum, so the dot product is
invariant (up to floating‑point reassociation, negligible). The permutation is applied to
**post‑RoPE** Q and K (RoPE is applied first, as in the current calibration hook), so it does not
interfere with rotary position encoding. V is never protected — unaffected. Q is not cached, so the
only runtime cost is a tiny gather on the single query vector.

**Cost/benefit.** Zero quality cost (basis permutation), near‑zero runtime cost, and it converts the
protected stream from the worst‑coalesced part of the read into a dense block — the exact overhead‑3
that the bf16 top‑k% introduces. Pairs naturally with **store‑as‑consumed** (§5).

---

## 7. Net effect if adopted (MODELED)

- **Density:** prot‑int8 (shipped) + symmetric residual (quality‑gated) → sidecar tax ~42 B → ~21 B;
  net density ~1.8× → **~1.9–2.0×**.
- **Speed:** in‑kernel gather (−~25% round‑trip) + store‑as‑consumed + contiguous‑protected
  permutation (coalesce the scattered protect/sidecar reads) → lift the worst‑case 0.22× toward the
  **~0.27–0.30× ceiling**; improves B=1 latency most with the specialized kernel.
- All labeled MODELED until measured on a GPU pod; the byte‑equality oracle (`phase6f_read_fusion`)
  gates any layout/kernel change before timing.

---

## 8. Patent note (for counsel)
- **prot‑int8** (static per‑channel asymmetric quantization of the *protected* channels using
  calibration‑derived, margin‑widened bounds) is already captured as a dependent claim (N4 /
  provisional §5.2, claim 4A/4B).
- **In‑kernel paged gather** and **store‑as‑consumed layout** are **low novelty** — the V3 analysis
  notes they are how vanilla bf16 paged attention already works. Do **not** anchor claims on them.
- **★ Contiguous‑protected permutation** (a fixed head‑dim permutation that clusters
  calibration‑selected protected channels for coalesced access, applied invariantly to post‑RoPE Q
  and K) appears **more novel** and is a plausible **dependent claim** tying the static‑mask
  invention (Concept E/A) to a serving‑throughput improvement. Flag it to counsel; pressure‑test
  against channel‑reordering / permutation‑quantization prior art (e.g., QuaRot‑style basis changes,
  though those are *rotations*, not index permutations) before relying on it.

---

## 9. Bottom line
The sidecar tax is **~25% of KVPro's footprint**, dominated by `xmin` (asymmetry) and the
**scattered** protected‑bf16 channels. The clean, shipped win is **prot‑int8** (halves the protect
sidecar, zero quality cost). The speed penalty from bf16 top‑k% is a **transaction‑pattern** problem,
not a byte‑count one — best addressed by **in‑kernel gather + store‑as‑consumed + a
contiguous‑protected permutation**, all quality‑neutral, lifting decode toward its **bounded
~0.27–0.30× ceiling (never parity)**. None of this changes the thesis: KVPro's value is
**capacity + quality**; the throughput work removes the deployment objection. **Keep this detail out
of investor materials** — it belongs in NDA technical diligence.
