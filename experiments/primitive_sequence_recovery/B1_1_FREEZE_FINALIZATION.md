# B1.1 Freeze Finalization

## 1. Scope and non-claims

Finalizes the B1.1 **artifact-set** freeze from the verified draft manifest. **This freezes the artifact set
only; it does NOT authorize generation.** No model / embedding / generation / scoring / judging. Does **not**
modify B1, change the verdict (`RANDOM_OR_SCRAMBLED_MATCHES`), or unblock Track B (**BLOCKED**). No ontology
validation, Sanskrit privilege, or semantic-truth claim. **Structure, not validated meaning.**

## 2. Freeze decision

**`FREEZE_FINALIZED_UNDER_FALLBACK_QUALIFICATION`.** All freeze artifacts exist, validate, and hash-verify;
the pre-freeze adversarial audit passed; the Meta-Llama-3-8B warning is decided (`ACCEPT_WITH_CAVEAT`); the
embedding-gate limitation is recorded as `FALLBACK_QUALIFIED`. The B1.1 artifact set is now frozen.

## 3. Final manifest status

- File: `b1_1_freeze_manifest.json` — **`manifest_status: FROZEN`**, **`freeze_status:
  FROZEN_NOT_AUTHORIZED_FOR_GENERATION`**, `generation_authorized: false`.
- Manifest verifier: **`MANIFEST_VERIFIED`**.
- Finalization: `finalized_from_draft_manifest_sha256` `d3afbeed…`, `finalized_commit_base` `d92dc2e`,
  `finalized_at` (UTC recorded), `generation_authorization_required_next: B1_1_GENERATION_AUTHORIZATION`.

## 4. Artifact hash summary

**12 artifacts bound** with sha256, all recomputed against current files at finalization → **all 12
matched** the verified draft (no unexpected change). Bound set: lexicon, bridge pool, six configs
(arm-construction, generation, seeds, judge-panel, scorer, leak/packet), prereg, bridge/prereg decision,
prereg/freeze decision, freeze-artifact validation report.

## 5. Fallback qualification

**`FALLBACK_QUALIFIED`.** The real sentence-embedding non-synonym gate was **not** run; the freeze proceeds
on the local lexical-audit fallback (surface-only). If embedding access is restored, the real gate should be
run and would supersede this qualification in any future re-freeze.

## 6. Embedding-gate status

**`BLOCKED_DEPENDENCY_UNAVAILABLE`** (HuggingFace model-host egress denial) — **still owed**. Preserved in
the manifest.

## 7. Meta-Llama-3 caveat

**`ACCEPT_WITH_CAVEAT`.** Meta-Llama-3-8B is retained with the explicit caveat that it needed heavy
missing-final-brace repair in B1; parser/QC rules remain strict (narrow missing-final-brace repair only),
judge outputs must be audited, and **no post-hoc judge selection**.

## 8. Pre-freeze audit result

**`PASS_PREFREEZE_AUDIT`** (`d92dc2e`): 0 blockers; leakage clean (0 Sanskrit/varṇa/IAST/meta/arm-label in
model-facing text); forbidden-framing clean; controls not weak; freeze-status clean; prereg consistent; dry
run `PASS_RENDER_DRY_RUN`. (An initial detector false positive on negated claim language was fixed in the
audit tool; no artifact was changed.)

## 9. What this freeze does and does not authorize

- **Does:** freeze the B1.1 artifact set and bind its hashes (`INVALID_POSTHOC` on any post-freeze edit).
- **Does NOT:** authorize generation, judging, or scoring.
- **A separate explicit `B1_1_GENERATION_AUTHORIZATION` gate is required.**
- **The first generation run must use the frozen manifest only.**
- **Any artifact edit after freeze invalidates this freeze and requires a new freeze manifest.**

## 10. Remaining risks

- Embedding gate blocked → deep paraphrase-synonymy risk undetected (fallback is surface-only).
- **`R_deranged` remains the crux** — a contrastive, clean pipeline cannot make A beat R if word-specific
  fit carries no signal.
- R_same / R_domain may still match A.
- Meta-Llama-3-8B parser-repair caveat (accepted, audited).
- **Positive result is limited to `LIMITED_GENERATION_UTILITY`** (in-architecture, this frozen design).
- A failure cannot be rescued into an ontology claim and cannot unblock Track B.

## 11. Next gate

**`B1_1_GENERATION_AUTHORIZATION`** — a separate, explicit gate. Generation is **not** authorized by this
freeze.

## 12. Final status block

```
manifest_status:       FROZEN
freeze_status:         FROZEN_NOT_AUTHORIZED_FOR_GENERATION
manifest_verifier:     MANIFEST_VERIFIED (12 artifacts)
finalization_decision: FREEZE_FINALIZED_UNDER_FALLBACK_QUALIFICATION
embedding_gate:        BLOCKED_DEPENDENCY_UNAVAILABLE (owed)
judge decision:        Meta-Llama-3-8B ACCEPT_WITH_CAVEAT
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES (unchanged)
Track B:               BLOCKED
B1.1 frozen:           YES (artifact set)
Generation authorized: NO
```
Preserved prior: Track G `RANDOM_POLARITY_EXPLAINS` (`1fe5562`; A_vs_R −0.1917, A_vs_X −0.075) · Track F
`CORRECTNESS_DEGRADED`. **`R_deranged` remains the crux.**

**Structure, not validated meaning.** The artifact set is frozen; generation remains unauthorized and the
B1 verdict stands with Track B BLOCKED.
