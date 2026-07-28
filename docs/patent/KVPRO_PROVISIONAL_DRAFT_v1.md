# PROVISIONAL PATENT APPLICATION (DRAFT v1 — hardened)

**Title:** Protected‑Precision Compression and Prefix‑Compatible Serving of Transformer
Key‑Value Caches

**Applicant / Assignee:** Ugence Labs
**Inventors:** [TO BE COMPLETED — see §12]
**Priority:** [none claimed / provisional]
**Prepared:** 2026‑07‑28

> **Status of this document.** This is a **hardened working draft of a US provisional**
> (35 U.S.C. §111(b)) derived from `KVPro_Patent_Portfolio_Specification_v3.docx` and grounded
> in the shipped implementation (`CTM_plus/KVPolicy/`). Changes vs. v3: (i) indefinite/marketing
> claim terms removed ("cryptographically safe," "fundamentally incompatible"); (ii) the measured
> fidelity and competitive data written in as **unexpected‑results** evidence (§8); (iii) §101
> "improvement to computer functioning" framing woven into the independent claims; (iv) an
> examiner‑facing **prosecution note** added as §11, clearly marked **NOT part of the filed
> disclosure**. A provisional does not require claims; the claims here are included to preserve
> scope and are illustrative. **Not legal advice — for review by registered patent counsel.**

---

## 1. Field

The disclosure relates to memory‑efficient inference of transformer neural networks, and more
specifically to compressing, reconstructing, persisting, and reusing the key‑value (KV) cache of a
transformer language model in a manner compatible with paged‑memory, fused‑attention serving
infrastructure.

## 2. Background and technical problem

At long context lengths the KV cache — not the model weights — becomes the dominant consumer of
accelerator (GPU) high‑bandwidth memory (HBM), and therefore the binding limit on how many
concurrent inference sequences a fixed accelerator can serve. Low‑bit (e.g., 4‑bit) KV
quantization reduces that footprint but, done naïvely, degrades model fidelity — particularly on
long‑context retrieval — because a small number of key channels carry disproportionately large
magnitudes ("outlier channels") that a single low‑bit scale cannot represent.

Prior approaches leave three **technical** problems unsolved in combination:

1. **Fidelity vs. density under real serving.** Methods that recover fidelity (outlier isolation
   via sparse operations; pre‑quantization matrix rotations; low‑rank+sparse correction) introduce
   irregular memory access or extra compute that conflict with **paged** KV layouts and **fused**
   attention kernels, so offline accuracy does not translate to online throughput.
2. **Prefix‑cache compatibility.** Methods that choose which channels to protect **per sequence**
   (dynamically, from the current sequence's activations) produce a per‑sequence protection
   structure. This makes a cached prefix's compressed state **non‑reusable** by a different
   request, because the two requests may protect different channels — defeating prefix caching, a
   central throughput mechanism of modern serving engines.
3. **Lossless cross‑tier reuse.** Methods that move KV to cheaper memory tiers (host DRAM, NVMe)
   for reuse across requests either operate on uncompressed/losslessly‑compressed data or
   recompute after transfer, and do not guarantee that reuse of the **compressed** state adds no
   further error, nor validate structural compatibility before reuse.

The disclosed system addresses these as an improvement to the **functioning of the computer**:
it increases the number of concurrent sequences resident in a fixed accelerator memory budget and
enables reuse of compressed KV state across requests and memory tiers without additional fidelity
loss, using deterministic memory layouts and validated restoration rather than abstract
mathematical manipulation.

## 3. Summary

The system comprises five inter‑operating concepts (A–E), each independently useful and jointly
forming a serving pipeline:

- **(A) Channel‑sensitivity discovery.** A one‑time, per‑model calibration pass runs a
  representative corpus through the unmodified model, accumulates a per‑channel importance metric
  from key activations captured during prefill, and selects a fixed subset of channels per layer
  and per attention head.
- **(B) Dual‑precision storage.** Selected (sensitive) key channels are retained in a
  higher‑precision representation; the remaining key channels, and all value channels, are stored
  in a lower‑precision (e.g., 4‑bit) representation with per‑block/per‑group reconstruction
  parameters, packed into a **uniform, deterministic** paged layout (no sparse structure).
- **(C) Runtime protected reconstruction.** A fused kernel reads the low‑precision codes and
  reconstruction parameters directly from paged memory, reconstructs values **in‑register**, and
  substitutes the higher‑precision sensitive‑channel values by a **conditional selection**
  (overlay), passing the combined result to the attention computation **without** materializing a
  full‑precision copy of the cache and **without** applying a matrix rotation to the cache.
- **(D) Persistent compressed state.** The compressed state of a prefix is snapshotted to a
  secondary memory tier and later restored **byte‑for‑byte**, gated by validation of format and
  geometry and by a one‑to‑one, ordered, count‑checked block mapping, so that reuse introduces no
  additional quantization error.
- **(E) Static prefix‑compatible protection masks.** The protection mask of (A) is **fixed per
  model and shared identically across all sequences and requests**, so that a cached prefix's
  compressed KV state is reusable by any request sharing the prefix — making protected‑precision
  KV compression compatible with prefix caching and multi‑tier cache sharing.

The unifying, non‑obvious insight is (E): **selecting protected channels statically per model
rather than dynamically per sequence** trades a theoretical per‑sequence optimum for a
system‑level capability — prefix reuse and cache sharing — that per‑sequence protection cannot
provide, and does so, as measured (§8), **without loss of long‑context retrieval fidelity**.

## 4. Brief description of the drawings (to be prepared)

- **FIG. 1** — end‑to‑end pipeline: calibration → dual‑precision write → fused read/overlay →
  snapshot/restore → prefix reuse.
- **FIG. 2** — calibration data flow: prefill‑only K capture, per‑(layer, head, channel)
  importance accumulation, top‑k selection, static mask artifact.
- **FIG. 3** — in‑register reconstruction and overlay (conditional select), showing **no** matrix
  rotation and **no** full‑precision intermediate buffer.
- **FIG. 4** — uniform paged byte layout: nibble‑packed codes + per‑block/per‑group sidecars +
  protected‑channel store, contrasted with a sparse outlier layout.
- **FIG. 5** — partial‑tail (splice) re‑quantization: block‑granular key quantization coexisting
  with token‑at‑a‑time decode.
- **FIG. 6** — snapshot/restore with format/geometry/count validation and byte‑faithful round‑trip.
- **FIG. 7** — chained per‑block prefix hashing and deepest‑first reuse matching across GPU/DRAM/NVMe tiers.
- **FIG. 8** — static‑vs‑dynamic mask comparison and its effect on prefix reuse (core narrative).

## 5. Detailed description

### 5.1 System overview
An unmodified pre‑trained transformer is served through a compression backend installed at each
attention layer. The backend (i) quantizes keys and values on write into a paged accelerator
memory, (ii) reads and reconstructs them within a fused attention kernel on decode, and (iii)
can snapshot and restore the compressed state of a prefix to and from a secondary memory tier for
reuse. A per‑model protection mask, computed once (§5.2), governs which key channels are retained
at higher precision.

### 5.2 Concept A — channel‑sensitivity discovery (calibration)
A representative calibration corpus (in one embodiment, on the order of 50–1000 diverse prompts
spanning prose, code, dialogue, technical, and long‑context text) is processed by the unmodified
model. A hook on each attention layer captures the **key tensor during prefill** (sequence length
> 1). For each layer *l*, key‑value head *h*, and channel *d*, an **importance metric** is
accumulated across the corpus. In the primary embodiment the metric is the **maximum absolute
value** of the key activation, aggregated as a **maximum across prompts** (max‑of‑maxes):

```
mag[l,h,d] = max over prompts ( max over tokens |K[l,h,d,token]| )
```

Per (layer, head), the **top‑N channels by mag** are selected, where
`N = max(1, round(D · protect_fraction))` and `protect_fraction` is a small fixed fraction
(0.04, i.e. 4%, in the primary embodiment). The selection is emitted as a static binary mask of
shape `(num_layers, H_kv, D)`, saved as a per‑model artifact with metadata (model id, fraction,
N, geometry, and the layer ordering).

In a second embodiment the calibration additionally records, per channel, the **signed minimum
and maximum** key values over the corpus and stores them, **widened outward by a margin factor**
(e.g., 1.1, adding (margin−1)×range on each side to provide headroom for live values exceeding the
calibration extremes), for use as static per‑channel reconstruction bounds of the higher‑precision
protected store (§5.3). Other importance metrics (mean‑absolute, variance, entropy/information‑
theoretic, Fisher‑information/sensitivity, spectral, or a learned selector) are contemplated as
alternatives to max‑absolute.

### 5.3 Concept B — dual‑precision storage
Per layer, per token:

- **Non‑protected key channels** are quantized with **per‑block, per‑(head, channel) asymmetric
  affine** quantization over a fixed block of `BS` tokens (BS = 32 in the primary embodiment):
  ```
  scale = clamp( (amax − amin) / (2^b − 1),  ≥ ε )        # b = 4 bits → divisor 15; ε = 1e‑8
  q     = clamp( round( (x − xmin) / scale ), 0, 2^b − 1 )
  x̂     = q · scale + xmin                                 # reconstruction
  ```
- **Value channels** are quantized with **per‑token, per‑(head, group) asymmetric affine**
  quantization, the head dimension partitioned into groups of fixed size (32 in the primary
  embodiment). Values are **not** protected.
- **Protected key channels** are additionally retained at **higher precision** — bf16 in one
  embodiment, or, in the second embodiment, an **8‑bit per‑channel asymmetric** representation
  whose bounds are the calibration‑derived, margin‑widened signed min/max
  (`scale = (kmax − kmin)/255`).
- **Packing and layout.** Low‑precision codes are packed two 4‑bit codes per byte (nibble‑packed)
  along the channel axis and written into a **uniform, contiguous** region of the paged cache;
  protected channels are stored in a separate small per‑block sidecar. Reconstruction sidecars
  (key scale/min per block; value scale/min per token‑group) accompany each block. Crucially, the
  layout is **dense and deterministic** — protected channels occupy the same regular grid as any
  other channel (and may themselves be nibble‑packed and later overridden), so decode uses regular,
  coalesced memory access with **no sparse‑matrix operations**.

### 5.4 Concept C — runtime protected reconstruction (in‑register overlay)
On decode, a fused attention kernel:

1. reads nibble‑packed codes and the per‑block/per‑group reconstruction parameters directly from
   paged memory;
2. reconstructs each low‑precision channel **in‑register** as `x̂ = q · scale + xmin`;
3. **overlays** protected channels by a per‑channel **conditional selection**
   `value = select(mask[l,h,d], protected_value, x̂)` — i.e., where the mask is set, the
   higher‑precision value replaces the reconstructed one — **before** the query·key inner product;
4. feeds the combined key/value tiles directly into the attention matmuls and softmax **without**
   assembling a full‑precision copy of the KV cache and **without** applying any rotation or other
   global mathematical transformation to the cache.

**Partial‑tail (splice) reconciliation.** Because keys are quantized per block of BS tokens while
decode appends one token at a time, the still‑filling trailing block is held in a per‑sequence
staging buffer and **re‑quantized each decode step** so the kernel always sees a self‑consistent
(codes, scale, min) triple for that block; completed blocks are read without re‑quantization.
This reconciles block‑granular quantization with token‑at‑a‑time generation.

### 5.5 Concept D — persistent compressed inference state
The compressed state of a completed prefix — comprising the packed key codes, packed value codes,
key scale, key minimum, protected‑channel store, value scale, value minimum, and a **format
identifier** — is snapshotted to a secondary memory tier (host DRAM, NVMe/SSD, or network/
distributed storage). Restoration:

- maps snapshot blocks to freshly allocated target blocks **one‑to‑one and in order**, and
  **refuses** the restore on a **count mismatch** (a partial/truncated load is rejected rather than
  silently truncated);
- validates that snapshot and target **geometry match exactly** (head dimension D, block size BS,
  protected‑channel count N) and that the **format identifiers are compatible**, refusing the
  restore otherwise;
- writes bytes back such that the restored compressed state is **byte‑for‑byte identical** to the
  snapshotted state. Byte‑faithfulness follows from the reconstruction being an identity on the
  code lattice (re‑encoding a dequantized value reproduces the same code), so a snapshot taken in a
  canonical higher‑precision view and re‑encoded on restore is exact even across storage formats;
- optionally computes an **integrity value** (e.g., a hash or checksum) over the snapshot to detect
  corruption before use.

Because reuse operates on the already‑compressed state and the round‑trip is byte‑faithful, reuse
across requests and tiers introduces **no additional quantization error** beyond the initial
compression.

### 5.6 Concept E — static prefix‑compatible protection masks (anchor)
The protection mask of §5.2 is generated **once per model, before inference,** and applied
**identically to every sequence and every request** — it is not recomputed per sequence, per
request, or adaptively from live activations. Consequences leveraged by the system:

- **Prefix reuse.** A prefix's compressed KV state, cached under the shared static mask, is
  reusable by **any** later request sharing that prefix, because the mask (which channels are
  protected, and thus the compressed representation's structure) is guaranteed identical across
  requests.
- **Single artifact.** The model carries **one** mask, not one per prefix; per‑prefix mask storage
  overhead is eliminated.
- **Prefix matching across tiers.** Cached prefixes are keyed by a **chained per‑block hash** — a
  hash computed for each completed block that depends on all tokens up to and including that block —
  and matched **deepest‑first**, with a block‑count check guarding against hash collision, so the
  longest byte‑faithfully‑restorable shared prefix is located and reused across GPU, DRAM, and NVMe
  tiers using the **same** static mask.
- **Simplified serving.** All sequences are treated identically by the batching/scheduling logic,
  removing per‑sequence mask bookkeeping.

## 6. Embodiments and variations
Importance metrics: max‑absolute (primary), mean‑absolute, variance, entropy/mutual‑information,
Fisher/gradient sensitivity, spectral/PCA, or learned selectors. Low‑precision formats: INT4
(primary), INT3/INT2, FP6/MXFP4, logarithmic. Higher‑precision formats: BF16 (primary), FP16, FP8,
INT8/INT16. Protected fraction: fixed (primary, ~4%) or distribution‑determined. Hardware: NVIDIA/
AMD GPU, TPU, Trainium/Inferentia, other accelerators/ASICs, or CPU SIMD. Secondary storage: DRAM,
NVMe/SSD, network‑attached, distributed cache. Block/group sizes, bit‑widths, and margin are
configurable.

## 7. Distinctions over specific prior art
- **KIVI** (per‑channel key / per‑token value asymmetric INT4): establishes the quantization
  granularity but has **no channel‑protection mechanism, no static per‑model mask, and no prefix‑
  caching integration**. Concepts A–E add over KIVI.
- **KVQuant** (dense‑and‑sparse outlier isolation): protects outliers via **sparse, per‑sequence**
  structure. The present system uses a **dense, deterministic** layout (§5.3) and a **static per‑
  model** mask (§5.6), enabling fused‑kernel access and prefix reuse that a sparse, per‑sequence
  scheme does not provide.
- **SAW‑INT4** (arXiv 2604.19157, April 2026; token‑wise INT4 with block‑diagonal Hadamard
  rotation, paged/fused): normalizes outliers by a **pre‑quantization matrix rotation**. The
  present system instead retains outlier channels in a higher‑precision sidecar and applies a
  **rotation‑free, in‑register conditional overlay** (§5.4), and adds the **static prefix‑
  compatible mask** and **byte‑faithful cross‑tier reuse** that SAW‑INT4 does not address. This is a
  **structural** distinction embodied in claim 1C and holds independent of any benchmark; see §8.3
  for why the observed SAW behavior is treated as motivation only, not comparative evidence.
- **CacheGen** (warm‑tier KV compression/reuse): does not disclose **format/geometry‑validated,
  byte‑faithful** restoration of a **protected‑precision** compressed state (§5.5). Concept D adds
  over it.
- **QuaRot / SpinQuant / SmoothQuant / HQQ / GPTQ / AWQ**: rotation‑ or smoothing‑based, and
  primarily **weight** quantization; none disclose the static‑mask‑for‑prefix‑reuse combination.

## 8. Unexpected results (empirical support)
The disclosed system's non‑obviousness rests on results measured **on the disclosed implementation
itself, under controlled conditions** — it does **not** depend on any competitor performing poorly.
The anchor is §8.1.

**8.1 — ANCHOR: exact fidelity retained by a static, coarse, per‑model mask (teaching‑away +
unexpected result).** With `protect_fraction = 0.04`, exact‑match long‑context needle‑in‑a‑haystack
retrieval **equal to stock BF16 (15/15)** was measured across **four models spanning three families
and two scales** — Qwen2.5‑7B‑Instruct, Mistral‑7B‑Instruct‑v0.3, Llama‑3.1‑8B‑Instruct, and
Qwen2.5‑14B‑Instruct — using the **same** calibration procedure with **no per‑family code changes**,
at approximately **0.5× the KV memory** of BF16 (yielding roughly **2× concurrent‑sequence capacity**
at a fixed memory budget). The art teaches toward per‑sequence/dynamic protection as the optimal
choice; that a **single static per‑model mask** instead preserves **exact** retrieval — across
multiple families and scales, with a coarse 4% selection — is the unexpected result and the
teaching‑away. This evidence is (i) measured on the claimed system, (ii) controlled against the same
model's BF16 reference, and (iii) commensurate in scope with independent claims 1E and 1A.

**8.2 — byte‑faithful snapshot/restore verified.** A snapshot → zero → restore → byte‑compare
round‑trip of the compressed state reproduced every stored tensor exactly, confirming that cross‑tier
reuse of the compressed state adds no additional error (§5.5). Supports claim 1D.

**8.3 — Motivation only (NOT relied upon as comparative evidence of record).** A block‑diagonal‑
rotation INT4 method (SAW‑INT4/BDR) was observed, on one mainstream model (Qwen2.5‑7B‑Instruct), to
lose long‑context retrieval where BF16 did not, while passing on the model it was tuned on. This is
included **only to motivate the technical problem** that model‑transfer fidelity of rotation‑only
INT4 is not guaranteed — it is **not** offered as evidence of comparative superiority, because it is
a single model, was not run under a common harness against the disclosed system, and used a rotation
configuration that may not be model‑specific. The distinction over SAW‑INT4 that the claims rely on
is **structural** (rotation‑free in‑register overlay, §5.4/claim 1C), which holds independent of any
benchmark. *(To convert §8.3 into admissible comparative evidence, run both methods on the same
model under one harness — a scoped, planned measurement — before relying on it in prosecution.)*

## 9. Illustrative claims (hardened; §112‑ and §101‑aware)

> Provisional filings need not include claims; these define intended scope. Marketing/indefinite
> terms present in v3 ("cryptographically safe," "fundamentally incompatible") have been removed and
> replaced with definite, functional recitations. Each independent claim recites concrete accelerator/
> serving structure to anchor eligibility.

**Concept E (anchor) — Claim 1E.** A method of serving a transformer language model with a paged
key‑value cache, comprising: generating, during a one‑time calibration of the model prior to
inference, a protection mask identifying a proper subset of key channels per layer per attention
head; storing the protection mask as a per‑model artifact **applied identically to every inference
sequence and request, without per‑sequence or per‑request recomputation**; storing, for a completed
prefix, a compressed key‑value state produced under the shared protection mask; and, responsive to a
later request sharing the prefix, **reusing the stored compressed key‑value state without
regenerating or recomputing the protection mask**, thereby increasing the number of concurrent
sequences served from a fixed accelerator memory budget.
- *2E.* The method of 1E, wherein a shared prefix is located by computing a hash for each completed
  block that depends on the tokens up to and including that block, matching candidate prefixes
  deepest‑first, and verifying a matched block count to guard against collision.
- *3E.* The method of 1E, wherein the shared protection mask is applied unchanged across a multi‑
  tier cache hierarchy (accelerator memory, host memory, and non‑volatile storage) such that a
  prefix cached in one tier is reusable from another tier.
- *4E.* The method of 1E, wherein reusing the stored compressed state comprises restoring it
  byte‑for‑byte (per Claim 1D) prior to continued generation.

**Concept A — Claim 1A.** A method comprising: executing an unmodified transformer over a
calibration corpus; capturing key activations at attention layers during prefill; computing, per
layer, per attention head, and per channel, an importance metric that aggregates a per‑channel
magnitude statistic across the corpus; selecting a fixed subset of channels per layer per head by
ranking on the metric; and emitting a binary protection mask that is invariant across inference
sequences.
- *2A.* Wherein the importance metric is a maximum absolute value aggregated as a maximum across the
  corpus, and the subset is a fixed fraction of channels per layer per head.
- *3A.* Wherein the calibration additionally records per‑channel signed minima and maxima, widened
  outward by a margin factor, for use as static reconstruction bounds of a higher‑precision store.
- *4A.* Wherein the importance metric is one of mean‑absolute value, variance, an information‑
  theoretic measure, a sensitivity measure, a spectral measure, or a learned selector.

**Concept B — Claim 1B.** A storage architecture for a transformer key‑value cache comprising: a
higher‑precision representation of key channels designated sensitive by a protection mask; a
lower‑precision representation of the remaining key channels and of value channels, with per‑block
key and per‑token‑group value reconstruction parameters; and a **uniform, contiguous paged layout**
in which sensitive and non‑sensitive channels occupy a common regular grid, providing deterministic,
coalesced memory access without sparse‑matrix operations.
- *2B.* Wherein the lower‑precision representation is 4‑bit codes packed two per byte and the
  reconstruction is asymmetric affine `x̂ = q·scale + offset`.
- *3B.* Wherein keys are quantized per block of a fixed number of tokens and values per group of a
  fixed number of channels.
- *4B.* Wherein the higher‑precision representation is bf16, or an 8‑bit per‑channel asymmetric
  representation with calibration‑derived, margin‑widened bounds.

**Concept C — Claim 1C.** A method comprising: reading, by a fused attention kernel, lower‑precision
key/value codes and reconstruction parameters from paged accelerator memory; reconstructing them
in‑register to approximate values; substituting protected‑channel higher‑precision values by a
per‑channel conditional selection under the protection mask; and passing the combined values to the
attention inner‑product and softmax **without materializing a full‑precision copy of the cache and
without applying a matrix rotation to the cache**.
- *2C.* Wherein a still‑filling trailing block is re‑quantized at each decode step to present a
  self‑consistent set of codes and reconstruction parameters, while completed blocks are read
  without re‑quantization.
- *3C.* Wherein multiple blocks are reconstructed in parallel without temporary full‑precision
  buffers.

**Concept D — Claim 1D.** A method for persisting and reusing compressed transformer inference state
comprising: snapshotting a compressed state — packed key codes, packed value codes, key
reconstruction parameters, value reconstruction parameters, protected‑channel values, and a format
identifier — to a secondary memory tier; and restoring it into freshly allocated paged memory only
after (i) verifying matching geometry (head dimension, block size, protected‑channel count) and
compatible format identifiers, and (ii) enforcing a one‑to‑one, ordered, count‑checked block
mapping, the restored state being byte‑for‑byte identical to the snapshot such that reuse introduces
no additional quantization error.
- *2D.* Wherein the secondary tier is host memory, non‑volatile storage, or network/distributed
  storage.
- *3D.* Wherein an integrity value (hash or checksum) over the snapshot is computed and verified to
  detect corruption before use.
- *4D.* Wherein a restore is refused on format mismatch, geometry mismatch, or block‑count mismatch.

**CRM.** A non‑transitory computer‑readable medium storing instructions that, when executed, cause a
system to perform the method of any of claims 1A, 1B, 1C, 1D, or 1E.

## 10. Definitions
"Channel" = a (head, head‑dimension‑index) coordinate over which a quantization scale ranges.
"Block" = a fixed group of tokens sharing key reconstruction parameters. "Group" = a fixed set of
head‑dimension indices sharing value reconstruction parameters. "Static/shared mask" = a mask
generated once per model and applied without per‑sequence or per‑request recomputation.
"Byte‑for‑byte identical" = every stored byte of the restored compressed state equals the
corresponding byte of the snapshot.

---

## 11. PROSECUTION STRATEGY NOTE — **NOT PART OF THE FILED DISCLOSURE** (for counsel only)
> Remove this section before filing, or keep only in the attorney file. It records strategy, not
> invention.

- **Anchor the portfolio on Concept E.** E (static, per‑model, prefix‑compatible mask) is the
  strongest independent claim: its non‑obviousness rests on a genuine **teaching‑away** (skilled
  practitioners default to per‑sequence/dynamic protection as "optimal") plus **unexpected
  results** (§8.1 — a coarse static 4% choice preserves exact retrieval). Lead with E; put the §8
  data on the record as evidence.
- **Treat A as fallback, expect compression.** Concept A alone is close to "calibration + outlier
  selection," which is near‑prior‑art (KVQuant + standard static calibration) and is the most
  §101‑exposed (mathematical/mental‑process risk). Anticipate an examiner rejecting or narrowing 1A,
  and possibly merging A–E; keep A as a dependent/supporting family, not a hill to die on.
- **Expect a KSR combination rejection** assembling KIVI + KVQuant + SAW‑INT4 + CacheGen. Rebut with
  (i) the **rotation‑free overlay** *structural* distinction over SAW‑INT4 (§5.4, claim 1C) — which
  does not depend on any benchmark; (ii) the **dense‑layout / prefix‑reuse** distinction over sparse
  per‑sequence KVQuant (§5.3, §5.6); and (iii) the **§8.1 unexpected‑results/teaching‑away** anchor —
  measured on the claimed system, not "no single reference did all four."
- **Do NOT lean on the SAW collapse (§8.3) as evidence.** It is single‑model, not a same‑harness
  head‑to‑head, and possibly configuration‑dependent — an examiner can disregard it (MPEP 716.02
  requires comparison to the closest prior art under identical conditions) and the authors could
  publicly rebut it. Keep it as motivation only. If comparative evidence is wanted, first run the
  scoped same‑harness, same‑model measurement of both methods (the repo's open item), then it may
  be added to the record.
- **§112 hygiene done:** removed "cryptographically safe" (replaced with definite integrity‑value/
  byte‑faithful language) and "fundamentally incompatible" (replaced with the functional recitation
  "applied without per‑sequence or per‑request recomputation").
- **Prior‑art date that binds:** SAW‑INT4 published **April 21, 2026** (arXiv 2604.19157). File the
  provisional promptly; draft over SAW‑INT4 as prior art regardless of its (non‑existent, as of now)
  patent status. Watch for a later‑publishing Together application (~18‑month window) for FTO.
- **Before filing:** confirm inventorship for the conception of each of A–E; execute assignments to
  Ugence Labs; inventory any non‑NDA public disclosure of the *method* and give counsel the dates.

## 12. Inventorship and assignment
**Sole inventor.** All of Concepts A–E were conceived by a single inventor; there are no
co‑inventors. Inventor: **[FULL LEGAL NAME — confirm exact spelling; add residence + citizenship
for the Application Data Sheet]**. All rights assigned to **Ugence Labs**; execute the assignment at
or before filing and record it with the USPTO.

## 13. Disclosure statement (bar‑date analysis)
- **No non‑confidential public disclosure of the method by the inventor to date.** As represented by
  the inventor, the compression method has not been publicly disclosed, published, offered for sale,
  or publicly used without an NDA. Accordingly, **no U.S. §102(b)(1) grace‑period clock has started**
  and **no foreign‑priority‑destroying disclosure has occurred** as of this draft's date.
- **⚠️ Verify repository visibility before filing.** If the source repository (e.g., `rasaha/symbolu`)
  is or becomes **public**, that publication of the implementation is itself a public disclosure that
  **starts the U.S. clock and can bar most foreign rights**. Confirm the repo is **private** through
  the filing date; if it was ever public, give counsel the exact date it went public.
- **Prior‑art note (independent of the inventor's own disclosure):** SAW‑INT4 (arXiv 2604.19157)
  published **April 21, 2026** is third‑party prior art and is drafted over regardless of the
  inventor's disclosure status.
- **Hygiene until filed:** keep the method NDA‑only; do not post, present, publish, or offer it for
  sale before the provisional is on file.

**END OF DRAFT — for review by registered patent counsel. Not legal advice.**
