# Disposition & Reason-Code Reconciliation (Phase 4)

*`governed_inference_pilot/dispositions.py` + `reason_codes.py`. Each stage keeps its own disposition
vocabulary; this layer maps each to the unified shadow outcome by **precedence**, never collapsing the
stage-local decisions into one opaque score.*

## Stage-local vocabularies (kept distinct)

| Stage | Local states |
|---|---|
| ExecutionGate | ELIGIBLE / CONDITIONALLY_ELIGIBLE / INELIGIBLE / INDETERMINATE |
| ModelPolicy | selected / abstain |
| ClaimIntegrity | 17 dispositions (VALID … REJECT_DECOMPOSITION … ESCALATE) |
| ScopeIntegrity | resolved / INDETERMINATE_SCOPE |
| EvidenceAssurance | 11 evidence states → delivery effect (ALLOW/QUALIFY/REJECT/ESCALATE/INDETERMINATE) |
| AssertionGate | ALLOW / QUALIFY / REJECT / ESCALATE / INDETERMINATE |
| ActionGate | PERMIT / CONSTRAIN / BLOCK / ESCALATE / INDETERMINATE / NO_ACTION |

Each maps to one of the 11 shadow outcomes via an explicit table (`*_MAP`). **An unknown local
disposition maps to `INDETERMINATE`** — fail closed, never silently to ALLOW.

## Precedence (the reconciliation rule)

The final shadow outcome is the **highest-precedence** non-empty stage outcome:

```
CONTRACT_ERROR > PIPELINE_ERROR > EXECUTION_UNAVAILABLE > EVIDENCE_UNAVAILABLE >
WOULD_BLOCK_ACTION > WOULD_REJECT > WOULD_ESCALATE > WOULD_CONSTRAIN_ACTION >
INDETERMINATE > WOULD_QUALIFY > WOULD_ALLOW
```

This encodes the safety-critical precedence the spec requires:

- **execution unavailable / evidence unavailable** outrank any delivery outcome;
- **an action block outranks an assertion allow** — a claim may be deliverable while its proposed
  action is not, and the action block must win (the runtime never lets an assertion allow hide an
  action block);
- **reject / escalate** outrank qualify / allow;
- **contract / pipeline errors** outrank everything — a broken pipeline is never a permissive result.

`reconcile()` returns `(final, per_stage)`; the `per_stage` map is carried into the envelope so the
final outcome never erases the stage decisions that produced it.

## Reason codes (preserved, never rewritten)

`reason_codes.namespace(stage, codes)` forwards each component's own codes under its stage namespace
(`EXEC.` / `MODEL.` / `CI.` / `SCOPE.` / `EA.` / `AGR.` / `ACT.`) **without rewriting them** — an
already-namespaced code (`EA.PROVENANCE_UNTRUSTED`) is kept verbatim. Pilot-level orchestration codes
use the `GIP.` namespace (missing field, unknown vocab, semantic loss, fail-closed, stage skipped,
stage exception, cascade-conservative, …). The final envelope carries the union, so every stage's
rationale survives to the operator view.

## The non-erasure guarantee

The single `final_shadow_disposition` is a *summary*, not a replacement. `stage_dispositions` in the
envelope and the per-stage `AuditEvent`s always retain each stage's own decision. An operator can
reconstruct exactly which stage drove the final outcome and why.
