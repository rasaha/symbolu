# Authority Boundary Check — P2.1

The v2 adapter classifies node disposition with the SAME `classify_node` used by
the v1 adapter, applied to the embedded `base_ir` graph. Dispositions are therefore
byte-identical to v1 (verified for all four P3A scenarios).

## Monotonic authority invariant (fail-closed)

- A `workflow_ir.v2` authoritative or governance-owned node can **never** become
  `AI_AGENT_ELIGIBLE`: the disposition comes from `classify_node`, not from the
  overlay, so an overlay cannot broaden authority.
- Binding approval, human authority, Decision Authority, ActionGate, Action
  Clearance, commit-time authorization, binding override and governance-owned
  execution remain **non-agent dispositions** — identical node sets in v1 and v2
  (`test_non_agent_and_authority_nodes_preserved`).
- An overlay that tries to remove a compiler-declared human review is rejected
  (`OVERLAY_REMOVES_HUMAN_REVIEW`) and the review is retained
  (`test_overlay_cannot_remove_compiler_human_review`).
- The adapter may classify MORE conservatively when semantics are unresolved; it
  never classifies more permissively.

The adapter grants, authorizes, executes nothing; it only reads the formal job
description.
