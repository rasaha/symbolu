# Authority Context

ActionGate preserves the authority chain and never widens or fabricates authority.

Preserved through request mapping (neutral → native):
`actor → principal`, `authority_context → authority`, `target_resource → resource`,
`policy_refs → policy_context`, `risk_context`, `evidence_refs`, `decision_refs`,
`correlation_id`, `idempotency_key`. The decision returns an `authority_basis` that
survives result mapping.

## Guarantees (tested)
- no actor substitution; no authority-context widening; no target-resource substitution;
- no policy-reference loss; no decision-reference loss;
- **missing authority is not replaced by fabricated authority** (empty stays empty);
- an **AI principal is not silently reclassified as a human authority**;
- ActionGate does **not** create underlying decision authority — it authorizes under
  supplied authority; it never replaces Decision Authority.

## Intentionally lossy
`tenant` is **not** carried by the neutral `ActionGovernanceRequest` (the kernel
adapter does not propagate it), so the native `tenant` is left empty. This is a
documented, intentional mapping gap — a semantic fix is a separate versioned phase,
not a packaging change. See `../../../docs/audits/actiongate_packaging/ACTIONGATE_DEPENDENCY_GRAPH.md`.
