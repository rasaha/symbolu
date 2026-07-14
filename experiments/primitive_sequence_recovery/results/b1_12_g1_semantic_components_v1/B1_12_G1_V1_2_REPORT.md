# B1.12 — Gate G1 V1.2 (Ordered Component-Descriptor Instrument) — Report

**Verdict: `G1_BLOCKED_DESCRIPTOR_QUALITY`.** The coverage-complete semantic ordered-component instrument was
built and audited; it is blocked because the only frozen descriptor source (affliction/tendency glosses) cannot
support a neutral, leakage-safe, referent-matchable order test. Coverage is 100%; the block is descriptor
quality, not coverage.

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`. No judges run, no evidence produced, no
confirmatory freeze. Remains B1.12 (no B1.13). Prior opaque G1 design (`9e8da86`) and reassessment (`bb2051e`)
preserved unchanged as development history. B1.10/B1.11 unchanged.

---

## Required atomic-varṇa inventory (Step 1, Role A)

**18 distinct `(type,unit)` identities** across the six (from frozen G0 `parser_outputs.json`):
- **Consonants (12):** d, g, j, k, n, r, s, th, v, y, ñ, ś
- **Vowels (6):** a, ā, i, ī, e, ū

## Coverage (Step 5)

- **Source-backed (Tier A): 18/18.** Developmental gap-fill (Tier B): **0.** `UNMAPPED`: 0.
- **SelectedSetCoverage = 100% → `G1_COMPONENT_COVERAGE_COMPLETE`.** Consonants are CONFIRMATORY_BACKBONE, vowels
  DEVELOPMENT_ONLY in the merged lexicon; the merged lexicon closes the vowel gap that `VARNA_PLAIN` (11
  consonants) left open — so the reassessment's coverage block is lifted by using the richer frozen source.

## Descriptor-authoring firewall (Step 3)

Emulated via three sequential commits: (1) inventory + source-status freeze; (2) descriptor authoring keyed
purely by `(type,unit)` from the frozen lexicon (fixed **binding** pole, verbatim, mechanical case/whitespace
normalization only); (3) audit + spec + verdict. The authoring stage received **only** atomic identities + their
frozen source glosses — never the selected-word meanings, sequences, or the candidate set.

## Descriptor quality audit (Step 10) — FAILED

| diagnostic | result |
|---|---|
| entries / exact duplicates | 18 / 0 |
| length min–max–mean | 24 – 217 – 108.4 |
| vowel length range | **24–36** |
| consonant length range | **87–217** (disjoint from vowels) |
| DEVELOPMENT vs CONFIRMATORY length | disjoint |
| embedded examples / parentheticals / em-dash narrative | 12 entries |
| affliction/tendency-domain descriptors | **16 / 18** |
| descriptor domain vs candidate domain | affliction_tendency **≠** ordinary_concrete_referent |
| **outcomes** | `DESCRIPTOR_LENGTH_LEAKAGE`, `DESCRIPTOR_SOURCE_TIER_LEAKAGE`, `DESCRIPTOR_NEUTRALITY_FAILURE` |

**Three independent, unfixable failures:**
1. **Neutrality / domain mismatch (dominant):** the frozen glosses describe **afflictions/psychological
   tendencies**, orthogonal to the concrete referents (bone, river, sun…). No principled basis exists for
   matching them to referents in any order → the instrument has no headroom to detect an order effect. This is
   the semantic analogue of the opaque task's "answer inaccessible from supplied information."
2. **Length leakage:** vowel (24–36) vs consonant (87–217) descriptor lengths are disjoint → rendered arms
   expose each word's consonant/vowel skeleton **before any judge** — a pre-run structural leak.
3. **Source-tier leakage + prose confound:** DEVELOPMENT (vowel) vs CONFIRMATORY (consonant) lengths disjoint;
   12 glosses embed examples/Sanskrit-term narrative → reintroduces the B1.10 prose-packet confound.

## Revised evaluator task (Step 7)

Candidate-relative semantic matching, within-word, `Δ_order = Acc(A) − Acc(B)` primary, `Δ_inventory =
Acc(A) − Acc(D)` secondary (spec in `arm_render_spec.json`). Design is sound; it is the **descriptor content**
that blocks it.

## A/B/D parity status (Step 6)

Render spec fixes identical multiset/count/template across arms; A true order, B fixed-seed scramble (20260101,
≠A, no resample), D canonical-by-component-id. **Parity of the design is intact** — but content-level parity is
undermined by the length leakage above (descriptor lengths correlate with vowel/consonant, so "identical
template footprint" still leaks the C/V pattern).

## Leakage-control status (Step 9)

`leakage_control_spec.json` defines the required ablations (first/last-position-only, unordered inventory,
single-most-diagnostic, content-masked, candidate-only) and the ≥1/6 tolerance. **Spec-level pre-run finding:**
descriptor length already leaks the C/V skeleton with content unmasked → a `CONTROL_LEAKAGE`-class problem before
any judge is run, concurrent with the descriptor-quality block.

## Revised B1.12 G1 verdict (Step 11)

**`G1_BLOCKED_DESCRIPTOR_QUALITY`** (with concurrent length/tier leakage). Not passed: descriptor audit fails and
domain match is false, so the coverage-complete instrument cannot be used. A **diagnostic usability probe is NOT
meaningful** with these descriptors — it would measure descriptor-referent mismatch and leakage, not order.

## Output paths & commits

`results/b1_12_g1_semantic_components_v1/`: `required_varna_inventory.json`, `coverage_report.json` (commit 1);
`component_descriptor_map_draft.json`, `component_descriptor_source_audit.json` (commit 2);
`descriptor_quality_audit.json`, `arm_render_spec.json`, `leakage_control_spec.json`, `g1_v1_2_verdict.json`,
`B1_12_G1_ORDERED_COMPONENT_INSTRUMENT_V1_2.md`, this report, `test_b1_12_g1_semantic_components_v1.py`
(commit 3). Builder: `b1_12_g1_semantic_components_v1.py`.

## Unresolved risks & resolution path

- **Dominant risk:** the frozen varṇa mappings are affliction-tendency glosses with no referent-descriptive
  content — so *any* instrument asking evaluators to recover ordinary referent meaning from varṇa composition is
  underpowered regardless of order (indirectly consistent with B1.10's null).
- **Resolution (separate pre-registration; not taken here):** author a referent-neutral, length-parity,
  non-narrative, coverage-adequate component-descriptor set authorable without inspecting the selected words'
  meanings; if none exists, conclude H2-via-leakage-safe-evaluator is **not testable** with current frozen
  varṇa mappings.

## Confirmations

No judges, evidence outputs, or confirmatory freeze occurred. Selected six, G0, pool, parser, merged lexicon,
and all prior thresholds untouched; B1.10 and B1.11 unchanged; prior G1 artifacts preserved. Structure, not
validated meaning.
