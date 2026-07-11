# B1 — Native Stage-1 Merged Lexicon (docs/data/code)

**Integration verdict: `NATIVE_STAGE1_MERGED_LEXICON_CREATED`. Readiness: `READY_FOR_NATIVE_WORD_MAPPING_REVIEW_WITH_PROVENANCE_LIMITS`.**
Built per the operator authority ruling. Authors **no** new meaning; the three source artifacts are **byte-unchanged**.
Structure, not validated meaning. No `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`. **Not** ready for confirmatory semantic testing.

## Artifact & source precedence

- **New artifact:** `frozen/varna_native_stage1_merged_v1.json` (built by `build_varna_native_stage1_merged.py`).
- **Consonants ← v3.1** (`varna_polarity_table_v3_1_metadata_refreeze.json`), copied **verbatim**. Consonant
  pole-content hash **equals** v3.1 (asserted mechanically).
- **Vowels + anusvāra (`am`) + visarga (`ah`) ← varṇa-lens** (`varna_lens/lexicon_authoritative_varna.json`), copied
  verbatim, marked `AUTHORED_PROVISIONAL` / `DEVELOPMENT_ONLY` / `NOT_EMPIRICALLY_VALIDATED`.
- **No lens consonant rows imported.** `sha`, `ssa`, `ha` come from v3.1; the rejected stale lens rows (sibilant
  swap; ha-night) are recorded in `conflict_notes`, not merged.
- **No `kṣa` producer** (parser decomposes क्ष → k + ṣ).
- Sources unmodified: v3 `d3ff8efd…`, v3.1 `9ac712a6…`, lens `81cbf55f…` (all asserted byte-identical).

## Merged inventory (51 rows)

| category | count | activation scope | source |
|---|---|---|---|
| consonants (producible) | 33 | `CONFIRMATORY_BACKBONE` | v3.1 |
| consonant `ḷ` (retroflex lateral) | 1 | `OUT_OF_SCOPE` | — (no v3.1 key) |
| vowels (a ā i ī u ū e ai o au) | 10 | `DEVELOPMENT_ONLY` | varṇa-lens |
| anusvāra `ṃ`→`am`, visarga `ḥ`→`ah` | 2 | `DEVELOPMENT_ONLY` | varṇa-lens |
| **missing** `ṛ ṝ l̥ l̥̄` + candrabindu `m̐` | 5 | `MISSING` | — |

Each row carries: `canonical_parser_unit, devanagari, iast, category, source_artifact, source_key,
binding_vritti, liberating_vritti, binding_pole_provenance, liberating_pole_provenance, activation_scope,
empirical_status_note, parser_reachable, aliases`.

## Provenance of vowel mappings (unchanged, honestly labelled)

The 10 vowels + `am`/`ah` are **`AUTHORED_PROVISIONAL`** on both poles (the lens vowel entries carry no
`source_quote`/`expanded_properties`, unlike the sourced consonants). Their `activation_scope` is
`DEVELOPMENT_ONLY` and `empirical_status_note` records **`NOT_EMPIRICALLY_VALIDATED`** with a direct reference to the
prior **`NO_SIGNAL`** results (`varna_lens/RESULTS_ACOUSTIC_SIGNAL.md` + `…_CORRECTED_LEXICON.md`) — **the rows are
retained, not deleted, and are NOT relabelled attested.**

## Corrected coverage (superseding audit)

`b1_stage1_native_merged_integration_audit.py` supersedes the prior `b1_stage1_mapping_integration_audit.py`
(**preserved** as historically correct relative to its v3.1-only source). Over the 110-word seed corpus (518
phonological tokens):

| coverage concept | token | word-full | includes authored vowels? |
|---|---|---|---|
| **`structurally_resolvable_coverage`** | **98.8%** | 94.5% | **yes** |
| **`confirmatory_eligible_coverage`** | **55.0%** | **0.0%** | no (consonant backbone only) |

**98.8% structural coverage is not a semantic-validation claim.** The confirmatory-eligible figure excludes the
authored-provisional vowels/markers; because every word contains vowels, **no word is fully confirmatory-eligible**
(word-full confirmatory = 0.0%). Remaining missing units: `ṛ ṝ l̥ l̥̄` + candrabindu.

## Corrections vs the prior audit

- Common vowels (a ā i ī u ū e ai o au) → **EXISTING** (were reported MISSING because the prior audit read v3.1 only).
- Anusvāra / visarga → **EXISTING** (`am` / `ah`).
- Still missing: the four vocalic sonorants + candrabindu.
- Consonant identity → from v3.1; **no wholesale authority** granted to the stale lens consonant portion.

## Contradictions prevented

- The lens **sibilant swap** (`ssa`=Kāma/Tamoguṇa) and **`ha`=Avidyā/Rātri/Night** were **not** imported; v3.1's
  primary-text-corrected `sha`/`ssa`/`ha` are kept. Recorded in `conflict_notes`.
- No averaging/merging of conflicting mappings; consonant pole content proven identical to v3.1.

## Validation

`test_varna_native_stage1_merged.py` (11) asserts: consonant pole content == v3.1; `sha`/`ssa`/`ha` from v3.1; 10
vowels resolve; `ṃ→am`/`ḥ→ah`; no unit collapse; vowel length separate; missing units explicit; no new meaning
authored; sources byte-identical; deterministic; two distinct coverage concepts with structural > confirmatory. All
pass.

## Single recommended next action

Inspect **parsed Sanskrit words against the merged mappings** and review the resulting **existing**
binding/liberating vṛtti sequences (development-grade, provenance-limited) — **not** to invent additional vowel
mappings, and **not** confirmatory semantic testing. Any positive-signal claim would first require raising the
vowel provenance above `AUTHORED_PROVISIONAL` and re-running a pre-registered signal test (given the prior `NO_SIGNAL`).
