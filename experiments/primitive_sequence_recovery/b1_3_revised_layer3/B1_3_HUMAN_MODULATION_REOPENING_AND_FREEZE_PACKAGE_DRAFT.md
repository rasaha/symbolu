# B1.3 Human Judged-Modulation — Reopening + Evidence-Freeze Package (DRAFT)

## 1. Scope of reopening

Reopens **only** the still-unrun **human judged-modulation** study. It does **not** reopen the full varṇa
empirical line and does **not** rescue B1.1, B1.2, the B1.3 automated/vector probes, Track G, Track F, or B1.4.
All prior nulls stand; B1.4 remains closed (ground-truth absent); the B1.3 register-field path remains closed
(category mismatch). No positive label is earned. Draft only — **no EVIDENCE_FREEZE, no run, no scoring.**
**Structure, not validated meaning.**

## 2. Corrected hypothesis

- **Dictionary meaning** fixes the object/denotation.
- **Varṇa/vṛtti does not define** the object; it supplies a **modulation/propensity-field** around the
  already-fixed meaning.
- **Human raters judge comparative fit** of the modulation — not definition, not truth.

## 3. Why this differs from B1.4

B1.4 needed an **external true vṛtti answer key** for each word — which does not exist non-circularly (→
closed). **Judged modulation needs no answer key:** the **human rater is the comparative arbiter** of which
modulation fits better. That sidesteps the ground-truth wall. It still does **not** prove ontology, Sanskrit
truth, or semantic truth — only whether humans prefer the real modulation over fakes.

## 4. Relationship to B1.1

B1.1 tested essentially this structure with **LLM judges** → null (`RANDOM_OR_SCRAMBLED_MATCHES`; real ≈
deranged/scrambled/random). The **human** version has **never** been run. This is **not a rescue of B1.1**;
it tests the distinct question: **do humans detect a modulation advantage that LLM judges did not?** (The
honest prior is against it — see §20 burden — but the instrument is genuinely untried.)

## 5. Stimulus structure

Each item: **target word** · **fixed dictionary anchor** · **short neutral context** · **Option A modulation**
· **Option B modulation**. Raters see **no arm labels**, no varṇa/Sanskrit markers.

## 6. Arms

**A_real · R_deranged · R_scrambled · R_random · X_neutral (no-varṇa).** Optional: R_semantic_near,
R_varṇa_near. Primary pairing = A_real vs R_deranged.

## 7. Human rater task (anchored)

> *"Given the dictionary meaning and context, which option better **modulates or brings out the inner
> tendency/field** of this word **without changing its meaning**?"*

**Forbidden framings:** "which is deeper," "more spiritual," "defines the word," "more poetic," "more
Sanskritic."

## 8. Word pool

Broad, diverse pool (reuse the confound-controlled measurement-spec pool: 60–100+ groups across domains).
**Kinship terms only as a labeled high-confound diagnostic subset**, never the primary evidence. **No
cherry-picking** after inspecting outputs; pool frozen before generation.

## 9. Generation protocol

Same template across arms; same **length band**; **no arm-specific hand-polishing**; **no visible
Symbol-U/varṇa markers**; all generation artifacts **hash-bound before judging**; seeds + prompts recorded;
frozen decoding.

## 10. Style / leakage controls

Mandatory **style-tell audit** on the stimuli before human rating; length/fluency matched; **no poetic
advantage** for A_real. **If raters (or an LLM classifier) can identify the real arm from style alone →
STOP.** (The B1.2 prose style-tell hit 0.70 — this gate is non-negotiable.)

## 11. Rater protocol

Blinded human raters; randomized item order; **position balancing** (each pair both orders); **sample size
fixed before run**; **naive** stratum + optional **spiritually-literate** stratum; **primary result must not
depend only on doctrine-trained raters** (a doctrine-only effect is scored as demand characteristics — kill).

## 12. Primary endpoint

**A_real win-rate vs R_deranged** (forced choice) is primary; A_real must **also** beat R_scrambled, R_random,
and X_neutral.

## 13. Success criteria

A_real beats **R_deranged AND R_scrambled AND R_random AND X_neutral** (win-rate > 0.5, corrected CI lower
bound above chance); survives multiplicity correction; **not driven by the kinship subset**; **not driven by
one rater group**; **style-tell passes**. **Only allowed future label: `HUMAN_PROPENSITY_MODULATION_SIGNAL`**
(after EVIDENCE_FREEZE).

## 14. Kill criteria

STOP / null if: A_real ≈ R_deranged; A_real ≈ R_scrambled; A_real ≈ R_random; A_real ≈ X_neutral; style-tell
fails; effect only in the doctrine-trained group; effect only in kinship/high-confound terms; A_real is
longer/richer/more poetic by construction.

## 15. Statistical plan

Pairwise forced-choice; **binomial** and/or **mixed-effects logistic** with **item and rater random effects**;
95% CIs; **Holm–Bonferroni** across arm comparisons; exclusion rules (attention checks, straight-lining) fixed
before run; per-stratum and drop-kinship sensitivity reported.

## 16. Evidence-freeze manifest draft

See `b1_3_human_modulation_freeze_manifest_draft.json` — `evidence_freeze_declared: false`, with hypothesis,
arms, allowed label, preserved priors, and per-component readiness status + missing blockers.

## 17. Missing blockers before an actual freeze

final word list · final generation template · final arm-construction artifacts · final rater sample size ·
final recruitment/ethics plan · final style audit · final scoring script · final thresholds · **manifest hash
binding**. None exists yet — this is a draft.

## 18. Decision

```
DECISION: HUMAN_MODULATION_FREEZE_PACKAGE_DRAFT_READY
```

The **draft** is coherent and ready for review: a valid, distinct, previously-unrun instrument (human judges)
for the corrected judged-modulation hypothesis, with strong controls (deranged crux, style-tell gate, naive +
literate strata, confound-controlled pool) and a weak, explicit label. It is **not** `HIGH_RISK_NEEDS_REVISION`
(the design is adequate as a draft — the risk is empirical, not design-flaw) and **not**
`REOPENING_REJECTED_CLOSE_LINE` (the human instrument is genuinely untried and legitimate). **"Draft ready" ≠
freeze-ready:** §17 blockers remain, and an EVIDENCE_FREEZE + a real, costly human study are separate explicit
steps.

## 19. Final status block

```
document:                    B1.3 human judged-modulation REOPENING + freeze-package DRAFT (draft only)
decision:                    HUMAN_MODULATION_FREEZE_PACKAGE_DRAFT_READY
scope:                       ONLY the unrun human judged-modulation study reopened
EVIDENCE_FREEZE:             NOT declared
ran humans / LLM judges / scoring: NO
only reachable positive:     HUMAN_PROPENSITY_MODULATION_SIGNAL (after EVIDENCE_FREEZE) — NOT earned
prior nulls:                 PRESERVED (B1.1 real≈fake; B1.2; B1.3 scrambled≈real; Track G; Track F)
B1.3 register-field:         CLOSED (category mismatch)
B1.4 vṛtti ground-truth:     CLOSED (not empirically adjudicable)
B1.1 verdict:                UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
PROPENSITY_MODULATION_SIGNAL / LLM_PROPENSITY_FIELD_DISCRIMINATION: NOT earned
LIMITED_GENERATION_UTILITY / MAPPING_FIDELITY_SIGNAL: NOT earned
Track B:                     BLOCKED
Track G / Track F:           RANDOM_POLARITY_EXPLAINS (1fe5562) / CORRECTNESS_DEGRADED — preserved
ontology / Sanskrit / truth: NONE
next:                        operator review → (optional) resolve §17 blockers → EVIDENCE_FREEZE + human study
```

## 20. Honest burden (read before investing)

The automated probes found the **real and fake fields to be near-identical objects** (`scrambled ≈ real`
cosine 0.967; `deranged ≈ real`). So the two stimuli a human is asked to choose between may be **nearly the
same text** — making a reliable human preference a **low-prior** outcome. The bet is narrow: *humans perceive a
felt modulation that LLMs and vectors could not.* Possible, and worth a pre-registered test if you want to
settle it — but pre-register so a null is believable, and expect a null given everything upstream. Even a clean
positive is `HUMAN_PROPENSITY_MODULATION_SIGNAL` scale — human sensitivity above controls — **not** validation
of the varṇa ontology.

**Structure, not validated meaning.** Only the unrun human judged-modulation path is reopened as a draft; all
prior nulls and closures stand, nothing is run or claimed as evidence, Track B remains BLOCKED, and an
EVIDENCE_FREEZE plus a controlled human study remain separate, explicit, not-yet-authorized steps.
