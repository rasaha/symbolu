# Normalized Projection Π — Specification (normative)

Binds the previously-inferred shape of `projection_pi` and `projection_pi_sha256`. An
implementer must be able to build Π and its hash from this document without inferring anything
from example fixtures. Uses TAP-CANON/1. The companion JSON Schema is
`spec/projection-pi.schema.json`.

## 1. Role
Π is the **implementation-independent semantic core** of an `AssuranceRecord`: the fields on which
two conforming implementations must agree bit-for-bit. Its hash is the cross-implementation equality
key.

## 2. Included fields (exactly these, no others)
```
projection_pi = {
  "outcome": "ASSURED" | "NOT_ASSURED" | "INDETERMINATE",
  "findings": [ { "category": <taxonomy category string>,
                  "polarity":  "POSITIVE_VIOLATION" | "EVALUATION_LIMITATION" } , ... ],
  "evaluation_summary": {
    "total_assertive":        <int>,
    "evaluated_assertive":    <int>,
    "unevaluated_assertive":  <int>,
    "positive_violations":    <int>,
    "evaluation_limitations": <int>
  }
}
```
- `findings` is an ordered array in the AssuranceRecord's canonical finding order (evaluated
  correspondence units first in assertion order, then document-level limitations in detection
  order). Each element carries **only** `category` and `polarity`.
- `evaluation_summary` carries **only** the five integer counts above.

## 3. Excluded fields (must NOT appear in Π)
- `evaluation_summary["x-tap-e7-base-evaluation-summary"]` — the correspondence-method histogram and
  companion counts are companion metadata, excluded from Π (though still compared in full-record
  conformance; see INTEROPERABILITY_PROFILE.md).
- Per-finding `finding_index`, `validation_ref`, and any locator/evidence pointer.
- The AssuranceTrace (any representation), wall-clock/timestamps, implementation identity/version,
  and any implementation-specific metadata.

## 4. Null / optional / required
- All five `evaluation_summary` counts are **required**, non-null, `>= 0` integers, and satisfy
  `evaluated_assertive + unevaluated_assertive = total_assertive`.
- `outcome` is **required**; `findings` is **required** (may be empty `[]`, never null).
- There are no optional Π fields; a Π object contains exactly the members in §2.

## 5. Hash
```
projection_pi_sha256 = digest(projection_pi)    // "sha-256:" + hex(SHA-256( canonical_json(projection_pi) + "\n" ))
```

## 6. Privacy interaction
Π is **identical in redacted and non-redacted modes**: it contains no raw artifact text, no
locators, and no sensitive values. Redaction affects only the AssuranceTrace, which is not part of
Π. Therefore `projection_pi_sha256` is stable across privacy modes for the same evaluation.

## 7. Determinism
Because Π depends only on the outcome, the ordered (category, polarity) findings, and the five
counts — and is serialized via TAP-CANON/1 — Π and its hash are byte-stable across implementations,
input wire-order variation, NFC-equivalent inputs, and excluded-metadata differences.
