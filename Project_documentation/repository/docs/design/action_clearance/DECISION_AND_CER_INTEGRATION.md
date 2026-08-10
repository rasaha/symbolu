# Decision Authority & CER Integration

`DecisionRecord` and `ContextEnvelopeRecord` (CER) live in `ugence_decision_authority`. The neutral
Action Clearance core must **not** import Decision Authority. It carries references by **id/hash only**.

## References required for reconstructability

| Reference | Field | Evaluated by Action Clearance? |
|---|---|---|
| `DecisionRecord` id | `decision_record_ref` | **No** — audit linkage only |
| CER id | `context_envelope_ref` (`cer_id`) | **No** — audit linkage only |
| CER content hash | `context_envelope_hash` (`content_hash`) | **Yes (structural)** — verifies the CER referenced is the one authorized |
| policy refs | `policy_refs` | **Yes** — policy-version evaluation |
| authorized-actor basis | `authorized_actor_basis` | **Referenced**; actor *status* evaluated via a current-state signal, not via the DecisionRecord |
| override / supersession refs | `override_ref` / `supersedes_ref` | **Structural** — a superseded decision invalidates clearance |

## What Action Clearance evaluates vs carries

- **Evaluates**: CER `content_hash` match (the CER is the one that was authorized), policy-version
  acceptance, override/supersession state (a superseded authorization is not clearable), and current
  actor *status* (from a signal).
- **Carries for audit only**: `DecisionRecord` id, `cer_id`, `authority_basis`.

## Does not

- **No SoD revalidation.** Segregation of duties is owned and validated by Decision Authority at decision
  time. Action Clearance does **not** revalidate SoD — unless a *current-state actor signal* (e.g.
  "approver account disabled since the decision") requires evaluating actor status, which is a signal
  evaluation, not a re-run of the SoD rule.
- **No duplicate decision record.** Action Clearance never creates or mutates a `DecisionRecord`; a
  changed decision is Decision Authority's supersession, surfaced to clearance as a superseded-reference
  or a current-state signal → old clearance unusable (acceptance scenario 25).
- **No import of `ugence_decision_authority`.** Only string ids and hashes cross the boundary.
