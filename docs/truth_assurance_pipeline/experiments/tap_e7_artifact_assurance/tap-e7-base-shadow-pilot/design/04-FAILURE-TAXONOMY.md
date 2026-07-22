# 4. Failure Taxonomy

Every observed problem is filed into exactly one class. **TAP-E7 is never modified to accommodate a
failure; failures are recorded only.**

## G — Generator failures
The upstream generator produced a defective artifact (hallucination, wrong citation, dropped
qualifier). This is the *target signal* — a "failure" of the artifact, correctly surfaced (or missed) by TAP-E7.
- G1 unsupported assertion / fabrication
- G2 status upgrade (asserting contradicted/uncertain claims)
- G3 citation / provenance mismatch
- G4 certainty inflation (engine-level)
- G5 scope expansion (engine-level)
- G6 omitted qualifier (engine-level)

## A — Artifact failures (structural)
The artifact could not be parsed/processed under BASE.
- A1 input integrity (bad UTF-8, duplicate JSON key, BOM, bidi-reject)
- A2 processing limit (depth/field/size, unsupported construct)
- A3 unsupported modality

## V — Validation (TAP-E7) failures
TAP-E7 itself behaved incorrectly relative to its own frozen rules.
- V1 false positive (flagged a genuinely faithful artifact) — **none observed in demo**
- V2 false negative *within* a BASE-detectable class (missed a structural issue it should catch)
- V3 nondeterminism / fingerprint drift
NOTE: a miss on an **engine-level** category (G4–G6) is **not** a V-failure — it is documented
out-of-scope behavior (class O).

## H — Human-review disagreement
- H1 reviewer vs reviewer (low κ)
- H2 reviewer vs expected relationship
- H3 reviewer vs TAP-E7 (where reviewer is right)

## O — Out-of-scope observations
Real but outside TAP-E7's verify-only mandate: tone, completeness, domain-specific policy, semantic
nuance beyond the taxonomy. Recorded as **future-work candidates**, never as TAP-E7 defects.

## Adjudication rule
Classify by *first controlling cause*. A missed scope-expansion is **G5 + O** (generator issue that
is out of BASE scope), **not** V2. Only a miss inside a BASE-detectable class is V2.
