# Clean-Room Handoff Specification — TAP-E7-BASE Implementation B

Implementation B must be authored by a party that has **not** read Implementation A's source, the
corpus builder, the auditors, or the packaging validator. B receives only the items below.

## 1. Authoritative normative documents (only these)
1. TAP-E7 — Artifact Assurance — Formal Specification v1.0.0
2. TAP-E7-BASE — Conformance Profile v1.0
3. TAP-E7-BASE Companion Release v1.0.0
4. The v1.1.0 package normative resources, grammar, schemas, and **corrected** mandatory corpus.

## 2. Package path
`docs/truth_assurance_pipeline/experiments/tap_e7_artifact_assurance/tap-e7-base-companion-1.1.0/`
(after the corpus point-release that corrects DT03, UC08, UC09 and clarifies the exact/structured
method labeling; see specification-ambiguities.md).

## 3. Conformance command contract
- Input: for each `corpus/<id>.json`, the tuple `{modality, validation_record, artifact,
  profile_ref, release_ref}` — B MUST NOT read `expected/`, `derivations/`, or the fixture
  `phenomenon`/`purpose`/`group`/`authoritative` fields during evaluation.
- B MUST recompute the runtime config fingerprint and halt if it differs from
  `manifest/release-manifest.json → roots.config_fingerprint`.
- Output: one `AssuranceRecord` per fixture with `{outcome, findings[], evaluation_summary,
  projection_pi, projection_pi_sha256}`.
- Comparison against `expected/<id>.expected.json` happens only after B has produced its record.

## 4. Expected output schema
`schemas/expected-result.schema.json` plus the projection Π shape:
`projection_pi = {outcome, findings:[{category,polarity}], evaluation_summary:{total_assertive,
evaluated_assertive, unevaluated_assertive, positive_violations, evaluation_limitations}}`,
canonicalized (`sort_keys, separators=(",",":"), ensure_ascii=false`, trailing `\n`) then SHA-256.
(Publishing this Π shape and the fingerprint recipe normatively is a recommended pre-B fix.)

## 5. Prohibited code reuse
B MUST NOT import or read: Implementation A `src/` or `tools/`, `tap-e7-base-companion-1.1.0-tooling/`,
the `derivations/`, or any expected-result generator. Shared: only the immutable resources/schemas
and generic UTF-8/JSON/SHA-256/canonical-ordering utilities (independently implemented).

## 6. Pass criterion
B passes only if every corrected mandatory fixture matches on outcome, findings, evaluation-summary,
and projection Π/hash, with the fingerprint and immutability checks green and deterministic replay
identical. Two independent passes (A on the corrected corpus + B) are the precondition for stable
promotion.
