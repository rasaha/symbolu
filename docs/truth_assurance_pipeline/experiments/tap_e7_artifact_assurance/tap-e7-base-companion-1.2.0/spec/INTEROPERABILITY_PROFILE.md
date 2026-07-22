# Interoperability Profile (normative)

Defines exactly what two conforming TAP-E7-BASE implementations must agree on for a given
`(ValidationRecord, CandidateArtifact)`.

## Normative agreement (MUST be byte-identical)
For every mandatory fixture, two conforming implementations MUST produce identical:
- `outcome`;
- `findings` as an ordered list of `(category, polarity)`;
- `evaluation_summary` — all five counts **and** the `x-tap-e7-base-evaluation-summary`
  correspondence-method histogram and companion counts (the selected correspondence stage is
  normative: it MUST be the earliest terminal stage);
- `projection_pi` and `projection_pi_sha256`;
- the recomputed `config_fingerprint` (before evaluation).

## Allowed implementation variation (MUST NOT affect the above)
- AssuranceTrace representation (by-reference vs embedded; internal field naming) — excluded from Π.
- Implementation identity/version and any `x-impl-*` metadata on the submission — excluded from Π.
- Wall-clock/timestamps; internal processing/iteration order that does not change canonical outputs.
- Redaction mode: redacted and non-redacted traces MUST yield the same findings, outcome, counts,
  and Π (Π is privacy-invariant per PROJECTION_PI_SPEC.md §6).

## Non-normative implementation details
Choice of language, data model, parser library (subject to observable BASE-MD/BASE-JSON behavior),
concurrency, and storage. These are unconstrained provided the normative agreement holds.

## Not implementations
The corpus builder, packaging validator, byte/derivation auditors, and this review tooling are
NOT conforming implementations and do not count toward the two-implementation interoperability
criterion.
