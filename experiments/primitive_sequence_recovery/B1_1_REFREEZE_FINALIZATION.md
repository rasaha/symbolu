# B1.1 Re-Freeze Finalization (post real-G2P leak fix + G1–G4 pinning)

## Status: `REFREEZE_FINALIZED_UNDER_FALLBACK_QUALIFICATION`

## 1. Scope and non-claims

Finalizes the **re-freeze** of the B1.1 artifact set after the post-freeze real-G2P render-only leak
(`FROZEN_ARTIFACT_LEAK`: `artha` in the Śa liberating bridge) was fixed and the four runner-discovered
gaps (G1–G4) were pinned. **This freezes the artifact set only; it does NOT authorize generation.** No
model / embedding / generation / scoring / judging ran. Does **not** modify B1, change the verdict
(`RANDOM_OR_SCRAMBLED_MATCHES`), or unblock Track B (**BLOCKED**). No ontology validation, Sanskrit
privilege, or semantic-truth claim. **Structure, not validated meaning.**

## 2. Supersession

- **Prior freeze `2b8e427` is superseded/invalidated for generation** (see
  `B1_1_FREEZE_INVALIDATION_POST_RUNNER_RENDER.md`). The prior manifest could not be used because its
  frozen bridge pool carried Sanskrit `artha` into model-facing conditioning under real G2P.
- The new final manifest records `supersedes.prior_freeze_commit: 2b8e427` and the invalidation reason.

## 3. The Śa fix

- Edited **only** the experimental lexicon's Śa `functional_operation`:
  `"uses aim and artha ..."` → `"uses aim and worldly purpose without identity or ownership"`.
- `artha` is **absent from every model-facing bridge/conditioning** (verified by the generic
  Sanskrit-label scan and the real-G2P render). It is retained **only** in the non-rendered
  `sanskrit_label`/`source_note` provenance, consistent with all 34 entries citing their classical source.
- Meaning preserved: worldly purpose / aim without possession, ownership, status, or control; not
  anti-worldliness, not renunciation, no good/bad framing.

## 4. G1–G4 resolution

- **G1 (A-composition):** pinned in `b1_1_arm_construction_config.json` `arms.A.composition_policy`
  (real-G2P routing only; consonants-only; vowel-attachment pole rule; bridge-pool-only meaning; order;
  `" ; "` separator; no cap; `contrast_boundary` not rendered). The runner reads the separator from config.
- **G2 (contrast_boundary):** pinned `METADATA_ONLY` (arm + leak configs); never rendered. The runner
  composes A/S from `binding_bridge`/`liberating_bridge` only.
- **G3 (R_domain buckets):** pinned `bucket_keyword_map` + bucket order + native/mismatched derivation +
  `length_parity_rule` + seed in the arm config; the runner **loads** them from config; per-word
  assignments persisted to `b1_1_r_domain_assignments.json` (deterministic; referenced in the manifest).
- **G4 (pool + D/C/X + G2P source):** paths recorded in the generation config and **hash-bound** in the
  manifest `referenced_source_hashes` (word/task pool, D/C/X, D-table, word list, G2P-routing module).

## 5. Validation results (all local; no model)

| gate | result |
|---|---|
| lexicon validator | **18/18 PASS** |
| bridge pool generator/validator | **PASS_BRIDGE_DRAFT** (68 phrases, distinct, forbidden-clean, distinctions ✓) |
| local lexical similarity audit | **SOFT_REVIEW_REQUIRED** (0 hard, 2 soft; FALLBACK, unchanged) |
| freeze artifact validator | **READY_FOR_FREEZE_REVIEW** (0 blockers, 1 judge warning) |
| generation runner render-only (REAL G2P) | **PASS_RENDER_ONLY** (200 cores, **leak_total 0**) |
| sample-word render dry run (REAL G2P) | **PASS_RENDER_DRY_RUN** (0 leak, 0 weak controls) |
| pre-freeze adversarial audit (REAL G2P, generic scan) | **PASS_PREFREEZE_AUDIT** (0 blockers) |
| final manifest verifier | **MANIFEST_VERIFIED** (12 bound artifacts) |

## 6. Leakage result under real G2P

- Generic Sanskrit-label-token scan over all 68 bridges: **0**. IAST: **0**. varṇa-names: **0**.
  arm-labels: **0**. Real-G2P render-only conditioning: **leak_total 0** over 200 cores. `artha`: **gone**
  from all model-facing text.

## 7. Final manifest

- `b1_1_freeze_manifest.json` — **`manifest_status: FROZEN`**, **`freeze_status:
  FROZEN_NOT_AUTHORIZED_FOR_GENERATION`**, `generation_authorized: false`.
- **`FALLBACK_QUALIFIED`**; embedding gate **`BLOCKED_DEPENDENCY_UNAVAILABLE`** (still owed).
- Anchors preserved: B1 `RANDOM_OR_SCRAMBLED_MATCHES`; Track B `BLOCKED`; Track G
  `RANDOM_POLARITY_EXPLAINS` (`1fe5562`; A_vs_R −0.1917, A_vs_X −0.075); positive cap
  `LIMITED_GENERATION_UTILITY`; **`R_deranged` remains the crux**.
- Meta-Llama-3-8B `ACCEPT_WITH_CAVEAT` retained.

## 8. What this does and does not authorize

- **Does:** re-freeze the B1.1 artifact set and bind its hashes (`INVALID_POSTHOC` on any post-freeze edit).
- **Does NOT:** authorize generation, judging, or scoring. A separate explicit
  **`B1_1_GENERATION_AUTHORIZATION`** gate is required, and generation cannot run in this environment
  (HuggingFace egress denied).

## 9. Final status block

```
refreeze_decision:     REFREEZE_FINALIZED_UNDER_FALLBACK_QUALIFICATION
manifest_status:       FROZEN
freeze_status:         FROZEN_NOT_AUTHORIZED_FOR_GENERATION
supersedes:            2b8e427 (prior freeze; invalidated for generation)
manifest_verifier:     MANIFEST_VERIFIED (12 bound + 5 referenced-source hashes + rda ref)
real_g2p_leak_total:   0
Śa artha in prompts:   NONE (retained only in non-rendered provenance)
G1-G4:                 PINNED
embedding_gate:        BLOCKED_DEPENDENCY_UNAVAILABLE (owed) · FALLBACK_QUALIFIED
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES (unchanged)
Track B:               BLOCKED
generation_authorized: NO
generation_executed:   NO · judging/scoring: NO
```
Preserved prior: Track G `RANDOM_POLARITY_EXPLAINS` (`1fe5562`) · Track F `CORRECTNESS_DEGRADED`.

## 10. Next gate

**`B1_1_RUNPOD_GENERATION_EXECUTION_PLAN`** — plan the real run on a model-access host using the re-frozen
manifest only. Generation remains **unauthorized** here.

**Structure, not validated meaning.** The artifact set is re-frozen; generation remains unauthorized, the
B1 verdict stands, and Track B remains BLOCKED.
