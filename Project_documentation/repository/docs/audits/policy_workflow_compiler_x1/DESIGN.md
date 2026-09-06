# PA/PWC-X1 — Authoritative Source Linkage: Design

**Status:** design, owner-ratified on both previously open items (X1-A sequencing and
composition-root placement). No source change is authorized by this document.
**Scope:** `packages/tooling/policy-workflow-compiler`, plus the placement of a new
composition layer. **No change to `packages/policy-authority` is required.**

Findings carry `[V]` verified against the repository, `[I]` inferred, `[R]` requires
ratification, `[G]` gap.

## The load-bearing constraint

X1 cannot be implemented as immutable source linkage on `policy_pack.v1` without
breaking the frozen v1 digest. `[V]` Measured: adding `authoritative_source = None`
to the pack payload of the procurement reference moves its release digest off
`sha256:fb9fd4b9…`. `_pack_logical` (`compiler/release.py`) serializes
`pack.model_dump()`, so even a defaulted, absent-valued field is a new key in the
canonical payload.

`[V]` The release manifest is **not** part of the logical payload — its keys are
`policy_pack`, `workflow_ir`, `capability_manifest`, `assurance_manifest`,
`coverage_matrix`, `audit_schema`, `compiler_distribution_version`. Manifest-only
carriage is therefore digest-*safe* but not digest-*bound*, which does not satisfy
the ratified words "immutable linkage".

Both facts point the same way: the binding rides on `policy_pack.v2`.

## Ruling X1-A — sequencing

**PA/PWC-X1 is ratified now as an architectural boundary. Its digest-bound
`AuthoritativeSourceRef` carriage activates only for `policy_pack.v2`.
`policy_pack.v1` remains structurally and digest-byte identical and gains no
unconditional or defaulted authoritative-source field.**

Explicitly prohibited on the v1 logical payload:

```python
logical_payload["authoritative_source"] = None      # PROHIBITED — moves every v1 digest
```

Required shape instead:

```python
if pack.schema_version == "policy_pack.v2":
    logical_payload["authoritative_source"] = ...    # v1 payload unchanged, key absent
```

**Revised implementation order** (amends the order in `../policy_workflow_compiler_ratification/RATIFICATION.md`):

1. PWC ratifications (D1–D5, X1 architecture).
2. **PWC-P3A** — diff-driven review semantics. It touches no source contract, so it
   ships against v1 without approaching a frozen digest.
3. **`policy_pack.v2`** — the first source-contract expansion.
4. **PA/PWC-X1 carriage and validation** — activated by v2.
5. **PWC-P3B** — declarative capability/contract binding validation.
6. **PWC-P3C** — deterministic offline simulation.

## Policy Authority requires no change

`[V]` PA already owns and issues everything X1 needs.

| Concern | PA source |
| --- | --- |
| Exact policy identity | `PolicyCoordinate` (`core/adapters.py:64`) — `policy_family`, `policy_id`, `version`, `content_digest`, `scope`, `tenant_id`; every field participates in identity |
| Issuance, signature, approval linkage | `IssuedPolicyRecord` (`core/records.py:60`) |
| Resolution, current versus historical validity | `PolicyResolution` (`core/records.py:202`) |
| Revocation | `PolicyRevocationRecord` (`core/records.py:134`), signed, targeting a complete coordinate |
| Canonicalization and digests | `core/canonical.py` — `canonical_dumps`, `framed_body_digest` |

`[V]` PA even anticipated cross-package verification: `PolicyResolution` publishes
`descriptor_adapter_id`, `descriptor_policy_type` and
`descriptor_canonical_projection` specifically so "a consumer that holds no adapter
registry can nonetheless recompute `framed_body_digest` … and compare it against
`record.policy_body_digest`", enforced all-three-or-none so that a partially
checkable triple cannot exist. X1 is entirely PWC-side and composition-side work.

The resulting separation:

```text
Policy Authority   = authenticates the policy
PWC                = records exactly which authenticated policy it compiled
```

## `AuthoritativeSourceRef` — PWC-owned contract

Declared with PWC's own primitives (`CompilerModel`, plain strings). PA model types
are never imported; that is what keeps the compiler a leaf distribution.

Three tiers, documented as distinct even while they live in one structure:

### Identity linkage — the binding material

```text
policy_family, policy_id, policy_version, content_digest, scope, tenant_id,
record_id, policy_body_digest
```

### Evidence snapshot — carried for audit and replay

```text
issuing_authority_id, key_id, signature_alg, signature_b64,
approving_authority_id, approval_ref, approval_digest, issued_at,
authority_protocol, authority_protocol_version
```

### Resolution context — temporal interpretation

```text
resolved_as_of, historical
```

`[I]` The tiering matters later: key rotation or an authority-protocol change can
enlarge or alter an evidence snapshot without altering policy identity. Keeping the
tiers semantically separate now avoids conflating "the identity moved" with "the
attestation format moved". This is documentation of intent, not a structural split,
and it does not block X1.

## Carriage and digest participation

- **Pack** (`policy_pack.v2` only): `authoritative_source` on the pack, included in
  `_pack_logical` under the schema-version gate above. This is what makes the linkage
  immutable — the compiled release digest commits to the exact issuance.
- **Manifest**: the coordinate is denormalized into `ReleaseManifest` for offline
  inspection, exactly as `compiler_distribution_version` already is. Manifest values
  are outside the logical digest, so this is convenience, never the binding.
- **`workflow_ir.v2` enrichment**: unaffected. `[V]` `base_ir_digest` is computed
  over ordered nodes and edges, so the v2 fingerprint does not move.

| Output | Effect |
| --- | --- |
| `workflow_ir.v1` release digest | unchanged — `sha256:fb9fd4b9…` |
| `workflow_ir.v1` IR digest | unchanged — `sha256:169ad24c…` |
| `workflow_ir.v2` fingerprint | unchanged — `sha256:2e031c78…` |
| `policy_pack.v2` releases | new digests by construction; no prior artifacts exist |

## PWC attests carriage, not authenticity

This is the design's central rule.

`[V]` Three digest algorithms are in play and none is interchangeable: PA's
`content_digest` / `framed_body_digest` (`core/canonical.py`), PWC's
`compute_pack_digest` (`approval/records.py`), and the release structural digest.
PWC therefore **cannot** confirm that `coordinate.content_digest` describes the pack
it compiled.

It must not try. Importing PA is forbidden by D1; reimplementing PA's
canonicalization is worse, because it creates a second implementation of Policy
Authority semantics that drifts from the first, and drift surfaces as a false
integrity failure on a valid artifact.

What PWC proves:

> This output is immutably bound to the authoritative-source assertion supplied at
> compilation.

What PWC does not prove:

> I independently established that the policy was currently authoritative.

### Diagnostic taxonomy — two vocabularies, never merged

PWC's validation codes must not imply a check PWC did not perform.

| PWC integrity (this package asserts) | PA authenticity (never asserted here) |
| --- | --- |
| `MISSING_AUTHORITATIVE_SOURCE` — a `policy_pack.v2` release carries none | signature validity |
| `MALFORMED_AUTHORITATIVE_COORDINATE` — empty token, non-`sha256:` digest, naive `issued_at` | key trust or rotation state |
| `INCOMPLETE_ISSUANCE_ATTESTATION` — PA's all-or-none rule mirrored structurally | revocation state |
| `AUTHORITATIVE_SOURCE_MISMATCH` — pack reference ≠ manifest reference | current resolution validity |

All four are structural and fail closed. `[V]` Authority and integrity failures in
`CompiledReleaseValidator` can never be downgraded to warnings, so the existing
severity floor carries them. No PWC diagnostic may be worded to suggest that a
signature was checked, a key was trusted, or a revocation was consulted.

## Composition-root placement — ruled

**The composition root lives in neither PA nor PWC, and not in the Governance
Studio.** `[V]` The Studio is `NON_AUTHORITY_STUDIO` by its own screen audit — it
"never issues, activates, revokes, grants, authorizes, clears or executes" — so it
cannot silently become the trust-composition owner.

Dependency direction:

```text
packages/policy-authority
          ▲
          │
   composition root  (packages/integration/…)
          │
          ▼
packages/tooling/policy-workflow-compiler
```

Never `PWC → PA`, and never `PA → PWC`.

`[V]` This layer already exists as a repository pattern.
`packages/integration/agent-constitution-activation` describes itself as a
composition root, declares `ugence-policy-authority` as a first-party dependency,
and reaches it "through its public api module ONLY". Six integration packages depend
on PA today. `[I]` An X1 composition root — an
`AuthoritativePolicyCompilationService` — belongs beside them, depending on the
public `api` modules of both PA and the compiler and on nothing private in either.

### What the service does

```text
1. Receive a PolicyCoordinate
2. Resolve it through Policy Authority
3. Require status == RESOLVED
4. Check the requested current/historical posture against caller intent
5. Obtain the canonical structured policy body
6. Construct policy_pack.v2
7. Derive AuthoritativeSourceRef from the resolution
8. Invoke the compiler
9. Return the compiled release
```

It owns **no new authority**. It cannot change PA's answer, and it cannot waive PWC
validation.

### Fail-closed requirements

The composition layer must require all of:

```text
resolution outcome == RESOLVED
requested coordinate == resolved coordinate
resolution descriptor complete (all three descriptor_* fields)
current/historical request semantics match caller intent
no caller-supplied AuthoritativeSourceRef accepted in place of a derived one
```

### The derivation prohibition

> **Neither PWC nor an untrusted caller may construct a production-trusted
> `AuthoritativeSourceRef` by assertion alone. Production authoritative-source
> linkage must originate from a successfully verified Policy Authority resolution
> through the designated composition root.**

A caller must not be able to submit a `PolicyPack` plus "I promise this came from
Policy Authority" and have it forwarded. On the authoritative path the reference is
**derived**, never authored. `[I]` This is the security property that turns X1 from
provenance *recording* into provenance *proof*; without it the coordinate is an
unchecked assertion with a digest wrapped around it.

## The resulting provenance chain

```text
PolicyCoordinate → PA resolution → IssuedPolicyRecord → AuthoritativeSourceRef
  → policy_pack.v2 digest → compilation → WorkflowIR → release digest / fingerprint
```

Answering, for any governed workflow: who authorized this policy, which exact
version, which approved issuance, which compiler input, which IR, which release.

## Open items

None blocking. `[R]` Two refinements are deferred by ratification rather than
unresolved: whether the identity and evidence tiers eventually become separate
structures, and the acceptance thresholds for the `production_certified` evidence
set (decision D4). Neither gates X1.
