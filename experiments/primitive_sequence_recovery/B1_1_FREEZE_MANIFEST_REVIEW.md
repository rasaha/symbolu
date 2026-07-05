# B1.1 Freeze-Manifest Review (draft, fallback-qualified)

## 1. Scope and non-claims

Reviews the **draft** freeze manifest (`b1_1_freeze_manifest.draft.json`). This is a freeze-**review**
artifact, **not** the final freeze and **not** generation authorization. **No model / embedding / generation
/ scoring / judging.** Does **not** modify B1, change the verdict (`RANDOM_OR_SCRAMBLED_MATCHES`), or unblock
Track B (**BLOCKED**). No ontology validation, Sanskrit privilege, or semantic-truth claim. **Structure, not
validated meaning.**

## 2. Freeze-readiness status

- **Regenerated** after the Ca de-Sanskritization leakage fix (`e125e0c`): the prior draft manifest's
  hashes were **stale**; this draft re-binds the current post-fix artifacts.
- Freeze-artifact validator: **`READY_FOR_FREEZE_REVIEW`** (0 blockers, 1 warning).
- Sample-word render dry run: **`PASS_RENDER_DRY_RUN`** (0 Sanskrit/varṇa leakage after the fix).
- Draft manifest status: **`DRAFT_READY_FOR_FREEZE_REVIEW`**.
- B1.1 is **not frozen**; generation is **not authorized**.

## 3. Artifact hash summary

**12 artifacts bound** with sha256 in the draft manifest (re-hashed after `e125e0c`): the lexicon, bridge
pool, six configs (arm-construction, generation, seeds, judge-panel, scorer, leak/packet), the prereg, the
bridge/prereg decision, the prereg/freeze decision, and the freeze-artifact validation report. Manifest
verifier recomputed every hash against the current artifacts → **`MANIFEST_VERIFIED`** (no mismatch).

## 4. Validator status summary

- `run_b1_1_freeze_artifact_validation.py` → `READY_FOR_FREEZE_REVIEW` (no `PLACEHOLDER_REQUIRED`, no
  `UNKNOWN_PENDING_FREEZE_REVIEW`, arms exactly the 8, primary comparisons include all three R controls,
  `generation_authorized:false`, anchors present, bridge 68/distinct/clean).
- `run_b1_1_freeze_manifest_verifier.py <draft>` → `MANIFEST_VERIFIED`.

## 5. Meta-Llama-3-8B acceptance decision

**`ACCEPT_WITH_CAVEAT`.** The candidate judge panel (Llama-3.1-8B, Meta-Llama-3-8B, gemma-2-9b-it) is
accepted for freeze review **with the explicit caveat** that Meta-Llama-3-8B required heavy
missing-final-brace repair in B1. Conditions preserved in the config + manifest: parser/QC rules remain
strict (narrow missing-final-brace repair only), judge outputs must be audited, **no post-hoc judge
selection**. The panel is **not replaced** at this gate.

## 6. Embedding-gate fallback decision

**Proceed `FALLBACK_QUALIFIED`.** The real sentence-embedding non-synonym gate remains
`BLOCKED_DEPENDENCY_UNAVAILABLE` (HuggingFace model-host egress denial) and is **still owed**. B1.1 proceeds
toward freeze on the **fallback** path (local lexical audit, surface-only), **not** the preferred
embedding-pass path. If embedding access is restored before finalization, the real gate should be run and
supersede the fallback qualification.

## 7. Remaining risks

- **Embedding gate blocked** → deep paraphrase-synonymy risk remains undetected.
- **Local lexical audit was surface-only** (`PASS_LOCAL_SURFACE_ONLY`) — not semantic contrastivity.
- **`R_deranged` remains the crux** — contrastivity cannot make A beat R if word-specific fit carries no
  signal.
- **`R_same` / `R_domain` may still match A** — the fallback cannot rule this out.
- **Meta-Llama-3-8B parser-repair caveat** — accepted, but must stay under strict repair + audit.
- **Positive result is limited to `LIMITED_GENERATION_UTILITY`** (in-architecture, this frozen design).
- **A failure cannot be rescued** into an ontology claim, and cannot unblock Track B.

## 8. What this manifest does not authorize

- It does **not** authorize generation, judging, or scoring.
- It is **not** the final freeze; the final `b1_1_freeze_manifest.json` is created only at
  **`B1_1_FREEZE_FINALIZATION`**.
- Generation requires a further, separate **`B1_1_GENERATION_AUTHORIZATION`** gate **after** freeze.

## 9. Go / no-go recommendation

**`RECOMMEND_FREEZE_FINALIZATION_UNDER_FALLBACK_QUALIFICATION`.**

All freeze artifacts exist, validate, and hash-verify; the one warning (Meta-Llama-3-8B) is decided
(`ACCEPT_WITH_CAVEAT`); the embedding-gate limitation is explicitly recorded as `FALLBACK_QUALIFIED` with the
elevated R-risk carried in the prereg. **This is a recommendation to proceed to freeze *finalization*, not
the freeze itself, and not generation.**

## 10. Next gate recommendation

**`B1_1_FREEZE_FINALIZATION`** — build and sign the final `b1_1_freeze_manifest.json` (from this reviewed
draft), moving freeze state to `FROZEN_NOT_AUTHORIZED_FOR_GENERATION`. Generation remains gated behind the
later `B1_1_GENERATION_AUTHORIZATION`.

## 11. Final status block

```
manifest_status:       DRAFT_READY_FOR_FREEZE_REVIEW
freeze_status:         READY_FOR_FREEZE_REVIEW
manifest_verifier:     MANIFEST_VERIFIED (12 artifacts)
judge decision:        Meta-Llama-3-8B ACCEPT_WITH_CAVEAT
embedding decision:    FALLBACK_QUALIFIED (embedding gate BLOCKED, owed)
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES (unchanged)
Track B:               BLOCKED
B1.1 frozen:           NO
Generation authorized: NO
```
Preserved prior: Track G `RANDOM_POLARITY_EXPLAINS` (`1fe5562`; A_vs_R −0.1917, A_vs_X −0.075) · Track F
`CORRECTNESS_DEGRADED`. **`R_deranged` remains the crux.**

**Structure, not validated meaning.** Draft review only; the B1 verdict stands and Track B remains BLOCKED.
