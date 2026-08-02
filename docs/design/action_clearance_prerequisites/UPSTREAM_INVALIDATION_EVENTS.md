# Upstream Invalidation Events

**Status:** PROPOSED · `action_clearance.prerequisites.v0.1`. Companion to `RECEIPT_LIFECYCLE.md`.
Defines how upstream events invalidate a previously issued clearance, the classification of each, and
which component detects and records it.

## Classification legend

- `REQUIRES_NEW_CLEARANCE` — the authorization still holds; a fresh clearance evaluation is needed.
- `REQUIRES_REAUTHORIZATION` — the authorization itself is gone/changed; ActionGate must re-authorize
  before a new clearance is even eligible.
- `TEMPORARY_HOLD` — a transient operational block; re-evaluate later, no upstream change needed.
- `PERMANENT_BLOCK` — this receipt is dead; it may never execute.
- `WORKFLOW_ESCALATION` — ambiguity/conflict requiring a human decision.

## Event → classification → detector

| Upstream event | Classification | Detected & recorded by | Receipt lifecycle effect |
|---|---|---|---|
| authorization superseded | `REQUIRES_NEW_CLEARANCE` | Workflow Service (on ActionGate authorization event) | `SUPERSEDED` or `REVOKED` |
| authorization revoked | `REQUIRES_REAUTHORIZATION` | Workflow Service (ActionGate/DA event) | `REVOKED` |
| decision superseded | `REQUIRES_REAUTHORIZATION` | Workflow Service (Decision Authority supersession) | `REVOKED` |
| CER hash changed | `REQUIRES_REAUTHORIZATION` | Workflow Service (CER `content_hash` mismatch) | `INVALIDATED` |
| action fingerprint changed | `REQUIRES_NEW_CLEARANCE` (new lineage) | evaluator surfaces mismatch; Workflow Service records | new lineage (never silent supersession — see `RECEIPT_SUPERSESSION.md`) |
| target changed | `REQUIRES_NEW_CLEARANCE` (new lineage) | evaluator (`TARGET_MISMATCH`) / Workflow Service | new lineage |
| policy version rejected | `PERMANENT_BLOCK` (for this receipt) | evaluator (`POLICY_VERSION_REJECTED`) / Workflow Service | `REVOKED` |
| actor disabled | `REQUIRES_REAUTHORIZATION` | identity signal → evaluator (`ACTOR_INVALID`); Workflow Service records | `REVOKED` |
| mandatory signal revoked | `TEMPORARY_HOLD` → `REQUIRES_NEW_CLEARANCE` | signal adapter / Workflow Service | `EXPIRED`/re-evaluate |
| security incident activated | `TEMPORARY_HOLD` (or `WORKFLOW_ESCALATION` by policy) | incident signal / Workflow Service | hold; receipt not usable while active |
| change freeze activated | `TEMPORARY_HOLD` | change-mgmt signal / Workflow Service | hold; receipt not usable while active |
| merge-group regenerated | `REQUIRES_NEW_CLEARANCE` (new lineage) | Code Governance / Workflow Service | new lineage on new `merge_group_sha` |

## Detection ownership rule

- Events that are **facts about upstream records** (authorization/decision/CER/policy) are detected and
  recorded by the **Workflow Service** watching those authoritative sources.
- Events that are **current-state facts** (actor disabled, incident, freeze, consumption) arrive as
  **trusted signals** and are evaluated by the **evaluator** at the next clearance request; the Workflow
  Service records the resulting lifecycle event.
- The **evaluator never mutates** a stored receipt; it can only *decline to clear* on the next
  evaluation. Durable invalidation of an already-issued receipt is always a Workflow Service append-only
  event.

## Fail-closed default

Any upstream event whose classification is ambiguous, or which cannot be reliably mapped, defaults to
`TEMPORARY_HOLD` for `HOLD`-eligible conditions and to `WORKFLOW_ESCALATION` for conflicts — never to
"still clear." No invalidation event may leave a receipt silently executable.

## Closure

**CLOSED_BY_NEW_PRODUCT_INTERFACE** — the event catalog, classifications, and detector ownership are
fixed; wiring the detectors is a Workflow Service / Code Governance deliverable.
