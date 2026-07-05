# B1.1 Generation Render-Only Report (structural; no model, no network)

## Status: `PASS_RENDER_ONLY`

Render-only structural validation of the 8-arm B1.1 runner against the **frozen** artifact set. **No model call, no download, no judging, no scoring.** This is **not** evidence that B1.1 works or outperforms B1/H2. `R_deranged` remains the crux. **Structure, not validated meaning.**

## Frozen integrity
- manifest_status: **FROZEN** · generation_authorized: **False** · freeze base `2026-07-05`
- The runner **re-hashes every bound artifact first** and aborts `INVALID_POSTHOC` on any mismatch.

## Arms rendered
- Arms (exactly 8): `A`, `D`, `S`, `R_same`, `R_deranged`, `R_domain`, `C`, `X`
- Conditioning cores rendered: **200** (25 words × 8 arms)
- Full prompts that would render (word × task × arm): **800**

## Runner mechanics
- **PASS (8 arms built, seeded, deterministic, manifest-verified)** — all 8 arms built deterministically from the frozen set with frozen seeds; A uses real G2P→varṇa; R_deranged uses a seeded derangement; controls are length-matched.

## Leakage scan (model-facing text)
- **Total leak hits: 0** across 200 cores.
- Per-arm: A=0, D=0, S=0, R_same=0, R_deranged=0, R_domain=0, C=0, X=0
- Scanned for: IAST diacritics, Sanskrit labels, varṇa names, multi-char arm labels. `contrast_boundary` is **excluded** from prompts (it names varṇas → would leak).

## A construction (real pipeline)
- A uses **real G2P→varṇa** (`varna_lens.phonemes_cmudict`) over the target word, then the **frozen** B1.1 bridge pool; per-varṇa pole via the vowel-attachment rule; composed in order.

## Freeze-coverage gaps (honest; do NOT block render-only, MUST be pinned before the real run)
- **G1 (RESOLVED)**: A-composition policy (pole rule, no cap, separator) is now pinned in b1_1_arm_construction_config.json arms.A.composition_policy; the runner reads the separator from it.
- **G2 (RESOLVED)**: contrast_boundary is pinned METADATA_ONLY in arm/leak configs and is never rendered; the runner composes A/S from binding_bridge/liberating_bridge only.
- **G3 (RESOLVED)**: R_domain bucket_keyword_map + bucket order + derivation rules + seed are pinned in the frozen arm config; the runner loads them from config and persists b1_1_r_domain_assignments.json.
- **G4 (RESOLVED)**: word/task pool + D/C/X + G2P-routing source paths are recorded in the generation config and hash-bound in the freeze manifest referenced_source_hashes.

## Model access in this environment
- torch importable: True · cuda: False · transformers: 5.13.0
- HuggingFace egress: DENIED_BY_ENV_POLICY (huggingface.co 403 CONNECT). No download attempted. Real generation must run on a model-access host (RunPod).
- Real generation is **hard-gated** (`--execute-generation` + `B1_1_GENERATION_APPROVED=YES` + model-access host) and **refuses here** before any model is contacted.

## Anchors preserved
- B1 verdict: **RANDOM_OR_SCRAMBLED_MATCHES** · Track B: **BLOCKED** · positive cap: **LIMITED_GENERATION_UTILITY** · crux: **R_deranged**
- Track G: `RANDOM_POLARITY_EXPLAINS` (`1fe5562`; A_vs_R -0.1917, A_vs_X -0.075) · fallback: **FALLBACK_QUALIFIED**

## Next gate
- **`B1_1_RUNPOD_GENERATION_EXECUTION_PLAN`** — plan the real run on a model-access host.
- Then **`B1_1_RUNPOD_GENERATION_EXECUTION_PLAN`** — plan the real run on a model-access host; resolve gaps G1–G4 into frozen artifacts before generating. Generation remains **unauthorized here**.

**Structure, not validated meaning.** Render only; the B1 verdict stands and Track B remains BLOCKED.
