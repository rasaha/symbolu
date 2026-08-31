# ADR — Cloud Scaling Phase 5B-0B: policy authenticity (contract closure)

**Status:** proposed — closure document, awaiting owner ratification of D-5B0B-4.
**Scope:** architecture closure only. No implementation is included or authorized by this
document. Implementation follows as a separate draft PR after ratification.

Phase 5B-0A (merged as `e49db558`) answers *"did this recommendation come from a trusted
producer?"*. This document closes the contract for *"did these policy limits come from the
authoritative policy system, unchanged and valid for this tenant, resource and evaluation
context?"*

## Evidence discipline

Every `[V]` below names the command that produced it. Commands were run at
`26f7a518` on branch `claude/phase-5b-0b-policy-authenticity-670bl1`. Labels:
`[V]` verified by a command shown, `[I]` inferred from source read, `[R]` requires owner
ratification, `[G]` gap.

Scripts named as `q123.py`, `q23.py`, `q2b.py`, `q2c.py` and `q6.py` were run outside the
repository — this task adds no file but this one. The two load-bearing ones are reproduced
in full in the appendix; the rest are short enough to reconstruct from the source excerpts
cited beside each claim.

### Baselines measured for this document

| Fact | Value | Command |
|---|---|---|
| Phase 5A suite | 242 passed | `python3 -m pytest -p no:cacheprovider --no-header --tb=no -v` in `packages/integration/cloud-scaling-authorization-contracts` → `242 passed in 119.15s` |
| Phase 5A frozen digest constants | 10 `FROZEN_*` | `grep -n '^\(FROZEN\|SUPERSEDED\|RA_\)[A-Z0-9_]* = ' tests/test_frozen_digests.py` → 10 `FROZEN_*`, plus `SUPERSEDED_PRE_F2_CANDIDATE_DIGEST` and `RA_ILLUSTRATIVE_FIXTURE`, which are pinned counter-examples, not live anchors |
| Frozen digests still hold | 8 passed | `python3 -m pytest tests/test_frozen_digests.py -v` |
| Policy Authority suite | 331 passed | `python3 -m pytest -p no:cacheprovider --tb=no` in `packages/policy-authority` → `331 passed in 233.10s` |
| Phase 5A version | `0.1.0` | `cat src/ugence_cloud_scaling_authorization_contracts/version.py` |
| 5B-0A changed no Phase 5A file | empty output | `git diff --name-only e49db558^1 e49db558 \| grep cloud-scaling-authorization-contracts` |

---

## Decision record

| # | Question | Ruling | Basis |
|---|---|---|---|
| D-5B0B-1 | What exact artifact is verified | A `PolicyResolution` with `status=RESOLVED` **and** `historical=False` | `[V]` trust-root dependence; `[V]` historical carries `implies_current_validity=False` |
| D-5B0B-2 | Which digest represents the policy | `policy_body_digest`. Phase 5A's `policy_artifact_digest` corresponds to **neither** | `[V]` format incompatibility; `[V]` core issuance rule; `[G]` resolution gap |
| D-5B0B-3 | How the coordinate is bound | All six components signature-covered (21 signed keys). Phase 5A's binding **cannot name a coordinate** | `[V]` enumerated payload; `[V]` field-set comparison |
| D-5B0B-4 | Who owns the policy trust anchor | **Recommend (a)** Policy Authority's `PolicyKeyRing` — **blocked on owner ratification** | `[V]` TEV has no tenant field by ratified refusal; `[V]` PA has tenant + issue/revoke split |
| D-5B0B-5 | How revocation and validity enter | "Is valid now", at an **injected** `as_of`; no clock introduced | `[V]` five temporal gates; `[V]` no clock read in PA source |
| D-5B0B-6 | How Phase 5A receives the proof | **Alongside** the candidate, in a new package. Phase 5A stays `0.1.0` | `[V]` option (a) moves 2 frozen digests, option (b) moves 0; `[V]` 5B-0A precedent |

---

## D-5B0B-1 — What exact artifact is verified

**Decision.** The verified artifact is a **`PolicyResolution` with `status=RESOLVED` and
`historical=False`**, produced by `resolve_policy()` — not an `IssuedPolicyRecord` alone,
and not "a resolution plus a separate revocation check" bolted on afterwards.

**Why the record alone is insufficient.** `IssuedPolicyRecord` is a public frozen
dataclass; constructing one proves nothing
(`packages/policy-authority/src/ugence_policy_authority/core/records.py`, module
docstring). `[V]` A record that verifies under one configured trust root fails under
another: the same registered record resolves `RESOLVED/RESOLVED` under a `PolicyKeyRing`
and `UNRESOLVED/KEY_UNKNOWN` under `DenyAllSignatureVerifier` (script `q123.py`,
outputs H and J). Authenticity is therefore a property of *an evaluation under configured
trust at an instant*, which is exactly what a `PolicyResolution` is and what a record is
not.

**Why revocation is not a separate second check.** `resolve_policy` already performs it,
in a fixed order, and verifies every stored revocation's signature and the revoker's
`REVOKE_POLICY` entitlement before applying it
(`core/resolution.py`, the revocation block; `core/revocation.py::verify_revocation_record`).
An unverifiable revocation record fails closed as `REVOCATION_INTEGRITY_INVALID` rather
than being ignored. `[V]` After `revoke_policy()`, the same reference resolves
`UNRESOLVED/REVOKED` (script `q123.py`, output K).

**What a verified policy proof must contain for a consumer to act on it.**

1. the complete `PolicyCoordinate` — `policy_family`, `policy_id`, `version`,
   `content_digest`, `scope`, `tenant_id`;
2. `policy_body_digest` — the framed adapter-projection digest that the signature covers
   (see D-5B0B-2 for why this, not `content_digest`, is the load-bearing binding);
3. `issuing_authority_id`, `key_id`, `signature_alg`;
4. the exact `as_of` the resolution was reached at, and the
   `expected_reference_tenant_id` presented;
5. the trust-configuration identity the resolution ran under;
6. the extracted policy limits the consumer will use, bound by digest to (2).

**What it deliberately does not establish.** It does not authorize any action; it does not
prove the policy is correct or wise; it does not prove organizational truth beyond what
the configured verifier attested; it does not establish caller entitlement —
`expected_reference_tenant_id` checks the *reference's declared* tenant, not the caller's
right to it (`core/resolution.py` module docstring, and the parameter's own doc).

**Historical resolutions.** `[V]` A historical answer is reachable only under an explicit
non-default rule: with `HistoricalResolutionRule.ALLOW_BEFORE_REVOCATION` and an `as_of`
strictly before `revoked_at`, resolution returns `RESOLVED` with `historical=True` and
`implies_current_validity=False`; the default `DENY_ALWAYS` returns `UNRESOLVED/REVOKED`
for the same instant (script `q123.py`, outputs L and M).

**Ruling: a historical resolution can never back an authorization.** Not by preference —
the type already says so. `PolicyResolution.implies_current_validity` is `False` for every
historical answer, and the field is a property, not a settable field. 5B-0B's verified
result must therefore refuse `historical=True` at admission rather than carry it forward
labelled. An authorization asserts that limits apply *to an action about to be taken*; a
historical answer is by construction a statement about the past.

**Rejected:** (a) verifying `IssuedPolicyRecord` alone — trust-root-independent, so it
proves nothing a consumer can act on `[V]`; (b) accepting a historical resolution with the
flag propagated — pushes a distinction the type already draws onto every downstream
consumer, and one that forgets it authorizes against a revoked policy.

---

## D-5B0B-2 — Which digest represents the policy

**Decision.** **`policy_body_digest`** is the policy's content binding.
`content_digest` is a *coordinate component* — part of identity and signature-covered as
such — and must not be relied on as the body binding by a consumer.

**What each covers.**

- `PolicyCoordinate.content_digest` is a declared 64-hex string, validated only for shape
  at construction (`core/adapters.py::_require_digest`). It participates in identity: two
  coordinates sharing an `identity_slot` but differing in digest are a registry conflict,
  not two versions.
- `policy_body_digest` is computed: `framed_body_digest()` over the adapter's
  `canonical_projection`, framed with the canonicalization version, the
  `ugence.policy-authority/policy-body/v1` domain tag, the adapter id and the policy type
  (`core/canonical.py::framed_body_bytes`).

**Can either move without the other?**

- **At issuance, no — and this is a core rule, not an adapter convention.**
  `issue_policy` stage 5 enforces *both* `declared_content_digest == policy_body_digest`
  *and* `coordinate.content_digest == policy_body_digest`
  (`core/issuance.py`, the two `PolicyDigestMismatchError` raises). `[V]` On a genuinely
  issued record all three values are byte-identical, and an artifact declaring a
  well-formed but wrong `content_digest` is refused with `PolicyDigestMismatchError`
  (script `q123.py`, outputs C–G).
- **At resolution, `[G]` the coordinate-side equality is NOT re-enforced.**
  `resolve_policy` checks `recomputed == declared_content_digest` and
  `recomputed == record.policy_body_digest`, but never
  `coordinate.content_digest == recomputed`. `[V]` A registered record whose coordinate
  carries `content_digest = "b"*64` while its body digest is
  `3b01508f…` resolves `RESOLVED/RESOLVED`, while `issue_policy` refuses the same artifact
  with *"the artifact's derived coordinate does not carry its computed body digest"*
  (script `q2c.py`).
  **Reachability:** not reachable through the one shipped adapter. `UviPolicyFamilyAdapter`
  derives both from `metadata.content_digest`
  (`adapters/uvi.py::describe`, `uvi_coordinate`), so they cannot diverge. Reproducing the
  gap required a synthetic adapter that deliberately decouples them. It is therefore a
  real defect of the *core resolution contract*, latent under the current adapter set.
  This is why 5B-0B binds `policy_body_digest`, not `content_digest`.

**Which one does Phase 5A's `policy_artifact_digest` correspond to?**

**Neither, and it cannot correspond to either without a format change.** `[V]`

- Policy Authority digests are **bare lowercase 64-hex, explicitly without a `sha256:`
  prefix** (`core/canonical.py` module docstring; measured shape
  `1c57b2e5…`, length 64).
- Phase 5A requires **`sha256:` + 64 hex** and rejects bare hex —
  `is_canonical_digest(<PA digest>)` returns `False`
  (`.../authorization_contracts/canonical.py::_DIGEST_RE`; script `q23.py`, outputs E–H).
  `PolicyTargetBindingReference.__post_init__` calls
  `require_canonical_digest("policy_artifact_digest", …)`, so a Policy Authority digest
  cannot be placed in that field at all.
- The two canonical encoders are not the obstacle. `[V]` For flat integers, an aware
  datetime and a nested list, `sha256_hex(canonical_bytes(obj))` equals Phase 5A's
  `canonical_digest(obj)` after stripping `sha256:`; they diverge only on Unicode posture,
  where Policy Authority *rejects* non-NFC and Phase 5A accepts it (script `q2b.py`).
  The obstacle is (i) the prefix and (ii) the **frame**: `framed_body_digest` hashes an
  envelope, not the bare projection.
- Independently, the Phase 5A fixture's value is
  `canonical_digest({"policy": policy_id, "v": policy_version})`
  (`tests/conftest.py:278`) — a placeholder that binds no policy body at all. That is a
  property of the fixture, not of the contract, and is noted only to prevent it being read
  as one.

**Consequence.** A 5B-0B proof cannot be delivered by populating Phase 5A's existing
`policy_artifact_digest` field. Together with D-5B0B-3, this is what decides D-5B0B-6.

**Rejected:** (a) treating `content_digest` as the content binding — the resolution gap
above makes that unsound at the contract level `[V]`; (b) carrying both digests in the
proof "for compatibility" — two digests that a core rule already forces equal at issuance
invites a consumer to check the weaker one.

---

## D-5B0B-3 — How the complete coordinate is bound, and whether Phase 5A can name one

**Decision.** The issuance signature covers the **entire** coordinate. Phase 5A's frozen
binding **cannot name a coordinate**, and that fact — not preference — decides D-5B0B-6.

**The signed payload, enumerated.** `[V]` The exact keys of
`IssuedPolicyRecord.signing_payload()`, decoded from the framed bytes after the
`\x00` domain separator (script `q123.py`, outputs A and B). Domain prefix:
`ugence.policy-authority/issuance/v1`. **21 keys:**

`adapter_id`, `approval_digest`, `approval_ref`, `approving_authority_id`,
`authority_protocol`, `authority_protocol_id`, `authority_protocol_version`,
`canonicalization`, `content_digest`, `domain`, `issued_at`, `issuing_authority_id`,
`key_id`, `policy_body_digest`, `policy_family`, `policy_id`, `record_id`, `scope`,
`signature_alg`, `tenant_id`, `version`.

**Coordinate coverage.** All six coordinate components — `policy_family`, `policy_id`,
`version`, `content_digest`, `scope`, `tenant_id` — appear as top-level signed keys. The
rule the code establishes: `_coordinate_fields(coordinate)` is spread into the signed body
by `core/payload.py`, so *every* field of `PolicyCoordinate` is signature-covered by
construction, and adding a coordinate field would extend coverage automatically rather
than leaving an unbound field. `[V] + [I]` — measured for the current six fields, inferred
for future ones from the `body.update(_coordinate_fields(...))` construction.

**Can Phase 5A's frozen binding name a coordinate?** `[V]` No. Comparing
`dataclasses.fields()` of both types, with renames credited
(`policy_id`→`policy_id`, `version`→`policy_version`,
`content_digest`→`policy_artifact_digest`) (script `q23.py`, outputs A–D):

| Coordinate component | Carried by `PolicyTargetBindingReference`? |
|---|---|
| `policy_id` | yes (`policy_id`) — measured |
| `version` | yes (`policy_version`) — measured |
| `content_digest` | field exists (`policy_artifact_digest`) but is **format-incompatible** — measured (D-5B0B-2) |
| `policy_family` | **no** — measured |
| `scope` | **no** — measured |
| `tenant_id` | **no** — measured |

Three of six components are absent, and the fourth cannot hold a Policy Authority digest.
Since every component participates in identity and exact-match lookup is the only lookup
the registry performs (`core/registry.py` module docstring), a reference missing three
components **cannot address a policy version** — it is not a partially-specified
coordinate, it is not a coordinate.

A second, independent blocker: the binding's `policy_signature` is unverifiable from the
binding's own fields. The issuance signature covers 21 keys including `record_id`,
`adapter_id`, the three approval fields, `issued_at` and the three protocol constants —
none of which the binding carries. `[I]` from the key list above compared against the
binding's twelve fields; no command can verify a signature whose payload cannot be
reconstructed.

**Rejected:** treating `policy_issuer` + `policy_key_id` as a sufficient stand-in for
family/scope/tenant. They name *who signed*, not *what was signed about whom*; a
tenant-scoped policy and a global policy of the same id and version are different
coordinates with the same issuer.

---

## D-5B0B-4 — Who supplies and controls the policy trust anchor `[R]`

**Recommendation: option (a) — verify through Policy Authority's own `PolicyKeyRing`.**
This is the fork the roadmap does not name, and the decision the owner must ratify.

**The measured asymmetry that drives it.** `TrustAnchorRecord` has **no tenant field, by
ratified refusal**: *"Tenant, system and domain restrictions are deliberately not fields …
No ratified clause additionally scopes a key to a tenant, and inventing one would mint an
entitlement model the ADR has not ratified — DD-3's neighbouring question about entitlement
is explicitly still open"*
(`packages/trusted-evidence-authority/src/ugence_trusted_evidence_authority/authority/trust.py`,
`TrustAnchorRecord` docstring). `PolicyVerificationKey` **has** `tenant_id`, and
`PolicyKeyRing.verify` enforces it: a tenant-bound key serving another tenant returns
`WRONG_TENANT` (`core/signing.py`). `[V]` from source read of both, plus the
`resolve_policy` call site passing `expected_tenant_id=coordinate.tenant_id`.

Option (b) would therefore either (i) drop tenant binding on the policy signing key, or
(ii) add a tenant field to `TrustAnchorRecord` — reopening a question TEV explicitly
declared unratified. Neither is acceptable for an artifact whose whole subject is
"valid **for this tenant**".

**Second asymmetry: entitlement granularity.** `KeyEntitlement` separates `ISSUE_POLICY`
from `REVOKE_POLICY`, and `verify_revocation_record` requires the latter
(`core/revocation.py`). TEV's `TrustAnchorCapability` is **single-valued per anchor** by
design, so expressing "may issue but not revoke" would require two disjoint capability
members and two anchors, duplicating a distinction Policy Authority already models on one
key.

**Is two trust systems in one authorization path a defect?** No — it is correct separation
of concerns, and specifically because the two systems answer questions with different
owners. TEV's `CLOUD_SCALING_RECOMMENDATION_ATTESTATION` anchors say *"this key speaks for
this recommendation producer"*; Policy Authority's ring says *"this key speaks for this
policy-issuing authority, for this tenant, with this entitlement"*. They are different
principals with different rotation authority. Collapsing them would place policy-issuance
key control under the evidence authority's operators, which no ratified clause supports.
The defect to guard against is not two systems — it is two systems *for the same
question*, which this is not.

**Rotation and revocation, per option.**

- (a) Policy Authority: rotation is `PolicyKeyRing.with_key()` returning a **new** ring —
  the ring is immutable and `__setattr__` raises; key revocation is
  `PolicyVerificationKey.revoke()` returning a revoked copy, checked before authority,
  tenant, entitlement and window in `PolicyKeyRing.verify`. The owner is the policy
  authority operator. `[V]` from `core/signing.py`.
- (b) TEV: `disabled` (administrative, reversible) and `KeyRevocation` (dated, terminal),
  plus a half-open `effective_from`/`effective_to` window, owned by the evidence-authority
  operator. `[V]` from `TrustAnchorRecord` docstring and fields.

**Composition-root cost.**

- (a) A new 5B-0B package declares `ugence-policy-authority`. Measured cost: that
  distribution declares `dependencies = ["ugence-uvi-policy-contracts>=0.1.0"]`
  (`packages/policy-authority/pyproject.toml:40`), and `api.py:15` imports
  `.adapters.uvi`, so the UVI contracts arrive transitively even though Cloud Scaling
  would register its own capacity-bounds adapter. `[V]` The core itself is clean —
  no `core/*.py` module imports a UVI or contracts symbol `[V]`
  (`grep -rn import src/ugence_policy_authority/core/*.py | grep -i 'uvi|contracts'` →
  empty). The deployment must also wire a ring, an adapter registry and an `as_of`.
- (b) Adds one `TrustAnchorCapability` member and reuses the resolver 5B-0A already wires,
  so the composition root gains nothing new — but the deployment must then *separately*
  reproduce tenant binding and the issue/revoke split outside the anchor, which is where
  the saving is spent.

**Residual for the owner `[R]`.** If the owner's operating model puts policy signing keys
and evidence keys under one custodian, option (b)'s single trust store may be worth the
two costs above. That is an organizational fact this repository does not settle, and it is
the ratification this document is blocked on.

**Rejected:** a third option — a 5B-0B-local key store — was considered and rejected
without further analysis: it would be a third trust system for a question two existing
ones already own.

---

## D-5B0B-5 — How revocation and validity enter the proof

**Decision.** Policy authenticity means **"is valid now"**, judged at an **injected
`as_of`** supplied by the caller. 5B-0B introduces no clock.

**Why "is valid now" rather than "was validly issued".** "Was validly issued" is
`IssuedPolicyRecord` plus a signature check, and D-5B0B-1 already rules that insufficient.
More directly: the same registered record yields different answers at different instants
with nothing else varying. `[V]` One record, one registry, one ring — `as_of` before
`effective_from` gives `UNRESOLVED/NOT_YET_EFFECTIVE`; `as_of` inside the window gives
`RESOLVED`; `as_of` at or after a verified `revoked_at` gives `UNRESOLVED/REVOKED`
(script `q123.py`, outputs N, H, K).

**The instant, and how it is injected.** `as_of` is a required, timezone-aware parameter of
`resolve_policy`; a naive datetime is refused by `require_tzaware`. `[V]` No wall-clock
read exists anywhere in the Policy Authority source: `grep -rn
'datetime.now\|utcnow\|time.time\|date.today' packages/policy-authority/src` returns
nothing (script `q123.py`, output O), and the package carries a
`tests/packaging/test_no_system_clock.py` guard. 5B-0B inherits this posture unchanged: its
verification entry point takes `as_of` as a required argument, exactly as
5B-0A's verifier does.

**What the injected instant is judged against.** Five independent temporal gates, in
`resolve_policy`'s fixed order: the signing key's `not_before`/`not_after` window; the
artifact's `effective_from`/`effective_to` half-open interval; the revocation instant; and
— when an `approval_verifier` is supplied — approval re-verification at `as_of`.
The lifecycle check is independent of all of them: *"a lifecycle label can never override
time, and a valid time window can never override an invalid lifecycle"*
(`core/resolution.py`).

**Whose clock supplies `as_of` is not settled here `[R]`.** 5B-0A had the same shape and
left it to the composition root. The residual is now sharper, because 5B-0B's answer is
time-dependent in five places rather than one: an authorization evaluated at an attacker-
chosen `as_of` can resolve a revoked or not-yet-effective policy. Binding `as_of` to a
trusted time source is **not** in 5B-0B's scope and is named here as an open residual for
5B-2's envelope issuance.

**Rejected:** (a) "was validly issued" — makes revocation unrepresentable in the proof,
and `PolicyRevocationRecord` exists and is signed, so the authority already models it;
(b) reading a clock inside 5B-0B — breaks determinism and contradicts the guard test both
neighbouring packages already ship.

---

## D-5B0B-6 — How Phase 5A receives the richer proof

**Decision.** The verified policy proof travels **alongside** the candidate, in a new
package, exactly as 5B-0A's `ProducerAttestationV2` does. Phase 5A stays at `0.1.0`,
unmodified. A successor contract/schema for `PolicyTargetBindingReference` is **not**
adopted now.

**The measurement that decides it.** `[V]` (script `q6.py`)

| Option | Frozen digests that move |
|---|---|
| (a) widen `PolicyTargetBindingReference` in place with `policy_family`, `scope`, `tenant_id` | **2** — `FROZEN_POLICY_BINDING_DIGEST` `sha256:8961f6b2…` → `sha256:73104271…`; `FROZEN_CANDIDATE_DIGEST` `sha256:db72ffff…` → `sha256:e17ea3fc…` |
| (b) carry the proof alongside the candidate | **0** — all ten recomputed live and matched their pinned constants |

Option (a) moves two because `digest_payload()` embeds
`policy_binding.to_canonical_dict()` **whole**
(`.../candidate.py:144`), so any added binding field propagates into the candidate digest.
A third movement follows structurally: `binding_digest` is self-validating over
`binding_payload()`, so a new field must enter `binding_payload()` to be
signature-relevant, which moves `binding_digest` too `[I]`.

**Option (b) has a merged precedent, not just a design argument.** `[V]` PR #1448 (5B-0A,
`e49db558`) changed **zero** files under
`packages/integration/cloud-scaling-authorization-contracts` — the `git diff --name-only`
across that merge returns nothing for that path. The pattern is proven to require no Phase
5A change at all.

**What option (b) costs, stated plainly.** The proof is not inside the candidate digest, so
a candidate and its policy proof are two artifacts a consumer must be given together and
must re-check together. That is the same residual 5B-0A carries and is 5B-1/5B-2's to
close, not 5B-0B's. It is a known cost, chosen over moving a frozen digest.

**Rejected:** (a) widening the frozen type — moves two pinned digests and a third
structurally, against a rule the task states and this document adopts: prefer the option
that moves none `[V]`; (c) a versioned successor
`PolicyTargetBindingReferenceV2` inside the Phase 5A distribution — moves no digest, but
publishes a second binding type from a package frozen at `0.1.0` and forces every consumer
to branch on which one it received, for no gain over (b) at this phase. It remains
available to 5B-1 if scope repair needs the binding *inside* the candidate.

---

## What the combination establishes — and what it does not

5B-0A's residual makes this load-bearing. `[V]` The existing, passing property
`test_one_attestation_verifies_against_any_candidate_agreeing_on_the_five_facts`
(A-59, `packages/integration/cloud-scaling-producer-attestation/tests/test_adversarial.py`;
`python3 -m pytest tests/test_adversarial.py::test_one_attestation_verifies_against_any_candidate_agreeing_on_the_five_facts -v` →
1 passed) measures that one genuine producer attestation verifies against candidates
carrying a **different policy binding**, a **different execution target scope** and
**different permitted magnitude bounds** — the attestation is bound to the recommendation,
not the candidate.

**Together, a verified producer attestation and a verified policy proof establish:**

1. a trusted producer, at a named coordinate, signed **this exact recommendation** —
   recommendation id and digest, tenant, subject and subject type (5B-0A);
2. an authoritative policy issuer, under configured policy trust, signed **this exact
   policy version** — the complete coordinate and the framed body digest — and that
   version was un-revoked, lifecycle-active and inside its effective period at the
   evaluated instant (5B-0B).

**They still do not establish:**

- **that the two are about the same thing.** Each is separately genuine; nothing yet binds
  the verified policy proof to the recommendation, the execution target scope, or the
  candidate. That binding is 5B-1's decision-scope repair. This is the direct successor to
  A-59's residual, narrowed but not closed.
- **that the bounds the candidate carries are the bounds the verified policy states.**
  `max_permitted_magnitude` and `max_permitted_delta` reaching the candidate from the
  verified policy body is bound-extraction work, not authenticity work.
- **that the caller may act.** Neither proof is an authorization. `resolve_policy`
  performs no caller authorization at all
  (`core/resolution.py` module docstring). Envelope issuance is 5B-2.
- **that `as_of` is honest** — D-5B0B-5's open residual.

**The pair is two verified facts, not a permission.**

---

## What 5B-0B will not establish

Stated once, as boundary rather than caveat: authorization; envelope issuance or signing;
decision-scope repair; bound extraction from the policy body into the candidate; caller
entitlement; a trusted clock; ActionGate admission; credentials; execution; effect
verification; production policy persistence (`InMemoryPolicyRegistry` is explicitly
reference-grade, `core/registry.py`).

## Open residuals

| # | Residual | Owner |
|---|---|---|
| R-1 `[R]` | D-5B0B-4: whether policy signing keys and evidence keys share a custodian — decides option (a) vs (b) | Owner |
| R-2 `[R]` | Where `as_of` comes from and what makes it trustworthy (D-5B0B-5) | 5B-2 |
| R-3 `[G]` | `resolve_policy` does not re-enforce `coordinate.content_digest == policy_body_digest`; latent under the shipped UVI adapter, reproducible with a synthetic one | Policy Authority |
| R-4 | Binding the verified policy proof to the recommendation and target scope | 5B-1 |
| R-5 | Structured successor references remain unsupported; a non-empty `supersedes_ref` fails closed at both issuance and resolution | Policy Authority |
| R-6 | Undeclared `requests` dependency in Cloud Scaling Operations — tracked separately as a maintenance PR, not addressed here | Separate |


---

## Appendix — reproducing the two load-bearing measurements

Both run from a bare checkout with `pytest` and `numpy` importable. Neither writes to the
repository.

**A. The 21 signed-payload keys (D-5B0B-3).** From `packages/policy-authority`:

```python
import pathlib, sys, json
P = pathlib.Path("packages")
for p in ("policy-authority/src", "governance-contracts/src", "uvi-policy-contracts/src"):
    sys.path.insert(0, str(P / p))
sys.path.insert(0, str(P / "policy-authority/tests"))
from ugence_policy_authority.api import (InMemoryPolicyRegistry, KeyEntitlement,
                                         PolicyKeyRing, default_uvi_adapters)
from _authority_fixtures import (Authority, RecordingApprovalVerifier, make_policy,
                                 make_signer)
signer = make_signer()
ring = PolicyKeyRing([signer.verification_key(entitlements=(KeyEntitlement.ISSUE_POLICY,))])
auth = Authority(signer=signer, revocation_signer=signer, key_ring=ring,
                 registry=InMemoryPolicyRegistry(), approval=RecordingApprovalVerifier(),
                 adapters=default_uvi_adapters())
record = auth.issue(make_policy())
prefix, _, body = record.signing_payload().partition(b"\x00")
print(prefix.decode(), sorted(json.loads(body.decode())))
```

**B. Which frozen digests move (D-5B0B-6).** From
`packages/integration/cloud-scaling-authorization-contracts/tests`:

```python
import sys, pathlib, runpy
TESTS = pathlib.Path.cwd(); runpy.run_path(str(TESTS.parent / "conftest.py"))
sys.path.insert(0, str(TESTS))
from conftest import (build_projection, build_decision, build_attestation,
                      build_target_scope, build_policy_binding)
from ugence_cloud_scaling_authorization_contracts import build_capacity_authorization_candidate
from ugence_cloud_scaling_authorization_contracts.canonical import canonical_digest
proj = build_projection(); dec = build_decision(proj)
att = build_attestation(recommendation_digest=proj.recommendation_digest)
scope = build_target_scope(proj); binding = build_policy_binding(scope)
cand = build_capacity_authorization_candidate(projection=proj, decision=dec,
    producer_attestation=att, policy_binding=binding, target_scope=scope)
wide = {**binding.to_canonical_dict(), "policy_family": "capacity-bounds",
        "policy_scope": "TENANT", "policy_tenant_id": proj.tenant_id}
moved = canonical_digest(wide)
print(binding.digest(), "->", moved)
print(cand.candidate_digest, "->",
      canonical_digest({**cand.digest_payload(), "policy_binding": wide,
                        "policy_binding_digest": moved}))
```

The resolution-gap probe (R-3) requires a synthetic non-conforming
`PolicyFamilyAdapter` whose descriptor coordinate carries a `content_digest` other than
`descriptor.body_digest()`; registering a hand-assembled, correctly-signed record under it
and calling `resolve_policy` returns `RESOLVED/RESOLVED`, while `issue_policy` on the same
artifact raises `PolicyDigestMismatchError`.
