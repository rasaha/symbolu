# Ugence Code Governance (MVP 1A — shadow)

**Read-only and non-enforcing.** This product proves a shadow governance path for
source-control changes and reconstructs the complete governance chain. It never
merges, approves, dispatches, or otherwise mutates a pull request. Execution is
disabled; there is no GitHub write path and no merge credential.

```
GitHub change event -> exact change identity (GovernedChangeIdentity)
  -> immutable evidence records -> structured Claim Manifest
  -> non-compensatory mandatory-claim evaluation -> TAP assertion evaluation
  -> explicit authorized-actor decision -> DecisionRecord
  -> ContextEnvelopeRecord (cer.v1) -> exact PreparedMergeAction
  -> ActionGate SHADOW evaluation -> reconstructable governance chain
  -> shadow recommendation only
```

Code Governance is **commercially independent, architecturally compositional**:
it composes shared Ugence capabilities (TAP, Decision Authority, ActionGate)
through their public APIs and owns no neutral governance contract.

See `docs/` for the implementation notes, workflow state machine, record model,
claim-manifest semantics, chain reconstruction, shadow limitations, and next
phases. Run the offline demo with `python examples/shadow_demo.py`.

The authoritative stage-gate standard for progressing beyond the current
shadow-pilot state — into the internal live pilot, the external enterprise pilot,
Phase 2A (enforcement foundation), Phase 2B (controlled merge execution), and
production rollout — is
[`docs/CODE_GOVERNANCE_PHASE_READINESS_REQUIREMENTS.md`](docs/CODE_GOVERNANCE_PHASE_READINESS_REQUIREMENTS.md)
(machine-readable companion:
[`artifacts/code_governance_phase_readiness_requirements.json`](artifacts/code_governance_phase_readiness_requirements.json)).
No gate verdict in that standard enables execution; execution remains disabled.
