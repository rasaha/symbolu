# Permission Bounding

`propose_permission_bound` produces a least-privilege **proposal** — it grants
nothing. The proposed set is the intersection

    role.required_permissions ∩ enterprise.maximum_permission_scope ∩ agent-supported
      minus (role.prohibited ∪ policy.governance_owned)

An agent's full requested set is never the proposal; permissions the role does not
need are categorized `EXCESSIVE_REQUESTED` and excluded. If any required permission
is prohibited, governance-owned, outside enterprise scope, or unsupported by the
agent, the assignment is **infeasible** (`feasible=False`).

Invariants: proposed ⊆ required, ⊆ enterprise-allowed, ⊆ agent-supported;
proposed ∩ prohibited = ∅; proposed authority ≤ role ceiling and ≤ enterprise
ceiling and ≤ agent scope. Categories: REQUIRED / PROPOSED / PROHIBITED /
UNSUPPORTED / EXCESSIVE_REQUESTED / REQUIRES_HUMAN_REVIEW / GOVERNANCE_OWNED.

Every proposal carries: *"This is a planning-time permission-bound proposal. It
does not grant, authorize, provision or execute any permission."*
