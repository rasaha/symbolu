# Existing-implementation disposition

A repo-wide search for a policy-pack / governed-workflow compiler was run before
building:

```
grep -rl "policy_workflow_compiler|policy-workflow-compiler|GovernedWorkflowCompiler" \
    --include=*.py --include=*.toml --include=*.md .
```

**Result:** no implementation, branch, or PR exists. The only match is the design
specification `POLICY_PACK_GOVERNED_WORKFLOW_COMPILER_SPEC.md` (documentation).

## Classification of related implementations

| Component | Path | Classification | Rationale |
|---|---|---|---|
| Policy-pack compiler | — | **NEW BUILD** | No prior implementation exists. |
| Procurement product | `packages/products/procurement/` | **REFERENCE_ONLY** | The authoritative behavior the compiler's Procurement pack is validated against. Not modified. |
| Decision Authority | `packages/capabilities/decision-authority/` | **REFERENCE_ONLY** | Neutral kernel vocabulary mirrored (not imported) by the compiler core. Not modified. |
| TAP / ActionGate / Action Clearance / StoryGraph / Model Selection | `packages/providers/*`, `packages/capabilities/*` | **COMPATIBILITY_ONLY** | Represented by stable capability identifiers + registry metadata. Not imported by the core. Not modified. |
| Governance contracts / provider framework | `packages/governance-contracts/`, `packages/governance-provider-framework/` | **REFERENCE_ONLY** | Neutral contracts; informed the registry metadata. Not depended on by the core. |
| Legacy aliases (`decision_governance`, `tap_provider`, `actiongate_provider`, `acp`) | repo root | **OUT_OF_SCOPE** | Not used; the compiler depends on neither legacy names nor concrete runtimes. |

**Disposition: NEW BUILD**, additive, under
`packages/tooling/policy-workflow-compiler/`. No existing capability behavior is
changed; no duplicate compiler is introduced.
