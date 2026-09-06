# ADR — Trusted Evidence Authority production trust-anchor resolver (TR-1 to TR-5)

**Status:** rulings TR-1 to TR-5 ratified by the owner, 2026-09-06; the §5
protocol amendment ratified the same day as **TR-3-PROTOCOL =
KEYWORD_ONLY_AS_OF_ON_RESOLVE**; implemented in
`ugence-trusted-evidence-authority` 0.5.0 as a production-shaped resolver
candidate.
**Maturity of the eventual result:** a production-shaped resolver candidate only.
Not independently reviewed, not externally cryptographically audited, not
production-ready. D-38 and D-32(4) remain applicable.
**Predecessors:** `ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md` (DD-10,
E-8, D-22, D-27, D-28, D-41), `ADR_UGENCE_SIGNED_EFFECT_ATTESTATION_SCOPING.md`
(SE-4), `ADR_UGENCE_RA8_EFFECT_ATTESTATION_INTEGRATION.md` (RI-4).

## 1 — The question

What must the Trusted Evidence Authority (TEA) ship so that a resolver can be
production-authoritative, and what must stay outside the repository? Answer: a
file-backed, manifest-signed, immutable snapshot resolver with typed unavailable
and stale refusals, and an operational publication, rotation and revocation
process that the ADR specifies and nothing implements.

## 2 — Findings

| Finding | Evidence |
| --- | --- |
| `TrustAnchorResolverPort.resolve(coordinate) -> TrustAnchorResolution` takes no instant, reads no clock, performs no authorization; network retrieval is outside TEV-2 `[V]` | `packages/trusted-evidence-authority/src/.../authority/trust.py:510-528` |
| `TrustAnchorRecord` validates the Ed25519 point at construction and on `verification_key()`; lifecycle order is revoked, disabled, not yet valid, expired at a caller-supplied aware instant; `canonical_digest()` is the anchor revision `[V]` | `trust.py:276-445` |
| `StaticTrustAnchorDirectory` is documented as "the shape a production resolver should present": duplicates refused, immutable, no widening, empty set refuses `NOT_CONFIGURED` `[V]` | `trust.py:530-668` |
| `DenyAllTrustAnchorDirectory` is E-8's deny default and refuses every coordinate `[V]` | `trust.py:670-696` |
| Every consumer admits a production resolver by the same rule: the static directory and its subclasses refused, `DenyAll` admitted by exact type, otherwise `is_production_authoritative is True` `[V]` | 5B-0A `trust.py`; effect attestation `trust.py:137-162`; RA-8 via the verifier's `production_mode` |
| All four `resolve` call sites hold an evaluation instant of their own when they call `[V]` | TEA `verification.py:419`, `reverification.py:742`; 5B-0A `verification.py:469`; effect attestation `verification.py:315` |
| The repository's precedent keeps a resolver instant-free and evaluates lifecycle in the verification seam so revoked, disabled, not-yet-valid and expired stay distinguishable `[V]` | BR-2C `contracts/ports.py:182-214` (D-27) |
| D-28 ratified fail-closed on unavailable **and** stale trust state with distinct refusals and never a cached fallback; TEA's refusal vocabulary has no equivalent members `[V]` | ADR D-28; `contracts/reasons.py` |
| Production posture flag precedent: Risk Authority's SQLite adapter is production-authoritative only when file-backed; D-22 ratified stdlib `sqlite3` single-node durability `[V]` | `risk_authority/persistence/sqlite.py:176-179`; ADR D-22 |
| No production resolver, no snapshot format, no loader, no publication or revocation tooling, and no custody owner exist; DD-10b remains deferred `[G]` | `packages/**` (no implementation); ADR DD-10b; `.github/CODEOWNERS` names no TEA owner |

## 3 — Rulings

| Ruling | Consequence |
| --- | --- |
| **TR-1 STORE = SIGNED_FILE_SNAPSHOT** | One immutable snapshot file, loaded at the composition root. No network, discovery, refresh or credential access in the package. Trust changes by verifying and atomically replacing the whole snapshot and constructing a new resolver; no `with_anchor`-style widening on the production type. |
| **TR-2 SET_AUTHENTICATION = SIGNED_MANIFEST_UNDER_NEW_CAPABILITY** | New enum member `TrustAnchorCapability.TRUST_ANCHOR_SET_PUBLICATION`. The manifest binds schema/domain version, set id, monotonic set version, publisher identity, `published_at`, `effective_from`/`effective_to`, the complete canonical record collection and its digest. The publication anchor is a pinned bootstrap root supplied at the composition boundary, never taken from the snapshot. Refused: self-authenticating snapshots, absent or unknown publication anchors, wrong-capability publication anchors, rollback or non-monotonic versions, any mutation of manifest, records, order or digest, duplicate coordinates, omitted or appended records. |
| **TR-3 STALENESS = MAX_SNAPSHOT_AGE_REFUSED** | Unavailable and stale are distinct typed refusals; both fail closed. Freshness ends at the earlier of the signed `effective_to` and `published_at` plus the owner-configured maximum age. No clock read; the composition root supplies an aware `as_of`. Freshness is not frozen at startup, not cached past expiry, and not conflated with anchor-level expiry. **Protocol check: see §5.** |
| **TR-4 CUSTODY_ROLES** | Organizational roles, not package classes: Trust Operations Publisher (assembles and invokes the external publication signer; cannot create or extract attester keys), Key Custody Officer (introduces replacements, bounded overlap, retirement through a new snapshot; cannot erase history), Security Incident Authority (orders immediate revocation or disablement and a superseding snapshot; never gated on the compromised owner's approval). Every action needs an immutable audit record: actor, reason, prior version, resulting version, artifact digest. No private key, HSM or KMS credential enters the repository; DD-10b stays deferred. |
| **TR-5 FIRST_CONSUMER = EFFECT_ATTESTATION** | After the resolver is complete and separately accepted, effect attestation wires first, then RA-8 once compatibility is proved, then 5B-0A as a separately validated step. Nothing is wired in the resolver PR. |

## 4 — What the package will and will not contain

Will: snapshot and manifest contracts, the capability, a bootstrap-anchor
input type, deterministic canonicalization and complete-set digest, atomic
file loading with no partial admission, a resolver that is
`is_production_authoritative` only after manifest, bootstrap anchor, version,
validity, freshness and every anchor validate, typed unavailable and stale
refusals, rollback refusal, and a reusable conformance suite.

Will not: publication tooling, KMS/HSM signing, remote retrieval, automated
rotation or revocation, any signer, any credential, any clock. The operational
process in TR-4 is specified here and implemented nowhere.

## 5 — TR-3 protocol check and the amendment for ruling `[R]`

**Finding.** A resolver can only refuse a stale snapshot at resolution time if
it knows the instant at resolution time. `resolve(coordinate)` carries none, the
package may read no clock, and an injected "current instant" supplier would be a
clock by another name, which D-11, D-28 and the 5B-2 ratification all reject in
favour of an explicit instant input. Enforcing TR-3 on every resolution therefore
requires changing the public `TrustAnchorResolverPort`. Per the ruling,
implementation stopped at this finding until the amendment below was ruled.

**Smallest additive amendment (recommended).** Add one keyword-only optional
parameter to the port and to both shipped directories:

```
def resolve(self, coordinate: TrustAnchorCoordinate, *, as_of: Optional[datetime] = None) -> TrustAnchorResolution
```

- Existing callers keep working unchanged: `resolve(coordinate)` remains valid.
- `StaticTrustAnchorDirectory` and `DenyAllTrustAnchorDirectory` accept and
  ignore `as_of`; their behaviour does not change.
- The production resolver refuses with a new typed reason
  `TRUST_ANCHOR_SET_INSTANT_REQUIRED` when `as_of` is absent or not an aware
  `datetime`, so a caller that forgets the instant cannot get an anchor.
- Two further typed reasons are added: `TRUST_ANCHOR_SET_UNAVAILABLE` and
  `TRUST_ANCHOR_SET_STALE`.
- The three consumers that pass through TEA's admission rule already hold an
  `as_of`; each forwards it in a one-line follow-up change under TR-5 ordering.

**Alternative considered, not recommended.** Keep the port unchanged and add
optional snapshot freshness bounds to `TrustAnchorResolution`, leaving staleness
evaluation to each consumer at its own instant. This follows the BR-2C
instant-free resolver precedent, but it makes the resolver unable to refuse a
stale snapshot itself, which TR-3 requires, and it spreads the freshness rule
across four verifiers instead of one resolver.

**Ruled: TR-3-PROTOCOL = KEYWORD_ONLY_AS_OF_ON_RESOLVE.** The port is amended
additively to `resolve(coordinate, *, as_of=None)`. Consequences, as ratified
and as implemented `[V]`:

1. callers that omit `as_of` remain source-compatible;
2. `StaticTrustAnchorDirectory` and `DenyAllTrustAnchorDirectory` accept the
   keyword and preserve their behaviour;
3. a resolver declaring `is_production_authoritative = True` requires an explicit
   timezone-aware `as_of` on every resolution;
4. a missing, naive, malformed or wrong-type `as_of` returns the typed refusal
   `TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_INSTANT_REQUIRED` (the package's
   `TRUSTED_EVIDENCE_` prefix applied to the ruled name);
5. the production resolver reads no clock, environment, filesystem metadata
   time or hidden time supplier;
6. freshness is evaluated against the `as_of` of that exact resolution;
7. the alternative is rejected because it delegates enforcement to consumers;
8. the default exists for compatibility only; no production resolution
   succeeds at `as_of=None`.

The four existing call sites forward their instant (`verification.py`,
`reverification.py`, 5B-0A, effect attestation), which is contract migration
only and not production consumer wiring; every in-repository double accepts the
keyword. A third-party resolver that lacks the keyword is not
production-conformant under 0.5.0.

## 5a — Reconciliation with the package's filesystem ban `[V]`

TR-1 says the snapshot is "loaded at the deployment composition root", and
`tests/packaging/test_no_clock_or_environment.py` bans `open(`, `os`, `pathlib`
and every clock call across the package's source tree. Both hold: the
composition root performs the file read and hands the **complete bytes** to
`SignedSnapshotTrustAnchorResolver.from_document`, which verifies atomically and
admits nothing on any failure. An unreadable file is passed as `None` and yields
the typed unavailable state. No file is opened inside the package.

## 5b — What 0.5.0 ships `[V]`

`TrustAnchorCapability.TRUST_ANCHOR_SET_PUBLICATION`; `TrustAnchorSetManifest`,
`TrustAnchorSetSnapshot`, the wire document (`parse_…`/`render_…`), the
complete-collection digest and the publication signing bytes;
`SignedSnapshotTrustAnchorResolver.from_document(document, publication_root=,
max_snapshot_age=, last_accepted_set_version=)`; `TrustAnchorSetLoadFailure`;
the three appended refusal reasons; the resolver conformance harness
(`tests/authority/resolver_conformance.py`); a measured mutation sweep. Every
snapshot check runs in the ruled order: instant, admission, publication root
lifecycle and set window at `as_of`, freshness, exact coordinate, typed
resolution. Anchor lifecycle stays with the verifier.

Not-yet-valid sets refuse as unavailable, not stale: the ruling minted three
reasons, and a set that is not yet in force is trust state that cannot be
consulted at that instant rather than trust state that has aged out.

## 6 — Stated explicitly

- A resolved anchor is an input to verification, never an authorization.
- The eventual resolver is a production-shaped candidate. It is not audited,
  not independently reviewed and not production-ready; D-38 and D-32(4) stand.
- The custody roles bind deployments, not this repository; nothing here
  enforces them.
- No consumer is wired to production by this milestone.

## 7 — Next step

Separate acceptance of 0.5.0, then wire effect attestation to the resolver at
reference grade under TR-5, still without a production claim.
