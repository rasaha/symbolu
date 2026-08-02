# Credential Boundary

> Credentials are **referenced, never embedded**. A `CredentialReference` names
> where a read-only credential lives (an env var or an external resolver ref) but
> never carries the value. Resolved credentials are process-memory-only and handed
> to the approved read-only transport immediately before a request, then discarded.

## Never crosses these boundaries

A resolved credential value never appears in: configuration objects · public
request/result models · durable records · logs · metrics · reports · audit
bundles · fingerprints · exception messages. The credential-bearing response
headers are stripped by the transport.

## Verification

`scan_for_credential(value, *artifacts)` proves absence. Using a unique test
credential, the acceptance tests and the offline demo confirm the value appears
nowhere outside the fake resolver + transport invocation boundary — not in the
durable store, logs, metrics, report, audit bundle, exceptions, or fingerprints.

No new secret manager is built; an existing env-var or external resolver reference
is used. A reference that tries to inline a value-looking token fails closed
(`CredentialBoundaryError`) without echoing the value.
