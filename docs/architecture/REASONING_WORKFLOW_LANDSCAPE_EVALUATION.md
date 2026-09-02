# Reasoning Workflow Landscape — Repository Evaluation

**Status:** evaluation record for owner review. No implementation, no enum
change, no contract change, no protocol change.
**Source:** two externally supplied posts proposing additional reasoning
workflows, workflow-selection parameters, an eligibility predicate, a choice
rule and a three-layer selection architecture. Every claim in them was captured
as a discrete item and evaluated against this repository.
**Relationship:** companion to
[`WORKFLOW_FIT_READINESS_SCOPING_NOTE.md`](WORKFLOW_FIT_READINESS_SCOPING_NOTE.md);
§2 below corrects that note's §6 — its "seven workflows" statement at `:289`.
**Evidence labels:** `[V]` verified at the cited `file:line` · `[I]` inferred or
external, not repo-verifiable · `[R]` requires owner ratification · `[G]` gap.

## The load-bearing question

**Does this repository need new reasoning workflows, or does it already
implement most of what was proposed under other names?** Mostly the latter. The
seven-member `WorkflowType` enum is not the framework's actual repertoire:
ReAct, specialist collaboration, human-in-the-loop and retrieval all exist
outside it. What is genuinely missing is narrower than the proposal assumes, and
the selection architecture's third layer — benchmark-driven choice — does not
exist at all.

## 1. Method

Three passes. The working inventory, verdict file and sweep script are **not
committed**; the counts below are from that run and the sweep's patterns are
declared inline wherever a count is stated:

1. **Capture.** 92 discrete items with stable ids — 4 numeric claims, 15
   additional workflows, 4 research references, 7 reductions, 1 landscape
   summary, 10 recommended workflows, 1 differentiation claim, 3 domain claims,
   13 selection parameters, 13 mapping rows, 5 eligibility conjuncts, 1 choice
   rule, 5 variables, 1 no-evidence rule, 4 cloud-scaling scenarios, 3 layers,
   2 closing claims.
2. **Evaluate.** One labelled repository check per item; every item assigned a verdict
   with evidence.
3. **Re-evaluate.** Inventory↔verdict coverage 92/92 both ways; all 41 source
   table rows and 14 key prose phrases confirmed present in the capture; the
   the sweep re-run once. **The working inventory, verdicts and sweep script are
   not committed, so that re-run is not independently reproducible from this
   PR**; every count stated in this document declares its pattern and scope
   inline so that it is.

## 2. The enum is not the repertoire

`WorkflowType` has exactly seven members `[V]`
(`agentic/agentic_framework/reasoning_workflows.py:78-86`). But the framework
implements, outside that enum:

| Proposed workflow | Exists as | Evidence |
|---|---|---|
| **ReAct** | `iterate_loop.py` — "Iterate-Until-Done"; the base wrapper "does not feed tool results back into the model to decide the next step", and this module "feeds the observations back into the next instruction" | `[V]` `agentic/agentic_framework/iterate_loop.py:8,19` |
| **Specialist collaboration** | `multi_agent.py` — "several governed agents can collaborate on one query" | `[V]` `agentic/agentic_framework/multi_agent.py:7-8` |
| **Human-in-the-loop** | `human_policy.py` — human-curated deterministic verdicts over ActionGate `ALLOW / DENY / DEFER` | `[V]` `agentic/agentic_framework/human_policy.py:2,6` |
| **Retrieval (RAG)** | infrastructure — 37 `.py` files under `agentic/`, `packages/`, `symbolu/` matching `retrieval.augmented\|\brag_\|_rag\b\|RAGEngine` case-insensitively — and `.github/workflows/core-rag-ci.yml` | `[V]` |
| Gated tool access | `mcp_gateway.py` — "THIS IS GATED MCP ACCESS" | `[V]` `agentic/agentic_framework/mcp_gateway.py:12` |
| Portfolio orchestration | `multi_workflow_orchestration.py` (H22) | `[V]` `agentic/agentic_framework/multi_workflow_orchestration.py:2` |

**Consequence:** any statement that "the seven workflows" bound the treatment
space — including §6 of the workflow-fit note (`:289`) — refers to the enum only. The
treatment space a benchmark must cover is larger, and none of these modules
carries a `WorkflowType` value, so they are currently invisible to
`WorkflowSelector` and to any workflow-fit provenance record `[G]`.

## 3. The fifteen additional workflows

| # | Workflow | Repository status | Evidence |
|---|---|---|---|
| W01 | Retrieval-Augmented Reasoning | **exists as infrastructure**, not a workflow | 37 files by the §2 pattern; `core-rag-ci.yml` `[V]` |
| W02 | ReAct | **exists under another name** | `iterate_loop.py:8,19` `[V]` |
| W03 | Plan-and-Execute | partial — Linear Chain at `DEEP`/`RECURSIVE` depth is decompose→analyze→synthesize; H22 portfolio orchestration | `adaptive_prompts.py:75-85`; `multi_workflow_orchestration.py:2` `[V]` |
| W04 | Least-to-Most | **absent** — `MapReduce` is parallel; no sequential-dependency form | 0 files under `agentic/`, `packages/` matching `least_to_most\|LeastToMost\|least-to-most`; one unrelated prose "least to most" exists under `packages/capabilities/storygraph` `[V]` |
| W05 | Self-Consistency | **absent as a reasoning workflow** — 9 files under `agentic/`, `packages/` match `self[-_ ]consistency` case-insensitively; eight concern internal consistency of definitions, and `agentic/reflective_phase_quad.py:202` lists "Self-consistency (multiple samples, agreement = quality)" as a *training source* for a quality-scoring model, not an implementation of the method | `[V]` |
| W06 | Graph of Thoughts | **absent** | 0 files matching `graph_of_thought\|GraphOfThought` `[V]` |
| W07 | Program-of-Thought / Code-Assisted | **absent** | 0 files matching `program_of_thought\|ProgramOfThought\|code_interpreter\|CodeAssisted` `[V]` |
| W08 | Generator–Verifier | partial — `IterativeRefinementWorkflow` has an in-pipeline CRITIC, same model | `reasoning_workflows.py:558-624` `[V]` |
| W09 | Hypothesis–Test | **absent** | 0 files matching `HypothesisTest\|hypothesis_test`; unrelated prose "hypothesis tests" occurrences exist `[V]` |
| W10 | Causal / Counterfactual | partial — evidence hooks exist (`MetricClaim.counterfactual_ref`, `.causal_method_ref`); `CAUSAL_REASONING` signal routes to `LINEAR_CHAIN` | `evidence.py:377-378`; `reasoning_workflows.py:1178-1187` `[V]` |
| W11 | Scenario Planning | **absent** as workflow; `forecast_horizon` and `AssessmentStage.FORECAST` exist, forecast engine deferred | `evidence.py:369`; `governed-value …/enums.py:91` `[V]` |
| W12 | Constraint / Optimization | **absent** as reasoning; constraint exists as *policy* | `packages/integration/cloud-scaling-capacity-bounds-policy` `[V]` |
| W13 | Case-Based Reasoning | **absent** | 0 files matching `CaseBased\|case_based` `[V]` |
| W14 | Specialist Collaboration | **exists under another name** | `multi_agent.py:7-8`; `packages/capabilities/agent-workforce-composer` `[V]` |
| W15 | Human-in-the-Loop Deliberation | **exists** | `human_policy.py:2,6`; `HUMAN_FALLBACK_READINESS`, `ESCALATION_READINESS` `enums.py:125-135`; `cost.py:39` `[V]` |

**Tally:** 3 exist, 1 as infrastructure, 3 partial, 8 absent.

**On W08 specifically.** The proposal's reduction — "Generator–Verifier resembles
Iterative Refinement with separate roles" — is right, and the separation is the
whole point. A same-model critic is the `SELF_CRITIQUE` that S2-B Round 2
rejected as private model behaviour `[V]`
(`ADR_UGENCE_S2B_ROUND2_VOCABULARY_RATIFICATION.md:64-68`). A verifier in a
separate trust domain is what UVI ADR §23.10 permits — "Reference producers
never self-attest/self-verify/self-approve"
(`ADR_UGENCE_VALUE_INTELLIGENCE_GV2C_GV2E_GV3R.md:322`; ratified as a structural
rule by `ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md:1286`). The two are not variants of one workflow; they sit on opposite sides of
a ratified line.

## 4. The recommended ten

| Recommended | Status |
|---|---|
| Linear Chain, Tree of Thought, Iterative Refinement, Debate | in `WorkflowType` `[V]` |
| Metacognitive routing | in `WorkflowType` + `WorkflowSelector` `[V]` |
| Retrieval-Augmented Reasoning | infrastructure `[V]` |
| ReAct / tool-assisted | `iterate_loop.py` `[V]` |
| Generator–Verifier | partial (same-model only) `[V]` |
| Causal / Counterfactual | partial (evidence refs, no workflow) `[V]` |
| Program / SQL-assisted | **absent** `[V]` |

Of ten, one is genuinely absent.

## 5. The thirteen selection parameters

| # | Parameter | Existing contract | Status |
|---|---|---|---|
| SP01 | Business context | `GeographyPolicy`, `DomainPolicy`, `IntendedOutcomePolicy` (`policies.py:131,177,212`); `DomainKind.REGULATED` (`governed-value …/enums.py:55`) | exists `[V]` |
| SP02 | Task structure | `ComplexitySignal.MULTI_PART_QUESTION` (`adaptive_prompts.py:88+`) | **partial** — no parallel-vs-sequential signal `[V]` |
| SP03 | Ambiguity | `AMBIGUITY_DETECTED → TREE_OF_THOUGHT` (`reasoning_workflows.py:1178-1187`) | exists `[V]` |
| SP04 | Evidence requirement | `MetricClaim` evidence axes; `packages/trusted-evidence-authority` | exists `[V]` |
| SP05 | Tool requirement | `TOOL_READINESS`, `INTEGRATION_READINESS` (`enums.py:125-135`); `mcp_gateway.py:12`; `trust/hallucinated_capability.py:2,5` | exists `[V]` |
| SP06 | Quantitative intensity | — | **absent** — no signal `[V]` |
| SP07 | Conflict | `CONDITIONAL_LOGIC → DEBATE` (`reasoning_workflows.py:1178-1187`) | **partial** — a proxy; no conflict/contradiction signal `[V]` |
| SP08 | Consequence | `DomainKind.REGULATED` loss-dominates; expected loss unbounded (`expected_loss.py:1`); `packages/risk_authority` | exists `[V]` |
| SP09 | Reversibility | `external_actions.Reversibility` — **four states**: `REVERSIBLE`, `IRREVERSIBLE`, `COMPENSATABLE`, `UNKNOWN` (`external_actions.py:155-159`); field at `:328` | exists **on actions**, not on tasks `[V]` |
| SP10 | Uncertainty | `UNCERTAINTY_RECOGNITION`, `CONFIDENCE_CALIBRATION` (`enums.py:108-118`); abstention as a recognised routing outcome — an evaluation-harness consistency check between an `expected_abstention` fixture flag and `REFUSE` routing (`hybrid_handover/evaluation/integrity.py:107`); evidence of the concept, not a routing implementation | exists `[V]` |
| SP11 | Explanation requirement | `AUDITABILITY`, `OBSERVABILITY` (`enums.py:125-135`) | exists `[V]` |
| SP12 | Resource budget | `INV-WF-2` `max_llm_calls` (`reasoning_workflows.py:36`); tokens via CM contracts, not wired; no time budget | **partial** `[V]` |
| SP13 | Historical performance | `packages/benchmark-registry` — BR-1, "Contracts only; no registry" (`README.md:9`); consuming evaluation engine unassigned | **partial** `[V]` |

**Tally:** 8 exist, 4 partial, 1 absent.

**On SP09.** The proposal frames reversibility as binary — "can a wrong action be
easily undone?" The repository already carries a third state, `COMPENSATABLE`,
and attaches reversibility to *external actions* at their governed execution
boundary, not to tasks at selection time. Using it for workflow selection would
mean reading a property of a downstream action before the action exists `[R]`.

## 6. The eligibility predicate, conjunct by conjunct

`Eligible(w,t) = PolicyAllowed ∧ ToolsAvailable ∧ EvidenceCompatible ∧ ArtifactShapeAllowed ∧ BudgetCompatible`

| Conjunct | Maps to | Status |
|---|---|---|
| `PolicyAllowed` | Policy Authority; `agentic-proposer-strategy-permission-policy` | exists `[V]` |
| `ToolsAvailable` | `trust/hallucinated_capability.py` — "pure set-membership + alias resolution" (`:5`), PROVISIONAL, advisory-only (`:2`); `mcp_gateway.py` | **partial** `[V]` |
| `EvidenceCompatible` | Trusted Evidence Authority (E-1/E-2) | exists `[V]` |
| `ArtifactShapeAllowed` | **S2-B's three ratified members, exactly** (`ADR_UGENCE_S2B_ROUND2_VOCABULARY_RATIFICATION.md:49-51`) | exists, 1:1 `[V]` |
| `BudgetCompatible` | `INV-WF-2` (`reasoning_workflows.py:36`) | exists, calls only `[V]` |

`ArtifactShapeAllowed` is the cleanest mapping in the proposal: it names a
ratified vocabulary without renaming it.

## 7. The choice rule and the no-evidence rule

**Choice rule:** *"w\* = least-resource admissible workflow expected to satisfy
Q(w,t) ≥ τ_t."*

Two problems `[V]`:

- **"Least-resource" presumes a scalar ordering over resources.** The
  workflow-fit note deliberately declined one: over-reasoning is defined by
  Pareto domination over a governed resource vector, "no weights, no scalar cost
  function, no invented constants" (`WORKFLOW_FIT_READINESS_SCOPING_NOTE.md:73`).
  With calls and tokens as separate resources there is often no single
  least-resource workflow. The wording conflicts with the ratified stance; the
  intent — cheapest sufficient — is the same.
- **"Expected to satisfy" requires benchmark evidence per task class**, which is
  layer 3 (§9) and does not exist.

The variables fare unevenly: `τ_t` is an existing `GovernedThreshold`
(`thresholds.py:31,41-45`) `[V]`; policies are the Policy Authority `[V]`; `Q(w,t)`
depends on the unassigned consuming evaluation engine `[G]`; benchmarks are
definitions only `[V]`; and **no task-class contract exists** at all `[G]`.

**No-evidence rule:** *"return NOT_ASSESSABLE or escalate — not let an LLM guess."*
`NOT_ASSESSABLE` is a `ReadinessClassification` tier `[V]` (`enums.py:43`) and
must not be borrowed; the workflow-fit note already names
`COMPARISON_EVIDENCE_ABSENT` for this state
(`WORKFLOW_FIT_READINESS_SCOPING_NOTE.md:84`). "Escalate" maps to
`ESCALATION_READINESS` and ActionGate `DEFER`. "Not an LLM guess" is already
true of the existing selector (§10).

## 8. The cloud-scaling scenarios

| Scenario | Proposed choice | Repository state |
|---|---|---|
| Routine, reversible sandbox change | Linear Chain | `Reversibility.REVERSIBLE` exists; `LINEAR_CHAIN` is the selector default (`reasoning_workflows.py:1228`) `[V]` |
| Ambiguous: models disagree, cost ceiling close, change freeze, several replica counts | Tree of Thought | `replica` (case-sensitive) in 83 files under `packages/capabilities/cloud-scaling-controller` `[V]`; **change freeze: 0 hits; cost ceiling: 0 hits** — the scenario's own conditions are unmodelled in the cloud-scaling packages `[G]` |
| Conflicting organizational decision | Debate / specialist collaboration, then governed decision | `DEBATE`; `multi_agent.py`; `packages/capabilities/decision-authority` `[V]` |
| Actual infrastructure action | ReAct for state; ActionGate + control plane authorize | **already implemented**: `external_actions.py:9` — "propose → authorize → execute → observe → commit", each action checked against ActionGate `[V]` |

The fourth row's separation of reasoning from authorization is not a proposal
for this repository; it is its existing design.

## 9. The three layers — current state

| Layer | Proposed | State |
|---|---|---|
| 1. Domain policy establishes constraints | banking / healthcare / cloud define evidence, risk, quality | policies exist (§5 SP01) but are **not wired into `WorkflowSelector`** `[V]` |
| 2. Task characteristics identify suitable workflows | ambiguity, decomposition, tools, uncertainty, consequence | exists, **deterministically** — see §10 `[V]` |
| 3. Benchmark evidence chooses among suitable workflows | historical paired tests | **absent** — the registry defines benchmarks and computes nothing (BR-1, B-12); no paired-run history; no consuming evaluation engine `[G]` |

So the closing claim — "domain conditions the decision, task structure drives
the initial choice, independent performance evidence validates that choice" —
describes one existing layer, one existing-but-unwired layer, and one missing
layer.

## 10. The selector prohibition is already satisfied — and that is also the weakness

The proposal's closing rule: the workflow must not be chosen "merely because an
LLM says 'this looks complex'", or the selector becomes an unverified reasoning
agent.

Today's selector already complies `[V]`. `ComplexityDetector`
(`adaptive_prompts.py:326`) classifies by regular-expression pattern tables —
`_MULTI_PART_PATTERNS`, `_CAUSAL_PATTERNS`, and so on (`:413+`) — with **zero
LLM calls**. `MetacognitiveWorkflow` (`reasoning_workflows.py:1011`) calls that
detector (`:1084`) and then `select_workflow` (`:1108`), a table lookup, also
with zero LLM calls. `WorkflowSelector` (`:1156`) is a fixed
signal→workflow map (`:1178-1187`) defaulting to `LINEAR_CHAIN` (`:1228`).

That is the good news. The rest: it is **keyword regex**, so it satisfies
layer 2 crudely; it reads **no domain policy** (layer 1 unwired); and it
consults **no benchmark evidence** (layer 3 absent). It is deterministic and
unvalidated — the exact condition the workflow-fit note proposes to place under
offline benchmark validation.

A separate concern surfaced in passing: `human_policy.py:2-6` notes that
ActionGate's decision core derives its verdict from *LLM-produced* signals
(quality, coherence, alignment scores). That is about action authorization, not
workflow selection, and is out of scope here — but it is the same class of
question.

## 11. External claims, not repo-verifiable `[I]`

- "No fixed industry-standard number"; "roughly 10–15 other families"; "exceeds
  30 with research variations."
- Research references: ReAct, Least-to-Most Prompting, Graph of Thoughts,
  Reflexion. Reflexion has 0 mentions anywhere in `agentic/`, `packages/` or
  `docs/` `[V]`.
- The banking example (balance query vs ₹50 crore restructure) is illustrative;
  `DomainKind` has `FINANCE_OPS` and `REGULATED` but no banking package.

"Ugence does not need twenty workflow implementations" is consistent with the
seven-member enum `[V]` — and, per §2, with the repository already having more
than seven.

## 12. Owner decisions `[R]`

1. **Enum versus repertoire** — whether `iterate_loop`, `multi_agent`,
   `human_policy` and retrieval are recognised as treatments for workflow-fit
   provenance and benchmarking, and if so how they are named without changing
   `WorkflowType` (§2).
2. **Missing signals** — whether quantitative intensity, conflict, and
   sequential-vs-parallel dependency become `ComplexitySignal` members, or are
   sourced from policy instead (§5).
3. **Reversibility at selection time** — whether a task-level reversibility
   input is introduced, distinct from the action-level
   `external_actions.Reversibility` (§5, SP09).
4. **Choice-rule wording** — whether "least-resource" is replaced by the
   ratified Pareto formulation, or a scalar cost rule is separately ratified
   (§7).
5. **Layer wiring** — whether domain policy is wired into selection (layer 1)
   and what evidence the benchmark layer (layer 3) requires before the selector
   may consult it (§9).

No constant, threshold, weight, signal pattern or enum member is proposed. The
one absent workflow of commercial interest (Program / SQL-assisted) is recorded,
not scoped.

**Recommendation:** treat the proposal as a mostly-accurate map of what already
exists, corrected for four things — the enum undercounts the repertoire, the
choice rule's wording conflicts with a ratified stance, the third layer is
absent, and the ambiguous-scenario conditions are unmodelled. Decision 1
precedes all others: until the repertoire is named, nothing can be benchmarked.
