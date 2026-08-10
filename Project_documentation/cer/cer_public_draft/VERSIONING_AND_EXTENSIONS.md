# CER Versioning & Extensions (Public Draft)

## Envelope version
`cer_version` is an exact-match string (`"0.2"` in this draft). An implementation MUST reject an
unrecognized `cer_version` (no implicit up/down-negotiation).

## Profile versioning
Profiles carry their version in the id (`…v1`). A profile is immutable once published: a change to
required/optional/prohibited fields, normalization, or identity mapping is a **new profile version**
(`…v2`), never an in-place edit. Unknown profile or version MUST fail closed. Adding a profile is
additive and MUST NOT change any existing profile's digests.

## Identity profile
The identity projection is versioned separately and domain-separated in the hash's `schema_version`
(v1 `"1.0.0"`, v2 `"2.0.0"`). A new identity profile is a new `schema_version`; it never mutates an
existing one.

## Extensions
`extensions` is an object. Only the empty object (or absence) is recognized in this draft. Any
non-empty unrecognized extension MUST fail closed. A future extension namespace MUST be registered
(name + version + whether it participates in identity) before it is accepted; unregistered
extensions never silently pass.

## Vectors & errata
Published conformance vectors are frozen. A correction is a **new vector** or a **versioned
clarification / erratum**, never an edit of a published vector. An implementation is never tuned to
another to hide a disagreement; any identity-affecting disagreement is a high-severity defect,
resolved by normative language + new vectors.
