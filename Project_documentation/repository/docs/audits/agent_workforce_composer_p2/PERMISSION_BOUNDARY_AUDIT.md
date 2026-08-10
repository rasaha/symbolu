# Permission Boundary Audit

- `propose_permission_bound` emits a **proposal only** — it grants/authorizes
  nothing (P2-I12). Proposal notice is mandatory and asserted in tests.
- Proposed = `role.required ∩ enterprise.max_scope ∩ agent-supported − (prohibited ∪
  governance_owned)`. The agent's full requested set is never the proposal;
  unnecessary requested permissions are `EXCESSIVE_REQUESTED` and excluded.
- A required permission that is prohibited / governance-owned / out-of-scope /
  unsupported makes the assignment **infeasible** (so composition can't select it).
- Invariants (tested): proposed ⊆ required, ⊆ enterprise-allowed, ⊆ agent-supported;
  proposed ∩ prohibited = ∅; proposed authority ≤ role ceiling, ≤ enterprise
  ceiling, ≤ agent scope (P2-I13 authority monotonicity — never broadened).
