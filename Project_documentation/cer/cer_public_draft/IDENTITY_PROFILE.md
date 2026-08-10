# CER Identity Profile v2 (Public Draft)

CER identity is the **content hash of the action**, computed over a projection that **excludes
provenance**. This is what makes identity runtime-independent.

## Included in identity
`agent_identity.{id,key_id}`, `delegator`, `delegation_chain`, `tool` (`server_id`+`tool_name`),
`operation`, `target_resource`, `arguments` (profile-specific, typed strings), `credential_scope`
(`principal`, `permissions` as an order-independent set), `current_state_hash`, `state_freshness`
(`as_of`, `source`), `reversibility`, `policy_version`, `correlation_id`, `sequence_id`, and
`rollback_plan` when present.

## Excluded from identity
- **Provenance:** `runtime`, `model_provider`, `objective`. Two runtimes proposing the *same*
  actuation produce the *same* identity; changing provenance never changes the digest.
- **Non-identity:** `action_id`, `timestamp`, `agent_identity.sig`, `approvals`, `attestation`.
  (Approvals and evidence *bind to* the identity; including them would be circular.)

## Why provenance exclusion matters
It is the property that lets one governance decision apply across every runtime. It is also
domain-separated from a legacy profile (v1) by the hash's `schema_version` (`"2.0.0"` vs `"1.0.0"`),
so a v1 and a v2 digest of the same envelope are always different and cannot be confused.

## Consequences (tested)
- Same actuation, different runtime → **same** digest.
- Any material change (target, arguments, statement digest, scope, strategy, …) → **different** digest.
- Approvals/evidence bind to the digest → **fail closed** if the action is modified after approval,
  and **cannot transfer** across different actions or domains.
