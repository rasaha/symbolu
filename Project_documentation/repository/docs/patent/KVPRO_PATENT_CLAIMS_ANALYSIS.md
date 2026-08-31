# KVPro — US Patent Claims Analysis (What You Can Claim, and How)

**Prepared for:** Ugence Labs / KVPro
**Purpose:** Identify patentable subject matter in the KVPro KV‑cache compression system and
draft example claims for a US provisional (and follow‑on non‑provisional) filing.
**Grounded in:** the actual shipped code in this repository (file:line citations throughout).

> ⚠️ **Not legal advice.** This is a technical/strategic analysis to prepare you for a
> conversation with a registered US patent attorney or agent. Claim scope, patentability,
> and filing decisions must be reviewed by counsel. Nothing here is a legal opinion on
> validity or infringement.

---

## 0. Two urgent housekeeping items (read first)

1. **The disclosure / on‑sale clock may already be running.** The `KVPro_VC_brief.md` says
   the method is *"proprietary and patent‑pending … available to qualified partners under NDA."*
   Good — NDA‑gated disclosure and the "patent‑pending" label are the right posture. **But:**
   - In the US, any **public** disclosure, publication, offer for sale, or public use starts a
     **12‑month grace period** (35 U.S.C. §102(b)) — after which you lose the right to file.
   - In **most of the rest of the world (EPO, China, etc.) there is *no* grace period** — a
     single public, non‑confidential disclosure **destroys** foreign rights immediately.
   - **Action:** before filing, inventory every place KVPro's *method* has been disclosed
     without an NDA (investor decks, blog posts, conference talks, GitHub if public, arXiv,
     benchmarks shared externally). If any non‑confidential disclosure has occurred, tell your
     attorney the **exact date** — it sets your bar date. File the provisional **before** any
     further disclosure.

2. **You have (at least) two separable inventions in this repo.** Don't conflate them:
   - **Invention A — "KVPro" proper:** the `int4_protected` **protected‑channel INT4 KV‑cache
     compression + paged/fused‑kernel serving + byte‑faithful warm‑tier snapshot/restore** system
     (`CTM_plus/KVPolicy/`). This is what the VC brief calls KVPro. **This memo focuses here.**
   - **Invention B — consistency‑scored cache (separate):** the BCVF/SCC/USE "consistency
     Lagrangian" cache‑entry scoring + entropy‑trend hallucination detector in
     `symbolu_core/ontological/kv_cache_enhanced.py`. Different problem (quality/hallucination,
     not memory), different mechanism. Potentially its own filing — flagged in §8, not developed here.

---

## 1. The invention as actually built (Invention A)

KVPro is a **post‑hoc (no‑retraining) low‑bit KV‑cache compression and serving system** for
transformer LLM inference. From the code, its end‑to‑end mechanism is:

### 1.1 Quantization format (`phase5b_4c_paged_writer.py`)
- **Keys (K):** per‑**block** (block size BS=32) per‑**(head, channel)** **asymmetric affine INT4**:
  `scale = (amax − amin)/15` (clamped ≥1e‑8); `q = round((x − xmin)/scale)` clamped to `[0,15]`;
  dequant `x̂ = q·scale + xmin`. (`:1108‑1113`)
- **Values (V):** per‑**token** per‑**(head, group)** (`v_group_size = 32`) asymmetric affine INT4,
  same affine form. (`:2059‑2068`)
- **Packing:** unsigned 4‑bit codes `[0,15]`, **2 codes/byte** (nibble‑packed), stored in vLLM's
  paged `uint8` cache. (`:2025`, `:2068`)
- **Sidecars per block:** `k_scale`, `k_xmin` (per‑block, per‑(H,D)); `v_scale`, `v_xmin`
  (per‑token, per‑(H,group)); `k_protect` (protected‑channel store). (SPEC: format table.)

### 1.2 Protected‑channel outlier scheme — **K only** (`calibrate_phase5b_protect_mask.py`)
- A **one‑time, per‑model calibration pass** runs a fixed prompt corpus through the *stock* model
  and hooks each leaf attention module to capture **K during prefill only** (`T>1`). (`:323‑375`)
- It accumulates, per **(layer, kv‑head, channel)**, the **max‑abs of K** across all prompts
  (`max‑of‑maxes` aggregation). (`:297‑320`)
- Per **(layer, kv‑head)** it selects the **top‑`protect_fraction` (default 4%)** channels by
  accumulated magnitude → a **static `(num_layers, H_kv, D)` int8 mask**. (`:378‑409`)
- Protected channels are stored at higher precision (bf16, or the **"prot‑int8" static
  per‑channel asymmetric** grid `scale=(k_max−k_min)/255` from calibration‑derived, **margin‑widened**
  signed min/max). (`:412‑446`, `:600‑624`)
- **The mask is per‑model and *shared across all sequences*** — explicitly replacing an earlier
  per‑sequence mask *"which can't be shared across sequences and breaks vLLM prefix caching."*
  (`:6‑8`) V is **never** protected.

### 1.3 Read/decode path — in‑register dequant + overlay (`phase5b_backend_install.py`, fused kernel)
- A **fused FlashAttention‑variant kernel** reads the INT4 nibbles + sidecars **straight from
  paged HBM**, dequantizes **in‑register** (`code·scale + xmin`), and **overlays the protected
  channels in place** — `where(mask, protect, dequant)` — before the `QKᵀ`/softmax/`PV` matmuls,
  with **no bf16 KV reconstruction** (`PHASE6C_BF16_BACKING_SKIP=1` default). (SPEC `:17`;
  `KVPRO_V3_ALGORITHM_RESEARCH.md` §A.2)
- Partial (tail) blocks are re‑quantized each step ("splice"); full blocks bypass staging.

### 1.4 Byte‑faithful warm‑tier snapshot/restore (`tier5b_snapshot.py`, `tier5c_warmtier_serving.py`)
- Compressed KV for a prefix (the **7 tensors**: `packed_k/v`, `k_scale`, `k_xmin`, `k_protect`,
  `v_scale`, `v_xmin` + a `prot_format` marker) is **snapshotted to CPU/flash** and **restored
  bit‑exactly** into a fresh paged allocation — the inverse of the writer's block dump. (`:1‑23`, `:32`)
- Restore is **1:1, in order, count‑checked** (refuses partial loads = silent corruption)
  (`plan_restore :36‑45`) and **geometry/format‑guarded** (`check_meta_compatible :48‑62`).
- Because quantize∘dequant is identity on the code lattice, the round‑trip is **byte‑clean**, so
  **CPU/flash movement and cross‑session reuse add *zero* quality loss** beyond the in‑GPU path —
  something lossy transport codecs cannot offer. (`:16‑23`)

### 1.5 Measured properties (per repo, for context — not claim language)
- ~0.5× bf16 KV memory (~1.8× net density); **15/15 needle == stock bf16** across **four models,
  three families, two scales** at 4% protect. (`INT4_PROTECTED_README.md`)
- Honest trade‑off: below full‑precision **decode throughput** on the current path (routing product).

---

## 2. Prior art — be honest about what is *already known*

Your own `docs/KV_COMPRESSION_POSITIONING_MEMO.md` is unusually candid and should shape claim
scope. The following are **prior art** and must **not** be claimed as bare elements:

| Known technique | Prior art | Implication for claims |
|---|---|---|
| Per‑channel **K** quantization; per‑token **V**; asymmetric scaling | **KIVI** (ICML'24) | Bare "asymmetric per‑channel K / per‑token V INT4" is **not novel**. |
| **Per‑channel outlier isolation / protected high‑precision channels** | **KVQuant** (2401.18079) | "Keep outlier channels in higher precision" is **not novel alone**. |
| Low‑rank + sparse correction, "near‑lossless" 4‑bit | **GEAR** (2403.05527) | — |
| **Mixed / sensitivity‑aware precision** | **KVTuner** (2502.04420) | Layer‑adaptive precision is prior art. |
| **Serving‑compatible (paged + fused) INT4 KV** | **SAW‑INT4** (2604.19157) | Closest comparator — paged+fused INT4 alone is **contested**. |
| Rotation/residual "zero‑loss" KV | **TurboQuant / QJL** | — |
| **Storage/transport KV codec, warm‑tier** | **CacheGen** | Bare "store KV to a cheaper tier" is prior art. |

**Consequence:** claims resting on *compression ratio*, *"near‑lossless quality"*, *"protected
K channels"*, or *"paged INT4"* **in isolation** are weak/likely anticipated. Your defensible
novelty is in the **specific combination and the systems constraints** that make it deploy and
reuse — exactly what the positioning memo calls the moat.

---

## 3. Where the real, defensible novelty is (ranked)

Ranked by patent strength (novelty × non‑obviousness × enforceability × §101 safety):

**Tier 1 — strongest, lead with these:**

- **(N1) Prefix‑cache‑compatible, per‑model *static, sequence‑shared* protected‑channel mask
  derived by prefill‑only calibration.** The specific move — calibrate **once per model** from
  **prefill K max‑abs**, freeze a **`(layer, kv‑head, channel)` static top‑k mask that every
  sequence shares** so it **doesn't break paged prefix caching** — is a concrete solution to a
  concrete serving problem (per‑sequence masks break prefix caching). This is the least likely to
  be anticipated because prior art frames outlier selection as per‑tensor/per‑sequence, not as a
  *shared static serving artifact*. (Code: `calibrate_phase5b_protect_mask.py:6‑8, 297‑409`.)

- **(N2) Byte‑exact snapshot/restore of *protected‑INT4* compressed KV enabling lossless
  cross‑session / warm‑tier reuse.** Snapshotting the compressed representation (nibbles + all
  sidecars + protect store + format marker) and restoring it **bit‑identically** into a fresh
  paged allocation, **guarded by geometry+format compatibility and a 1:1 count check**, so tiered
  movement (GPU→CPU→flash) and prefix reuse add **no** quality loss. Competitors are HBM‑only or
  use *lossy* transport codecs. (Code: `tier5b_snapshot.py:1‑62`; `tier5c_warmtier_serving.py`.)

- **(N3) The integrated system claim (the "moat"):** protected‑channel INT4 KV **+** in‑register
  overlay in a **fused paged** attention kernel (no bf16 reconstruction) **+** the shared static
  calibrated mask **+** byte‑faithful warm‑tier reuse, operated as a **routing** backend. The
  *combination* is what deploys; each piece alone is contested, the assembled serving system is not.

- **(N3b) Chained per‑block prefix hashing for warm‑tier reuse matching.** Cross‑session reuse
  keys a stored compressed prefix by **one chained `blake2b` hash per *complete* block** (hash *i*
  depends on tokens `0..(i+1)·BS`), matched **deepest‑first** with an explicit **collision guard**
  (`rec.n_blocks == i+1`), so the *longest* byte‑faithfully‑restorable prefix is found and only
  fully‑written blocks are reused. Concrete mechanism tying the byte‑exact snapshot to a serving
  cache. (Code: `tier5c_warmtier_serving.py:36‑49, 87‑94`.) Pairs with N2.

**Tier 2 — good dependent/secondary claims:**

- **(N4) "prot‑int8": static per‑channel *asymmetric* quantization of the protected channels**
  using calibration‑derived signed min/max **widened by a deployment margin** (`scale=(k_max−k_min)/255`,
  bounds pushed outward by `(margin−1)·range` for clip headroom on live values past calibration
  extremes). A concrete, narrow, non‑obvious second‑tier encoding of the outlier stream.
  (Code: `calibrate_phase5b_protect_mask.py:412‑446`.)

- **(N5) In‑register overlay semantics** — `where(protect_mask, protected_value, int4_dequant)`
  applied **before** the attention inner product inside a single fused kernel pass, with the
  protected channels *also* nibble‑packed but overridden (uniform layout, no scatter). Narrower
  than N3; useful as a dependent claim tying quality to the kernel.

- **(N5b) Partial‑tail splice re‑quantization** — reconciling **block‑granular K quantization**
  (one scale/xmin per 32‑token block) with **token‑at‑a‑time decode**: the still‑filling last
  block is held in a per‑sequence staging buffer and **re‑quantized each decode step** so the
  fused kernel always sees a self‑consistent `(scale, xmin, nibbles)` triple for the trailing
  block, while full blocks are read without re‑quantization. The agent analysis flags this as one
  of the two least‑obvious mechanisms in the system. (Code: `phase5b_backend_install.py:2004‑2037`,
  batched variants `phase5b_4c_paged_writer.py:1806‑2001`.)

- **(N6) Cross‑model‑family *method* (the calibration procedure) yielding a deployable artifact
  with no per‑family code changes** — claim the **process** (calibrate→select→freeze→serve) as a
  method claim independent of the specific model.

**Tier 3 — weak / do NOT rely on (mention to attorney, likely reject or narrow):**
- Bare compression ratio, "near‑lossless quality," protected‑K alone, per‑channel/per‑token
  asymmetric INT4 alone, paged INT4 alone, generic KV tiering (§2 prior art).
- The V3 "in‑kernel paged gather" / "store‑as‑consumed layout" ideas — your own research doc
  (`KVPRO_V3_ALGORITHM_RESEARCH.md`) says these are **how bf16 paged attention already works**
  (low novelty). Skip for patenting; they're engineering, not invention.

---

## 4. §101 eligibility — frame it as a computer improvement (critical for software/math)

KV quantization is math on a computer → **subject‑matter eligibility (Alice/Mayo) is the biggest
risk**, bigger than novelty. Survive it by anchoring every independent claim to a **technical
improvement in the functioning of the computer**, not an abstract idea:

- ✅ Frame the benefit as **"increasing the number of concurrent inference sequences resident in a
  fixed GPU memory (HBM) budget"** and **"reusing compressed key‑value state across requests without
  additional quality loss,"** reducing memory bandwidth / GPU count. These are *Enfish/McRO*‑style
  improvements to computer operation, not abstract math.
- ✅ Recite **concrete hardware/serving structure**: paged HBM allocation, fused attention kernel,
  block/page layout, snapshot to a *second, lower‑cost memory tier*, restore into a *fresh paged
  allocation*. Structure defeats "do it on a generic computer."
- ✅ Tie the protected‑mask + overlay to a **measurable technical result** (retrieval fidelity at
  half the KV memory) rather than "better accuracy" in the abstract.
- ❌ Avoid claiming the quantization *formula* in isolation ("compute scale=(amax−amin)/15…") — a
  math formula per se is the classic §101 trap. Recite it as a step *within* the memory‑reduction
  serving apparatus.

---

## 5. Example draft claims (attorney to refine)

> Illustrative only — structure and coverage, not final language. One independent method claim,
> one system/apparatus claim, one CRM claim, plus dependents mapping to N1–N6.

### Independent Claim 1 (method — the integrated compression + serving system, N3)
> 1. A method of serving a transformer language model, comprising:
> **(a)** obtaining, for the model, a **static protection mask** that identifies, for each of a
> plurality of attention layers and each key‑value head, a proper subset of key channels selected
> as protected channels, wherein the mask is derived **once per model** by (i) processing a
> calibration corpus through the model, (ii) accumulating, per layer, per key‑value head, and per
> channel, an aggregate magnitude statistic of key activations captured during prefill, and
> (iii) selecting, per layer and per key‑value head, the channels having the largest aggregate
> magnitude, the mask being **shared across all inference sequences**;
> **(b)** during inference, storing keys and values of the model's key‑value cache in a paged
> memory as **4‑bit quantized codes**, wherein non‑protected key channels are quantized with a
> **per‑block, per‑channel asymmetric affine** quantization and values are quantized with a
> per‑token, per‑group asymmetric affine quantization, and wherein the **protected key channels
> are additionally retained at a higher precision** than 4 bits;
> **(c)** computing attention by a fused kernel that reads the 4‑bit codes and per‑block
> reconstruction parameters from the paged memory, **dequantizes them in‑register**, and
> **substitutes the higher‑precision protected key channels in place of their dequantized values**
> prior to computing the attention inner product, **without materializing a full‑precision copy**
> of the key‑value cache; and
> **(d)** routing memory‑bound sequences to the paged 4‑bit path so as to increase the number of
> concurrent sequences resident in a fixed accelerator memory budget.

### Independent Claim 2 (system — warm‑tier byte‑faithful reuse, N2)
> 2. A system comprising one or more accelerators and a memory hierarchy, configured to:
> maintain a key‑value cache of a transformer model as **4‑bit quantized codes plus reconstruction
> sidecars and a protected‑channel store** in a paged first‑tier (accelerator) memory;
> **snapshot** the compressed key‑value state of a prefix — comprising the packed key codes,
> packed value codes, key scale, key minimum, protected‑channel store, value scale, and value
> minimum, together with a **format identifier** — to a lower‑cost second‑tier memory; and later
> **restore** said snapshot **bit‑identically** into a freshly allocated paged region for a
> subsequent request, **conditioned on a compatibility check** that verifies matching geometry
> (head dimension, block size, protected‑channel count) and format and enforces a one‑to‑one,
> ordered block mapping, such that reuse of the compressed key‑value state across requests
> **introduces no additional quantization error**.

### Independent Claim 3 (CRM)
> 3. A non‑transitory computer‑readable medium storing instructions that, when executed, cause a
> system to perform the method of claim 1.

### Dependent claims (map to the ranked novelties)
> 4. (N1) …wherein the aggregate magnitude statistic is a **maximum absolute value** of key
> activations accumulated as a maximum across the calibration corpus, and the selected proper
> subset is a fixed fraction (e.g., ~4%) of channels per layer per key‑value head.
> 5. (N1) …wherein the static protection mask is **compatible with prefix caching** in that a
> single mask is applied unchanged to every sequence sharing a cached prefix.
> 6. (N5) …wherein the protected key channels are **also stored as 4‑bit codes** in the paged
> memory but are **overridden** by the higher‑precision values during said in‑register
> substitution, so the paged layout is uniform across channels.
> 7. (N4) …wherein the higher‑precision protected‑channel store is an **8‑bit per‑channel
> asymmetric** representation whose per‑channel bounds are derived from calibration‑time signed
> minima and maxima **widened outward by a margin factor** to provide clipping headroom for
> activations exceeding the calibration extremes.
> 8. (N3) …wherein **values are never protected** and only keys carry protected channels.
> 9. …wherein the model is unmodified (no retraining or quantization‑aware fine‑tuning) and the
> method is applied as a **drop‑in serving backend**.
> 10. (N6) …wherein the same calibration method produces a deployable mask artifact across
> multiple model families **without model‑family‑specific code changes**.
> 11. (N2) …wherein the second‑tier memory is host DRAM or NVMe flash, and the restored compressed
> state is **byte‑identical** to the snapshotted state.
> 12. …further comprising **refusing** a restore when the snapshot's geometry or format identifier
> does not match the target writer's.
> 13. (N5b) …wherein keys are quantized with **one set of reconstruction parameters per fixed‑size
> block of tokens**, and a still‑filling trailing block is held in a per‑sequence staging buffer and
> **re‑quantized at each decode step** to present a self‑consistent set of codes and reconstruction
> parameters to the fused kernel, while completed blocks are read without re‑quantization.
> 14. (N3b) …wherein a stored compressed prefix is located for reuse by computing a **chained hash
> per completed block**, matching a request's blocks **deepest‑first**, and verifying the matched
> block count to guard against hash collision, so the longest byte‑faithfully‑restorable prefix is
> reused.

---

## 6. What each independent claim buys you (coverage map)

- **Claim 1** covers the **in‑GPU compression + fused overlay + shared static calibrated mask +
  routing** — the core product. Dependents 4–10 harden it against design‑arounds (different
  statistic, different protected‑store precision, V‑protection variants).
- **Claim 2** covers the **warm‑tier byte‑faithful reuse** independently — valuable because it
  reads on the *expansion* (KVPro WarmTier) and on competitors who add lossless reuse of
  *compressed* KV even with a different quantizer.
- Consider a **fourth independent claim** to the **calibration method alone** (N1/N6): "a method of
  producing a shared static protection mask for a transformer model" — a process claim that reads
  on anyone who *generates* the artifact, not just who serves with it.

---

## 7. Provisional filing strategy & next steps

1. **File a US provisional (35 U.S.C. §111(b)) now.** It is cheap, needs no formal claims, and
   sets your priority date. But it **only** gives priority to what it **describes and enables** —
   so make it *rich*:
   - Include this technical description (§1), the **exact formulas and granularities**, the
     calibration algorithm, the kernel overlay semantics, the snapshot/restore format and guards,
     block/page layout, and the **best mode** (4% protect, BS=32, v_group=32, prot‑int8 margin 1.1).
   - Attach the key source files / pseudocode as an appendix and figures (write path, read/overlay
     path, snapshot/restore path, calibration pipeline). Breadth of disclosure now = breadth of
     claims you can pursue in the next 12 months.
2. **Within 12 months**, file the **non‑provisional** (and a **PCT** if you want foreign rights)
   claiming priority. Draft the real claims with counsel around N1–N6.
3. **Prior‑art search before drafting claims** — have counsel (or a search firm) pull and read:
   **KIVI, KVQuant, GEAR, KVTuner, SAW‑INT4, TurboQuant/QJL, CacheGen, H2O, Atom, QServe/Marlin,
   FlexGen**, and vLLM's paged‑attention/prefix‑caching disclosures. Your positioning memo already
   maps most of these — hand it to counsel.
4. **Inventorship & assignment.** Identify every person who contributed to the *conception* of
   N1–N6 (not just coders of obvious parts). Ensure **assignments to Ugence Labs** are executed
   (and check any employer/contractor IP clauses). Wrong inventorship can invalidate a patent.
5. **Disclosure hygiene until filed.** Keep the *method* NDA‑only (as you already do). Do not post
   the mechanism publicly, present it un‑NDA'd, or push it to a public repo before the provisional
   is on file. If this repository is or becomes public, treat that as a disclosure event and tell
   counsel the date.
6. **§101 framing** (§4 above) baked into every independent claim.
7. **Drafting caveat — pick one canonical quantization convention.** The tree contains **two
   numerically distinct nibble parameterizations**: the **production** paged path uses **unsigned
   codes `[0,15]` + a stored `xmin` offset** (asymmetric affine), while the standalone Triton
   sketch kernel uses **signed codes `(nibble − 8)` + scale**. They are the same idea in different
   coordinates. Claim the **unsigned‑affine + xmin** production convention (it is the byte‑faithful
   path that everything else — snapshot, restore, splice — is built on), and have counsel write the
   dequant step at a level of generality that reads on both parameterizations.

---

## 8. Invention B — the consistency‑scored cache (separate potential filing)

`symbolu_core/ontological/kv_cache_enhanced.py` implements a **different** idea worth its own
attorney conversation: scoring each KV‑cache entry by a **consistency Lagrangian**
`L = λf(1−sf)² + λb(1−sb)² + λc(sf−sb)²` (forward coherence sf vs backward/entropy confidence sb),
converting to a weight `exp(−β·L)`, and **pruning low‑weight entries**, combined with an
**entropy‑trend hallucination detector** (`dH/dt` spike → warning). This targets *generation
quality / hallucination*, not memory. It is more abstract (higher §101 risk — must be tied to a
concrete technical result such as cache eviction / compute saved) but is **mechanistically distinct**
from Invention A and should not be merged into the KVPro filing. Flag it; don't develop it here.

---

## 9. One‑paragraph bottom line

You **cannot** defensibly patent "low‑bit KV compression," "protected/outlier K channels,"
"asymmetric INT4," or "paged INT4" — all are prior art (KIVI/KVQuant/GEAR/KVTuner/SAW‑INT4). You
**can** pursue: **(N1)** a per‑model, prefill‑calibrated, *static sequence‑shared* protected‑channel
mask that is prefix‑cache‑compatible; **(N2)** **byte‑faithful snapshot/restore of compressed
protected‑INT4 KV** for lossless warm‑tier / cross‑session reuse with geometry/format guards;
**(N3)** the **integrated serving system** combining these with an in‑register fused‑kernel overlay
and routing; and narrower **(N4)** prot‑int8 outlier storage and **(N5)** the overlay semantics.
Frame all of it as a **technical improvement to GPU memory utilization and cross‑request state
reuse** for §101, file a **rich provisional now**, run a real prior‑art search, and lock down
inventorship/assignment — all with a registered patent attorney.
