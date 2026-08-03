# Evidence boundary

- The neutral contract carries evidence **references** only (`evidence_refs`),
  never raw content. The request mapper resolves each reference into a native
  evidence item whose `source_reference` is the caller-supplied id and whose
  `provenance` records the resolution mode.
- TAP does **not** implicitly fetch unrestricted enterprise data. Evidence
  acquisition is caller-supplied by default; the mode is explicit and validated
  (`caller_supplied` / `provider_client` / `external_resolver`).
- Raw credentials / embedded secrets are **rejected**; only secret *references*
  (`ref:...`) are accepted. TAP implements no secret-management system.
- Provenance/authority describe *where evidence came from* and are kept **separate
  from support** — provenance is never treated as proof of truth.
- Audit records store counts and coverage ratios only — never unrestricted source
  corpora or secrets.

No connector, crawler, RAG system, external database, or document-fetching behavior
belongs in TAP. Enforced by `tests/mapping/test_evidence_boundary.py`.
