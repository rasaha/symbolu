# Code Governance MVP 1A — Implementation

> **Read-only and non-enforcing.** This phase proves a shadow governance path and
> reconstructs the complete governance chain. Execution is disabled: no GitHub
> write path, no merge credential, no Action Clearance, no execution provider.

Authoritative design/audit sources (merged; cross-referenced, not duplicated):

- `UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md` (v0.2)
- `docs/audits/code_governance_readiness/` (readiness audit + mapping matrices)
- `docs/audits/code_governance_readiness/CHANGE_INTELLIGENCE_EVIDENCE_LAYER.md`
- `ACTION_CLEARANCE_V0_1_DESIGN_SPEC.md` (future boundary only)

## 1. What this phase proves

```
GitHub change event
  -> exact change identity (GovernedChangeIdentity)
  -> immutable evidence records (EvidenceRecord)
  -> structured Claim Manifest (ClaimManifest)
  -> non-compensatory mandatory-claim evaluation (ClaimEvaluation)
  -> TAP assertion evaluation (per-claim, by evidence reference)
  -> explicit authorized-actor decision recording
  -> DecisionRecord (reused verbatim from Decision Authority)
  -> ContextEnvelopeRecord (cer.v1, reused verbatim)
  -> exact prepared action (PreparedMergeAction)
  -> ActionGate shadow evaluation (SHADOW_ONLY)
  -> complete reconstructable governance chain (GovernanceChainRecord)
  -> shadow recommendation only
```

The phase **stops after** ActionGate shadow evaluation + chain reconstruction. It
does not begin Action Clearance, execution reservation, dispatch, or merge.

## 2. Package

| Property | Value |
|---|---|
| Location | `products/code-governance/` (first `products/` package; per PRODUCT_PACKAGE_BOUNDARY audit) |
| Namespace | `ugence_code_governance` |
| Distribution | `ugence-code-governance` |
| Version | `0.1.0` |
| Runtime deps | stdlib only for product models; public APIs of `ugence-governance-contracts`, `ugence-decision-authority`, `dgm-tap-provider`, `dgm-actiongate-provider` |

Code Governance is **commercially independent, architecturally compositional**:
it composes shared capabilities through their public surfaces and owns no neutral
governance contract.

## 3. Authority boundaries (never collapsed)

| Concern | Owner | Product role |
|---|---|---|
| Assertion governance | TAP (`ASSERTION_GOVERNANCE`) | product invokes; coverage stays descriptive |
| Binding decision | Decision Authority | product supplies an explicit authorized actor; DA validates + records |
| Exact-action authorization | ActionGate (`ACTION_GOVERNANCE`) | product evaluates in **shadow**; never acts on the result |
| Immediate executability (Action Clearance) | *future* | **not evaluated** in this phase |
| Execution | *future* | **disabled** |
| Stage coordination | Workflow Service (product) | owns coordination, **no authority** |

The system makes it structurally impossible for "all automated checks passed" to
mean "binding approval granted": the automated `GovernanceRecommendation` is a
distinct product type (`is_binding = False`) and can never be a `DecisionRecord`.

## 4. Reuse of live public APIs (no upstream modification)

| Capability | Public surface imported | What the product does |
|---|---|---|
| Governance contracts | `ugence_governance_contracts.api` / `governance_providers.api` | consumes neutral request/result types; reuses `ProviderKind` (adds none) |
| TAP | `tap_provider.api` | `build_tap_provider` + `TAPProvider.evaluate` per claim, by evidence reference |
| Decision Authority | `ugence_decision_authority.api` | `CaseDecisionService.record_decision` (explicit actor) → `DecisionRecord`; `CERBindingService.bind_cer` → `ContextEnvelopeRecord` (`cer.v1`) |
| ActionGate | `actiongate_provider.api` | `ActionGateProvider.authorize` in shadow; result recorded `SHADOW_ONLY` |

## 5. Determinism

All evaluation fingerprints are content-derived (domain-separated SHA-256) with
no hidden time reads, no randomness, no unstable ordering, and no mutable global
config. Caller-supplied times are threaded through every stage. Deterministic
replay reproduces stable change/manifest/TAP/prepared-action/ActionGate-request
fingerprints, workflow transitions, and reconstruction outcome. Service-minted
ids (`decision_id`, `cer_id`) and the CER `content_hash` are provenance
references that legitimately vary; they are bound as fields but excluded from
content-derived identity fingerprints.

## 6. Tests & demo

- `products/code-governance/tests/` — 65 tests (45 acceptance scenarios mapped in
  `docs/acceptance_scenarios.json`, plus workflow/tenant/demo tests).
- `products/code-governance/examples/shadow_demo.py` — deterministic, offline,
  fixture-only demonstration of the full path incl. head-SHA invalidation.

## 7. Explicit non-goals in this phase

See `CODE_GOVERNANCE_SHADOW_LIMITATIONS.md` and `CODE_GOVERNANCE_NEXT_PHASES.md`.
No Action Clearance, no execution reservation, no GitHub execution provider, no
merge enforcement, no new `ProviderKind`, no neutral-contract change, no `cer.v2`.
