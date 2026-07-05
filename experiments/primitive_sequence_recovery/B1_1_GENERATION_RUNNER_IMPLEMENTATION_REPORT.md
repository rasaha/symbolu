# B1.1 Generation Runner Implementation Report (render-only; no generation)

## 1. Scope and non-claims

Implements the B1.1 **8-arm generation runner** (`run_b1_1_generation.py`) and runs it in **render-only**
mode. **No model call, no download, no judging, no scoring, no freeze/authorization change.** Does **not**
modify any frozen artifact, does **not** edit the freeze manifest, does **not** change the B1 verdict
(`RANDOM_OR_SCRAMBLED_MATCHES`), and does **not** unblock Track B (**BLOCKED**). No ontology validation,
Sanskrit privilege, or semantic-truth claim. **Structure, not validated meaning.**

## 2. What was built

`experiments/primitive_sequence_recovery/run_b1_1_generation.py` — a render-only-safe runner whose real
generation path is hard-gated behind three independent locks. It:

1. **Verifies the frozen manifest first** (`b1_1_freeze_manifest.json`) by re-hashing every one of the 12
   bound artifacts; aborts **`INVALID_POSTHOC`** on any mismatch (verified by tamper test → correctly
   aborted, then the frozen manifest was restored byte-identically).
2. **Loads only the frozen configs** (bridge pool, arm-construction, seeds, generation, leak/packet,
   lexicon) via the paths in the verified manifest.
3. **Builds exactly the 8 frozen arms** `A / D / S / R_same / R_deranged / R_domain / C / X`
   deterministically, with seeds from the frozen `b1_1_seeds_config.json`:
   - **A** — real **G2P→varṇa** (`varna_lens.phonemes_cmudict`) over the target word; per-varṇa pole via
     the varna_lens vowel-attachment rule; composed from the **frozen** bridge pool in order.
   - **S** — the word's own varṇa bridges, seeded scramble of order (`arm_construction_seed`).
   - **R_same** — seeded sample from the 68-phrase pool, **excluding the target's own varṇas**
     (`r_same_sample_seed`), count-matched to A.
   - **R_deranged** (the crux) — a seeded **derangement** π over the word list (π(w)≠w); word *w* receives
     the **real A mapping of π(w)** (`r_deranged_assignment_seed`).
   - **R_domain** — a fluent bridge from a deterministically **mismatched** bucket
     (`r_domain_assignment_seed`); see gap **G3**.
   - **D / C / X** — lexicon-independent controls reused from committed B1 (`b1_real_conditioning`):
     dictionary D-table, surface facts, neutral filler.
4. **`--render-only` (default, safe)** — renders prompts, hashes them, leak-scans them; **no model, no
   network**. Writes `B1_1_GENERATION_RENDER_ONLY_REPORT.{json,md}`.
5. **`--execute-generation`** — refuses unless **`B1_1_GENERATION_APPROVED=YES`**, refuses without a
   model-access host (CUDA + transformers), refuses if `--out` exists without `--resume`, and — before
   contacting any model — refuses **`REFUSED_HF_EGRESS`** in this environment. All three refusals were
   exercised and confirmed.

## 3. Render-only result

**`REVIEW_REQUIRED_BLOCKER`.** Runner mechanics **PASS** (all 8 arms built, seeded, deterministic,
manifest-verified; 200 conditioning cores over 25 words × 8 arms; 1200 full prompts would render). But the
leak scan found a **frozen-artifact leak** (§4).

## 4. Blocker: `FROZEN_ARTIFACT_LEAK` — `artha` in the frozen Śa bridge

- The frozen bridge pool's **Śa liberating bridge** contains the Sanskrit term **`artha`**
  (`"…uses aim and artha without identity or ownership"`).
- Under **real G2P→varṇa**, every word with a /ʃ/ ("sh") sound routes to Śa; when Śa takes its liberating
  pole, `artha` enters the **model-facing conditioning**. It surfaced in **10 cores** across arms
  **A / S / R_same / R_deranged**, words **freedom, friendship, integrity, justice, mountain, ocean,
  patience**. (`shadow` takes Śa's *binding* pole → clean, correctly not flagged.)
- **Why the pre-freeze dry run missed it:** the sample-word dry run used **illustrative spelling-based**
  decomposition, which never routed those words to Śa. The real G2P pipeline does. This is precisely the
  confound the render step exists to catch — an exact parallel to the pre-freeze Ca/"Viveka" catch, but
  this one only manifests under real G2P.
- **This is a leak in a FROZEN artifact.** It **cannot** be repaired post-hoc (editing the frozen bridge
  pool = `INVALID_POSTHOC`), and it is in the **conditioning** (the independent variable), so it cannot be
  scrubbed at the output-leak-repair stage without changing the stimulus. **Generation must not run** until
  a **re-freeze** removes it. I did **not** edit any frozen artifact.

## 5. Honest freeze-coverage gaps (surfaced, not resolved)

These do **not** block render-only validation but **must** be pinned in a frozen artifact before the real
run:

- **G1 — A-composition policy not frozen.** Which pole per varṇa, any cap, and the separator are **not**
  pinned in `b1_1_arm_construction_config.json`. The runner uses the varna_lens vowel-attachment polarity
  rule, no cap, and `" ; "`. Deterministic, but a design choice, not a frozen one.
- **G2 — `contrast_boundary` cannot be rendered.** The frozen config says "preserve
  functional_operation + contrast_boundary", but `contrast_boundary` names other varṇas (e.g. "not
  object-renunciation (Gha)") and would **leak the mapping**. It is kept in metadata only; the config
  wording cannot be applied literally to prompt text.
- **G3 — R_domain bucket maps not frozen.** Neither word→native-bucket nor bridge→bucket is frozen. The
  runner uses a documented **build-time keyword heuristic** so the render is fluent and leak-checkable, and
  flags R_domain `NOT_FULLY_SPECIFIED_BY_FROZEN_CONFIG`.
- **G4 — word/task pool and D/C/X sources not frozen.** They live in committed-but-not-frozen
  `b1_dry_run_harness.py` and `b1_real_conditioning.py`.

## 6. Files

- `run_b1_1_generation.py` (new) — the runner.
- `B1_1_GENERATION_RENDER_ONLY_REPORT.json` / `.md` (new) — render-only output.
- `B1_1_GENERATION_RUNNER_IMPLEMENTATION_REPORT.md` (this file).
- **No frozen artifact and no manifest was modified.**

## 7. What this does and does not authorize

- **Does:** provide a manifest-verifying, render-only-safe, hard-gated 8-arm runner and a structural render.
- **Does NOT:** run any model, judge, or score; authorize generation; freeze or unfreeze anything; unblock
  Track B; or change the B1 verdict.

## 8. Next gate

1. **Resolve the `FROZEN_ARTIFACT_LEAK`** (`artha` in Śa) via a **re-freeze** (edit the source
   lexicon/bridge under a new manifest), and re-run the pre-freeze audit/dry-run with **real G2P** (not
   illustrative spelling) so latent varṇa-routing leaks are caught. Also pin gaps **G1–G4** into frozen
   artifacts.
2. Then **`B1_1_RUNPOD_GENERATION_EXECUTION_PLAN`** — plan the real run on a model-access host. Generation
   remains **unauthorized** and cannot run in this environment (HuggingFace egress denied).

## 9. Final status block

```
runner_implemented:        YES (run_b1_1_generation.py; render-only safe, execution hard-gated)
runner_mechanics:          PASS (8 arms, seeded, deterministic, manifest-verified)
render_only_status:        REVIEW_REQUIRED_BLOCKER
blocker:                   FROZEN_ARTIFACT_LEAK (artha in frozen Śa liberating bridge; real-G2P only)
generation_executed:       NO
model_call / download:     NONE
frozen artifacts modified: NONE
manifest modified:         NO (tamper-test abort verified; manifest restored byte-identical)
manifest_verifier:         MANIFEST_VERIFIED
B1 verdict:                RANDOM_OR_SCRAMBLED_MATCHES (unchanged)
Track B:                   BLOCKED
positive cap:              LIMITED_GENERATION_UTILITY
crux:                      R_deranged
```
Preserved prior: Track G `RANDOM_POLARITY_EXPLAINS` (`1fe5562`; A_vs_R −0.1917, A_vs_X −0.075) · Track F
`CORRECTNESS_DEGRADED`.

**Structure, not validated meaning.** Runner + render only; generation not executed, the B1 verdict stands,
and Track B remains BLOCKED.
