# B1 — Sanskrit Symbolic-Profile Preregistration (docs/data-only, Stage-F gated)

**Readiness: `PREREG_BLOCKED_BY_UNDEFINED_PACKET_PROJECTION`.** Docs/data-only. No study, no judges, no raters, no
model calls. Does **not** modify the parser, varṇa mappings, merged lexicon, prior packets, or prior results, and does
**not** reinterpret or rescue any prior null. Frozen artifacts + hashes: `symbolic_profile_prereg/freeze_index.json`.
Structure, not validated meaning.

## 1. Relationship to prior studies (all preserved, none rescued)

This study is **separate** from, and preserves the results of: B1.10 pole/source-condition testing (−2.78); the
consonant-backbone six-way word-identification study (**NULL** — `NO_WORD_SPECIFIC_SIGNAL`); the leading-vowel
inversion idea; unrestricted AND-composition; and the latent-state / decoder (`D`) proposals. The new claim is **not**
that the packet reconstructs a dictionary meaning. It is:

> For eligible monomorphemic, etymologically opaque Sanskrit words, the frozen **true** varṇa packet predicts an
> **independently measured, closed-inventory symbolic attribute profile** for that lexical item **better than**
> matched false, swapped, randomized, and morphology-based controls.

The decisive quantity is **relative** fit, never absolute fit.

## 2. Two-stage gated structure

- **Stage F (feasibility)** — define and certify viability *before* any profile collection or scoring: closed
  attribute inventory; word-eligibility rule; independent sources; minimum sample; profile-collection procedure;
  packet→attribute projection; AND operator; morphology baseline; control construction. **Proceed to Stage C only if
  every gate passes.**
- **Stage C (confirmatory)** — runs only after Stage F is frozen and passed. **No result-dependent change** to
  attributes, words, mappings, scoring, or controls after Stage F.

**This document reports Stage F. It does not pass (see §20 and the feasibility report).**

## 3. Primary hypothesis

`Δ = Fit(true packet, true profile) − max Fit(control packet/profile). ` Success requires `Δ > 0` against **all**
controls with a CI excluding zero, held-out replication, and the profile-swap collapse. Absolute fit is not evidence.

## 4. Strong null

Any apparent correspondence is explained by generic attributes, valence, packet length, phoneme frequency,
**morphology**, profile construction, **lexical overlap**, or flexible narrative interpretation. The true packet must
beat every relevant control (§13).

## 5. Word eligibility

Primary words must be native Devanāgarī forms; deterministically parsed by the frozen parser; **monomorphemic /
simplex**; **etymologically opaque / rūḍha** (not transparently compositional); backed by **≥2 independent
lexicographic sources**; using only confirmatory consonant mappings with no contradiction; and selected **without
inspecting packet↔profile fit**. Excluded: transparent compounds; root+affix (yaugika) derivations whose profile is
morphology-predictable; packet-convincing picks; words with unmeasurable profiles or unresolved identity. A 7-step
**decision tree** (simplex vs derived; opaque vs transparent; conventionalized vs compositional; uncertain→exclude)
adjudicates each word with ≥2 sources; every decision is auditable. Spec: `word_eligibility_spec.json`.

## 6. Minimum sample (fixed before search)

Development **≥40**; confirmatory **60–100** preferred; balanced across semantic/grammatical categories with variation
in length, consonant count, vowel pattern, and profile. Shortfall → `PREREG_BLOCKED_BY_INSUFFICIENT_OPAQUE_LEXEMES`.
**Never weaken eligibility to grow N.**

## 7. Closed symbolic attribute inventory

Fixed, externally-defined, closed inventory — **no free-text profiles**, no packet-specific attributes, no target-word
names, no open "other", clear anchors. Grounded in **Osgood EPA**, **Binder et al. 2016**, **Brysbaert 2014**,
**McRae 2005**, **Warriner 2013** (15 dimensions: animacy, living, concreteness, size, weight, mobility, agency,
boundedness, naturalness, ecological domain, ontological type, valence, potency, activity, harm). Each dimension
records its external source and a general (non-tailored) justification. Spec: `closed_attribute_inventory.json`.

## 8. Independent profile collection (plan only — not run here)

Raters blind to varṇa mappings, packets, hypothesis, true/foil assignment, and packet predictions; they receive only
the Sanskrit word, a controlled definition/source, and the fixed questionnaire. Predefine rater count, qualifications,
scale, missing-response handling, **inter-rater reliability threshold**, and aggregation. No author of
mappings/packets/hypotheses may supply confirmatory profiles. Below threshold → `PROFILE_TARGET_NOT_RELIABLE`. Spec:
`blind_profile_collection_protocol.json`.

## 9. Predict-then-measure ordering

Freeze words → freeze packet representation → freeze deterministic packet→attribute prediction → **hash-pin
predictions** → *only then* collect blind profiles → score mechanically after profiles are frozen. No one inspects
both predictions and profiles before both are frozen.

## 10. Packet→attribute projection

One deterministic/tightly-constrained transformation from the **complete** packet into the **same** closed attribute
space, identical per word, frozen before profiles, with defined order/repeat/contradiction/missing handling, no
per-word polarity, no target-aware wording, a hard capacity limit, and **byte-identical** across two implementations.
Free human/LLM narration is prohibited; an unconstrained LLM "interpretation" may **not** substitute for a defined
projection. **If the packet cannot be converted into the fixed attribute space without subjective narrative judgment →
`PREREG_BLOCKED_BY_UNDEFINED_PACKET_PROJECTION`.** Spec + feasibility: `packet_projection_spec.json`.

## 11. AND-composition

One fixed operator (intersection / min-support / product / constraint-satisfaction) that consumes **all** confirmatory
mappings, logs contradictions, produces one reproducible profile, is identical across words and non-adaptive to
meaning, and is byte-identical across two implementations. It operates on per-varṇa **attribute vectors** — which exist
only *after* the §10 projection. Spec: `and_composition_spec.json`.

## 12. Morphology baseline

For every word record any traditional/historical derivation, whether it predicts closed attributes, confidence +
source, and a morphology profile in the same space. The varṇa packet must show **incremental validity** over
dictionary-only, morphology, and generic-class baselines. Morphology ≥ true packet → `MORPHOLOGY_EXPLAINS_PROFILE`.
Spec: `morphology_baseline_spec.json`.

## 13. Controls

**T** true; **X** cross-word packet (frozen derangement); **R** randomized varṇa assignment; **S** order scramble;
**P** profile swap; **G** generic matched; **M** morphology/etymology; **D** dictionary/semantic-class. Matched for
profile density, attribute prevalence, word/packet length, valence, concreteness, grammatical class where practical.
Spec: `control_spec.json`.

## 14. Scoring (mechanical only)

One frozen `Fit(prediction, profile)` (precision, recall/coverage, F, contradiction penalty, weighted similarity)
applied identically to T/X/R/S/P/G/M/D. **No free-form "joint coherence"** unless reduced to an exact function.
Primary contrast `Δ = Fit(T) − max(Fit(X),Fit(R),Fit(P),Fit(G),Fit(M),Fit(D))`; order effect `Fit(T) − Fit(S)`;
cluster bootstrap over words (BCa CI), packet↔profile permutation, held-out replication, MDL/capacity bound,
lookup-table ban. Spec: `scoring_analysis_plan.json`.

## 15. Primary success criteria (conjunctive)

T > X, R, P, G, D, M; Δ CI excludes zero; direction replicates held-out; not driven only by valence/one class;
survives exclusion of pre-flagged transparent words; profile-swap margin collapses; inter-rater reliability passes.
Never from absolute fit. Spec: `success_kill_criteria.json`.

## 16. Synonym analysis (secondary)

Synonym sets (e.g. gaja/hastin/vāraṇa/kuñjara for elephant) only as a separately-powered secondary analysis, and only
if enough **independently documented distinct** profiles exist. Establish differences first via lexicography / corpus /
blind ratings; never invent nuance after seeing packets. Then test within-referent discrimination against morphology
and synonym-swap controls. (Note: within-synonym discrimination is exactly where morphology is the prime confound.)

## 17. Profile-swap integrity gate (mandatory)

Permute profiles across words; recompute everything. A valid word-specific signal requires strong T fit under correct
pairing **and** collapse toward null under swapping. Signal that survives swapping → `GENERIC_PROFILE_FIT_EXPLAINS`.

## 18. Held-out validation & capacity control

Split dev / untouched-confirmatory before any scoring; freeze inventory + projection using dev + permissible sources
only; no tuning on confirmatory profiles; capacity well below memorizing word-profile pairs; lookup tables and
word-specific exceptions forbidden. Spec: `heldout_split_procedure.json`.

## 19. Outcome taxonomy (one primary)

`SYMBOLIC_PROFILE_SIGNAL_REPLICATES` · `GENERIC_PROFILE_FIT_EXPLAINS` · `MORPHOLOGY_EXPLAINS_PROFILE` ·
`RANDOM_ASSIGNMENT_EXPLAINS` · `ORDER_NOT_INFORMATIVE` · `PROFILE_TARGET_NOT_RELIABLE` · `NO_SYMBOLIC_PROFILE_SIGNAL` ·
`STUDY_BLOCKED_BY_INSUFFICIENT_DATA` · `STUDY_BLOCKED_BY_UNDEFINED_PROJECTION`. **If run now → `STUDY_BLOCKED_BY_UNDEFINED_PROJECTION`.**

## 20. Feasibility gates & readiness verdict

| gate | pass |
|---|---|
| attribute inventory finalized | ✅ |
| eligibility rule defined | ✅ |
| **candidate words sourced + min sample** | ❌ needs external lexicographic sources (unavailable here); no invention allowed |
| **deterministic packet projection defined** | ❌ **domain mismatch** (tendency-space vs referent-attribute space) |
| AND operator has admissible inputs | ❌ inert without the projection |
| mechanical scoring defined | ✅ |
| **morphology baseline feasible** | ❌ needs external etymology sources |
| matched controls feasible | ✅ (depend on the blocked projection) |
| held-out split feasible | ✅ |
| profile reliability plan defined | ✅ (plan only) |

**The deepest blocker is conceptual and not resolvable by sourcing more words:** the frozen packet is composed of
**psychological-tendency** glosses (grasping hope, anxious rumination, restless striving, possessive attachment,
vanity, distorted discernment). A deterministic domain scan of all 66 confirmatory poles finds **40 tendency terms and
0 genuine referent-attribute terms** (7 apparent hits are all metaphor or substring accidents — "fire of life-force",
"quenched at its root", "not thirst for water", "f**light**", "late-t**rain**"). The closed attribute inventory
describes properties of a word's **referent** (animate/large/terrestrial/concrete). **No principled, non-narrative,
capacity-limited function maps tendency-space onto referent-property-space**, and none is supplied by the frozen
mappings; a frozen text-embedder is rejected (a prohibited unconstrained interpretation, leakage-driven). Therefore the
packet→attribute projection gate cannot be satisfied.

**Readiness verdict: `PREREG_BLOCKED_BY_UNDEFINED_PACKET_PROJECTION`.**

### What would unblock it (a *different* hypothesis, not a patch)

- Redefine the prediction target so packet and profile share **one domain** — e.g. an experiential/tendency inventory
  the packet actually populates. But then the "**referent** profile" target dissolves, and the hypothesis must be
  **reformulated** (it is no longer "packet predicts the word's referent-attributes").
- Or supply a principled, non-narrative, capacity-limited **tendency→referent-attribute** map derived independently of
  the target words. None is known; constructing one is the entire unsolved problem, not a preprocessing step.

## Exact next action

Do **not** proceed to Stage C. Either (a) reformulate the target into a single shared domain and re-run Stage F on the
reformulated claim, or (b) abandon the referent-attribute target. No profiles are collected and no packets are frozen
under the current, blocked formulation. Prior nulls stand; no positive claim exists.
