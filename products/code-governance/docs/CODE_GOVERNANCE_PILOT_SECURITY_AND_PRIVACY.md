# Pilot Security & Privacy

> All enterprise integrations are **read-only**; GitHub writes are structurally
> prohibited. Credentials never enter the durable store, and only
> governance-relevant data is collected.

## Read-only, structurally

The read-only transport exposes only GET/HEAD and rejects every mutating method,
unapproved host, unapproved endpoint, and unapproved redirect target. The GitHub
adapter has no write method and no write client. There is no GitHub App write
permission, no merge credential, and no execution provider.

## Credential boundary

Credentials are supplied to the transport through a `CredentialResolver` (a
caller-provided resolver, an environment reference, or an existing secret-manager
interface — no new secret manager is built). Credentials are used only to
authenticate an outbound read. They are **never**:

- returned in a `ReadOnlyResponse` (credential-bearing headers are stripped),
- included in an `AdapterResult`, a fingerprint, or an audit bundle,
- written to the durable Code Governance store,
- included in an error message, or logged.

The offline demo asserts that a resolver-supplied bearer token never appears
anywhere in the persisted pilot records.

## Sensitive response handling

Adapter response fields are classified `PERSIST_CANONICAL`, `PERSIST_NORMALIZED`,
`PERSIST_REFERENCE_ONLY`, or `DO_NOT_PERSIST`. Repository/head SHA persist
canonically; check conclusions persist normalized; full CI logs are reference-only;
authorization headers, tokens, raw identity profiles, and private incident notes
are never persisted. Durable serialization fails closed if a prohibited field is
passed (reusing the 1C data-minimization guard).

## Data minimization

Identity snapshots may carry only `actor_ref`, `account_active`, `status_category`,
`roles`, `groups`, and `authority_scopes`; salary, medical, performance content,
private messages, browsing/device telemetry, home address, personal phone number,
and unrelated demographics are never collected or persisted. Stable subject
references are used, never full employee profiles. No unrelated employee or company
data is collected.

## Retention

Pilot data carries a documented retention category (`SHORT_PILOT`,
`STANDARD_AUDIT`, `REFERENCE_ONLY`) and bounded response sizes. MVP 1D adds no
destructive automated retention engine and no public API that deletes immutable
governance history.
