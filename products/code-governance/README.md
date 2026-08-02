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
