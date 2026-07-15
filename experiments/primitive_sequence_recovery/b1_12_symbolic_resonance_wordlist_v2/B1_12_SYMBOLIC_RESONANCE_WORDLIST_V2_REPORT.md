# B1.12 Bare-Word Symbolic Resonance — V2 Fresh Word List (FROZEN)

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`

Precommitted under the frozen V2 preregistration `VARNA_SYMBOLIC_RESONANCE_PREREG_V2.md`
(SHA-256 `831e48ec…`) and its freeze record `B1_12_V2_PREREG_FREEZE.md`. **No scoring performed; no model executed.**

- **N = 20**, 4 per category (afflictive, virtue_calm, concrete_object, animal_body_living, natural_action_abstract).
- **Word-list SHA-256:** `7a558008a22151a48f7770790bbfb01cdef190b64d3ae6feb8677b0b360457b4`
- **Frozen inputs:** parser `d885391f…`, mapping v3 `65116f37…` (both hash-verified before selection).

## Included words

| Category | Words (IAST) |
|---|---|
| afflictive | asūyā, bhrama, cintā, kārpaṇya |
| virtue_calm | akrodha, audārya, dama, dhṛti |
| concrete_object | cāpa, darpaṇa, kuṇḍala, mukura |
| animal_body_living | jaṅghā, kapāla, kūrma, lalāṭa |
| natural_action_abstract | chāyā, dhvani, pavana, pralaya |

## Audits (all passed)

- **Contamination:** every word is `FRESH_UNINSPECTED` against a repo-wide index of **269** previously-seen IAST
  tokens (all prior B1.12 symbolic-resonance / affliction / resolution / feature-lift / dev artifacts, including the
  v1 BSR 20-word list). **Overlap with the v1 BSR list = ∅.** No word from any previous B1.12 study is reused.
- **Parser coverage:** every word parses with **coverage = 100%** (every consonant occurrence maps to a
  CONFIRMATORY_BACKBONE unit with a binding_vṛtti), ≥ 2 mapped consonants each, no parser warnings. Coverage was
  computed via mapped-unit **set membership only** — mapping gloss text was **not** read during selection (firewall
  preserved).
- **Deterministic selection:** attested-lexeme eligibility → FRESH requirement → parser/mapping coverage → category
  quota (4) → IAST Unicode-codepoint ascending → first eligible per category. Candidate pool, per-word coverage,
  contamination status, and exclusion reasons are recorded in `candidate_source_list.json`,
  `parser_coverage_audit.json`, `contamination_audit.json`, and `excluded_candidates.json`.

## Discipline

Fresh, category-balanced, attested Sanskrit; the v1 20 words are not reused. The frozen mappings, parser, glosses,
thresholds, verdict bands, and the independent two-model V2 design are unchanged. Words were selected without
consulting varṇa mapping glosses; glosses are read only at scoring time (a separate, not-yet-run phase).
