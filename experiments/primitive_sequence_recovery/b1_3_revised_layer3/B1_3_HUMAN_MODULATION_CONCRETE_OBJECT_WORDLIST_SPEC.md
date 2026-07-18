# B1.3 Human Modulation — Concrete-Object Word List Refinement Spec

## 1. Scope and status

Revises the primary analyzable word set for the reopened human judged-modulation study so it uses **stable
concrete objects** rather than emotionally / socially / spiritually / religiously loaded words. Preparation and
specification only — **no final stimuli generated, no judging, no scoring, no EVIDENCE_FREEZE.** Prior results
unchanged; B1.3 register-field and B1.4 vṛtti paths remain closed; no positive label earned.
**Structure, not validated meaning.**

## 2. Why revise — the loaded-word problem

Loaded words (kinship, religious, affect, social-register) carry strong prior associations. Asked to judge a
"field/modulation" around *mother*, *prayer*, or *grief*, a rater draws on **memory, doctrine, feeling, and
politeness convention** — not on how well a supplied modulation *fits a fixed meaning*. A "hit" on such words
would rediscover Jakobson babbling universals, register, doctrine, or emotion-word convention, **not** varṇa
modulation. This is the same confound that closed the kinship/register field-table path (register dims
undefensible; scrambled≈real 0.967). Concrete objects strip that pull: their denotation is stable and
low-association, so the rater's judgment is forced onto **modulation-fit**, which is exactly the construct under
test.

## 3. The three-tier design

- **PRIMARY — stable concrete objects.** The only set used for the primary analyzable endpoint.
- **SECONDARY — supporting stratum.** Neutral physical action verbs + low-religion structural abstracts +
  stable low-drama body/nature. Reported as support, never as the primary endpoint.
- **DIAGNOSTIC — confound quarantine.** Kinship / religious / affect / social-register. **Never** primary;
  reported separately, and a "hit" here is read as a confound signal, not evidence.

## 4. Candidate word list

`b1_3_human_modulation_concrete_object_candidate_wordlist.json` — **92 candidates, all 92 eligible**
(each routes through cmudict G2P → varṇa and has a WordNet synset). Tiers: **primary 53, secondary 22,
diagnostic 17.** Each item carries word · category · dictionary_anchor · neutral_context ·
tier / primary_or_secondary_or_diagnostic · high_confound · confound_notes · inclusion_status ·
exclusion_reason. **Final frozen list + full eligibility screen remains a downstream blocker.**

## 5. Primary set — stable concrete objects (53)

Seven object families, none carrying strong affect/doctrine/register:

- **furniture** (5): chair, table, bed, bench, shelf
- **containers** (8): cup, bowl, box, bottle, basket, jar, bucket, pot
- **barriers / openings** (6): door, wall, gate, window, fence, roof
- **tools** (10): knife, hammer, key, rope, needle, nail, wheel, ladder, lamp, spoon
- **natural objects** (8): stone, tree, leaf, branch, rock, sand, seed, shell
- **household objects** (8): mirror, book, clock, candle, blanket, plate, broom, basketball
- **structures** (8): bridge, tower, house, road, well, pillar, staircase, boat

These are the seed families named in the request; the exact frozen subset (and any per-item drops for
comparable-control reasons) is a downstream screen, not fixed here.

## 6. Secondary set — supporting stratum (22)

- **action verbs** (9): carry, gather, break, bind, open, close, build, cut, pour
- **low-religion abstract** (7): order, measure, number, distance, weight, shape, balance
- **stable body/nature** (6): hand, bone, skin, river, mountain, cloud

Physical, structural, low-drama. Reported as a secondary stratum; **not** the primary endpoint.

## 7. Diagnostic set — confound quarantine (17)

- **kinship** (5): mother, mama, father, papa, dad — babbling universal + reduplication + register
- **religious** (5): prayer, temple, soul, devotion, surrender — doctrinal loading → convention judgment
- **affect** (4): fear, joy, grief, anger — emotional loading → feeling-match judgment
- **social-register** (3): friend, stranger, guest — register/politeness confound

**Never primary.** A hit here rediscovers convention, not varṇa modulation.

## 8. Dictionary anchor policy

Each anchor is short, neutral, object-first (e.g. *"chair = an object designed for one person to sit on"*),
contains **no** Symbol-U / varṇa / vṛtti language, is **identical across all arms**, and **fixes denotation**.
No arm may alter it.

## 9. Neutral context policy

One plain context sentence per item (object-framed for the primary tier: *"Consider the ordinary object
'chair' in a plain, everyday sentence."*). It does **not** force a modulation answer, is not emotionally loaded,
and is **identical across all arms**.

## 10. Constrained field-tag generation template

The loaded-word study's free 4-slot prose template is tightened to a constrained field-tag form for objects:

> *"Within the fixed meaning, this object is modulated by [tag1], [tag2], [tag3], and [tag4]."*

Four field tags, same syntax for every arm, no poetic flourish, **no new denotation**, no varṇa/Sanskrit/pole
markers, no arm-identifying vocabulary. A **style-tell audit hook** runs on rendered options before any human
rating.

## 11. Rater wording

> *"Given the dictionary meaning of the object, which option gives a more fitting inner tendency or field around
> this object without changing what it is?"*

This pins the rater to **modulation-fit under fixed meaning** — the construct — and deliberately avoids
"deeper", "more spiritual", "which do you connect with", or any wording that invites memory/feeling.

## 12. Arms retained (unchanged)

Arms are **unchanged** from the arm-construction spec: **A_real · R_deranged · R_scrambled · R_random ·
X_neutral** (+ optional R_semantic_near, R_varṇa_near). Primary pairing **A_real vs R_deranged** (word-
specificity crux; B1.1 found this null); A_real must also beat R_scrambled (order; prior automated
scrambled≈real 0.967), R_random (generic prose), X_neutral (does modulation add anything). Only the **word
set** and the **template/rater wording** change in this revision, not the control logic.

## 13. Style-control and blinding (unchanged)

Equal length bands; exactly 4 field tags per arm; same syntax; no arm-specific richer adjectives; no manual
editing after arm identity is known; shared surface-register normalization; arm labels hidden; position
randomized; pairwise comparisons balanced; private truth-map stored separately. The style-tell audit is a
**hard gate**: if the real arm is identifiable by surface style above threshold, **STOP** before human rating.

## 14. Candidate exclusions

Exclude a word if: no stable dictionary anchor; culture-specific or ambiguous denotation; obvious
register/babble/doctrine/affect confound (→ diagnostic tier, never primary); no comparable control can be
built; or modulation would change denotation. Applied here: all 92 candidates route (no G2P/varṇa/WordNet
exclusions); loaded words are **quarantined to the diagnostic tier**, not deleted, so the confound can be
measured rather than hidden.

## 15. What did NOT change

Prior nulls and closures stand verbatim (B1.1 real≈fake; B1.2 real≈deranged; B1.3 automated scrambled≈real
0.967; B1.3 register-field CLOSED; B1.4 vṛtti CLOSED; Track G RANDOM_POLARITY_EXPLAINS; Track F
CORRECTNESS_DEGRADED). The hypothesis, instrument (blinded humans), arms, primary endpoint, honest low prior,
freeze policy, and disallowed labels are unchanged. This revision is a **confound-reduction on the input word
set**, not a new claim and not a rescue of any null.

## 16. Freeze-readiness

Ready-as-draft: primary set is now stable concrete objects ✔; secondary/diagnostic tiers flagged ✔; template
and rater wording tightened for objects ✔; arms/controls unchanged ✔; **no final evidence stimuli generated**
✔. **Not** freeze-ready — downstream blockers remain: final frozen list (screened), rater sample size,
recruitment/ethics, style-tell audit protocol + result, scoring script, decision thresholds, manifest hash
binding.

## 17. Decision

```
DECISION: CONCRETE_OBJECT_WORDLIST_SPEC_READY
```

The primary analyzable set is refined to stable concrete objects (53 across seven object families), the loaded
categories are quarantined to a diagnostic tier (17) that can never count as primary evidence, a secondary
supporting stratum (22) is retained, and the template + rater wording are tightened to force modulation-fit
judgment on objects. Controls and arms are unchanged. This is not `HIGH_RISK_NEEDS_REVISION` (the confound is
now controlled, not amplified) and not `STRATEGY_REJECTED` (concrete objects are a legitimate, more
confound-resistant substrate for the same test). Next: style-audit + scoring protocols and the remaining freeze
blockers.

```
document:                    B1.3 human-modulation CONCRETE-OBJECT word-list refinement (preparation only)
decision:                    CONCRETE_OBJECT_WORDLIST_SPEC_READY
candidates:                  92 (all eligible) — primary 53 concrete objects / secondary 22 / diagnostic 17
primary set:                 stable concrete objects (furniture, containers, barriers/openings, tools,
                             natural objects, household objects, structures)
diagnostic (never primary):  kinship / religious / affect / social-register
template:                    constrained 4-field-tag object form; rater wording = modulation-fit under fixed meaning
arms:                        UNCHANGED — A_real / R_deranged / R_scrambled / R_random / X_neutral (+ optional near)
final stimuli generated:     NO
ran humans / LLM judges / scoring: NO
EVIDENCE_FREEZE:             NOT declared
prior nulls:                 PRESERVED (B1.1 real≈fake; B1.2; scrambled≈real 0.967; Track G; Track F)
B1.3 register-field:         CLOSED    | B1.4 vṛtti ground-truth: CLOSED
human judged-modulation:     NOT yet run
HUMAN_PROPENSITY_MODULATION_SIGNAL / PROPENSITY_MODULATION_SIGNAL / LLM_PROPENSITY_FIELD_DISCRIMINATION: NOT earned
LIMITED_GENERATION_UTILITY / MAPPING_FIDELITY_SIGNAL: NOT earned
Track B:                     BLOCKED
Track G / Track F:           RANDOM_POLARITY_EXPLAINS (1fe5562) / CORRECTNESS_DEGRADED — preserved
ontology / Sanskrit / truth: NONE
next:                        style-audit protocol + scoring/thresholds spec; then remaining freeze blockers
```

**Structure, not validated meaning.** The primary analyzable word set is refined to stable concrete objects to
force modulation-fit judgment and strip the loaded-word confound; loaded categories are quarantined as
diagnostic-only; no stimuli were generated, nothing was run or scored, prior nulls and closures stand, Track B
remains BLOCKED, and EVIDENCE_FREEZE is not declared.
