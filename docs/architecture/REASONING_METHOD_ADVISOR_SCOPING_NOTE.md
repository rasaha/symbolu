# Reasoning Method Advisor — Scoping Note

**Status:** scoping note; **owner decisions 2 and 4 recorded AMENDED
2026-09-02** (§8; decisions 1, 3 and 5 remain `[R]`). **Documentation only.**
This note connects no runtimes, adds no contract, changes no enum, and
implements no package. Every contract named below is a **candidate**, specified for
ratification, not created.
**Scope:** a proposed new design-time capability, its lifecycle, its output
contract, its evaluation, and the runtime boundary it depends on.
**Relationship:** builds on
[`WORKFLOW_FIT_READINESS_SCOPING_NOTE.md`](WORKFLOW_FIT_READINESS_SCOPING_NOTE.md)
and [`REASONING_WORKFLOW_LANDSCAPE_EVALUATION.md`](REASONING_WORKFLOW_LANDSCAPE_EVALUATION.md);
links to the merged
[`READINESS_ADVISORY_COMPOSITE_DESIGN_NOTE.md`](READINESS_ADVISORY_COMPOSITE_DESIGN_NOTE.md)
without editing or reopening it.
**Evidence labels:** `[V]` verified at the cited `file:line` · `[I]` inferred ·
`[R]` requires owner ratification · `[G]` gap.

## The load-bearing question

**Can a developer be told, before deployment, which reasoning method their agent
should try — and can that advice later be shown to have been right?** Yes to
both, but not from where the idea was first placed, and not before two things
exist: a neutral record that carries reasoning-method evidence across a runtime
boundary that is currently disjoint, and a consuming evaluation engine to read
it. The advisor's first version is therefore rule-derived or unknown, and says
so.

## 1. Terminology — *method*, not *workflow*

New catalog and contract names use **reasoning method**, not *workflow*. Two
collisions force this `[V]`:

- The Agent Workforce Composer already uses "workflow" for `workflow_ir.v2`, the
  compiled *planning* workflow from the policy-workflow compiler
  (`agent-workforce-composer …/cli.py:107`; `…/compatibility.py:3` — "routes a
  serialized compiled workflow"; the policy-workflow compiler is an optional
  reference dependency, `…/pyproject.toml:60`). A second meaning inside a
  neighbouring contract would be a semantic and contract collision.
- The seven-member `WorkflowType` enum names *processing*, which S2-B ruled out
  of the Proposer's declared vocabulary
  (`ADR_UGENCE_S2B_ROUND2_VOCABULARY_RATIFICATION.md:58,64-68`).

Candidate names, **not created here** `[R]`:

| Candidate | Role |
|---|---|
| `ReasoningMethodCatalog` | the governed, versioned repertoire of methods an advisor may name |
| `ReasoningMethodRef` | an exact method id + version reference |
| `ReasoningMethodExecutionRecord` | *conceptual, future* — the neutral evidence record of §3 |
| `ReasoningMethodFitAssessment` | the fit judgement of §4, superseding "Workflow-Fit" as the contract name |

The catalog must cover the **repertoire, not the enum**: the landscape
evaluation established that `iterate_loop.py`, `multi_agent.py`,
`human_policy.py` and retrieval infrastructure implement methods outside
`WorkflowType` `[V]`. Method names in the catalog **never become S2-B strategy
tokens**; the three ratified shapes are unchanged.

## 2. Capability home — Reasoning Method Advisor, new

**Recommended:** a new design-time capability, **Reasoning Method Advisor**.

**Not Agentic Proposer** `[V]`. The Proposer "proposes. It decides nothing"
(`agentic-proposer/README.md:5`) and "performs no agent eligibility, ranking,
team composition or permission-bound proposal: the Agent Workforce Composer owns
those" (`:12-13`). It is a runtime, per-case advisory: `ProposerAdvisory` carries
`parent_advisory_digest`, `case_ref`, `agent_id`, `role_contract_id`
(`agentic-proposer …/contracts.py:980-983`). A developer consultation before
deployment is a different object with a different lifecycle, and it names
methods — which the Proposer may not.

**Not Agent Workforce Composer, in the first version — by authority and
lifecycle, not by naming.** AWC's ratified authority is over *agents*: it
answers "how are eligible agents ranked, least-privilege permission bound is
proposed, and what ordered fallbacks apply" over P1-eligible sets
(`agent-workforce-composer/README.md:18` names its contracts `awc.v1`
*preserved* and `awc.composition.v1` *additive*, over a *frozen* registry) `[V]`.
This capability's subject is a *method*, its lifecycle is a design-time
recommend → pilot → assess loop with no analogue in AWC, and its evidence is a
fit assessment AWC does not produce. Making AWC's candidate sets carry methods
would change ratified, preserved contracts — a cost the naming collision (§1)
merely adds to.

*Considered alternative, recorded not selected* `[R]`: extend AWC, reusing its
ranking, candidate-set and fallback machinery and avoiding a new integration
boundary. That reuse assumes the machinery is type-agnostic; the preserved
contract versions say it is not. If the owner reopens placement, the
justification to defeat is the authority-and-lifecycle one above, not the
naming one. AWC may later **consume** the advisor's qualifying set when
composing a team; it should not own the method analysis.

## 3. The runtime boundary — currently disjoint

Established `[V]`:

- `packages/capabilities/agentic-proposer` and its integration packages have
  **no import of, and no dependency on**, `WorkflowType`, `reasoning_workflows`,
  `agentic_framework` or `WorkflowResult`: under `src/` there are zero
  references. The only mentions anywhere in those packages — `pyproject.toml`,
  `tests/test_boundaries.py`, `tests/test_vocabulary.py`,
  `verify_agentic_proposer_distribution.py` and `docs/S0_SCOPE.md` — are
  **prohibitions** that forbid the dependency (a forbidden-wheel-substring list
  and boundary tests). The disjointness is enforced, not incidental.
- **No package** in `packages/` consumes `WorkflowResult` or `workflow_type`.
- `agentic/` has **no `pyproject.toml`** and is imported by **zero** packages. It
  is a monorepo tree, not a distribution.

So today no reasoning-method identity, telemetry or artifact can reach the
governed side at all. **This note does not propose a direct import between
`agentic/` and governed packages, and does not pass `WorkflowResult` across the
boundary.** `WorkflowResult` is an implementation class of an experimental
runtime; binding governed contracts to it would couple the governed side to
that runtime's internals.

**Specified instead:** a **neutral, versioned future evidence record** —
candidate name `ReasoningMethodExecutionRecord` `[R]` — that could carry:

| Field group | Content |
|---|---|
| Method | `ReasoningMethodRef` — method id and version |
| Binding | invocation id; subject id; the `AssessedSystemBinding` under test |
| Task | task-class reference; configuration reference |
| Digests | input digest; configuration digest |
| References | model reference (Model Authority); policy references |
| Artifacts | structured artifact references — candidates, parent-bound revisions, decisions; **never private reasoning traces** |
| Telemetry | calls, tokens where available, duration — each with its **measurement source** (`TokenCountBasis`-style provenance) |
| Status | evidence status and authority status on the existing axes |

The experimental reasoning runtime **may eventually implement an adapter** that
emits this record. The governed side consumes the record **without depending on
any `agentic/` implementation class**. The record's evidence axes already exist:
`SourceBasis`, `AttestationStatus`, `VerificationStatus` on `MetricClaim`
(`governance-contracts …/evidence.py:363,372,379`) `[V]`, and
`TokenCountBasis` / `ApiCallTokenRecord` for telemetry provenance
(`context-minimization …/token_accounting.py:135,433`) `[V]`.

**Until a trusted capture boundary exists, method identity and telemetry remain
runtime-reported, never independently verified.** A record emitted by the same
process that ran the method is `OBSERVED` / `UNATTESTED` / `UNVERIFIED`, exactly
as the workflow-fit note states for telemetry.

**This record is a direction, not a contract.** It is intentionally **not
implementable without a separate ratification round**. Undecided, and left so
here: record **identity** and digest rule; **canonicalization**; **issuer
authority** — who may emit it and with what key; **lifecycle** — supersession
and revocation; **version compatibility** across record versions; and
**evidence-promotion rules** — what moves a record's status beyond
`OBSERVED`/`UNATTESTED`/`UNVERIFIED`. The field table specifies what the record
must be able to say, not its schema `[R]`. Of the field groups, **telemetry is
the likeliest to be wrong**: tokens may be unavailable, latency is
infrastructure-confounded, and the trustworthiness of runtime-produced counts is
the open decision of the workflow-fit note.

## 4. Lifecycle

```
developer task profile
        │
        ▼
Reasoning Method Advisor ──► qualifying set  (§5; may contain no primary)
        │
        ▼
owner chooses pilot configuration
        │
        ▼
AssessedSystemBinding identifies the configuration under test
        │
        ▼
reasoning-method pilot executions  (baseline + recommended + challenger, §6)
        │   emit ReasoningMethodExecutionRecord (future, §3)
        ▼
consuming evaluation engine  (unassigned — composite-note ballot 1)
        │
        ▼
Reasoning Method Fit Assessment
        │
        ├── SUFFICIENT_PARETO_EFFICIENT ──► eligible for owner approval and a
        │                                   future production-binding decision
        │
        ├── INSUFFICIENT_QUALITY or
        │   SUFFICIENT_RESOURCE_DOMINATED ─► return to advisor / profile /
        │                                   configuration for revision
        │
        └── COMPARISON_EVIDENCE_ABSENT ───► no approval; nothing is bound
```

**This corrects the earlier flow** in three places `[V]`:

1. **The feedback edge exists.** The prior diagram was linear; a failed
   assessment had nowhere to go.
2. **`AssessedSystemBinding` identifies the configuration under test, before
   the pilot.** It carries `configuration_id` and `configuration_digest`
   (`governance-contracts …/system_identity.py:283-284`). Binding here means
   *identifying what is being assessed*, not approving it; readiness assesses a
   bound configuration by design.
3. **Agent Constitution does not appear as binding workflow permission.** The
   pilot role document binds `permitted_tool_scopes`,
   `permitted_candidate_dispositions`, `permitted_review_actions` and
   `strategy_policy_ref`
   (`agent-constitution-activation/pilot/invoice-reconciler-role.v1.json`) `[V]`
   — **role permissions and a strategy-policy reference, not reasoning methods
   and not assessed configurations**. It binds no `configuration_digest` or
   `system_manifest` (0 hits) `[V]`. Whether a future constitution version binds
   a reasoning-method policy is a **separate owner decision, taken only after
   pilot evidence exists** `[R]`.

The evidence-absent branch uses `COMPARISON_EVIDENCE_ABSENT`, not
`NOT_ASSESSABLE`: the latter is a `ReadinessClassification` tier
(`agent-value-readiness …/contracts/enums.py:43`) `[V]`.

**Three conditions make "identifying, not approving" defensible** `[R]`:

1. **Pilot-only status must be explicit.** `AssessedSystemBinding` carries no
   state field; it carries `deployment_environment_ref`, `effective_from` and
   `effective_to` (`governance-contracts …/system_identity.py:288-290`) `[V]`.
   A pilot binding can be distinguished today by its `deployment_environment_ref`
   naming a pilot environment; a dedicated `UNDER_ASSESSMENT` state is the
   alternative if that is judged too implicit. Either way, a binding **grants
   nothing**: `authorizes_deployment` is a property returning `False` on both
   readiness traces (`evaluation/trace.py:191`, `orchestration/trace.py:723`)
   `[V]`.
2. **Approval is a separate, authority-produced artifact.** A
   `SUFFICIENT_PARETO_EFFICIENT` assessment makes a configuration *eligible* for
   approval; it is not the approval. That artifact comes from an accountable
   authority — Decision Authority for the business decision — never from the
   assessment or the advisor.
3. **Revision has lineage.** A failed configuration that is changed receives a
   **new** `configuration_digest` and a **new** binding, linked to its failed
   predecessor. The generic feedback arrow above is insufficient on its own;
   the precedent for parent linkage is `ProposerAdvisory.parent_advisory_digest`
   (`agentic-proposer …/contracts.py:980`) `[V]`.

## 5. Advisor output

The advisor returns a **set of qualifying methods** and **may return no primary
selection**. This requires an **advisor-specific no-forced-winner rule**, to be
ratified as its own ruling `[R]`. OD-8 — "more than one qualifying candidate
produces no selection" (`ADR_UGENCE_S2B_ROUND2_VOCABULARY_RATIFICATION.md:54`)
`[V]` — is cited as **precedent only**: it governs runtime candidate selection
in the Proposer, and its authority does not extend to design-time method advice.
Claiming that it did would be a category error. *(An earlier version of this
note made that claim.)*

**Every claim is labelled**, with one of three labels `[R]`:

| Label | Meaning |
|---|---|
| `RULE_DERIVED` | follows from declared task-profile characteristics and policy |
| `BENCHMARK_DERIVED` | supported by an admitted comparison on the applicable task class |
| `COMPARISON_EVIDENCE_ABSENT` | no admitted evidence; the advisor does not know |

Two prohibitions:

- **No numeric outcome prediction may appear without an admitted benchmark
  source.** A range such as "92–95%" on a rule-derived claim is a fabricated
  prediction.
- **No scalar resource label** — "medium", "high" — **may appear without a
  governed method.** Resource comparison is Pareto over a governed vector
  (`WORKFLOW_FIT_READINESS_SCOPING_NOTE.md:73`) `[V]`; a label is an unratified
  ordering.

**The initial version is rule-derived or unknown, and must say so.** The
consuming evaluation layer is unassigned and no admitted comparison evidence
exists. A rule-derived advisor recommends from declared task characteristics; it
does not predict proven outcomes, and its output must carry that statement.

What a rule-derived v0 can reuse `[V]`: `WorkflowSelector`'s signal→method
table (`reasoning_workflows.py:1178-1187`, default `:1228`). What it cannot:
`ComplexityDetector.analyze(self, text: str)` (`adaptive_prompts.py:359`) reads
runtime query text, not a design-time profile. A profile-to-signal mapping is
new `[G]`.

**Developer task profile.** The landscape evaluation mapped thirteen selection
parameters to existing contracts. The advisor's profile begins **minimal and
typed** `[R]`; privacy and regulatory requirements are represented through
**policy references**, never unconstrained prose alone — privacy has no contract
anywhere in the readiness, governance or policy packages (0 hits) `[V]`, and
`MetricClaim.policy_refs` is the existing pattern for reference-not-inline. The
profile is `REPORTED` — a developer's assertion — until policy and evidence
systems resolve what can be independently established. Permitted models are not
a profile field: Model Authority "determines which model, if any"
(`model-selection/README.md:5`) `[V]`.

## 6. Evaluating the advisor

**Not top-one hit rate.** Several methods may legitimately qualify, so "did the
first recommendation win?" penalises correct set-valued answers. Candidate
measures `[R]`:

| Measure | Question | Reads from |
|---|---|---|
| Qualifying-set success | did the set contain a method later found `SUFFICIENT_PARETO_EFFICIENT`? | fit assessment |
| Observed false exclusion | did an excluded, **tested** method prove sufficient and undominated? | fit assessment on challengers |
| Dominated-recommendation rate | how often was a recommended method `SUFFICIENT_RESOURCE_DOMINATED`? | fit assessment |
| Unsupported-selection rate | did the advisor name a primary without `BENCHMARK_DERIVED` support? | advisory labels |
| Appropriate abstention rate | when evidence was absent, did it say `COMPARISON_EVIDENCE_ABSENT`? | advisory labels vs. evidence state |
| **Set precision** | of the qualifying set, what fraction proved sufficient and undominated? | fit assessment |
| **Recommendation-set size** | how many methods did the advisor qualify, against the catalog size? | advisory |
| **Coverage** | what fraction of the catalog has been tested for this task class at all? | pilot record |
| **Error severity** | when wrong, was the miss a marginal domination or a threshold failure on a consequential task? | fit assessment + task profile |

**The five measures alone are gameable.** Qualifying-set success is inflated by
recommending nearly every admissible method; set precision and
recommendation-set size exist to catch that. **One challenger measures almost
nothing**: it is a floor, not an evidence base for false exclusion.

**False exclusion is measurable only against methods actually tested.** For the
pilot, run:

- the **governed baseline** for the task class;
- **every recommended** method;
- **non-recommended challengers under a governed sampling policy** —
  preregistered, risk-based or randomized, with adequate catalog coverage
  declared in advance `[R]`. "At least one" is the minimum the owner set; it
  is not sufficient for any claim about exclusion.

**This does not measure exclusion across the entire catalog.** Untested methods
remain unknown, and the note claims nothing about them. Challengers increase
pilot scope in proportion to the sampling policy; that cost is a design
decision, recorded here rather than absorbed silently.

## 7. Recommended ordering

1. Ratify placement (§2) and terminology (§1).
2. Define the reasoning-method repertoire as `ReasoningMethodCatalog` — covering
   the repertoire, not the enum.
3. Define the developer task profile (§5).
4. Define the neutral execution-record boundary (§3).
5. Assign the consuming evaluation engine and the trusted telemetry boundary
   (composite-note ballot 1; workflow-fit-note decision 4).
6. Run Reasoning-Method-Fit pilots (§4, §6).
7. Introduce `BENCHMARK_DERIVED` advisor recommendations.
8. **Only afterward** consider production policy or Constitution binding.

Step 4 precedes step 6 absolutely: without the record, nothing crosses the
boundary and no pilot can be assessed.

## 8. Owner decisions `[R]`

1. **Placement, terminology and the advisor's own rules** — Reasoning Method
   Advisor as a new capability, justified by authority and lifecycle (§2), with
   the AWC-extension alternative recorded; *method* not *workflow*; the four
   candidate contract names; and the **advisor-specific no-forced-winner rule**
   ratified on its own, citing OD-8 as precedent only (§5).
2. **Execution-record boundary, and the record's governance** — ~~`[R]`~~
   **AMENDED 2026-09-02.** *As proposed:* the neutral record's field set and
   version; the adapter obligation with no direct import; the undecided
   identity, canonicalization, issuer, lifecycle, compatibility and promotion
   rules (§3); and access, retention and disclosure rules for prompts,
   structured artifacts and telemetry held in the record — none of which any
   package defines today `[G]`. *Owner ruling:* the **neutral, versioned
   execution-record boundary and the adapter-without-direct-import
   architecture are ratified**. The current field table (§3) is **not an
   implementation-ready contract**. Identity, schema version, issuer/capture
   authority, canonicalization, lifecycle, compatibility, promotion,
   supersession, access, retention and disclosure **require a later contract
   ruling with no defaults**.
3. **Pilot composition and the sampling policy** — governed baseline, every
   recommended method, and challengers under a preregistered, risk-based or
   randomized policy with declared coverage; plus the anti-gaming measures of
   §6.
4. **Task profile and task-class identity** — ~~`[R]`~~ **AMENDED 2026-09-02.**
   *As proposed:* the minimal typed profile with privacy and regulation as
   policy references; and what defines a task class, and when two tasks are
   comparable enough to share benchmark evidence — no task-class contract
   exists `[G]`. *Owner ruling:* a **typed, versioned task profile and
   task-class identity are ratified**. Task-class identity binds **domain,
   intended outcome, consequence, reversibility, evidence/tool requirements,
   structural characteristics, applicable population or distribution,
   benchmark set, threshold and sufficiency-rule version**. Evidence may be
   shared **only when those governed coordinates are compatible**; otherwise
   comparison evidence is absent (`COMPARISON_EVIDENCE_ABSENT`). The contract
   carrying this identity is not created by this ruling.
5. **Binding lifecycle, reassessment and post-pilot approval** — pilot-only
   status via `deployment_environment_ref` or a new state; the separate
   authority-produced approval artifact; revision lineage by new digest (§4);
   **reassessment triggers** — since a binding is to an exact
   `configuration_digest` (`system_identity.py:284`) `[V]`, any change to
   model, prompt, tools, policy, data distribution or method version is a new
   configuration and invalidates the prior assessment, and whether any narrower
   rule is ever ratified is this decision; and any future Constitution
   method-policy binding.

Constants, thresholds, sampling rates, label semantics beyond the three names,
catalog members and profile fields remain unratified with no defaults.

**Recommendation:** ratify §1, §2, §4 and §5 as architecture. Ratify nothing
numeric. Create no contract, connect no runtime, and change no enum until
decision 2 is taken — it gates every later step.

**Ratification record (2026-09-02).** Decision 2 AMENDED; decision 4 AMENDED —
each as recorded above. Decisions 1, 3 and 5 remain `[R]`. Decision 2's ruling
ratifies the boundary and adapter architecture only; the contract round it
gates has not been taken.

**Authority.** Owner ratification by Rakesh Mohan, 2026-09-02, issued as an explicit owner instruction in Claude Code session `session_01VXERHvJzbb9cjZ1GyFFQLn` after advisory analysis in ChatGPT/Codex and Claude sessions of the same date. The model analysis was advisory only; the owner instruction was the ratifying act. Nothing numeric was ratified, and no code, contract, enum, experiment or test changed with this record.
