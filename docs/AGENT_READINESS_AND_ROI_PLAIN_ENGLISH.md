# Agent Readiness and ROI, in plain English

**Audience:** anyone who needs to understand what these two modules do without
reading the code or the ADRs. Nothing here is a specification; the packages'
READMEs and the UVI ADR remain authoritative.

## The one-sentence version

Two separate modules answer two different questions about an AI agent:
**"is it ready to deploy?"** (`packages/capabilities/agent-value-readiness`) and
**"did it make money?"** (`packages/governed-value`). They are deliberately kept
apart — the readiness module contains no money vocabulary at all, and the value
module contains no readiness classification.

## Why they are separate

Think of hiring someone.

- **Before** they start, you ask: can they do the work, do we have the tools set
  up, will the team actually use them? That is *readiness*. No salary maths yet.
- **After** they have worked for a quarter, you ask: what did this cost, what did
  it produce, was it worth it? That is *ROI*.

Mixing the two is the classic failure mode of AI business cases — a projected
dollar figure gets attached to a system nobody has yet shown can do the job. The
codebase enforces the separation structurally so that mixing cannot happen by
accident.

---

## Module 1 — Agent Value Readiness

**Where:** `packages/capabilities/agent-value-readiness/`
(`src/ugence_agent_value_readiness/`)

### What it is

A decision engine that takes evidence about an agent and returns one of five
verdicts. Its own shorthand is:

```
PreROIReadiness = f(Intelligence, Capabilities, Adoption
                    | Geography, Domain, IntendedOutcome)
```

Read that as: *readiness depends on three things about the agent, judged in the
context of where and for what it will be used.*

### The three things it looks at

| Family | Plain-English question | Example dimensions |
|---|---|---|
| **Intelligence** | Does it think well enough? | accuracy, reliability, consistency, confidence calibration, knowing when it is unsure |
| **Capability** | Can it actually do the job end to end? | tool readiness, integration readiness, workflow completion, security, auditability, human fallback |
| **Adoption** | Will people actually use it? | workflow coverage, expected utilization, trust readiness, training, expected override/rejection rates |

None of these is money. They are *leading indicators* — signs that value is
plausible later, not a claim that value exists.

### The five verdicts

`ReadinessClassification`, from worst to best:

1. **NOT_ASSESSABLE** — we cannot even judge. The governing policy is missing or
   expired, or required evidence is absent. Silence, not a "no".
2. **NOT_READY** — a mandatory requirement failed, or an unresolved concern has
   no acceptable workaround.
3. **PILOT_READY** — good enough for a bounded pilot, not for production.
4. **READY_WITH_CONDITIONS** — production is acceptable *provided* named,
   approved, still-in-force conditions hold.
5. **DEPLOYMENT_READY** — every applicable mandatory requirement passed and no
   applicable concern is unresolved.

The engine picks the verdict; the caller cannot assert one. The rules are checked
in a fixed order (`R0` policy precondition → `R1` mandatory failure → … → `R8`
deployment ready), so the same inputs always produce the same verdict.

### The three important "no"s

- **It does not authorize deployment.** The result is advisory. A human or a
  separate deployment-governance process decides. `authorizes_deployment` is
  permanently `False` — not a field anyone can set.
- **It does not measure anything.** It consumes gate results and indicator
  records produced elsewhere; it never computes a metric or compares one to a
  threshold.
- **It trusts nothing by default.** Through the main entry point
  (`assess_readiness`), every input — the policy, the gate results, the
  conditions, the identity of the system being assessed — must come back verified
  from an injected checker. Nothing configured means **deny**, not allow. There is
  deliberately no "allow everything" test verifier shipped in the package.

### How it is used

One call: `assess_readiness(request, *, policy_resolver, gate_verifier,
condition_verifier)`. In, a request describing which system, which tenant, which
target (pilot or production), plus the evidence. Out, a verdict with the rule
that produced it, the reason codes, and a trace of anything that could not be
verified.

---

## Module 2 — Governed Value (the ROI side)

**Where:** `packages/governed-value/` (`src/governed_value/`)

### What it computes

```
total benefit    = labor displaced + throughput/revenue gained + loss avoided
ReportedNGV      = total benefit − actual losses − cost to serve
RiskAdjustedNGV  = ReportedNGV − residual expected loss
ReportedROI      = ReportedNGV / total investment
RiskAdjustedROI  = RiskAdjustedNGV / total investment
```

NGV is "net governed value" — the money left after you subtract what went wrong
and what it cost to run.

### The four ideas worth knowing

1. **Only three things count as value.** Labor displaced, throughput gained, loss
   avoided. Satisfaction scores, "productivity", adoption rates are leading
   indicators, not value, and cannot be represented here at all.
2. **Risk is subtracted in real money, not as a discount.** Residual expected
   loss is `Σ (probability × loss magnitude)` in currency. A rare but catastrophic
   failure can exceed all the benefit and push risk-adjusted value deeply
   negative — which is exactly the case a high-stakes agent needs to surface.
3. **Investment and cost-to-serve are different numbers.** Cost to serve is
   subtracted from benefit; total investment is the ROI denominator. Rolling them
   together misstates ROI, so they are separate objects.
4. **When there is no defensible basis, no number is published.** `Scorability`
   can be `NOT_SCORABLE`, which suppresses the headline figure. A number without
   a basis is treated as worse than no number.

### What the numbers do and do not mean

Every figure is classified on three independent axes, so a reader always knows
what they are looking at:

- **Stage** — where in the lifecycle: pre-ROI readiness / forecast /
  post-deployment. This kernel only ever emits *post-deployment*.
- **Evidence** — reported → modeled → observed → attributed → verified. This
  kernel only ever emits *reported*: every input is a caller's assertion. Calling
  an input "realized" does not make it observed.
- **Authority** — did a governance or finance authority attest it? This kernel
  only ever emits *unverified*.

There is a fourth, separate label: `reported_confidence` (low/medium/high). It is
a caller's opinion, it is not evidence, and it never enters any calculation.

### How it is used

`GovernedValueApplication.score(case)` takes a case describing the agent, the
domain, the intended outcome and the reported figures, and returns a result plus
a published event. The intended outcome determines the measurement method
automatically — for example, deterministic automation is measured before/after
against a baseline, while risk containment is measured against an actuarial
baseline.

---

---

## Worked example — a customer-support agent

One agent, followed across both stages. **Every result below was produced by
executing the packages, not by hand** — Stage 1 by calling `assess_readiness`
with a real Policy Authority resolver, Stage 2 by calling `score_case` from
`packages/governed-value/src/governed_value/services/scorer.py`. Verdicts, rule
ids, reason codes, advisories and rupee figures are all transcribed from real
output. Stage 1 carries one caveat about its verifiers, stated at the end of
that stage.

### Stage 1 — before deployment: readiness

An Indian enterprise wants to deploy a support agent that resolves refund and
order-status tickets. Its readiness policy defines four gates:

| Gate | Class | Compensable? |
|---|---|---|
| `accuracy` | `MANDATORY` | — |
| `security` | `MANDATORY` | — |
| `human-escalation` | `CONDITIONAL` | yes |
| `regional-language` | `CONDITIONAL` | yes |

Both mandatory gates `PASS`. Both conditional gates `FAIL`, and each is covered
by an approved, still-in-force condition — a staffed escalation desk, and a
rollout held to English until Hindi/Tamil coverage lands. Assessed against a
`PRODUCTION` target, `assess_readiness` returns:

```
status                 EVALUATED
classification         READY_WITH_CONDITIONS
rule_id                GV3RB_R7_READY_WITH_CONDITIONS
reason_codes           GV3RB_ALL_APPLICABLE_MANDATORY_GATES_PASSED
                       GV3RB_CONDITIONAL_CONCERNS_COVERED_BY_ACTIVE_CONDITIONS
advisory_codes         GV3RB_ADV_ADVISORY_ONLY_NOT_DEPLOYMENT_AUTHORIZATION
                       GV3RB_ADV_POLICY_AUTHENTICITY_NOT_VERIFIED
                       GV3RB_ADV_GATE_STATUS_STRUCTURALLY_SUPPLIED
                       GV3RB_ADV_EVIDENCE_CLASSIFICATION_PRESERVED
                       GV3RB_ADV_READINESS_IS_LEADING_INDICATOR_ONLY
                       GV3RB_ADV_CONDITION_APPROVAL_AUTHENTICITY_NOT_VERIFIED
                       GV3RB_ADV_CONDITION_SCOPE_NOT_TENANT_BOUND
authorizes_deployment  False
accepted_condition_ids ('cond-english-only-rollout', 'cond-escalation-desk')
unresolved_conditional ('human-escalation', 'regional-language')
uncovered_conditional  ()
trust_gap_codes        ()
orchestrator_version   ugence.readiness-orchestration/v0.2
formula_version        GV-3R-b.3
```

Note how many advisories a *good* result carries. Five are emitted
unconditionally and two more whenever any condition is present: the evaluator
states what it did **not** prove every single time, including on its best
verdicts. `GV3RB_ADV_POLICY_AUTHENTICITY_NOT_VERIFIED` appears even though this
run resolved its policy through a genuinely signed and registered authority —
the evaluator speaks only for itself and never claims the orchestrator's
verification as its own.

Change one input and the verdict moves, each time by a different rule:

| Change | Verdict | Rule |
|---|---|---|
| (as above) | `READY_WITH_CONDITIONS` | `R7` |
| Conditions omitted | `NOT_READY` | `R5` — concerns uncovered |
| `condition_verifier=None` | `NOT_READY` | `R5`, plus trust gaps |
| Mandatory `accuracy` fails | `NOT_READY` | `R1` — mandatory failure |
| All four gates pass | `DEPLOYMENT_READY` | `R8` |
| Same evidence, `PILOT` target | `PILOT_READY` | `R6` |

Two of those rows are the ones worth dwelling on.

**Unconfigured means deny, not allow.** Passing `condition_verifier=None` does
not leave the conditions merely unchecked — they are refused admission entirely,
the concerns become uncovered, and the verdict drops to `NOT_READY` carrying
`READINESS_ORCHESTRATION_CONDITION_VERIFIER_NOT_CONFIGURED`. An unverified
condition compensates for nothing.

**`PILOT_READY` carries the conditions with it.** Against a pilot target the
same two covered concerns yield `PILOT_READY` plus
`GV3RB_PILOT_SCOPE_IS_BOUNDED` — not a "pilot ready with conditions" tier,
because none exists. The bounded pilot scope *is* the condition.

**No rupee figure appears anywhere in this result.** Readiness does not predict
savings, revenue or ROI.

> **How this was produced, and its one limit.** The run above uses the real
> `assess_readiness` entry point and a real
> `PolicyAuthorityReadinessPolicyResolver` over a policy genuinely issued,
> signed and registered through the shared Policy Authority — digest binding,
> key trust and signature verification all execute
> (`policy_resolution_status=RESOLVED`, `accepted=True`). The gate and condition
> verifiers are `StubGateVerifier` and `StubConditionVerifier` from
> `tests/orchestration/_orchestration_fixtures.py`, because **the package ships
> no real ones** — evidence and TAP verification are deferred, and the absence
> of any allow-all verifier is itself the trust boundary. So this example proves
> the classification logic and the orchestration boundary, not that any gate
> status was independently established. That is precisely what
> `GV3RB_ADV_GATE_STATUS_STRUCTURALLY_SUPPLIED` is telling you.

### Stage 2 — three months later: governed value

The agent has run for a quarter. The enterprise reports its own figures — all
amounts in ₹ lakh, single currency, one accounting window.

**Benefit (the numerator)**

| Component | Amount |
|---|---|
| Labour displaced | ₹8.00 lakh |
| Throughput gained | ₹1.00 lakh |
| Loss avoided | ₹2.00 lakh |
| **Total benefit** | **₹11.00 lakh** |

Note that *loss avoided* is a **benefit** — losses the agent prevented. It is a
different object from residual expected loss below, and the two are never mixed.

**Subtractions**

| Component | Amount |
|---|---|
| Actual losses incurred (mis-resolutions the agent caused) | ₹0.50 lakh |
| Cost to serve — inference ₹1.20, retries ₹0.20, evals ₹0.30, monitoring ₹0.40, human-in-loop review ₹1.00, incident remediation ₹0.30, model migration ₹0.10 | ₹3.50 lakh |

All seven cost components are stated. A component left unstated is *not* the
same as one stated as zero: the kernel flags "cost-to-serve incomplete" and
degrades the verdict, so "we forgot monitoring" cannot masquerade as "monitoring
is free".

**Forward risk (the risk-adjusted view only)**

| Item | Probability | Magnitude | Expected loss |
|---|---|---|---|
| Wrongful refund / mis-resolution at scale | 0.05 | ₹20.00 lakh | ₹1.00 lakh |
| Regulatory complaint from a mishandled case | 0.02 | ₹25.00 lakh | ₹0.50 lakh |
| **Residual expected loss** | | | **₹1.50 lakh** |

**Investment (the ROI denominator)**

Capex ₹2.00 + one-time build ₹10.00 + integration ₹6.00 + amortized cost-to-serve
₹2.00 = **₹20.00 lakh**. This is distinct from cost-to-serve; dividing by the
wrong one misstates ROI.

**Result**

```
ReportedNGV      = 11.00 − 0.50 − 3.50            = ₹7.00 lakh
RiskAdjustedNGV  = 7.00 − 1.50                    = ₹5.50 lakh
ReportedROI      = 7.00 / 20.00                   = 0.35   (35%)
RiskAdjustedROI  = 5.50 / 20.00                   = 0.275  (27.5%)

stage       = POST_DEPLOYMENT_VALUE
evidence    = REPORTED
authority   = UNVERIFIED
scorability = SCORABLE
method      = BEFORE_AFTER_BASELINE   (fixed by the intended outcome)
confidence  = MEDIUM                  (caller's label; not used in the arithmetic)
```

Read the labels as strictly as they are written. `REPORTED` means every input is
the enterprise's own assertion about that window — the kernel verified nothing.
`UNVERIFIED` means no governance or finance authority attested the figure. A
defensible way to publish it is: **"Reported ROI 35% (risk-adjusted 27.5%) —
reported, unverified."** Dropping either qualifier overstates what the number is.

Payback is `None` here, because payback is computed only when the caller supplies
a defensible net run-rate per period.

### The trap: no baseline, no headline

Re-run the identical case with one change — no pre-deployment baseline was
captured:

```
scorability     = NOT_SCORABLE
ReportedROI     = None          (suppressed, not reduced)
RiskAdjustedROI = None
reason          : "no pre-deployment baseline captured;
                   before/after value is unrecoverable"
```

The component money is still reported, but **the headline ratio is withheld
entirely**. A number without a defensible basis is treated as worse than no
number.

This is the practical reason the two stages belong to one story. Baseline
capture, holdout design and instrumentation are *readiness-stage* work: if they
are not in place before deployment, no amount of post-deployment accounting can
recover an ROI figure. Readiness is not only "is the agent good enough" — it is
also "will we be able to measure what it does".

### What connects the two stages

Nothing in code. `packages/governed-value` declares
`dependencies = []` and neither package imports the other; there is no adapter,
no shared entry point, and no readiness field anywhere in `AgentValueCase`. A
`READY_WITH_CONDITIONS` verdict does not flow into a value calculation and does
not predict a 35% return. The link is a human process: people carry a readiness
result to a deployment decision, and — if they set up measurement properly —
score the value afterwards.

That gap is deliberate. A high readiness verdict guaranteeing ROI is precisely
the claim neither module makes.

## What neither module does yet

Both packages are explicit that large pieces are deferred, and it matters for
anyone reading a number out of them:

- No benchmark registry, no evidence verification, no attribution — so no figure
  can currently claim to be observed, attributed, or verified.
- No system-binding verifier exists, so the identity of the assessed system is
  structurally recorded but not cryptographically proven.
- No forecast engine, no FX, no portfolio comparison.
- Neither module authorizes anything. Both are inputs to human decisions.

## Where to read more

- `packages/capabilities/agent-value-readiness/README.md` — scope and boundaries
- `packages/capabilities/agent-value-readiness/public_api.json` — the exact
  vocabulary, generated from the installed package
- `packages/governed-value/README.md` — the formulas and their rationale
- `packages/governed-value/src/governed_value/domain/enums.py` — the
  classification axes, with the reasoning in the docstrings
