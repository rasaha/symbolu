# Changelog — ugence-clearance-export

## 0.1.0 — 2026-09-06

First release. Contracts only, under
`docs/architecture/ADR_UGENCE_CLEARANCE_EXPORT_SCOPING.md` §10 (CE-1 to CE-5) and
§13 (CE-6, CE-7).

- `ClearanceExportArtifact` — one received `ClearanceReceiptBody`, carried unaltered,
  wrapped with what a reader can and cannot check about it. Content-addressed
  (`cxp_` + fingerprint) and stable: no clock, no nonce, so two exports of the same
  clearance are byte-identical.
- Three one-member enums, on the `SystemBindingAuthenticityStatus` precedent —
  `IdentityAssurance.PRESENTED_UNPROVEN` (CE-3), `ExportAuthenticity.UNSIGNED` with
  the unfed trust-anchor prerequisite named in the artifact (CE-4), and
  `ExportDataClassification.SYNTHETIC_DEMONSTRATION_ONLY` (CE-7, §13.1). All three
  are required keyword arguments, validated, always serialized, and inside the
  fingerprint preimage.
- `verify_export` — a pure verifier returning a report, never a boolean, so integrity
  is never read as authenticity. Names four things it did not establish, and answers
  `confers` with `NOTHING`.
- `ReceivedClearanceSource` — the one read-only Protocol. Two reads, no write (CE-5).
- Refusal reasons for every softened claim, and `COMPILE_SHAPED_KEYS` so a compile
  result cannot enter as a clearance (CE-1).

One declared dependency: `ugence-action-clearance`, for the frozen receipt type CE-2
forbids redefining. `ugence-execution-reservation` is deliberately not a dependency —
it persists receipts, and a store reached through the dependency graph is still a
store.
