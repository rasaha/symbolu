# B1.12 — Gate G1 V1.2 (Normalized Ordered Component-Descriptor Instrument) — Report

**Verdict: `G1_BLOCKED_DESCRIPTOR_QUALITY`.** This iteration went further than the v1 attempt (`d48ae9f`):
descriptors were **normalized to shorter standalone labels**, full A/B/D render examples were generated, and a
complete descriptor-quality + deterministic-leakage audit was run. Normalization removed some narrative but did
**not** unblock the instrument — length leakage persists and the affliction-vs-referent domain mismatch is
irreducible.

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`. No judges run, no evidence, no confirmatory freeze.
Remains B1.12 (no B1.13). Prior G1 artifacts preserved. B1.10/B1.11 unchanged.

---

## Required atomic-varṇa inventory (Phase 1)
**18 identities:** consonants d, g, j, k, n, r, s, th, v, y, ñ, ś (12) + vowels a, ā, i, ī, e, ū (6).

## Coverage
- **Source-backed: 18/18.** Developmental gap-fill: **0.** Unmapped: **0.** **SelectedSetCoverage = 100% →
  `G1_COMPONENT_COVERAGE_COMPLETE`** (from the merged lexicon binding pole; consonants CONFIRMATORY_BACKBONE,
  vowels DEVELOPMENT_ONLY).

## Descriptor-authoring firewall
Three sequential commits: (1) inventory + source-status freeze (Role A, no word meanings); (2) descriptor
authoring keyed only by `(type,unit)` from the frozen lexicon — verbatim binding gloss + mechanical
normalization (Role B); (3) audit + arm spec/examples + verdict (Role C).

## Descriptor-quality result — FAILED
| diagnostic | result |
|---|---|
| entries / exact duplicates | 18 / 0 |
| prohibited progression terms | none |
| normalized length min–max–mean | 24 – 121 – ~57 |
| vowel vs consonant length range | 24–36 vs 37–121 (**disjoint** → C/V leak persists) |
| DEVELOPMENT vs CONFIRMATORY length | disjoint |
| em-dash narrative retained | 11 of 12 consonant labels |
| raw Sanskrit terms in labels | 7 (āśā, moha, sarvanāśa, sattvic, viśāda, aviśvāsa, kāma) |
| affliction/tendency-domain | **17 / 18** |
| descriptor domain vs candidate domain | affliction_tendency **≠** ordinary_concrete_referent |
| **outcomes** | `DESCRIPTOR_LENGTH_LEAKAGE`, `DESCRIPTOR_SOURCE_TIER_LEAKAGE`, `DESCRIPTOR_NEUTRALITY_FAILURE` |

## Chosen evaluator task
Candidate-relative semantic matching, within-word; `Δ_order = Acc(A) − Acc(B)` primary, `Δ_inventory =
Acc(A) − Acc(D)` secondary. Design sound; blocked by descriptor content.

## A/B/D parity result
**Exact** — for every word, arms A/B/D share the identical component-id multiset and template footprint; A ≠ B in
order; D is canonical (sorted by component id); content-masked arms are byte-identical. (`abd_parity_multiset_equal
= true`.)

## Deterministic leakage-control result
- Descriptor **length still leaks the C/V skeleton** (disjoint vowel/consonant ranges) — pre-run leak.
- **First descriptor is unique per word** (first-position shortcut).
- **Unordered inventory uniquely identifies each word** (distinct inventories) → arm D alone identifies the word
  → **no order headroom** even with diagnostic descriptors.
- **Raw Sanskrit terms** present in 7 evaluator-facing descriptors.
- Content-masked arm formatting is identical (no format-only classification). Target-word transliteration absent
  from renders.
- These are `CONTROL_LEAKAGE`-class risks concurrent with, and independent of, the descriptor-quality block.

## Revised B1.12 G1 verdict
**`G1_BLOCKED_DESCRIPTOR_QUALITY`** (dominant: `DESCRIPTOR_NEUTRALITY_FAILURE` — affliction-vs-referent domain
mismatch, irreducible; with concurrent length/tier leakage and inventory-identifiability). The design and
mechanics pass; the only frozen descriptor source is unfit for the task.

## Output paths & commits
`results/b1_12_g1_semantic_components_v1_2/`: `required_varna_inventory.json`, `coverage_report.json` (commit 1);
`component_descriptor_map.json`, `component_descriptor_source_audit.json` (commit 2);
`descriptor_quality_audit.json`, `arm_render_spec.json`, `arm_render_examples.json`, `leakage_control_spec.json`,
`g1_v1_2_manifest.json`, `B1_12_G1_ORDERED_COMPONENT_INSTRUMENT_V1_2.md`, this report,
`test_b1_12_g1_semantic_components_v1_2.py` (commit 3). Builder: `b1_12_g1_semantic_components_v1_2.py`.

## Is a diagnostic usability probe now meaningful?
**No.** With these descriptors a probe would measure affliction-vs-referent mismatch, length/first-position/
inventory shortcuts — not order. A meaningful probe requires the resolution below first.

## Unresolved risks & resolution path
- **Dominant risk (unchanged, now demonstrated with normalized labels):** the frozen varṇa mappings are
  affliction-tendency glosses, not referent descriptors; any instrument asking evaluators to recover ordinary
  referent meaning from varṇa composition is underpowered regardless of order — indirectly consistent with
  B1.10's null.
- **Resolution (separate pre-registration; not taken here):** a referent-neutral, length-parity, non-narrative,
  Sanskrit-term-free, coverage-adequate descriptor set authored without inspecting the selected words, on a word
  set whose inventories are not individually identifying (for order headroom). If none exists, conclude H2-via-
  leakage-safe-evaluator is **not testable** with current frozen varṇa mappings.

## Confirmations
No judges, evidence outputs, or confirmatory freeze occurred (deterministic tests; `pytest` 13 passed). Remains
B1.12 (no B1.13). Selected six, G0, pool, parser, merged lexicon, and prior thresholds untouched; prior G1
artifacts preserved; B1.10 and B1.11 unchanged. Structure, not validated meaning.
