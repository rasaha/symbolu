# H3 — Governance Integration — Completion Report

Application-local, additive integration of the completed H1/H2 hiring domain with
the **frozen Decision Governance kernel**. Every **eligible, review-ready** hiring
recommendation can now be **bound to a governed `DecisionCase` and resolved through an
authorized human decision process** inside the Decision Governance Platform, while the
resulting decision remains **non-executable until H4**. (Incomplete, rejected, or
superseded recommendations are not required to become decisions.) **No frozen platform file was modified; no
frozen API changed; no ActionGate wiring or execution behavior was added.** All new
code is under `ai_hiring/` and reaches the kernel only through `decision_governance.api`.

## Status & outcome

- **Implemented:** recommendation→DecisionCase binding, kernel recommendation
  submission, review-task lifecycle, **human** decisions through the kernel,
  acceptance/rejection, decision rationale + overrides, governance-case
  reconstruction, recommendation supersession, human-authority enforcement,
  cross-linked hiring↔DGM audit, provider-result persistence, review workspace,
  governance dashboards, and recommendation history.
- **Tests:** **26 new H3 tests**; full AI Hiring suite **658 passed** (was 632).
- **Frozen platform:** untouched — freeze **PASS**; dependency-direction **0
  violations**; kernel+framework+TAP+ActionGate+AI-Hiring **797 passed**.

## Invariant (preserved and enforced)

> **Recommendation → Human Decision → (H4) Authorized Action.** Never Recommendation → Action.

H3 records the governed **human decision** and stops there. The integration service
exposes **no** authorize/execute/dispatch/action method (`test_h3_boundary.py`), and
imports **no** ActionGate/action-request/execution symbols. Human authority is
enforced three ways: the H3 service rejects non-human decision actors
(`ReviewerAuthorityError` + audited denial); the kernel `record_decision` validates
`HUMAN_APPROVER` authority against the actor's identity type; and the access grants
withhold `MAKE_DECISION`/`OVERRIDE_RECOMMENDATION` from the AI actor.

## Architecture

```mermaid
flowchart TD
    R[H2 HiringRecommendation - READY / ASSERTION_REVIEW_REQUIRED] --> OC[open_case - AI]
    OC --> CC[DGM DecisionCaseService.create_case]
    CC --> LA[link_assessment via HiringRecommendationLinkedRecordAdapter -> LinkedRecordPort]
    LA --> MR[mark_ready_for_recommendation]
    MR --> SR[CaseRecommendationService.submit_recommendation - AI_ASSISTED, advisory]
    SR --> B[(GovernanceCaseBinding: hiring rec <-> case <-> kernel rec)]
    B --> RV[assign_review / complete_review]
    RV --> HD{record_human_decision - HUMAN only}
    HD -->|kernel enforces HUMAN_APPROVER authority| DR[CaseDecisionService.record_decision]
    DR -->|diverges from proposal| OV[OverrideRecord]
    DR --> BD[(binding: DECIDED + decision_id)]
    BD --> STOP([STOP - non-executable; action authorization is H4])
    subgraph Audit (cross-linked by correlation id)
      HA[Hiring-owned domain audit - hash-chained] -. correlation_id .- GA[DGM governance audit]
    end
    OC --> HA
    HD --> HA
    BD --> RC[GovernanceCaseReconstructionService]
    HA --> RC
    GA --> RC
    classDef frozen fill:#eef,stroke:#88a;
    class CC,LA,MR,SR,DR,OV,GA frozen;
```

## Implemented behavior (deliverables → artifacts)

| Deliverable | Artifact |
|---|---|
| Recommendation → DecisionCase binding | `GovernanceCaseBinding` + `open_case` (`governance/binding.py`, `services/governance_integration_service.py`) |
| Recommendation review lifecycle | H2 review + kernel review tasks (`assign_review`/`complete_review`) |
| Human reviewer decisions | `record_human_decision` → kernel `record_decision` (human-only) |
| DecisionCase creation & updates | kernel `DecisionCaseService` via the integration service |
| Recommendation acceptance / rejection | decision `ADVANCE/HOLD` (accept) / `REJECT` + `reject_recommendation` |
| Decision rationale capture | reason codes + override reason codes/notes on the kernel decision |
| Governance-case reconstruction | `GovernanceCaseReconstructionService` |
| Recommendation supersession | `supersede_case` (kernel supersede if DECIDED, else cancel) |
| Human authority enforcement | H3 guard + kernel authority validation + access grants |
| Governance audit linkage | hiring events carry the case correlation id; DGM events pulled by `list_by_correlation` |
| Provider-result persistence | H2 `ClaimAssertionBinding`s surfaced in reconstruction |
| Review workspace | `GovernanceViewService.review_workspace` |
| Governance dashboards | `GovernanceViewService.dashboard` |
| Recommendation history | `GovernanceViewService.recommendation_history` |
| Cross-linking hiring ↔ DGM audit | correlation-id linkage (taxonomies **not** merged) |

**Outcome mapping** (`governance/outcomes.py`): advisory H2 `RecommendationOutcome` →
kernel `ProposedOutcome`; human `HiringDecisionIntent` (ADVANCE/HOLD/REJECT/DEFER) →
kernel `DecisionOutcome`; override detected when the human decision diverges from the
AI-proposed outcome.

## Audit cross-linking (not merged)

The DGM kernel emits its own governance audit events (case/recommendation/decision)
to the kernel `AuditService`. H3 emits hiring-owned events
(`GOVERNANCE_CASE_OPENED`, `RECOMMENDATION_BOUND_TO_CASE`, `HUMAN_DECISION_RECORDED`,
`GOVERNANCE_DECISION_OVERRIDE_RECORDED`, review/reject/supersede) to the hiring-owned
hash-chained trail. The two are **linked by shared correlation ids and causation ids**
(hiring events carry the DGM case/decision id as `causation_id`); reconstruction pulls
the DGM side via `AuditRepository.list_by_correlation`. The taxonomies remain separate
(the new hiring event names are disjoint from the frozen kernel `AuditEventType`,
enforced by `test_h1_boundary.py`).

## Validation report

| Check | Result |
|---|---|
| AI Hiring suite (`pytest ai_hiring`) | **658 passed** (632 baseline + 26 H3) |
| Kernel + framework + TAP + ActionGate + AI Hiring | **797 passed** |
| Platform Freeze verification | **PASS** |
| Dependency-direction | **0 violations** |
| Frozen platform files modified | **none** (diff = `ai_hiring/` + `docs/ai-hiring/`) |
| H3 import surface | `decision_governance.api` only; no ActionGate/action-request/execution imports (`test_h3_boundary.py`) |

### H3 test coverage (26 tests)
case binding · duplicate-safe open · review-bound precondition · human decision · AI/
system cannot decide · override on divergence · human reject-recommendation · supersede
(after decision / cancel undecided) · assign & complete review · tenant isolation
(open/decision/reconstruct/dashboard) · no-action-method invariant · full reconstruction
· cross-linked hiring+governance audit · hiring hash-chain verification · override in
reconstruction · review workspace · dashboard counts · recommendation history ·
import-boundary (no ActionGate/execution) · decision-intent kernel-neutrality.

**Baseline limitations carried forward** (unchanged, pre-existing, unrelated): the
`classify_change` freeze-tooling self-test failure and the whole-repository
`_SymboluFinder` collection errors in unrelated experimental modules. The H3 green
baseline is scoped to the platform-relevant packages, **not** the whole repository.

## Completion criteria — met

- Every **eligible, review-ready** recommendation can be bound to a governed
  `DecisionCase` and resolved through an authorized **human** decision process ✓.
- The decision remains **non-executable** until H4 — no action authorization,
  ActionGate wiring, or execution exists ✓.
- Human authority enforced (H3 + kernel + grants); AI cannot decide/override ✓.
- Governance case reconstructable with cross-linked hiring ↔ DGM audit ✓.
- All prior + new tests pass; Platform Freeze passes; no frozen file changed ✓.

## Deferred to H4 (NOT implemented in H3)

ActionGate authorization · external execution · offer generation · rejection execution ·
email/HRIS integration · compensation · execution reconciliation. These belong
**exclusively to H4** and preserve the invariant *Recommendation → Human Decision →
(H4) Authorized Action*.
