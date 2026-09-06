# Ugence Authoritative Policy Compilation (`ugence-authoritative-policy-compilation`)

The PA/PWC-X1 **composition root**. Policy Authority authenticates a policy; the
Policy Workflow Compiler binds a reference to it into a compiled release. This
package supplies the one thing neither can do alone: it **derives** the
authoritative-source reference from a verified resolution, so a release is bound to
an issuance that was actually resolved rather than one a caller asserted.

```text
Policy Authority   authenticates the policy
composition root   derives the reference from a verified resolution
compiler           binds it immutably into the release
```

## Orchestration, not authority

It issues nothing, revokes nothing, approves nothing, and holds no key material.
Trust — registry, signature verifier, adapters, approval verifier — arrives already
constructed from the operator. It cannot change Policy Authority's answer and cannot
waive the compiler's gates.

- **Distribution:** `ugence-authoritative-policy-compilation`
- **Canonical import:** `ugence_authoritative_policy_compilation`
- **Dependencies:** `ugence-policy-authority` and `ugence-policy-workflow-compiler`,
  each reached through its public `api` module only
- **Production certified:** **No** (`version_info().production_certified == False`)

## The flow

```python
service = AuthoritativePolicyCompilationService()
draft = service.draft_from_coordinate(
    coordinate=coordinate, as_of=as_of,
    registry=registry, signature_verifier=verifier, adapters=adapters,
    pack_builder=my_family_builder,      # ruling CR-2 — families supply this
)
# ruling CR-1 — a human approves draft.pack_digest, outside this package
result = compile_policy_pack(draft.pack, approval)
```

## The five fail-closed requirements

`POLICY_NOT_RESOLVED`, `RESOLVED_COORDINATE_MISMATCH`,
`INCOMPLETE_RESOLUTION_DESCRIPTOR`, `BODY_DIGEST_MISMATCH`,
`HISTORICAL_RESOLUTION_NOT_REQUESTED` — plus `AUTHORED_SOURCE_REFUSED`,
`NO_PACK_BUILDER` and `BUILDER_RETURNED_UNUSABLE_PACK`.

The body digest is re-verified with **Policy Authority's own**
`framed_body_digest`. Reimplementing that canonicalization here would create a
second authority semantics whose drift would surface as a false failure on a valid
artifact; an AST test proves this package implements no hashing of its own.

## Two rulings this package implements

- **CR-1** — the root returns the pack and the digest a reviewer must approve; it
  never accepts or brokers an approval. Placing an orchestrator between a reviewer
  and the artifact they approve is the seam the no-self-approval rule protects.
- **CR-2** — turning a resolved artifact into a `policy_pack.v2` pack is
  family-specific and injected. This root ships no builder and refuses without one.

## The derivation prohibition, enforced

`AuthoritativeSourceRef` is constructed at exactly one AST node, inside
`_derive_source_ref(resolution)`, from the resolution alone — no caller input reaches
it, and a pack that arrives already carrying a source is refused rather than
forwarded. An AST test asserts the single construction site, that the derivation
takes only the resolution, that the package cannot mint or read key material, and
that both neighbours are reached through their public `api` modules only.

## A boundary detail worth knowing

Policy Authority states digests as bare 64-character hex; the compiler states them
as `sha256:<hex>`. Translating between two neighbours' conventions is what a
composition root is for. The translation is total and lossless — the hex is carried
through unaltered, only prefixed — and a test pins it.

See `Project_documentation/repository/docs/audits/policy_workflow_compiler_x1/COMPOSITION_ROOT.md`.
