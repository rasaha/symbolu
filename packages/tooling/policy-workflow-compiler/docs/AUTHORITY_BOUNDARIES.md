# Authority Boundaries

Authority boundaries (`validation/authority_boundaries.py`) encode the rule that
each workflow node must be owned by the right capability with the right
disposition. A violation is a `FATAL` compile error: the pipeline halts and no
package is produced.

## The node-kind ownership table

Authority boundaries are a table mapping each node kind to a required **owning
capability** and a required **disposition** (`advisory` or `authoritative`).
Every synthesized node is checked against this table. The table exists so that
authoritative acts (deciding, authorizing, gating actions) can only be owned by
capabilities entitled to perform them, and advisory capabilities can only ever
advise.

## Illegal compositions that are rejected

The following compositions are explicitly disallowed and cause a `FATAL`
`AUTHORITY_BOUNDARY_VIOLATION`:

- **TAP deciding.** The advisory TAP capability may not own a decision node.
- **StoryGraph deciding.** The advisory StoryGraph capability may not own a
  decision node.
- **Decision Authority doing exact-action authorization.** The decision maker
  may not perform the exact-action authorization that belongs to an action
  capability.
- **Action Gate / Action Clearance making the business decision.** Action
  capabilities gate and clear actions; they may not make the underlying business
  decision.
- **Orchestrator granting authority.** An orchestrator may sequence work but may
  not grant authority.
- **An advisory node marked authoritative.** A node owned by an advisory
  capability may not claim an `authoritative` disposition.

Each of these is a separation-of-powers rule: advisory input, authoritative
decision, and action authorization are kept in distinct hands.

## FATAL on violation

Because authority-boundary violations are `FATAL`, they are non-negotiable
blocking findings — severity is never reclassified downward, and no human
approval path exists to compile a pack whose IR crosses an authority boundary.
The only remedy is to correct the policy pack so that each node is owned by an
entitled capability with a consistent disposition.

This table is the structural complement to the capability registry
(`CAPABILITY_REGISTRY.md`), which declares each capability's disposition, and to
the workflow IR (`WORKFLOW_IR.md`), which records each node's `owning_capability`
and `disposition`.
