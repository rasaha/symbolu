# Changelog — ugence-agent-constitution-activation

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
