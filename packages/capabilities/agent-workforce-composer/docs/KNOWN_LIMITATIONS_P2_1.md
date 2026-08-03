# P2.1 Known Limitations

- `data_classification`, permission-intent and tool references from `workflow_ir.v2`
  are DEFERRED: they are surfaced but not consumed onto the role in P2.1 (the compiler
  populates them only on source declaration; enterprise policy remains authoritative).
- The v2 adapter sources `input/output_contract_refs` from the embedded `base_ir` node
  (identical to v1) to keep composition interface compatibility byte-equivalent; the
  compiler's richer typed contract refs are surfaced in the adaptation envelope only.
- v2 adaptation and plan fingerprints legitimately differ from v1 (richer provenance /
  source contract). Equivalence is reported as SEMANTICALLY_EQUIVALENT, never byte
  identity.
- No Governance Studio API, runtime handoff, runtime execution, H16/H22/Model Selection
  integration, permission granting, or action authorization is implemented.
- Not pilot-validated and not production-certified.
