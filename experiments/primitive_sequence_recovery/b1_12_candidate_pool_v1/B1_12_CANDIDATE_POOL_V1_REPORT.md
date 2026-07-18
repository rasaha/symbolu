# B1.12 — Developmental Candidate Pool v1 — Curator Freeze Report

**Readiness: `CANDIDATE_POOL_V1_FROZEN`.** 35 eligible, attested, parser-valid Sanskrit words frozen and hashed.
This is the **curator** commit (V1.1 §13); the G0 auditor role is **not** performed here. Selection was **blind
to every structural metric** — words were chosen on attestation / meaning / category / morphology /
parser-validity **only**. Ordered atomic-varṇa sequences are **sealed** (not emitted into any artifact) for the
later G0-auditor step.

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`. Structure, not validated meaning. No
`GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; no ontology / semantic-truth / Sanskrit-privilege / individual-varṇa
claim. B1.4b′ remains `NULL_RETURN_BOTTOM`; B1.10 `G0_NOT_TESTABLE_WITH_CURRENT_PROSE_PACKETS`; B1.11 unchanged.

---

## 1. Controlling artifacts

- `B1_12_ORDERED_VARNA_COMPOSITION_PREREG.md` (commit `2c613f4`)
- `B1_12_ORDERED_VARNA_COMPOSITION_PREREG_V1_1.md` (commit `6f197fd`) — frozen constants + pool rules (§12) + role separation (§13)
- `B1_12_ORDERED_VARNA_COMPOSITION_PREREG_V1_2.md` (commit `7935f48`) — order-distinctness formula correction

## 2. Developmental-simplicity note (scope of this first pool)

This first pool is intentionally built to test the ordered-sequence instrument under **favorable but
legitimate** conditions: **short words, clear concrete meanings, simple morphology, reliable Monier-Williams
attestation, limited phonological complexity.** This is **not** cherry-picking, because selection is **blind to
all B1.12 structural metrics and expected outcomes** (§6). **Any future positive result is limited to this
simple-data regime** until replicated on longer forms, abstract concepts, broader categories, harder phonology,
and independent held-out pools. **No generality is claimed from this pool.**

## 3. Pool size & source list

- **Source list considered:** 54 words (all parser-valid) + 4 pre-excluded on morphology/ambiguity = 58 entries.
- **Frozen pool size:** **35** (target 30–36; ≤40 respected).
- **Deterministic selection rule:** per-category target, then canonical **IAST ascending (Unicode NFC
  code-point)** within each category; stable IDs `W01…W35` assigned in **global IAST-ascending** order after
  selection. **No manual choice among equally valid words; no preferred six nominated.**

## 4. Category distribution (targets met)

| category | target | selected | words |
|---|---|---|---|
| ANIMAL | 7 | 7 | aja, aśva, gaja, haṃsa, khaga, mīna, mṛga |
| NATURAL_OBJECT | 6 | 6 | aśma, bīja, giri, jala, latā, maṇi |
| BODY | 6 | 6 | asthi, danta, grīvā, kara, karṇa, keśa |
| PHENOMENON | 6 | 6 | agni, candra, hima, megha, nadī, sūrya |
| ACTION | 5 | 5 | dāna, gati, hāsa, nṛtya, pāna |
| ABSTRACT | 5 | 5 | bala, bhaya, jñāna, satya, sukha |
| **total** | **35** | **35** | 6 categories, ≥5 each — abstract/affective kept a minority (5/35) |

## 5. Included words (id · IAST · ordinary gloss · category)

`W01 agni` fire · PHENOMENON  |  `W02 aja` goat · ANIMAL  |  `W03 asthi` bone · BODY  |  `W04 aśma` stone ·
NATURAL_OBJECT  |  `W05 aśva` horse · ANIMAL  |  `W06 bala` strength · ABSTRACT  |  `W07 bhaya` fear · ABSTRACT
|  `W08 bīja` seed · NATURAL_OBJECT  |  `W09 candra` moon · PHENOMENON  |  `W10 danta` tooth · BODY  |
`W11 dāna` gift/giving · ACTION  |  `W12 gaja` elephant · ANIMAL  |  `W13 gati` motion · ACTION  |  `W14 giri`
mountain · NATURAL_OBJECT  |  `W15 grīvā` neck · BODY  |  `W16 haṃsa` goose/swan · ANIMAL  |  `W17 hima` snow ·
PHENOMENON  |  `W18 hāsa` laughter · ACTION  |  `W19 jala` water · NATURAL_OBJECT  |  `W20 jñāna` knowledge ·
ABSTRACT  |  `W21 kara` hand · BODY  |  `W22 karṇa` ear · BODY  |  `W23 keśa` hair · BODY  |  `W24 khaga` bird ·
ANIMAL  |  `W25 latā` creeper · NATURAL_OBJECT  |  `W26 maṇi` jewel · NATURAL_OBJECT  |  `W27 megha` cloud ·
PHENOMENON  |  `W28 mīna` fish · ANIMAL  |  `W29 mṛga` deer · ANIMAL  |  `W30 nadī` river · PHENOMENON  |
`W31 nṛtya` dance · ACTION  |  `W32 pāna` drinking · ACTION  |  `W33 satya` truth · ABSTRACT  |  `W34 sukha`
happiness · ABSTRACT  |  `W35 sūrya` sun · PHENOMENON.

## 6. Anti-selection discipline (what was NOT inspected)

During curation **none** of the following were computed or consulted: pairwise edit distances; order-distinctness
scores; n-gram / endpoint overlaps; subset eligibility; whether any word helps G0 pass; binding/liberating
gloss packets; likely experimental outcomes. The parser was run **only** for per-word eligibility (§8). The
`b1_12_freeze_candidate_pool_v1.py` generator contains **no** distance, n-gram, subset, or metric code. Words
similar in surface form (e.g. `kara`/`karṇa`) were **kept** because they are morphologically independent
lexemes — surface-sequence appearance was deliberately **not** used to add, drop, or replace any word.

## 7. Attestation

Primary source **Monier-Williams** (headword pointer per word; Apte permitted as secondary per V1.1 §12). All
35 are standard classical lexemes with a single dominant ordinary meaning; no reconstructed or unattested forms.

## 8. Parser-validity summary

- **Parser:** `sanskrit_stage1_parser.py`, spec `PARSER_SPEC_v1`,
  sha256 `d885391ffc269803ae776191181a509c7880ace76bc631318eb0270103721947`.
- **Predeclared eligibility rule:** parser completes; `warnings == []`; no atomic unit typed
  `unsupported`/`missing`; atomic-varṇa length ∈ **[2, 6]**.
- **Result:** 54/54 considered words **valid**; **0** invalid / out-of-band; 4 pre-excluded on
  morphology/ambiguity before parsing. All 35 selected words pass validity.
- **Sequences sealed:** the ordered `atomic_varnas` are **not** stored in any artifact (verified: no
  `atomic_varnas` key present) — only validity + length + warnings are recorded, preserving curator/auditor
  separation.

## 9. Length distribution (atomic-varṇa count, selected pool)

`len 3: 1` (aja) · `len 4: 25` · `len 5: 8` (danta, grīvā, haṃsa, jñāna, karṇa, nṛtya, satya, sūrya) ·
`len 6: 1` (candra). All within the frozen band [2, 6].

## 10. Exclusions

- **Pre-parse (morphology / ambiguity), 4:** `hasta` (near-synonym of `kara` "hand"); `gamana` (same root √gam
  as `gati`); `duḥkha` (prefix-variant of `kha` paired with `sukha`); `go` (homograph cow/ray/speech/earth —
  ambiguous controlling gloss).
- **By deterministic IAST truncation (over-allocated categories), 19:** the alphabetically-later valid words in
  categories that exceeded their target (e.g. `mukha, nakha, nayana, pāda, phala, puṣpa, tṛṇa, vana, vṛkṣa,
  nara, sarpa, siṃha, vṛka, tārā, varṣa, vidyut, vāyu, śakti, snāna`). These remain in the source list for
  future pools; their exclusion is purely the deterministic rule, never sequence appearance.
- **Parser-invalid / out-of-band:** 0.

## 11. Artifacts & hashes

| file | role |
|---|---|
| `b1_12_candidate_source_list.json` | all 58 considered entries + validity + exclusion reasons |
| `b1_12_candidate_pool_v1.json` | **frozen 35-word pool** (sequences sealed) — sha256 `8cf857891f95bb07e66a3048f7eabe4f1e5814777889abdf6dadb0d5d296d0b4` |
| `b1_12_candidate_pool_manifest.json` | controlling pregs/commits, selection rule, parser hash, counts, category/length distributions, pool SHA-256, no-metrics/no-preferred-subset confirmations |
| `b1_12_freeze_candidate_pool_v1.py` | deterministic curator generator (no metric code) |

## 12. Role separation & next step

This is the **pool-curator** commit. A **separate** G0-auditor task/commit may then reveal the ordered parser
outputs, build the opaque-ID map, compute structural metrics, enumerate size-6 subsets, and issue the G0 verdict
under V1.1/V1.2. **The auditor may not add, remove, or replace any word in this frozen pool.**

## 13. Guardrails

Docs/data-only + one deterministic curator script. No G0 metric computed; no preferred six chosen; no G1 work,
contexts, judges, generators, or runs; no binding/liberating packets or evaluator encoding; no import of the
Varṇa–Affliction Resolution Test; V1.1/V1.2 thresholds unchanged; B1.10 and B1.11 unchanged. **Structure, not
validated meaning.**
