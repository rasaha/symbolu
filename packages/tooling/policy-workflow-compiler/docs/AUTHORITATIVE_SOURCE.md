# Authoritative Source Linkage (PA/PWC-X1)

A `policy_pack.v2` pack may carry the exact Policy Authority issuance it was
compiled from. The compiler binds that reference into the release and validates it
structurally — and does no more than that.

## Carriage, not authenticity

| This package asserts | Policy Authority asserts (never here) |
| --- | --- |
| the reference is present where required | the signature is valid |
| the coordinate is well-formed | the key is trusted |
| the issuance attestation is complete | the policy is not revoked |
| the release agrees with its own manifest | the resolution is current |

The compiler imports nothing from `packages/policy-authority`, enforced by a
boundary test. It could not verify a signature without reimplementing Policy
Authority's canonicalization — a second implementation of authority semantics whose
drift would surface as a false integrity failure on a valid artifact.

`version_info()` says both halves out loud:
`authoritative_source_carriage_implemented=true`,
`authoritative_source_verification_implemented=false`.

## What is carried

`AuthoritativeSourceRef` holds plain strings in three tiers: the six-field
coordinate plus `record_id` and `policy_body_digest` (identity linkage), the
issuance attestation (evidence for audit and replay), and the resolution context
(`resolved_as_of`, `historical` — a historical answer never implies current
validity).

**The binding is the pack's own reference**, which a v2 pack's logical digest
commits to. `ReleaseManifest.authoritative_source_coordinate` denormalizes it for
offline inspection; manifest values are outside the logical digest, so that copy is
a convenience rendering and never the binding.

## Refusal codes

| Code | Raised when |
| --- | --- |
| `MISSING_AUTHORITATIVE_SOURCE` | A caller required the linkage and the pack carries none |
| `MALFORMED_AUTHORITATIVE_COORDINATE` | A coordinate field is blank, or a digest field is not `sha256:…`-shaped |
| `INCOMPLETE_ISSUANCE_ATTESTATION` | The attestation is partial — all-or-none, mirroring Policy Authority's own descriptor rule, because a partial attestation looks checkable and is not |
| `AUTHORITATIVE_SOURCE_MISMATCH` | The manifest's denormalized coordinate disagrees with the pack's reference — an integrity failure of *this release*, not a claim about the issuance it names |

No code may be worded to suggest a signature, key-trust or revocation check that
did not happen.

## Why `MISSING_AUTHORITATIVE_SOURCE` is opt-in

`policy_pack.v2` is a schema, not an authority integration. Requiring Policy
Authority linkage on every v2 pack would couple the two, which the ratified boundary
keeps apart — and would make a local or demonstration v2 pack impossible. So the
code is raised only when a caller states it requires the linkage:

```python
check_authoritative_source(pack, required=True)
```

The composition root that derives the reference from a `RESOLVED` resolution is
exactly that caller. Everything else — shape, completeness, agreement — is checked
unconditionally and fails closed.

## Where the trust actually comes from

The reference must be **derived** from a successfully verified Policy Authority
resolution by the designated composition root, never authored by a caller. That is
the ratified derivation prohibition (X1-B); this package can carry a reference
faithfully, but it cannot tell a derived one from an asserted one.
