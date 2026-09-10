# Ugence — module flowcharts and inter-module interactions

**Status:** documentation only, 2026-09-10. Continues the Ugence Module Map (66 packages, 15 modules, rev 2 of 2026-09-06). No code changed. Labels: `[V]` verified against `packages/*/src`, `[I]` inferred, `[G]` gap.

## 1 — The question

The module map shows one governed action moving through fifteen modules. **Inside each module, what are the steps and decision points, and which module-to-module hops exist as code rather than as a drawing?**

**Answer.** Every module below has a step-level flowchart drawn from its source, and section 17 lists all 39 module-to-module import edges that exist `[V]`. Four hops on the high-level diagram are not carried by any import: the constitution into the runtime (M2 to M9), the signed policy version into the decision authority (M1 to M6), the runtime hook into action clearance (M9 to M8), and receipts into value and readiness (M12 to M13). Each is either an injected argument, a string-valued enum match, or a composition root that does not exist in the repository yet. Section 18 states each one.

Every flowchart depicts what the code does today. Where a README and the code disagree, the code is drawn and the disagreement is listed in section 19.

## 2 — How to read the flowcharts

- A rectangle is a step; a diamond is a decision; a rounded box is a terminal outcome.
- A subgraph is one package. Arrows inside a subgraph are calls; arrows between subgraphs are imports `[V]` unless labelled *injected* or *by value*.
- Each module section ends with its interaction surface: what it imports (outbound) and who imports it (inbound), by package.

---

## 3 — M0 Substrate

`governance-contracts`, `governance-provider-framework`, `jcs`. Not sellable. Every other module imports at least one of these.

```mermaid
flowchart TD
  subgraph gpf["governance-provider-framework"]
    R1["register(descriptor)"] --> R2{"id blank, factory not callable,<br/>kind unknown, or kind mismatch?"}
    R2 -->|yes| RX(["ProviderRegistrationError"])
    R2 -->|no| R3{"contract major or kernel<br/>major incompatible?"}
    R3 -->|yes| RY(["ProviderCompatibilityError"])
    R3 -->|no| R4{"duplicate id or<br/>second default for kind?"}
    R4 -->|yes| RX
    R4 -->|no| R5["store descriptor"]
    S1["resolve(request)"] --> S2["candidates by kind and capability"]
    S2 --> S3{"explicit provider_id?"}
    S3 -->|eligible| S9["select EXPLICIT_ID"]
    S3 -->|not eligible| SX(["ProviderResolutionError"])
    S3 -->|none| S4{"domain or global<br/>default eligible?"}
    S4 -->|yes| S9
    S4 -->|no| S5{"exactly one eligible?"}
    S5 -->|yes| S9
    S5 -->|zero| SX
    S5 -->|several| SY(["ProviderResolutionError: ambiguous"])
    S9 --> S10["factory() then initialize():<br/>REGISTERED to INITIALIZING to AVAILABLE"]
    S10 --> I1["record_invocation(fn)"]
    I1 --> I2{"fn raised ProviderError?"}
    I2 -->|yes| I3["append record completed=false<br/>and re-raise"]
    I2 -->|no| I4["append record completed=true"]
    A1["ActionGovernanceControlPlaneAdapter.authorize"] --> A2["build ActionGovernanceRequest<br/>authorization_expired = cer.expires_at before now"]
    A2 --> A3{"provider raised?"}
    A3 -->|yes| A4(["INDETERMINATE + provider_error reason"])
    A3 -->|no| A5(["ActionAuthorizationResponse via OUTCOME_MAP"])
  end
  subgraph jcs["jcs"]
    J1["canonical_sha256_hex(value)"] --> J2{"value type"}
    J2 -->|bool or None| J3["true false null"]
    J2 -->|int or float| JX(["BareNumberError: numerics must be typed strings"])
    J2 -->|str on nfc path, not NFC| JY(["NonNFCError"])
    J2 -->|dict| J4["sort keys by UTF-16BE, render members"]
    J2 -->|list on set path| J5{"duplicates?"}
    J5 -->|yes| JZ(["DuplicateSetElementError"])
    J5 -->|no| J6["sort, join"]
    J4 --> J7(["bare sha256 hex, no prefix"])
    J6 --> J7
  end
  subgraph gc["governance-contracts"]
    C1["frozen dataclasses: Action, Assertion,<br/>Execution requests and results"] --> C2["__post_init__ structural invariants only"]
    C2 --> C3["Validity.status_at(as_of):<br/>NOT_YET_VALID outranks EXPIRED outranks STALE outranks FRESH"]
    C2 --> C4["IdempotencyResolution.UNKNOWN is never FIRST"]
    C2 --> C5["AssessedSystemBinding.authenticity_verified<br/>permanently False"]
  end
  gpf -.->|"re-exports the same objects"| gc
```

**Capabilities**

| Package | Entry point | Decides or produces | Boundary `[V]` |
|---|---|---|---|
| `governance-contracts` | `api.py` (93 symbols) | Neutral contract shapes; digest-bound `AuditReference`, `EvidenceReference`, labels | "Contracts and structural invariants only. It grants no action permission and mints no authority." |
| `governance-provider-framework` | `ProviderRegistry`, `resolve`, `record_invocation`, `ActionGovernanceControlPlaneAdapter` | Which provider instance serves a request; never silently picks among equals | "Owns no governance authority"; vendor exceptions normalise to `INDETERMINATE` |
| `jcs` | `canonical_bytes`, `canonical_sha256_hex` | RFC 8785 bytes and a bare SHA-256 | "Decides nothing"; alpha; consumed by five packages only |

**Interaction surface.** Outbound: none (all three are leaves except the framework, which re-exports contracts). Inbound: 21 packages import `governance-contracts`; the two providers, `console-api`, `ai-hiring` and `risk-authority-evidence-runtime` import the framework; `agentic-proposer`, the three reasoning-method packages and `workflow-fit-pilot` import `jcs`. Policy Authority, the compiler and the capacity-bounds family each canonicalise with their own `json.dumps` helper, not `jcs` `[V]`.

---

## 4 — M1 Policy authority

`policy-authority`, `uvi-policy-contracts`, `policy-workflow-compiler`, `cloud-scaling-capacity-bounds-policy`. Detective. Supplies the "which policy version applied" field.

```mermaid
flowchart TD
  subgraph pa["policy-authority: issue_policy, ten fixed stages"]
    P1["1 request structure: exact ApprovalEvidenceRef,<br/>signer, registry, AdapterRegistry"] --> P2["2-3 adapters.describe(policy)<br/>yields descriptor and PolicyCoordinate"]
    P2 --> P3{"expected tenant differs<br/>from coordinate tenant?"}
    P3 -->|yes| PX(["PolicyAuthorityRequestError"])
    P3 -->|no| P4{"4 unstructured<br/>supersedes_ref?"}
    P4 -->|yes| PY(["UnsupportedSupersessionError<br/>before approval, clock, signing, registry"])
    P4 -->|structured predecessor| P5["require_admissible_supersession<br/>registry read only"]
    P4 -->|none| P6
    P5 --> P6["4b exclusivity claims:<br/>require_no_exclusivity_conflict"]
    P6 --> P7{"5 declared digest ==<br/>computed body digest ==<br/>coordinate digest?"}
    P7 -->|no| PZ(["PolicyDigestMismatchError"])
    P7 -->|yes| P8["6 approval_verifier.verify_approval<br/>then require_verified_approval:<br/>approver != issuer"]
    P8 --> P9{"7 lifecycle active and<br/>issued_at before effective_to?"}
    P9 -->|no| PW(["PolicyIssuanceError"])
    P9 -->|yes| P10["8 sign domain-separated payload"]
    P10 --> P11["9 IssuedPolicyRecord<br/>protocol id and version stamped"]
    P11 --> P12(["10 registry.append_issuance<br/>the only mutation"])
  end
  subgraph res["policy-authority: resolve_policy, fail-closed order"]
    Q1["TENANT_SCOPE_MISMATCH"] --> Q2["NOT_FOUND, REFERENCE_MISMATCH,<br/>NO_ADAPTER_REGISTERED"]
    Q2 --> Q3["ARTIFACT_REFERENCE_MISMATCH,<br/>NOT_CANONICALIZABLE, digest mismatches"]
    Q3 --> Q4["KEY_UNKNOWN, KEY_REVOKED,<br/>KEY_NOT_ENTITLED, SIGNATURE_INVALID"]
    Q4 --> Q5["APPROVAL_PROOF_INVALID,<br/>LIFECYCLE_NOT_ACTIVE,<br/>NOT_YET_EFFECTIVE, EXPIRED"]
    Q5 --> Q6["SUPERSEDED, REVOKED"]
    Q6 --> Q7(["PolicyResolution RESOLVED<br/>with canonical projection"])
  end
  subgraph fam["policy families: adapters"]
    F1["uvi-policy-contracts<br/>AssessmentContext.bind_policies"] --> F2{"lifecycle APPROVED_ACTIVE,<br/>same tenant, effective at as_of?"}
    F2 -->|no| FX(["PolicyContractError"])
    F2 -->|yes| F3(["frozen AssessmentContext of PolicyReferences"])
    F4["cloud-scaling-capacity-bounds-policy<br/>adapter.describe"] --> F5{"type(artifact) is<br/>CapacityBoundsPolicy exactly?"}
    F5 -->|no| FY(["UnsupportedPolicyArtifactError"])
    F5 -->|yes| F6["to_canonical_obj, remove<br/>metadata.content_digest path"]
    F6 --> F7(["PolicyArtifactDescriptor"])
  end
  subgraph cmp["policy-workflow-compiler: compile"]
    K1["validate_policy_pack"] --> K2{"report.ok?"}
    K2 -->|no| KX(["CompilationResult success=false"])
    K2 -->|yes| K3{"human approval valid,<br/>non-self, for this pack digest?"}
    K3 -->|no| KX
    K3 -->|yes| K4{"review requirement<br/>satisfied?"}
    K4 -->|no| KX
    K4 -->|yes| K5["synthesize WorkflowIR"]
    K5 --> K6{"authority boundary<br/>violations in IR?"}
    K6 -->|yes| KX
    K6 -->|no| K7["assurance manifest, coverage, audit schema"]
    K7 --> K8(["CompiledReleasePackage<br/>with logical_digest"])
  end
  F7 --> P2
  fam -.->|"uvi adapter only"| pa
```

**Capabilities**

| Package | Entry point | Decides or produces | Boundary `[V]` |
|---|---|---|---|
| `policy-authority` | `issue_policy`, `resolve_policy`, `revoke_policy`, `suspend_policy` | Ed25519-signed `IssuedPolicyRecord`; one `PolicyResolutionReason` per failed resolution | "Never a runtime authorizer"; only `DenyAllApprovalVerifier` ships; in-memory registry refused in production |
| `uvi-policy-contracts` | `AssessmentContext.bind_policies`, five policy shapes | Digest-bound references, structural fail-closed binding | "Never verifies a signature, approval, issuance or revocation" |
| `policy-workflow-compiler` | `GovernedWorkflowCompiler.compile`, `verify_compiled_package` | Deterministic `WorkflowIR` plus assurance package, content-addressed | "Tooling, not a governance authority"; not pilot-validated |
| `cloud-scaling-capacity-bounds-policy` | `CapacityBoundsPolicy`, `CapacityBoundsPolicyFamilyAdapter` | A declarative bound artifact and its descriptor | "No composition root calls this today" |

**Interaction surface.** Outbound: `uvi-policy-contracts` imports `governance-contracts`; the compiler lazily imports `decision-authority`, `ai-hiring` and `procurement` for its reference equivalence checks only. Inbound: `policy-authority` is imported by ten packages (M2's five, `agent-value-readiness`, `cloud-scaling-policy-authenticity`, `cloud-scaling-envelope-issuance`, `authoritative-policy-compilation`, `cloud-scaling-capacity-bounds-policy`). The compiler is imported by `agent-workforce-composer` (optional extra), `workflow-converters`, `authoritative-policy-compilation`, `procurement-policy-compilation`. `policy-authority` and `policy-workflow-compiler` share no import edge in either direction `[V]`.

---

## 5 — M2 Agent constitution and strategy permission

Five packages. Detective. Two policy families over M1, each with a fail-closed resolver.

```mermaid
flowchart TD
  subgraph pol["agent-constitution-policy"]
    C1["AgentConstitutionPolicy(metadata, role refs, three bounds)"] --> C2{"tokens sorted, unique,<br/>in admitted vocabulary?"}
    C2 -->|no| CX(["AgentConstitutionOrderingError<br/>or DuplicateError: refused, never reordered"])
    C2 -->|yes| C3["adapter.describe: exclusivity claim<br/>per governed role, projection minus digest"]
  end
  subgraph act["agent-constitution-activation"]
    A1["preflight_issuance: no signer, no registry"] --> A2{"all rows ok:<br/>recognition, digest, lifecycle,<br/>effectivity, approval?"}
    A2 -->|no| AX(["PreflightReport ready=false"])
    A2 -->|yes| A3["issue_constitution → M1 issue_policy"]
    A3 --> A4["IssuanceReceipt: signer identity fields only"]
    A4 --> A5["activate_constitution: registry.get_issued"]
    A5 --> A6{"record halves agree,<br/>no conflicting existing entry?"}
    A6 -->|no| AY(["ReferenceMapConflictError"])
    A6 -->|yes| A7(["DerivedReferenceMap<br/>(tenant, role) → coordinate<br/>plus ActivationReceipt"])
  end
  subgraph conf["agent-constitution-conformance"]
    R1["resolve(tenant, role_contract_ref, as_of)"] --> R2{"key in reference map?"}
    R2 -->|no| RX(["UnknownConstitutionReferenceError<br/>no prefix match, no newest rule"])
    R2 -->|yes| R3["M1 resolve_policy<br/>historical = DENY_ALWAYS"]
    R3 --> R4{"RESOLVED?"}
    R4 -->|no| RY(["ConstitutionUnresolvedError.reason"])
    R4 -->|yes| R5{"exact type, role in refs,<br/>vocabulary inside enums,<br/>presented ref equal?"}
    R5 -->|no| RZ(["typed binding error"])
    R5 -->|yes| R6(["AgentConstitutionPolicy<br/>no envelope, no verified flag"])
    R7["role_facts_conform(policy, facts)"] --> R8(["bool: report, never a denial"])
  end
  subgraph spp["agentic-proposer-strategy-permission-policy"]
    S1["StrategyPermissionPolicy(permitted_strategies)"] --> S2{"non-empty tuple, sorted,<br/>unique, in ReasoningStrategy?"}
    S2 -->|no| SX(["StrategyPermissionFieldError"])
    S2 -->|yes| S3["adapter.describe"]
  end
  subgraph spr["agentic-proposer-strategy-permission-runtime"]
    T1["resolve(StrategyPolicyRequest)"] --> T2{"(tenant, strategy_policy_ref)<br/>in map? case_ref excluded"}
    T2 -->|no| TX(["UnknownStrategyPolicyReferenceError"])
    T2 -->|yes| T3["M1 resolve_policy DENY_ALWAYS"]
    T3 --> T4{"RESOLVED, exact type,<br/>ref equal, tokens in enum?"}
    T4 -->|no| TY(["typed error, reason never in text"])
    T4 -->|yes| T5(["StrategyPolicyResponse<br/>to the proposer"])
  end
  C3 --> A1
  A7 -->|"DerivedReferenceMap"| R1
  S3 -.->|"issued via M1"| T1
```

**Capabilities**

| Package | Entry point | Decides or produces | Boundary `[V]` |
|---|---|---|---|
| `agent-constitution-policy` | `AgentConstitutionPolicy`, family adapter, `register_agent_constitution_policy_family` | Digest-bound bound statement; family collision guard | "A bound is a ceiling on declarations; it grants nothing"; no constitution issued yet |
| `agent-constitution-activation` | `build_activation_root`, `preflight_issuance`, `issue_constitution`, `activate_constitution` | Issued record via M1; derived reference map | Receipts unsigned; "no signing key, trust root or approval artifact exists anywhere in this repository" |
| `agent-constitution-conformance` | `PolicyAuthorityConstitutionResolver.resolve`, `role_facts_conform`, `governed_role_overlaps` | The exact resolved policy, or a typed refusal; a conformance bool | "The verifier's False is a report, never a denial"; overlap "is not enforcement" |
| `agentic-proposer-strategy-permission-policy` | `StrategyPermissionPolicy.permits` | Which reasoning strategies a role may declare | "Authorizes no runtime action" |
| `agentic-proposer-strategy-permission-runtime` | `PolicyAuthorityStrategyPolicyResolver.resolve` | `StrategyPolicyResponse` consumed by the proposer | "Performs no caller authorization and claims none" |

**Interaction surface.** Outbound: all five import `policy-authority` (M1); the policy and runtime packages import `agentic-proposer` enums and request types (M3). Inbound: nothing outside M2 imports any of the five `[V]`. The proposer receives the constitution resolution and strategy resolver as injected arguments, so the M2 to M3 runtime hop is by injection at a composition root, not by import.

---

## 6 — M3 Proposal and advisory

Eleven packages. Input. Everything that recommends and nothing that decides. Six of the eleven are leaves with zero cross-package imports.

```mermaid
flowchart TD
  subgraph ap["agentic-proposer: build_proposer_advisory"]
    B1["cross-contract scope: tenant and case equal<br/>across identity, role, mandate, context, candidates"] --> B2{"context.mandate_id ==<br/>mandate.mandate_id?"}
    B2 -->|no| BX(["CrossContractViolationError"])
    B2 -->|yes| B3["resolve strategy policy via injected<br/>StrategyPolicyResolver, correlation-check echo"]
    B3 --> B4{"declared_strategy in<br/>permitted set?"}
    B4 -->|no| BX
    B4 -->|yes| B5{"injected constitution_resolution<br/>ref == role.constitution_ref?"}
    B5 -->|no| BX
    B5 -->|yes| B6["recompute Eq.1 eligibility per candidate"]
    B6 --> B7{"stored is_eligible agrees?"}
    B7 -->|no| BY(["EligibilityMismatchError"])
    B7 -->|yes| B8["resolve observation_refs;<br/>replay domain evaluation and selection policy"]
    B8 --> B9{"replay matches?"}
    B9 -->|no| BZ(["DomainEvaluationProviderError"])
    B9 -->|yes| B10{"selected_candidate_id set?"}
    B10 -->|yes| B11{"review action permitted,<br/>destination role present,<br/>Eq.2 readiness true?"}
    B11 -->|no| BX
    B11 -->|yes| B12
    B10 -->|no, dependents absent| B12["freeze P_unsigned"]
    B12 --> B13(["ProposerAdvisory<br/>advisory_digest = sha256 of jcs bytes"])
    B14["build_proposer_process_record<br/>terminal PROPOSAL, NEED_EVIDENCE, ABSTAIN, ESCALATE"] --> B15["optional reasoning_method_advisory_input<br/>outside P_unsigned"]
  end
  subgraph rm["reasoning-method-governance, advisor, research bridge"]
    M1["advise(request): admissible set by<br/>implementation status; rules as set semantics"] --> M2{"qualifying count"}
    M2 -->|1| M3["primary = SOLE_QUALIFYING_METHOD"]
    M2 -->|0 or >1| M4["primary none; trade-offs as set differences"]
    M3 --> M5["ReasoningMethodAdvisory<br/>usage_scope RESEARCH_ONLY"]
    M4 --> M5
    M5 --> M6["admit(advisory, result, verified)"]
    M6 --> M7{"result from ugence-readiness-comparison,<br/>signature present if required,<br/>every qualifier covered, none contradicted?"}
    M7 -->|no| MX(["RESEARCH_ONLY_REFUSED_IN_PRODUCT<br/>or typed refusal"])
    M7 -->|yes| M8["ReasoningMethodAdvisoryAdmission<br/>ADVISORY_INPUT"]
    M8 --> M9["to_proposer_input: 14-key mapping"]
  end
  M9 -.->|"no import, no composition root in repo: gap"| B15
  subgraph feeders["other advisory feeders, all leaves"]
    W1["agent-workforce-composer<br/>build_agent_team_plan"] --> W2{"bounds exceeded or<br/>no feasible team?"}
    W2 -->|yes| W3(["SEARCH_SPACE_EXCEEDED or NO_FEASIBLE_TEAM"])
    W2 -->|no| W4(["AgentTeamPlan, fingerprint-bound proposal"])
    S1["model-selection<br/>ModelAuthority.authorize"] --> S2["gate every candidate;<br/>missing or stale signal → UNKNOWN"]
    S2 --> S3{"eligible set non-empty?"}
    S3 -->|yes| S4(["ALLOW + governed fallback chain"])
    S3 -->|no, an INDETERMINATE| S5(["ESCALATE or HOLD"])
    S3 -->|no| S6(["DENY NO_ELIGIBLE_MODEL"])
    L1["llm-steering-controller<br/>recommend"] --> L2["hard constraints before scoring"]
    L2 --> L3{"eligible?"}
    L3 -->|none| L4(["NO_ELIGIBLE_CANDIDATE, never a fallback"])
    L3 -->|some| L5(["RoutingRecommendation<br/>execution_status NOT_EXECUTED"])
    X1["context-minimization<br/>minimize_context"] --> X2{"oracle supplied?"}
    X2 -->|no| X3(["OracleRequiredError"])
    X2 -->|yes| X4["dedup, extractive select,<br/>re-evaluate oracle"]
    X4 --> X5{"equivalence key equal?"}
    X5 -->|yes| X6(["VERIFIED"])
    X5 -->|after restoring spans| X7(["RESTORED"])
    X5 -->|no| X8(["JOINT_EFFECT_FALLBACK: full context"])
    G1["storygraph<br/>SequenceRiskAnalyzer.ingest"] --> G2["link to assemblies;<br/>extract fragments; bounded ledger"]
    G2 --> G3{"recipe completeness<br/>with corroboration?"}
    G3 -->|edge-triggered| G4(["OBSERVE or ESCALATE finding<br/>never ALLOW or DENY"])
    G3 -->|governor refused| G5(["UNAVAILABLE"])
    K1["cloud-scaling-controller<br/>recommend_capacity_action"] --> K2{"state, forecast, cost,<br/>topology gates pass?"}
    K2 -->|no| K3(["RecommendationAbstention, typed reason"])
    K2 -->|yes| K4(["CapacityActionRecommendation<br/>advisory_only, actuation_performed=false"])
    K4 --> K5["cloud-scaling-risk-integration<br/>authenticate: exact type, recomputed digest"]
    K5 --> K6{"digest matches independent<br/>expected digest, within validity?"}
    K6 -->|no| K7(["PROJECTION_REJECTED"])
    K6 -->|yes| K8["project to SubjectRiskEvaluationRequestV2<br/>seam.evaluate (M6)"]
    K8 --> K9(["RISK_DECISION: non-executable"])
    T1["cm-token-accounting-runtime<br/>on_attempt(ProviderAttempt) from M9"] --> T2{"prepared measurement registered?"}
    T2 -->|no| T3(["skipped, never zero"])
    T2 -->|yes| T4(["ApiCallTokenRecord; settlement at quantum boundary"])
  end
```

**Capabilities**

| Package | Entry point | Decides or produces | Boundary `[V]` |
|---|---|---|---|
| `agentic-proposer` | `build_proposer_advisory`, `build_proposer_process_record` | Digest-bound `ProposerAdvisory`; never emits CLEAR, HOLD, BLOCK, AUTHORIZED, DENIED | "Proposes. It decides nothing."; no concrete domain evaluator ships |
| `agent-workforce-composer` | `build_agent_team_plan` | Bounded-exact `AgentTeamPlan`, `PermissionBoundProposal` | "Grants nothing, authorizes nothing, schedules nothing, executes nothing" |
| `model-selection` | `ModelAuthority.authorize` | `ModelAuthorizationDecision` ALLOW, DENY, HOLD, ESCALATE over model eligibility | "The gate narrows and never widens"; evidence primarily synthetic |
| `llm-steering-controller` | `recommend` | `RoutingRecommendation` with fallback and escalation advice | `authority_class: ADVISORY`, `provider_invocation_capability: NONE` |
| `context-minimization` | `minimize_context`, `structural_minimize`, token accounting | Extractive reduction with `equivalence_status`; token records | "Creates no authority"; "extractive, never generative" |
| `context-minimization-token-accounting-runtime` | `RuntimeTokenAccountingBridge.on_attempt`, `settle_budget_from_usage` | Per-attempt token record; conservative or measured settlement | "No real provider adapter is implemented here" |
| `storygraph` | `SequenceRiskAnalyzer.ingest`, `to_advisory_evidence` | OBSERVE, ESCALATE, UNAVAILABLE findings as ActionGate evidence | "Advisory / evidentiary only"; enforcement promotion deferred 0 of 10 |
| `cloud-scaling-controller` | `CloudScalingController.recommend`, `recommend_capacity_action` | `ScalingRecommendation`, `CapacityActionRecommendation` or abstention | "Forecasts never feed the live controller and never actuate anything" |
| `cloud-scaling-risk-integration` | `CloudScalingRiskAdapter.evaluate` | `CloudScalingRiskOutcome` ending at a non-executable `SubjectRiskDecision` | "A risk pass is not authorization" |
| `reasoning-method-governance` | contract dataclasses, `derive_implementation_status` | Digest-settled contracts; record v1 fixed UNATTESTED and UNVERIFIED | "Slice 1 issues no envelope"; research-only |
| `reasoning-method-advisor` | `advise`, `admit`, `validate_admission`, `to_proposer_input` | Rule-derived advisory; admission on comparison evidence | "A verified admission authorizes nothing"; no production key exists |

**Interaction surface.** Outbound: `agentic-proposer` imports only `jcs`; `reasoning-method-governance` imports `governance-contracts`, `uvi-policy-contracts`, `jcs`; the advisor imports governance and `jcs`; `cloud-scaling-risk-integration` imports the controller and `risk_authority` (M6); the token-accounting runtime imports `context-minimization` and `agent-runtime` (M9). Inbound: `agentic-proposer` is imported by M2's three proposer-facing packages; `cloud-scaling-controller` by `cloud-scaling-operations`, `cloud-scaling-authorization-contracts`, `cloud-scaling-risk-integration`; the reasoning-method packages by M4 and `reasoning-method-result-attestation`; `context-minimization` by `console-api`. The advisor names the proposer's input model as a string constant; neither imports the other `[V]`.

---

## 7 — M4 Research-only

`readiness-comparison`, `workflow-fit-pilot`. Out of product. Produces the comparison evidence an admission in M3 is granted on.

```mermaid
flowchart TD
  subgraph wfp["workflow-fit-pilot: run_pilot"]
    P1["validate manifest against catalog,<br/>rule set, advisory before any run"] --> P2{"evaluator identity equals<br/>record issuer, requester or boundary?"}
    P2 -->|yes| PX(["EVALUATOR_SELF_LOOP"])
    P2 -->|no| P3{"case digests equal<br/>benchmark manifest set?"}
    P3 -->|no| PY(["BENCHMARK_MANIFEST_MISMATCH"])
    P3 -->|yes| P4["start BoundaryProcess: the only client"]
    P4 --> P5["per method: propose() PROPOSED;<br/>RUN_BEGIN, CASE_BEGIN and CASE_END<br/>with harness-observed call counts"]
    P5 --> P6{"workflow raised or<br/>capture incomplete?"}
    P6 -->|yes| P7(["INCONCLUSIVE: WORKFLOW_FAILED<br/>or CAPTURE_INCOMPLETE"])
    P6 -->|no| P8["RUN_END telemetry recomputed by boundary;<br/>ATTEST → AttestationEnvelope"]
    P8 --> P9["QualityScorerPort per case;<br/>MetricClaim SourceBasis.REPORTED"]
    P9 --> P10["PilotObservation validated;<br/>OBSERVATION_VALIDATED"]
    P10 --> P11{"run role CALIBRATION?"}
    P11 -->|yes| P12(["rests at UNDER_TEST;<br/>no comparison, no summary"])
    P11 -->|no| P13["build ReadinessComparisonRequest;<br/>compare(request, produced_at)"]
  end
  subgraph rc["readiness-comparison: compare"]
    C1["schema versions pinned"] --> C2{"threshold names a<br/>benchmark_ref?"}
    C2 -->|yes| C3(["THRESHOLD_UNRESOLVABLE:<br/>slice 1 never fetches"])
    C2 -->|no| C4["records: task-class digest,<br/>baseline present, dimensions available"]
    C4 --> C5{"high-consequence class and<br/>threshold-only sufficiency?"}
    C5 -->|no resolved admission| C6(["THRESHOLD_ONLY_NOT_ADMITTED"])
    C5 -->|admitted or n/a| C7["envelopes: self-attestation and<br/>self-verification refused;<br/>EvidenceStatusView per record"]
    C7 --> C8{"quality value meets<br/>threshold under comparator?"}
    C8 -->|no| C9(["INSUFFICIENT_QUALITY with margin"])
    C8 -->|yes| C10{"another sufficient method no worse<br/>on every dimension, better on one?"}
    C10 -->|yes| C11(["SUFFICIENT_RESOURCE_DOMINATED"])
    C10 -->|no| C12(["SUFFICIENT_PARETO_EFFICIENT"])
    C13(["every assessment usage_scope RESEARCH_ONLY;<br/>authority_resolution_basis REQUESTER_ASSERTED"])
  end
  P13 --> C1
  C9 --> P14
  C11 --> P14
  C12 --> P14
  P14["RESULT_ASSESSED → EVALUATED;<br/>coverage report; render with<br/>RESEARCH_ONLY suffix on every line"]
```

**Capabilities**

| Package | Entry point | Decides or produces | Boundary `[V]` |
|---|---|---|---|
| `readiness-comparison` | `compare(request, produced_at)` | `ReadinessComparisonResult`: per-method fit outcome, refusals, evidence views | "Nothing this package produces is approval-bearing" |
| `workflow-fit-pilot` | `run_pilot`, `run_phase_4c_pilot`, `write_and_verify` | `PilotRunResult` with a five-state research ledger, `approval_status "NONE"` | "No custody adapter is bound"; forbidden renderings: verified, trusted, qualified, success |

**Interaction surface.** Outbound: both import `reasoning-method-governance` (M3), `governance-contracts` and `jcs` (M0); the pilot imports `readiness-comparison` and `reasoning-method-advisor`; the engine imports `uvi-policy-contracts` (M1) for `ComparisonOperator`. Inbound: nothing imports either package `[V]`. The evidence path into the product runs M4 to M3 by value: the advisor's `admit` accepts a `ReadinessComparisonResult` whose `engine_identity` must equal `ugence-readiness-comparison`.

---

## 8 — M5 Evidence and trust

`trusted-evidence-authority`, `risk-authority-evidence-runtime`, `tap`, `agent-assurance-evidence`. Detective. A verified receipt authorizes nothing.

```mermaid
flowchart TD
  subgraph tea["trusted-evidence-authority"]
    V1["verify(submission, request, verified_at)"] --> V2{"submission.evidence ==<br/>request.evidence?"}
    V2 -->|no| VX(["refuse CONTENT_DIGEST_MISMATCH"])
    V2 -->|yes| V3{"lifecycle REVOKED<br/>or EXPIRED?"}
    V3 -->|yes| VY(["refuse REVOKED or STALE"])
    V3 -->|no| V4["structural scope mismatches;<br/>temporal refusal at as_of"]
    V4 --> V5["run Ed25519 protocol:<br/>content digest, anchor, profile,<br/>key lifecycle, signature"]
    V5 --> V6{"protocol result valid<br/>and every requested stage cleared?"}
    V6 -->|no| VZ(["refuse VERIFICATION_NOT_PERFORMED<br/>or protocol reason"])
    V6 -->|yes| V7["EvidenceVerificationDetermination ADMITTED<br/>with issuance_token"]
    V7 --> V8["ReceiptIssuer.issue: authority, key,<br/>protocol, request digest must agree"]
    V8 --> V9(["SignedEvidenceVerificationReceipt<br/>Ed25519, domain-separated"])
    V10["verify_bound(envelope, expectation, evaluated_at)"] --> V11{"payload digest recomputed,<br/>anchor resolved at exact coordinate,<br/>signature valid, window includes instant,<br/>every expectation coordinate equal?"}
    V11 -->|no| VW(["typed refusal"])
    V11 -->|yes| V12(["ScopeBoundVerificationResult<br/>CONTEXT_SYSTEM_BOUND"])
  end
  subgraph tap["tap provider"]
    T1["TAPProvider.evaluate(AssertionGovernanceRequest)"] --> T2["map to native request:<br/>evidence refs only, never content"]
    T2 --> T3{"client raised?"}
    T3 -->|yes, fail_safe| T4(["INDETERMINATE provider_error"])
    T3 -->|no| T5{"evidence"}
    T5 -->|none| T6(["INDETERMINATE missing_evidence"])
    T5 -->|any contradicts| T7(["UNSUPPORTED"])
    T5 -->|coverage >= 1| T8(["SUPPORTED"])
    T5 -->|partial| T9(["CONSTRAINED supported_components_only"])
  end
  subgraph ra5["risk-authority-evidence-runtime (RA-5)"]
    E1["submit_evidence_and_evaluate"] --> E2["RiskAuthorityApplication(production_mode=True)<br/>refuses in-memory stores"]
    E2 --> E3{"ProductionEvidenceAdmission:<br/>schema, ADMITTED, current,<br/>integrity and admission digests ok,<br/>identifiers non-blank?"}
    E3 -->|no| E4["evidence inert"]
    E3 -->|yes| E5["TapControlAssurance.evaluate"]
    E5 --> E6{"admitted evidence empty?"}
    E6 -->|yes| E7(["ControlStatus MISSING<br/>provider not consulted"])
    E6 -->|no| E8["provider.evaluate(AssertionGovernanceRequest)"]
    E8 --> E9{"map_assertion_outcome"}
    E9 -->|UNSUPPORTED| E10(["FAIL"])
    E9 -->|SUPPORTED, coverage >= 1| E11{"presumptive PASS without<br/>explicit stance?"}
    E11 -->|yes| E12(["UNKNOWN, H-1 downgrade"])
    E11 -->|no| E13(["PASS"])
    E9 -->|other or infra failure| E12
    E13 --> E14["bind_control_result → RA non-compensatory gate<br/>→ RiskDecision (M6)"]
  end
  subgraph aae["agent-assurance-evidence"]
    D1["AssuranceFindingDeclaration"] --> D2{"binding, evidence, finding, validity<br/>are governance-contracts types;<br/>tenant and subject agree;<br/>id == derived id?"}
    D2 -->|no| DX(["ContractViolation"])
    D2 -->|yes| D3(["record, digest-bound, unsigned, no store"])
  end
  T8 -.->|"by neutral contract, wired by caller"| E8
```

**Capabilities**

| Package | Entry point | Decides or produces | Boundary `[V]` |
|---|---|---|---|
| `trusted-evidence-authority` | `EvidenceVerificationAuthority.verify`, `ReceiptIssuer.issue`, `SignedReceiptVerifier.verify_bound` | Typed determination; Ed25519 receipt; scope-bound re-verification | "A verified receipt authorizes nothing"; no anchor configured means deny |
| `risk-authority-evidence-runtime` | `RiskAuthorityEvidenceRuntime`, `ProductionEvidenceAdmission`, `TapControlAssurance` | Trusted `ControlResult` for the RA gate; caller-supplied PASS is inert | "Adds no second machine authority artifact"; envelope issuance still fails closed in production |
| `tap` | `TAPProvider.evaluate` | `AssertionGovernanceResult` coverage SUPPORTED, UNSUPPORTED, CONSTRAINED, INDETERMINATE | "Never promoted to supported" on failure; not production certified |
| `agent-assurance-evidence` | `AssuranceFindingDeclaration`, selectors, `AssuranceFindingPort` | Declaration record with derived id and supersession rules | "Never runs, probes, scores, admits, evaluates, persists or decides" |

**Interaction surface.** Outbound: the evidence runtime imports `risk_authority` (M6) and the provider framework; TAP imports the framework; effect attestation (M11) and producer attestation (M10) import the authority. Inbound: `trusted-evidence-authority` is imported by `cloud-scaling-producer-attestation`, `risk-authority-effect-attestation`, `reasoning-method-result-attestation`, `benchmark-registry-authority` (canonical helpers); TAP by `ai-hiring`, `console-api`. The evidence runtime declares TAP as a dependency but imports only the neutral `AssertionGovernanceProvider` contract `[V]`.

---

## 9 — M6 Decision and risk authority

`decision-authority`, `risk_authority`, `risk-authority-runtime`. The sole source of machine authority.

```mermaid
flowchart TD
  subgraph ra["risk_authority: RA-1 to RA-4 spine"]
    A1["RA-1 create_case bound to ACTIVE WorkflowIR digest<br/>CREATED → CLASSIFIED → CONTROLS_RESOLVED"] --> A2["RA-2 RiskEngine.evaluate"]
    A2 --> A3{"any required control<br/>unsatisfied?"}
    A3 -->|"FAIL or DENY_UNLESS_ALL"| A4(["DENY"])
    A3 -->|otherwise| A5(["ESCALATE, never coerced to PASS"])
    A3 -->|no| A6{"conditions supplied?"}
    A6 -->|yes| A7(["ALLOW_WITH_CONDITIONS"])
    A6 -->|no| A8(["ALLOW"])
    A7 --> A9["RA-3 issue_decision: case must be AUTHORITY_REVIEW"]
    A8 --> A9
    A9 --> A10{"delegation monotonic:<br/>requested scope within grant?"}
    A10 -->|no| A11(["AuthorityDeniedError"])
    A10 -->|yes| A12["RiskDecision: digests, expires_at = now + ttl"]
    A12 --> A13["RA-4a EnvelopeIssuer.issue"]
    A13 --> A14{"decision grants authority,<br/>not expired, envelope scope<br/>subset of decision scope,<br/>key inside its window?"}
    A14 -->|no| A15(["raise; an expired decision is never re-minted"])
    A14 -->|yes| A16(["RiskAuthorizationEnvelope<br/>Ed25519 over canonical bytes,<br/>bound to tenant authority epoch"])
    A16 --> A17["RA-4b ReferenceActionGate.authorize"]
    A17 --> A18{"EnvelopeVerifier: key known and in window,<br/>signature valid, tenant, audience, session,<br/>nbf and exp, not revoked?"}
    A18 -->|no| A19(["DENIED"])
    A18 -->|yes| A20{"action tenant, actor, model equal envelope<br/>and RuntimeIdentity; scope, purpose,<br/>tool, data, destination, amount match?"}
    A20 -->|no| A19
    A20 -->|yes| A21(["ActionAuthorization AUTHORIZED<br/>executable permanently False"])
    A22["RevocationState: advance_epoch(tenant)<br/>invalidates every prior-epoch envelope;<br/>revoke_envelope, subject, model targeted"] --> A18
  end
  subgraph rar["risk-authority-runtime (RA-4.5): compose"]
    R1["RiskAuthorityEnforcer.production refuses<br/>ReferenceActionGate; reads clock once"] --> R2["verify_and_bind: 8 ordered checks"]
    R2 --> R3{"envelope verifies?"}
    R3 -->|no| R4["RA DENY"]
    R3 -->|yes| R5{"authorization bound to this envelope,<br/>this action digest, this tenant?"}
    R5 -->|no| R6["BindingViolation → ERROR,<br/>never recorded as RA denied"]
    R5 -->|yes| R7["adapters by string value:<br/>DecisionOutcome ADVANCE NO_VETO, HOLD or DEFER HOLD, REJECT DENY;<br/>ActionGate ALLOW NO_VETO, constraints tighten, UNKNOWN DENY"]
    R7 --> R8["apply_restrictions: amount min, expiry earliest,<br/>allow sets intersect, deny sets union"]
    R8 --> R9{"precedence"}
    R9 -->|"RA ERROR"| R10(["ERROR_NON_EXECUTABLE"])
    R9 -->|"RA DENY, DA REJECT, AG DENY or UNKNOWN"| R11(["DENY"])
    R9 -->|"DA HOLD or DEFER"| R12(["HOLD_NON_EXECUTABLE<br/>required_approvals carried"])
    R9 -->|"empty scope or action outside<br/>narrowed scope"| R11
    R9 -->|otherwise| R13(["GRANT: GovernedExecutionDecision<br/>no signature, not a second envelope"])
  end
  subgraph da["decision-authority kernel: record_decision"]
    D1["load case"] --> D2{"terminal status?"}
    D2 -->|yes| D3(["CaseFinalizedError"])
    D2 -->|no| D4["authorize actor for MAKE_DECISION;<br/>readiness over review tasks"]
    D4 --> D5{"ready and transition legal?"}
    D5 -->|no| D6(["DecisionReadinessError or InvalidCaseTransitionError"])
    D5 -->|yes| D7{"authority: AI barred, delegated bounds,<br/>segregation of duties"}
    D7 -->|AI| D8(["AIDecisionAuthorityError"])
    D7 -->|SoD| D9(["SegregationOfDutiesError"])
    D7 -->|ok| D10{"outcome departs from recommendation<br/>without override reasons?"}
    D10 -->|yes| D11(["UnauthorizedOverrideError"])
    D10 -->|no| D12(["DecisionRecord appended;<br/>case DECIDED, never executed"])
  end
  A16 --> R2
  da -.->|"DecisionOutcome by string value"| R7
```

**Capabilities**

| Package | Entry point | Decides or produces | Boundary `[V]` |
|---|---|---|---|
| `decision-authority` | `CaseDecisionService.record_decision`, `DecisionCaseService`, `ActionAuthorizationService`, `ExecutionService`, `ReconciliationService` | `DecisionRecord`, CER, `ActionAuthorizationResponse`, execution and reconciliation records; hashed, append-only | `AuthorityType` has no AI member; "DECIDED is a terminal decision state, not an execution state" |
| `risk_authority` | `RiskAuthorityApplication`, `EnvelopeIssuer`, `EnvelopeVerifier`, `RevocationState`, `EnvelopeIssuanceSeam`, `ActionAdmissionSeam` | Ed25519 `RiskAuthorizationEnvelope`; `ActionAuthorization`; hash-linked governance events | "`issue_envelope` is disabled in production_mode"; reference gate "never production enforcement"; jurisdiction and autonomy constraints not matched (F-D) |
| `risk-authority-runtime` | `RiskAuthorityEnforcer`, `verify_and_bind`, `RiskAuthorityCompositionEngine.compose` | `GovernedExecutionDecision` with `FinalDisposition` GRANT, HOLD_NON_EXECUTABLE, DENY, ERROR_NON_EXECUTABLE | "Production kernel ALLOW is not machine execution authority"; deployment validation pending |

**Interaction surface.** Outbound: `decision-authority` and `risk_authority` are leaves with zero Ugence imports; `risk-authority-runtime` imports only `risk_authority`. It declares `decision-authority` and `actiongate` as dependencies but matches both by enum string value, not by import `[V]`. Inbound: `risk_authority` is imported by twelve packages (all of M10, M11's three RA packages, `risk-authority-evidence-runtime`, `cloud-scaling-risk-integration`, `risk-authority-runtime`); `decision-authority` by `execution-reservation`, `risk-authority-execution-assurance`, `cloud-scaling-bounded-execution`, `ai-hiring`, `procurement`, the compiler; `risk-authority-runtime` by `agent-runtime-governance` and `governed-review`.

---

## 10 — M7 Human authority and approval

Five packages. Detective. Binds an approval to a parked proposal and consumes it exactly once.

```mermaid
flowchart TD
  subgraph gr["governed-review: ApprovalBoundInputSource"]
    G1["inputs_for(proposal) from upstream source"] --> G2{"Decision Authority veto is HOLD<br/>with required_approvals?"}
    G2 -->|no| G3(["pass upstream inputs unchanged"])
    G2 -->|yes| G4["approval_id from proposal fingerprint;<br/>consumer_ref = instance_id:task_id"]
    G4 --> G5{"approval record state"}
    G5 -->|none| G6["request_approval Validity 7 days;<br/>present_for_decision; instance parks"]
    G5 -->|PENDING| G7(["AWAITING_DECISION: still parked"])
    G5 -->|GRANTED or CONSUMED| G8["consume under this key"]
    G8 --> G9{"CONSUMED_FIRST, or ALREADY_CONSUMED<br/>by this instance and task?"}
    G9 -->|no| G10(["CONSUMED_BY_OTHER or REFUSED: parked"])
    G9 -->|yes| G11(["released inputs: veto NO_VETO,<br/>required_approvals emptied,<br/>GR_APPROVAL_CONSUMED reason;<br/>all other restrictions unchanged"])
  end
  subgraph grs["governed-review-service: submit_decision"]
    S1["decision GRANT or REJECT; ApproverRef; proof header"] --> S2{"identity port configured?"}
    S2 -->|yes| S3["approver-identity-jwt authenticate"]
    S3 --> S4{"authenticated, HUMAN by exact configured claim,<br/>not expired, presented id == proven subject?"}
    S4 -->|no| SX(["REFUSED_UNAUTHENTICATED, NOT_HUMAN,<br/>IDENTITY_MISMATCH: nothing written"])
    S2 -->|no| S5
    S4 -->|yes| S5{"approval known, reviewable,<br/>tenant proven or single-tenant?"}
    S5 -->|no| SY(["REFUSED_UNKNOWN_APPROVAL or TENANT_UNPROVEN"])
    S5 -->|yes| S6{"record state"}
    S6 -->|REQUESTED or PENDING| S7["ledger.decide: eligibility via authority-directory"]
    S7 --> S8{"eligible and transition legal?"}
    S8 -->|no| SZ(["REFUSED_INELIGIBLE or NOT_OPEN"])
    S8 -->|yes| S9["RECORDED; signal review_decision to durable engine"]
    S6 -->|identical resubmission| S10(["REPLAYED"])
    S6 -->|already decided| S11(["REFUSED_ALREADY_DECIDED: first decision stands"])
    S9 --> S12{"GRANT?"}
    S12 -->|no| S13(["instance stays parked"])
    S12 -->|yes| S14["adapter.resume: re-arm only, runs nothing;<br/>link to control-plane-root ledger"]
  end
  subgraph aw["approval-workflow: consume"]
    W1["BEGIN IMMEDIATE; ConsumptionKey(tenant, approval, subject digest, consumer)"] --> W2{"key already held?"}
    W2 -->|yes| W3(["ALREADY_CONSUMED naming holder"])
    W2 -->|no| W4{"subject digest equal, state consumable,<br/>valid at as_of?"}
    W4 -->|no| W5(["SUBJECT_MISMATCH, NOT_GRANTED,<br/>EXPIRED_APPROVAL"])
    W4 -->|yes| W6["INSERT ON CONFLICT DO NOTHING;<br/>UNIQUE one consumption per approval"]
    W6 --> W7{"rowcount == 1?"}
    W7 -->|no| W3
    W7 -->|yes| W8(["CONSUMED_FIRST; state CONSUMED;<br/>hash-linked event appended"])
  end
  subgraph ad["authority-directory: is_eligible"]
    E1["scope approval/subject_kind/subject_digest"] --> E2{"valid grant of required role<br/>covering the scope at as_of?"}
    E2 -->|no| E3(["EligibilityAnswer false, reasons"])
    E2 -->|yes| E4{"presented kind and role<br/>equal the record?"}
    E4 -->|no| E3
    E4 -->|yes| E5(["EligibilityAnswer true"])
  end
  G6 --> S1
  S14 -.->|"next advance in M9 re-enters hook"| G1
  G8 --> W1
  S7 --> E1
```

**Capabilities**

| Package | Entry point | Decides or produces | Boundary `[V]` |
|---|---|---|---|
| `approval-workflow` | `SqliteApprovalWorkflowStore.request_approval`, `decide`, `consume` | Forward-only state machine; once-only consumption keyed `approval_key.v1` | "Never approves, authenticates, mints authority, or executes"; signs nothing |
| `governed-review` | `ApprovalBoundInputSource.inputs_for`, `reconstruct` | Released `CompositionInputs`; `ReviewLinkage` with typed `LinkageError`s | "Binds and consumes an approval. Never approves, authenticates, mints authority, signals, resumes or executes" |
| `governed-review-service` | `ReviewService.list_queue`, `submit_decision`, HTTP routes | Typed `DecisionOutcome`; audit linkage entry | "Records a decision a human already made"; `IDENTITY_PROOF PRESENTED_UNPROVEN` without an adapter |
| `approver-identity-jwt` | `JwtApproverIdentityAdapter.authenticate` | `VerifiedClaims` from a locally validated RFC 9068 token | "Validates a proof it did not issue"; only an in-process issuer has ever been run |
| `authority-directory` | `SqliteAuthorityDirectory.put_grant`, `DirectoryApproverEligibility.is_eligible` | Time-bounded role grants; one-hop narrowing delegation; committee report without quorum verdict | "Reports role grants. Never authenticates, never approves, never mints authority" |

**Interaction surface.** Outbound: `governed-review` imports `agent-runtime-governance` (M9), `risk-authority-runtime` (M6), `approval-workflow`, `authority-directory`, `governance-contracts`; the service imports `control-plane-root` (M12), `durable-execution` schema name (M9), `governed-review`, `approval-workflow`; the JWT adapter imports only the service. Inbound: nothing outside M7 imports M7; `approver-identity-jwt` is wired only by `deployment/governed-runtime-worker` `[V]`. `authority-directory` satisfies the approval workflow's eligibility port structurally without importing it.

---

## 11 — M8 Authorization and clearance

`actiongate`, `action-clearance`, `execution-reservation`. Preventive-capable. CLEAR plus ACQUIRED is still not execution.

```mermaid
flowchart TD
  subgraph ag["actiongate provider: authorize"]
    A1["map ActionGovernanceRequest to native;<br/>tenant left empty"] --> A2{"engine failure mode?"}
    A2 -->|timeout, unavailable, config, malformed| A3(["classified ProviderError raised;<br/>framework adapter turns it INDETERMINATE"])
    A2 -->|none| A4["trace id = ag- + sha256(type, params, tenant) first 16 hex"]
    A4 --> A5{"action_type in policy ladder"}
    A5 -->|denied| A6(["DENIED policy_denied"])
    A5 -->|unknown| A7(["INDETERMINATE policy_unknown"])
    A5 -->|constrained| A8(["AUTHORIZED_WITH_CONSTRAINTS<br/>expiry emitted, not enforced"])
    A5 -->|else| A9(["AUTHORIZED"])
  end
  subgraph ac["action-clearance: evaluate_clearance"]
    C1["validate: no future-captured signal,<br/>no credential or token in any signal value"] --> C2{"authorization outcome eligible<br/>and not expired at evaluation_time?"}
    C2 -->|no| C3["AUTHORIZATION_NOT_ELIGIBLE or EXPIRED → BLOCK"]
    C2 -->|yes| C4["per signal: tenant, subject, authorization ref,<br/>action fingerprint binding"]
    C4 --> C5["liveness: UNKNOWN → SIGNAL_MISSING;<br/>trust: provenance, digest, source, adapter, level;<br/>freshness: valid_until, max age"]
    C5 --> C6["type semantics: actor disabled, change freeze,<br/>incident, artifact drift, required control,<br/>target unavailable, policy rejected"]
    C6 --> C7{"PRIOR_CONSUMPTION"}
    C7 -->|CONSUMED| C8["ALREADY_CONSUMED → BLOCK"]
    C7 -->|RESERVED| C9["CONSUMPTION_RESERVED → policy response"]
    C7 -->|unknown or absent| C10["CONSUMPTION_STATUS_UNKNOWN → HOLD"]
    C7 -->|UNUSED| C11
    C8 --> C11
    C9 --> C11
    C10 --> C11["required signals present; conflicts → ESCALATE;<br/>constraint intersection narrows only;<br/>obligations superset"]
    C3 --> C11
    C11 --> C12{"least permissive wins:<br/>BLOCK outranks ESCALATE outranks HOLD outranks CLEAR"}
    C12 --> C13(["ClearanceResult: status, reason codes,<br/>valid_until = min(authorization, signals, lifetime);<br/>content-addressed acr_ receipt, unsigned"])
  end
  subgraph er["execution-reservation: reserve_once"]
    R1["ExecutionKey(tenant, authorization ref,<br/>action fingerprint, target, operation)<br/>receipt ref excluded"] --> R2["BEGIN IMMEDIATE; load receipt and lifecycle"]
    R2 --> R3{"receipt present, body intact, CLEAR,<br/>fields match, ISSUED, not superseded,<br/>not expired?"}
    R3 -->|revoked| R4(["STALE_AUTHORIZATION"])
    R3 -->|expired| R5(["EXPIRED_CLEARANCE"])
    R3 -->|other failure| R6(["INVALID_RECEIPT"])
    R3 -->|yes| R7{"classify_head"}
    R7 -->|"none, AVAILABLE, RELEASED,<br/>RECONCILED_FAILURE, abandoned lease"| R8["generation + 1; deterministic rsv_ id"]
    R7 -->|RESERVED live| R9(["ALREADY_RESERVED, resolution DUPLICATE"])
    R7 -->|"DISPATCHED, OUTCOME_UNCERTAIN,<br/>OBSERVED_FAILURE"| R10(["ALREADY_DISPATCHED: uncertain is never free"])
    R7 -->|"OBSERVED or RECONCILED_SUCCESS"| R11(["ALREADY_COMPLETED"])
    R8 --> R12{"INSERT ON CONFLICT DO NOTHING<br/>rowcount == 1?"}
    R12 -->|no| R13(["CONFLICT"])
    R12 -->|yes| R14(["ACQUIRED; RESERVED event on<br/>append-only hash-linked ledger"])
    R14 --> R15["forward-only: DISPATCHED → OBSERVED_* →<br/>RECONCILED_* → RELEASED; rank never downgrades"]
    R15 --> R16["consumption_status_for(head):<br/>UNUSED, RESERVED, CONSUMED, UNKNOWN<br/>→ PRIOR_CONSUMPTION TrustedSignal"]
  end
  A9 -.->|"outcome by plain string"| C2
  C13 --> R2
  R16 --> C7
```

**Capabilities**

| Package | Entry point | Decides or produces | Boundary `[V]` |
|---|---|---|---|
| `actiongate` | `ActionGateProvider.authorize`, `build_actiongate_provider`, `check` | `ActionGovernanceResult` AUTHORIZED, WITH_CONSTRAINTS, DENIED, INDETERMINATE; fingerprint, unsigned | "Owns no dispatch and no execution authority"; `single_use` is not durable replay prevention |
| `action-clearance` | `evaluate_clearance(request, policy)` | `ClearanceResult` CLEAR, HOLD, BLOCK, ESCALATE; receipt body | "Stateless"; "CLEAR is not execution"; stores nothing, reserves nothing |
| `execution-reservation` | `ExecutionReservationPort.reserve_once`, `SqliteExecutionReservationStore`, `build_consumption_signal` | One-time reservation per execution key; hash-linked ledger; consumption signal | `MATURITY REFERENCE_GRADE_SHADOW_ONLY`, `ENFORCEMENT_ENABLED False`; no clock read anywhere |

**Interaction surface.** Outbound: `actiongate` imports the provider framework; `action-clearance` imports nothing and speaks the outcome vocabulary "by value"; `execution-reservation` imports `action-clearance`, `governance-contracts` and `decision-authority` execution types. Inbound: `actiongate` is imported by `ai-hiring` and `console-api`; `action-clearance` by `execution-reservation` and `clearance-export`; `execution-reservation` by `cloud-scaling-credential-broker` and `cloud-scaling-bounded-execution`. **No M9 package imports any M8 package** `[V]`; see section 18.

---

## 12 — M9 Governed runtime

`agent-runtime`, `agent-runtime-governance`, `durable-execution`. Preventive-capable. The hook fires before every consequential provider call.

```mermaid
flowchart TD
  subgraph de["durable-execution: one advance = one DBOS step"]
    U1["DbosRuntimeHost refuses monotonic clock"] --> U2["advance(instance_id, attempt_token)<br/>fresh DBOS workflow id per attempt"]
    U2 --> U3{"state.claim held by<br/>another worker?"}
    U3 -->|yes| U4(["StepOutcome parked: refused, not queued"])
    U3 -->|no| U5["rehydrate if not resident;<br/>AgentRuntime.advance_workflow"]
  end
  subgraph art["agent-runtime: _run_task"]
    T1["TransitionProposal: frozen args,<br/>idempotency_key = instance:task,<br/>no attempt number, no timestamp"] --> T2{"task consequential?"}
    T2 -->|no| T3["directive CONTINUE, no boundary crossed"]
    T2 -->|yes| T4["governance_hook.evaluate(proposal, clock())"]
    T4 --> T5{"disposition"}
    T5 -->|HOLD| T6(["task WAITING, workflow WAITING governance_hold"])
    T5 -->|ESCALATE| T7(["task WAITING, workflow PAUSED governance_escalate"])
    T5 -->|BLOCK, None, unknown| T8(["task FAILED GOVERNANCE_BLOCK"])
    T5 -->|CLEAR| T9["validate_clearance: proposal intact,<br/>fingerprint equal, binding reference present,<br/>now before valid_until, correlation equal"]
    T9 --> T10{"permitted?"}
    T10 -->|no| T11(["FAILED CLEAR_REJECTED"])
    T10 -->|yes| T12["authority_recheck immediately before effect"]
    T12 --> T13{"recheck"}
    T13 -->|"stale, raised, malformed"| T14(["FAILED GOVERNANCE_CLEAR_AUTHORITY_STALE<br/>or RECHECK_ERROR, never a permit"])
    T13 -->|ok| T15["task RUNNING; ToolInvocation re-fingerprinted"]
    T15 --> T16{"invocation fingerprint ==<br/>proposal fingerprint?"}
    T16 -->|no| T17(["FAILED PROPOSAL_INVOCATION_MISMATCH"])
    T16 -->|yes| T18["execute_with_policy: timeouts not retried,<br/>retriable errors to max_attempts,<br/>one ProviderAttempt per real invocation"]
    T18 --> T19{"outcome ok?"}
    T19 -->|yes| T20(["COMPLETED, checkpoint"])
    T19 -->|no| T21(["FAILED, workflow FAILED"])
    T3 --> T15
  end
  subgraph arg["agent-runtime-governance: GovernedExecutionHook.evaluate"]
    H1["sweep consumed, expired, stale records"] --> H2["source.inputs_for(proposal)"]
    H2 --> H3{"raised, None, or<br/>not CompositionInputs?"}
    H3 -->|yes| H4(["BLOCK: INPUT_SOURCE_UNAVAILABLE,<br/>NOT_AUTHORITY_BOUND, MALFORMED"])
    H3 -->|no| H5["RiskAuthorityCompositionEngine.compose (M6)"]
    H5 --> H6{"project_disposition"}
    H6 -->|"GRANT and executable"| H7{"envelope_id present?"}
    H7 -->|no| H8(["BLOCK GRANT_WITHOUT_AUTHORIZATION_REFERENCE"])
    H7 -->|yes| H9{"clearance record at capacity?"}
    H9 -->|yes| H10(["BLOCK RECORD_AT_CAPACITY"])
    H9 -->|no| H11(["CLEAR: fingerprint, envelope_id,<br/>correlation, valid_until epoch seconds"])
    H6 -->|"HOLD_NON_EXECUTABLE with required_approvals"| H12(["ESCALATE: EXTERNAL_APPROVAL"])
    H6 -->|"HOLD_NON_EXECUTABLE"| H13(["HOLD: GOVERNANCE_HOLD_RELEASE"])
    H6 -->|"DENY, ERROR, unknown"| H14(["BLOCK"])
    H15["build_authority_recheck over RA-6<br/>make_pre_effect_recheck (M11)"] --> H16["hook_envelope_resolver consumes the record;<br/>missing record for a CLEAR → RECHECK_ERROR"]
  end
  U5 --> T1
  T4 --> H1
  H11 --> T5
  T12 --> H15
```

**Capabilities**

| Package | Entry point | Decides or produces | Boundary `[V]` |
|---|---|---|---|
| `agent-runtime` | `create_runtime`, `AgentRuntime.advance_workflow`, `validate_clearance`, `GovernanceHook` protocol | Task states PENDING, READY, RUNNING, WAITING, COMPLETED, FAILED; `ProviderAttempt` telemetry; checkpoints | "With no governance adapter configured, consequential transitions fail closed"; `dependencies = []` |
| `agent-runtime-governance` | `GovernedExecutionHook.evaluate`, `project_disposition`, `build_authority_recheck` | `GovernanceEvaluation` bound to the exact proposal; binding reference is RA's envelope id | "Compose, then project. Mint nothing."; "does not implement a recheck" |
| `durable-execution` | `DbosExecutionAdapter.start`, `advance`, `signal`, `resume`, `recover` | `StepOutcome` with HOLD and ESCALATE collapsed into `awaiting_external`; Postgres `ugence_art` schema | "The engine owns scheduling and recovery. It owns nothing else."; ratified means the ADR matrix passes in CI |

**Interaction surface.** Outbound: `agent-runtime` imports nothing; `agent-runtime-governance` imports `agent-runtime`, `risk-authority-runtime` (M6) and, lazily, `risk-authority-status-runtime` (M11); `durable-execution` lazily imports `agent-runtime` inside `postgres/`. Inbound: `agent-runtime` is imported by `agent-runtime-governance`, `durable-execution`, `context-minimization-token-accounting-runtime`; `agent-runtime-governance` by `governed-review`; `durable-execution` by `governed-review-service`.

---

## 13 — M10 Execution ladder

Eight packages, phases 5A to 5D and 5X. The only module with a real executor. LIVE is off by default and downgrades to dry-run when any posture fact is missing.

```mermaid
flowchart TD
  subgraph p5a["5A cloud-scaling-authorization-contracts"]
    A1["build_capacity_authorization_candidate"] --> A2["reconcile_phase4: re-derive context, subject,<br/>recommendation, request digests via risk_authority"]
    A2 --> A3{"digests, temporal order without a clock,<br/>target scope, policy binding, ceilings all agree?"}
    A3 -->|no| A4(["typed error: Reconciliation, TemporalOrdering,<br/>TargetScope, PolicyTargetBinding, MagnitudeBound"])
    A3 -->|yes| A5(["CapacityAuthorizationCandidate<br/>grants_authority derived False"])
  end
  subgraph p5b0a["5B-0A cloud-scaling-producer-attestation"]
    B1["verify(candidate, attestation, as_of)"] --> B2{"recomputed signing payload == signed bytes;<br/>anchor at (issuer, key) resolved, right capability,<br/>in lifecycle; Ed25519 valid?"}
    B2 -->|no| B3(["ProducerAttestationRefusal"])
    B2 -->|yes| B4(["VerifiedProducerAttestation<br/>bound to candidate_digest"])
  end
  subgraph p5b0b["5B-0B cloud-scaling-policy-authenticity"]
    C1["verify(coordinate, tenant, as_of, candidate)"] --> C2["M1 resolve_policy unchanged"]
    C2 --> C3{"RESOLVED, current not historical,<br/>coordinate digest == signed body digest,<br/>bounds reconcile with candidate ceilings?"}
    C3 -->|no| C4(["PolicyAuthenticityRefusal"])
    C3 -->|yes| C5(["VerifiedPolicyAuthenticity"])
  end
  subgraph p5b4["5B-4 cloud-scaling-envelope-issuance"]
    D1["issue(request): seam reads clock once"] --> D2["port verifies at that instant:<br/>candidate re-derived, producer and policy verified,<br/>five bindings in ratified order"]
    D2 --> D3{"all five VERIFIED at the same instant?"}
    D3 -->|no| D4(["EnvelopeIssuanceRefusal"])
    D3 -->|yes| D5(["RiskAuthorizationEnvelope signed by M6 seam;<br/>executable permanently False"])
  end
  subgraph p5c["5C cloud-scaling-action-admission"]
    E1["admit(request): CapacityActionGate as ActionGatePort"] --> E2["kernel verifies envelope; replay lookup"]
    E2 --> E3{"scope and candidate bindings match,<br/>tenant actor model purpose equal,<br/>no data or money, within bounds,<br/>conditions satisfied?"}
    E3 -->|no| E4(["ActionAuthorization DENIED"])
    E3 -->|yes| E5(["ActionAuthorization AUTHORIZED<br/>executable False"])
  end
  subgraph p5x["5X cloud-scaling-credential-broker"]
    F1["materialize(request): clock once"] --> F2{"authorization AUTHORIZED and unexpired,<br/>envelope present and unexpired,<br/>reservation RESERVED with live lease?"}
    F2 -->|no| F3(["typed refusal"])
    F2 -->|yes| F4["mint CredentialRequest: action re-derived,<br/>least-privilege role; window = min of all"]
    F4 --> F5{"existing grant for this id?"}
    F5 -->|other request| F6(["GRANT_CONFLICT"])
    F5 -->|same| F7(["REPLAYED"])
    F5 -->|none| F8["broker port; validate grant:<br/>no role widening, inside window"]
    F8 --> F9(["CredentialGrant: a handle, no secret;<br/>executable False"])
  end
  subgraph p5d["5D cloud-scaling-bounded-execution"]
    G1["dispatch(request): clock once; replay by record id"] --> G2{"grant, reservation RESERVED, authorization,<br/>envelope all present and valid?"}
    G2 -->|no| G3(["typed DispatchRefusal"])
    G2 -->|yes| G4["re-mint credential request; must equal grant"]
    G4 --> G5{"posture: production app, ledger, grant store,<br/>broker, non-reference handle, backend, readiness"}
    G5 -->|"any missing and mode LIVE"| G6["effective mode DRY_RUN, never SIMULATION"]
    G5 -->|all proven| G7["effective mode LIVE"]
    G5 -->|"mode not LIVE"| G8["mode unchanged"]
    G6 --> G9["narrow target policy to the role;<br/>per-act ExecutionAuthorization"]
    G7 --> G9
    G8 --> G9
    G9 --> G10["mark_dispatched before executor if applying"]
  end
  subgraph ops["cloud-scaling-operations: ControlledScalingExecutor.execute"]
    H1{"config.mode"} -->|DRY_RUN| H2(["PROPOSED, applied=false, no backend call"])
    H1 -->|SHADOW| H3(["SHADOWED: read replicas only"])
    H1 -->|SIMULATION or LIVE| H4["verify_authorization fails closed"]
    H4 --> H5{"idempotency key reused<br/>with different digest?"}
    H5 -->|yes| H6(["ExecutionIntegrityError"])
    H5 -->|completed before| H7(["DUPLICATE"])
    H5 -->|no| H8{"LIVE preconditions: injected backend,<br/>audit sink, no insecure TLS, readiness"}
    H8 -->|missing| H9(["DENIED"])
    H8 -->|ok| H10["read_replicas, set_replicas(expected_current)<br/>via injected AppsV1Api or ArgoCD HTTP caller"]
    H10 --> H11(["APPLIED or SIMULATED, or FAILED<br/>concurrency_conflict, backend_error"])
  end
  A5 --> B1
  A5 --> C1
  B4 --> D2
  C5 --> D2
  D5 --> E2
  E5 --> F2
  F9 --> G2
  G10 --> H1
  H11 --> G11(["BoundedExecutionRecord + RA-8 EffectObservation (M11)"])
```

**Capabilities**

| Package | Phase | Decides or produces | Boundary `[V]` |
|---|---|---|---|
| `cloud-scaling-authorization-contracts` | 5A | Digest-bound candidate; `grants_authority` False | "Production LIVE execution remains structurally blocked until 5X" |
| `cloud-scaling-producer-attestation` | 5B-0A | Who produced the recommendation, under a trust anchor | "A verified attestation grants nothing" |
| `cloud-scaling-policy-authenticity` | 5B-0B | Was the named policy version issued by M1 and in force | "A verified policy proof grants nothing"; no TEV anchor lent |
| `cloud-scaling-envelope-issuance` | 5B-4 | One signed envelope via the M6 seam | "An envelope is authority, not execution" |
| `cloud-scaling-action-admission` | 5C | Is this exact capacity action the one the envelope covers | "An authorization is admission, not execution" |
| `cloud-scaling-credential-broker` | 5X | A credential handle; role never widened | "Holds NO secret, NO key, NO clock"; os, socket, cloud SDKs banned structurally |
| `cloud-scaling-bounded-execution` | 5D | One bounded change per grant; effective mode | "Any absence resolves to dry_run and never simulation"; holds no credential |
| `cloud-scaling-operations` | actuation | Receipt PROPOSED, SHADOWED, SIMULATED, APPLIED, DENIED, DUPLICATE, FAILED | Default mode `dry_run`; "not live-cluster validated"; no kubectl subprocess exists |

**Interaction surface.** The ladder is strictly one-way: no package is imported by one below it `[V]`. Outbound edges leave the module to `risk_authority` (M6, six packages), `policy-authority` (M1), `trusted-evidence-authority` (M5), `cloud-scaling-controller` and `risk-integration` (M3), `execution-reservation` (M8), `risk-authority-execution-assurance` (M11), `decision-authority` (M6), `governance-contracts` (M0). Inbound: nothing imports 5D; the rest are imported only within the ladder.

---

## 14 — M11 Post-effect assurance

`risk-authority-status-runtime` (RA-6), `risk-authority-runtime-assurance` (RA-7), `risk-authority-execution-assurance` (RA-8), `risk-authority-effect-attestation`. Detective. Reassesses; never mints authority.

```mermaid
flowchart TD
  subgraph ra7["RA-7 runtime-assurance: observe"]
    S1["RuntimeEventAdapter: event plus caller bindings"] --> S2["TrustedTelemetryIngress.admit:<br/>authenticate producer, binding errors, domain"]
    S2 --> S3{"admitted and not duplicate?"}
    S3 -->|no| S4(["IGNORE_EVENT"])
    S3 -->|yes| S5["bounded trajectory window per instance"]
    S5 --> S6{"policy_ref resolvable?"}
    S6 -->|no| S7(["UNKNOWN_ASSESSMENT: blind window"])
    S6 -->|yes| S8["six rules: cumulative exposure, near-boundary repeats,<br/>retry loop, data class rank, context expansion,<br/>model behaviour changed"]
    S8 --> S9{"any fired?"}
    S9 -->|no| S10(["NORMAL, NO_SIGNAL"])
    S9 -->|yes| S11(["ESCALATED → AuthorityReassessmentSignal<br/>RUNTIME_RISK_ESCALATED"])
  end
  subgraph ra8["RA-8 execution-assurance: assess"]
    X1["ExecutionCorrelation from governed context"] --> X2["admit observations: unsigned rejected in production;<br/>attested via effect-attestation verifier"]
    X2 --> X3{"effect source available?"}
    X3 -->|no| X4(["UNVERIFIABLE EFFECT_SOURCE_UNAVAILABLE"])
    X3 -->|yes| X5{"any admitted?"}
    X5 -->|none supplied| X6(["UNKNOWN NO_OBSERVATION"])
    X5 -->|all rejected| X7(["UNVERIFIABLE"])
    X5 -->|yes| X8["Decision Authority kernel (M6):<br/>intent, attempt, external outcomes, reconcile"]
    X8 --> X9["safe_aggregate over all records"]
    X9 --> X10{"aggregate"}
    X10 -->|duplicate success ids| X11(["MANUAL_REVIEW DUPLICATE_EFFECT"])
    X10 -->|favourable and unfavourable final| X12(["CONFLICTED: favourable never masks"])
    X10 -->|unfavourable final| X13(["MISMATCH"])
    X10 -->|favourable final| X14{"production and no INDEPENDENT_OBSERVER<br/>verified favourable observation?"}
    X14 -->|yes| X15(["UNVERIFIABLE INDEPENDENT_OBSERVER_REQUIRED"])
    X14 -->|no| X16(["MATCHED"])
    X10 -->|partial or pending| X17(["PARTIAL"])
    X11 --> X18["material → AuthorityReassessmentSignal<br/>EXECUTION_EFFECT_MISMATCH, target ENVELOPE"]
    X12 --> X18
    X13 --> X18
  end
  subgraph att["effect-attestation: verify"]
    T1["EffectAttestation over one unmodified ExecutionObservation;<br/>role EXECUTING_PROVIDER or INDEPENDENT_OBSERVER is signed"] --> T2{"role expected, tenant equal,<br/>observation digest equal?"}
    T2 -->|no| T3(["ROLE_MISMATCH, WRONG_TENANT, OBSERVATION_MISMATCH"])
    T2 -->|yes| T4["anchor at (identity, key, role capability) via TEA (M5)"]
    T4 --> T5{"anchor found, lifecycle ok,<br/>payload recomputed equal, Ed25519 valid?"}
    T5 -->|no| T6(["typed refusal"])
    T5 -->|yes| T7(["VERIFIED: PROVENANCE_AND_INTEGRITY_ONLY;<br/>factual_correctness_established False"])
  end
  subgraph ra6["RA-6 status-runtime: reassess and revoke"]
    R1["AuthorityReassessor.submit(signal)"] --> R2{"malformed, emergency-stop<br/>via intake, or duplicate?"}
    R2 -->|yes| R3(["IGNORED"])
    R2 -->|no| R4["decide: REVOKE_ENVELOPE, SUBJECT, MODEL,<br/>ADVANCE_EPOCH or NONE"]
    R4 --> R5["AuthorityLifecycleService guard:<br/>principal, tenant, authorizer"]
    R5 --> R6{"authorized?"}
    R6 -->|no| R7(["ERROR_NON_EXECUTABLE"])
    R6 -->|yes| R8{"already applied?"}
    R8 -->|yes| R9(["NO_STATE_CHANGE idempotent"])
    R8 -->|no| R10(["APPLIED: grow-only revocation sets,<br/>monotone epoch, GovernanceEvent"])
    R11["AuthorityStatusCache.sync → RevocationState"] --> R12["StatusAwareActionGate: freshness first,<br/>then the RA gate"]
    R11 --> R13["make_pre_effect_recheck → used by M9 hook"]
  end
  S11 --> R1
  X18 --> R1
  T7 --> X2
```

**Capabilities**

| Package | Entry point | Decides or produces | Boundary `[V]` |
|---|---|---|---|
| `risk-authority-status-runtime` | `AuthorityLifecycleService`, `AuthorityReassessor.submit`, `StatusAwareActionGate`, `make_pre_effect_recheck` | Revocations and epochs; `LifecycleWriteResult`; pre-effect recheck | "Not globally-consistent, cryptographically-attested, multi-region, or zero-window revocation"; Postgres store is a skeleton |
| `risk-authority-runtime-assurance` | `RuntimeAssuranceService.observe` | `TrajectoryAssessment` NORMAL, ESCALATED, UNKNOWN; signal to RA-6 | "RA-7 mints nothing, mutates no lifecycle state" |
| `risk-authority-execution-assurance` | `EffectAssuranceService.assess`, `TrustedEffectIngress` | `EffectAssuranceAssessment` MATCHED, MISMATCH, PARTIAL, CONFLICTED, MANUAL_REVIEW, UNKNOWN, UNVERIFIABLE | "No failure resolves to MATCHED"; production wiring blocked: the only admissible resolver refuses every anchor (RI-4) |
| `risk-authority-effect-attestation` | `mint_effect_attestation`, `Ed25519EffectAttestationVerifier.verify` | Signed attestation; verification result binding role and digests | "A verified signature never means the effect is true"; no production signer |

**Interaction surface.** Outbound: all three RA packages import `risk_authority` (M6); RA-8 imports `decision-authority` (M6), `governance-contracts`, and `risk-authority-effect-attestation`; effect attestation imports `trusted-evidence-authority` (M5) and `governance-contracts`. RA-7 declares RA-6 as a dependency but imports only the leaf-owned intake protocol `[V]`. Inbound: RA-6 is imported by `agent-runtime-governance` (M9); RA-8 by `cloud-scaling-bounded-execution` (M10); effect attestation by RA-8 only.

---

## 15 — M12 Ledger and registry

`control-plane-root`, `ai-system-registry`, `data-use-admission`, `vendor-dependency`, `incident-response`, `benchmark-registry`, `benchmark-registry-authority`. Record.

```mermaid
flowchart TD
  subgraph cpr["control-plane-root: AuditLedger.append"]
    L1["LedgerEntry: tenant, kind, tz-aware recorded_at,<br/>recorded_by, JSON payload, correlation_id"] --> L2{"schema_version matches?"}
    L2 -->|no| L3(["SchemaVersionMismatch: refused, not migrated"])
    L2 -->|yes| L4["BEGIN IMMEDIATE; head = last (tenant_seq, record_digest)<br/>or (0, GENESIS)"]
    L4 --> L5["content_digest = domain_digest(entry);<br/>record_digest = domain_digest(tenant, seq, prev, content)"]
    L5 --> L6["INSERT; triggers refuse UPDATE and DELETE"]
    L6 --> L7(["injected reference_factory → AuditReference<br/>entry_ref tenant/seq"])
    L8["verify_chain(tenant)"] --> L9{"every seq contiguous, prev equal,<br/>digest recomputes?"}
    L9 -->|no| L10(["LedgerIntegrityError at position"])
    L9 -->|yes| L11(["True: tamper-evident, not tamper-proof"])
  end
  subgraph regs["ai-system-registry, data-use-admission, vendor-dependency: declare"]
    D1["record over governance-contracts types:<br/>AssessedSystemBinding, label, Validity"] --> D2{"types exact, tenant equal to binding,<br/>vocabulary binding present on current version,<br/>id == derived id?"}
    D2 -->|no| D3(["ContractViolation"])
    D2 -->|yes| D4{"store: production path durable,<br/>schema current, tenant bound?"}
    D4 -->|no| D5(["RegistryProductionModeError,<br/>StorageError, CrossTenantRefused"])
    D4 -->|yes| D6{"duplicate id?"}
    D6 -->|yes| D7(["DuplicateRegistrationError: never edited"])
    D6 -->|no| D8{"supersession admissible:<br/>predecessor exists, same tenant,<br/>same subject, terms changed?"}
    D8 -->|no| D9(["SupersessionError"])
    D8 -->|yes| D10(["INSERT record_json + record_digest;<br/>reads re-verify digest and omit out-of-window"])
  end
  subgraph inc["incident-response"]
    I1["IncidentRecord: id derived from tenant, subject,<br/>evidence AuditReferences, opened_at"] --> I2["containment_requested → REQUESTED"]
    I2 --> I3{"lift: request digest, tenant,<br/>target, incident equal, lifted_at at least requested_at?"}
    I3 -->|no| I4(["ContainmentLiftRefused"])
    I3 -->|yes| I5(["LIFTED; closing never lifts, lifting never closes"])
    I2 --> I6(["signal_for_containment: ReassessmentSignalPayload<br/>returned, never delivered"])
  end
  subgraph br["benchmark-registry and authority"]
    B1["CanonicalBenchmarkDefinitionIdentity"] --> B2{"approval binds this content_digest;<br/>publisher != approving authority?"}
    B2 -->|no| B3(["refused"])
    B2 -->|yes| B4(["structural_refusals_at never empty:<br/>BENCHMARK_RESOLUTION_NOT_PERFORMED"])
    B5["BenchmarkEd25519Verifier.verify_publisher_submission"] --> B6["directory anchor at exact (role, identity, key)"]
    B6 --> B7{"anchor matches asked triple,<br/>profile ED25519_SHA512_V1,<br/>libsodium point valid, signature valid?"}
    B7 -->|no| B8(["REFUSED or INDETERMINATE"])
    B7 -->|yes| B9(["VERIFIED with anchor revision"])
    B10["plan_submission_outcome(snapshot, record)"] --> B11{"slot"}
    B11 -->|empty| B12(["plan SUBMITTED"])
    B11 -->|byte-identical| B13(["IDEMPOTENT_DUPLICATE"])
    B11 -->|same locator, different bytes| B14(["COORDINATE_SLOT_CONFLICT"])
    B11 -->|digest elsewhere| B15(["DIGEST_ALREADY_BOUND"])
  end
```

**Capabilities**

| Package | Entry point | Decides or produces | Boundary `[V]` |
|---|---|---|---|
| `control-plane-root` | `AuditLedger.append`, `read_entries`, `verify_chain` | Per-tenant hash chain in SQLite; `AuditReference` via injected factory | "Appends and returns a reference. Decides nothing"; unsigned chain |
| `ai-system-registry` | `SqliteSystemRegistry.register` | Append-only registrations with derived ids | "Not an operational registry"; "a registration is a record, not a permission" |
| `data-use-admission` | `SqliteDataUseDeclarations.declare` | Declarations of data use by reference | "Not an admission engine"; residency recorded, never evaluated |
| `vendor-dependency` | `SqliteVendorDeclarations.declare` | Vendor dependency declarations linked to a policy by text | "Not a policy resolver"; `policy_ref` is text |
| `incident-response` | `IncidentRecord`, `ContainmentRequest`, `signal_for_containment` | Records and a reassessment payload, never delivered | "Records only"; "nothing here detects anything" |
| `benchmark-registry` | `CanonicalBenchmarkDefinitionIdentity`, lifecycle predicates | Digest-bound identity; refusal tuple never empty | "Contracts only; no registry" |
| `benchmark-registry-authority` | `BenchmarkEd25519Verifier`, `plan_transition`, `plan_submission_outcome` | Verified or refused envelopes; transition plans | "Candidate, not release"; cannot admit, register, revoke or resolve |

**Interaction surface.** Outbound: the four record packages and incident-response import only `governance-contracts`; `control-plane-root` and `benchmark-registry` import nothing; the authority imports `benchmark-registry`. Inbound: `control-plane-root` is imported by `governed-review-service` and `governed-review` (M7) only; nothing imports the registries, incident-response or the benchmark authority `[V]`. The other append-only ledgers in the platform (risk_authority, approval-workflow, execution-reservation, authority-directory, policy-authority SQLite, ai-hiring domain audit) are separate stores that do not write to `control-plane-root`; see section 19.

---

## 16 — M13 Value and readiness, M14 Domain products

```mermaid
flowchart TD
  subgraph avr["agent-value-readiness: assess_readiness"]
    V1["1 resolve policy through PolicyAuthorityReadinessPolicyResolver (M1);<br/>deny-all if omitted"] --> V2{"resolved?"}
    V2 -->|no| V3(["NOT_EVALUATED: no classification"])
    V2 -->|yes| V4{"2 AssessedSystemBinding present<br/>and consistent?"}
    V4 -->|no| V3
    V4 -->|yes| V5["3 gate results attested by verifier;<br/>unverified treated as absent<br/>4 conditions verified<br/>5 indicators admitted against catalogs"]
    V5 --> V6["6 evaluate_readiness once over sanitized case"]
    V6 --> V7{"R0 policy bound, active, effective?"}
    V7 -->|no| V8(["NOT_ASSESSABLE"])
    V7 -->|yes| V9{"R1 mandatory FAIL?"}
    V9 -->|yes| V10(["NOT_READY"])
    V9 -->|no| V11{"R2-R3 structural gap or mandatory INDETERMINATE?"}
    V11 -->|yes| V8
    V11 -->|no| V12{"R4-R5 uncovered concern?"}
    V12 -->|yes| V10
    V12 -->|no| V13(["PILOT_READY or READY_WITH_CONDITIONS;<br/>advisory, unsigned"])
  end
  subgraph gv["governed-value: score"]
    W1["admit_observations: exact MetricObservation (M0),<br/>tenant and unit equal, ids unique"] --> W2{"all admitted?"}
    W2 -->|no| W3(["ObservationBindingError: no result"])
    W2 -->|yes| W4["reported_ngv = benefit - losses - cost;<br/>risk_adjusted = reported - residual expected loss"]
    W4 --> W5{"fatal: no baseline, outcome needs<br/>holdout, discovery insight?"}
    W5 -->|yes| W6(["NOT_SCORABLE: ROI and payback None"])
    W5 -->|no| W7(["SCORABLE or DEGRADED;<br/>fixed EvidenceStatus REPORTED, AuthorityStatus UNVERIFIED"])
  end
  subgraph proc["procurement: ProcurementAPI.run"]
    P1["validate request; six deterministic checks"] --> P2["kernel case; advisory recommendation<br/>DETERMINISTIC_POLICY"]
    P2 --> P3["record_decision with AuthorityType HUMAN_APPROVER"]
    P3 --> P4["request_action; bind CER; submit_for_authorization"]
    P4 --> P5{"BudgetAuthorityAdapter"}
    P5 -->|CER expired| P6(["EXPIRED"])
    P5 -->|restricted or above hard limit| P7(["DENIED"])
    P5 -->|above threshold| P8(["AUTHORIZED_WITH_CONSTRAINTS senior_approval_required"])
    P5 -->|else| P9(["AUTHORIZED"])
    P9 --> P10["explicit dispatch; offline supplier adapter;<br/>reconcile_execution"]
    P10 --> P11(["ProcurementRunResult; compensation_required flag"])
  end
  subgraph hire["ai-hiring: DecisionService.create"]
    H1["advisory Recommendation: actor AI, binding False"] --> H2{"human actor authenticated?"}
    H2 -->|no| H3(["audited denial, security=True"])
    H2 -->|yes| H4{"evaluation REVIEW_BLOCKED?"}
    H4 -->|yes| H3
    H4 -->|no| H5{"disposition diverges without Override?"}
    H5 -->|yes| H3
    H5 -->|no| H6(["Decision actor_type HUMAN;<br/>hash-chained domain audit event"])
    H6 --> H7["HiringActionProposalService: only HUMAN_REVIEWER,<br/>HUMAN_APPROVER, COMMITTEE authority"]
  end
```

**Capabilities**

| Package | Module | Entry point | Decides or produces | Boundary `[V]` |
|---|---|---|---|---|
| `agent-value-readiness` | M13 | `assess_readiness`, `evaluate_readiness` | `ReadinessAssessmentOutcome` EVALUATED or NOT_EVALUATED; classification NOT_READY, NOT_ASSESSABLE, PILOT_READY, READY_WITH_CONDITIONS | "Experimental, internal, advisory, non-financial"; "no allow-all verifier ships" |
| `governed-value` | M13 | `GovernedValueApplication.score` | `GovernedValueResult` with money terms and optional ratios | "Can never claim OBSERVED, ATTRIBUTED, VERIFIED, whatever the caller named an input" |
| `ai-hiring` | M14 | `build_in_memory_platform`, `DecisionService.create` | Binding human `Decision`; advisory `Recommendation`; chained audit | "Ships no AI scoring model"; only `DETERMINISTIC_SIMULATION` supported |
| `procurement` | M14 | `ProcurementAPI.run` | `ProcurementRunResult` through the Decision Authority kernel | "Deterministic and offline"; `pilot_validated False`, `production_certified False` |

**Interaction surface.** M13 outbound: `agent-value-readiness` imports `uvi-policy-contracts` and `policy-authority` (M1) and `governance-contracts`; `governed-value` imports one symbol, `MetricObservation`, from `governance-contracts`. Neither reads any M12 store `[V]`. M14 outbound: `procurement` imports only `decision-authority` (M6); `ai-hiring` imports `decision-authority`, the provider framework, `actiongate` (M8) and `tap` (M5). Inbound: nothing imports M13; M14 is imported lazily by the compiler's reference equivalence checks only.

---

## 17 — Inter-module interaction: verified import edges

Every edge below is a `from ugence_* import` or `from risk_authority import` found in `packages/*/src` `[V]` (recomputed 2026-09-10; test-only references excluded). Direction is importer to imported.

```mermaid
flowchart LR
  M1["M1 Policy authority"]
  M2["M2 Constitution"]
  M3["M3 Proposal, advisory"]
  M4["M4 Research"]
  M5["M5 Evidence, trust"]
  M6["M6 Decision, risk authority"]
  M7["M7 Human approval"]
  M8["M8 Clearance"]
  M9["M9 Governed runtime"]
  M10["M10 Execution ladder"]
  M11["M11 Post-effect"]
  M12["M12 Ledger, registry"]
  M13["M13 Value"]
  M14["M14 Products"]
  M2 --> M1
  M2 --> M3
  M3 --> M1
  M3 -->|risk-integration| M6
  M3 -->|token accounting| M9
  M4 --> M1
  M4 --> M3
  M5 -->|evidence runtime| M6
  M7 -->|veto contracts| M6
  M7 -->|CompositionInputs, schema| M9
  M7 -->|audit ledger| M12
  M8 -->|execution types| M6
  M9 -->|compose| M6
  M9 -->|pre-effect recheck| M11
  M10 --> M1
  M10 --> M3
  M10 --> M5
  M10 --> M6
  M10 --> M8
  M10 --> M11
  M11 --> M5
  M11 --> M6
  M13 --> M1
  M14 --> M5
  M14 --> M6
  M14 --> M8
  M1 -.->|compiler reference checks, lazy| M14
  M1 -.->|utc_now only| M6
```

M0 is omitted from the drawing: M1, M3, M4, M5, M7, M8, M10, M11, M12, M13 and M14 each import it. M12 imports only M0.

| Importer | Imported | Carrying packages and symbols `[V]` |
|---|---|---|
| M1 | M0, M6, M14 | `uvi-policy-contracts` → contracts; compiler → `decision-authority.utc_now`, `ai-hiring` and `procurement` reference modules (lazy, optional extras) |
| M2 | M1, M3 | all five → `policy-authority.api`; policy and runtime → `agentic-proposer` `ReasoningStrategy`, `CandidateDisposition`, `ReviewAction`, `StrategyPolicyRequest`, `StrategyPolicyResponse` |
| M3 | M0, M1, M6, M9 | `jcs.canonical_sha256_hex`; `reasoning-method-governance` → `GovernedThreshold`; `cloud-scaling-risk-integration` → `risk_authority.integrations.SubjectRiskDecision`, `validate_subject_binding`; token accounting → `agent-runtime.ProviderAttempt`, `BudgetCoordinator` |
| M4 | M0, M1, M3 | `readiness-comparison` → `ComparisonOperator`; `workflow-fit-pilot` → `reasoning-method-governance`, `reasoning-method-advisor` |
| M5 | M0, M6 | `risk-authority-evidence-runtime` → `RiskAuthorityApplication`, `ControlAssurancePort`, `EvidenceAdmissionPort`, `bind_control_result` |
| M7 | M0, M6, M9, M12 | `governed-review` → `risk-authority-runtime.GovernanceVetoResult`, `VetoDisposition`; `agent-runtime-governance.CompositionInputs`; service → `control-plane-root.AuditLedger`, `LedgerEntry`; `durable-execution.SCHEMA_NAME` |
| M8 | M0, M6 | `execution-reservation` → `decision-authority.ExecutionIntent`, `ExecutionAttempt`, `ExecutionRecord`, `ReconciliationResult` |
| M9 | M6, M11 | `agent-runtime-governance` → `RiskAuthorityCompositionEngine`, `FinalDisposition`; `risk-authority-status-runtime.make_pre_effect_recheck`, `PreEffectContext` |
| M10 | M0, M1, M3, M5, M6, M8, M11 | see section 13; six packages import `risk_authority`; 5D imports `execution-reservation`, `risk-authority-execution-assurance.EffectObservation` |
| M11 | M0, M5, M6 | RA-6, RA-7, RA-8 → `risk_authority`; RA-8 → `decision-authority` kernel services; effect attestation → `trusted-evidence-authority` anchors |
| M12 | M0 | `AuditReference`, `AssessedSystemBinding`, labels, `Validity` |
| M13 | M0, M1 | `agent-value-readiness` → `PolicyResolution`, `ReadinessPolicy`; `governed-value` → `MetricObservation` |
| M14 | M0, M5, M6, M8 | `ai-hiring` → `TAPProvider`, `ActionGateProvider`, kernel; `procurement` → kernel contracts |

Six packages exist under `packages/` that the 66-package map does not assign: `console-api`, `clearance-export`, `authoritative-policy-compilation`, `procurement-policy-compilation`, `reasoning-method-result-attestation`, `workflow-converters` `[V]`. They are excluded from the edges above.

## 18 — The designed flow against the code

The high-level diagram draws nine hops. This is what carries each one.

| Hop on the module map | Mechanism in code | Status |
|---|---|---|
| M3 proposal → M9 hook | No import. The runtime receives a `WorkflowDefinition`; nothing in M9 reads a `ProposerAdvisory`. The only M3 to M9 edge is token accounting, which flows the other way (runtime attempts into accounting). | `[G]` composition-root wiring, none in repo |
| M2 constitution → runtime | No import into M9. The proposer takes `constitution_resolution` and a `StrategyPolicyResolver` as injected arguments; M2 imports M3's enums. | `[G]` injection at a composition root |
| M1 signed policy → M6 authority | No import from M6 to M1. Risk Authority binds a `WorkflowIR` digest, not an `IssuedPolicyRecord`. M1 reaches an envelope only through M10's policy-authenticity binding for capacity actions. | `[G]` for the general path; `[V]` for cloud scaling |
| M5 trusted evidence → M6 | `risk-authority-evidence-runtime` wraps `RiskAuthorityApplication`; TAP reaches it by the neutral provider contract. | `[V]` |
| M7 approval → M6 | `governed-review` rewrites the Decision Authority veto result inside `CompositionInputs` after consuming the approval. | `[V]` |
| M6 envelope → M8 clearance | For the agent-runtime path the "clearance" is M6's composition engine projected by M9's hook onto CLEAR, HOLD, BLOCK, ESCALATE. `action-clearance` and `execution-reservation` are imported only by M10 and `clearance-export`. Two clearance vocabularies coexist by string value. | `[V]` for M10; `[G]` for M9 |
| M8 CLEAR + ACQUIRED → M10 | 5X and 5D import `execution-reservation` and require a `RESERVED` reservation with a live lease. | `[V]` |
| M10 effect → M11 | 5D imports RA-8's `EffectObservation` and returns one per dispatch. RA-8's production `MATCHED` path is blocked by the deny-all anchor resolver. | `[V]` structure; `[G]` production |
| M11 reassess → M6 | RA-7 and RA-8 emit `AuthorityReassessmentSignal`; RA-6 decides and its sole writer revokes or advances the epoch; M9's recheck reads the result. | `[V]` |
| everything → M12 ledger | Only `governed-review-service` writes to `control-plane-root`. Risk Authority, approval-workflow, execution-reservation, authority-directory and policy-authority each keep their own hash-linked SQLite `ledger_events` table, and `ai-hiring` chains its domain audit events by `previous_event_hash`. | `[G]` one chain per tenant does not exist |
| M12 receipts → M13 | Neither M13 package reads any M12 store. `governed-value` admits `MetricObservation` receipts from M0; readiness resolves policy from M1. | `[G]` |

## 19 — Findings surfaced while drawing

1. **Two clearance paths** `[V]`. Agent Runtime clears through `risk-authority-runtime` composition plus RA-6 recheck; the cloud-scaling ladder clears through `action-clearance` receipts plus `execution-reservation`. Neither path imports the other's vocabulary; both use CLEAR, HOLD, BLOCK, ESCALATE by string.
2. **Seven independent append-only ledgers** `[V]`: `control-plane-root` plus the six listed in section 18. The module map's "one append-only audit chain per tenant" describes `control-plane-root` alone, which has one writer. `decision-authority` reserves `previous_event_hash` but does not chain yet.
3. **Declared but unimported dependencies** `[V]`: `risk-authority-runtime` declares `decision-authority` and `actiongate`; `risk-authority-evidence-runtime` declares `tap`; RA-7 declares RA-6. Each couples by enum value or protocol, so the wheel graph overstates the import graph.
4. **Stale README statements** `[V]`: `risk-authority-effect-attestation` says "not wired into RA-8" while RA-8 imports and calls it (no production wiring, RI-4); `agent-workforce-composer` says ranking and composition "remain unimplemented" while `ranking.py`, `composition.py`, `plan.py` ship; `agent-runtime-governance` module docstring says ESCALATE has no sink while its README corrects this on 2026-09-08.
5. **The reasoning-method admission bridge is unwired** `[V]`. `to_proposer_input` exists in the advisor and `ReasoningMethodAdvisoryInput` exists in the proposer; no source file under `packages/*/src` connects them.
6. **No kubectl adapter exists** `[V]`. Mutation reaches Kubernetes only through an injected `AppsV1Api` client and ArgoCD through an injected HTTP caller.
7. **`jcs` is not the platform canonicalizer** `[V]`. Five packages use it; Policy Authority, the compiler, the capacity-bounds family and every SQLite ledger use their own sorted-key JSON helper.

## 20 — Next step

Findings 1 and 2 are the two places where the drawn flow and the code disagree about authority and record. Each needs an owner ruling before any composition root is written. Ruling 1: which clearance path is canonical for a hosted-boundary provider, and does the other retire or federate. Ruling 2: whether `control-plane-root` becomes the sink for the six other ledgers by a linkage entry, as `governed-review-service` already does, or whether "one chain per tenant" is withdrawn from the module map.

> Read `docs/UGENCE_MODULE_FLOWCHARTS.md` sections 18 and 19. For finding 1, cite the exact symbols where the two clearance vocabularies meet (`agent-runtime-governance/dispositions.py`, `action-clearance/models/enums.py`, `execution-reservation/receipts.py`) and state whether a hosted-boundary provider per `docs/UGENCE_PREVENTIVE_DETECTIVE_MODULE_MAP.md` §8 would clear through composition, through receipts, or both. For finding 2, list each ledger's table, chain digest function and writer with `file:line`, and state whether a linkage entry into `control-plane-root` of the kind `governed-review-service/linkage.py` appends is sufficient for the receipt's `audit_ref` field. End with two owner rulings, each one sentence. Max 700 words. Documentation only; change no code.
