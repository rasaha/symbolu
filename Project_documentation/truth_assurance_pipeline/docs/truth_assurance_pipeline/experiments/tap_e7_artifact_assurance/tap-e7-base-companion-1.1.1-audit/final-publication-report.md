# TAP-E7-BASE Companion Package v1.1.1 — Final Publication Report

## Package verdict: **1 — independently verified publication-complete and suitable for clean-room Implementation B**
## Implementation A verdict: **1 — passes all mandatory TAP-E7-BASE v1.1.1 fixtures**
## Maturity: **Ready to commission clean-room Implementation B**

v1.1.1 is a corpus-oracle PATCH that corrects exactly the five defects Independent Implementation A
exposed in v1.1.0. It changes **no** frozen runtime semantics and **no** runtime resource.

## Scope of change (19 files, all non-runtime)
| Change class | Count | Files |
| --- | --- | --- |
| FIXTURE_INPUT_CORRECTION | 5 | corpus/{DT03,SEC05,UC07,UC08,UC09}.json |
| DERIVATION_CORRECTION | 5 | derivations/{DT03,SEC05,UC07,UC08,UC09}.json |
| EXPECTED_RESULT_CORRECTION | 4 | expected/{SEC05,UC07,UC08,UC09}.expected.json (DT03 expected was already ASSURED/exact — byte-identical) |
| MANIFEST_UPDATE | 2 | manifest/{corpus,release}-manifest.json |
| HASH_UPDATE | 3 | hashes/{corpus-root,package-root,sha256sums} |
| **RUNTIME_RESOURCE_CHANGE** | **0** | — |

## Adjudications (see defect-adjudications.json)
- **DT03, UC08, UC09** — fixture-input defects (verdict A). Impl A's byte-faithful result was correct;
  the fixtures asserted matches the bytes did not support. Corrected via complete propositions and
  record-supplied accented aliases (NFC pairs), **without** introducing diacritic folding.
- **UC07, SEC05** — method-histogram defects (verdict D). The earliest terminal correspondence stage
  is `exact`, not `structured`; corrected. Outcome/findings/projection unchanged.
- No case was an Implementation A defect.

## Genuine roots (independently recomputed, full hex)
```
resource_root      a6ab878888a5cc98e660fc18b9d8da603cdf999c9989b2a5b1b40acfdc10d175   (== v1.1.0)
schema_root        d1f1a95c70e75b1f58453fef43022a99ef349fde4f834e4286cbff629783bcc8   (== v1.1.0)
config_fingerprint d01e466e5bb57d6a1a00d42b01fb9943d9208e6e39b6a90413a0b247b0416734   (== v1.1.0, == v1.0.0)
corpus_root        f8c83c91c9d5db15e8608ed414784c5c83d0783838ddd48c527c97637130b614   (changed)
package_root       fa22021a83d7c784021c5ac617b55d8b3d27c892dc8d94563cfc38f35a61133e   (changed)
audit_root         e9d9ad6a80a86794921614f1541a77c108aee1f53adae66c58d159cf72fe1c3c
```
Runtime `config_fingerprint` and both outcome-affecting roots are **byte-identical** to v1.1.0 — the
patch is provably corpus-only.

## Implementation A re-execution (unmodified, blind, against v1.1.1)
- Config fingerprint recomputed → MATCH. Blind boundary intact (0 expected/derivation reads).
- **Mandatory 86/86 EXACT_PASS.** ALLOWED_IMPLEMENTATION_METADATA_DIFFERENCE 0, IMPLEMENTATION_DEFECT 0,
  PACKAGE_DEFECT 0, SPECIFICATION_AMBIGUITY 0.
- Informative INF01–04: abstained (engine-level), correctly non-gate — **not** promoted.
- Deterministic replay identical; package left byte-immutable (composite `39672e11…` before == after).

## Independent re-audit (fresh tools, no builder import) — 0 failures
Inventory, all manifest/fixture/expected/derivation digests, 5 roots, §8.1 outcomes, taxonomy/polarity,
count invariants, projection hashes, placeholder scan, mandatory mapping — all pass.
- **Correspondence-stage precedence audit**: 86/86 — every stored method equals the earliest-qualifying
  stage (cross-checked against Impl A's independent staging).
- **Unicode-equivalence audit**: NFC precomposed/decomposed equivalence, accented-vs-unaccented
  (now via record alias), confusable-only, invisible strip-and-flag, bidi reject, and space-normalize
  are each classified distinctly; the corpus never conflates NFC / skeleton / alias / diacritic-folding.

## Tests (Implementation A vs v1.1.1)
Unit 32/32; Metamorphic 8 pass + 4 N/A_ENGINE; Security 8/8; Privacy 3/3. 0 failures.

## Final scores (independent)
| Dimension | /10 |
| --- | --- |
| Corpus oracle correctness | 10 |
| Unicode normalization precision | 10 |
| Correspondence-stage precision | 10 |
| Expected-result derivability | 10 |
| Hash/package reproducibility | 10 |
| Implementation A conformance | 10 |
| Specification implementability | 8 (fingerprint/Π recipes still under-documented — recommended pre-B publish) |
| Validator independence | 9 |
| Interoperability enablement | 9 |
| Normative precision | 9 |
| Overall publication readiness | 10 |

## Immutability & history
v1.0.0, v1.1.0, and Implementation A remain byte-unchanged. Stable promotion is **not** claimed: it
still requires a genuinely separate Implementation B to pass this corrected mandatory corpus.
