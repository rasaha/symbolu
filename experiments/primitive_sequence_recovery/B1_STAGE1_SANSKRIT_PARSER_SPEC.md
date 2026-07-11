# B1 — Stage-1 Native-Sanskrit Parser Specification (docs-only)

**Status: `PARSER_SPEC_v1` — specification only. No parser code, no varṇa-table change, no vowel meanings, no
scoring, no Track-G change, no Sanskrit word experiment.** This document specifies a deterministic decomposer that
turns a Devanāgarī word into a lossless, ordered phonological record. It is **Stage-1 input infrastructure**: it
assigns **no** binding/liberating meaning, chooses **no** polarity, aggregates **no** facets, and scores nothing.

**Structure, not validated meaning.** No `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; no ontology / semantic-truth /
Sanskrit-privilege / generation-utility claim. B1.4b′ remains `NULL_RETURN_BOTTOM`; Track B blocked; run01, Track G,
and all frozen mappings unchanged.

---

## 0. Source framing (what the source does and does not mandate)

The patent/source architecture (`Rakesh_Mohan_NPA_SymbolU.docx`) permits **“syllabic or phonetic units”** and
**separately** assigns roles to consonants and to vowels. It does **not** uniquely mandate akṣara-level *or*
atomic-varṇa-level decomposition. This specification therefore does **not** claim the source selects one exclusive
unit. Instead it adopts a **hierarchical, lossless** representation that preserves **both** levels:

```
Devanāgarī surface form  →  ordered akṣara sequence  →  ordered atomic phonological-varṇa sequence
```

Three distinctions are kept explicit throughout and must never be conflated:

| layer | what it is | provenance status |
|---|---|---|
| **source-supported architecture** | "syllabic or phonetic units"; consonants and vowels have roles | attested in source |
| **parser engineering decision** | the exact deterministic rules R1–R12 below | authored engineering, *not* a meaning claim |
| **later empirical composition hypothesis** | whether/how order, akṣara vs varṇa, vowels compose to meaning | out of scope here; a separate pre-registered study |

Emitting a vowel/anusvāra/visarga varṇa in the atomic record is a **phonological fact only**; it attaches **no**
pole and adds **no** meaning. The polarity table has no vowel entries and this spec does not create any.

---

## 1. Canonical input (Decision 1)

- **Authoritative input:** normalized Devanāgarī (rule R1).
- Roman/IAST transliteration is generated as **metadata for readability only**; it **must not** control
  decomposition. (This directly removes the Stage-0 spelling confound: the old pipeline decomposed English
  orthography, e.g. `faith→[ta]`, `doubt→[da,ba,ta]`. Under this spec the letters never participate.)

---

## 2. Canonical output schema (Decision 2)

Every word yields one record. **No field is optional-by-omission**; absent data is an explicit empty list or
`null`, never a silent drop.

```jsonc
{
  "word_id": "s000",
  "word_devanagari": "शान्ति",              // exactly as supplied
  "normalized_devanagari": "शान्ति",         // R1 (Unicode NFC)
  "transliteration_iast": "śānti",          // metadata only; derived from atomic layer
  "normalization": {
    "form": "NFC",
    "changed": false,                        // true iff normalized != original
    "notes": []
  },
  "aksharas": [                              // ORDERED; the source's syllabic/pronounceable grouping
    {
      "index": 0,
      "devanagari": "शा",
      "translit": "śā",
      "codepoints": ["U+0936","U+093E"],
      "atomic_varna_indices": [0,1]          // slice into atomic_varnas
    }
    // ...
  ],
  "atomic_varnas": [                         // ORDERED, LOSSLESS phonological record
    {
      "index": 0,
      "unit": "ś",                           // canonical varṇa id (IAST key)
      "devanagari": "श",
      "type": "consonant",                   // consonant | vowel | anusvara | visarga | nasalization | marker | unsupported
      "origin": "consonant",                 // see origin vocabulary §3
      "aspirated": false,                    // consonants only; else null
      "vowel_length": null,                  // vowels only: short | long | null
      "inherent_inserted": false,            // true iff this vowel is an R3 inherent-अ
      "orthographic_source": "base_letter",  // base_letter | independent_vowel | dependent_vowel_sign | inherent | virama_terminated | conjunct_constituent | combining_mark
      "position": "onset",                   // onset | medial | final  (word-level)
      "source_akshara_index": 0
    }
    // ...
  ],
  "inherent_vowel_insertions": { "count": 0, "atomic_indices": [] },
  "multiplicity": {                          // convenience mirror; never used to dedup
    "varna_counts": { "ś": 1, "ā": 1, "n": 1, "t": 1, "i": 1 },
    "geminations": []                        // adjacent identical/related-cluster runs, recorded not collapsed
  },
  "derived_noncanonical": {                  // OPTIONAL, clearly NON-canonical; never replaces the record
    "resolved_pronunciation_candidate": null // e.g. anusvāra→homorganic nasal; §7
  },
  "warnings": [],                            // R10 unresolved/unsupported code points, with class + code point
  "parser_spec_version": "PARSER_SPEC_v1"
}
```

- **The akṣara layer is not decorative** — it *is* the source's pronounceable/syllabic grouping and is a canonical
  output.
- **The atomic-varṇa layer is not the composition rule** — it is the lossless record from which later, separately
  pre-registered composition hypotheses may be tested. This spec defines the *record*, not the *composition*.

---

## 3. Deterministic rules (R1–R12)

The parser is a **total function**: every input code point is either routed to an emitted unit or recorded as a
warning; nothing is silently dropped. Single left-to-right pass; no randomness; no locale dependence; byte-stable
output for identical normalized input.

**R1 — Normalization.** Apply Unicode **NFC**. Record `normalization.changed`. NFC is pinned; no other
transformation (no case, no transliteration, no reordering) occurs at this step.

**R2 — Akṣara segmentation (orthographic).** Scan left→right, greedily forming orthographic clusters:
- an **independent vowel** (optionally followed by anusvāra/candrabindu/visarga) is one akṣara; or
- a **base consonant**, plus any number of *(virāma + consonant)* continuations, plus an optional trailing
  dependent vowel sign, plus optional anusvāra/candrabindu/visarga, is one akṣara.
- A word-medial virāma-terminated consonant that ligates **rightward** groups with the **following** consonant
  (orthographic ligature), e.g. `न्` + `ति` → akṣara `न्ति`. **This is orthographic grouping and may differ from
  phonological syllabification** (see U1).

**R3 — Atomic expansion (within each akṣara), left→right:**
- **Independent vowel** → one vowel varṇa (`origin=independent_vowel`).
- **Consonant** → emit the consonant varṇa, then decide its vowel:
  - followed by **virāma** → **no vowel** (`origin=virama_terminated`; it is a `conjunct_constituent` if another
    consonant follows in the same akṣara);
  - else followed by a **dependent vowel sign** → emit that vowel varṇa (`origin=dependent_vowel_sign`);
  - else → **insert inherent अ** (`origin=inherent_a`, `inherent_inserted=true`).
- **Anusvāra ं** → varṇa `ṃ` (`type=anusvara`), positioned after the vowel it follows.
- **Visarga ः** → varṇa `ḥ` (`type=visarga`).
- **Candrabindu ँ** → varṇa `m̐` (`type=nasalization`), kept **distinct** from anusvāra (see U2).

**R4 — Aspirate integrity.** The aspirated graphemes **ख घ छ झ ठ ढ थ ध फ भ** are **single** phonological varṇas.
Never split into unaspirated-stop + `ह`. `aspirated=true` on the emitted consonant.

**R5 — Conjunct rule.** Inside a conjunct, constituents joined by virāma emit as consonants **in order** with **no
inherent अ between them**. The **final** constituent follows R3's vowel logic (dependent sign, virāma, or inherent
अ if the orthography licenses one). The akṣara layer keeps the **whole** conjunct; the atomic layer lists the
**ordered constituents**.

**R6 — Vowel identity.** Independent vowels and dependent vowel signs map to the **same canonical vowel identity**;
the orthographic origin (`independent_vowel` vs `dependent_vowel_sign` vs `inherent`) is recorded, and
`vowel_length` (short/long) is recorded. Canonical vowels: **अ आ इ ई उ ऊ ऋ ॠ ऌ ए ऐ ओ औ** (and their signs).

**R7 — Anusvāra / visarga canonical preservation.** Both are preserved as their own canonical atomic units. Any
homorganic-nasal or sandhi resolution is emitted **only** in `derived_noncanonical` and **never** alters the
canonical record (§7, §8).

**R8 — No sandhi.** The parser decomposes the **attested surface** form only. It never reverses or reconstructs
sandhi. Surface-vs-underlying comparison is a separate, pre-registered study, not parser behavior (Decision 10).

**R9 — Order & multiplicity.** Append-only emission. **Never deduplicate.** Preserve phoneme order, repeated
phonemes, repeated vowels, gemination, and per-unit `position` (onset = first atomic of the word, final = last,
else medial). `geminations` records adjacent identical/related-cluster runs **without collapsing them**.

**R10 — Unresolved / unsupported forms.** Route each to an explicit `warnings` entry `{class, codepoint, action}`
and retain it; never silently drop. Deterministic policy per class:

| class | code points | canonical action |
|---|---|---|
| candrabindu | ँ U+0901 | emit `nasalization` unit (R3); no warning |
| avagraha | ऽ U+093D | **no varṇa emitted** (elision marker); `marker` unit + warning `avagraha_elision` |
| jihvāmūlīya / upadhmānīya | ᳵ U+1CF5 / ᳶ U+1CF6 | emit `visarga`-class allophone unit + warning `visarga_allophone` |
| Vedic accent marks | udātta U+0951, anudātta U+0952, svarita, etc. | **suprasegmental**: record on the bearing varṇa's metadata, emit **no** separate varṇa + warning `vedic_accent_recorded` |
| daṇḍa / punctuation | । U+0964, ॥ U+0965 | boundary; emit no varṇa + warning `punctuation_boundary` |
| numerals | ० U+0966 – ९ U+096F | emit no varṇa + warning `numeral_unsupported` |
| nukta / non-classical | ़ U+093C, क़ ख़ ग़ ज़ ड़ ढ़ फ़ … | **`unsupported` unit** (retain base+nukta raw) + warning `non_classical_nukta`; **do not** silently map to a classical consonant |
| any other unassigned code point | — | `unsupported` unit + warning `unrecognized_codepoint` |

**R11 — Determinism guarantees.** Single pass; NFC pinned; no RNG; no locale/collation dependence; rules R2–R10 are
**mutually exclusive and exhaustive** over the classical Devanāgarī block, so the function is total and its output
is byte-stable for identical normalized input.

**R12 — Parser neutrality.** The parser must not: assign binding/liberating meaning; choose polarity; aggregate
facets; score words; apply the unordered bag-of-varṇas mechanism; infer semantic correctness; or repair/insert any
missing vowel *meaning*. (Inserting an inherent **अ** under R3 is a *phonological* fact, not a meaning.)

---

## 4. Worked examples

Atomic sequences below are hand-derived from the confirmed NFC code points; a conformant parser must reproduce them
byte-for-byte. IAST is metadata. `⟨…⟩` marks an inherent-अ insertion.

### 4.1 कमल — inherent vowels (`kamala`)
- code points: `क`(U+0915) `म`(U+092E) `ल`(U+0932) — three bare consonants, no signs, no virāma.
- **akṣaras:** `[क, म, ल]` → `ka · ma · la`
- **atomic varṇas:** `[क, ⟨अ⟩, म, ⟨अ⟩, ल, ⟨अ⟩]` = `k, a, m, a, l, a`
- **inherent insertions:** 3 (after क, म, ल). No schwa deletion.

### 4.2 शान्ति — long vowel + conjunct (`śānti`)
- code points: `श` `ा`(AA sign) `न` `्`(virāma) `त` `ि`(I sign).
- **akṣaras:** `[शा, न्ति]` → `śā · nti` (न् ligates rightward with ति — orthographic; phonological syllable is
  `śān·ti`, see U1).
- **atomic varṇas:** `[श, आ, न, त, इ]` = `ś, ā, n, t, i`
- **inherent insertions:** 0 (शा has explicit ā; न् is virāma-terminated; ति has explicit i).

### 4.3 शक्ति — conjunct (`śakti`)
- code points: `श` `क` `्` `त` `ि`.
- **akṣaras:** `[श, क्ति]` → `śa · kti`
- **atomic varṇas:** `[श, ⟨अ⟩, क, त, इ]` = `ś, a, k, t, i`
- **inherent insertions:** 1 (श). No अ between क and त (virāma-joined).

### 4.4 दुःख — visarga + aspirate (`duḥkha`)
- code points: `द` `ु`(U sign) `ः`(visarga) `ख`(aspirate).
- **akṣaras:** `[दुः, ख]` → `duḥ · kha`
- **atomic varṇas:** `[द, उ, ः, ख, ⟨अ⟩]` = `d, u, ḥ, kh, a`
- **notes:** `ख` is a **single** aspirate varṇa (`kh`), not `k+h` (R4). Visarga `ḥ` is its own canonical unit (R7);
  no allophonic change (R8). Inherent insertions: 1 (ख).

### 4.5 संस्कृत — anusvāra + conjuncts + vocalic ṛ (`saṃskṛta`)
- code points: `स` `ं`(anusvāra) `स` `्` `क` `ृ`(vocalic-R sign) `त`.
- **akṣaras:** `[सं, स्कृ, त]` → `saṃ · skṛ · ta`
- **atomic varṇas:** `[स, ⟨अ⟩, ं, स, क, ऋ, त, ⟨अ⟩]` = `s, a, ṃ, s, k, ṛ, t, a`
- **notes:** anusvāra follows the first स's inherent अ (R3). `ृ` maps to canonical vowel `ऋ` (R6). Inherent
  insertions: 2 (first स, त). The two `स` are **both** kept (R9, no dedup).

### 4.6 बुद्धि — gemination/conjunct structure (`buddhi`)
- code points: `ब` `ु` `द` `्` `ध`(aspirate) `ि`.
- **akṣaras:** `[बु, द्धि]` → `bu · ddhi`
- **atomic varṇas:** `[ब, उ, द, ध, इ]` = `b, u, d, dh, i`
- **notes:** the `द्ध` cluster is `d` + `dh` — **two adjacent dental stops** (second aspirated), preserved in order,
  not collapsed to a single "geminate" (R4, R9). Inherent insertions: 0.

### 4.7 क्षमा — conjunct + long vowel (`kṣamā`)
- code points: `क` `्` `ष` `म` `ा`.
- **akṣaras:** `[क्ष, मा]` → `kṣa · mā`
- **atomic varṇas:** `[क, ष, ⟨अ⟩, म, आ]` = `k, ṣ, a, m, ā`
- **notes:** `क्ष` → akṣara kept whole; atomic constituents `[क, ष]` in order (R5). **No अ between क and ष**
  (virāma-joined); `ष` takes inherent अ because the surface orthography licenses it (no following virāma/sign
  before म). Inherent insertions: 1 (ष).

### 4.8 अग्नि — independent-vowel-initial + conjunct (`agni`)
- code points: `अ`(independent A) `ग` `्` `न` `ि`.
- **akṣaras:** `[अ, ग्नि]` → `a · gni`
- **atomic varṇas:** `[अ, ग, न, इ]` = `a, g, n, i`
- **notes:** leading `अ` is an **independent** vowel (`origin=independent_vowel`), distinct from an inherent अ
  (`inherent_inserted=false`). Inherent insertions: 0.

**Cross-example coverage:** inherent अ (4.1, 4.3, 4.4, 4.5, 4.7); long vowel (4.2, 4.7); vocalic ṛ (4.5);
conjuncts (4.2, 4.3, 4.5, 4.6, 4.7); aspirate-as-unit (4.4, 4.6); anusvāra (4.5); visarga (4.4);
independent-vowel onset (4.8); no-dedup with repeated स (4.5).

---

## 5. Determinism validation (internal)

- **Total function:** R2–R10 partition the classical Devanāgarī block; every code point is emitted or warned. No
  reachable "silent drop" path.
- **Single pass, order-preserving:** emission is append-only; `position` is a pure function of index; no reordering.
- **NFC pinned:** the only normalization is NFC (R1); output is a pure function of the NFC input.
- **No nondeterminism:** no RNG, no clock, no locale/collation, no set/dict-iteration-order dependence in the
  specified output (all sequences are ordered lists).
- **Hand-reproducibility:** all eight §4 records are fully determined by the rules; a conformant implementation must
  match them byte-for-byte. These serve as the acceptance fixtures.
- **Neutrality invariant:** no rule reads or writes polarity/meaning/score; R12 is checkable by absence.

---

## 6. Remaining unresolved parser decisions (documented, non-blocking)

These do **not** block a deterministic implementation — each has a **specified default** — but the *theory* must
eventually pin them, and they are recorded so the choice is explicit rather than accidental:

- **U1 — akṣara grouping of word-medial codas.** Default = **orthographic** ligature grouping (शान्ति → `[शा,
  न्ति]`). This diverges from phonological syllabification (`śān·ti`). If the composition hypothesis wants
  phonological syllables, a second syllabifier layer is needed; the atomic-varṇa layer is unaffected either way.
- **U2 — candrabindu vs anusvāra.** Default = kept **distinct** (`nasalization` vs `anusvara`). If the theory
  treats them identically, that is a downstream merge, not a parser change.
- **U3 — anusvāra resolution.** Default = canonical `ṃ` preserved; homorganic-nasal resolution only in
  `derived_noncanonical`. Which the composition study consumes is a downstream, pre-registered choice.
- **U4 — inherent-अ visibility to composition.** The record flags `inherent_inserted`; whether a later composition
  rule counts inherent अ, explicit अ, or neither is a downstream decision (the parser only records it).
- **U5 — akṣara vs atomic as the scoring unit.** Deliberately **both** are emitted; the source does not decide.
  Picking the composition unit is the later empirical study, not this spec.

None of U1–U5 introduces nondeterminism; they are choices *above* the parser.

---

## 7. Anusvāra — canonical vs derived (Decision 7)

- Canonical record: `ं` → atomic unit `ṃ` (`type=anusvara`), always.
- The parser **may** additionally emit `derived_noncanonical.resolved_pronunciation_candidate` (e.g. the homorganic
  nasal implied by the following consonant), but this field is explicitly non-canonical and **must not** replace or
  alter the surface decomposition. Rationale: resolution depends on phonological tradition/recitation/context.

## 8. Visarga (Decision 8)

- `ः` → atomic unit `ḥ` (`type=visarga`), always. No context-dependent allophonic or sandhi transformation in the
  canonical parser (jihvāmūlīya/upadhmānīya, if literally present in the input, are handled by R10, not synthesized).

---

## 9. Scope guardrails (Decision 12, restated)

This artifact is a **specification**. It does not: write parser code; alter `frozen/varna_polarity_table_v3.json`;
add any vowel/anusvāra/visarga **meaning**; run any example through scoring; modify Track G; or start a Sanskrit
word experiment. Emitting phonological vowels here does **not** lift the provenance register's
`BLOCKED_BY_SOURCE_CONTRADICTIONS` verdict: the vowel **poles** remain `MISSING` and no order-preserving composition
rule exists yet. Both remain prerequisites for any test and must go through the same blinding/pre-registration
discipline as everything else.

---

## 10. Readiness verdict

**`READY_FOR_PARSER_IMPLEMENTATION` (with documented defaults U1–U5).** The canonical schema (§2), the deterministic
rules R1–R12 (§3), the R10 code-point-class policy, and the eight acceptance fixtures (§4) fully determine a total,
byte-stable parser over classical Devanāgarī. The only open items (U1–U5) are theory-side composition choices with
specified engineering defaults and do **not** block implementation.

**Single recommended next action:** implement the parser to this spec **plus a test suite that pins the eight §4
fixtures byte-for-byte** — as Stage-1 input infrastructure only — before, and separately from, any vowel-pole
authoring or composition-rule pre-registration.
