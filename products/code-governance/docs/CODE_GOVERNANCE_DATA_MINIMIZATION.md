# Data Minimization

> The durable store persists **only governance-relevant data**: identifiers,
> content hashes, and normalized metadata. Field names that look like credentials
> or unrelated PII are **rejected** (fail closed). Naive (timezone-unaware)
> datetimes are rejected. The store never persists arbitrary live Python objects —
> only frozen product records and explicit projection dicts.

Machine-readable companion: `docs/data_minimization.json`.

## Prohibited field names

Serialization rejects any mapping key whose lowercased name contains a prohibited
substring, raising `ProhibitedFieldError`:

```
token, secret, password, passwd, private_key, privatekey, api_key, apikey,
oauth, credential, webhook, salary, ssn, social_security, medical,
health_record, date_of_birth, home_address
```

This is a structural guard, not a scrub: a payload that tries to carry a
credential-like field is refused outright rather than silently redacted.

## Never persisted

- Credentials, tokens, OAuth material, webhook secrets.
- Source diffs or file contents.
- Unrelated company or employee data / PII.

The projections that reference upstream authoritative records store the record's
**identity + content hash** only — enough to verify linkage, nothing more.

## Canonicalization rules

- Mappings are emitted with sorted keys and compact separators.
- Enums serialize to their `.value`; tuples to lists.
- `datetime` must be timezone-aware and is normalized to RFC 3339 UTC (`…Z`); a
  naive datetime raises `ProhibitedFieldError`.
- Unknown/opaque object types are refused (`ProhibitedFieldError`) — there is no
  pickling and no best-effort `str()` of arbitrary objects.

## Why fail closed

Data minimization here is a boundary, not a filter. Refusing an out-of-policy
field at write time makes it impossible for a caller to accidentally persist a
secret into the append-only audit store, where it could never be deleted.
