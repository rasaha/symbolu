# Varṇa Feature-Lift Study — Pre-Run Freeze Report V1

**Data-assembly and pre-run freeze only.** No feature computed, no embedding, no model, no prediction metric, no
real-vs-shuffled comparison, no lift result. This report freezes the **word list**, the **independent affective
target labels**, the **dependence/split controls**, the **shuffle-control spec**, the **base-representation spec**,
and a **complete audit of every failed / excluded candidate**. `EXPLORATORY / DEVELOPMENT_ONLY /
NOT_CONFIRMATORY_EVIDENCE`.

Controlling preregistration: `VARNA_FEATURE_LIFT_PREREG_V1.md` (`READY_FOR_PRERUN_FREEZE`). This report executes
its §13 pre-run-freeze gate. It modifies **no** prereg, parser, lexicon, or B1.x / Varṇa–Affliction artifact.

**Readiness: `READY_FOR_FEATURE_EXTRACTION_AND_LIFT_RUN`** — 88 words included (floor 30). The run itself
(§5–§7 of the prereg) requires ML dependencies absent here and occurs elsewhere.

---

## 0. Reproduction

Generator: `build_varna_feature_lift_prerun_v1.py` (deterministic; no network at run time; reads the pinned norm
CSV locally). Emits eleven JSON artifacts under `varna_feature_lift_prerun_v1/`. Re-running reproduces byte-identical
outputs (fixed seeds; no `Date.now`/`random`).

```
python3 build_varna_feature_lift_prerun_v1.py
```

## 1. Frozen inputs & checksums

| Input | Identity / SHA-256 |
|---|---|
| Parser | `sanskrit_stage1_parser.py` — `d885391ffc269803ae776191181a509c7880ace76bc631318eb0270103721947` |
| Lexicon (33 confirmatory-backbone consonants + verbatim binding glosses) | `varna_native_stage1_merged_v1.json` — `af4c1f54adbfac2b0e2be88993860dcca5e1ebf41631efec23672786584cca96` |
| Affective-norm source | Warriner, Kuperman & Brysbaert (2013) VAD — `78ac8107c78e116bb96538fae4faa47281a155f5f8fe39f30bbc6ea3db05b446` |
| Real consonant→gloss bijection (shuffle anchor) | `af697897bbb10f70591f62049716ba08a460472886cc456cc3e04df53c2d0f8b` |
| Split assignment | `aba4af30ecc73eac6f0cb3e1e9a0159008c8f069fcd4383caa2d584379567325` |

Per-artifact hashes are pinned in `varna_feature_lift_prerun_v1/prerun_freeze_manifest.json`.

## 2. Affective target (independent, non-circular)

- **Source:** Warriner et al. (2013), 13,905 English lemmas rated for **Valence / Arousal / Dominance** (1–9
  Likert means). Produced with **zero** knowledge of Sanskrit phonology or the varṇa mappings → no shared source
  with the feature. Pinned by URL + SHA-256; **raw CSV NOT committed** (size + license — reconstruct from the
  pinned `source_url` + checksum in `affective_norm_source_manifest.json`; the derived per-word values live in the
  committed `word_target_table.json`).
- **Primary target: Arousal / Activation** (`A.Mean.Sum`). **Secondary (reported, not primary):** Valence
  (`V.Mean.Sum`), Dominance (`D.Mean.Sum`).
- **Lookup rule (frozen):** lowercase **exact-lemma** match on the controlling English gloss. Fuzzy / stemmed /
  nearest-neighbor matching is **prohibited**; a gloss absent as an exact lemma → `NO_EXACT_NORM_MATCH` exclusion
  (recorded, never replaced).
- **Target spread over the 88 included words** (evidence the primary target is genuinely discriminating, not a
  constant): Arousal min 2.67, max 7.24, mean 4.55, SD 1.00. Valence min 1.68, max 8.48, mean 5.75, SD 1.71.
  Dominance min 2.50, max 7.42, mean 5.42, SD 1.14.

## 3. Word list — how candidates were built (blind to the target)

The candidate pool of 106 attested Sanskrit words was assembled on **linguistic grounds only**. Every field used
for eligibility — attestation, the single controlling ordinary-English gloss, translation-ambiguity flags,
technical/proper-name flags, root family — was fixed **before any arousal/valence value was consulted**. No
candidate was added, kept, dropped, or re-glossed because of how its target looked or whether it "fit" the
theory. `no_target_informed_selection: true` is asserted in the freeze manifest.

Eligibility gates (all pre-declared, applied in stage order §5 below):
1. **Attested** (Monier-Williams) Sanskrit lexeme.
2. **Single dominant ordinary-English gloss** that is materially unambiguous. Words whose ordinary gloss is
   genuinely split across materially different senses (e.g. *go* = cow / earth / ray / speech) are excluded as
   `MATERIAL_GLOSS_VALENCE_CONFLICT` — **not** because of their affect, but because no single gloss can carry the
   label honestly.
3. **Not** a proper name / religious-philosophical technical term (`PROPER_NAME_OR_TECHNICAL_TERM`).
4. **Parser-valid** and yields **≥1 mapped confirmatory consonant** with sufficient mapping coverage.
5. Gloss present as an **exact lemma** in the norms lexicon.
6. **Dependence-clean** (no duplicate English gloss; see §6).

## 4. Included words (88) — controlling gloss, target, structure, split

Consonants are the parser's occurrence-level mapped confirmatory consonants (multiset; order shown for reference
only — **the feature is order-free**, prereg §2/§4). `A/V/D` = Warriner Arousal/Valence/Dominance means.

| ID | IAST | Gloss | A | V | D | Category | Consonants | Split |
|---|---|---|---|---|---|---|---|---|
| S001 | agni | fire | 6.05 | 4.32 | 4.57 | nature | g+n | train |
| S002 | aja | goat | 2.94 | 5.3 | 5.17 | animal | j | train |
| S003 | asthi | bone | 4.75 | 5.24 | 6.0 | body | s+th | test |
| S004 | aśma | stone | 3.25 | 4.81 | 7.26 | nature | ś+m | dev |
| S005 | aśva | horse | 4.16 | 6.05 | 5.71 | animal | ś+v | dev |
| S006 | bala | strength | 5.3 | 6.73 | 7.42 | abstract | b+l | test |
| S007 | bhakti | devotion | 4.73 | 6.0 | 6.3 | emotion | bh+k+t | train |
| S008 | bhaya | fear | 6.14 | 2.93 | 3.32 | emotion | bh+y | test |
| S010 | buddhi | intellect | 4.41 | 6.62 | 6.69 | cognitive | b+d+dh | train |
| S011 | bīja | seed | 3.68 | 6.38 | 5.19 | nature | b+j | test |
| S012 | candra | moon | 3.43 | 7.0 | 6.11 | nature | c+n+d+r | train |
| S013 | danta | tooth | 3.52 | 5.06 | 4.89 | body | d+n+t | dev |
| S015 | dhana | wealth | 5.24 | 7.33 | 6.53 | abstract | dh+n | train |
| S017 | dhūma | smoke | 5.0 | 3.44 | 4.17 | nature | dh+m | dev |
| S018 | duḥkha | sorrow | 3.55 | 2.95 | 3.8 | emotion | d+kh | train |
| S019 | dveṣa | hatred | 5.22 | 2.38 | 4.0 | emotion | d+v+ṣ | dev |
| S020 | dāna | gift | 4.64 | 7.27 | 6.32 | action | d+n | dev |
| S021 | gaja | elephant | 4.23 | 6.17 | 4.23 | animal | g+j | train |
| S023 | gardabha | donkey | 2.9 | 6.29 | 5.12 | animal | g+r+d+bh | train |
| S024 | gati | motion | 4.71 | 5.8 | 6.15 | action | g+t | dev |
| S025 | ghaṭa | pot | 4.0 | 5.81 | 6.0 | object | gh+ṭ | test |
| S026 | giri | mountain | 4.12 | 6.65 | 6.18 | nature | g+r | train |
| S028 | grīvā | neck | 3.65 | 5.44 | 5.17 | body | g+r+v | train |
| S029 | gṛha | house | 3.95 | 7.19 | 6.41 | object | g+h | train |
| S030 | harṣa | joy | 5.55 | 8.21 | 7.0 | emotion | h+r+ṣ | test |
| S031 | hasta | hand | 3.98 | 5.9 | 5.88 | body | h+s+t | test |
| S033 | hima | snow | 4.57 | 6.78 | 5.62 | nature | h+m | train |
| S034 | hāsa | laughter | 5.39 | 8.05 | 7.02 | action | h+s | train |
| S035 | hṛdaya | heart | 5.07 | 6.95 | 5.43 | body | h+d+y | train |
| S036 | jala | water | 3.71 | 7.0 | 6.12 | nature | j+l | train |
| S037 | jihvā | tongue | 4.25 | 6.29 | 6.32 | body | j+h+v | train |
| S038 | jñāna | knowledge | 4.86 | 7.28 | 7.2 | cognitive | j+ñ+n | test |
| S039 | kapi | monkey | 5.15 | 5.82 | 5.74 | animal | k+p | test |
| S041 | karṇa | ear | 3.5 | 5.86 | 6.74 | body | k+r+ṇ | train |
| S042 | keśa | hair | 3.71 | 6.18 | 6.69 | body | k+ś | train |
| S043 | khaga | bird | 3.83 | 6.75 | 5.88 | animal | kh+g | test |
| S044 | khaḍga | sword | 5.95 | 5.27 | 6.0 | object | kh+ḍ+g | train |
| S045 | krodha | anger | 5.93 | 2.5 | 5.14 | emotion | k+r+dh | dev |
| S046 | krīḍā | play | 3.81 | 7.55 | 6.29 | action | k+r+ḍ | test |
| S049 | kṣudhā | hunger | 4.8 | 3.2 | 3.18 | state | k+ṣ+dh | test |
| S050 | lajjā | shame | 5.4 | 2.62 | 5.21 | emotion | l+j+j | test |
| S051 | latā | creeper | 5.68 | 3.61 | 3.86 | nature | l+t | train |
| S052 | lobha | greed | 4.45 | 2.48 | 4.0 | emotion | l+bh | test |
| S054 | manas | mind | 5.05 | 6.7 | 6.09 | cognitive | m+n+s | train |
| S055 | maṇi | jewel | 3.83 | 6.68 | 5.1 | object | m+ṇ | train |
| S056 | megha | cloud | 2.81 | 6.2 | 4.79 | nature | m+gh | test |
| S057 | mitra | friend | 4.29 | 6.79 | 6.31 | person | m+t+r | train |
| S058 | moha | delusion | 4.6 | 3.3 | 3.91 | emotion | m+h | train |
| S060 | mārjāra | cat | 4.5 | 6.95 | 5.48 | animal | m+r+j+r | train |
| S061 | mīna | fish | 3.33 | 6.42 | 6.08 | animal | m+n | train |
| S062 | mṛga | deer | 3.95 | 6.89 | 4.89 | animal | m+g | train |
| S063 | mṛtyu | death | 5.53 | 1.89 | 3.42 | state | m+t+y | dev |
| S064 | nadī | river | 4.22 | 6.72 | 4.89 | nature | n+d | train |
| S065 | netra | eye | 3.95 | 6.18 | 5.72 | body | n+t+r | train |
| S066 | nidrā | sleep | 3.6 | 7.22 | 5.3 | state | n+d+r | train |
| S067 | nṛtya | dance | 5.48 | 7.27 | 6.28 | action | n+t+y | test |
| S069 | phala | fruit | 4.09 | 7.0 | 6.12 | nature | ph+l | train |
| S070 | pustaka | book | 3.13 | 7.05 | 6.41 | object | p+s+t+k | train |
| S071 | puṣpa | flower | 3.67 | 7.3 | 6.43 | nature | p+ṣ+p | train |
| S072 | pāda | foot | 2.77 | 4.68 | 5.97 | body | p+d | train |
| S073 | pāpa | sin | 5.82 | 3.08 | 5.74 | abstract | p+p | train |
| S075 | ratha | chariot | 4.11 | 6.11 | 6.59 | object | r+th | train |
| S076 | roga | disease | 5.5 | 1.68 | 2.8 | state | r+g | test |
| S077 | samudra | sea | 2.8 | 6.56 | 5.22 | nature | s+m+d+r | train |
| S078 | sarpa | snake | 7.24 | 4.03 | 3.65 | animal | s+r+p | dev |
| S079 | satya | truth | 3.88 | 7.19 | 6.95 | abstract | s+t+y | train |
| S080 | siṃha | lion | 5.29 | 5.84 | 4.86 | animal | s+h | train |
| S081 | smṛti | memory | 4.08 | 6.58 | 5.75 | cognitive | s+m+t | test |
| S082 | sukha | happiness | 6.5 | 8.48 | 7.05 | emotion | s+kh | test |
| S083 | suvarṇa | gold | 6.35 | 7.28 | 5.8 | object | s+v+r+ṇ | test |
| S084 | svapna | dream | 4.37 | 7.43 | 5.4 | state | s+v+p+n | dev |
| S085 | sūrya | sun | 4.64 | 6.92 | 4.98 | nature | s+r+y | test |
| S086 | tārā | star | 5.5 | 7.47 | 5.82 | nature | t+r | test |
| S087 | tṛṇa | grass | 3.39 | 6.47 | 5.67 | nature | t+ṇ | test |
| S089 | vana | forest | 4.44 | 6.68 | 5.71 | nature | v+n | train |
| S091 | vidyut | lightning | 6.75 | 5.34 | 4.0 | nature | v+d+y+t | dev |
| S092 | vyāghra | tiger | 5.55 | 6.0 | 4.4 | animal | v+y+gh+r | train |
| S094 | vāyu | wind | 3.7 | 5.67 | 4.5 | nature | v+y | dev |
| S095 | vīra | hero | 6.35 | 7.44 | 5.78 | person | v+r | train |
| S096 | vṛka | wolf | 5.25 | 6.26 | 4.59 | animal | v+k | train |
| S097 | vṛkṣa | tree | 2.67 | 7.59 | 5.62 | nature | v+k+ṣ | train |
| S099 | yaśas | fame | 4.63 | 5.45 | 6.27 | abstract | y+ś+s | test |
| S100 | yuddha | war | 6.27 | 2.23 | 3.27 | action | y+d+dh | test |
| S102 | īrṣyā | envy | 4.35 | 3.05 | 3.16 | emotion | r+ṣ+y | train |
| S103 | śatru | enemy | 5.3 | 2.22 | 2.5 | person | ś+t+r | test |
| S104 | śiras | head | 4.45 | 5.86 | 5.56 | body | ś+r+s | train |
| S105 | śoka | grief | 4.95 | 2.33 | 3.26 | emotion | ś+k | train |
| S106 | śānti | peace | 4.65 | 7.75 | 7.17 | emotion | ś+n+t | train |

**Category distribution (88):** nature 21, animal 13, emotion 13, body 11, object 7, action 6, abstract 5,
state 5, cognitive 4, person 3. Deliberately spans calm/stable referents, fierce animals, destructive forces,
and afflictive concepts (matching the prereg's adversarial-breadth intent), with the target label pulled
**after** the pool was fixed.

## 5. Failed / excluded sample audit (complete)

**Every** candidate that entered but did not reach `included` is recorded in `excluded_word_manifest.json` with
its attempted English gloss, its parser result, its failure **stage**, and its failure **reason** from the fixed
taxonomy. No candidate was recorded as "failed" because its varṇa feature looked weak, its target looked
difficult, or it did not fit the theory — failure reasons are **structural / lexical only**.

**Fixed failure taxonomy** (the full pre-declared set; only reasons actually triggered are listed with counts):

| Reason | Meaning | Count |
|---|---|---|
| `MATERIAL_GLOSS_VALENCE_CONFLICT` | ordinary gloss splits across materially different senses; no single honest label | 10 |
| `PROPER_NAME_OR_TECHNICAL_TERM` | proper name / religious-philosophical technical term | 3 |
| `DUPLICATE_ENGLISH_GLOSS` | same controlling English gloss as an already-kept word (dependence dedup) | 3 |
| `NO_EXACT_NORM_MATCH` | gloss absent as an exact lemma in the norms lexicon | 2 |
| `TRANSLATION_AMBIGUITY` | (declared; not triggered) | 0 |
| `MULTIWORD_GLOSS_REQUIRED` | (declared; not triggered) | 0 |
| `PARSER_INVALID` | (declared; not triggered) | 0 |
| `NO_MAPPED_CONSONANTS` | (declared; not triggered) | 0 |
| `INSUFFICIENT_MAPPING_COVERAGE` | (declared; not triggered) | 0 |
| `SANSKRIT_MORPHOLOGICAL_DUPLICATE` | (declared; not triggered) | 0 |
| `NEAR_SYNONYM_DEPENDENCE` | (declared; not triggered) | 0 |
| `UNSUPPORTED_AFFECTIVE_TARGET` | (declared; not triggered) | 0 |
| `GROUP_SPLIT_CONFLICT` | (declared; not triggered) | 0 |
| `OTHER_PREDECLARED_EXCLUSION` | (declared; not triggered) | 0 |

**All 18 excluded candidates:**

| ID | IAST | Attempted gloss | Reason | Stage | Note |
|---|---|---|---|---|---|
| S009 | bhojana | food | MATERIAL_GLOSS_VALENCE_CONFLICT | 1 | food vs eating vs meal — materially different |
| S014 | deva | god | PROPER_NAME_OR_TECHNICAL_TERM | 1 | religious technical term |
| S016 | dharma | virtue | MATERIAL_GLOSS_VALENCE_CONFLICT | 1 | virtue/duty/law/religion — materially different |
| S022 | gamana | going | NO_EXACT_NORM_MATCH | 4 | "going" absent as exact lemma |
| S027 | go | cow | MATERIAL_GLOSS_VALENCE_CONFLICT | 1 | cow/earth/ray/speech — materially different |
| S032 | haṃsa | swan | NO_EXACT_NORM_MATCH | 4 | "swan" absent as exact lemma |
| S040 | kara | hand | MATERIAL_GLOSS_VALENCE_CONFLICT | 1 | hand/ray/tax — materially different |
| S047 | kāma | desire | MATERIAL_GLOSS_VALENCE_CONFLICT | 1 | desire vs love vs lust — materially different |
| S048 | kṣetra | field | MATERIAL_GLOSS_VALENCE_CONFLICT | 1 | field/body/sacred-place — materially different |
| S053 | mada | pride | MATERIAL_GLOSS_VALENCE_CONFLICT | 1 | pride vs intoxication — materially different |
| S059 | mukha | face | MATERIAL_GLOSS_VALENCE_CONFLICT | 1 | face vs mouth — materially different |
| S068 | parvata | mountain | DUPLICATE_ENGLISH_GLOSS | 5 | duplicate of S026 *giri* (mountain) |
| S074 | rakta | blood | MATERIAL_GLOSS_VALENCE_CONFLICT | 1 | blood (noun) vs red (adj) — materially different |
| S088 | vahni | fire | DUPLICATE_ENGLISH_GLOSS | 5 | duplicate of S001 *agni* (fire) |
| S090 | varṣa | rain | MATERIAL_GLOSS_VALENCE_CONFLICT | 1 | rain vs year — materially different |
| S093 | vānara | monkey | DUPLICATE_ENGLISH_GLOSS | 5 | duplicate of S039 *kapi* (monkey) |
| S098 | yajña | sacrifice | PROPER_NAME_OR_TECHNICAL_TERM | 1 | ritual technical term |
| S101 | ātman | self | PROPER_NAME_OR_TECHNICAL_TERM | 1 | philosophical technical term |

The two `NO_EXACT_NORM_MATCH` exclusions were independently verified against the pinned CSV: *going* and *swan*
are genuinely not present as exact lowercase lemmas (Warriner is lemma-based; the exact-match rule is applied
without fuzzy fallback, as pre-declared). The three `DUPLICATE_ENGLISH_GLOSS` exclusions each collide with an
earlier-sorted included word carrying the identical gloss; the kept mate is the alphabetically-first IAST form,
a mechanical rule fixed before any target was seen.

## 6. Candidate funnel (six stages, with counts)

| Stage | Gate | Remaining | Dropped |
|---|---|---|---|
| 0 | considered | 106 | — |
| 1 | scope valid (unambiguous single gloss; not proper/technical) | 93 | 13 |
| 2 | parser valid (parses; ≥1 mapped consonant; coverage ok) | 93 | 0 |
| 3 | gloss frozen | 93 | 0 |
| 4 | exact norm match | 91 | 2 |
| 5 | dependence clean (no duplicate gloss) | 88 | 3 |
| 6 | **included** | **88** | 0 |

Drops by reason: `MATERIAL_GLOSS_VALENCE_CONFLICT` 10 + `PROPER_NAME_OR_TECHNICAL_TERM` 3 (stage 1);
`NO_EXACT_NORM_MATCH` 2 (stage 4); `DUPLICATE_ENGLISH_GLOSS` 3 (stage 5). Total excluded 18; 106 − 18 = 88.

## 7. Dependence controls & split freeze

- **Dependence:** words are grouped by `root_family`; a duplicate controlling English gloss is dropped
  (`DUPLICATE_ENGLISH_GLOSS`) so no two included words carry the same label. Among the 88 included words the
  grouping yields **88 singleton groups** — i.e. after the material-duplicate and same-gloss exclusions, no two
  survivors share a root family, so no train/test leakage across morphological relatives is possible. (The
  grouping machinery is still applied and frozen so the property is enforced, not assumed.)
- **Split (frozen):** grouped, deterministic, hash-ordered on a fixed seed (`20260101`); target **never**
  consulted; no manual reassignment. Sizes: **train 49 · dev 13 · test 26** (test 30%, dev ~15%). Assignment
  SHA-256 `aba4af30…`; full ID lists in `split_manifest.json`. **Test is untouched until the single final run.**

## 8. Shuffle-control freeze (critical control)

- **Procedure:** global bijective permutation of the **33** consonant→gloss assignments; features recomputed with
  the **same** encoder and pooling as the real feature. Preserves gloss inventory, dimensionality, word lengths,
  multiplicity, and missingness — **only** the consonant→gloss identity changes, isolating the *specific*
  assignments from generic negativity / length / dimensionality.
- **Frozen params:** `K = 1000` permutation seeds, master seed `20260101`, derangement not required (fixed points
  allowed and recorded per seed). Real bijection anchor SHA-256 `af697897…`. **No permutation executed here.**

## 9. Base-representation freeze

- **Base input:** the controlling English gloss text (lowercased lemma). Secondary weaker base: the Sanskrit IAST
  form (reported separately). The base model **must not** receive the varṇa packet — the feature must add signal
  *on top of* the base.
- **Feature `f(w)`:** the **same** frozen sentence encoder applied to each mapped consonant's exact binding gloss,
  then **mean-pooled**, multiplicity preserved, **order-free** (prereg §4). Recommended encoder id
  `sentence-transformers/all-mpnet-base-v2`, 768-d, mean pooling, L2 normalization; exact **id + revision + hash
  pinned at run start, encoder never tuned**. Nothing embedded here (`executed: false`).

## 10. Artifacts (committed) & guardrails

Under `varna_feature_lift_prerun_v1/` (hashes in `prerun_freeze_manifest.json`): `candidate_source_list.json`,
`included_word_manifest.json`, `excluded_word_manifest.json`, `word_target_table.json`,
`affective_norm_source_manifest.json`, `dependency_groups.json`, `split_manifest.json`,
`shuffle_control_manifest.json`, `base_representation_manifest.json`, `sample_failure_funnel.json`,
`prerun_freeze_manifest.json`. Narrative failed-sample walkthrough: `sample_failure_examples.md`.

**Not committed:** the raw Warriner CSV (`_norm_src/`, git-ignored) — pinned by checksum only.

**Guardrails.** Data assembly + freeze only. No feature/embedding/model/metric/real-vs-shuffled/lift computed.
Target labels are an independent affective lexicon (no shared source with the mappings). Word selection and all
exclusions are structural/lexical and **outcome-blind**; no sample was ever failed for a weak feature, a hard
target, or theory-misfit. Parser, lexicon, mappings, the Varṇa–Affliction Resolution Test, and all B1.x artifacts
are unchanged. Structure, not validated meaning.
