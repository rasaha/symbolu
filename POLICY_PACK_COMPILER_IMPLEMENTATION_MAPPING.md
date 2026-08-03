# Policy-Pack Compiler — Implementation Mapping (companion to the design spec)

**Companion to** `POLICY_PACK_GOVERNED_WORKFLOW_COMPILER_SPEC.md`. The design spec
is preserved as historical design intent; this document maps its conceptual
capability names and legacy repository aliases onto the **current canonical
packages** and records Phase 1 support status. Nothing in the spec is rewritten.

## Capability name mapping

| Conceptual capability (spec) | Legacy alias (spec §5) | Current canonical distribution / namespace | Phase 1 support |
|---|---|---|---|
| TAP | `tap_provider/` | `ugence-tap-provider` / `ugence_tap_provider` | Registry target (advisory); IR reference only |
| Decision Authority | `decision_governance/` | `ugence-decision-authority` / `ugence_decision_authority` | Registry target (authoritative); IR reference; neutral vocabulary mirrored |
| ActionGate | `actiongate_provider/` | `ugence-actiongate-provider` / `ugence_actiongate_provider` | Registry target (authoritative); IR reference only |
| ACP → Action Clearance | `acp/` | `ugence-action-clearance` / `ugence_action_clearance` | Registry target (authoritative); IR reference only |
| StoryGraph | `composite_threat_detector/` | `ugence-storygraph` / `ugence_storygraph` | Registry target (advisory); IR reference only |
| Model Selection | `model_selection_pilot/` | `ugence-model-selection` / `ugence_model_selection` | Registry target (advisory); IR reference only |
| Optional orchestrator / AI Control Plane | `ugence_console_api/orchestrator.py` | (bypassable; no canonical distribution) | Registry entry; never required |

Notes:
- The repo-root `acp/` is a documentation-only directory; the robotics
  `autonomous_control_plane` package is a separate subsystem. Neither is a
  governance capability the compiler depends on. The spec's "ACP" (commit-time
  operational clearance) maps to the canonical **Action Clearance** capability.
- The compiler represents every capability by a **stable identifier** and resolves
  it through the capability registry's metadata. It imports **no** runtime
  provider to emit an IR; core dependency is `pydantic` only.

## Stage support status (Phase 1)

| Stage | Spec | Phase 1 |
|---|---|---|
| Stage 1 — ingestion | document ingestion | **NOT implemented** (out of scope) |
| Stage 2 — extraction | NLP/ML proposal | **NOT implemented** (out of scope) |
| Stage 3 precursor | structured validation | **Implemented** |
| Stage 3 | deterministic workflow synthesis | **Implemented** |
| Stage 4 | deterministic assurance generation | **Implemented** |
| Stage 5 | human approval + deterministic release | **Implemented** (release-package subset; no production deployment) |

## Inherited constraint (spec §7)

Learned models may propose; humans approve; deterministic packs enforce. Phase 1
implements only the deterministic enforcement-artifact side: no learned model is an
enforcement node, and no model SDK is a dependency.

Implementation lives at `packages/tooling/policy-workflow-compiler/`
(`ugence-policy-workflow-compiler` / `ugence_policy_workflow_compiler`).
