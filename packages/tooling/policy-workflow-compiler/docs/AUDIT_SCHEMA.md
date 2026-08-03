# Audit Schema

The audit schema (`compiler/audit_schema.py`) defines the shape of the audit
events a governed workflow is expected to emit. The compiler emits the schema as
part of the compiled package; it does not itself produce runtime audit events.

## Baseline fields

Every audit event carries a fixed baseline of fields:

| Field | Meaning |
| --- | --- |
| `policy_pack_id` | The pack the event derives from. |
| `policy_pack_version` | The pack version. |
| `compiled_package_digest` | Digest of the compiled package. |
| `workflow_node_id` | The IR node that emitted the event. |
| `source_object_ids` | Policy objects behind the node. |
| `evidence_references` | Evidence involved. |
| `actor_identity` | Who acted. |
| `actor_role` | The actor's role. |
| `authority_reference` | The authority relied upon. |
| `recommendation_reference` | An advisory recommendation, if any. |
| `decision_reference` | The decision, if any. |
| `action_reference` | The action, if any. |
| `constraint_digest` | Digest of the governing constraint. |
| `override_reference` | An override, if any. |
| `exception_reference` | An exception, if any. |
| `outcome` | The terminal outcome. |
| `reason_codes` | Structured reasons for the outcome. |
| `timestamp_field_definition` | Definition of the timestamp field. |
| `previous_event_digest` | Digest of the prior event in the chain. |
| `event_digest` | Digest of this event. |

## Canonical event-digest chain

Audit events form a **deterministic canonical digest chain**. Each event carries
a `previous_event_digest` and its own `event_digest`, both computed with SHA-256
over the event's canonical (sorted-key) form. Because the encoding is canonical,
the same sequence of events always yields the same chain of digests, which makes
tampering with an intermediate event detectable by recomputation.

## No immutability claim

The digest chain is explicitly **not** a cryptographic-immutability claim. It
provides deterministic, recomputable integrity linking — nothing more. It is not
a blockchain, not tamper-proof storage, and does not by itself prevent an actor
with write access from rewriting a whole chain. Treat it as a determinism and
consistency mechanism, and rely on the surrounding runtime and storage controls
for immutability guarantees.

The `compiled_package_digest` and `constraint_digest` fields tie audit events
back to the deterministic package digest described in `DETERMINISM.md`.
