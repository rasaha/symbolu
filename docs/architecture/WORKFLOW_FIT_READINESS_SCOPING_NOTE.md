# Workflow-Fit Readiness — Scoping Note

**Status:** scoping note for owner review. No implementation, no package change,
no contract or protocol proposal.
**Scope:** `agentic/agentic_framework/reasoning_workflows.py`, the S2-B strategy
vocabulary, the readiness and governed-value contracts, and the Context
Minimization token-accounting contracts.
**Relationship:** a **separate design thread** from
[`READINESS_ADVISORY_COMPOSITE_DESIGN_NOTE.md`](READINESS_ADVISORY_COMPOSITE_DESIGN_NOTE.md).
That note governs an advisory composite over Intelligence / Capability /
Adoption. This one governs whether a reasoning workflow was *justified*. They
share one unresolved dependency (§9) and are otherwise independent.
**Evidence labels:** `[V]` verified against the repository · `[I]` inferred ·
`[R]` requires owner ratification · `[G]` gap.

## The load-bearing question

**Does the agent use enough reasoning to reach the required quality, and no more
than the task justifies?** Answering it requires a comparison the system does not
currently make, over resources it does not currently record, scored by an
evaluator that does not currently exist. Everything below is what would have to
be true first.

## 1. Four roles, kept apart

| Role | Owner | What it decides |
|---|---|---|
| **Reasoning treatment** | the workflow | which procedure ran |
| **Artifact admissibility** | S2-B | whether the resulting artifact shape is permitted and derivable |
| **Workflow fit** | readiness | whether that treatment reached sufficient quality at justified cost |
| **Measurement** | an independent evaluator | quality and resource use — **the workflow never grades itself** |

S2-B's three ratified members — `SINGLE_CANDIDATE_UNREVISED`,
`MULTI_CANDIDATE_UNREVISED`, `REVISED_ADVISORY` — are **unchanged by this note**.
They are defined over artifact shape (candidate count, parent binding), never
over processing. Workflow identity is **provenance only** and is never proof of
intelligence. The four candidates rejected in S2-B Round 2 stay rejected; nothing
here reopens them.

Only **structured intermediate artifacts** are ever admissible — candidates,
parent-bound revisions, decisions, summaries. **Private reasoning traces are
never required and never admitted.**

## 2. The two failure modes, kept separate

For workflow `w` on task class `t`, with independently measured quality `Q(w,t)`
and governed sufficiency threshold `τ_t`:

```
Under-reasoning regret :  U(w,t) = max(0, τ_t − Q(w,t))

Over-reasoning         :  w meets τ_t, but some admissible v also meets τ_t
                          using no more of any governed resource and less of
                          at least one  (Pareto domination)
```

**No weights, no scalar cost function, no invented constants.** A scalar
resource function would let one resource trade against another by fiat; none is
proposed here `[R]`.

The two outcomes are **reported separately and never combined**:

| Outcome | Meaning |
|---|---|
| `INSUFFICIENT_QUALITY` | `Q(w,t) < τ_t` |
| `SUFFICIENT_RESOURCE_DOMINATED` | meets `τ_t`, dominated on resources |

Low quality is **never penalised inside an efficiency score**. Mixing them would
reproduce exactly the compensatory scoring the composite note rejects.

**Vocabulary caution.** `NOT_ASSESSABLE` is a `ReadinessClassification` **tier**
produced by evaluator rules `R0`/`R2`/`R3` `[V]`
(`contracts/enums.py:43`). Workflow-fit must **not** reuse that name for
"comparison evidence absent"; it needs its own status vocabulary, following the
repository's precedent of one status enum per concern
(`ReadinessInputVerificationStatus`, `ReadinessIndicatorAdmissionStatus`) `[R]`.

## 3. Resources — the contracts already exist

**No new usage type is proposed.** Context Minimization already defines, as
ratified contracts `[V]`
(`packages/capabilities/context-minimization/src/ugence_context_minimization/token_accounting.py`):

- **`ProviderTokenUsage`** — `input_tokens`, `cached_input_tokens`,
  `cache_write_input_tokens`, `output_tokens`, **`reasoning_tokens`**,
  `total_tokens`, all `Optional`, plus `provider_request_id`, `usage_schema`,
  `adapter_id`, `adapter_version`.
- **`TokenCountBasis`** — `PROVIDER_REPORTED`, `INJECTED_COUNTER`,
  `CALLER_SUPPLIED`, `DEFAULT_APPROXIMATE`, `MIXED`, `UNKNOWN`.
- **`UsageAvailability`** — `AVAILABLE`, `UNAVAILABLE_NOT_REPORTED`,
  `UNAVAILABLE_PROVIDER_ERROR`, `UNAVAILABLE_UNKNOWN`.
- **`ApiCallTokenRecord`** — binds `logical_request_id`, `attempt_id`,
  `attempt_number`, `context_id`, `provider_id`, `status`, `usage_availability`
  and an optional `provider_usage`.

`ugence-integration-context-minimization-token-accounting-runtime` (CM-TA1)
already wires these to the Agent Runtime's `ProviderAttempt` telemetry `[V]`.

Three consequences:

1. **Estimated and provider-reported counts must never be conflated.**
   `TokenCountBasis` exists precisely to keep them apart, and CM-TA1's README
   warns that these quantities "are related but not interchangeable" `[V]`.
2. **Missing usage is already expressible** — `UsageAvailability` says both
   *that* usage is absent and *why*. A governing method that requires tokens can
   therefore refuse to assess rather than silently substitute an estimate.
3. **Any workflow-side envelope must be additive.** `LLMClient.call` is
   `def call(self, prompt: str) -> str` `[V]`
   (`reasoning_workflows.py:70`) — a `Protocol`, so every implementer is bound by
   its shape. **No protocol change is proposed here** `[R]`.

**The collection point is a single chokepoint.** All 21 workflow invocations go
through one wrapper, `_call_llm` `[V]` (`reasoning_workflows.py:228-263`), which
performs the sole `llm.call(prompt)` at line 250, enforces the `max_calls` budget
(`INV-WF-2`, line 36), times the call and builds the `WorkflowStep`. Whatever
usage capture is later ratified, it has **one** place to attach, not 21.

**What is recorded today:** `WorkflowResult` carries `workflow_type`,
`total_llm_calls`, `total_duration_ms` and `depth_used`. **No token accounting
exists in the workflow runtime** `[G]`, so the usable resource vector is
currently **one dimension — call count**.

**Calls and tokens correlate**, so Pareto domination will often be **silent**:
many workflow pairs are incomparable, and over-reasoning may go undetected.
Reduced to calls alone the comparison becomes a total order, but that is an
implicit cost rule chosen by omission rather than ratified `[R]`. This is a
stated limitation of the weight-free approach, not a defect to be patched with
weights.

**Latency is diagnostic only.** `total_duration_ms` is wall-clock around
`llm.call` `[V]`, so it carries provider load, network and caching conditions. It
does not determine reasoning efficiency, and it is **not** `CostToServe`, whose
components are monetary — `inference`, `retries`, `evals`, `monitoring`,
`human_in_loop_review`, `incident_remediation`, `model_migration` `[V]`. Latency
belongs to operational/SLA measurement; any translation into money would be a
separate governed calculation.

## 4. Quality, and the self-score

`τ_t` is **expressible with an existing contract**: a `GovernedThreshold` carries
`threshold_id`, `governed_unit`, `comparator` (five operators) and either a
`literal_value` or a `benchmark_ref` `[V]`. No new threshold artifact is needed.

**The workflow's own score is not evidence — and must not be deleted.**
`_basic_quality` awards points for exceeding 20, 50 and 100 words and for
containing a newline `[V]` (`reasoning_workflows.py:265-279`), and it is applied
to **every** step by `_call_llm` (line 259). It is also **load-bearing for
control flow**: `IterativeRefinementWorkflow` compares against
`quality_threshold` (default `0.8`, line 558) and tracks `best_score` to decide
whether to keep revising `[V]` (lines 594, 611, 624). Removing it would remove
the loop's termination condition.

The correct treatment is **separation, not deprecation** `[R]`: the self-score
remains an internal control signal, and is **labelled self-reported and
advisory**. It may never enter a `MetricClaim` as quality evidence. `Q(w,t)` must
come from an independent evaluator.

## 5. What runtime telemetry is, on the existing axes

Telemetry captured by a wrapper inside the same process and trust domain is
**not** independent evidence — the workflow author can alter it. The repository
already has vocabulary for that state, so no new label is coined: such a record
is `SourceBasis.OBSERVED` with `AttestationStatus.UNATTESTED` and
`VerificationStatus.UNVERIFIED` on a `MetricClaim` `[V]`.

Promotion beyond that requires binding telemetry to the exact invocation, model
and provider, workflow execution, subject and task, timestamp and measurement
source, in an immutable or signed record — the role the ratified Trusted Evidence
Authority (TEV, E-1/E-2) exists to play. **Which controls suffice is unresolved**
`[R]`. Until then, workflow telemetry is described as runtime-captured, never as
independently verified.

## 6. Baselines and the comparison set

**Baselines are governed per task class** `[R]`. Linear Chain is a **provisional**
baseline for initial research where it is applicable — not a permanent universal
rule. Some task classes require decomposition, tools or multiple candidates, and
Linear Chain is then an invalid comparator.

The rule is: compare the selected workflow against a **governed set of admissible
alternatives**, including the simplest applicable reference workflow.

**Whether quality above `τ_t` has value is domain-conditioned, and unresolved**
`[R]`. If quality is capped at sufficiency, a cheaper sufficient baseline
dominates a more accurate workflow. That is wrong where loss dominates:
`DomainKind.REGULATED` is annotated "health, legal, credit — **loss dominates**"
`[V]`, `OutcomeClass.RISK_CONTAINMENT` maps to an actuarial baseline, and
residual expected loss is explicitly **unbounded relative to benefit** `[V]`.
A sufficiency cap applied uniformly would recommend under-reasoning exactly where
it is most dangerous.

**This note does not rank the seven workflows as levels of intelligence.** Any
ordering of workflows describes potential evidential exposure or resource
profile, never maturity: a linear workflow can outperform a debate on a simple
task.

## 7. Metacognitive selection

Modelled as an **upstream router**. It selects a workflow; each resulting
proposer invocation still carries **exactly one** admissible strategy shape,
preserving `S2B-D3`'s one-strategy-per-invocation rule. Selection quality is a
property of the router, measurable only by also running an alternative — never by
inspecting a single invocation.

`WorkflowSelector` today is a **fixed categorical routing table**, not a
validated policy: ambiguity → Tree of Thought, conditional logic → Debate,
multi-part → MapReduce, with `LINEAR_CHAIN` as the default for no signal `[V]`
(`reasoning_workflows.py:1228`). That table is an unvalidated justification claim
for every task class it covers. Placing it under **offline benchmark validation**
is the first empirical use of this note `[R]`.

## 8. Validation

**Paired, repeated offline benchmark trials per task class** — never a
counterfactual run during production invocation. A production request executes
one workflow; justification is established in benchmarks, not by doubling live
traffic.

Sample size, effect thresholds, `τ_t` values and acceptance criteria are
**pre-registration matters** and are left with no defaults `[R]`.

## 9. Shared dependency with the composite note

`Q(w,t)` requires deterministic comparison of a verified observation against an
exactly resolved definition — the **consuming evaluation engine**, whose
assignment is ballot 1 of the advisory-composite note and remains open `[V]`.
The two threads are conceptually separate but cannot both proceed past design
until that role is assigned.

## 10. Contract fit

| Quantity | Exists today | Gap |
|---|---|---|
| Workflow identity, call count, duration, depth | `WorkflowResult` `[V]` | — |
| Single capture chokepoint | `_call_llm` `[V]` | — |
| Call budget invariant | `INV-WF-2` `[V]` | — |
| Token categories, basis, availability, per-call record | CM token-accounting contracts `[V]` | not wired to workflows `[G]` |
| Trusted attempt telemetry | Agent Runtime `ProviderAttempt` + CM-TA1 `[V]` | — |
| Sufficiency threshold `τ_t` | `GovernedThreshold` `[V]` | per-task-class values `[G]` |
| Evidence axes for unverified telemetry | `SourceBasis` / `AttestationStatus` / `VerificationStatus` `[V]` | promotion controls `[G]` |
| Independent quality `Q(w,t)` | — | consuming evaluation engine unassigned `[G]` |
| Workflow-fit status vocabulary | — | `[G]` |
| Reasoning-efficiency indicator | no such dimension in any catalog `[V]` | subject ownership unresolved `[G]` |
| Governed alternative set per task class | — | `[G]` |

## 11. Owner decisions `[R]`

1. **Usage binding** — whether workflow token usage binds to the existing
   `ApiCallTokenRecord` / `ProviderTokenUsage` contracts rather than any new
   type, and how estimated versus provider-reported counts are kept distinct.
2. **Status vocabulary** — workflow-fit's own outcome names, avoiding collision
   with the `ReadinessClassification` tiers.
3. **Sufficiency cap** — whether value above `τ_t` is recognised, conditioned on
   domain and outcome class.
4. **Trust controls** — what promotes runtime telemetry beyond
   `OBSERVED`/`UNATTESTED`/`UNVERIFIED`.
5. **Subject ownership** — whether reasoning efficiency is an agent capability,
   a property of the selector, or an operational property of the runtime,
   **resolved before any catalog change is considered**.

Constants, thresholds, weights, ordinal mappings, exponents, sample sizes and
acceptance criteria remain unratified with no defaults.

**Recommendation:** ratify §1, §2 and §6 as architecture. Ratify nothing
numeric, change no contract, and add no enum or protocol member. Decision 5 gates
any catalog work; decisions 1 and 4 gate any measurement work; the
`WorkflowSelector` validation study in §7 can proceed under the research
configuration in §3 and §8 without any of them.
