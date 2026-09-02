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

**The inference runs one way only.** A workflow must **never be inferred from an
observed artifact shape.** A model may privately run Tree of Thought and reveal a
single answer; its observable output is still `SINGLE_CANDIDATE_UNREVISED`, and
**no claim about processing may be made from that artifact**. Workflow identity
is admissible only as declared provenance from the execution record — never
reconstructed from what the advisory looks like. Shape constrains what may be
declared; it never reveals what happened.

**Two boundaries this note does not touch.** The existing gate-based readiness
classification — rules `R0`–`R8`, `EVALUATOR_FORMULA_VERSION` `GV-3R-b.3` — is
**unchanged**; workflow fit never reads it, writes it, or influences a tier.
And workflow fit is **non-financial**: it deals in quality and counted resources,
never money, and **never enters ROI**. Monetary consequences of reasoning spend
belong to `governed-value`'s post-deployment `CostToServe`, which is a different
stage with different evidence rules.

## 2. The four outcomes

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

Four outcomes, **reported separately and never combined** `[R]`:

| Outcome | Meaning |
|---|---|
| `INSUFFICIENT_QUALITY` | `Q(w,t) < τ_t` — under-reasoning |
| `SUFFICIENT_RESOURCE_DOMINATED` | meets `τ_t`, but a tested admissible alternative also met it using no more of any governed resource and less of at least one — over-reasoning |
| `SUFFICIENT_PARETO_EFFICIENT` | meets `τ_t` and no tested alternative dominates it — the **pass** state |
| `COMPARISON_EVIDENCE_ABSENT` | required quality, telemetry, threshold or alternative-run evidence is missing, so **no fit judgement is made** |

> **Correction.** The first draft of this note (`941f74b9`) defined only the two
> failure modes and **named no success outcome**, so a workflow that met its
> threshold and was dominated by nothing had no result to be assigned. That was a
> defect, not a presentation choice: an assessment that can only report failures
> is not an assessment. `SUFFICIENT_PARETO_EFFICIENT` and
> `COMPARISON_EVIDENCE_ABSENT` complete the set.

Low quality is **never penalised inside an efficiency score**. Mixing them would
reproduce exactly the compensatory scoring the composite note rejects.

**Vocabulary caution — why the last two are named as they are.**
`ReadinessClassification` members are `NOT_ASSESSABLE`, `NOT_READY`,
`PILOT_READY`, `READY_WITH_CONDITIONS`, `DEPLOYMENT_READY` `[V]`
(`contracts/enums.py:43-47`). Workflow-fit must **not** reuse any of them — in
particular `NOT_ASSESSABLE`, the tier produced by evaluator rules
`R0`/`R2`/`R3`, must not be borrowed for "comparison evidence absent", hence
`COMPARISON_EVIDENCE_ABSENT`. All four names above are unused anywhere in
`packages/` or `agentic/` `[V]`, following the repository's precedent of one
status enum per concern (`ReadinessInputVerificationStatus`,
`ReadinessIndicatorAdmissionStatus`). The names are illustrative and unratified
`[R]`.

## 2a. A worked example

**Illustrative figures only — not measurements.** No such benchmark has been
run; the numbers exist to show the shape of the judgement `[I]`.

Suppose policy sets `τ_t = 90%` quality for customer-support answers.

**Easy task — "how do I reset my password?"**

| Workflow | Quality | Calls | Meets `τ_t`? |
|---|---|---|---|
| Linear Chain | 92% | 1 | yes |
| Tree of Thought | 94% | 4 | yes |
| Debate | 95% | 5 | yes |

All three clear the threshold. Linear Chain met it using fewer calls than either
alternative, so on this evidence Debate and Tree of Thought are
`SUFFICIENT_RESOURCE_DOMINATED` — **over-reasoning**. The extra quality is real
but was not required. Linear Chain is `SUFFICIENT_PARETO_EFFICIENT`.

**Consequential task — a disputed insurance claim**

| Workflow | Quality | Calls | Meets `τ_t`? |
|---|---|---|---|
| Linear Chain | 72% | 1 | no |
| Tree of Thought | 91% | 4 | yes |
| Debate | 93% | 5 | yes |

Linear Chain is `INSUFFICIENT_QUALITY` — **under-reasoning**. Its cheapness is
irrelevant, because cost is only compared among workflows that already meet the
threshold. Tree of Thought met `τ_t` using fewer calls than Debate, so Debate is
dominated **on a threshold-only reading**.

**That last conclusion is exactly what decision 3 governs.** If this task class
declares that quality above `τ_t` retains value — as §6 argues it must where loss
dominates — then Debate's 93% is not waste and it is not dominated. The same
figures yield different verdicts under different, governed sufficiency rules.
Neither reading is a default `[R]`.

Note what the example does **not** show: that Debate is more intelligent than
Linear Chain. Linear Chain was the right choice in the first case and the wrong
one in the second. **Fit is a property of the pairing, not a ranking of
workflows.**

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
`total_llm_calls`, `total_duration_ms` and `depth_used` `[V]`
(`reasoning_workflows.py:135`). **No token accounting exists in the workflow
runtime** `[G]`, so the usable resource vector is currently **one dimension —
call count**.

**`depth_used` is provenance, not automatically a governed resource** `[R]`. It
is a `ReasoningDepth` ordinal — `SHALLOW`, `MODERATE`, `DEEP`, `RECURSIVE` `[V]`
(`adaptive_prompts.py:75`) — describing *how a workflow was configured*, not a
consumed quantity. Depth correlates with calls but is not a unit of anything;
admitting it into the resource vector would double-count call consumption under a
second name. It is recorded for attribution and left out of the vector unless
ratified otherwise.

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

**One legitimate research use.** The self-score may be studied as the **object**
of a calibration measurement — does a workflow's own confidence track independent
judgement? — which is a question about `CONFIDENCE_CALIBRATION`, an existing
`IntelligenceDimension` `[V]`. Being measured is the opposite of being trusted:
the score is the *subject under test*, never the evidence.

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
   domain and outcome class. One option to consider: let **each task class
   declare its own sufficiency rule** — either *threshold-based*, where quality
   above `τ_t` carries no further readiness value and the cheapest sufficient
   workflow wins, or *improvement-valued*, where gains above `τ_t` continue to
   count and cannot be dominated away on cost alone. §2a shows the same figures
   resolving differently under each. No default is proposed.
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
