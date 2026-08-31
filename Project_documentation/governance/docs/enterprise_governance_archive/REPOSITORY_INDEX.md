# Repository Index — Enterprise Governance Track

**Status:** Archival index of the important files for this track, grouped by role.
Every file appears **once** (no duplicates). Paths are repo-relative. Cross-references
the frozen architecture
([`../../ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../actiongate/ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md)).

> This index covers only the Enterprise Governance / ActionGate governance track.
> The monorepo contains many unrelated tracks (Symbolu/Varna, agent-runtime,
> robotics, sovereign, …) which are intentionally excluded.

---

## Architecture (frozen model + human-authority substrate + domain instantiations)

| File | Purpose |
|---|---|
| `agentic/enterprise_governance/model.py` | Frozen neutral model: 10 `CapabilityGroup`s, typed `GovernanceEvidence` (status incl. MISSING / verification / authority_role), `GovernanceDecision`/`Execution`/`WorkflowDependency`/`WorkflowEvidence`, `PromotionLevel` ladder, `Disposition`. |
| `agentic/enterprise_governance/invariants.py` | Frozen 11 reusable invariants + failure-code vocabulary; `run_invariants`. |
| `agentic/enterprise_governance/adapters.py` | Read-only `ReadOnlyAdapter` protocol + reference adapters (CRM/Policy/Finance/IAM); emits MISSING for absent fields. |
| `agentic/enterprise_governance/__init__.py` | Package surface for the neutral model. |
| `agentic/agentic_framework/human_policy.py` | Human-policy authority substrate: modes (BASELINE / SOURCE_OF_TRUTH), criticality registry, per-decision authority resolution, `stricter_decision`. |
| `agentic/agentic_framework/governance_service.py` | ActionGate service with human-policy composition + audit provenance (`final_authority_used`, etc.). |
| `agentic/agentic_framework/governance_models.py` | Adds optional `human_policy` audit field to AuditEvent / AuthorizationResponse. |
| `agentic/healthcare/` | Hospital data-access governance specialization (taxonomy, criticality, minimum-necessary, consent, policy, service) wrapping the generic engine. |
| `agentic/healthcare/enforcement/` | Healthcare enforcement harness: HMAC-authenticated artifact, synthetic EMR, enforcement adapter, PHI-safe receipts. |
| `agentic/trading/` | Cash-equity pre-trade governance specialization (taxonomy, limits/universe, policy, service). |
| `agentic/trading/enforcement/` | Trading enforcement harness: HMAC-authenticated artifact, simulated broker, broker enforcement adapter. |

## Research (ontology scaffold — retained as discovery history)

| File | Purpose |
|---|---|
| `agentic/enterprise_ontology/layers.py` | Twelve-layer definitions (scaffold; rejected as runtime schema). |
| `agentic/enterprise_ontology/records.py` | Ontology record model + metadata (epistemic origin / verification / authority role). |
| `agentic/enterprise_ontology/verticals.py` | Cross-vertical definitions. |
| `agentic/enterprise_ontology/events.py` | Event model for scenarios. |
| `agentic/enterprise_ontology/authority.py` | Authority-role modeling for the scaffold. |
| `agentic/enterprise_ontology/failure_classes.py` | Ontology-era failure taxonomy. |
| `agentic/enterprise_ontology/invariants.py` | Stage-1 invariants. |
| `agentic/enterprise_ontology/projection.py` | Projection utilities. |
| `agentic/enterprise_ontology/gap_analysis.py` | Stage-1 verdict + layer-dependence ablation. |
| `agentic/enterprise_ontology/scenarios/` | Stage-1 scenarios: discount, campaign, procurement, hiring (+ helpers). |
| `agentic/enterprise_ontology/stage2/` | Stage-2: content-keyed evidence, invariants, failures, `ablation` (label vs content), scenarios, evaluation. |

## Shadow Pilot (synthetic, schema-shaped evaluation)

| File | Purpose |
|---|---|
| `agentic/enterprise_governance/baseline.py` | Strong (generous) existing-controls baseline; `BASELINE_DETECTABLE`. |
| `agentic/enterprise_governance/shadow.py` | Shadow evaluator + `shadow_report()`; net-new, reuse, false-positive metrics. |
| `agentic/enterprise_governance/workflows.py` | Two synthetic workflows (discount→contract, IAM role/offboarding) built via the adapters. |
| `ACTIONGATE_ENTERPRISE_GOVERNANCE_PHASE3_PILOT.md` | Shadow-pilot writeup with the honesty boundary and non-claims. |

## Documentation (canonical / current)

| File | Purpose |
|---|---|
| `FINAL_PROJECT_STATUS.md` | Canonical top-level status entry point for the track. |
| `ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md` | The frozen architectural position (governs the freeze). |
| `Project_documentation/governance/docs/enterprise_governance_archive/RESEARCH_TIMELINE.md` | Phase-by-phase record. |
| `Project_documentation/governance/docs/enterprise_governance_archive/FINAL_CONCLUSIONS.md` | Validated / partially supported / rejected / unknown. |
| `Project_documentation/governance/docs/enterprise_governance_archive/LESSONS_LEARNED.md` | Wrong assumptions, surprises, what mattered. |
| `Project_documentation/governance/docs/enterprise_governance_archive/FUTURE_WORK.md` | Immediate / requires-real-enterprise / new. |
| `Project_documentation/governance/docs/enterprise_governance_archive/ARCHITECTURE_FREEZE.md` | What is frozen and the change bar. |
| `Project_documentation/governance/docs/enterprise_governance_archive/DECISION_LOG.md` | Major decisions with reason/evidence/status. |
| `Project_documentation/governance/docs/enterprise_governance_archive/KNOWN_LIMITATIONS.md` | Every explicit limitation. |
| `Project_documentation/governance/docs/enterprise_governance_archive/RESUME_GUIDE.md` | How to resume later. |
| `Project_documentation/governance/docs/enterprise_governance_archive/REPOSITORY_INDEX.md` | This index. |
| `Project_documentation/governance/docs/enterprise_pilot/ENTERPRISE_PILOT_ONBOARDING_GUIDE.md` | What a real pilot provides / how onboarding runs. |
| `Project_documentation/governance/docs/enterprise_pilot/SOURCE_ADAPTER_SPECIFICATION.md` | Read-only adapter contract for real sources. |
| `Project_documentation/governance/docs/enterprise_pilot/GROUND_TRUTH_PROTOCOL.md` | Enterprise-authored labels for judging findings. |
| `Project_documentation/governance/docs/enterprise_pilot/BASELINE_COMPARISON_FRAMEWORK.md` | Net-new vs the enterprise's real controls. |
| `Project_documentation/governance/docs/enterprise_pilot/ENTERPRISE_METRICS.md` | Metric definitions (values `TBD`). |
| `Project_documentation/governance/docs/enterprise_pilot/SHADOW_MODE_OPERATION.md` | How the pilot is operated read-only. |
| `Project_documentation/governance/docs/enterprise_pilot/REAL_ENTERPRISE_PILOT_CHECKLIST.md` | Phase A–I operational checklist. |
| `Project_documentation/governance/docs/enterprise_pilot/RESEARCH_BOUNDARY.md` | The honesty contract (read first). |
| `Project_documentation/governance/docs/enterprise_pilot/ENTERPRISE_READINESS_REPORT.md` | Readiness-to-begin self-assessment. |

## Templates (blank mapping templates)

| File | Purpose |
|---|---|
| `Project_documentation/governance/docs/enterprise_pilot/templates/MAPPING_TEMPLATE_IAM.md` | Blank IAM role/access mapping. |
| `Project_documentation/governance/docs/enterprise_pilot/templates/MAPPING_TEMPLATE_DISCOUNT_APPROVAL.md` | Blank discount-approval mapping (recommended first workflow). |
| `Project_documentation/governance/docs/enterprise_pilot/templates/MAPPING_TEMPLATE_CONTRACT_LIFECYCLE.md` | Blank contract-lifecycle mapping. |
| `Project_documentation/governance/docs/enterprise_pilot/templates/MAPPING_TEMPLATE_EMPLOYEE_ONBOARDING.md` | Blank employee-onboarding mapping. |

## Tests

| File | Purpose |
|---|---|
| `agentic/enterprise_governance/tests/test_enterprise_governance.py` | Neutral model + shadow pilot tests, incl. isolation/self-containment. |
| `agentic/enterprise_ontology/tests/test_invariants.py` | Stage-1 invariant tests. |
| `agentic/enterprise_ontology/tests/test_scenarios_and_eval.py` | Stage-1 scenario + evaluation tests. |
| `agentic/enterprise_ontology/tests/test_stage2.py` | Stage-2 ablation + evaluation tests. |
| `agentic/healthcare/tests/test_healthcare_governance.py` | Healthcare decision-layer scenarios. |
| `agentic/healthcare/tests/test_enforcement_validation.py` | Healthcare adversarial enforcement tests. |
| `agentic/trading/tests/test_trading_governance.py` | Trading decision-layer scenarios. |
| `agentic/trading/tests/test_trading_enforcement.py` | Trading adversarial enforcement tests. |

## Historical Documents (research-history writeups, retained unchanged)

| File | Purpose |
|---|---|
| `ACTIONGATE_HUMAN_POLICY_GOVERNANCE.md` | Human-policy governance design + implementation writeup. |
| `ACTIONGATE_HEALTHCARE_DATA_ACCESS_GOVERNANCE.md` | Healthcare decision-layer writeup. |
| `ACTIONGATE_HEALTHCARE_ENFORCEMENT_VALIDATION.md` | Healthcare enforcement/adversarial-validation writeup. |
| `ACTIONGATE_TRADING_PRETRADE_GOVERNANCE.md` | Trading decision-layer writeup. |
| `ACTIONGATE_TRADING_ENFORCEMENT_VALIDATION.md` | Trading enforcement/adversarial-validation writeup. |
| `ACTIONGATE_ENTERPRISE_ONTOLOGY_EVALUATION.md` | Stage-1 cross-vertical value evaluation. |
| `ACTIONGATE_ENTERPRISE_ONTOLOGY_STAGE2_EVALUATION.md` | Stage-2 label-vs-content ablation evaluation. |

> Note: `ACTIONGATE_VC_BRIEF.md` exists at the repo root and references ActionGate,
> but it is a briefing document, not a research artifact of this track's
> conclusions; it is listed here only for completeness and is out of scope for the
> freeze.

## Cross-references

- Timeline: [`RESEARCH_TIMELINE.md`](RESEARCH_TIMELINE.md)
- Freeze: [`ARCHITECTURE_FREEZE.md`](ARCHITECTURE_FREEZE.md)
- Resume: [`RESUME_GUIDE.md`](RESUME_GUIDE.md)
