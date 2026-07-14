# B1.12 Bare-Word Symbolic Resonance — Word-List Precommitment V1

**Curation & precommitment only. No word was scored; no model was run; no mapping gloss was inspected.**
Controlling preregistration: `VARNA_SYMBOLIC_RESONANCE_PREREG_V1.md`; scope artifact:
`B1_12_SCOPE_UPDATE_AND_CONTROLLING_PREREG.md`. `EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`.

## Status: `B1_12_BSR_WORDLIST_PRECOMMITTED`

A fresh, adversarial, attested-Sanskrit **N = 20** bare-word list is frozen and hashed **before** any evaluator
run. Final word-list SHA-256: **`9779384dcb82e0c6d86fa88ed1f000317ed387ea5f227cb32f96f38b95f8a6ba`**.

## Frozen parameters (fixed before any mapping content was seen)

- **N = 20**; **category quotas = 4** per super-category × 5 = 20.
- **Deterministic rule:** attestation/lexical eligibility → contamination classification → parser + coverage
  eligibility → category quotas → **IAST Unicode-codepoint ascending** within category → take first eligible
  until quota & N met. No word was manually preferred after any mapping inspection.

## Pinned inputs

| Input | SHA-256 |
|---|---|
| Controlling prereg `VARNA_SYMBOLIC_RESONANCE_PREREG_V1.md` | (in `wordlist_manifest.json`) |
| Scope artifact `B1_12_SCOPE_UPDATE_AND_CONTROLLING_PREREG.md` | (in `wordlist_manifest.json`) |
| Parser `sanskrit_stage1_parser.py` | `d885391ffc269803…` |
| Mapping table `frozen/varna_native_stage1_merged_v3.json` | `65116f37…` (file hash only; gloss text not inspected) |

## Counts

- **Source-list size:** 30 · **Included:** 20 · **Excluded:** 10 (all `OVER_CATEGORY_QUOTA` — eligible but beyond
  the frozen quota under deterministic IAST order).
- **Fresh vs previously seen:** **20 / 20 `FRESH_UNINSPECTED`**; 0 previously-seen; 0 development-contaminated.
  (Checked against 122 indexed prior words from the 60-word symbolic-resonance set, resolution pilots,
  feature-lift dataset, and B1.12 G0/G1/descriptor development sets.)

## Category distribution (4 each)

| Super-category | Words |
|---|---|
| afflictive | droha (malice), garva (arrogance), kapaṭa (deceit), kleśa (distress) |
| virtue / calm | prema (love), santoṣa (contentment), sneha (affection), titikṣā (forbearance) |
| concrete object | dīpa (lamp), naukā (boat), setu (bridge), vastra (garment) |
| animal / body / living | bāhu (arm), kāka (crow), mayūra (peacock), nāsā (nose) |
| natural / action / abstract | bhūmi (earth), pāṭha (recitation), rūpa (form), snāna (bathing) |

Meets/exceeds all "≥3 per group" requirements (4 each).

## Included words with ordinary glosses (frozen list, IAST order)

| IAST | Devanāgarī | Ordinary gloss | Category | Consonants | Coverage |
|---|---|---|---|---|---|
| bhūmi | भूमि | earth | natural/action/abstract | bh, m | 100% |
| bāhu | बाहु | arm | animal/body/living | b, h | 100% |
| droha | द्रोह | malice | afflictive | d, r, h | 100% |
| dīpa | दीप | lamp | concrete object | d, p | 100% |
| garva | गर्व | arrogance | afflictive | g, r, v | 100% |
| kapaṭa | कपट | deceit | afflictive | k, p, ṭ | 100% |
| kleśa | क्लेश | distress | afflictive | k, l, ś | 100% |
| kāka | काक | crow | animal/body/living | k, k | 100% |
| mayūra | मयूर | peacock | animal/body/living | m, y, r | 100% |
| naukā | नौका | boat | concrete object | n, k | 100% |
| nāsā | नासा | nose | animal/body/living | n, s | 100% |
| prema | प्रेम | love | virtue/calm | p, r, m | 100% |
| pāṭha | पाठ | recitation | natural/action/abstract | p, ṭh | 100% |
| rūpa | रूप | form | natural/action/abstract | r, p | 100% |
| santoṣa | सन्तोष | contentment | virtue/calm | s, n, t, ṣ | 100% |
| setu | सेतु | bridge | concrete object | s, t | 100% |
| sneha | स्नेह | affection | virtue/calm | s, n, h | 100% |
| snāna | स्नान | bathing | natural/action/abstract | s, n, n | 100% |
| titikṣā | तितिक्षा | forbearance | virtue/calm | t, t, k, ṣ | 100% |
| vastra | वस्त्र | garment | concrete object | v, s, t, r | 100% |

## Parser-validity & coverage summary

All 20 parse successfully with **no warnings**, **no unsupported/missing units**, and **100% mapped-consonant
coverage** (every consonant occurrence is a mapped confirmatory-backbone unit). Coverage was computed **only** from
the set of mapped unit names (membership), never from gloss content.

## Excluded words and reasons (10)

All 10 are **`OVER_CATEGORY_QUOTA`** — attested, fresh, parser-valid, 100%-coverage, but placed beyond the frozen
4-per-category quota by deterministic IAST order:
ālasya, vaira (afflictive); śraddhā, vinaya (virtue); śayyā, yaṣṭi (concrete); udara, uṣṭra (animal/body);
tuṣāra, ākāśa (natural). None excluded for content reasons; full records in `excluded_candidates.json`.

## Firewall & discipline confirmations

- **No mapping glosses influenced selection.** Selection used only attestation, ordinary meaning, lexical
  ambiguity, morphology, semantic category, parser validity, coverage (unit-set membership), and prior-artifact
  contamination. The binding-gloss **text** was never read during curation.
- **No prior scores influenced selection.** No component score, relationship type, or expected fit was consulted.
- **No word was scored.** No BSR packet, no Run A/Run B, no model prompt, no Qwen/Mistral execution.
- **The old 60-word calibration set was NOT reused** as the primary list — all 20 are `FRESH_UNINSPECTED`.
- **No prior or frozen artifact was modified** — parser, mappings, controlling prereg, and all previous B1.12
  artifacts are unchanged; only this new precommitment directory was added.

## Artifacts

`b1_12_symbolic_resonance_wordlist_v1/`: `candidate_source_list.json`, `included_wordlist.json`,
`excluded_candidates.json`, `contamination_audit.json`, `parser_coverage_audit.json`, `wordlist_manifest.json`,
this report.

## Guardrails
Word-list curation & precommitment only. No scoring, no model, no evidence generation, no gloss inspection during
selection, no modification of prior/frozen artifacts. Frozen before any evaluator run. Structure, not validated
meaning.
