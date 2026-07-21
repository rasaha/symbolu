# Ugence Platform — Cost Savings Analysis (Honest Edition)

**Ugence Labs | The Governed AI Platform**
*Per-module cost-savings levers, grounded in the repository's own numbers — with the counter-costs stated, not hidden.*
*Version 1.0 — July 2026*

> **Purpose and discipline.** For each of the ten platform components this document states
> (a) the **cost lever** — how it could reduce a customer's total cost, (b) the **grounded
> figure** the repo actually supports (labeled by evidence type), (c) the **counter-cost** —
> what the module *adds* or trades away, and (d) an **honest net read**. It is a costing
> *framework*, not a savings *guarantee*. Canonical architecture: `UGENCE_PLATFORM_OVERVIEW.md`;
> maturity detail: `UGENCE_PLATFORM_VALUE_PROPOSITIONS.md`.
>
> **Evidence labels.**
> **[MEASURED]** observed on this repo's code/experiments (mostly synthetic/internal, no
> third-party or production data) · **[PROJECTED]** an analytical consequence of the
> architecture's complexity class, not a benchmark · **[ROADMAP]** not yet run ·
> **[NOT-QUANTIFIED]** a real cost lever with no repo number behind it yet.
>
> **Three honest warnings before any number below is used:**
> 1. **No dollar figure here is a repo measurement.** Any `$` amount is *illustrative unit
>    economics* — a ratio from the repo multiplied by a rate **you** supply. Ratios are real
>    (labeled); the dollars are worked examples, not claims.
> 2. **Two modules have a real counter-cost that can make them cost-*negative* if misapplied**
>    (KVPro throughput; Context Minimization accuracy). These are called out, not buried.
> 3. **Risk-avoidance "savings" are the softest category.** Avoided-incident cost depends on an
>    incident rate this repo has not measured on real data. Treated as scenario math, not fact.

---

## The three cost-savings mechanisms

A platform can lower a customer's cost in three structurally different ways. Mixing them into
one "X% cheaper" headline is where honesty usually breaks — so they are kept separate.

| Mechanism | What it reduces | Modules | Confidence |
|---|---|---|---|
| **A. Compute efficiency** | $ per token / per session / per GPU-hour | Hybrid LLM, KVPro, Context Minimization, Cloud Scaling Controller | Hardest, most quantifiable — but each has a counter-cost |
| **B. Risk / incident avoidance** | Cost of a bad action, wrong answer, or outage that *didn't happen* | ActionGate, TAP, ACP, Agent Runtime (governance) | Real lever, softest numbers (depends on unmeasured incident rates) |
| **C. Quality / rework avoidance** | Retries, human review, wasted generations | LLM Steering Controller, Agent Runtime (proposals) | Weakly validated today |

---

# Mechanism A — Compute efficiency (the quantifiable levers)

## 1. Hybrid LLM — remove the O(n²) tax on the long-range path

**Cost lever.** Standard attention cost grows with n²; the Hybrid LLM's long-range path is
**O(n)** with the quadratic branch invoked only on conditional top-K proposals. At long
context the *shape* of the compute-and-memory curve is fundamentally lower.

**Grounded figure.**
- **[PROJECTED]** Compute-work *shape* vs. a dense stack (from the complexity class, not a
  benchmark): ~1× at 4K → the dense stack grows ~64× at 32K, ~1,024× at 128K, ~62,500× at 1M,
  while the hybrid long-range path grows ~linearly plus a conditional top-K term.
- **[PROJECTED]** Memory: a dense KV cache grows linearly with context and dominates
  long-context serving; the phase state is **bounded** with an O(1) per-step update.
- **[MEASURED]** only at the mechanism level (240K pure-phase, 100% needle at 10K on a
  synthetic task) — this validates the *mechanism*, not a serving-cost number.

**Counter-cost.** Serial fusion adds sequencing/normalization work per layer; at **short**
context (4K–8K) the O(n²) tax is small, so the savings are muted exactly where many workloads
live. The throughput report that would turn "projected" into "measured" is **[ROADMAP]**.

**Honest net.** A *structural* cost-curve advantage that is real in complexity terms and
unproven in wall-clock terms. Quote the **shape**, never a specific "N× cheaper" dollar figure,
until the throughput report exists.

## 2. KVPro — more concurrent long-context sessions per GPU (with a real catch)

**Cost lever.** Storing the KV cache in INT4 (with ~4% protected channels) raises KV **density**,
so one GPU holds more concurrent long-context sessions → fewer GPUs for the same session count.

**Grounded figure.**
- **[MEASURED]** **1.83× net / 2.02× raw** KV density under saturation, at near-parity quality
  (needle 15/15 == bf16 on 3/4 models; MMLU 0.0-pt delta with 100% per-question agreement).
- *Illustrative unit economics:* if a workload is **KV-capacity-bound** and you serve N
  sessions on G GPUs, ~1.8× density → serve the same N on ≈ G/1.8 GPUs. Multiply the removed
  GPU-hours by *your* GPU rate for the dollar figure. (Ratio [MEASURED]; dollars illustrative.)

**Counter-cost — this one can flip the sign.**
- **[MEASURED]** Throughput is **negative**: ~**0.13–0.67× bf16** (worst case ~0.22×). If your
  cost is **throughput-bound**, KVPro *increases* $/token even as it *decreases* $/session-slot.
- **[MEASURED]** A **+4.4 GB HBM "sidecar tax,"** so it is *capacity-negative at equal
  GPU-memory-utilization* — net-positive only when run at the KV block limit.

**Honest net.** A genuine **capacity/quality** saving for memory-bound long-context serving,
and a **cost increase** for throughput-bound serving. The saving is real only when the binding
constraint is KV memory, not tokens/sec. The repo's own memo says it plainly: *"we do not win
on compression ratio or 'perfect quality.'"* v2 throughput recovery is **[ROADMAP]** (GPU-blocked).

## 3. Context Minimization — fewer input tokens per authorization-bearing call

**Cost lever.** Extractively drop context spans a deterministic gate proves cannot change its
decision → fewer input tokens billed per governed call, with a byte-identical gate decision.

**Grounded figure.**
- **[MEASURED, synthetic corpus]** Claimed **32–66% token reduction** on authorization context;
  real open-weight GPU runs committed (Qwen-7B/14B).
- *Illustrative:* 50% fewer input tokens on the governed portion of a prompt → ~50% off that
  portion's input-token bill. Multiply by *your* input-token price and call volume.

**Counter-cost.**
- **[MEASURED]** Self-verdict is **`LIMITED_GO`**: absolute downstream task accuracy is depressed
  on some tasks (tool-argument generation ~37.5%). Token savings that reduce answer quality can
  cost more in rework than they save in tokens.
- The **32–66% is partly a corpus artifact** (synthetic filler sits in decision-neutral spans);
  on mixed real content "precision will drop."

**Honest net.** A real input-token saving for governed, context-heavy calls — but only bankable
once the fail-closed loop is validated on *real* mixed content, and only where the accuracy hit
is tolerable. Net savings = token savings − rework cost from any accuracy loss.

## 4. Cloud Scaling Controller — stop paying for over-provisioning and thrash

**Cost lever.** Coherence-gated damping refuses to chase volatile demand, avoiding the
over-provisioning and oscillation that dominate autoscaler waste.

**Grounded figure.**
- **[MEASURED, simulation]** vs. an HPA baseline across six traffic patterns: **~7.8× better
  average cost efficiency** (1.07× vs 8.32× of optimal), **zero oscillations**, **max overshoot
  +3 vs HPA's +203**. On the oscillating pattern specifically, HPA burned **21.6× optimal**.
- *Illustrative:* if replica-hours track cost and your autoscaler runs near HPA's ~8× optimal on
  volatile load, moving toward ~1.1–1.2× optimal is the saving envelope. Multiply the removed
  replica-hours by *your* instance rate.

**Counter-cost.**
- **[MEASURED]** The default profile is **under-actuated**: reaction time **200 cycles
  (effectively never reacts)** and a **higher SLO-breach rate** than HPA — under-provisioning is
  its own cost (latency, lost requests). The docs show a one-parameter fix (`G_base` 1.0→2.0
  recovers ~40% of reaction time at 1.16× cost, keeping zero oscillations), but the shipped
  default trades SLO for savings.
- All numbers are **simulation** vs. synthetic patterns and an oracle baseline — **not a real
  cloud or real cost data.**

**Honest net.** The largest, cleanest *efficiency ratio* in the portfolio (7–8×) — but on
simulated load, and only bankable with tuning that balances the SLO-breach counter-cost. Real
savings = avoided over-provisioning − cost of any SLO breaches from under-provisioning.

---

# Mechanism B — Risk / incident avoidance (real lever, softest numbers)

> These modules do not lower $/token; they lower the *expected cost of a bad event*. Expected
> saving = (incident probability avoided) × (cost per incident). **This repo has not measured an
> incident rate on real data**, so every figure here is **[NOT-QUANTIFIED]** scenario math. What
> the repo *does* support is that the mechanism catches the events in test.

## 5. ActionGate — prevent the unauthorized/irreversible action

**Cost lever.** Deterministically deny/escalate an unsafe action *before* commit → avoid the
cost of a bad automated action (bad deploy, wrong DB mutation, unauthorized spend) and the
audit/remediation that follows.

**Grounded figure.** **[MEASURED]** Red-team detection **12/12 injected attacks**; **24/24**
conformance vectors; replay/TOCTOU caught in tests. These prove the gate *catches* the events;
they do **not** put a dollar on avoided incidents. Expected saving is **[NOT-QUANTIFIED]** —
scenario: (rate of would-be bad actions) × (blast-radius cost each).

**Counter-cost.** Real deployment adds a gate hop (latency) and the operational cost of running
the control plane (which today lacks HA/observability/API — so productionizing it is itself a
cost). False-deny/escalation friction has a productivity cost not yet measured.

**Honest net.** The most *build-validated* risk lever in the portfolio — but the savings number
is a function of an incident rate the customer must supply; we can prove detection, not ROI.

## 6. TAP — prevent the ungrounded assertion reaching a user

**Cost lever.** Validate/qualify/abstain before delivery → avoid the cost of an acted-upon
hallucination (bad decision, compliance exposure, lost trust). This targets the #1 stated
blocker slowing enterprise gen-AI adoption.

**Grounded figure.** **[NOT-QUANTIFIED].** TAP is **emerging** — only the Claim Truth layer has a
synthetic prototype whose own verdict is "production: NO." No avoided-error rate is measured.

**Counter-cost.** Validation adds latency and compute per response (retrieval + checks), and
abstention has a coverage cost (some answerable queries get declined). Net only positive when
the avoided-error cost exceeds the added per-response validation cost.

**Honest net.** Strategically the best-aimed cost lever (it attacks the exact trust gap that
stalls adoption) — but today a *thesis*, not a measured saving.

## 7. Autonomous Control Plane (ACP) — prevent the unsafe physical action

**Cost lever.** Fail-closed clearance so an unsafe robotic/industrial action structurally cannot
execute → avoid the (potentially very high) cost of an unsafe physical event.

**Grounded figure.** **[MEASURED, shadow/synthetic]** deterministic core, agreement 1.00 on
synthetic scenarios, generalizes hash-identical across robotics + cloud. Avoided-incident dollars
are **[NOT-QUANTIFIED]**.

**Counter-cost.** Shadow-only, OFF by default, stub planner, WCET **asserted not measured**;
productionizing needs a C++/Rust port for hard-real-time. Verdict is `INSUFFICIENT_EVIDENCE` —
today it is a cost (engineering) more than a saving.

**Honest net.** High *potential* avoided-cost (physical incidents are expensive), lowest current
evidence. Do not put a number on it yet.

## 8. Agent Runtime (governance) — one governed contract instead of N per-framework glue

**Cost lever.** A single canonical execution contract (CER) governed externally → avoid rebuilding
governance/audit glue per agent framework, and avoid the cost of an ungoverned agent action.

**Grounded figure.** **[MEASURED]** 0 governance-boundary violations; parity corpus 16/16. The
*engineering-cost* saving (build-once vs. per-framework) is **[NOT-QUANTIFIED]** (real, but no repo
number). Ungoverned-action avoidance is scenario math.

**Counter-cost.** Every **real-model** validation phase is **`BLOCKED_NO_REAL_MODEL`**; the v1
suite isn't green in a clean run and isn't in CI. The integration/operational cost is real and
present; the savings are prospective.

**Honest net.** A credible *build-once governance* saving in principle; unproven end-to-end.

---

# Mechanism C — Quality / rework avoidance (weakly validated)

## 9. LLM Steering Controller — fewer off-frame answers, fewer retries

**Cost lever.** Deterministically fix the answer frame → fewer wrong-domain/off-policy generations
→ fewer retries and less human review per query.

**Grounded figure.** **[MEASURED, single model, rubric-scored]** primary-frame correctness
0.61→0.74, rejected-domain avoidance 0.86→0.91 on one model, scored by a deterministic rubric
(not humans). Rework-dollars are **[NOT-QUANTIFIED]**.

**Counter-cost.** The headline data file isn't committed to the repo; **no human validation
exists**; the "Conscious Generation" signals are self-falsified. Adds a per-call framing/audit hop.

**Honest net.** A plausible retry-reduction saving from the deterministic layer, on thin evidence.
The savings claim should ride only on the frame-control product, not the research layer.

## 10. Autonomous Runtime (BCVF) — *no defensible cost-savings claim today*

**Cost lever (as pitched).** Predictor-trust arbitration to avoid acting on a failing predictor.

**Grounded figure.** **None that survives the repo's own audit.** The preregistered audit finds
the arbitration **underperforms a trivial deterministic baseline** (recall 0.90 vs 1.00;
false-alarm 0.67 vs 0.04) and its "safety invariance" guards a *harmful* error class.

**Honest net.** **Do not put a cost-savings number on this module.** Its only recoverable value
(detection latency) is available by bolting it onto the deterministic baseline as an off-by-default
feature — a cost story to be re-derived after the V2 reframe, not before.

---

## Summary table

| # | Module | Mechanism | Best grounded figure | Evidence | Counter-cost that can erase it |
|---|---|---|---|---|---|
| 1 | Hybrid LLM | Compute | O(n) long-range path; dense grows ~64×/1,024×/62,500× at 32K/128K/1M | [PROJECTED] | short-context savings muted; throughput unmeasured |
| 2 | KVPro | Compute | 1.83× KV density at ~parity quality | [MEASURED] | throughput 0.13–0.67× bf16; +4.4 GB HBM tax |
| 3 | Context Minimization | Compute | 32–66% input-token cut on governed context | [MEASURED, synthetic] | accuracy hit (`LIMITED_GO`); % partly a corpus artifact |
| 4 | Cloud Scaling Controller | Compute | ~7.8× cost efficiency vs HPA | [MEASURED, sim] | under-actuated default → higher SLO breaches |
| 5 | ActionGate | Risk | 12/12 attacks blocked (detection, not $) | [MEASURED] | control-plane run cost; unmeasured incident rate |
| 6 | TAP | Risk | avoided-hallucination cost | [NOT-QUANTIFIED] | emerging; per-response validation cost |
| 7 | ACP | Risk | avoided unsafe physical action | [NOT-QUANTIFIED] | shadow-only; `INSUFFICIENT_EVIDENCE` |
| 8 | Agent Runtime | Risk / build-once | 0 boundary violations; build-once governance | [MEASURED] / [NOT-QUANTIFIED] | real-model blocked; integration cost now |
| 9 | LLM Steering Controller | Rework | frame correctness 0.61→0.74 (1 model, rubric) | [MEASURED, thin] | no human validation; data uncommitted |
| 10 | Autonomous Runtime (BCVF) | — | **none defensible** | claim inverted by own audit | underperforms trivial baseline |

---

## An illustrative worked example (clearly hypothetical)

*Purpose: show how to combine the levers — not to assert a result. Every ratio is [MEASURED]/
[PROJECTED] as labeled; every rate is a placeholder you replace.*

A team serves long-context enterprise agents that are **KV-memory-bound** at 32K context:

- **Context Minimization** trims ~40% of governed input tokens → ~40% off that call's input bill
  *(if accuracy on their tasks holds — must be verified on their data).*
- **KVPro** raises KV density ~1.8× → ~1.8× more sessions per GPU → ≈ `G/1.8` GPUs for the same
  session count *(only because the constraint is KV memory, not tokens/sec — if it were
  throughput-bound, KVPro would raise cost here).*
- **Cloud Scaling Controller** keeps the fleet near ~1.1–1.2× optimal instead of thrashing to ~8×
  on their spiky load *(after tuning `G_base` so SLO breaches stay acceptable).*
- **Hybrid LLM** (if/when its throughput report lands) would lower the per-call compute-curve at
  32K by construction — **[ROADMAP]**, so left out of any committed number.

The *combined* saving is the product of the compute ratios **on the portion of cost each one
actually touches** — not additive, and gated on each module's counter-cost being satisfied. Plug
the team's real token price, GPU rate, and load profile to get a figure; do **not** quote a
portfolio "X% cheaper" headline, because the three mechanisms and their counter-costs don't
compose into one number.

---

## Cross-cutting honest read

- **The strongest, cleanest ratios** are Cloud Scaling Controller (~7–8×, sim) and KVPro density
  (1.83×, measured) — but each has a counter-cost (SLO breaches; throughput) that can invert the
  saving if the binding constraint is misread.
- **The largest *structural* saving** is the Hybrid LLM's O(n) curve — but it is **projected**, so
  it belongs in a "why the architecture scales cheaper" narrative, not a committed invoice.
- **Risk-avoidance modules** (ActionGate/TAP/ACP/Agent Runtime) have real levers but **no measured
  incident rate**, so their ROI is scenario math the customer parameterizes — we can prove
  *detection*, not *dollars*.
- **Two modules should carry no savings number today:** Context Minimization only nets positive
  where its accuracy hit is tolerable and verified on real data; Autonomous Runtime (BCVF) has its
  cost claim inverted by the repo's own audit.
- **Portfolio caveat (again):** every ratio is self-generated, mostly synthetic; there is no
  production, real-workload, or third-party cost validation yet. This is a **costing framework to
  validate against a real workload**, not a savings guarantee.

---

*Ugence Labs — the governed AI platform.*
*Sources: each module's VC brief, readiness/implementation audit, and machine-readable results
under the repository; see `UGENCE_PLATFORM_VALUE_PROPOSITIONS.md` for maturity detail and
`UGENCE_PLATFORM_OVERVIEW.md` for the canonical taxonomy.*
