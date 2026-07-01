# Review — Ontology-Level Frozen Artifacts (pre-realization audit)

**Status:** Review report only. No artifact changes, no realizations/distractors/manifest, no run, no embeddings/scores, no Stage A change. Audits `frozen/{assignment,word_list,meaning_reference}.json` (73-word Sanskrit corpus, consonant-only).

**Verdict:** assignment is clean; the word list and meanings are usable but have **blocking issues that must be resolved before adding realizations** — chiefly 3 canonical-sequence collisions (including two exact antonym pairs) and a weak/spurious `family_id`. N=73 is below the ≥100 READY target.

---

## 1. `assignment.json` — opacity audit → **PASS**

- Top-level keys exactly `{schema_version, varnas, atoms, tau}`; no extra fields.
- 34 varṇas → 34 **distinct opaque atoms** `atom_00..atom_33`; injective; every `tau` value matches `atom_\d\d` (no gloss/meaning/polarity/coordinate/realization text anywhere).
- Schema-valid. **No opacity violations.**

---

## 2. `word_list.json` — audit

**Decomposition (general):** 73 words, consonant-only; lengths {2:41, 3:28, 4:4}; no empty or singleton sequences. Conjuncts handled correctly (`kṣ→ksha`, `jñ→ja,nya`, e.g. `jñāna→[ja,nya,na]`, `vṛkṣa→[va,ksha]`).

**2a. Sequence collisions (BLOCKING).** Three groups of distinct words share an identical canonical sequence, because consonant-only decomposition **drops the a-privative prefix and vowel length**:

| sequence | words (meanings) | nature |
|---|---|---|
| `na, ra` | nara (man) / nārī (woman) | gender via dropped vowel length (a/ā, ī) |
| `va, da, ya` | vidyā (knowledge) / avidyā (ignorance) | **exact antonyms** via dropped a-privative |
| `ha, ma, sa` | himsā (violence) / ahimsā (nonviolence) | **exact antonyms** via dropped a-privative |

For each pair the query is *identical*, so no realization can ever rank them apart — including both makes those items unrankable and injects guaranteed confusion. **Honest observation:** that two exact opposites (vidyā/avidyā, himsā/ahimsā) collapse to the same consonant skeleton is itself mild evidence that the consonant-only primitive sequence does not determine meaning for these words (the meaning-flipping morpheme lives in a dropped vowel). This is a structural limit of the chosen decomposition, not a bug in the data.

**2b. Questionable segmentation (minor).** `duḥkha → [da, kha]` drops the visarga (ḥ); acceptable under consonant-only but noted.

**2c. Polysemy.** `sense_id` is uniformly `"0"`; the corpus is common single-sense nouns, so this is fine for now — except the antonym pairs above, which are not polysemy but morphological relatives.

**2d. `family_id` weak/provisional (BLOCKING for READY).** Current family = initial-consonant varṇa → 21 families, 6 singletons, largest 8 (`fam_ma`, `fam_pa`, `fam_na`). This **spuriously groups** unrelated words that merely share a first consonant, and — worse — **fails to group genuine relatives** (vidyā/avidyā and himsā/ahimsā are etymological kin but land in different families). This partition is unfit for the Galton-safe bootstrap and must be replaced (see §5).

---

## 3. `meaning_reference.json` — audit

**3a. Coverage → PASS.** 73/73 words have a meaning; `realization_specific_reference` is empty for all (correct — no realizations attached yet).

**3b. Vague / multi-sense glosses (flag, non-blocking).**
- **Gloss duplicate:** `"knowledge"` is the canonical meaning for **both** jñāna and vidyā → an ambiguous ranking target (two distinct words, one meaning string). Disambiguate (e.g. jñāna = "gnosis/realized knowledge", vidyā = "learning/knowledge") or exclude one.
- **Abstract/broad glosses** likely to complicate distractor matching and ranking: *form* (rūpa), *essence* (rasa), *action* (karma), *world* (loka), *union* (yoga), *power/strength* (śakti/bala), *illusion* (māyā) vs *delusion* (moha), *truth* (satya). Recommend upgrading these to language-neutral concept IDs (WordNet synset / Q-ID) at the meaning-freeze, and matching distractors on category.

---

## 4. Top-up plan to N ≥ 100

Current usable N after removing one member of each collision (−3) ≈ **70**; need **≥30 more** clean words.

**Inclusion rules (apply at assembly):**
1. IAST with diacritics; single dominant concrete sense; ≥1 consonant.
2. **Unique canonical sequence** — reject any word whose consonant-only skeleton collides with an existing or already-accepted word (this is the check that would have caught the antonym pairs).
3. Prefer **concrete nouns** (animals, nature, artifacts) over abstract concepts to reduce gloss vagueness.
4. Avoid **near-synonyms** of existing entries (keep meanings distinct); avoid morphological variants (a-privative, gendered pairs) of existing words.
5. Prefer words that **cover under-represented atoms**.

**Exclusion rules:** drop on skeleton-collision, high polysemy, or synonymy/derivation from an existing entry.

**Candidate pool (already collision-checked; 37 pass, no new files created):** aśva(horse), gaja(elephant), siṃha(lion), sarpa(snake), khaga(bird), mṛga(deer), go(cow), megha(cloud), vidyut(lightning), samudra(ocean), dvīpa(island), ratna(jewel), suvarṇa(gold), rajata(silver), kāṣṭha(wood), tṛṇa(grass), mūla(root), bīja(seed), kṣetra(field), grāma(village), nagara(city), mārga(road), dvāra(door), setu(bridge), cakra(wheel), dhanus(bow), śara(arrow), khaḍga(sword), ratha(chariot), vastra(cloth), kṣīra(milk), madhu(honey), taila(oil), lavaṇa(salt), yajña(sacrifice), tapas(austerity), karṇa(ear). *(mīna, patra, mukha were rejected for colliding with existing words — the rule working as intended.)* Adding ~30 of these clears N ≥ 100.

Recommended source for further top-up: a standard basic-vocabulary/Swadesh-style Sanskrit noun list (Monier-Williams headwords), filtered by the rules above. **No new file until approved.**

---

## 5. `family_id` refinement

Replace the initial-consonant heuristic (it is spurious). In priority order:
1. **Etymological root (dhātu) family — preferred.** Group by verbal/nominal root (from a root-annotated source such as Monier-Williams). This correctly co-locates true relatives (vid → vidyā/avidyā; hiṃs → himsā/ahimsā; nṛ → nara/nārī) and is the right resampling unit for the Galton-safe bootstrap.
2. **Source/derivation family** — if a derivational database is used, group by shared derivational base.
3. **Conservative unique-family fallback.** If no etymology is available, assign **one family per word** (treat words as independent) **plus** a small hand-curated merge list for the obvious morphological relatives above. Unique-family is safer than the current heuristic (no spurious grouping); the manual merges recover the few known kin.

Do **not** ship the initial-consonant family into a READY manifest.

---

## Recommended actions before Step C.2 (realizations)

**Blocking (fix in the artifacts first):**
- Resolve the 3 sequence collisions — set `exclude_flag=true` on one member each (recommend the derived/less-basic member: avidyā, ahimsā, nārī) **or** document them as an intentional identical-sequence probe. Exclusion is cleaner.
- Disambiguate or de-duplicate the `"knowledge"` gloss.
- Replace `family_id` per §5.

**Blocking for READY (later, not now):**
- Top up to N ≥ 100 per §4.
- Consider upgrading abstract glosses to concept IDs at the meaning-freeze.

**Non-blocking:** visarga handling in `duḥkha`.

No artifact was modified by this review; this report is the only deliverable.

> structure, not validated meaning.
