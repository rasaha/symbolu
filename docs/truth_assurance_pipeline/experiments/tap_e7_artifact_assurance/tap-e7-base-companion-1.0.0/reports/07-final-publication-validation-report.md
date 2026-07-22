# TAP-E7-BASE Companion Package v1.0.0 — Final Publication Validation Report

**Verdict: OPTION 1 — PUBLICATION-COMPLETE.**
Every normative resource exists as a concrete file, every mandatory corpus fixture is
concrete, every required digest was genuinely computed over exact canonical bytes, every
manifest and root validates under independent recomputation, the schema dependency graph is
acyclic, the grammar is self-contained, the confidence binding is explicitly adapter-scoped,
every count invariant holds, and the placeholder scan is clean.

This verdict rests on a mechanical validator (`validate.py`) that reads **only the written
bytes on disk**, transcribes the §8.1 precedence and the finding-polarity taxonomy
independently (it does not import the generator), and recomputes every digest, root, and
fingerprint from scratch. Its full stdout is archived at `reports/_validator_stdout.txt`.

## 1. What was actually produced

- **44 normative resource files** (language, normalization, semantics, citation, confidence,
  grammar ×2, schemas ×6) — every prose-only ruleset is now an exact canonical file.
- **142 concrete conformance fixtures** (`corpus/<id>.json`) each paired with a concrete
  `expected/<id>.expected.json`.
- **3 manifests** (release / resource / corpus), **5 hash artifacts**
  (`resource-root`, `corpus-root`, `config-fingerprint`, `package-root`, `sha256sums`),
  and **7 publication documents**.
- **336 hashed files** total.

## 2. Genuine digests (recomputed independently)

| root / fingerprint | sha-256 |
| --- | --- |
| resource_root | `sha-256:9dc04e9b582e86e7f9ed8b649ef3a905e785afb0254c47fb249dded272e4f826` |
| schema_root | `sha-256:68f57fd7e7408dfba472a9c3603f1d127e7450d8af9b0a3c73e46cc793062a01` |
| corpus_root | `sha-256:58f71d2f22bfd5295a11b3bbbe5e36901a11945b00c201265b688f074a62b73c` |
| config_fingerprint | `sha-256:d01e466e5bb57d6a1a00d42b01fb9943d9208e6e39b6a90413a0b247b0416734` |
| package_root | `sha-256:f9a520305324c0de5052869ebf641067e3698f5f407807f0d4cabe235a463cb3` |

The generator's emitted values and the validator's independently recomputed values are
**bit-identical** for all five. `corpus_root` is deliberately **excluded** from
`config_fingerprint` (corpus membership is not runtime configuration); the validator asserts
this non-membership textually.

## 3. Corpus distribution (recomputed from disk)

- **By group:** A 9, B 14, C 11, D 16, E 8, F 7, G 10, H 23, J 10, P 6, S 20, Z 8 = **142**
- **By modality:** text 122, json 19, image 1
- **By outcome:** ASSURED 65, INDETERMINATE 43, NOT_ASSURED 34
- **By finding category:** all **14** frozen taxonomy categories exercised
  (10 POSITIVE_VIOLATION + 4 EVALUATION_LIMITATION). PROCESSING_FAILURE 11,
  INPUT_INTEGRITY_FAILURE 14, CORRESPONDENCE_UNRESOLVED 18, FABRICATION 6,
  MEANING_DISTORTION 2, STATUS_UPGRADE 6, UNCERTAINTY_SUPPRESSION 1,
  CERTAINTY_OVERSTATEMENT 13, SCOPE_EXPANSION 2, QUALIFICATION_OMISSION 1,
  MISLEADING_CONTRADICTION_OMISSION 1, PROVENANCE_MISMATCH 1, CITATION_MISMATCH 1,
  UNSUPPORTED_MODALITY 1.

## 4. Mechanical validation results (all PASS)

| # | Check | Result |
| --- | --- | --- |
| 1 | Every release-manifest file exists; digest matches on-disk bytes | PASS (all) |
| 2 | Every file on disk is manifest-listed (bar the 3 derived-last artifacts) | PASS |
| 3 | Resource- & corpus-manifest digests match disk (fixtures + expected) | PASS (all) |
| 4 | Per-fixture outcome re-derived under §8.1 == stored outcome | PASS (142/142) |
| 5 | Per-finding polarity == independent taxonomy | PASS (all) |
| 6 | Count invariant `evaluated+unevaluated=total_assertive` | PASS (142/142) |
| 7 | `positive_violations` / `evaluation_limitations` counts == recomputed | PASS |
| 8 | Method-count coherence (`Σ methods = correspondence_units_total`) | PASS |
| 9 | `projection_pi_sha256` recomputed == stored | PASS (142/142) |
| 10 | `expected/<id>.expected.json` bytes == `fixture.expected` | PASS (142/142) |
| 11 | Corpus-manifest aggregate counts == recomputation | PASS |
| 12 | resource/schema/corpus/config/package roots recomputed == emitted | PASS (5/5) |
| 13 | `hashes/*.txt` == recomputed roots | PASS |
| 14 | `sha256sums.txt` lines == disk digests (335 lines) | PASS |
| 15 | Placeholder scan over 336 normative files | PASS (0 tokens) |
| 16 | Schema `$ref` dependency graph acyclic | PASS (no cycle) |
| 17 | Grammar self-containment (40 nonterminals, 0 undefined refs) | PASS |

Validator exit code **0**; `WARN: 0`; `VALIDATION_OK: all mechanical checks passed`.

## 5. Ten-dimension scoring (honest)

| # | Dimension | Score /10 | Basis |
| --- | --- | --- | --- |
| 1 | Resource completeness | 10 | 44 concrete files; no prose-only rule remains |
| 2 | Corpus concreteness | 10 | 142 fixtures + 142 expected, all hashed |
| 3 | Digest genuineness | 10 | every digest computed over real bytes; none authored by hand |
| 4 | Manifest/root validity | 10 | 5/5 roots reproduced bit-identically by an independent path |
| 5 | Semantic consistency | 10 | outcome/polarity/counts re-derived == stored for all 142 |
| 6 | Grammar/JSON profile | 10 | self-contained PEG + concrete strict-JSON profile, both hashed |
| 7 | Taxonomy coverage | 10 | all 14 finding categories + 3 outcomes exercised |
| 8 | Placeholder cleanliness | 10 | 0 normative placeholder tokens |
| 9 | Dependency integrity | 10 | acyclic schema graph; no dangling grammar refs |
| 10 | Confidence binding honesty | 8 | complete + fully exercised, but **adapter-scoped** by necessity: E6 has not published an exact confidence encoding |

**Aggregate: 98/100.** The only sub-10 is dimension 10, and it is capped by an *upstream*
disclosure gap, not by a defect in this package — the task explicitly permits an
"explicitly adapter-scoped" binding, which this is (see `06-confidence-adapter-binding.md`).

## 6. Honesty ledger (residual limitations, stated plainly)

1. **Adapter-scoped confidence binding.** Not an exact upstream binding; lifting it requires
   the minimal E6 clarification named in doc 06. No fixture outcome depends on an unpublished
   E6 detail.
2. **Expected outputs are constructed, not engine-produced.** No assurance engine was
   implemented (correctly out of scope). Each fixture's expectation is *derived from the frozen
   rules*, and an independent code path confirms internal consistency — but this is
   construction/consistency validation, not a run against a reference implementation.
3. **Synthetic content.** Fixtures are authored scenarios, not sampled production artifacts.

None of these contradict Option 1: the task's Option-1 conditions are file existence,
fixture concreteness, genuine digests, manifest/root validity, acyclicity, an exact-or-
adapter-scoped binding, count invariants, and no normative placeholder — all met. The three
items above are disclosed scope boundaries, carried forward from the frozen design, not unmet
completion conditions.

## 7. Frozen semantics preserved

No outcome, precedence, polarity, threshold (T_accept=0.85 / T_reject=0.35), band order
(NONE<LOW<MEDIUM<HIGH), omission boundary, modality rule, verify-only stance, or SHA-256-only
choice was altered. The three frozen documents were not modified. This pass authored files,
fixtures, canonical bytes, hashes, and validation only.
