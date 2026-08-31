# KVPro Provisional — Figure Specifications (FIG. 1–8)

**For:** the patent illustrator / counsel. **Companion to:** `KVPRO_PROVISIONAL_DRAFT_v1.md` §4–§5.
These are **drawing specs**, not final art. Follow USPTO drawing rules: black‑and‑white line art,
no shading/grayscale, number every element with a reference numeral, use lead lines, and keep each
figure to one sheet. Reference numerals below are suggestions — keep them consistent across figures
(e.g., the static mask is **150** everywhere). Label flows with arrows; label alternatives with
"(embodiment)" where noted. **No color, no photographs, no screenshots.**

---

## FIG. 1 — End‑to‑end pipeline (system overview)
**Purpose:** one‑glance map of the whole system; anchors §101 "improvement to computer functioning."

Left‑to‑right block flow, five stages, each a labeled box:
- **100 Unmodified transformer model** → feeds **110 Calibration (one‑time, per model)** → emits
  **150 Static protection mask (per‑model artifact)**.
- **150** feeds both **200 Dual‑precision write path** and **300 Fused read / overlay path**.
- **200** writes into **250 Paged accelerator memory (HBM)** (draw as a grid of blocks/pages).
- **300** reads from **250**, produces **310 Attention output**.
- **250** ↔ **400 Snapshot / Restore** ↔ **450 Secondary memory tier (DRAM / NVMe)**.
- **500 Prefix reuse / router** sits above, drawing arrows from incoming **requests A, B, C** into
  **250**/**450**, annotated "shared static mask 150 across all requests."

Callouts (dashed): near **250**, "≈0.5× KV memory → ≈2× concurrent sequences." Near **500**,
"prefix reuse enabled by static mask." Keep it schematic — detail is in later figures.

---

## FIG. 2 — Calibration data flow (Concept A)
**Purpose:** how the static mask is produced.

Top‑to‑bottom:
- **120 Calibration corpus** (box, label "N diverse prompts, e.g. 50–1000") → into **100 model**
  (prefill only, label "sequence length > 1").
- From each attention layer, a **130 K‑capture hook** taps the **key tensor** (label
  "post‑projection K, per layer *l*, head *h*, channel *d*").
- Hook feeds **140 Importance accumulator**: show the operation
  `mag[l,h,d] = max_prompts( max_tokens |K| )` in a small formula box (label "max‑of‑maxes";
  alt‑metrics footnote: "variance / entropy / Fisher / learned (embodiment)").
- **140** → **145 Top‑N selection per (layer, head)** (label `N = round(D · protect_fraction)`,
  "e.g. 4%").
- **145** → **150 Static protection mask** drawn as a 3‑D array `(num_layers × H_kv × D)` with a
  few cells shaded‑by‑hatching = protected. Annotate "shared across all sequences."
- Optional branch (dashed, embodiment): **140** also emits **148 per‑channel signed min/max,
  margin‑widened** → into the higher‑precision store of FIG. 4.

---

## FIG. 3 — In‑register reconstruction and overlay (Concept C) — the SAW distinction
**Purpose:** show reconstruction happens in‑register with a conditional select and **no rotation,
no full‑precision buffer**. This figure carries claim 1C.

Center: a box **300 Fused attention kernel** with an inner **"registers / on‑chip"** dashed
boundary. Inside, sequence of small ops:
1. **320 Load packed nibbles + sidecars** from **250** (arrow in from paged memory).
2. **330 Unpack nibble → code**.
3. **340 Dequantize:** formula box `x̂ = q · scale + xmin`.
4. **350 Conditional overlay:** a MUX/select symbol fed by three inputs — `x̂` (from 340), the
   **360 protected‑channel value** (higher precision), and **150 mask bit** as the selector; output
   labeled `select(mask[l,h,d], protected, x̂)`.
5. **370 tl.dot(Q·Kᵀ) → softmax → ·V** → **310 output**.

Explicit **negative‑space callouts** (important for distinguishing prior art), drawn as crossed‑out
boxes outside the register boundary:
- ⊘ **380 "No matrix rotation of the cache"** (contrast: SAW‑INT4 / QuaRot).
- ⊘ **390 "No full‑precision KV reconstructed in memory"**.

---

## FIG. 4 — Uniform paged byte layout vs. sparse (Concept B)
**Purpose:** show the dense/deterministic layout; contrast with sparse outlier storage.

Two side‑by‑side panels:
- **Panel A (invention) — 250 Paged block, uniform layout.** Draw one block `(BS tokens × H heads ×
  D channels)`. Show a byte‑strip: **210 nibble‑packed codes** ("2 codes/byte, contiguous along D")
  occupying the first half of the strip; then small sidecar boxes **220 k_scale / k_xmin (per
  block)**, **230 v_scale / v_xmin (per token‑group)**, **240 protected‑channel store (per block)**.
  Annotate "protected channels sit on the same regular grid, overridden at read → deterministic,
  coalesced access."
- **Panel B (prior art, for contrast) — sparse outlier layout.** Show scattered outlier entries with
  an index/coordinate list and irregular arrows into a dense matrix. Label "sparse ops / irregular
  access — fights fused kernels (e.g. KVQuant)."

Small legend maps hatch patterns to K‑codes / V‑codes / scale / xmin / protected.

---

## FIG. 5 — Partial‑tail (splice) re‑quantization (Concept C detail)
**Purpose:** block‑granular quantization coexisting with token‑at‑a‑time decode.

- A row of **250 completed blocks** (label "read as‑is, not re‑quantized").
- A **260 trailing partial block** partially filled (some token slots empty), held in a **265
  per‑sequence staging buffer** (dashed box off to the side).
- Arrow "decode step t appends 1 token" into **265**; then **270 re‑quantize staging buffer**
  (formula box `scale=((max−min)/15).clamp; q=round((x−min)/scale)`) → overwrites the trailing
  block's `(codes, scale, xmin)` slice presented to **300**.
- Annotate "completed blocks: 0 re‑quant; only the filling tail is re‑quantized each step."

---

## FIG. 6 — Snapshot / restore with validation guards (Concept D)
**Purpose:** byte‑faithful persistence gated by validation.

Two lanes, mirror images:
- **Snapshot lane:** **250 paged block** → **410 serialize 7 tensors** (list them in a stacked box:
  packed_k, packed_v, k_scale, k_xmin, k_protect, v_scale, v_xmin) **+ 415 format identifier** →
  **450 secondary tier (DRAM/NVMe)**. Optional **418 integrity value (hash/checksum)**.
- **Restore lane:** **450** → **420 validation gate** drawn as a diamond decision with three checks
  listed: "geometry match (D, BS, N)?", "format compatible?", "block count 1:1 in order?" →
  **YES** → **430 write back into freshly allocated block** (label "byte‑for‑byte identical");
  **NO** → **440 refuse restore** (label "reject — no silent corruption").
- Small inset formula box **435**: "reconstruction is identity on the code lattice →
  re‑encode(dequant(code)) = code ⇒ byte‑faithful." Annotate "reuse adds no additional error."

---

## FIG. 7 — Chained per‑block prefix hashing & multi‑tier reuse (Concept E)
**Purpose:** how a shared prefix is found and reused across tiers with the same static mask.

- Top: a token stream split into **completed blocks B0, B1, B2, …**. Under each, a **hash node**
  showing **chaining**: `H0 = h(B0)`, `H1 = h(H0 ‖ B1)`, `H2 = h(H1 ‖ B2)` (label "each block hash
  depends on all prior tokens").
- A **510 prefix store / manifest** table: rows = (chained key, n_blocks, tier, path).
- **520 Deepest‑first match**: incoming request's block hashes compared top‑down; show the **longest
  matching prefix** highlighted, with a **525 collision guard** note ("verify matched n_blocks =
  i+1").
- Matched prefix restored (via FIG. 6) from whichever tier — draw three tiers **530 GPU HBM / 540
  host DRAM / 550 NVMe** — all annotated "same static mask 150 applies in every tier."

---

## FIG. 8 — Static vs. dynamic mask (core narrative, Concept E)
**Purpose:** the teaching‑away picture; why static unlocks reuse. This is the money figure.

Two panels:
- **Panel A — Dynamic / per‑sequence (prior‑art instinct):** Request A computes **mask_A** from its
  own activations; Request B computes **mask_B**. Show a cached prefix from A; an arrow from B trying
  to reuse it hits a ⊘ **"mask mismatch — prefix not reusable"**. Side note stack: "per‑prefix mask
  storage O(prefixes)", "cache fragmentation", "complex batching".
- **Panel B — Static / per‑model (invention):** single **150 mask** feeds Requests A, B, C
  identically; A's cached prefix flows freely to B and C (green‑path arrows, but keep B/W: solid
  bold arrows) labeled "any request reuses any shared prefix". Side note stack: "one mask O(1)",
  "unified cache", "simple batching", and a callout to **§8.1**: "measured: exact BF16 retrieval
  retained at static 4% across 4 models."

---

## Numeral index (keep consistent)
100 model · 110 calibration · 120 corpus · 130 K‑capture hook · 140 importance accumulator ·
145 top‑N select · 148 signed min/max · 150 static mask · 200 write path · 210 packed codes ·
220 k scale/xmin · 230 v scale/xmin · 240/360 protected store/value · 250 paged HBM ·
260 partial block · 265 staging buffer · 270 re‑quant · 300 fused kernel · 310 output ·
320 load · 330 unpack · 340 dequant · 350 overlay select · 370 attention matmul ·
400 snapshot/restore · 410 serialize · 415 format id · 418 integrity · 420 validation gate ·
430 restore · 440 refuse · 450 secondary tier · 500 router/reuse · 510 prefix store ·
520 deepest‑first match · 525 collision guard · 530/540/550 HBM/DRAM/NVMe.
