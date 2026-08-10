# Prior Artifacts & Scope (Phase 1)

*Unified Governed Inference End-to-End Shadow Pilot (`governed_inference_pilot`). A product-integration
and shadow-validation track — **not** a component-discovery study. It composes the completed, frozen
governance components into one read-only, auditable, replayable inference control plane and asks whether
they operate coherently on realistic artifacts. It modifies no frozen logic and enables no enforcement.*

## Purpose

Determine whether the independently-developed components compose correctly: whether contracts fit,
whether dispositions keep their meaning across boundaries, whether conservative decisions accumulate
into unusable over-blocking, whether unsafe outputs/actions still escape, whether latency/cost are
acceptable, whether operators can review decisions, and whether a smaller configuration suffices — i.e.
whether the architecture is ready for a bounded customer shadow pilot, and what must precede production.

## Frozen prior artifacts (guarded)

`governed_inference_pilot/verify_prior_artifacts.py` hash-pins **17** outcome-bearing artifacts across
five completed tracks (AGE, AssertionGate robustness, EvidenceAssurance, ClaimIntegrity, ScopeIntegrity)
and fails on drift. In addition, the **component source logic** of every stage is treated as frozen:
the pilot imports each component read-only and never edits its decision code.

## What the most recent (ScopeIntegrity) study established

1. broad scope-propagation is unsafe outside its purpose-built corpus;
2. only a tightly-gated hybrid is deployable;
3. the general ClaimIntegrity unsafe-delivery residual was reduced 0.068 → 0.000 on the frozen corpus;
4. the load-bearing mechanism is postposed-exception distribution over the frozen splitter output;
5. ambiguous cases must remain flagged, not force-resolved;
6. all prior components remained frozen and compatible;
7. the next unanswered questions are **operational and end-to-end**, not conceptual — this pilot.

## Non-negotiable constraints (restated, enforced in code)

- **No modification** of frozen decision logic in ExecutionGate, ModelPolicy, ClaimIntegrity,
  ScopeIntegrity, EvidenceAssurance, AssertionGate, ActionGate, TAP, AGE, prior control-plane packages,
  datasets, ground truth, thresholds, evaluation reports, freeze manifests, or outcome-bearing
  artifacts. Adapters and versioned contracts only.
- **No silent patching** of a frozen component to make integration pass. On a contract mismatch:
  document it, create an adapter, preserve both source and transformed representations, test for
  semantic loss, **fail closed** when meaning cannot be preserved.
- **Shadow only:** no live enforcement, no real-world actions, no unrestricted provider calls, no
  unrestricted web retrieval, no customer production deployment, no silent human override, no claim of
  production readiness.

## Shadow-only outcome vocabulary

The runtime may emit `WOULD_ALLOW`, `WOULD_QUALIFY`, `WOULD_REJECT`, `WOULD_ESCALATE`,
`WOULD_BLOCK_ACTION`, `WOULD_CONSTRAIN_ACTION`, `INDETERMINATE`, `PIPELINE_ERROR`, `CONTRACT_ERROR`,
`EVIDENCE_UNAVAILABLE`, `EXECUTION_UNAVAILABLE`. It never performs the governed external action and
never replaces an actual business decision.

## Isolation

All new code lives under `governed_inference_pilot/` and `docs/governed_inference_pilot/`. Prior
components are consumed read-only. See `COMPONENT_INVENTORY.md` for the exact import surface, versions,
failure modes, and known residuals of each stage.
