# Data-Handling Controls (M5)

*`customer_shadow_readiness/data_controls.py`. Classification & permitted-use, redaction & minimization,
secrets/encryption **interfaces** (no real keys), and retention/deletion/export — all **non-enforcing,
shadow-only**. No real crypto, no real data egress.*

## Classification & permitted-use

- `classify(text)` → `restricted` (SSN/PII/PHI/credentials markers), `confidential` (salary/revenue/
  contract markers), else `internal`.
- `permitted_use(artifact_class, request_clearance)` enforces a **clearance lattice**: a request's
  declared `data_sensitivity` clearance may process only artifact classes at or below it. A `restricted`
  artifact requires `restricted` clearance; a `confidential` artifact is denied under `internal`
  clearance. This blocks non-permitted use before the artifact enters the runtime.

## Redaction & minimization

- `redact(text)` masks SSNs, 16-digit card numbers, emails, and `password/secret/token=…` assignments →
  `[SSN]/[CARD]/[EMAIL]/[REDACTED]`. Applied to traces and exports.
- `minimize(record)` keeps only the governance-necessary fields (request id, tenant, risk, domain, final
  disposition, stage dispositions, reason codes) — a raw record's extra fields (including any `secret`)
  are dropped. Data minimization by construction.

## Secrets & encryption interfaces (stubs)

`SecretRef` + `encrypt_at_rest(data, ref)` are **interface stubs** returning a hashed handle labelled
`STUB-NOT-REAL` — they document the boundary where a real KMS / envelope encryption must sit in a
production deployment. **No real key material exists in this track**; the HMAC key in `security.py` and
these stubs are explicitly not secrets. This is a NOT-EVALUATED production dimension; the interface makes
the gap explicit rather than hiding it.

## Retention / deletion / export (tenant-scoped)

`TenantDataStore` is an in-memory, tenant-scoped store:

- **retention:** `put` enforces a per-tenant `max_records` cap (oldest dropped);
- **isolation:** `get`/`export` raise `PermissionError` on a cross-tenant read (only the owning tenant or
  admin);
- **deletion (right-to-erasure):** `delete_tenant` purges a tenant's full record set and returns the
  count;
- **export:** minimized + redacted by default — an export never carries raw or cross-tenant data.

Verified: restricted classification, clearance-lattice permit/deny, redaction of all four pattern types,
minimization dropping non-governance fields, retention cap, cross-tenant read blocked, deletion purge.

## Scope honesty

These are **shadow-pilot** controls: enough to classify, minimize, redact, scope, retain, delete, and
export tenant data safely inside a bounded pilot. They are **not** a production data-governance stack —
real KMS, real encryption, DLP, and a data-processing agreement are NOT-EVALUATED and required before
production. The controls here make each of those boundaries explicit.
