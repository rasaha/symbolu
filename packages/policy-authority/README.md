# Ugence Policy Authority (`ugence-policy-authority`)

**The shared, platform-wide Ugence Policy Authority.** Internal platform
infrastructure — not a customer-facing module, not a product, and not a UVI
engine. There is exactly **one** Policy Authority in Ugence; this is it.

It owns one technical job: **issuing, signing, registering, resolving,
verifying and revoking policy versions** — for any policy family that registers
an adapter. **UVI policy schemas are its first adapter**, a consumer of the
boundary rather than the owner of it.

Ratified in
[`ADR_UGENCE_POLICY_AUTHORITY.md`](../../docs/architecture/ADR_UGENCE_POLICY_AUTHORITY.md)
(P-1 … P-11), which also resolves §26.1 of the
[UVI ADR](../../docs/architecture/ADR_UGENCE_VALUE_INTELLIGENCE_GV2C_GV2E_GV3R.md)
and upholds its D-1 unchanged.

> **Retired without qualification.** The names `packages/uvi-policy-authority/`,
> distribution `ugence-uvi-policy-authority`, and namespace
> `ugence_uvi_policy_authority` are gone. No compatibility package, alias,
> import shim, or second wheel exists under them, and the old import fails in a
> clean environment.

---

## Role separation

| Role | Owner | This package |
|---|---|---|
| Policy author | human / authoring process | **no** |
| **Approver** | external governance process | **no — verified, never performed** |
| Approval verifier | the composition root's configured trust boundary | consumes it |
| **Issuer / signer** | **this package** | yes |
| **Registry / resolver** | **this package** | yes |
| **Policy-version revoker** | **this package** | yes |
| Runtime authorizer | Risk Authority / ActionGate | **no** |
| Readiness evaluator | `agent-value-readiness` | **no** |
| Financial calculator | `governed-value` | **no** |
| Benchmark-value governance | deferred milestone | **no** |

No row absorbs another. In particular, *approver* and *issuer* are never the
same component for the same policy, and the authority is never a runtime
authorizer — it is consulted **before** runtime, by resolution, and never sits
on the hot path.

---

## Shared core + policy-family adapters

| Generic **core** owns | Policy-**family adapter** owns |
|---|---|
| approval-verification boundary | supported artifact types |
| issuance orchestration | identity & coordinate extraction |
| signing / trust-anchor verification | canonical body projection |
| exact append-only registry | family-specific structural validation |
| trusted resolution | lifecycle / effective-period access |
| policy-version revocation | supersession-field interpretation |
| shared records, statuses, errors, protocols | — |

**The hard boundary.** The core imports no policy family, names no family type,
and contains no `isinstance(..., GeographyPolicy)`-style branch. Adding a second
family means registering a second adapter — with **no** change to issuance,
signing, registry, resolution, or revocation code. Both facts are enforced by
`tests/packaging/test_core_adapter_boundary.py` (AST scan) and demonstrated by
`tests/authority/test_second_adapter.py`, which drives the full lifecycle with a
synthetic non-UVI family.

The core identifies a policy version by a family-neutral `PolicyCoordinate`
(family, id, version, content digest, scope, tenant). The UVI adapter maps its
`PolicyReference` onto one; a future family maps its own.

```python
from ugence_policy_authority.api import AdapterRegistry, default_uvi_adapters

adapters = default_uvi_adapters()              # convenience: UVI only
adapters = adapters.with_adapter(MyAdapter())  # add a family, no core change
```

`default_uvi_adapters()` is a **convenience for the composition root**. The core
depends only on the adapter protocol — a deployment may assemble any registry,
including one with no UVI adapter at all.

---

## Approval remains external

Organizational approval is produced **outside** this package. The authority
**verifies** it; it never creates it and never approves its own policy.

Issuance requires an externally produced approval artifact, verified through an
injected `ApprovalVerifier` that the **composition root selects and trusts**.
The authority then independently re-checks that the verification binds the exact
policy coordinate, body digest, approval artifact and digest, tenant/scope,
approving authority and validity period — and that the approving authority is
**not** the issuing authority. A merely lax verifier is therefore still
constrained.

Explicitly **not** approval, each proven by a test:

- a caller `approved=True` — no such parameter exists;
- a bare authority name — a string names nobody;
- `PolicyLifecycleState.APPROVED_ACTIVE` on the artifact — a self-assertion;
- an evidence-status enum;
- a fabricated duck-typed object that merely *looks* like a verification.

Approval failure occurs **before** signing and **before** any registry
mutation. The only verifier shipped is `DenyAllApprovalVerifier`; no allow-all
verifier and no public test verifier ships anywhere in the distribution.

---

## Canonicalization and the content digest

Versioned and domain-separated. Canonicalization version:
`ugence.policy-authority/canonicalization/v1`.

**Exact encoding.** UTF-8 JSON via `json.dumps` with `sort_keys=True`,
`separators=(",", ":")`, `ensure_ascii=False`; keys sorted lexicographically by
code point; the hash input is exactly those UTF-8 bytes; `sha-256` rendered as
bare lowercase 64-hex. Enums serialize by `.value`. `bytes` are base64url
without padding. Ordered collections preserve order.

**Unicode posture — ADR §12.1 option (a).** Strings must already be **NFC**;
non-NFC input is **rejected**, recursively, including nested fields and mapping
keys. The authority deliberately does **not** silently normalize: folding NFD
onto NFC would map two structurally different artifacts to one digest, so a
signature over one would verify a body nobody signed. The posture is bound to
the canonicalization version.

**Naive datetimes are prohibited, not discouraged.** Every `datetime` must carry
an offset; naive values are refused everywhere, including by direct calls to the
canonicalization helpers. Timezone-aware values normalize to UTC and render
`%Y-%m-%dT%H:%M:%S.%fZ`, so two spellings of one instant are byte-identical.
`float` and unsupported types are rejected.

**The body digest.** The adapter supplies the family-specific projection; the
core frames it with the canonicalization version, the domain tag, the adapter
identity and the exact policy type, then hashes:

```
sha256( canonical_json({
    "canonicalization": "ugence.policy-authority/canonicalization/v1",
    "domain":           "ugence.policy-authority/policy-body/v1",
    "adapter":          <adapter id>,
    "policy_type":      <exact runtime dataclass name>,
    "body":             <adapter projection>,
}) )
```

The UVI adapter's v1 projection removes **exactly one declared path**,
`metadata.content_digest` — **removed, not blanked**, so no sentinel
participates and no fixed-point iteration is needed. Removal is **by path, not
by name**: a nested `content_digest` on a `BenchmarkReference` or a referenced
`PolicyReference` stays bound (proven by test). A policy artifact has no
signature field, so the digest cannot depend on a signature. The declared digest
must equal the computed digest **before** approval verification, signing, or
registration.

**Independent verification.** `canonical_bytes`, `sha256_hex`,
`framed_body_bytes` and `framed_body_digest` are public: a third party holding
the artifact and the adapter projection can recompute and check any digest
without authority internals.

---

## Supersession — v0.1 rejects it at issuance

`supersedes_ref` is an unstructured `str` in the merged contracts; it cannot
bind a complete exact coordinate, and guessing one would be an unsigned
authority decision.

- **Emptiness is defined by `supersedes_ref.strip()`** — absent, empty and
  whitespace-only all mean *no supersession* and issue normally.
- **Any other non-empty value is rejected at issuance** with the stable typed
  reason `SUPERSESSION_REFERENCE_UNSUPPORTED`, **before** approval
  verification, clock use, signing, and any registry access. Nothing from the
  rejected artifact is stored.
- **Blast radius is one artifact**: other versions of the same identity remain
  fully usable, and a clean replacement issues immediately afterwards.
- No string parsing, no version guessing, no "latest" lookup — ever.
- A legacy or hand-assembled record that reaches resolution **fails closed**
  with the same typed reason rather than returning a usable policy.

There is no permissive posture: `SupersessionRule`, `SELF_DECLARED_ONLY` and
`SUPERSESSION_UNDETERMINED` no longer exist. **Structured successor identity
remains deferred** to a separate contract milestone (ADR §13.4).

---

## Revocation

- **A revocation signer is mandatory.** No unsigned revocation record can be
  created through the public service, and `PolicyRevocationRecord` refuses empty
  signature bytes — an unsigned revocation is invalid, not "pending".
- **The issuer is never silently substituted as the revoker**; the revoking
  authority comes from the signer, and a missing signer is an error.
- The record binds the **complete exact coordinate** — family, policy identity,
  version, content digest, scope and tenant.
- A **distinct, versioned, domain-separated** revocation payload is signed.
- The revoking key must be **authorized for that exact policy scope**: known,
  un-revoked, in window, matching authority and tenant, and holding the
  `REVOKE_POLICY` entitlement. A foreign signer with a structurally valid
  signature is rejected.
- **Resolution re-verifies** the signature, key, entitlement, tenant/scope,
  coordinate and instant before applying a revocation. A forged, replayed or
  tampered revocation is **never** treated as valid, and never silently ignored:
  it fails closed as `REVOCATION_INTEGRITY_INVALID`.
- Append-only; identical repeats idempotent; conflicting records rejected.
- **Default historical semantics are deny-always.** With
  `HistoricalResolutionRule.ALLOW_BEFORE_REVOCATION`, an `as_of` strictly before
  the revocation instant may resolve — and the result carries `historical=True`,
  its explicit `as_of`, and `implies_current_validity is False`.
- Policy-version revocation, **signing-key revocation**, and **Risk Authority
  envelope revocation** are three distinct concepts. No envelope epoch is reused.

---

## Trust anchors and the registry

Trust anchors are immutable. `PolicyKeyRing` **defensively copies** every caller
mapping or sequence, stores it behind a `MappingProxyType`, exposes only that
read-only view, and refuses attribute rebinding — so mutating the dict you
passed in, the view you got back, or the ring itself cannot alter trust state
after construction. Keys bind identity, authority, tenant/scope, validity
period, algorithm, key id and entitlements. Private keys never appear in a
record, registry object, serialization, exception or `repr`.

The registry is **reference-grade and process-local**:

- exact-coordinate lookup only — no `latest()`, `current()`, `find_by_id()` or
  partial-id lookup exists, so a floating reference is *unrepresentable*;
- append-only, with issuance and revocation stored separately;
- re-registration is idempotent **only** for a canonically identical record; any
  other reuse of a slot is a typed conflict;
- cross-tenant lookup returns the **same** typed miss as a nonexistent record
  and leaks no other tenant's identifier;
- compound check-and-append sequences are guarded by a process-local re-entrant
  lock, so concurrent threads in this process cannot interleave into a corrupt
  state.

**The in-memory registry is not durable and does not claim to be.** It stays
the process-local test reference and is refused in production mode.

### Durable registry (ADR §15.7, closed under decision D-3)

`SqlitePolicyRegistry` is the single-node durable registry, adopting Benchmark
Registry ruling D-22 Posture B: stdlib `sqlite3`, WAL journal, every append
inside `BEGIN IMMEDIATE`, exact-coordinate lookup only, issuance, revocation and
supersession in three append-only tables guarded by triggers that refuse
`UPDATE` and `DELETE`, and one hash-linked `ledger_events` table so tampering by
a privileged writer is detectable after the fact (`verify_chain()`). It keeps
every rule above: idempotent only for a canonically identical record, typed
conflict for any other reuse of a slot, cross-tenant lookup the same miss, and
successor plus supersession committed as one transaction or not at all.

Rehydration is family-owned. The core defines the `PolicyArtifactCodec` port and
never implements it; `UviPolicyArtifactCodec` rebuilds the five UVI families from
the same canonical structure their body digest is computed over, driven by the
contracts' own type annotations, so trusted resolution succeeds from a cold
start with every digest and signature re-checked. A stored record the configured
codec cannot rehydrate is a `PolicyRegistryStorageError`, never `None`: an
unreadable record is not an absent one.

What each registry claims is a typed declaration, not prose:
`declared_consistency(registry)` returns a `PolicyRegistryConsistencyDescriptor`
whose answers are derived read-only properties of its scope.

| Guarantee | `PROCESS_LOCAL_ONLY` (in-memory) | `SINGLE_NODE_DURABLE` (SQLite) |
|---|---|---|
| process-local atomicity, read-after-write | claimed | claimed |
| durability across restart | disclaimed | claimed |
| multi-process coordination on one host | disclaimed | claimed |
| cross-process atomic revocation | disclaimed | claimed |
| distributed strong consistency | disclaimed | **disclaimed** |
| eventual-consistency safety | disclaimed | **disclaimed** |

There is no replication, no second node, no high availability and no production
key-custody story; a `:memory:` path is refused in production mode. No public
resolution semantics and no signing behaviour changed.

---

## What a resolution proves — and what it does not

Only `resolve_policy` produces an authority-evaluated resolution. It returns a
policy **only** when all of these hold at an explicit, timezone-aware `as_of`:
exact coordinate identity; the artifact re-derives that coordinate; the declared
content digest equals the independently computed body digest; the issuance
signature verifies under an authorized trusted key; the approval proof is valid
under the configured verifier and independently re-checked; no unstructured
supersession; lifecycle is active; `as_of` is inside the half-open
`[effective_from, effective_to)` interval; and any stored revocation verifies
and does not apply. Cross-tenant access discloses nothing. A failed resolution
**never** returns a policy or a trusted record, and `RESOLVED` without a policy
is structurally impossible.

**Construction is not authenticity.** `IssuedPolicyRecord` and
`PolicyResolution` are public dataclasses and remain structurally
constructible — building one proves nothing. **Registry retrieval is not trusted
resolution**: a hand-assembled record reaches every digest, key and signature
check and fails them.

A resolution proves only what the **configured trust roots** attest, at the
**explicit `as_of`** supplied. It does **not** authorize any runtime action, does
not prove organizational truth beyond what the configured verifier attested,
does not prove the policy is correct, lawful, wise, or commercially sound, and —
when `historical` is set — does **not** imply current validity.

`expected_reference_tenant_id` checks the **reference's declared tenant
identity**, not caller entitlement; this authority performs no caller
authorization. A `GLOBAL`-scope coordinate carries the canonical **empty**
tenant component (`GLOBAL_TENANT == ""`) and matches only a request presenting
exactly that.

---

## Issuance order

1. request structure (including that `issued_at` is timezone-aware);
2. adapter/family recognition;
3. exact identity/coordinate derivation;
4. **supersession admissibility**;
5. canonical body digest and declared-digest equality;
6. **approval verification**;
7. lifecycle/effectivity at the explicit issuance instant;
8. signing;
9. record construction;
10. atomic process-local registry append.

Instrumented call-count tests prove: a structural, family, supersession or
digest failure never invokes the approval verifier; an approval failure never
invokes the signer; a signing failure never mutates the registry; and the
registry is byte-identical after a failure at **every** stage. No wall clock, no
random UUID, no environment lookup, no network call, no hidden global state —
the instant is injected and read exactly once, so identical inputs give
byte-identical records.

---

## Dependencies

```
ugence-policy-authority
      └── ugence-uvi-policy-contracts >= 0.1.0   (first family adapter only)
```

Standard library otherwise. `ugence-governance-contracts` is **not** a declared
dependency — nothing here imports it. The authority imports no
`agent-value-readiness`, `governed-value`, Risk/Decision Authority internals,
Agent Runtime, Runtime Assurance, forecasting, or benchmark-value service, and
nothing imports it back. Ed25519 follows the repository's existing stdlib-only
RFC 8032 authority convention, reproduced rather than imported.

## Verification

```bash
python -m pytest packages/policy-authority/tests -q
python packages/policy-authority/verify_policy_authority_distribution.py
python packages/policy-authority/adversarial_probes.py
```
