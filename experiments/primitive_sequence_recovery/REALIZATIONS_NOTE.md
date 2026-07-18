# Realization-Layer Note — Primitive-Sequence Recovery (Step C.2)

**Status:** Documentation only. Records the three realization artifacts authored under
`frozen/`. **No** distractors, realizer, run_params, or manifest were created; readiness
remains **NOT_READY**. No embeddings, no scores, no retrieval, no network/LLM, no Stage A
change. Design basis: `varna_lens/CANONICAL_PRIMITIVE_REPRESENTATION.md`,
`varna_lens/PREREG_PRIMITIVE_SEQUENCE_RECOVERY.md`, `SCHEMA_SPECIFICATION.md`.

A **realization** `R_j` attaches *content* to the opaque atoms of `assignment.json`. The
assignment itself stays semantics-free (relabeling-invariance theorem); content — and
therefore all testable signal — enters **only** here, and only through a realization that
can be varied and factored out. Three realizations are the minimum the pre-registration
requires, so that no single rendering can masquerade as ontological signal.

---

## 1. The three realizations

| file | `realization_id` | language | kind | atom content |
|---|---|---|---|---|
| `realization_en_gloss.json` | `en_gloss` | `en` | `gloss_text` | English gloss of each varṇa's vṛtti |
| `realization_sa_term.json` | `sa_term` | `sa` | `gloss_text` | Sanskrit (IAST) term of each varṇa's vṛtti |
| `realization_concept_id.json` | `concept_id` | `concept` | `synset_id` | opaque language-neutral concept-node ID (`svc:NN`) |

Each maps **all 34** assignment atoms (total coverage, mechanically verified). Each
`meaning_encoder.ref` names the *intended* offline resolver/embedding; **no resolver is run
here** — the actual asset is pinned later in `realizer.json` at freeze.

### Provenance

- **`en_gloss`** — `atom_content[atom]` = `word_formation_reading.english`, verbatim, from
  `varna_lens/lexicon_wordformation.json` (P.R. Sarkar's acoustic-root vṛtti table, *binding /
  in-combination* reading — the pole used when a varṇa enters a word). English surface strings.
- **`sa_term`** — `atom_content[atom]` = `word_formation_reading.sanskrit`, verbatim, from the
  **same** lexicon field. Sanskrit/IAST surface strings. One entry is a source gap (see §5).
- **`concept_id`** — `atom_content[atom]` = `svc:NN`, an opaque concept-node ID from a
  locally-authored inventory (`symbolu_vrtti_concept_inventory_v1`, §6) **derived from** the
  same vṛtti table. IDs are numbered by Sanskrit term (not by atom index), so the concept
  realization is a genuine re-encoding, not a trivial atom relabeling (1/34 IDs coincide with
  the atom index by chance). The concept *definitions* live in §6; the concept resolver /
  similarity graph is **not yet frozen** (§5).

---

## 2. Why they are declared independent

`SCHEMA_SPECIFICATION.md` §2 defines an independent realization pair as **distinct `source`
and distinct `language`/`kind`**, so a shared *rendering* bias cannot manufacture
cross-realization agreement. On that criterion the three pairs qualify:

| pair | distinct source? | distinct language/kind? |
|---|---|---|
| `en_gloss` ‖ `sa_term` | English gloss field vs Sanskrit term field | `en` vs `sa` (different embedding pipeline) |
| `en_gloss` ‖ `concept_id` | lexicon gloss vs concept inventory | `gloss_text`/`en` vs `synset_id`/`concept` |
| `sa_term` ‖ `concept_id` | lexicon term vs concept inventory | `gloss_text`/`sa` vs `synset_id`/`concept` |

The intent: if the ordered primitive sequence carries real signal, it should survive being
rendered in English text, in Sanskrit text, **and** through a non-textual concept graph — three
different encoders with three different failure modes. A positive under only one is at most
`REALIZATION_ARTIFACT` (English is never privileged); the confirmatory claim is
cross-realization invariance.

**This is independence of *rendering/encoder*, not of *source concept* — see §5.**

---

## 3. Why English-only is insufficient

A positive result under an English rendering alone cannot distinguish "the primitive sequence
carries meaning" from "English embeddings happen to align these particular gloss strings."
English glosses smuggle in English distributional structure, polysemy, and translator choices;
an English-only win is fully consistent with the ontology carrying **no** signal (the
`REALIZATION_ARTIFACT` verdict exists precisely for this). Requiring the same real-vs-scrambled
gap under Sanskrit terms and a language-neutral concept encoding is what would rule out an
English-rendering artifact. Hence English is authored as **one** realization among three, with
no privileged status.

## 4. Why a concept-ID realization is included

Both `en_gloss` and `sa_term` are still *text* — they inherit whatever a text embedder encodes
(orthography, frequency, morphology). The concept-ID realization is included to break that
shared modality: it references concept **nodes** (resolved by a concept graph), not surface
strings, so it can agree with the text realizations **only** through shared *meaning*, not
shared *lexical form*. If a signal is genuinely ontological it should reach the concept space
too; if it is a text artifact, the concept realization is where it should fail. It is the
strongest of the three independence levers — and (honestly) the least mature (§5).

---

## 5. Limitations and realization-dependence risk

These are stated plainly; some are material and could change the eventual verdict.

- **Shared conceptual source (the main caveat).** All three realizations trace to the *same*
  underlying vṛtti table (`lexicon_wordformation.json`). The independence achieved is of
  **rendering/encoder**, **not** of the source concept assignment. A bias baked into the
  original varṇa→vṛtti choices is **common to all three** and would not be caught by
  cross-realization agreement. True source-independence would require a second, independently
  constructed varṇa→meaning table — which does not exist here. Cross-realization invariance is
  therefore **necessary but not sufficient** evidence for an ontological signal; it controls
  for the *encoder*, not for the *concept table*. This must be foregrounded when interpreting
  any future result.
- **Concept resolver not yet frozen.** `concept_id` currently supplies concept *identities*
  and their definitions (§6); the concept-graph *similarity structure* that would give this
  realization independent discriminative content is **not** frozen (it belongs to the
  `realizer.json` asset, authored later). Until then the concept realization is effectively a
  placeholder: it cannot yet contribute genuine independent signal, and READY must not be
  declared on the strength of it.
- **Sanskrit source gap.** The source lists **no** binding-pole Sanskrit term for `sa`
  (its root is the *liberating* Mokṣa/Sattva); `sa_term` therefore stores the verbatim `"—"`
  for `atom_31`. This is faithful to the source but degenerate for embedding, and it touches
  every word containing `sa` (e.g. satya, sukha, asura, manas, rasa) under the `sa_term`
  realization. Not fabricated; flagged for resolution at the meaning/realizer freeze.
- **`synset_id` kind is a local inventory, not WordNet/Wikidata.** `concept_id` uses the
  `synset_id` kind to mean "concept-node ID"; the nodes are our locally-authored `svc:NN`
  inventory, **not** external database IDs (external KBs are not reachable in this offline
  environment, and fabricating real synset/Q-IDs would be dishonest). Provenance says so.
- **Gloss quality.** Several vṛtti glosses are compound/abstract ("lack of discrimination /
  confused discernment"); embedding stability of such phrases is untested and may itself be a
  realizer-dependent factor.

None of these are resolved by adding realizations; they are recorded so the readiness gate and
any eventual interpretation account for them.

---

## 6. Concept inventory (`symbolu_vrtti_concept_inventory_v1`)

Definitions for every `svc:NN` used by `realization_concept_id.json`. Numbered by Sanskrit
term; `definition_en` is the language-neutral concept gloss (from the same vṛtti table).

| concept_id | atom | varṇa | sanskrit | definition |
|---|---|---|---|---|
| svc:00 | atom_07 | ja | Ahaṁkāra | ego / inflated I-feeling |
| svc:01 | atom_11 | ttha | Anutāpa | repentance / remorse |
| svc:02 | atom_33 | ksha | Aparā-vidyā | mundane / material knowledge |
| svc:03 | atom_22 | ba | Avajñā | indifference / neglect |
| svc:04 | atom_05 | ca | Aviveka | lack of discrimination / confused discernment |
| svc:05 | atom_25 | ya | Aviśvāsa | lack of confidence / wavering movement |
| svc:06 | atom_21 | pha | Bhaya | fear |
| svc:07 | atom_02 | ga | Ceṣṭā | effort / striving |
| svc:08 | atom_01 | kha | Cintā | worry / impersonal thought |
| svc:09 | atom_04 | nga | Dambha | vanity / pride-display |
| svc:10 | atom_28 | va | Dharma | holding / ensconcement in original stance (BINDS — dhṛ = to hold; non-moral) |
| svc:11 | atom_20 | pa | Ghṛṇā | hatred / revulsion |
| svc:12 | atom_15 | ta | Jāḍya / Nidrā | inertia / staticity / dullness |
| svc:13 | atom_09 | nya | Kapaṭatā | hypocrisy / deceit |
| svc:14 | atom_17 | da | Krodha / Karkaśatā | peevishness / irritability |
| svc:15 | atom_27 | la | Krūratā | cruelty |
| svc:16 | atom_12 | dda | Lajjā | shyness |
| svc:17 | atom_08 | jha | Lobha | greed / avarice |
| svc:18 | atom_03 | gha | Mamatā | attachment / mine-ness |
| svc:19 | atom_19 | na | Moha | blind attachment / infatuation |
| svc:20 | atom_23 | bha | Mūrcchā | deluded obsession |
| svc:21 | atom_13 | ddha | Piśunatā | sadistic cruelty |
| svc:22 | atom_24 | ma | Praṇāśa / Praśraya | annihilation / indulgence (giving latitude) |
| svc:23 | atom_29 | sha | Rajoguṇa / Artha | mutative drive / material pursuit |
| svc:24 | atom_32 | ha | Rātri | night / darkness (contractive opposite of ha = day / light) |
| svc:25 | atom_26 | ra | Sarvanāśa | defeatist annihilation-thought |
| svc:26 | atom_30 | ssa | Tamoguṇa / Kāma | static inertia / worldly desire |
| svc:27 | atom_18 | dha | Tṛṣṇā | craving / thirst for acquisition |
| svc:28 | atom_06 | cha | Vikalatā | nervous breakdown / collapse |
| svc:29 | atom_10 | tta | Vitarka | overstatement / garrulousness |
| svc:30 | atom_16 | tha | Viṣāda | melancholy / dejection |
| svc:31 | atom_00 | ka | Āśā | hope / forward-grasping desire |
| svc:32 | atom_14 | nna | Īrṣyā | envy |
| svc:33 | atom_31 | sa | — | escapism / premature static withdrawal (no binding-pole Sanskrit term in source) |

---

## 7. Realization-specific meaning references (Step C.3)

`meaning_reference.json` now carries, for **every** word, a
`realization_specific_reference` with exactly the three realization IDs — how each
word's *target meaning* enters each realization's space (the query side, built from
varṇa-atom content, is scored against these targets; **no scoring is done here**).

| key | how produced | consumed by |
|---|---|---|
| `en_gloss` | the word's canonical English gloss, **verbatim** from `canonical_meaning` (unchanged) | `en_gloss` (gloss_text / en) |
| `sa_term` | the word's **Sanskrit lexeme** = `word_list.spelling` (IAST), the sense-fixed Sanskrit target | `sa_term` (gloss_text / sa) |
| `concept_id` | a deterministic **word-meaning** concept id `wmc:NNN`, one per distinct canonical meaning, numbered alphabetically by the English gloss | `concept_id` (synset_id / concept) |

`canonical_meaning` was **not** changed (no prior audit note required a further
correction beyond the already-applied jñāna→"cognition" fix).

### Atom concept IDs (`svc:NN`) vs word-meaning concept IDs (`wmc:NNN`)

These are two **different** inventories and must not be conflated:

- **`svc:NN`** (§6) is a **per-varṇa-atom** concept — the *vṛtti* attached to an opaque
  atom, used on the **query/atom** side by `realization_concept_id.json`. 34 of them.
- **`wmc:NNN`** is a **per-word-meaning** concept — the target a word denotes (anger,
  water, …), used on the **meaning/target** side here. One per distinct meaning (110).

Rule 4 requires the word-meaning reference to identify the *meaning*, not the atom; a
word's `concept_id` target is therefore a `wmc:*`, never an `svc:*`. The two spaces meet
only through the (later, not-yet-frozen) concept resolver.

### Excluded-word handling

The three excluded words (`w030` nārī, `w058` avidyā, `w068` ahimsā;
`exclude_flag=true`) **retain** meaning entries with all three references populated. The
readiness referential-integrity check requires every *present* meaning to carry every
realization id, and every *non-excluded* word to have a meaning; keeping complete refs on
the excluded entries satisfies both and keeps ids stable if a word is ever re-included.
Active count used for READY is **107** (excluded words are dropped from that count).

### Limitations / placeholders / gaps

- **`concept_id` is not yet independently grounded.** `wmc:NNN` is currently 1:1 with the
  English `canonical_meaning` (it is numbered by that gloss), so as it stands the
  word-meaning concept is effectively an **opaque relabeling of the English meaning**, not
  an independent language-neutral encoding. Genuine independence needs the concept
  resolver / similarity graph (to be frozen in `realizer.json`); until then `concept_id`
  cannot contribute real independent signal, and READY must not lean on it. Same caveat as
  the atom-level `svc` inventory (§5).
- **`sa_term` target = the word's own spelling.** This is the correct Sanskrit sense
  reference and is non-circular (the query is composed from *atom* vṛtti terms, not the
  spelling), but it means the Sanskrit target side inherits any transliteration/segmentation
  choices already in `word_list.spelling`. No word-level Sanskrit gap exists (all 110 words
  have IAST spellings); the only Sanskrit gap remains at the **atom** level (`sa`→"—", §5).
- **No placeholders were needed** for `sa_term` at the word level — every word has an exact
  Sanskrit lexeme, so rule 3's placeholder path did not trigger.
- **Shared conceptual source (unchanged).** As in §5, all three references still trace to
  the same meaning table; cross-realization agreement controls for the encoder, not for the
  meaning assignment.

> structure, not validated meaning.
