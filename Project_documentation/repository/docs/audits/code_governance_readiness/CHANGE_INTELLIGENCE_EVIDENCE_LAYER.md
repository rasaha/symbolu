# Code Change Intelligence — Evidence Layer for Hidden-Bug & Hidden-Bloat Detection

> Documentation only. Companion to `CODE_GOVERNANCE_IMPLEMENTATION_READINESS_AUDIT.md`.
> Authoritative technical source: `UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md` v0.2. Verified against live
> code at commit `3ec11e4e`. **No runtime, package, contract, provider, API snapshot, or frozen
> artifact is changed by this document.** Machine-readable companion:
> `change_intelligence_evidence_profiles.json`.

## 0. Thesis (evaluated and confirmed)

> **Ugence Code Governance (UGC) can *govern* hidden-bug and hidden-bloat detection, but it cannot
> *discover* defects merely by being a governance layer.**

This is **architecturally correct and fully consistent with the v0.2 design and this readiness
audit.** UGC's role is: collect evidence, decide whether it is sufficient and trustworthy, obtain an
authorized decision, and permit only the exact validated change to merge/deploy. Therefore:

- UGC **can force** hidden-bug and bloat analysis to occur (policy makes it mandatory);
- UGC **can reject** a change when required analysis is missing or fails (fail-closed gates);
- UGC **can prevent** the coding agent from validating its own work (independence + evidence-tier);
- UGC **cannot guarantee** detection of a defect that every connected validator, test, and reviewer
  failed to expose.

**The correct fix is not to turn TAP, ActionGate, or Decision Authority into code analyzers.** It is
to add an **upstream Code Change Intelligence evidence layer** whose outputs are risk-dependent,
**mandatory, non-compensatory** inputs to the existing chain. This document evaluates that idea
against the live contracts and specifies how it slots in without changing any frozen artifact.

### The distinction (this is the load-bearing idea)

| Layer | Question it answers | Owner |
|---|---|---|
| **Detection** | "What defects, regressions, or unnecessary code may exist?" | Change Intelligence validators (evidence producers) |
| **Governance (UGC)** | "Were the required independent detection methods run, are their claims supported by admissible evidence, and is this exact change authorized?" | TAP → Decision Authority → ActionGate → ACP |

## 1. Where it fits (mapped to live seams)

```
AI-generated (or human) patch
        ↓
Code Change Intelligence  (PRODUCT evidence producers — NO authority)
  ├── semantic / differential / property / fuzz / metamorphic / mutation validators
  ├── static & data-flow / security validators
  ├── dependency & supply-chain analyzer
  ├── performance & resource-budget analyzer
  ├── bloat & complexity analyzer
  ├── architecture-drift analyzer
  └── AI-change provenance validator
        ↓ ValidationEvidenceBundle → immutable evidence_refs + signed claim manifest
GitHub Evidence Connector  (stores artifacts, emits refs — NO authority)
        ↓ AssertionGovernanceRequest.evidence_refs
TAP  (ASSERTION_GOVERNANCE)  → AssertionGovernanceResult (per-claim coverage)
        ↓ verified assessment
Code Governance Workflow Service  (applies non-compensatory gates from policy; fails closed)
        ↓
Decision Authority  → DecisionRecord (binding)
        ↓ CER
ActionGate  → ActionGovernanceResult (exact-change authorization)
        ↓
ACP  → live clearance
        ↓
GitHub Execution Provider  → exact merge
```

**This is exactly the `evidence_refs → TAP → Decision Authority → ActionGate → ACP` seam this audit
already documented** (`EVIDENCE_AND_TAP_MAPPING.md`, `AUTHORITY_BOUNDARY_MATRIX.md`). Change
Intelligence is the concrete population of the design's `ValidationEvidenceBundle` (§6) — the bundle
stays product-side; only its immutable `evidence_refs` enter the governance request.

## 2. Architectural placement — evidence producers, not authorities

**Verdict: Change Intelligence validators are `PRODUCT_ADAPTER` / `PRODUCT_RECORD` evidence
producers** (per the classification in `EVIDENCE_AND_TAP_MAPPING.md`). Consequences, all confirmed
against live contracts:

- **No new `ProviderKind`.** Validators do not register as governance providers. They are product
  code that produces evidence; TAP remains the sole `ASSERTION_GOVERNANCE` provider. Adding a family
  would be a MAJOR freeze change (`platform/PLATFORM_FREEZE_V1.json:21`) and is unnecessary.
- **No frozen-contract change.** Each validator's output becomes (a) stored artifacts behind
  immutable `evidence_refs` and (b) structured **claims** carried into
  `AssertionGovernanceRequest.evidence_refs` (`contracts/assertion.py:26`). Claim → coverage mapping
  is TAP's existing job (`AssertionCoverage`).
- **They own no authority.** They cannot approve, authorize, clear, or merge. Same boundary as the
  GitHub Evidence Connector (`PROVIDER_ROLE_MATRIX.md`).

### Package boundary (extends `PRODUCT_PACKAGE_BOUNDARY.md`)

```
products/code-governance/
  change_intelligence/           # NEW subsystem — evidence producers
    risk_classifier/             # change-risk classification (LOW/MEDIUM/HIGH)
    semantic_regression/         # differential + metamorphic coordination
    test_intelligence/           # property/fuzz/mutation coordination + adequacy
    security_dataflow/           # taint/nullability/concurrency/authz-flow adapters
    dependency_supplychain/      # dependency delta + SBOM diff + vuln lookup
    bloat_complexity/            # code/dep/duplication/complexity/reachability/API/artifact deltas
    architecture_drift/          # forbidden-edge / layer-violation deltas
    performance_budget/          # latency/memory/allocation/I/O/startup deltas
    provenance_validator/        # AI-change provenance + validator identity/version binding
    evidence_manifest/           # signed, SHA-bound ValidationEvidenceBundle + claim manifest builder
```

These sit **upstream of** `evidence_mapping/` (which projects them to neutral `evidence_refs`). Most
validators are **thin adapters over external tools** (compilers, fuzzers, mutation frameworks, SAST,
SBOM/vuln feeds, profilers), not net-new analyzers — the value is normalization, provenance binding,
and delta computation, not re-implementing analysis engines.

## 3. Contract mapping — what each validator emits

Every validator emits, per finding: an **immutable evidence ref** (content-addressed artifact) plus a
**claim** with provenance. This reuses the pervasive content-hashing already in the evidence subsystem
(`with_fingerprint`, `content_hash`, `stable_hash`) and the design's provenance model.

| Producer output | Neutral carrier | Classification | Live anchor / gap |
|---|---|---|---|
| differential/property/fuzz/metamorphic/mutation results | claim + `evidence_refs` → TAP | PRODUCT_ADAPTER | REUSE `AssertionGovernanceRequest.evidence_refs`; producers MISSING |
| static / data-flow / security findings | claim + `evidence_refs` → TAP | PRODUCT_ADAPTER | REUSE seam; producers MISSING |
| dependency / SBOM delta + vuln lookup | claim (`dependency_scan_results`) + refs | PRODUCT_ADAPTER | design §16.2; producers MISSING |
| bloat / complexity / reachability / artifact / API deltas | claim + refs (delta values) | PRODUCT_RECORD | **new** evidence pack (§5) |
| architecture-drift edges | claim + refs; **also feeds StoryGraph** | PRODUCT_RECORD | design §16.3 pattern pack |
| performance / resource deltas | claim (`benchmark_results`) + refs | PRODUCT_ADAPTER | design §6 `ValidationEvidenceBundle`; producers MISSING |
| **validator identity + version** on every ref | evidence provenance binding | **NEW (product record or neutral field)** | **gap R18** — evidence types lack a validator-id/version field today |
| signed claim manifest | product schema → `evidence_refs` | PRODUCT_PUBLIC | **no `ClaimManifest` type exists** (nearest: TAP E5 `EvidencePacket`) |

**Key reinforcement of the audit:** this idea depends on two prerequisites the audit already flagged
as missing — a **signed claim manifest** and **validator-identity/version binding on evidence**
(R18). Change Intelligence makes them mandatory, not optional.

## 4. Hidden functional bugs — required detection methods

Ordinary unit tests answer "does the code pass the examples we anticipated?" Hidden bugs live outside
those examples. Each method below is an evidence producer; UGC requires the **method to have run** and
its **claims to be admissible**, per risk tier.

| Method | Catches | Oracle / applicability | Claim produced | Honest limit |
|---|---|---|---|---|
| **Differential testing** | behavioral divergence in refactors/optimizations/rewrites/parsers/serializers | needs an **oracle** (old vs new impl) — only for replacements/refactors, not new features | "new behaves identically to old on corpus C" | no oracle for greenfield features |
| **Property-based testing** | invariant violations (`serialize(deserialize(x))==x`; `authorization cannot increase after clearance`; idempotent retry ≠ duplicate) | invariants, not examples | "invariants I hold over generated domain" | invariant selection is human/AI judgment |
| **Fuzz testing** | boundary/adversarial/malformed inputs the author didn't anticipate | no oracle needed (crashes/asserts) | "no crash/assert/leak over N fuzz iters" | nondeterministic; flake handling (§16.7) needed |
| **Metamorphic testing** | relation-preservation where no exact oracle exists | metamorphic relations | "transform T preserves relation R" | relations are domain-specific |
| **Mutation testing** | **test suites that merely confirm the implementation** (critical for AI-authored tests) | inject defects; surviving mutants ⇒ weak tests | "mutation score ≥ threshold on touched code" | expensive; scope to sensitive modules |
| **Static / data-flow** | taint, uninitialized state, nullability, races, authz-flow, secrets, unsafe deserialization, injection | SAST/dataflow tools | "no critical finding in class X" | false positives; tool coverage varies |
| **Contract / compatibility** | broken public APIs, schema drift, changed defaults, serialization/exception/event-ordering changes, back-compat breaks | API/schema baselines | "no breaking API/schema delta (or approved exception)" | needs a stable baseline artifact |
| **Adversarial independent review** | what automated methods miss; the model refuting the patch, not summarizing it | a **different** model or human | "independent reviewer found no blocking issue" | independence must be enforced (§9) |

**Evidence-tier rule (design §9.2, confirmed):** candidate-**generated** tests **cannot alone** satisfy
mandatory validation. Mutation adequacy is the mechanism that exposes self-confirming AI tests. This
directly hardens the "AI validating its own work" failure mode.

## 5. Hidden bloat — Bloat & Architecture Evidence Pack

AI-generated code often passes tests while adding unnecessary abstractions, duplicate implementations,
speculative generality, unused helpers, dependency proliferation, redundant validation layers, and
layering violations — each piece looks reasonable in isolation, so ordinary review misses the
aggregate. This is a **new, delta-based evidence pack** (the measure is the **change delta**, not an
arbitrary total-code threshold).

| Dimension | Evidence (delta) |
|---|---|
| Code growth | net executable lines; generated-code delta |
| Dependency growth | new direct/transitive packages; package size; SBOM diff |
| Duplication | clone / semantic-duplicate detection |
| Complexity | cyclomatic / cognitive / nesting deltas |
| Reachability | added code no production path invokes (**advisory** — see limits) |
| API growth | new public types/flags/options/extension points |
| Runtime cost | latency / memory / allocation / I/O / startup delta |
| Artifact size | wheel / bundle / binary / image / container growth |
| Architecture drift | new forbidden dependency edges / layer violations |
| Configuration bloat | new switches / env vars / policy branches |
| Test effectiveness | coverage **and mutation sensitivity** (not coverage alone) |
| Maintenance burden | new owners / services / migrations / operational states |

Example delta claim → policy budget:

```
This PR adds: +4% executable code · +1 direct dependency · +18 MB container ·
              +12% p95 latency · +3 public config flags
→ policy: bloat budget exceeded on {dependency, artifact_size, latency}
        → JUSTIFICATION_REQUIRED or DENY (per repository policy)
```

**Limit (honest):** reachability/dead-code is undecidable in general (dynamic dispatch, reflection,
plugins). Treat "unreachable added code" as an **advisory signal → escalation**, never a hard
auto-DENY, and let StoryGraph corroborate sequence patterns.

## 6. Risk-adaptive evidence profiles

Not every PR needs fuzzing, mutation testing, and multiple reviewers. UGC classifies the change first
(a `risk_classifier` product component), then applies a **required evidence profile** — expressed in
the repository policy pack (`POLICY_OWNERSHIP_MATRIX.md`; policy `scope.paths` in design §10).

| Risk | Examples | Minimum governance evidence |
|---|---|---|
| **LOW** | docs, comments, internal renaming | build · unit tests · static checks · basic bloat delta |
| **MEDIUM** | feature logic, API changes, new deps, perf-sensitive paths | LOW + differential/property tests · dependency & performance checks |
| **HIGH** | auth, authorization, payments, data deletion, crypto, governance policy, deploy controls, credentials, safety boundaries | MEDIUM + mutation/fuzz · independent reviewer · security approval · explicit human authority |

This maps onto existing mechanisms: risk tier → policy `required_evidence` + `approval` block →
`AuthorityContext.required_approvals` / `segregation_of_duties` / `AuthorityType` roles. HIGH risk is
also where **Competitive Validation Mode** (design §12) and StoryGraph escalation apply.

Machine-readable profiles: `change_intelligence_evidence_profiles.json`.

## 7. Non-compensatory gates (the critical correctness point)

**UGC must not average all evidence into one quality score.** A high test score must never compensate
for an untrusted validator, missing security analysis, an unsigned manifest, an unauthorized reviewer,
a changed head SHA, failed mutation testing, unexplained dependency growth, a severe performance
regression, or a prohibited architecture edge.

**Grounding caveat:** TAP's `AssertionGovernanceResult` carries `evidence_coverage: float`
(`contracts/assertion.py:44`) — a **per-claim** coverage fraction. The mandatory-gate logic must
**not** be collapsed into that float. Non-compensatory gating lives in **policy + the Workflow
Service + Decision Authority + ActionGate**, using TAP's *per-claim* `coverage` (`SUPPORTED /
UNSUPPORTED / INDETERMINATE / CONSTRAINED`), not a blended number. This mirrors the design's authority
hierarchy (§5): a preferred outcome never overrides failing mandatory tests, security failures, missing
evidence, invalid reviewers, SoD violations, a changed artifact SHA, or an expired authorization.

| Gate condition | Outcome | Where enforced | Workflow state |
|---|---|---|---|
| required evidence missing | INCOMPLETE / ESCALATE | Workflow Service (policy) | `EVIDENCE_PENDING` / `ESCALATED` |
| critical validator failed | DENY | Decision Authority (policy) | `DENIED` |
| evidence bound to old head SHA | STALE | Workflow Service (re-entry) | `SUPERSEDED` |
| bloat budget exceeded | JUSTIFICATION_REQUIRED or DENY | policy → Decision Authority | `DECISION_PENDING` / `DENIED` |
| security approval missing | DECISION_PENDING | Decision Authority | `DECISION_PENDING` |
| all mandatory evidence admitted | decision may proceed | — | `APPROVED` |

These map onto the states in `STATE_MACHINE.md` and the outcomes in `DECISION_AND_CER_MAPPING.md`.
**Fail-closed is the default** — missing mandatory evidence never fails open.

## 8. AI-specific controls (AI-Generated Change Policy Pack)

Consistent with design §16.1 (anti-gaming) and §9 (independence); enforced through policy + evidence:

1. The generating agent **cannot** be the final validating authority. *(SoD; `AuthorityType` has no AI member.)*
2. Tests created by the same agent are **not sufficient evidence** by themselves. *(evidence-tier §9.2; mutation adequacy.)*
3. An **independent** validator must challenge the implementation. *(adversarial review; model diversity.)*
4. Generated code must carry **provenance**. *(`PatchCandidate.independence_profile`; provenance validator.)*
5. Added dependencies require **explicit purpose + alternatives analysis**. *(dependency analyzer + justification.)*
6. Large generated patches require **decomposition or elevated review**. *(risk classifier + churn signal.)*
7. Repair patches are **new candidates**, fully revalidated. *(re-entry rule §7/§8; different `diff_digest`.)*
8. Changes to tests/CI/policies/validators get **higher scrutiny**. *(same-candidate policy-tampering detection; StoryGraph.)*
9. Sensitive code **cannot merge solely through AI approvals**. *(HIGH-risk profile requires human authority.)*
10. The exact approved head/base/merge artifact stays **bound through execution**. *(`EXACT_MERGE_IDENTITY.md`; §4.6/§4.7.)*

## 9. Sequence-level detection (StoryGraph, advisory)

Some dangerous changes are harmless individually — reduce coverage → weaken branch protection → alter
authorization → add a privileged path. This is exactly the **StoryGraph control-erosion pattern pack**
(design §16.3), which this audit confirmed is advisory (`OBSERVE/ESCALATE/UNAVAILABLE` only). Change
Intelligence's architecture-drift and test-effectiveness deltas **feed** StoryGraph, which contributes
sequence-risk evidence to Decision Authority; UGC then escalates the current change based on the
accumulated sequence, not the PR in isolation. StoryGraph never blocks on its own.

## 10. Escaped defects — extend to deployment (MVP3)

No pre-merge system finds every hidden bug. The authorization chain should eventually extend to
deployment (design MVP3; `IMPLEMENTATION_SEQUENCE.md` phase I):

```
Merge authorization → controlled deployment → canary / shadow execution →
runtime invariants & regression telemetry → promote / pause / rollback
```

Runtime evidence (latency, memory, error-rate, unexpected authorization decisions, unreachable
features, infra cost) exposes what static analysis and tests missed, and feeds ACP runtime signals.
This remains **deployment governance**, not the core PR reviewer.

## 11. Maturity (honest)

**None of the Change Intelligence validators exist in the canonical packages/products today**
(verified: no mutation/fuzz/property/differential/metamorphic/complexity/duplication/bloat/dead-code/
taint analyzers in `packages/` or `products/`). They are **MISSING / net-new**, mostly as thin
adapters over external tools. The two enabling contracts they need — **signed claim manifest** and
**validator-identity/version binding on evidence** — are also missing (audit R18). The building blocks
that *do* exist and can be reused: content-hashing/provenance in the evidence subsystem, TAP's
`evidence_refs` seam, StoryGraph for sequence risk, and Model Selection for routing reviewer/generator
models within a governance budget (design §16.5).

| Change Intelligence component | Maturity | Note |
|---|---|---|
| Semantic Regression Analyzer (differential/metamorphic) | MISSING | adapter over test harnesses |
| Property/Fuzz/Mutation Test Coordinator | MISSING | adapter over hypothesis/fuzzers/mutation frameworks |
| Security & Data-Flow Evidence Adapter | MISSING | adapter over SAST/dataflow tools |
| Dependency & Supply-Chain Analyzer | MISSING | SBOM diff + vuln feed (design §16.2) |
| Bloat & Complexity Analyzer | MISSING | new delta-based pack (§5) |
| Architecture Drift Analyzer | MISSING | reuses dependency-direction concepts; feeds StoryGraph |
| Performance & Resource Budget Analyzer | MISSING | profiler adapter |
| AI-Change Provenance Validator | MISSING | binds validator id/version (R18) |
| Evidence Manifest Builder | MISSING | signed, SHA-bound bundle + claim manifest (PRODUCT_PUBLIC) |

## 12. MVP priority (bounded first version)

Aligns with `IMPLEMENTATION_SEQUENCE.md` (fits phases B–D as a Change Intelligence workstream; all
shadow/recommendation, no enforcement, no GitHub writes until phase F):

1. change-risk classification;
2. duplicate & dead-code detection (advisory);
3. dependency delta;
4. complexity & public-API delta;
5. artifact-size & basic performance delta;
6. differential testing (for refactors/replacements);
7. mutation adequacy for **sensitive modules only** (cost-bounded);
8. independent-review requirement for AI-generated patches;
9. **SHA-bound, signed structured evidence manifest** (with validator identity/version);
10. **fail-closed** treatment of missing mandatory evidence.

Items 9–10 are the load-bearing governance pieces; 1–8 are the initial evidence producers. Property
/fuzz/metamorphic and full SAST are added per risk tier after the bounded version is calibrated in
shadow.

## 13. New risks (to fold into `RISK_REGISTER.md` at implementation time)

| Risk | Priority | Category |
|---|---|---|
| Non-compensatory gates collapsed into a single score / TAP coverage float | **P0** | implementation prerequisite |
| AI-authored tests self-confirm (no mutation adequacy) | **P0** | implementation prerequisite |
| Validator trust: an untrusted/unpinned analyzer admitted as evidence | **P0** | implementation prerequisite (needs validator-id/version binding, R18) |
| Reachability/dead-code false positives auto-DENYing valid code | P1 | implementation prerequisite (advisory-only) |
| Differential testing misapplied to greenfield (no oracle) | P1 | implementation prerequisite |
| Mutation/fuzz cost & flake making governance unusable | P1 | pilot prerequisite (risk-scope + §16.7 flake handling) |
| Bloat budgets miscalibrated (block legitimate change or miss real bloat) | P1 | pilot prerequisite (shadow calibration §16.10) |

## 14. Positioning & claim discipline

**Do not claim:** "UGC finds every hidden bug."

**Use:** *UGC ensures that AI-generated changes cannot merge merely because they compile or receive an
AI approval. It requires risk-appropriate, independently produced evidence for correctness, security,
efficiency, and architectural fitness before authorizing the exact change.* (Consistent with the
claim discipline in design §15.1: evidence-supported · policy-compliant · approved under declared
controls · bound to the exact reviewed artifact · reconstructable · operationally cleared.)

## 15. Verdict

**Architecturally sound and consistent with the readiness audit.** Code Change Intelligence is the
right way to capture many hidden bugs and hidden bloat: **orchestrate specialized, independent evidence
producers and make their risk-dependent outputs mandatory, non-compensatory inputs to the existing
TAP → Decision Authority → ActionGate → ACP chain.**

- **No frozen-contract change and no new `ProviderKind`** — validators are product evidence producers
  feeding `AssertionGovernanceRequest.evidence_refs`.
- **Two prerequisites it shares with the audit are hard requirements**: a signed claim manifest and
  validator-identity/version binding on evidence (R18); plus fail-closed, non-compensatory gating.
- **It is net-new product work** (all validators MISSING today) and belongs in a
  `products/code-governance/change_intelligence/` subsystem, upstream of evidence mapping, delivered
  shadow → recommendation → enforced like the rest of MVP.

This does not change the overall audit verdict: **CODE GOVERNANCE READY WITH PREREQUISITES.** Change
Intelligence is a high-value evidence layer to build on top of the readiness prerequisites, not a
reason to alter the authority or contract architecture.
