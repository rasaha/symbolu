# B1 — Stage-1 Sanskrit Structural Parser — Freeze Record (docs-only)

**This is a docs-only freeze record.** It changes no parser code, tests, fixtures, schema, mappings, experiments,
or prior verdicts. It records a frozen implementation baseline of the **structural** Stage-1 parser.

## Frozen baseline

| field | value |
|---|---|
| implementation | `sanskrit_stage1_parser.py` |
| specification | `B1_STAGE1_SANSKRIT_PARSER_SPEC.md` |
| tests | `test_sanskrit_stage1_parser.py`, `test_sanskrit_stage1_parser_corrective.py` |
| golden fixtures | `stage1_golden/` (eight, byte-for-byte) |
| commit | **`a1988394`** |
| schema version | **1.1** |
| verdict | **`READY_TO_FREEZE_WITH_DOCUMENTED_NONBLOCKING_LIMITATIONS`** |

## Scope of this freeze — what IS frozen (structural only)

This freeze covers **only** the neutral structural decomposer:

1. Devanāgarī **normalization** (Unicode NFC), with faithful original-input echo and `normalization.changed`;
2. **orthographic akṣara segmentation** (explicit, not a generic grapheme-cluster library);
3. **ordered atomic-varṇa decomposition** (order and multiplicity preserved; no deduplication);
4. **inherent-vowel (अ) insertion** (no Hindi-style schwa deletion);
5. **aspirate and conjunct handling** (aspirates are single varṇas; conjuncts decompose to ordered constituents);
6. **anusvāra / visarga preservation** (canonical surface units; resolution only as a non-canonical derived field);
7. **join-control behavior** (ZWJ/ZWNJ transparent in conjuncts, never atomic, always warned);
8. **source reconstruction** (akṣara substrings reconstruct the NFC input exactly — lossless);
9. **deterministic structural metadata** (byte-stable serialization; `position` + authoritative `is_initial`/`is_final`);
10. **semantic-firewall independence** (stdlib-only; imports no varṇa polarity table, scoring module, Track-G
    evaluator, or English G2P utility; no meaning-bearing fields in output).

## Scope of this freeze — what is NOT validated or frozen

This freeze makes **no** claim about, and does **not** freeze:

- binding or liberating **meanings**;
- **polarity selection**;
- **vowel, anusvāra, visarga, or candrabindu meanings**;
- **word-level composition rules**;
- **semantic interpretation** of any parsed output;
- **Track-G claims** (unchanged and not reinterpreted);
- **native-Sanskrit hypothesis validity**.

Emitting a phonological vowel/mark is a **structural fact only** and attaches no meaning. Consistent with the
integration audit, the mapping table remains consonant-only; vowel/anusvāra/visarga/candrabindu meanings remain
unresolved and out of scope here.

## Accepted non-blocking limitations

These were identified by the re-freeze audit and are **accepted** as non-blocking for a structural freeze:

1. **`multiplicity.varna_counts` counts all emitted atomic units, including unsupported placeholders.**
   Phonological consumers must filter by atomic `type` (`consonant`/`vowel`/`anusvara`/`visarga`/`nasalization`)
   before computing varṇa statistics.
2. **ASCII whitespace has dedicated handling; some Unicode space characters (e.g. NBSP, U+00A0) do not.** Those
   remain retained as **warned unsupported units** rather than being treated as whitespace.
3. **`virama_before_independent_vowel` detection is guaranteed only for the directly adjacent malformed pattern.**
   An intervening combining mark (e.g. anusvāra/visarga) may prevent that specialized warning; the input remains
   deterministic and **lossless** in that case (other warnings may still fire).

**None of these limitations corrupts the canonical atomic sequence for valid classical Sanskrit input.** They
affect only a convenience mirror (1), exotic/pathological whitespace (2), and warning completeness on
doubly-malformed input (3).

## Guardrails

Docs-only. **Structure, not validated meaning.** No `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; no ontology /
semantic-truth / Sanskrit-privilege / generation-utility claim. Parser code, tests, fixtures, schema, mappings,
Track-G, and all prior verdicts are unchanged by this record.
