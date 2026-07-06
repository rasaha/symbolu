# B1.2 Mapping-Fidelity Prereg Decision (go/no-go memo — decision only)

## 1. Decision scope

This memo decides **one thing**: whether a B1.2 mapping-fidelity study is worth **preregistering**, or
whether the varṇa generation/mapping-utility line should be **closed for now**. It does **not** authorize
implementation, run models, or score anything. It does **not** change, reinterpret, or rescue B1.1, and it
does **not** claim `LIMITED_GENERATION_UTILITY`, ontology validation, Sanskrit privilege, or semantic truth.
It unifies three committed inputs — `B1_1_POST_RESULT_FORENSIC_REPORT.md`,
`B1_2_R_DERANGED_CONTROL_VALIDITY_REVIEW.md`, `B1_1_THEORY_APPLICATION_MISMATCH_REVIEW.md` — plus the locked
`B1_1_FINAL_SCORING_AND_VERDICT.md`.

**Locked facts (unchanged by this memo):** B1.1 = `RANDOM_OR_SCRAMBLED_MATCHES`; `LIMITED_GENERATION_UTILITY`
not earned; Track B **BLOCKED**; Track G `RANDOM_POLARITY_EXPLAINS` and Track F `CORRECTNESS_DEGRADED`
preserved. **Structure, not validated meaning.**

## 2. Evidence against continuing

- **Two independent nulls.** B1 and B1.1 both returned `RANDOM_OR_SCRAMBLED_MATCHES`. B1.1 was the corrected,
  contrastive, blinded redesign built specifically to give the hypothesis its best fair shot — and it still
  failed.
- **A failed *every* strong symbolic control.** A_vs_R_deranged 0.516 (non-robust near tie), A_vs_R_domain
  0.460 (loses), A_vs_R_same 0.471 (ties/loses); A even tied scrambled S (0.497). The failure is broad, not
  a single borderline miss.
- **Two further standing negatives.** Track G (`RANDOM_POLARITY_EXPLAINS`) and Track F
  (`CORRECTNESS_DEGRADED`) both point the same direction.
- **The generation-utility line is weak-to-exhausted.** The forensic report's deep limiting factors — English
  G2P→varṇa is lossy, any fluent coherent bridge conditions open generation about equally — suggest the
  effect A shows is generic resonance, and may indicate the generative hypothesis is false or mis-scoped.
- **Another *generation* study is not recommended** by any of the three inputs. "B1.1 with nicer prose" would
  only re-measure generic resonance.

## 3. Evidence for one final, different test

- **The intended theory was never tested layer-by-layer.** The theory-application review shows B1.1 tested an
  end-to-end *generation* pipeline, not the three layers in isolation — it did not isolate **Layer 2**
  (dictionary grounding) or **Layer 3** (differential synonym-separation). *Untested ≠ vindicated*, but it
  does mean the specific Layer-3 claim has not actually been put to a fair test.
- **Flat R_deranged had poor resolution.** The control-validity review shows the flat deranged arm blended
  near/mid/far wrongness; it could not reveal whether A fails specifically at the near-synonym boundary — the
  one place Layer 3 is supposed to do work.
- **A discriminative test is materially different from generation scoring.** Forced-choice / ranking /
  odd-one-out tasks make a *wrong* mapping **score wrong**, rather than merely read differently. This changes
  what is measured (recoverable word-specific signature) and what the judges reward (fit, not fluency).

So there is a genuine, narrow, previously-untested question — **mapping fidelity** — that a single sharply
different study could answer with a clean signal or a clean kill.

## 4. Decision alternatives

**Option A — Stop now.**
Close the varṇa generation/mapping-utility line. Treat B1 + B1.1 + Track G + Track F as sufficient evidence.
*Pros:* avoids overfitting-after-failure; honest and defensible; zero further cost. *Cons:* leaves the
Layer-3 mapping-fidelity question formally untested (though the burden was never met).

**Option B — One B1.2 mapping-fidelity prereg.**
A single, sharply different, **discriminative** (not generative) study that isolates Layer 2 and Layer 3,
uses **stratified R_deranged_near/mid/far**, and **retains R_same and R_domain**. New prereg + new freeze;
B1.1 not reusable as a positive prior. *Pros:* actually tests the intended Layer-3 claim; bounded to one
shot; strong controls make a positive hard to fake. *Cons:* real risk of motivated design after a failure —
mitigated only by strict pre-freezing of the answer key and tiers.

**Option C — Domain shift to Sanskrit/IAST.**
Test words given directly in IAST so the varṇa sequence is **exact**, removing the lossy-G2P confound.
*Important:* this is a **new and different question**, **not** a fix to B1.1 and **not** a Sanskrit-privilege
claim. *Cons:* not directly comparable to the English B1/B1.1 line; introduces Sanskrit-leakage risk; a scope
change, not a falsifier of the existing hypothesis.

## 5. Recommended decision

- **Do not run another generation study** (rules out any "B1.1 redo").
- **Recommend Option B — authorize exactly one B1.2 mapping-fidelity prereg — conditionally.** It is the only
  option that fairly tests the specific, previously-unisolated Layer-3 claim, and it is bounded to a single
  shot. **However**, it may proceed **only** if it meets *all* §6 conditions; if any condition cannot be met
  (e.g. the Layer-3 answer key or distance tiers cannot be frozen before judging without hand-tuning), the
  decision **defaults to Option A — Stop now.** Option A remains fully defensible on its own and is the
  fallback, not a lesser choice.
- **If B1.2 is authorized, it is the FINAL varṇa-mapping falsifier in this line.** Unless it produces a
  **clean, preregistered `MAPPING_FIDELITY_SIGNAL`**, the line closes. No third generation-side attempt.
- Option C (Sanskrit/IAST) is **not** recommended now; if ever pursued it must be scoped as its own separate
  question, not as part of this decision.

## 6. Conditions for authorizing B1.2

B1.2 may proceed **only if every one** of these holds:

- **new prereg** and **new freeze** (own manifest, own seeds, own hashes);
- **no reuse of B1.1** as a positive prior;
- **explicit three-layer architecture** (Layer 1 skeleton, Layer 2 grounding, Layer 3 differentiation);
- **Layer 2 dictionary field frozen before judging** (the word's conventional semantic field, checkable);
- **Layer 3 differential signature frozen before judging** (the correct answer key, authored and hashed
  *before* any output is seen);
- **near/mid/far deranged tiers frozen before judging** (assigned by a documented embedding/WordNet/blind
  procedure, seeded, hashed — no post-hoc reassignment);
- **R_same and R_domain retained** (B1.1 also failed these; they must still be beaten);
- **generic symbolic (non-varṇa) control retained** (bounds the generic-resonance baseline A must exceed);
- **no post-hoc lexicon tuning** (A uses the frozen composition; no re-authoring after seeing examples);
- **no weak/nonsense controls** (all distractors fluent, real, length/register/pole-matched; "far" = distant
  *source word*, not degraded text);
- **real-G2P leakage pre-scan** (no varṇa/Sanskrit labels or mapping metadata in any presented bridge);
- **no ontology / Sanskrit-privilege / semantic-truth claim** at any outcome.

## 7. B1.2 minimum viable design

Each item carries:

- **target word**;
- **dictionary semantic field** (Layer 2, frozen);
- **near-neighbor confusion set** (the synonyms/category-neighbors Layer 3 must separate against);
- **correct Layer-3 differential signature** (frozen answer key);
- **R_deranged_near** · **R_deranged_mid** · **R_deranged_far** (stratified wrong bridges);
- **R_same** (same-pool random real phrases);
- **R_domain** (mismatched-domain real bridge);
- **generic symbolic control** (high-quality non-varṇa resonant prose).

**Discriminative judge task:** *"Which bridge/signature best fits this word and distinguishes it from its
near synonyms?"* — forced-choice / ranking / odd-one-out, blinded, no varṇa labels. A wrong mapping must be
**scorable as wrong**.

## 8. B1.2 success criteria

Support requires **all**:

- A beats **R_deranged_far** (corrected CI lower bound > chance);
- A beats **R_deranged_mid** (corrected CI lower bound > chance);
- A **does not lose** to **R_deranged_near**;
- a **monotonic distance gradient**: margin_far > margin_mid > margin_near;
- A **also beats R_same and R_domain**;
- the result **survives** multiplicity correction and the pre-specified robustness/sensitivity checks
  (drop-judge, drop-parse-fail, drop-repaired).

**Only allowed positive label:** `MAPPING_FIDELITY_SIGNAL` (with distance-gradient qualifier). **Never**
`LIMITED_GENERATION_UTILITY`, ontology validation, Sanskrit privilege, semantic truth, or Track-B unblock.

## 9. B1.2 kill criteria

- **A fails far** → no recoverable word-specific signal (strongest kill).
- **near ≈ mid ≈ far (flat)** → generic symbolic resonance explains the effect; Layer 3 adds nothing.
- **R_same or R_domain matches/beats A** → mapping fidelity unsupported regardless of the deranged gradient.
- **Success only on handpicked examples** / not surviving robustness → not robust, not support.
- **Layer 3 answer key hand-authored post-hoc** → overfit and invalid.

Any kill closes the varṇa-mapping line (subject to §5); no rescue language, no control weakening, no goalpost
move to the weak controls.

## 10. Final recommendation block

```
DECISION: AUTHORIZE_ONE_B1_2_PREREG  (conditional on all §6 conditions; else defaults to STOP_NOW)
scope:    exactly one discriminative mapping-fidelity study — the FINAL varṇa-mapping falsifier in this line
fallback: STOP_NOW (fully defensible; the default if §6 cannot be met without hand-tuning)
excluded: any further generation-utility study; Sanskrit/IAST domain shift (separate question, not now)
```

**This is not a rescue of B1.1.** It is one final, different, discriminative falsifier of the corrected
three-layer theory. It cannot revive B1.1's null, cannot earn `LIMITED_GENERATION_UTILITY`, and cannot
unblock Track B. Its best possible outcome is a narrow `MAPPING_FIDELITY_SIGNAL` (discriminability within the
frozen system); its likely outcomes, given four standing negatives, include a clean final kill — which is an
acceptable and honest result.

## 11. Final status block

```
document:                   B1.2 mapping-fidelity prereg DECISION memo (decision only; nothing run)
decision:                   AUTHORIZE_ONE_B1_2_PREREG (conditional) — final falsifier; else STOP_NOW
B1.1 verdict:               UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
LIMITED_GENERATION_UTILITY: NOT earned
only allowed B1.2 positive: MAPPING_FIDELITY_SIGNAL
Track B:                    BLOCKED
Track G negative:           RANDOM_POLARITY_EXPLAINS (1fe5562; A_vs_R -0.1917, A_vs_X -0.075) — preserved
Track F negative:           CORRECTNESS_DEGRADED — preserved
ontology validation:        NONE
Sanskrit privilege:         NONE
semantic-truth claim:       NONE
requires:                   new prereg + new freeze (B1.1 not reusable as a positive prior)
```

**Structure, not validated meaning.** A single, different, discriminative falsifier may be preregistered
under strict conditions; the B1.1 verdict stands, no result is rescued, Track B remains BLOCKED, and the
prior negatives (Track G, Track F) are preserved.
