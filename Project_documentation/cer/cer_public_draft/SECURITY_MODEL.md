# CER Security Model (Public Draft)

CER is an identity + integrity contract for governed actions. It does not itself authorize;
it makes the action **canonical, hashable, and tamper-evident** so an external authorizer and an
operational-safety layer can bind decisions to the exact action.

## Threat model
Adversary may control the runtime/model and can attempt to: smuggle extra fields; hide a
downgrade; reuse an approval/evidence for a different action or domain; alter an action after
approval; embed credentials; or force two different actions to collide.

## Invariants (MUST hold in a conformant implementation)
1. **Exact-action binding** — identity is the content hash of the projected action; any material
   change changes the digest.
2. **Provenance cannot alter identity** — runtime/model/objective are excluded.
3. **No cross-action / cross-domain transfer** — approvals and evidence bind to the digest; a
   different action (or domain) has a different digest and fails closed.
4. **No profile collision** — distinct profiles are domain-separated inside the hash; identical
   field names across profiles do not collide.
5. **Fail closed** — unknown profile/field/extension, operation/profile mismatch, prohibited
   (downgrade) field, bare/NaN/Inf numeric, duplicate keys → rejected before any identity.
6. **No secret in identity** — domains that declare it (e.g. database) reject raw credentials,
   DSNs, connection strings, statement text, and embedded-credential value patterns before
   hashing; no secret enters identity, canonical bytes, logs, or conformance output.
7. **Determinism** — canonicalization + hashing are deterministic; reruns are byte-identical.

## Out of scope for CER itself
Authorization policy, key custody/signing, replay protection, and operational safety are the
responsibility of the *governance layer* that consumes CER (in the reference deployment, the
Ugence AI Control Plane). CER guarantees the object those layers bind to is exact and stable.
