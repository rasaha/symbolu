# B1.1 Generation Render-Only Report (structural; no model, no network)

## Status: `REVIEW_REQUIRED_BLOCKER`

Render-only structural validation of the 8-arm B1.1 runner against the **frozen** artifact set. **No model call, no download, no judging, no scoring.** This is **not** evidence that B1.1 works or outperforms B1/H2. `R_deranged` remains the crux. **Structure, not validated meaning.**

## Frozen integrity
- manifest_status: **FROZEN** · generation_authorized: **False** · freeze base `d92dc2ef6c`
- The runner **re-hashes every bound artifact first** and aborts `INVALID_POSTHOC` on any mismatch.

## Arms rendered
- Arms (exactly 8): `A`, `D`, `S`, `R_same`, `R_deranged`, `R_domain`, `C`, `X`
- Conditioning cores rendered: **200** (25 words × 8 arms)
- Full prompts that would render (word × task × arm): **800**

## Runner mechanics
- **PASS (8 arms built, seeded, deterministic, manifest-verified)** — all 8 arms built deterministically from the frozen set with frozen seeds; A uses real G2P→varṇa; R_deranged uses a seeded derangement; controls are length-matched.

## Leakage scan (model-facing text)
- **Total leak hits: 10** across 200 cores.
- Per-arm: A=3, D=0, S=3, R_same=1, R_deranged=3, R_domain=0, C=0, X=0
- Scanned for: IAST diacritics, Sanskrit labels, varṇa names, multi-char arm labels. `contrast_boundary` is **excluded** from prompts (it names varṇas → would leak).

### Leak findings (BLOCKER — originate in the FROZEN bridge pool)
- token **`artha`** (sanskrit_labels) — source Śa/liberating; appears in 10 core(s), arms ['A', 'R_deranged', 'R_same', 'S'], words ['freedom', 'friendship', 'integrity', 'justice', 'mountain', 'ocean', 'patience']. **FROZEN_ARTIFACT_LEAK — requires re-freeze (bridge pool is frozen; cannot be edited without INVALID_POSTHOC and a new manifest)**

> **Why the pre-freeze dry run missed this:** the sample-word dry run used **illustrative spelling-based** varṇa decomposition, which never routed these words to the leaking varṇa. Real G2P→varṇa (used here) does. The leak is in the **frozen** bridge pool, so it is a `FROZEN_ARTIFACT_LEAK`: generation must not run until a re-freeze removes it.

## A construction (real pipeline)
- A uses **real G2P→varṇa** (`varna_lens.phonemes_cmudict`) over the target word, then the **frozen** B1.1 bridge pool; per-varṇa pole via the vowel-attachment rule; composed in order.

## Freeze-coverage gaps (honest; do NOT block render-only, MUST be pinned before the real run)
- **G1**: A-composition pole/cap/separator NOT pinned in the frozen arm-construction config (runner uses varna_lens vowel-attachment polarity + ' ; ' + no cap).
- **G2**: contrast_boundary cannot be rendered (it names other varṇas -> would leak); kept in metadata only. The frozen config's 'preserve contrast_boundary' cannot apply to prompt text.
- **G3**: R_domain word->bucket and bridge->bucket maps NOT frozen; runner uses a build-time keyword heuristic and flags R_domain NOT_FULLY_SPECIFIED_BY_FROZEN_CONFIG.
- **G4**: word/task pool (b1_dry_run_harness.py) and D/C/X sources (b1_real_conditioning.py) are committed but NOT in the frozen artifact set.

## Model access in this environment
- torch importable: True · cuda: False · transformers: 5.13.0
- HuggingFace egress: DENIED_BY_ENV_POLICY (huggingface.co 403 CONNECT). No download attempted. Real generation must run on a model-access host (RunPod).
- Real generation is **hard-gated** (`--execute-generation` + `B1_1_GENERATION_APPROVED=YES` + model-access host) and **refuses here** before any model is contacted.

## Anchors preserved
- B1 verdict: **RANDOM_OR_SCRAMBLED_MATCHES** · Track B: **BLOCKED** · positive cap: **LIMITED_GENERATION_UTILITY** · crux: **R_deranged**
- Track G: `RANDOM_POLARITY_EXPLAINS` (`1fe5562`; A_vs_R -0.1917, A_vs_X -0.075) · fallback: **FALLBACK_QUALIFIED**

## Next gate
- **BLOCKER FIRST:** the `FROZEN_ARTIFACT_LEAK` (see leak findings) must be resolved by a **re-freeze** (edit the source lexicon/bridge under a new manifest — the current freeze cannot be edited without `INVALID_POSTHOC`). The pre-freeze audit/dry-run should be re-run with **real G2P** (not illustrative spelling) so latent varṇa-routing leaks are caught.
- Then **`B1_1_RUNPOD_GENERATION_EXECUTION_PLAN`** — plan the real run on a model-access host; resolve gaps G1–G4 into frozen artifacts before generating. Generation remains **unauthorized here**.

**Structure, not validated meaning.** Render only; the B1 verdict stands and Track B remains BLOCKED.
