# ugence-benchmark-registry-authority — BR-2C candidate (0.3.0rc1)

**Registry and exact-resolution contracts, the non-authoritative lifecycle
kernel, and the BR-2C candidate verifier.** The authority/registry layer of the
shared, platform-wide Benchmark Registry, sitting **above** the frozen identity
layer [`ugence-benchmark-registry`](../benchmark-registry) and never inside it.

> **Candidate, not release.** `0.3.0rc1` is a candidate version ratified by the
> owner as a candidate only. The verifier it ships has been engineered and
> tested; it has **not** been independently reviewed or externally audited, and
> nothing here says otherwise. `0.3.0` — BR-2C's closure — waits on the D-38
> independent external cryptographic reviewer being named and the review
> commissioned and completed (D-32(4), D-38(i)).

Internal platform infrastructure. Not a customer-facing module, not a product,
and not a UVI engine. It computes nothing: no observation, no benchmark result,
no comparison, no readiness, no ROI.

> **Contracts, pure validation, planning, and one verifier.** Nothing in this
> package executes a registry operation. There is no admission engine, storage
> implementation, trust-anchor store, clock read, resolver, convenience
> resolver, selection API, supersession implementation, adapter registry,
> identity allow-list or production composition root. The candidate verifier
> establishes cryptographic verification of one envelope against one anchor
> revision at one caller-supplied instant, and nothing else: it cannot admit,
> register, revoke or resolve. Every other capability that does not exist is
> **unrepresentable in the type surface**, not merely unimplemented.

---

## The two layers

```
ugence-governance-contracts 0.3.1        leaf — depends on nothing
        ▲
ugence-benchmark-registry 0.1.0          FROZEN — zero runtime dependencies,
        ▲                                contracts only, BR-1 identity layer
        │  BR-2 depends on this and nothing else
        │
ugence-benchmark-registry-authority
  0.1.0  (BR-2A)  deps: ugence-benchmark-registry ==0.1.*   + stdlib
  0.2.0  (BR-2B)  deps: unchanged
  0.2.1  (BR-2C-0) deps: unchanged — BR-2C's contracts, no BR-2C capability
  0.2.2  (BR-2C-0) deps: unchanged — D-34's anchor-resolution outcome
  0.2.3  (BR-2C-0) deps: unchanged — D-35's verified-result refusal subset
  0.3.0rc1 (BR-2C-RC) deps: + the D-41 pair (cryptography, PyNaCl), imported
                    only inside verifier.py — the CANDIDATE verifier
  0.3.0  (BR-2C)  deps: unchanged — the same verifier, after independent review
  0.4.0  (BR-2D)  deps: + a durable backend named only after ADR DD-10
  0.5.0  (BR-2E)  deps: + whatever operations require, and nothing sooner
```

The frozen layer stays frozen. This package adds no BR-1 field, changes no BR-1
digest, appends no member to BR-1's frozen refusal enum, and never mutates a
stored BR-1 canonical artifact or its identity digest.

## Milestone boundary

| Subphase | Version | Ships | Status |
| --- | --- | --- | --- |
| BR-2A | `0.1.0` | Registry and exact-resolution **contracts** | shipped |
| BR-2B | `0.2.0` | **Non-authoritative lifecycle kernel**: transition validation, predecessor checks, terminality, conflict and idempotency calculation over *caller-asserted* state. **No store, no verifier, no clock, no append path, no authority-issued result** — it cannot admit, register, revoke or resolve | shipped |
| BR-2C-0 | `0.2.1`, `0.2.2`, `0.2.3` | **BR-2C's ratified contract surface, and no BR-2C capability.** A version rung, not a subphase (ADR §35.2 **D-33**, **D-36**): `api.__all__` 93 → 108 across the three versions | shipped |
| **BR-2C-RC** | `0.3.0rc1` | **The BR-2C candidate head.** `BenchmarkEd25519Verifier` — the three verification seams on the D-41 pair inside one dedicated module — and `BenchmarkDenyAllVerifier`, the exact deny-all default; the D-42/D-43 identifier grammar at construction; `api.__all__` 108 → 110. A version rung, not a subphase; the twelve BR-2C capability tokens unlock here and nothing else moves | **this release — candidate only; not reviewed, not audited** |
| BR-2C | `0.3.0` | BR-2C's closure: the same verifier after the D-38 independent external cryptographic review and D-32(4)'s external audit are commissioned, completed and recorded. The composition-root trust-resolver adapter and key entitlements stay with the composition root (D-04) | blocked on the D-38 reviewer being named and the review completed |
| BR-2D | `0.4.0` | Durable registry authority: persistence, the trusted clock, compare-and-set transitions, immutable event history, the process-local in-memory adapter, registry-event signing, and the **first authoritative** admission, registration, revocation and exact resolution. Closes with the identity-locked composition root | blocked on ADR DD-10 |
| BR-2E | `0.5.0` | Production composition and operations: tenant authorization, service APIs, deployment controls, migrations, backup/recovery, observability, audit export | blocked on BR-2D |

## The two lifecycles, never merged

|  | BR-1 embedded lifecycle | BR-2 registry lifecycle |
| --- | --- | --- |
| Type | `BenchmarkLifecycleState` | `BenchmarkRegistrationState` |
| Owner | the artifact's author — a self-declaration | the registry — an observed, appended fact |
| Members | `AUTHORED · APPROVED · REGISTERED · REVOKED` | `SUBMITTED · ADMITTED · REGISTERED · REVOKED · REJECTED` |
| Evidential weight | **none** — a lifecycle enum on the artifact is not approval evidence | authoritative for resolvability, from BR-2D onward |
| Mutability | frozen and digest-bound | append-only events; no record is ever edited |

The two share the spellings `REGISTERED` and `REVOKED`, and because both are
`str`-valued enums those members **compare equal**. That is exactly why there is
**no automatic bridge**: no conversion helper, no field-name equality and no
enum-value equality turns one into the other, and every boundary in this package
uses `type(x) is Expected` rather than equality. A package test asserts the
absence of any such helper.

## One structural representation per transition

```
initial ──▶ SUBMITTED ──▶ ADMITTED ──▶ REGISTERED ──▶ REVOKED   (terminal)
                 │            │
                 ▼            ▼
             REJECTED     REJECTED
            (terminal)   (terminal)
```

| Transition | Payload | Nests | `prev_event_digest` | Terminal |
| --- | --- | --- | --- | --- |
| — → `SUBMITTED` | `BenchmarkSubmissionRecordPayload` | publisher envelope | **`None`** — the only payload permitted it | no |
| `SUBMITTED` → `ADMITTED` | `BenchmarkAdmissionDecisionPayload` (`declared_outcome=ADMITTED`) | submission record **+** approval envelope | recomputed submission-record digest | no |
| `SUBMITTED` → `REJECTED` | `BenchmarkAdmissionDecisionPayload` (`declared_outcome=REJECTED`) | same | recomputed submission-record digest | **yes** |
| `ADMITTED` → `REJECTED` | `BenchmarkPostAdmissionRejectionEventPayload` | the **`ADMITTED`** admission decision | recomputed admission-decision digest | **yes** |
| `ADMITTED` → `REGISTERED` | `BenchmarkRegistrationEventPayload` | the **`ADMITTED`** admission decision | recomputed admitted-decision digest | no |
| `REGISTERED` → `REVOKED` | `BenchmarkRevocationEventPayload` | registration event **+** revocation envelope | recomputed registration-event digest | **yes** |

`BenchmarkConflictRecordPayload` sits **outside** the linear chain: it records a
refused attempt, nests the submission record it conflicts with, and appends no
successor.

**Every `prev_event_digest` is a derived, read-only property** recomputed from
the exact nested predecessor. There is no caller-supplied upstream digest field
anywhere in the package, and no alternative binding contract or shortened wire
shape — exact nesting is the only permitted representation. Substituting any
upstream object therefore changes every downstream digest by construction rather
than by check.

**Both rejection paths are terminal.** A `REJECTED` admission decision and a
post-admission rejection event are each unnestable by every later lifecycle
payload — the first by a constructor gate, the second by structural absence:
no payload declares a field of that type at all.

## The universal no-authority rule

Every caller-constructible contract permanently derives, as read-only properties
with **no constructor argument, no assignment path and no subclass hook**:

```
authority_verified                    is False
publisher_authenticity_established    is False
approval_authenticity_established     is False
registry_admission_established        is False
trusted_resolution_established        is False
```

Every envelope additionally derives `signature_verified is False` and
`admission_established is False`. Even `object.__setattr__` cannot reach any of
them: a `property` is a data descriptor with no setter, so the write is refused
rather than shadowed.

The authority-bearing names `BenchmarkAdmissionDecision`,
`BenchmarkRegistrationEvent` and `BenchmarkResolution` are **reserved and
undefined**. A caller can build a payload all day and never build a result,
because there is no result type to construct.

## Trusted resolution versus historical inspection

|  | trusted resolution | historical inspection |
| --- | --- | --- |
| Accepts | exact BR-1 locator, and nothing else | exact locator **plus a mandatory `as_of`** |
| `as_of` | **absent** — not optional, not defaulted | required, caller-supplied, disclosed |
| Revoked artifact | never resolves, at any instant (`DENY_ALWAYS`) | visible as history, labelled, never admissible |
| Return shape | `BenchmarkResolutionRecordPayload` | `BenchmarkHistoricalRecordPayload` — a **different exact type** |
| Selection | none. No `latest`, `active`, version selection, implicit default, fallback or coercion exists | none |

Neither payload can satisfy an API expecting the other, and they occupy
different canonical byte spaces, so they cannot be confused at the digest level
either.

## Canonicalization

One encoder, one digest path, reproducing the frozen layer's posture rather than
re-deriving it: a **sealed, closure-held, identity-keyed** contract-type registry
(`cls is RegisteredClass`, never `__name__`, `__module__`, `in`, `[]`, a class's
own `__eq__`/`__hash__`, or a metaclass path); sorted keys; no whitespace;
`ensure_ascii=False`; total field inclusion with explicit `null`; UTC-normalized
microsecond timestamps; aware datetimes only; NFC required and **rejected, never
normalized**; `float`, mappings and `bytes` refused; unknown types fail closed
with no `default=` hook and no `repr()` anywhere.

Graph revalidation runs **before any byte** and walks the whole nested chain at
full depth, **post-order**: every nested node is proved to be an exact registered
class and revalidated before its parent's validator — or any derived property
that validator reads — touches a single one of its fields.

### Twenty-two artifact classes, twenty-two domains, twenty-two pinned vectors

| Contract | Digest domain | Pinned digest |
| --- | --- | --- |
| `BenchmarkPublisherSubmissionEnvelope` | `ugence.benchmark-registry-authority/publisher-submission-envelope/v1` | `7038bc50492921dc655fd425651ee87521d5d4ca06e65f20978db4d46f1f3fe9` |
| `BenchmarkApprovalEnvelope` | `…/approval-envelope/v1` | `6a3874bcfe7d9fc313c5c4baec997a2652143a052147e4959c060dc1f953eba5` |
| `BenchmarkRevocationEnvelope` | `…/revocation-envelope/v1` | `1ffcc23049dd3ca6f5dd1e40cab367d11a873a681b8102d4c1d6d5698856e603` |
| `BenchmarkSubmissionRecordPayload` | `…/submission-record-payload/v1` | `c8a384bf6e14a0c0828c29879a7344358f602a386dfa8ce798d460206b1e9e67` |
| `BenchmarkAdmissionDecisionPayload` | `…/admission-decision-payload/v1` | `4b0c28a34b4c857c462b771d4a44aa43e261541584abc5fa58d06c97d1a7e75a` |
| `BenchmarkPostAdmissionRejectionEventPayload` | `…/post-admission-rejection-event-payload/v1` | `18863811d7670d9bf7b00060acd1a0b06d9ab2167201c7f61c352c4c74f5cb45` |
| `BenchmarkRegistrationEventPayload` | `…/registration-event-payload/v1` | `27419a00b5c57d507507f146dfa6d8c317826baf401cbf08709e8ce98005777b` |
| `BenchmarkRevocationEventPayload` | `…/revocation-event-payload/v1` | `409c730c33b7598a50a70ec7b6d9a6f2e78840b84038b5c8d75d6099c4fe5634` |
| `BenchmarkConflictRecordPayload` | `…/conflict-record-payload/v1` | `3676266f22fbabbc15c795535a982279eee625fb6b55f1b9a455697ab6b0b598` |
| `BenchmarkResolutionRecordPayload` | `…/resolution-record-payload/v1` | `306e45250e98e7d5c5d3b19dc8c2fbda04166aa2960e5162a5dc99ecbb4ef666` |
| `BenchmarkHistoricalRecordPayload` | `…/historical-record-payload/v1` | `10dd79cbe5d56dfce80223c262aefe8a638ae393a8180c56d75e4a8ee0b1c87b` |
| `BenchmarkExactResolutionRequest` | `…/exact-resolution-request/v1` | `a073dc85dde914b19062544f58adb0fa0d2abc89dd9b62079bf8f7a70ae14937` |
| `BenchmarkHistoricalInspectionRequest` | `…/historical-inspection-request/v1` | `0b1d2dfd8fda95d8c7234a8dc0063b788d753f97e23c2b14a5919ef2c758284f` |
| `PlatformRegistryScopeExpectation` | `…/platform-registry-scope-expectation/v1` | `c1d80cf0f2e83d0086f62bb0214d5386c16dd2083726506b0421233052d9dadc` |
| `TenantRegistryScopeExpectation` | `…/tenant-registry-scope-expectation/v1` | `fa12f4dfdb94e0fe76206196d9b880d6a1d11c56c8e7ba7de9aabe475714a543` |
| `BenchmarkRegistrySnapshotAssertion` | `…/registry-snapshot-assertion/v1` | `1d60f269a1e745304fb392f97039b307a5d29076cc39de2337ae4c49aee7554e` |
| `BenchmarkTransitionPlan` | `…/transition-plan/v1` | `83b342bec31fb04c24d7214038e5c257c5ee22c6e5d332fba40978be877c96fd` |
| `BenchmarkTransitionRefusal` | `…/transition-refusal/v1` | `efa9a8e8d79e06e6099126878e0bf78ecaf3a9193a54e71d3de23817cab8ea70` |
| `BenchmarkTrustAnchorRecord` | `…/trust-anchor-record/v1` | `86d2ff9b9edbc2a4acd4a0edb1e54ef221e276a8b55a22fb35009189aee885f4` |
| `BenchmarkPublisherVerifiedResult` | `…/publisher-verified-result/v1` | `7df2cff0f37e0544bebbcd977928fd2d91fd3c30490c053a3788eaf29eaebe0d` |
| `BenchmarkApprovalVerifiedResult` | `…/approval-verified-result/v1` | `7ee8fb68bbbdfbf9715f136ca750d3df1391244c860cf70c3d74074ef4dfabd4` |
| `BenchmarkRevocationVerifiedResult` | `…/revocation-verified-result/v1` | `fb697a58598890cddaedf744236485885904260d79cc14c9f1500dc7921926fa` |

Each vector's exact canonical bytes are committed in
[`pinned_canonical_vectors.json`](pinned_canonical_vectors.json) and every digest
is independently recomputable with plain `hashlib` over the byte string alone,
importing nothing from the package.

The last four rows are BR-2C's ratified **contract surface**, landed in `0.2.1`
under ADR §35.2 D-24, D-25 and D-26: the immutable role-scoped trust-anchor
record the resolution seam returns, and the three distinct exact verified-result
types. At `0.3.0rc1` the verifier those contracts describe **exists, as a
candidate** (see *The candidate verifier* below). It is produced by
`BenchmarkEd25519Verifier` and by the deny-all default, and by nothing else.
**No anchor is held or resolved by this package and no clock is read**: the
anchor directory and the trusted instant are both inputs. D-32 makes an
external cryptographic audit a hard precondition to any production use, and
forbids any artifact here describing the verifier as audited, independently
reviewed or production-ready until that audit is obtained and recorded. None
does.

## The candidate verifier

One module, [`verifier.py`](src/ugence_benchmark_registry_authority/verifier.py),
performs cryptography, and it is the only module permitted to import the D-41
pair. It ships two implementations of `BenchmarkApprovalVerifierPort`:

| Class | What it does |
| --- | --- |
| `BenchmarkDenyAllVerifier` | The **exact deny-all default**. Every seam refuses `NO_TRUST_ANCHOR_CONFIGURED`, consults no directory, admits no key, and has no field to flip. Still binds the envelope digest, the declared signer and the trusted instant, so a deny-all answer is as evidence-bound as any other |
| `BenchmarkEd25519Verifier` | The candidate. Takes an injected `BenchmarkPublisherTrustDirectoryPort`; for each seam it reconstructs the signing input from the pinned `BENCHMARK_SIGNING_FRAME_SPECIFICATION`, resolves the exact `(role, identity, key_id)` triple, evaluates the anchor in D-28's order at the explicit trusted instant, admits the key only after libsodium's strict point check, applies RFC 8032's `S < L`, and verifies with the signature backend |

What a refusal looks like, and where it comes from:

| Condition | Result |
| --- | --- |
| Directory has no anchor at the triple / cannot be consulted | `TRUST_ANCHOR_NOT_FOUND` / `TRUST_DIRECTORY_UNAVAILABLE`, no revision bound |
| Directory raises, returns the wrong type, or answers a different triple | `INDETERMINATE` — never a fallback (D-28) |
| Anchor revoked / disabled / not yet valid / expired, in that order | the matching `TRUST_ANCHOR_*`, **with** the anchor revision bound |
| Key material is the identity, a small-order point, or a non-canonical encoding | `INDETERMINATE`, with the revision bound — refused at admission, before the signature backend sees it |
| Signature malformed, `S ≥ L`, or does not verify | `SIGNATURE_INVALID` |
| A contract error with a reason outside D-35's twelve, or none | `INDETERMINATE` (D-42(d)) |
| A non-envelope, or a naive trusted instant | **raises** `BenchmarkRegistryContractError` before evaluation — a caller's contract violation, not external trust state (D-42(a)) |

Why two backends: measured on this pair, the signature backend alone accepts a
key-less forgery under five of the twelve strict-corpus keys — the identity
point, its non-canonical encoding, the order-2 point, one order-4 point and a
`y ≥ p` encoding. The point check refuses all twelve. That measurement is a
standing test, not a citation.

What it is not: not reviewed, not audited, not wired to a composition root
(none exists before BR-2D), and not a signer — the module imports no signing
primitive, and a gate asserts it. The only private keys anywhere are fixed-seed
**test** keys in `tests/contract/test_verifier.py`; the probe harness carries
three pinned public keys and three pinned signatures as literals and imports no
cryptographic library at all.

The three **nested-admissible-only** classes — `BenchmarkCoordinate`,
`BenchmarkScope`, `BenchmarkApplicabilityCoordinate` — may appear inside a BR-2
graph but own **no** BR-2 domain and are refused as canonicalization roots. A
BR-1 identity must keep exactly one digest: the one BR-1 computes.

## Four-party separation

D-02's separation is enforced in constructors, at the first point each pair of
identities becomes mechanically reachable — never documented for a later engine
to remember:

| Contract | Refuses |
| --- | --- |
| `BenchmarkApprovalEnvelope` | approver == publisher |
| `BenchmarkSubmissionRecordPayload` | registry authority == publisher |
| `BenchmarkAdmissionDecisionPayload` | registry authority == approver |
| `BenchmarkRevocationEventPayload` | revoker == registry authority |

Distinctness is not authenticity: four distinct identities are four
*declarations*, none verified. The composition root — the fourth party — is
never represented as an issuer or a signer in any payload.

## Two refusal vocabularies, provably disjoint

BR-1's seventeen refusal reasons are frozen; BR-2 **appends and never inserts,
renames, re-values, re-orders or removes**. `BenchmarkRegistryRefusalReason`
holds twenty-four BR-2 reasons, disjoint from BR-1's by member *and* by value.

`BENCHMARK_REGISTRY_ALL_REFUSAL_REASONS` is the ordered composite (41 members).
Its BR-1 prefix is taken from `tuple(BenchmarkRefusalReason)` — iterating the
*enum*, which yields declaration order — and explicitly **not** from
`BR1_BENCHMARK_REFUSAL_REASONS`, which is a `frozenset` whose iteration order is
a hash artifact. An import-time guard asserts the two agree, so they cannot
drift without this package failing to import.

Every reason maps to exactly one of seven `BenchmarkRegistryFaultClass` members;
the mapping is total, and `fault_class_for` raises rather than guessing.

## Verification

```bash
# suite, probes, ratio
python -m pytest packages/benchmark-registry-authority/tests -q
PYTHONPATH=packages/benchmark-registry-authority/src:packages/benchmark-registry/src \
    python packages/benchmark-registry-authority/adversarial_probes.py

# build, offline install, negative controls, source/wheel/sdist parity
python packages/benchmark-registry-authority/verify_benchmark_registry_authority_distribution.py

# the frozen BR-1 layer is unchanged
python packages/benchmark-registry-authority/verify_br1_freeze_matrix.py

# gate inventory and measured gate-deletion mutation sweep
python packages/benchmark-registry-authority/gate_mutation_sweep.py
```

### Measured results at this revision

**Re-measured, not edited.** Every number below was produced by executing the
named check against this tree at `0.3.0rc1` — never by adjusting the figures
that stood here.

**Nothing checks these figures.** No test, probe, verifier, sweep or generator
compares a number in this table against a run. What attests them is the run
recorded in the commit that states them, and the discipline of re-running rather
than editing. That is weaker than a gate, and is said here rather than left to be
assumed: a stale figure in this table would survive until someone re-ran the
checks and noticed.

**This file is not unread, though.** `pyproject.toml` sets
`readme = "README.md"`, so setuptools embeds the **whole** of it — this paragraph
and the table below included — in the built distribution's `METADATA`, and
[`verify_benchmark_registry_authority_distribution.py`](verify_benchmark_registry_authority_distribution.py)
substring-scans that blob for dependency names beyond the ratified three it
lists in its own source. **Prose written here can turn a distribution check
red.** The only place any check parses a document directly is BR-1's own
`README.md`, where it looks for pinned digests.

| Check | Result |
| --- | --- |
| Package suite | **2256 tests passed**, 1 pre-existing failure (`test_no_package_in_the_monorepo_imports_this_one`: another package's boundary test names this package by string; red on the default branch too) |
| Independent adversarial probes | **93 passed** (also inside the installed wheel) |
| Distinct properties | **558 adversarial : 41 happy = 13.61 : 1** (required ≥ 2:1) |
| Gate inventory | **72 gates** |
| Mutation sweep | **67 KILLED, 5 SURVIVED, 0 errored** — every survivor classified; the same five as at `0.2.3` |
| Distribution | wheel + sdist built; `--no-index` install from a local wheelhouse holding BR-1 and the D-41 pair verified |
| Negative controls | **8 run, 8 caught** |
| pyflakes | clean |

The five survivors are recorded in [`gate_inventory.json`](gate_inventory.json)
with their classifications: four are **shadowed** (an earlier gate refuses the
same input first, and the shadowing gate is named), and one is **equivalent**
while BR-1 is frozen. **Production behaviour was not changed to reduce that
number**; where a survivor became KILLED it was by adding a test for a
requirement the ratification already stated, never by editing the package.

## Consistency, and the absent flag

BR-2 claims **process-local atomicity and read-after-write behaviour, and
nothing more**. Durability, multi-process coordination, distributed strong
consistency, eventual-consistency safety and cross-process atomic revocation are
**explicitly disclaimed in the contract**, as typed properties a consumer can
read.

`BenchmarkRegistryStoreConsistencyDescriptor` carries one field — a closed
`BenchmarkRegistryConsistencyScope` with exactly one ratified member — and
derives all seven answers from it. **There is no flag to set, because there is
no flag**, and an over-claiming descriptor is *unconstructible*: there is no
`DURABLE` scope member to pass.

The ratified production-adapter admission requirement — an allow-list checked by
interpreter identity, raising `BenchmarkRegistryCompositionError` for anything
else — is **stated here and implemented nowhere in this distribution**.

## Confusable coordinates — rejection only, honestly empty

`BENCHMARK_CONFUSABLE_COMPARISON_CONTRACT` records what is compared (the exact
nine-element BR-1 identity tuple), against what, and what the refusal means.
Normalization is `EXPLICITLY_PROHIBITED`: the canonical locator and the stored
bytes are never casefolded, NFKC-normalized or otherwise rewritten — only
compared and refused.

`algorithm_identifier` and `unicode_version` are **`None`**, and the
completeness claim is **`NONE`**. No complete Unicode-confusable algorithm is
claimed at this version. A partial implementation presented as complete would
leave a consumer believing this class of attack is handled; a declared absence
does not.

## Governance

Ratified in
[`docs/architecture/ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md`](../../docs/architecture/ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md),
decisions **D-01 through D-43**, including their recorded modifications, and
the owner's BR-2C candidate rulings: the D-38 reviewer authority is an
independent external cryptographic reviewer, to be individually named with the
review commissioned and completed before any final `0.3.0`; candidate
engineering and testing may precede that naming; the D-40 release transition
for the candidate rung confines the D-41 pair to the dedicated verifier module
and moves no other prohibition; and `0.3.0rc1` is a candidate version only.
