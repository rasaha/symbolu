# External Implementer's Guide (informative)

A concise, non-normative orientation for building a conforming TAP-E7-BASE verifier. Normative
authority is the Formal Specification, the BASE Profile, the Companion Release, and the spec/
documents in this package.

## Required documents
1. TAP-E7 — Artifact Assurance — Formal Specification v1.0.0 (outcomes, precedence, taxonomy).
2. TAP-E7-BASE — Conformance Profile v1.0 (correspondence stages, thresholds, Unicode/JSON behavior).
3. This package's `spec/CANONICALIZATION.md`, `CONFIG_FINGERPRINT_SPEC.md`, `PROJECTION_PI_SPEC.md`,
   `INTEROPERABILITY_PROFILE.md`.

## Required resources (read from the package)
`resources/**`, `grammar/**`, `schemas/strict-json-profile.json`, and the three manifests. Bind them
by recomputing `config_fingerprint` (CONFIG_FINGERPRINT_SPEC.md) and halting on mismatch.

## Suggested implementation order
1. Canonical JSON + SHA-256; reproduce the four published roots and the fingerprint (self-check).
2. Strict JSON validator (raw-byte, duplicate-key-preserving) per `schemas/strict-json-profile.json`.
3. Content tokenization + lemmatization from `resources/**`; integer-rational Jaccard.
4. Correspondence staging explicit → exact → structured → lexical (earliest terminal stage wins).
5. Unicode dispositions (reject / strip-and-flag / normalize) with NFC; record-supplied aliases.
6. Structural fidelity; §8.1 aggregation; evaluation-summary counts; projection Π + hash.
7. AssuranceTrace + redaction; run the mandatory corpus blind, then compare to `expected/`.

## Common mistakes
- Comparing Jaccard as binary floats at 0.35/0.85 (use exact rationals).
- Trusting a host JSON parser that erases duplicate keys.
- Treating NFC, confusable skeleton, alias equivalence, and diacritic folding as interchangeable
  (they are distinct; **no diacritic folding exists**).
- Labeling a full-text normalized exact match as `structured` (exact precedes structured).
- Letting the corpus or reports leak into the config fingerprint.

## What must NOT be implemented / out of scope
Artifact generation, repair, wording recommendations, completeness evaluation, operational
disposition, external fact-checking, LLM/embedding/network use. The four informative categories
(MEANING_DISTORTION, CERTAINTY_OVERSTATEMENT, SCOPE_EXPANSION, QUALIFICATION_OMISSION) are non-gate
and are not required for mandatory conformance.
