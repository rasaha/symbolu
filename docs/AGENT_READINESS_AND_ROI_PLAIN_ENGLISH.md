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
