# ugence-agent-constitution-activation

The Agent Constitution **issuance & activation** distribution (`ACC-IA-1` –
`ACC-IA-5`): the composition layer that turns a ratified constitution artifact
into a genuinely issued, resolvable policy — by orchestrating surfaces that
already exist, never by defining new authority.

## What it does

* **Composition root** (`build_activation_root`): one construction wiring the
  registry, the adapter registry with the `ACC-S1-Q3` family-collision guard
  run on every path, the signer, the signature verifier and the
  always-required approval verifier. No dependency has a default; an
  incompletely wired deployment fails to construct.
* **Preflight** (`preflight_issuance`): a mutation-free dry run of every check
  `issue_policy` performs before it signs — artifact recognition, tenant,
  supersession, canonical body digest, lifecycle, effectivity, approval — as a
  structured report. It takes no signer and no registry, so it cannot sign or
  store.
* **Issuance** (`ActivationRoot.issue_constitution`): the authority's own
  `issue_policy`, orchestrated, with the outcome restated as an
  `IssuanceReceipt` carrying signer *identity fields* only — never key
  material, never signature bytes.
* **Governed reference-map population** (`populate_reference_map`,
  `ActivationRoot.activate_constitution`): entries derive **only** from an
  issued record — one per reference in the carried artifact's own
  `governed_role_refs`, mapped to the record's exact coordinate under its own
  tenant component. Free-form entries are unrepresentable; a conflicting
  existing entry fails closed; every derived entry is listed on the
  `ActivationReceipt`. The result is a `DerivedReferenceMap`, a read-only
  mapping only that function can construct, carrying `derived_from` — the
  coordinates of the records every entry came from.
* **Resolver assembly** (`ActivationRoot.constitution_resolver`): a
  fail-closed conformance resolver over this root's trust and a **derived**
  mapping. `ACC-COUPLING`: this path accepts only the exact
  `DerivedReferenceMap` `activate_constitution` returns, so a map that was
  typed rather than derived from an issued record cannot reach a resolver
  through this root. Disclosed plainly: the conformance package's own
  `build_constitution_resolver` still accepts any mapping — that injected-trust
  posture is ratified and untouched — so a deployment composing conformance
  directly still carries the original disclosed gap. The gap is narrowed to one
  path, not eliminated.

Removing an entry and re-pointing one stay outside this package (`ACC-RECONFIG`):
an operator needing a different map derives one from the records it intends.
Omission is how an entry leaves, and a conflicting entry still fails closed
rather than being overwritten — a removal seam taking effect on a live
deployment would be lifecycle authority under another name (`OD-C4=A`).

## What it is not

Not an authority (no signing, approval, canonicalization, registry or
resolution semantics of its own); not custody (the signer and verifiers arrive
already constructed — this package provably cannot mint, read or persist key
material, and no signing key, trust root or approval artifact exists anywhere
in this repository); not a lifecycle authority (`OD-C4=A` — no revocation seam
exists here, and activation writes no agent, role or registry state); not a
disposition (`OD-C3=B`); not a clock (every instant is caller-supplied and
timezone-aware).

## The end-to-end proof

The suite and `verify_agent_constitution_activation_distribution.py` drive the
whole chain on ephemeral in-process keys minted at run time and discarded:
**issue → activate → resolve → bind → conform**, on the ratified `ACC-FC`
content values — and prove the four-way fail-closed matrix: missing approval,
missing trust, missing mapping, and revoked policy each refuse with a typed
error and mutate nothing.
