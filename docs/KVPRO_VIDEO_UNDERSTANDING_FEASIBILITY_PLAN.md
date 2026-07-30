# KVPro × Video-Understanding — Target Market + Feasibility Gate (pre-registered)

**Internal engineering plan.** Question: does KVPro's channel-protected INT4 KV compression carry over
from text to **video-understanding VLMs** (video → text: Q&A, captioning, summarization)? This is the
**only** video direction where KVPro's mechanism (a growing autoregressive KV cache) even exists — not
diffusion generation, not encoder models like V-JEPA. **Pre-registered:** the go/no-go gates are fixed
below *before* running. Evidence labels: **MEASURED / MODELED / INFERRED / RESOURCE_BLOCKED**.

Status: **harness built, go/no-go logic CPU-unit-tested (4/4 pass); model capture pod-only, not yet run.**

---

## 1. Why this is the fit (and what isn't)

A video-understanding VLM is a **long-context text decoder** where much of the context is **visual
tokens**. Video is a KV-cache monster — a short clip is tens of thousands of visual tokens before the
model writes a word — so the decoder KV cache dominates memory. That is exactly KVPro's regime:
long-context, memory/capacity-bound, quality-critical. **Not** in scope: diffusion image/video
*generation* (no growing KV cache) and **V-JEPA / CLIP / ViT encoders** (representation models, no
autoregressive decode). *(INFERRED — KVPro validated on text only; this plan tests the transfer.)*

**Model under test: Qwen2.5-VL-7B-Instruct** — its language backbone *is* Qwen2.5, the family our KVPro
tooling already covers, so this tests transfer rather than a new integration. (InternVL2.5, LLaVA-Video
are alternates on the same backbones.)

---

## 2. Target market (unvalidated — a market map, not a customer list)

KVPro helps whoever **serves long-video VLM inference at scale, is memory/capacity-bound, quality-
critical, and does not build their own KV-compression kernels.**

- **Realistic buyers:** **inference providers** (Together, Fireworks, Baseten, DeepInfra) serving VLMs;
  and **vertical video-AI vendors** — moderation (Hive), meetings/sales (Gong, Otter), security/bodycam
  (Verkada, Ambient.ai, Axon), creator-clip (Opus Clip), sports (Hudl).
- **Build-it-themselves (hard to sell):** hyperscale platforms (YouTube, TikTok, Meta).
- **Strongest wedge:** quality-critical segments — **moderation, security/bodycam, healthcare, legal** —
  where a cheap wrong token has real consequences (KVPro's "quality held" beats cheap KV quant, and they
  may pay for a guaranteed-full-fidelity tier).

**Honest:** target market, **gated on the feasibility result below.** No video customer or benchmark
exists yet.

---

## 3. The feasibility gate — Phase 1 (cheap, decisive)

KVPro's quality trick works **only if a small set of channels carries outsized magnitude** (the
protected channels). Phase 1 captures the Qwen2.5-VL KV cache over video and asks, **visual vs text
tokens**, three pre-registered questions:

| Gate | Metric | Pre-registered threshold |
|---|---|---|
| **G1 Structure** | do a few channels dominate visual KV? (top-4% energy share / fair share) | concentration ratio ≥ **3.0** |
| **G2 Protection** | does keeping top-4% channels exact cut INT4 error on visual KV? | int4 err / int4+protect err ≥ **1.30** |
| **G3 Transfer** | do visual outlier channels overlap text's? (one static mask covers both) | mask IoU ≥ **0.50**, *or* union mask ≤ **2×** the 4% budget |

**Verdicts:** `GO` (all pass, mask transfers) · `GO_WITH_COMBINED_MASK` (union mask covers both) ·
`GO_BUT_MASK_DOES_NOT_TRANSFER` (visual needs its own mask) · `NO_GO_PROTECTION` (outliers exist but
protection doesn't help) · `NO_GO_STRUCTURE` (visual KV is diffuse — protection can't work).

Also **MEASURED** in the same pass: **KV-cache growth vs clip length** (8→32→128 frames) — the
memory-bound-ness where a density win would live. This alone quantifies the problem even if the
verdict is NO_GO.

---

## 4. Phase 2 — end-to-end quality (only if Phase 1 = GO*)

Run video-QA (e.g., a public video-QA set) with the KV cache reconstructed under INT4+protect vs BF16,
and measure task accuracy delta with a **pre-registered equivalence margin** (accuracy ≥ BF16 − 1 pt).
Heavier (needs generation + a benchmark); gated on Phase 1 to avoid wasted effort.

---

## 5. Harness

- `scripts/kvpro_video_understanding/capture_vlm_kv.py` — **pod-only**: loads Qwen2.5-VL, feeds a video
  at several frame counts, dumps per-layer KV split by visual/text token, + `kv_growth.json`.
- `scripts/kvpro_video_understanding/analyze_kv_outliers.py` — **CPU**: computes G1/G2/G3 and emits the
  verdict JSON + per-layer CSV. No GPU/model needed.
- `scripts/kvpro_video_understanding/test_analyze_kv_outliers_cpu.py` — **CPU unit test (4/4 pass)**:
  proves the verdict flips correctly (GO when visual matches text; NO_GO_STRUCTURE when diffuse;
  mask-mismatch when outliers differ). **TEST-BACKED.**
- `scripts/kvpro_video_understanding/run_commands.sh` — pod orchestration.

---

## 6. What's measured vs blocked

- **TEST-BACKED (here, CPU):** the go/no-go analysis logic (unit test).
- **RESOURCE_BLOCKED (pod-only):** the actual Qwen2.5-VL KV capture, the KV-growth numbers, and Phase 2
  video-QA quality — all need a GPU + the model + a video, unavailable in this authoring environment.

---

## 7. Decision

Phase 1 returns a **GO/NO-GO with a reason**, plus measured KV-growth. `GO*` → run Phase 2 quality →
if within margin, KVPro-on-video-understanding is real and the §2 market is addressable. `NO_GO_*` →
we say so plainly and don't pursue the market. **Measure first, then pitch.**
