# Full Concrete Conformance Corpus

- **corpus_id:** `tap-e7-base-corpus`  **version:** `1.0`
- **corpus_root:** `sha-256:58f71d2f22bfd5295a11b3bbbe5e36901a11945b00c201265b688f074a62b73c`
- **total fixtures:** 142  (each = one concrete `corpus/<id>.json` + one
  `expected/<id>.expected.json`, both hashed in `manifest/corpus-manifest.json`)

Every fixture's `outcome` is re-derived by the independent validator from its finding set
under the frozen §8.1 precedence (POSITIVE_VIOLATION → NOT_ASSURED; else EVALUATION_LIMITATION
→ INDETERMINATE; else ASSURED) and matches the stored value for all 142 fixtures;
every finding polarity, every count invariant
(`evaluated_assertive + unevaluated_assertive = total_assertive`), and every
`projection_pi_sha256` were recomputed and matched.

## By group
| group | fixtures |
| --- | --- |
| A | 9 |
| B | 14 |
| C | 11 |
| D | 16 |
| E | 8 |
| F | 7 |
| G | 10 |
| H | 23 |
| J | 10 |
| P | 6 |
| S | 20 |
| Z | 8 |

## By modality
| modality | fixtures |
| --- | --- |
| image | 1 |
| json | 19 |
| text | 122 |

## By outcome
| outcome | fixtures |
| --- | --- |
| ASSURED | 65 |
| INDETERMINATE | 43 |
| NOT_ASSURED | 34 |

## By finding category (all 14 taxonomy categories exercised)
| category | occurrences |
| --- | --- |
| CERTAINTY_OVERSTATEMENT | 13 |
| CITATION_MISMATCH | 1 |
| CORRESPONDENCE_UNRESOLVED | 18 |
| FABRICATION | 6 |
| INPUT_INTEGRITY_FAILURE | 14 |
| MEANING_DISTORTION | 2 |
| MISLEADING_CONTRADICTION_OMISSION | 1 |
| PROCESSING_FAILURE | 11 |
| PROVENANCE_MISMATCH | 1 |
| QUALIFICATION_OMISSION | 1 |
| SCOPE_EXPANSION | 2 |
| STATUS_UPGRADE | 6 |
| UNCERTAINTY_SUPPRESSION | 1 |
| UNSUPPORTED_MODALITY | 1 |

## By correspondence / companion method
| method | units |
| --- | --- |
| exact | 1 |
| explicit | 7 |
| lexical | 3 |
| no_match | 6 |
| structured | 77 |
| unresolved | 18 |

