# B1.3 Concrete-Object Modulation — LLM-Judge Revision Spec

## 1. Scope and status

Revises the concrete-object judged-modulation plan to allow **LLM judges as the primary pilot/evidence
instrument** for **objective object-function fit** — whether a supplied modulation fits a concrete object's
stable function under a fixed dictionary anchor. Preparation/specification only — **no study run, no final
stimuli, no scoring, no EVIDENCE_FREEZE.** No positive label earned. **Structure, not validated meaning.**

This is **not** the earlier mixed/loaded-word LLM test (B1.1), which returned null. That test asked judges to
feel out fields on emotionally/socially/spiritually loaded words. The target here is **objective object-function
modulation** on stable concrete objects — a different, more defensible construct for a machine judge.

## 2. What changed from the concrete-object word-list spec

The concrete-object word-list refinement (`…CONCRETE_OBJECT_WORDLIST_SPEC`, decision
`CONCRETE_OBJECT_WORDLIST_SPEC_READY`) fixed the **input set** to stable concrete objects. This revision fixes
the **instrument**: the primary pilot/evidence judge for that set may now be an **LLM**, scoring
**object-function fit** rather than felt resonance. Word set, arms, and controls are otherwise unchanged.

## 3. New possible future label

```
LLM_OBJECT_MODULATION_SIGNAL
```

**Meaning:** LLM judges, under fixed dictionary anchors for concrete objects, prefer the **real** varṇa-derived
modulation over **deranged, scrambled, random, and neutral** controls for **object-function fit**.

**Reachable only** after: a declared EVIDENCE_FREEZE, an actual run, a passed style-tell audit, the primary
endpoint met on primary concrete objects, and no result driven by the diagnostic loaded words. It is a claim
about **LLM object-fit preference**, explicitly **not** human felt validation, **not** ontology validation,
**not** Sanskrit privilege, **not** semantic truth. It does **not** unblock Track B.

## 4. Why concrete objects make LLM judging more defensible

- **Stable denotation** — a concrete object's dictionary meaning is fixed and unambiguous, so the judge is not
  guessing what the word denotes before assessing modulation-fit.
- **Clear object-function** — objects have a graspable function (a door closes an entrance; a key opens a
  lock), giving an objective referent against which "fit" can be assessed.
- **Lower emotional projection** — objects carry far less affect than *grief*/*joy*, so preference is less
  contaminated by feeling-match.
- **Lower doctrinal leakage** — objects carry no doctrine, unlike *prayer*/*soul*, so preference is not
  convention recall.
- **Easier wrong-answer controls** — with a concrete function, a mismatched (deranged/random) modulation is
  more clearly *wrong*, making the controls sharper and a real preference easier to detect if it exists.

## 5. Remaining risks (why a positive is still not proof)

- **Ordinary object semantics.** The LLM may prefer A_real because its tags happen to align with ordinary
  learned object semantics, not because varṇa carries anything — the modulation could be re-derivable from the
  dictionary meaning alone. (Mitigation: the fixed anchor is identical across arms; tags may not restate
  denotation; a semantics-only baseline should be checked.)
- **Prose preference.** The LLM may prefer whichever option simply reads better. (Mitigation: hard style-tell
  audit gate; shared surface-register normalization; equal length/tag-count.)
- **Scrambled may still equal real.** The prior automated finding was scrambled≈real (cosine 0.967); order may
  again carry nothing, and R_scrambled≈A_real would be a null.
- **LLM object-fit evidence only.** Even a clean positive is **LLM object-fit evidence**, not human felt
  validation — `LLM_OBJECT_MODULATION_SIGNAL` is the ceiling this instrument can reach; the human study and
  `HUMAN_PROPENSITY_MODULATION_SIGNAL` remain separate and unearned.

## 6. Required arms (unchanged)

`A_real` · `R_deranged` · `R_scrambled` · `R_random` · `X_neutral` (optional near arms retained). Construction,
seeding, and determinism per `b1_3_human_modulation_arm_construction_spec.json`; only the judge and the scored
construct change.

## 7. Primary endpoint

**A_real win-rate vs R_deranged** (forced choice) on the **primary concrete objects**. This is the
word-specificity crux (B1.1/B1.2 found real≈deranged).

## 8. Required success (all must hold)

1. **A_real beats R_deranged, R_scrambled, R_random, and X_neutral** on primary concrete objects.
2. **Style-tell audit passes** (real arm not identifiable by surface style; else STOP before judging).
3. **No result driven by the diagnostic loaded words** (kinship/religious/affect/social-register are diagnostic
   only; primary endpoint computed on concrete objects, with a drop-diagnostic sensitivity check).
4. **No ontology or Sanskrit-truth claim** attached to any outcome.

Failure of any → not `LLM_OBJECT_MODULATION_SIGNAL`.

## 9. Preserved prior results (unchanged)

- **B1.1** — LLM null on the earlier mixed/loaded design (RANDOM_OR_SCRAMBLED_MATCHES).
- **B1.2 / B1.3 automated** — nulls (real≈deranged; scrambled≈real, cosine 0.967; order-invariant).
- **B1.3 register-field** — CLOSED (category mismatch).
- **B1.4 vṛtti ground-truth** — CLOSED (ground truth absent / not empirically adjudicable).
- **Track B** — BLOCKED.
- **Track G / Track F** — RANDOM_POLARITY_EXPLAINS (1fe5562) / CORRECTNESS_DEGRADED.
- No positive label earned yet.

## 10. Honest prior

Automated probes found real≈fake **objects** (scrambled≈real 0.967; deranged≈real). The LLM judge is asked to
choose between near-identical stimuli; the prior is **low**. Concrete objects sharpen the controls but do not
by themselves predict a positive. Pre-register so a null is believable and a positive is not a prose or
ordinary-semantics artifact.

## 11. Decision

```
DECISION: LLM_OBJECT_MODULATION_PROTOCOL_READY
```

Allowing LLM judges for **objective object-function fit** on stable concrete objects is a defensible pilot
instrument: the construct (function-fit under fixed denotation) is one machines assess more reliably than felt
resonance, the controls are sharper, and the ceiling label (`LLM_OBJECT_MODULATION_SIGNAL`) is honestly bounded
to LLM object-fit — not human validation, ontology, or truth. This is not
`LLM_OBJECT_MODULATION_HIGH_RISK_NEEDS_REVISION` (the confounds are named and controllable, not amplified) and
not `LLM_OBJECT_MODULATION_REJECTED_HUMANS_REQUIRED` (LLM judging of objective object-function is a legitimate
pilot; humans remain required only for felt validation, which is a separate, still-open thread). Next: the
style-audit + scoring/thresholds protocol and remaining freeze blockers.

```
document:                    B1.3 concrete-object modulation — LLM-JUDGE revision (preparation only)
decision:                    LLM_OBJECT_MODULATION_PROTOCOL_READY
instrument:                  LLM judges (primary pilot/evidence) for OBJECTIVE object-function fit
target set:                  primary concrete objects (from CONCRETE_OBJECT_WORDLIST_SPEC)
new future label:            LLM_OBJECT_MODULATION_SIGNAL (LLM object-fit only; not human/ontology/truth)
arms:                        UNCHANGED — A_real / R_deranged / R_scrambled / R_random / X_neutral (+ optional near)
primary endpoint:            A_real win-rate vs R_deranged on primary concrete objects
required success:            A_real beats R_deranged + R_scrambled + R_random + X_neutral; style audit passes;
                             not driven by diagnostic loaded words; no ontology/Sanskrit-truth claim
final stimuli generated:     NO
ran LLM judges / humans / scoring: NO
EVIDENCE_FREEZE:             NOT declared
prior nulls:                 PRESERVED (B1.1 LLM null; B1.2/B1.3 automated; scrambled≈real 0.967; Track G; Track F)
B1.3 register-field:         CLOSED    | B1.4 vṛtti ground-truth: CLOSED
HUMAN_PROPENSITY_MODULATION_SIGNAL: NOT earned (separate, still-open)
LLM_OBJECT_MODULATION_SIGNAL / PROPENSITY_MODULATION_SIGNAL / LLM_PROPENSITY_FIELD_DISCRIMINATION: NOT earned
MAPPING_FIDELITY_SIGNAL / LIMITED_GENERATION_UTILITY / VRITTI_PROPENSITY_SIGNAL: NOT earned
Track B:                     BLOCKED
ontology / Sanskrit / truth: NONE
next:                        style-audit protocol + scoring/thresholds spec; then remaining freeze blockers
```

**Structure, not validated meaning.** LLM judges are allowed as the primary pilot instrument for objective
concrete-object function-fit, with a new honestly-bounded ceiling label `LLM_OBJECT_MODULATION_SIGNAL`; no
stimuli were generated, nothing was run or scored, prior nulls and closures stand, Track B remains BLOCKED, and
EVIDENCE_FREEZE is not declared.
