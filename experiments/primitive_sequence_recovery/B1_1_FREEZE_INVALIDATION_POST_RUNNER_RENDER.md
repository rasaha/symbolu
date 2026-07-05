# B1.1 Freeze Invalidation — Post-Runner Real-G2P Render Leak

## Status: `FREEZE_INVALIDATED_PENDING_REFREEZE`

## 1. Scope and non-claims

Records that the finalized B1.1 artifact-set freeze is **invalidated for generation** because the B1.1
generation runner's **real-G2P render-only** validation surfaced a Sanskrit leak in the frozen bridge pool.
**No model / embedding / generation / scoring / judging ran.** This does **not** modify B1, change the B1
verdict (`RANDOM_OR_SCRAMBLED_MATCHES`), or unblock Track B (**BLOCKED**). No ontology validation, Sanskrit
privilege, or semantic-truth claim. **Structure, not validated meaning.**

## 2. Freeze lineage

- **Prior freeze finalized at:** commit `2b8e427` (`b1_1_freeze_manifest.json`, `manifest_status: FROZEN`,
  `FROZEN_NOT_AUTHORIZED_FOR_GENERATION`, finalized base `d92dc2e`).
- **Runner implemented + render-only run at:** commit `585c855`.
- **Runner render-only status:** `REVIEW_REQUIRED_BLOCKER`.

## 3. Exact leak

- **Blocker:** `FROZEN_ARTIFACT_LEAK`.
- The **frozen Śa liberating bridge** contained the Sanskrit term **`artha`**
  (`functional_operation`: "uses aim and **artha** without identity or ownership" →
  `liberating_bridge`: "purposeful action without possessive bondage — uses aim and **artha** without
  identity or ownership").
- Under **real G2P→varṇa**, every word with a /ʃ/ ("sh") sound routes to Śa; when Śa takes its liberating
  pole, `artha` enters the **model-facing conditioning** (arms A / S / R_same / R_deranged; words freedom,
  friendship, integrity, justice, mountain, ocean, patience — 10 cores). `shadow` takes Śa's binding pole,
  so it was clean.

## 4. Why the previous freeze cannot be used for generation

- Generation prompts built from the frozen bridge pool would carry a **Sanskrit term into model-facing
  text** — exactly the leakage the blinding discipline forbids (it could cue the model/judges to the
  varṇa mapping).
- The leak is in the **conditioning** (the independent variable), so it **cannot** be repaired at the
  post-generation output-leak-scan stage without changing the stimulus.
- Editing the frozen bridge pool in place would be **`INVALID_POSTHOC`**. Therefore the freeze must be
  **re-done** from an edited source lexicon under a **new manifest**.

## 5. Why the pre-freeze audit / dry run missed it

- The pre-freeze **sample-word render dry run** used **illustrative spelling-based** varṇa decomposition,
  which never routed the affected words to Śa. **Real G2P** (used by the runner) does.
- The pre-freeze **adversarial audit** used a **hardcoded** Sanskrit-term list that did not include
  `artha`. The re-freeze replaces that with a **generic** scan over every Sanskrit source-label token, and
  re-runs the dry run with **real G2P routing**.

## 6. State at invalidation

- Generation: **NOT run**. Judging/scoring: **NOT run**. Raw outputs / judge packets: **none**.
- Generation remains **UNAUTHORIZED**.
- B1 verdict: `RANDOM_OR_SCRAMBLED_MATCHES` (unchanged). Track B: **BLOCKED**.
- Track G negative anchor preserved: `RANDOM_POLARITY_EXPLAINS` (`1fe5562`; A_vs_R −0.1917, A_vs_X −0.075).

## 7. Required action (this gate: `B1_1_POSTFREEZE_LEAK_FIX_AND_REFREEZE`)

1. Minimal de-Sanskritization of Śa in the experimental lexicon (`artha` → English "worldly purpose" in
   the rendered `functional_operation`; Sanskrit provenance retained only in non-rendered
   `sanskrit_label`/`source_note`, consistent with all 34 entries).
2. Pin the four runner-discovered gaps G1–G4 into frozen config/manifest.
3. Regenerate the bridge pool and all affected reports; re-run all local validators with **real G2P**.
4. Rebuild the draft + final manifests, marking the prior freeze **superseded/invalidated**.
5. The re-freeze is `FROZEN_NOT_AUTHORIZED_FOR_GENERATION`; generation stays gated behind a later,
   separate `B1_1_GENERATION_AUTHORIZATION`.

**Structure, not validated meaning.** Freeze invalidated for generation; generation not executed, the B1
verdict stands, and Track B remains BLOCKED.
