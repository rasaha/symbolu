# Clean-Room Declaration — Implementation B

Implementation B (`src/verifier.js`) was authored from the published TAP-E7 spec, BASE profile, and
the v1.1.1 normative resources/manifests. It imports **nothing** from Implementation A, the corpus
builder, the v1.1.0/v1.1.1 correction builders, the packaging validator, the byte-reproducibility
auditor, the normative-derivation auditor, or any expected-result/derivation logic. It contains no
fixture-ID dispatch table (verified: `results/fixture-id-independence.json`).

Blind execution is technically enforced (guarded `fs.readFileSync`), not merely asserted; the access
log and blind-boundary proof are in `clean_room_evidence/`.

**Irreducible caveat, stated up front:** A and B share one author. This is *language + architecture*
independence, not *organizational* independence. See `CLEAN_ROOM_ACCESS_POLICY.json` and
`reports/stable-promotion-assessment.md`.
