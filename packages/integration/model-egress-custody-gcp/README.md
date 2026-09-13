# Ugence Model Egress Custody (GCP)

**Version:** 0.1.0
**Maturity:** `PRODUCTION_FORM_NON_PRODUCTION_SCOPE` · `LIVE_VENDOR_EGRESS = False`

The production-form Google Secret Manager custody adapter for the Model Egress Unit.
This is the adapter LP-8 names as the only one that may materialize the provider
credential for the commissioning validation.

## This distribution holds no credential and calls no model vendor

It reads one pinned Secret Manager version through an **injected client**. No HTTP
client, no vendor SDK and no model destination exist here. The Google SDK is an
optional extra imported inside `build_google_secret_manager_client()` and nowhere else,
so importing this package imports no Google SDK, constructs no client and opens no
connection. The whole test suite runs with no Google dependency installed and contacts
nothing.

"Production-form" describes the *client*, not the deployment. The deployment it serves
is the dedicated non-production commissioning path; production needs its own
commissioning record.

## What it refuses, in the order it refuses

| Stage | Refused |
|---|---|
| Configuration | a credential shape in any field, a downloaded service-account key document, a field that names material rather than a reference (`FORBIDDEN_CONFIG_KEYS`), an environment other than `non-production`, a rotation window over 90 days |
| Resource | `latest`, any alias, a non-numeric, zero, negative or zero-padded version, a missing or extra segment, surrounding whitespace |
| Identity | `application_default_credentials` (a discovery order, not an identity), developer credentials, a downloaded key file, an emulator, a human or default-compute account, a runtime account that is not the exact designated one, a missing attestation or designation digest |
| Designation | fewer than seventeen obligations, any obligation still `UNDESIGNATED`, a credential shape in an obligation, a missing independent verification, a secret version in a different project than the designated one |
| Binding | a configured version that is not the designated one, an identity whose account disagrees with the record, a mechanism other than the designated one |
| Answer | a reply for a different version, a non-bytes payload, an empty or whitespace-only payload, a payload over 8 KiB, a payload that is not valid UTF-8, a payload carrying control characters |
| Provider error | anything the client raises becomes `CUSTODY_UNAVAILABLE` carrying the exception's **type name only**, never its message |

Construction performs every check and touches nothing: no network call, no file read,
no environment read. A misconfigured adapter cannot be constructed, so it cannot call.

## The one permitted call

The client protocol carries exactly one method, `access_secret_version(*, name)`. There
is no `list_secrets`, no `list_secret_versions` and no `get_secret` to call, and the
SDK object is private inside the wrapper, so a holder of the wrapper cannot reach one.
`tests/test_boundaries.py` asserts the protocol's whole surface.

## Where the secret is, and is not

The payload exists inside one function and reaches the caller only inside the unit's
`CredentialLease`, which keeps it out of `repr`, `str`, equality, `as_record()` and
pickling and hands it to exactly one consumer through `use()`. The adapter's own
`as_record()` is identifiers only; its `repr` names no principal secret and no client;
it refuses pickling. The audit trail is the unit's existing `CustodyAuditEvent` of
identifiers and digests.

## Composition

```python
from ugence_model_egress_custody_gcp import (
    CustodyConfig, ProductionFormSecretManagerCustodyAdapter,
    RuntimeIdentityAssertion, build_google_secret_manager_client)

adapter = ProductionFormSecretManagerCustodyAdapter(
    config=CustodyConfig(..., identity=RuntimeIdentityAssertion(
        source="attached_service_account", service_account_resource=SA,
        designated_service_account=SA, designation_attested_by=WHO,
        designation_record_digest=DIGEST)),
    client=build_google_secret_manager_client(),   # deployment composition root only
    designation=designation_record["step8_required_values"])
```

Tests inject a fake client instead. Nothing in this package calls
`build_google_secret_manager_client()` for you.

## Tests

`pytest packages/integration/model-egress-custody-gcp` — sockets are refused inside the
suite, so a test that reached a network would fail rather than pass slowly.
