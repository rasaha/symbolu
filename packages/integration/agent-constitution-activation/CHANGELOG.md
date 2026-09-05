# Changelog — ugence-agent-constitution-activation

## Repository act — the invoice-reconciler pilot (no release, no version move)

The pilot change set authorized as `ACC-PR-IA-2` (see
`docs/architecture/ADR_UGENCE_AGENT_CONSTITUTION_INVOICE_RECONCILER_PILOT_IMPLEMENTATION_AUTHORITY.md`,
over the `ACC-PR-BASE`/`ACC-PR-1`..`ACC-PR-5` ratification): the first
committed governed role declaration,
`pilot/invoice-reconciler-role.v1.json` — the `ACC-PR-2` content under the
ratified governed reference, data outside `src/`, never shipped in the wheel —
with its three-leg proof (`tests/test_pilot_role_document.py`: document →
contract equality; conformance with a widened-scope control and the two
pinning assertions; the issue → activate → resolve → bind → conform chain
re-driven over this role on ephemeral in-process keys, with a
mismatched-reference refusal control), and the `ACC-PR-IA-1` extension of the
role-projection scan to every committed text file under the distribution. The
shipped wheel is byte-identical; the distribution remains `0.1.0`. No agent
runs, is enrolled, or is claimed governed; no constitution is issued.

## 0.1.0 — first release (the `ACC-IA` round)

The issuance & activation change set ratified as `ACC-IA-BASE` and
`ACC-IA-1`..`ACC-IA-5` (see
`docs/architecture/ADR_UGENCE_AGENT_CONSTITUTION_ISSUANCE_ACTIVATION_RATIFICATION.md`),
implemented under the separate `ACC-IA-IMPL=YES` ruling over the merge of
PR #1532.

* **The composition root** — `ActivationRoot` / `build_activation_root`
  (`ACC-IA-2`): registry, guarded adapters, signer, signature verifier and the
  always-required approval verifier, all injected already constructed via
  `ugence_policy_authority.api` protocols; no defaults that grant; the
  `ACC-S1-Q3` guard runs at construction and again at every resolver build.
* **Governed reference-map population** — `populate_reference_map` and
  `ActivationRoot.activate_constitution` (`ACC-IA-3`): entries derive only
  from an issued record, one per reference in the carried artifact's
  `governed_role_refs`, under the coordinate's own tenant; conflicts fail
  closed; every derived entry is listed on the `ActivationReceipt`.
* **Mutation-free preflight** — `preflight_issuance`, `PreflightCheck`,
  `PreflightReport` (`ACC-IA-4`): every pre-signing check replayed through
  public API calls, no signer and no registry accepted, a structured report
  returned instead of an exception for policy-and-evidence findings.
* **Receipts** — `IssuanceReceipt`, `ActivationReceipt` (`ACC-IA-4`): frozen,
  validated shapes pinning coordinate, digests, record id, signer identity
  fields (`authority_id`/`key_id`/`signature_alg` — never key material, never
  signature bytes), approval reference and digest, caller-supplied
  timezone-aware times, and the activated entries.
* **The error family** — `AgentConstitutionActivationError` root with four
  leaves (`ActivationCompositionError`, `ActivationRequestError`,
  `ReferenceMapDerivationError`, `ReferenceMapConflictError`); every authority
  refusal propagates as the authority's own typed error, never re-worded.
* **The end-to-end proof** (`ACC-IA-5`): tests plus the pinned offline
  `verify_agent_constitution_activation_distribution.py` drive
  issue → activate → resolve → bind → conform on the ratified `ACC-FC`
  content values with ephemeral in-process keys, and prove the four-way
  fail-closed matrix (missing approval, missing trust, missing mapping,
  revoked policy), each refusal typed.

Thirteen public names plus `__version__`; no signing key, trust root or
approval artifact enters the repository; no existing package's version,
`public_api.json` or source moved in this change set.
