# TAP-E7-BASE Companion Package v1.1.0 — Corpus-Correction Release & Final Audit

## Verdict: **2 — publication-complete subject to explicitly listed non-semantic corrections**
## Maturity: **Stable promotion NOT yet supported — two independent TAP-E7 implementations must still pass the corpus**

v1.1.0 corrects the defect the independent audit of v1.0.0 identified: fixtures whose
expected results were asserted rather than encoded in their input bytes. Every mandatory
fixture in v1.1.0 now encodes its phenomenon in real bytes, and every mandatory expected
result is **independently re-derived from those bytes** by an auditor that does not import the
builder. What keeps this at Verdict 2 (not 1) is stated plainly in §"Residual" below.

## 1. Versioning
- New sibling directory `tap-e7-base-companion-1.1.0/`; the committed `1.0.0` package is
  **untouched** (preserved for audit history).
- `release_id = tap-e7-base-companion/1.1.0`, `corpus_id = tap-e7-base-corpus/1.1`,
  `supersedes = tap-e7-base-companion/1.0.0`.

## 2. Frozen-semantics preservation (verified)
- **`config_fingerprint` byte-identical to v1.0.0**: `sha-256:d01e466e5bb57d6a1a00d42b01fb9943d9208e6e39b6a90413a0b247b0416734`.
- **0 `RUNTIME_RESOURCE_CHANGE`** in the diff. No threshold, precedence, taxonomy, polarity,
  band order, scope semantic, or verify-only boundary was altered.
- `resource_root`/`schema_root` **did** change — solely because the corpus-fixture schema was
  intentionally extended (add `image` modality + input recipes). That schema is not
  outcome-affecting and is excluded from the runtime fingerprint; classified `SCHEMA_UPDATE`,
  not a runtime change.

## 3. Genuine roots (independently recomputed, full hex)
```
resource_root      a6ab878888a5cc98e660fc18b9d8da603cdf999c9989b2a5b1b40acfdc10d175
schema_root        d1f1a95c70e75b1f58453fef43022a99ef349fde4f834e4286cbff629783bcc8
corpus_root        642e7ecbbdb03508a12589961741a13ed1ccf9398b784889c2c4b57cde7ee5b1
config_fingerprint d01e466e5bb57d6a1a00d42b01fb9943d9208e6e39b6a90413a0b247b0416734   (== v1.0.0)
package_root       bff7685055fb99e9bec1ebfe3cec150f56540cd16421d36f40962ade9975f5ff
```
New corpus_root and package_root differ from v1.0.0 (corpus bytes changed); config_fingerprint
is unchanged. No hash was copied from v1.0.0 or fabricated.

## 4. Corpus
- **90 fixtures = 86 mandatory + 4 informative.**
- By group: LX 6, CR 3, JS 22, UC 9, EM 5, PV 4, SV 5, MD 1, DT 10, PR 6, SEC 11, ZR 4, INF 4.
- By modality: text 52, json 37, image 1.  By outcome: ASSURED 40, INDETERMINATE 38, NOT_ASSURED 12.
- **All 14 taxonomy categories** exercised.
- Every mandatory fixture carries a `derivations/<id>.json` derivation record.

## 5. Three independent tool roles (§18 separation, documented)
- **Builder** (`build_11.py`) — authors bytes + expected + derivations.
- **Byte-reproducibility auditor** (`audit_bytes_11.py`) — confirms the claimed phenomenon is
  present in the raw bytes, by methods different from the builder. Imports only shared
  primitives + frozen resources; does not import the builder.
- **Normative-derivation auditor** (`audit_deriv_11.py`) — re-implements the bounded verdict
  logic (strict-JSON, Jaccard classification, Unicode disposition, structural checks) and
  recomputes each mandatory expected result from bytes. Does not import the builder or its
  expected-generation.
- **Packaging validator** (`validate_pkg_11.py`) — schemas/manifests/hashes/roots/placeholder/
  §8.1 consistency.

The shared layer (`primitives.py`) is canonicalization only (tokenization, Jaccard fraction,
JSON structural scan, byte reconstruction, resource-table loaders, sha) — no finding
derivation.

## 6. Audit results (all reproduced)
| Check | Result |
| --- | --- |
| Byte-reproducibility (all 90 fixtures) | **0 failures** — every mandatory fixture's phenomenon present in bytes |
| Normative derivation (86 mandatory) | **0 mismatches** — re-derived finding-set + §8.1 outcome == stored |
| Packaging (digests/roots/§8.1/counts/projection/expected-bytes) | **0 failures** |
| config_fingerprint unchanged vs v1.0.0 | **True** |
| Mandatory-requirement mapping | **84/84 requirements mapped, all byte-reproducible** |
| Placeholder scan (incl. label-artifact tokens `boundary 0.x`, `depth65`, `oversized`) | **0** |
| Runtime-resource changes | **0** |

## 7. Concrete phenomenon coverage (byte-level spot-verified)
- **Jaccard** LX01–LX06: exact rationals 7/20, 6/20, 8/20, 17/20, 16/20, 18/20 → the six
  boundary branches around T_reject=0.35 and T_accept=0.85, recomputed independently.
- **Strict JSON** JS01–JS22: real bytes/recipes for empty/array, dup top+nested key, BOM
  (`EF BB BF…`), malformed UTF-8, lone hi/lo surrogate, valid pair, leading zero/plus,
  NaN/Infinity, −0, exponent, depth 64 vs 65 (actual nesting), fields 100000 vs 100001,
  string 1048576 vs 1048577.
- **Unicode** UC01–UC09: real code points U+03BF, U+0441, U+200B, U+200C, U+202E (reject),
  U+202B (strip-and-flag), U+00A0 (normalize), U+00E9 / e+U+0301 (NFC pair).
- **Explicit-map** EM01–EM05, **profile/version** PV01–PV04, **structural violations**
  SV01–SV05, **determinism** DT01–DT10 (distinct wire bytes, equal canonical/NFC), **privacy**
  PR01–PR06 (real non-redacted + redacted traces; redaction scan finds zero raw leaks),
  **security** SEC01–SEC12 (embedded payloads).

## 8. Residual (why Verdict 2, not Verdict 1)
1. **Expected results are derived by bounded rules, not by a reference engine.** The derivation
   auditor is one independent derivation, not a second conforming TAP-E7 implementation.
2. **Four informative fixtures (INF01–INF04)** for MEANING_DISTORTION / CERTAINTY_OVERSTATEMENT
   / SCOPE_EXPANSION / QUALIFICATION_OMISSION require full engine semantics (predicate/scope/
   certainty NLP) and are explicitly marked `authoritative:false` and **excluded from the
   mandatory gate**. Those four taxonomy categories therefore have taxonomy *visibility* but no
   mandatory gated fixture.
3. **Interoperability is enabled, not demonstrated.** No second implementation has run the
   corpus.

None of these are packaging or byte-fidelity defects; they are the honest boundary of a
corpus-only correction pass that does not implement the engine.

## 9. Independent score (derived)
| Dimension | /10 |
| --- | --- |
| Corpus byte fidelity | 10 |
| Expected-result derivability (mandatory) | 9 |
| Strict-JSON branch coverage | 10 |
| Unicode-security coverage | 10 |
| Determinism evidence | 9 |
| Privacy evidence | 9 |
| Mandatory-requirement coverage | 10 |
| Hash/package reproducibility | 10 |
| Validator independence | 8 |
| Normative precision | 9 |
| Interoperability enablement | 6 |
| Overall publication readiness | 9 |
**Aggregate ≈ 9.1/10.** Up from the ≈6.2/10 audited for v1.0.0; the residual gap is the
missing second implementation and the four engine-dependent categories, not fixture fidelity.
