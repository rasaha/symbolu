# Known Limitations

- **Synthetic fixtures only.** All workflows, agents, and evidence are synthetic
  (`provenance.synthetic = True`). No live registry, no real benchmark evidence, no
  production connector. `pilot_validated=false`, `production_certified=false`.
- **Data-only compiler seam.** The adapter consumes a serialized `workflow_ir.v1`
  document. It supports exactly the versions in `SUPPORTED_IR_VERSIONS`
  (`workflow_ir.v1`) and fails closed on anything else. It does not itself compile
  policy packs — that is the Policy Workflow Compiler's job.
- **Agent-eligible surface is narrow by contract.** In the current
  governance-centric IR, only advisory, compiler-owned `EVIDENCE_REQUIREMENT` nodes
  become agent roles; richer agent-task node kinds would come from future IR
  versions. This is deliberate authority-preserving conservatism, not a bug.
- **Hard constraints only.** No soft scoring, ranking, or trade-offs. Quality /
  latency / cost are enforced only as hard limits; the finer-grained optimization
  fields on `WorkflowRoleRequirement` are typed placeholders, never ranked.
- **No downstream authority.** AWC proposes; it does not grant permissions,
  authorize actions, make binding decisions, clear operations, select agents, or
  hand off to any runtime.
- **Enterprise-policy-derived role fields require an overlay.** Role constraints
  beyond node-kind-derived capabilities must be injected via `role_overlay`; the
  adapter never infers them from free text.
