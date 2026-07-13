# B1.12 — Gate G1 Ordered Component-Descriptor Instrument V1.2 (design spec)

**Versioned replacement design for the underdetermined opaque-ID G1 task** (reassessment `bb2051e`,
`G1_BLOCKED_NO_IDENTIFIABLE_TASK`). Remains **B1.12** (same H2 question — does ordered varṇa composition add
word-specific information beyond unordered inventory; the opaque encoding was an instrument failure, not a new
hypothesis). Prior G1 artifacts preserved unchanged as development history. **No B1.13.**

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`. No judges, no run, no contexts beyond rigid
templates, no evidence freeze. No change to the selected six, G0, pool, parser, lexicon, or thresholds. B1.10
`G0_NOT_TESTABLE_WITH_CURRENT_PROSE_PACKETS`; B1.11 unchanged.

**Outcome of building this instrument: `G1_BLOCKED_DESCRIPTOR_QUALITY`** (see §7 and `B1_12_G1_V1_2_REPORT.md`).
The design is documented here in full; the block is a property of the only available frozen descriptor source,
not of the design shape.

---

## 1. Selected six (unchanged, frozen by G0 `1713311`)
W03 asthi · W15 grīvā · W20 jñāna · W23 keśa · W30 nadī · W35 sūrya. Not replaced, removed, or added.

## 2. Instrument shape

- **Component descriptors at the varṇa level** (not word level): each atomic varṇa identity `(type,unit)` in the
  six gets one fixed descriptor. **18 distinct identities** (12 consonants, 6 vowels).
- **Arms** (all share the exact same component multiset, count, and template; only order varies):
  - **A** — components in true pronunciation-derived order (repetition preserved);
  - **B** — same components, fixed-seed scramble (seed 20260101), differs from A, no resample;
  - **D** — same components, canonical order by `stable_component_id` (no pronunciation-order semantics);
  - **E** (secondary only) — ordered adjacent descriptor pairs.
- **Rigid renderer:** `position i: <descriptor>`, one line per varṇa, **no connectives, no prose paragraphs,
  no progression/causal language**.
- **Primary task (candidate-relative semantic matching):** evaluator sees one arm's components + the fixed set
  of six ordinary candidate meanings (randomized order), no Sanskrit word / transliteration / raw varṇa id / arm
  label; chooses the meaning best represented. Correct answer = the hidden word's frozen ordinary meaning.
- **Primary contrast:** `Δ_order = Acc(A) − Acc(B)` (within-word); secondary `Δ_inventory = Acc(A) − Acc(D)`.
  A positive claim requires true order to beat **both** matched controls.

## 3. Descriptor tiers (frozen policy)

- **Tier A — source-backed:** where the frozen merged lexicon (`varna_native_stage1_merged_v1.json`) has a
  gloss, use the exact **binding-pole** `binding_vritti` **verbatim** (fixed polarity, no switching, no
  softening/broadening); mechanical case/whitespace normalization only (no truncation/paraphrase); original +
  normalized both preserved; source path + hash recorded.
- **Tier B — developmental gap-fill:** for uncovered identities, one concise fixed `DEVELOPMENT_ONLY` descriptor
  authored without inspecting any selected word; if none defensible → identity `UNMAPPED` and G1 blocked.
  **(Not needed here — coverage is 100% source-backed.)**

## 4. Descriptor-authoring firewall (role separation)

- **Role A (inventory extractor):** reads only frozen parser output + lexicon coverage; **does not** read
  selected-word meanings or word→meaning fit. → `required_varna_inventory.json`, `coverage_report.json` (commit 1).
- **Role B (descriptor author):** receives only the atomic identity + its frozen source gloss; **does not**
  receive which word contains it, word meanings, full word sequences, or the candidate set. Descriptors are keyed
  purely by `(type,unit)` from the lexicon. → `component_descriptor_map_draft.json`,
  `component_descriptor_source_audit.json` (commit 2).
- **Role C (reviewer / application):** source fidelity, neutrality, non-narrative, distinctness, length/tier
  parity, coverage, leakage; renderer + task spec; verdict. → `descriptor_quality_audit.json`,
  `arm_render_spec.json`, `leakage_control_spec.json`, reports (commit 3).
- Emulated in one session via **three sequential commits**; authoring and audit are **not** in the same commit.

## 5. Rigid descriptor schema (per entry)
`atomic_identity · stable_component_id · source_tier · source_status · original_frozen_gloss ·
normalized_component_descriptor · source_reference · source_hash · review_status · development_only · notes`
(provenance only). No Sanskrit word examples, no word-level interpretation, no connectives
(`becomes/leads-to/transforms/resolves/culminates/balances/removes`).

## 6. Why this design is H2, not B1.10 prose-packet
A, B, D use the **exact same** component descriptors, the same count, and the same formatting; **only order
differs** between A and B; D removes order; there is **no** authored word-level packet prose and **no**
progression narrative; the primary statistic is the **order advantage**, not general packet quality. Any gain
common to A/B/D is inventory/descriptor utility, **not** ordered-composition evidence.

## 7. Full-coverage gate & why the instrument is nonetheless blocked
- **Coverage gate:** `SelectedSetCoverage = 100%` (`G1_COMPONENT_COVERAGE_COMPLETE`) — all 18 identities have a
  frozen binding-pole gloss (consonants CONFIRMATORY_BACKBONE, vowels DEVELOPMENT_ONLY). The merged lexicon
  closes the vowel gap that `VARNA_PLAIN` (11 consonants) left open.
- **Descriptor-quality gate FAILS** (`G1_BLOCKED_DESCRIPTOR_QUALITY`), on three independent grounds, none
  fixable without firewall violation, fabrication, or softening the frozen mappings:
  1. **`DESCRIPTOR_NEUTRALITY_FAILURE` (dominant, unfixable):** 16/18 glosses are **affliction/psychological-
     tendency** descriptors (peevishness, grasping hope, moha/attachment, kāma/desire, self-doubt, melancholy…)
     — a semantic domain **orthogonal to the ordinary concrete referents** (bone, river, sun, hair, knowledge,
     neck) the task must match. There is **no principled basis** for an evaluator to map affliction-tendencies to
     referents, in any order → the instrument has **no headroom** for an order effect (the same
     "answer-inaccessible-from-supplied-information" failure as the opaque task, now semantic). Referent-level
     descriptors cannot be authored without inspecting the words' meanings (firewall violation) or fabricating
     unsourced glosses.
  2. **`DESCRIPTOR_LENGTH_LEAKAGE`:** vowel descriptors 24–36 chars vs consonant descriptors 87–217 chars —
     **disjoint** ranges → descriptor length perfectly classifies vowel vs consonant → the rendered arms expose
     each word's **consonant/vowel skeleton** (a strong structural fingerprint) **before any judge is run**.
  3. **`DESCRIPTOR_SOURCE_TIER_LEAKAGE`:** DEVELOPMENT_ONLY (vowel) vs CONFIRMATORY (consonant) descriptor
     lengths are disjoint → source tier leaks via length. Plus the source glosses embed illustrative examples /
     Sanskrit terms / narrative (`—`, parentheticals) that reintroduce the B1.10 prose-packet confound.

## 8. Versioned G1 status
**`G1_BLOCKED_DESCRIPTOR_QUALITY`.** Not passed: although coverage is 100% and the A/B/D design is sound, the
only frozen descriptor source cannot support a neutral, leakage-safe, referent-matchable task. A usability probe
is **not** meaningful with these descriptors.

## 9. Resolution path (separate, pre-registered; none taken here)
Author a **referent-neutral, length-parity, non-narrative, coverage-adequate** component-descriptor set under a
new B1.12 pre-registration with its own blinding — descriptors must (a) be authorable without inspecting the
selected words' meanings, (b) provide a principled basis for matching to ordinary referents, (c) hold length and
source-tier parity, (d) contain no examples/progression. If no such source exists, the honest conclusion is that
**H2 via a leakage-safe evaluator instrument is not testable with current frozen varṇa mappings** — consistent
with B1.10's null and the arbitrariness-of-the-sign prior. Structure, not validated meaning.
