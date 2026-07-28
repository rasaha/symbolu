# Ugence Labs / Symbolu — Module Use Cases

**Problem → How we're solving it, module by module.**

*Prepared for investor review. One card per platform module: the problem it
attacks, how we solve it, who it's for, and the proof we have today — including,
in plain language, what is not yet proven.*

---

## How to read this document

Ugence is **one platform: three architectural layers containing ten platform
components**, plus a small set of cross-cutting and adjacent modules. The
organizing thesis is simple:

> **"Making AI trustworthy — from chip to chat."**
> The runtime *proposes*, the control plane *governs*, the infrastructure *runs
> it efficiently*. Governance is deliberately kept **external and deterministic**
> — a runtime that grades its own homework is not governed.

```
  SPECIALIZED AI SYSTEMS   reason · steer · execute      → proposes actions
        │
  AI CONTROL PLANE         govern the interaction boundary → validated · authorized · cleared
        │
  AI INFRASTRUCTURE        run it efficiently (never governs)
```

**A note on evidence — read this first.** These modules are backed by extensive
internal test suites and pre-registered evaluations, and the numbers below are
real. But almost all results to date are from **our own repositories and CI, on
synthetic or internally-authored corpora** — not third-party benchmarks, and not
production or paying-customer deployments. Where a module is early, the card says
so explicitly. That discipline is deliberate: every brief in this codebase keeps
an honest ledger of what failed and what remains unproven, and this summary
preserves it. The credible pitch is the *architecture and the trajectory*, not a
claim of production maturity.

A one-line status tag on each card:

- 🟢 **Validated (internal):** strong internal/CI evidence across multiple
  settings; production/customer validation still pending.
- 🟡 **Prototyped:** working implementation with promising results on synthetic
  or single-model evidence.
- 🔵 **Emerging / research:** architecture specified, early or negative-result
  discipline in progress.

---

# Layer 1 — Specialized AI Systems

*Someone has to actually do the AI work: reason well, control how generation
happens, and drive a supervised execution loop. This layer owns the applied
intelligence. It proposes; it never authorizes itself.*

---

## 1.1 Hybrid LLM — the reasoning substrate  🟢

**Problem.** In most agentic AI stacks a single language model is trusted, inside
one probabilistic loop, to interpret evidence, state conclusions, decide, and
trigger actions. That collapses four distinct duties — interpretation,
fact-admission, decision authority, execution authority — into one generative
call. This is where enterprise reliability breaks: a "request" gets read as an
"approval," a stale policy looks current, or an agent authorizes its own action.
These are *separation-of-duties* failures, not problems a bigger model fixes.

**How we're solving it.** Hybrid LLM separates those duties across dedicated
layers. It computes what is knowable *exactly* with deterministic parsing, and
confines the model to the few genuinely semantic fields where it may only
*propose* provenance-linked, span-verified records. Model outputs become
**provisional evidence that must be validated before being trusted**; enterprise
facts and outcomes are computed deterministically wherever possible. An
assertion-governance layer independently checks each generated explanation
against the evidence and hard authority ceilings, after which decision governance
decides *who* has authority and ActionGate authorizes *which* action executes.
The governing principle: **"Runtime proposes. The Control Plane authorizes."**

**Who it's for.** Enterprises running agentic AI over authoritative systems of
record where reliability and auditability matter (demonstrated on a synthetic
procurement corpus). Ugence can either back its own agents or sit as a governance
layer over a third-party agent stack — "build or govern."

**Proof points.**
- **0.00 unsupported-fact admission** at every simulated interpreter-quality
  level, vs an ungoverned baseline of **0.35 (17.7% admission)**.
- Assertion governance: **100% recall** on unsupported / authority-exceeding
  claims at 1.00 supported precision, vs **0.00** for prompt-only grounding.
- Deterministic field computation lifts outcome correctness **0.64 → 1.00** and
  conflict F1 **0.26 → 1.00**; ID preservation 1.00 / unauthorized inclusion 0.00.
- *Honest scope:* all enterprise results are on a **synthetic, controlled** corpus
  using a **simulated interpreter, not a live model**; live-model interpretation
  remains externally unvalidated.

---

## 1.2 LLM Steering Controller — deterministic generation steering & audit  🟡

**Problem.** LLMs usually fail not because they write badly, but because they
answer under the **wrong frame** — promoting a secondary reading of an ambiguous
query, drifting into an adjacent domain mid-answer, or padding with generic
low-signal text. Existing fixes (RLHF, retrieval, moderation) act only *after* the
model has committed, and they are stochastic: the same prompt behaves differently
across runs and silently drifts across model versions. For an enterprise buyer
that is behavior which can't be reproduced, tested, or audited — a governance
problem, not just a quality one.

**How we're solving it.** A deterministic, model-agnostic "steering wheel and
trip-recorder" bolted onto any LLM. *Before* generation, a rule-based engine
(C×R×S: Context × Semantic × Resonance) matches the input to a meaning-frame
(primary / secondary / weak / rejected) using frozen thresholds, so the same
input always yields the same frame. The answer is generated inside that frame; a
deterministic answer-audit gate then passes, rewrites, or escalates it. Every
steering decision emits a logged, traceable reason. No weight changes, no
retraining; works on open-weight models (activation-level steering) and closed
APIs (as a vendor-agnostic control plane). **We sell control and trust, not
"intelligence" or "decoded meaning."**

**Who it's for.** Two buyers from one product: (1) self-hosting, privacy/compliance
shops — especially European/regulated buyers — who own open-weight models and
want on-prem, AI-Act-friendly governance; (2) teams on proprietary APIs
(Claude/GPT/Gemini) who want cross-vendor consistency, one audit trail, and
freedom from lock-in.

**Proof points.**
- Internal eval (Mistral-7B-Instruct-v0.3, 110-item polysemy set, deterministic
  rubric): primary-frame correctness **0.609 → 0.736** (+0.127), rejected-domain
  avoidance **0.855 → 0.909**, factuality preserved **0.945 → 0.964**;
  `production_valid=True`.
- Differentiators are true **by construction**, not empirical bets: determinism,
  auditability, model-agnosticism, and low cost — guarantees stochastic
  activation-steering competitors cannot offer.
- *Honesty ledger (kept, not hidden):* speculative signal tracks were
  pre-registered and **parked when they failed** (the "Resonance" signal was shown
  to be a text-difficulty confound); the validated product depends on none of
  them. Results are internal, single-model, rubric-scored; human validation and a
  head-to-head vs control-vectors benchmark are pending.

---

## 1.3 Agent Runtime — supervised digital execution  🟢

**Problem.** The last two years produced a wave of agent runtimes (LangGraph,
CrewAI, AutoGen, Bedrock Agents, Vertex, OpenAI Agents SDK). Every one reasons
differently, represents a chosen action differently, and enforces policy inside
its own framework-specific loop. Enterprises increasingly run **more than one at
once**, so governance fragments — there is no single, stable answer to *what an
agent is about to do, who authorized it, and whether it's safe*. The market
doesn't need another runtime with embedded governance; it needs **one trustworthy
execution contract** that any runtime can produce and one governance layer can
authorize.

**How we're solving it.** Instead of handing a framework's internal action object
straight to execution, the Agent Runtime converts reasoning — planning,
decomposition, memory, reflection, tool orchestration — into a **Canonical
Execution Request (CER)** as its *native* output: a runtime-independent, hashable
object carrying the intended action, normalized parameters, target, evidence,
and a deterministic content-hash identity. Because the CER is emitted natively,
there's no translation seam: what the runtime proposes is exactly what the
Control Plane authorizes. Execution is decided *outside* the runtime (ActionGate +
operational-safety clearance); the governed result returns for memory and
reflection. The runtime keeps proposal-side safeguards (validation, budgets,
human-in-the-loop, advisory risk evidence) but explicitly does **not** own
authorization or execution authority.

**Who it's for.** Enterprises that want the cleanest, most evidence-rich native
producer for a runtime-independent governance layer — and teams already on
LangGraph/OpenAI Agents who can keep those runtimes (fronted via adapters) rather
than rip-and-replace.

**Proof points.**
- **1,550+ tests** across the runtime and its primitives.
- CER proven **cross-runtime and cross-domain**: native Ugence + real LangGraph +
  real OpenAI Agents adapters produce **identical action identity** across three
  execution profiles (K8s scale, K8s rollout, DB mutation), plus an independent
  clean-room implementation reproducing **byte-identical** payloads and digests.
- Advisory-evidence signals are measured and honest: risk taxonomy AUROC ≈ 0.82,
  next-token entropy AUROC 0.857 — *advisory only; never grants authorization.*
- *Honest scope:* runtime independence is architectural interoperability shown in
  the repo — **not** a claim of market adoption; CER is a versioned interoperability
  contract, not yet an adopted industry standard.

---

## 1.4 Autonomous Runtime (BCVF Autonomy Runtime) — supervised physical execution  🟡

**Problem.** Every modern AV, drone, mobile-robot, and humanoid stack converged on
the same pattern: **multiple predictors** (HD-map prior, learned predictor,
kinematic model, redundant sensors) feeding **one planner**. When predictors
agree, planning is routine. When they *disagree* — exactly the regime where the
failures that matter live — the planner has no principled way to decide which to
trust. Today that gap is bespoke glue code, rebuilt per stack and per release,
and it's where disengagements and safety-case escalations concentrate. Classical
fusion (Kalman/EKF) was built to combine honest noisy signals, not to distrust a
silently-wrong predictor.

**How we're solving it.** A drop-in arbitration layer between the predictors and
the planner. At every planning step it detects the *shape* of disagreement,
distinguishing harmless constant-offset and linear-drift patterns from
**accelerating divergence**. Its core "Lemma 1 invariance" guarantees that
constant and linear-drift disagreement produce *exactly zero* trust signal — only
acceleration above the noise floor moves a weight. It then down-weights suspect
predictors and plans against a trust-weighted consensus, emitting a frame-by-frame
audit trace. Planner-agnostic, tunable without retraining, pure NumPy, CPU,
microseconds per tick. **It arbitrates trust — it does not replace perception,
fusion, prediction, or planning.**

**Who it's for.** Tier-1 suppliers and OEMs building AV/drone/robot/humanoid
autonomy — specifically their safety and certification teams (ISO 21448 / SOTIF,
ISO 26262, UN ECE R155). Ships with the artifacts those teams ask for first:
ROS 2 message schemas, a documented DDS QoS profile, and a CycloneDX SBOM.

**Proof points.**
- Head-to-head vs baselines: BCVF is the only arbitrator with **zero
  false-attribution** on invariant disagreements (Majority-Vote scores a
  catastrophic 16.7 on constant-bias, EKF 1.1, **BCVF 0.000**), and **8–19× faster
  per tick** (~3.7µs vs EKF ~70µs).
- Certification-grade sweep: **0% false-positive / 0% false-negative** across the
  primary grid (22 configs × 60 seeds = 1,320 cells); every per-config 95% CI
  lower bound ≥ 0.90.
- **1,117 tests passing**, CPU-only, reproducible; a SOTIF/ISO 26262 traceability
  template maps 41 artifacts to 12 standard clauses.
- *Honest scope:* no production deployment yet (synthetic + realistic-noise
  predictors; real-sensor pilot pending). Explicitly does **not** transfer to LLM
  hallucination routing (clean null, AUC ≈ 0.5), and can't alone catch a stealth
  spoof below the kernel threshold.

---

# Layer 2 — AI Control Plane

*A runtime that grades its own homework is not governed. For autonomous AI to
touch anything consequential, governance of what it says and does must be
external, deterministic, and identical across every runtime. Four distinct
responsibilities: what may **enter** a decision, what **assertions** may leave,
what **actions** may commit, and whether **execution** is safe right now.*

> **Why the runtime can't own this.** A runtime is optimized to *produce* good
> assertions and actions; governance must be willing to *reject* them,
> deterministically, under rules the runtime cannot edit at runtime. Those are
> opposing objectives — so one external control plane sits in front of **many**
> runtimes (including third-party ones via CER adapters) and gives the enterprise
> **one consistent answer**.

---

## 2.1 Context Minimization — what may enter a decision  🟢

**Problem.** Enterprise agents re-send the same authorization-bearing context —
policies, approvals, state, evidence, history — to an LLM on *every step*. As
fleets scale, this repeated context is one of the largest recurring inference
costs in enterprise AI. Existing compression cuts that cost by rewriting or
summarizing — which can silently change the authorization the context would
produce: a dropped policy clause, a "FORBID" softened to "prefer not to," a
removed payment amount. The token bill falls and a *decision moves with it*. That
forces an unacceptable choice: pay for tokens, or pay a human to check that
compression didn't flip anything.

**How we're solving it.** An **extractive** compressor that removes only the spans
a deterministic authorization gate *proves* are irrelevant. Every context is
decomposed into spans; each span is classified protected or droppable by running
the **real ActionGate over ablations** of the context; droppable spans are cut to
a token budget; then a **fail-closed invariance check** re-runs the gate and
requires a byte-identical authorization decision, restoring spans if it diverges.
It never rewrites, paraphrases, or summarizes — KEEP-or-DROP only. Because
preservation is computed by the deterministic gate, not by the downstream model,
the safety guarantee is **structural and model-portable by construction**.

**Who it's for.** Any enterprise running authorization-bearing autonomous agents —
finance, infrastructure, access agents. Horizontal middleware every such agent
passes through, not a per-workflow app.

**Proof points.**
- On the real gate: **100% decision invariance and 100% protected-span recall** at
  every budget, up to **~66% token reduction**; a protection-*unaware* baseline
  corrupts decisions in up to **~51%** of contexts where this corrupts none.
- **Cross-model replication** (`CONSISTENT_REPLICATION`) on 3 open-weight models
  (Qwen2.5-7B/14B, Mistral-7B): 100% decision preservation with **32–50% token
  reduction** and utility non-regression.
- Frozen, fingerprinted benchmarks; 135 tests (133 passing).
- *Honest status:* recommendation is **`LIMITED_GO`** — absolute downstream
  accuracy is depressed by a model-side tool-argument ceiling (repaired in a V2
  benchmark), not by the compression. Moat is the **authorization-invariance
  contract**, "a real head start, not an insurmountable moat." Pending: two more
  models, a real-data pilot, third-party audit.

---

## 2.2 Truth Assurance Platform (TAP) — what assertions may leave  🔵

**Problem.** Enterprises can generate fluent AI answers but cannot **independently
prove** an answer was supported before it reached a user, customer, or regulator —
today that judgment is usually made by the same model that produced the answer
(the system grading its own work). In consequential workflows — regulated
reporting, compliance drafting, financial analysis, clinical information — an
unsupported statement presented as fact is not a productivity issue but an
**admissibility** issue, unacceptable regardless of how rarely it occurs.

**How we're solving it.** An external, model-independent layer that inspects a
*completed* response and decides **DELIVER / QUALIFY / ABSTAIN** — without
generating text itself. Four layers: ClaimIntegrity decomposes the response
*without altering meaning* (preservation-first), ScopeIntegrity handles
exception/scope spans, EvidenceAssurance checks each claim for
support/contradiction/staleness/gaps, and AssertionGate applies a risk-aware
delivery decision — all with a replayable provenance record. Founding principle
(from a completed study): evidence assurance is trustworthy only when semantic
scope is **preserved before verification begins**.

**Who it's for.** Enterprises deploying AI in high-consequence, regulated
workflows where unsupported output is inadmissible — financial services,
healthcare, legal & compliance, insurance, government. The economics are
**deployment enablement**: turning "cannot deploy AI here" into "can deploy under
governed delivery."

**Proof points.**
- Mechanism matters by an **order of magnitude**: preservation-first splitting
  yields **0.068** unsafe delivery vs **0.864** for triple/parser extraction;
  ScopeIntegrity's ~4-rule gate cuts the residual **0.068 → 0.000**;
  EvidenceAssurance drives correlated-failure escape to **0.000** where baselines
  escape 0.67–1.00.
- Discipline as differentiator: repeatedly **rejected complexity** that didn't
  improve safety (a 15-probe engine that only tied a 2-probe splitter).
- *Honest status — this is emerging:* **all results are synthetic**, self-authored,
  with simulated stand-ins for LLMs/parsers; no human agreement, no real-customer
  data, no production efficacy. A disclosed "no-tell" ceiling failure (fabricated
  provenance) escapes 1.000. Next step is one bounded enterprise shadow
  deployment on real data; **no ROI claim is made.**

---

## 2.3 ActionGate — what actions may commit  🟢

**Problem.** It's now easy to give an LLM tools (MCP, function-calling, agent
frameworks), but there is **no unified way to bind policy, human approval, current
state, credential issuance, and execution to one exact agent-generated action.**
The industry reflex is monitoring — logging, scoring, alerting — which only tells
you what an agent *did* after the fact and holds no credential, so it cannot stop
a harmful action. The dangerous seam is between "the model emitted a tool call"
and "that exact call committed against production." Static RBAC grants a *standing
role*, not approval of one specific action, and an agent holding durable
credentials can act even when compromised.

**How we're solving it.** A deterministic decision-and-enforcement layer at the
tool boundary. Every action is reduced to a canonical envelope, hashed into a
**stable action identity**, and evaluated by a frozen state machine returning one
of six outcomes (ALLOW, ALLOW_WITH_CONSTRAINTS, SIMULATE_AND_RETRY,
REQUEST_MORE_EVIDENCE, ESCALATE_TO_HUMAN, DENY). Hard invariants are
non-compensatory — a hard failure can't be bought back by any soft score. Human
approvals are cryptographically bound to the exact action hash. Critically, **the
agent never holds a durable credential**: a single-use, narrowly scoped credential
is minted just-in-time by a broker that independently recomputes the hash, and
commit-time state re-verification closes the time-of-check/time-of-use gap — every
decision written to a tamper-evident, hash-chained audit record.

**Who it's for.** Security-conscious enterprises putting autonomous agents in
front of money, infrastructure, and customers. Strongest validated surface today:
Kubernetes / infrastructure actions against a real control plane.

**Proof points.**
- **274 tests** across five packages; isolated red-team verdict
  `ISOLATED_GATE_THESIS_SUPPORTED` — **27/27 attacks blocked, all actually
  executed** (no hard-coded passes).
- On the decisive-attack baseline, the design blocks attacks that static RBAC,
  admission-only, and time-window-JIT designs each block only **1 of**.
- The differentiated unit of authorization is an **action, not a principal** —
  "Just-Enough Authorization" (single-use), not time-window JIT.
- *Honest scope:* independent architectural validation sits at
  `SUPPORTED_WITH_LIMITATIONS` (single-host store, trusted signing root,
  pure-Python crypto); cross-domain breadth beyond Kubernetes (AWS, GitHub,
  Terraform, DBs) is roadmap; no third-party external red-team yet.

---

## 2.4 Autonomous Control Plane (ACP) — whether execution is safe *right now*  🟢

**Problem.** Even a correctly *authorized* action can be operationally unsafe at
the moment of execution — during a freeze window, under current load, with a blast
radius that's too large right now, or against drifted state. Authorization
("is this allowed?") and operational safety ("is it safe *this second*?") are
different questions, and collapsing them means an agent fleet you cannot certify,
insure, or audit — because the answer depends on which framework generated the
action.

**How we're solving it.** ACP clears an already-authorized CER against **live
operational state**. Its core is domain-neutral, with a thin deterministic
per-domain safety adapter (Kubernetes: blast radius, freeze window, readiness,
state-drift; database: reachability, affected-row bound, replication, migration
conflict, rollback-available), producing PROCEED / HOLD / REOBSERVE. Two
non-negotiable invariants hold the whole control plane together: **an ActionGate
denial is never overridden by ACP, and ACP can only *hold* — it can never mint
authorization.** An action proceeds *iff both layers pass.*

**Who it's for.** Risk, security, and compliance teams running autonomous agents
across multiple runtimes who need one consistent governance answer to certify,
insure, or audit a fleet. Governs both the native Agent Runtime and third-party
runtimes (LangGraph, OpenAI Agents) via a CER adapter, across Kubernetes and
database domains.

**Proof points.**
- **Runtime independence:** three real runtimes produce identical action identity
  for identical actuation; the control plane contains **zero runtime-specific
  tokens** (verified by a CI ownership scan).
- **Cross-domain:** a materially different domain (`database.mutation.v1`) was
  governed with **0 lines changed in ActionGate**, reusing the frozen composition
  core.
- **Independent implementability:** a clean-room CER implementation reproduces
  byte-identical digests with **0 identity-affecting ambiguities** across 77
  differential items.
- *Honest scope:* ACP runs against authored fixtures in **shadow-only** mode and
  actuates nothing (no live cluster/DB telemetry yet); a reference control plane
  with a proven contract, **not a certified production deployment.**

---

# Layer 3 — AI Infrastructure

*Reasoning and execution are expensive. Something has to make long context
affordable and make scaling decisions well — **without ever deciding what the AI
is allowed to do.** This layer owns efficiency, and only efficiency.*

---

## 3.1 KVPro — memory & inference efficiency  🟢

**Problem.** At long context (32K+), the **KV-cache — not model weights —**
dominates LLM serving cost and caps concurrency (a single 7B request at 32K can
consume ~2 GB of bf16 KV). The obvious fix, 4-bit KV, hasn't shipped *at quality*:
fp8 sacrifices accuracy on outlier-heavy models and only reaches 2× where the
market wants 4-bit, while naive int4 collapses token-agreement vs bf16 to 0.53.
The gap between **"4-bit density" and "maintained quality"** is the market — and it
binds exactly the fastest-growing segments (long-context, agentic, RAG).

**How we're solving it.** A quality-safe, post-hoc KV compressor that plugs into an
existing deployment with no retraining and no model-code changes — a one-line
vLLM backend. A ~30-second, 55-prompt calibration identifies the small fraction of
K-channels (~4%) carrying most of the attention signal and keeps them at bf16
while quantizing the rest to int4; a forked flash-attention kernel dequantizes on
the fly and splices the protected channels back, producing output bit-comparable
to bf16 per (layer, head). It's a **capacity + quality** tool, not a raw-speed
replacement — so deployment is a routing decision: send memory-bound, long-context,
high-fan-out traffic to KVPro; keep latency-critical single-stream chat on bf16.

**Who it's for.** Inference API providers, enterprise self-hosters in
quality-sensitive domains (legal/health/finance), open-model serving hubs, and
edge/low-HBM deployments — anyone where KV memory is the binding constraint.

**Proof points.**
- **Quality parity:** 4-model portfolio (Qwen/Mistral/Llama, 7–14B) hits **15/15
  needle == bf16**, academic benchmarks at **0.0-pt delta** with 100% per-question
  agreement, and **+20 pts** token-agreement over naive int4.
- **Density / cost:** **2.0× raw, ~1.8× net** KV capacity per GPU under saturation;
  modeled unit economics show **~44% fewer GPUs** for a 32K-concurrency workload
  (scaling to ~$5.3M/yr saved at 10,000 sessions), deliberately under-promised.
- **Competitive moat (measured, own hardware):** a leading denser 4-bit method
  **collapses to 0%** hard-retrieval where KVPro and bf16 hold **100%**.
- *Honest scope:* below full-precision throughput today (**~0.13–0.67×**) on an
  unoptimized path — throughput recovery is a funded v2 item with bounded upside;
  patent-pending; pre-revenue.

---

## 3.2 Cloud Scaling Controller (Autoscaling Safety Interlock) — scaling-decision quality  🟡

**Problem.** Every production autoscaler (Kubernetes HPA, KEDA, Karpenter, CAST AI)
knows *when* to add replicas but **cannot tell whether adding them fixed
anything.** When latency is bad for reasons more replicas can't fix — a saturated
downstream dependency, lock contention, a collapsed queue — the controller keeps
scaling out anyway, riding from a handful of replicas to dozens while the incident
gets *worse* and someone gets paged at 2 a.m. The feedback loop that would catch a
futile scaling decision simply doesn't exist; incumbents treat the scaling action
as correct by assumption. This "decision-quality" layer is structurally empty.

**How we're solving it.** Three **read-only, zero-write** layers beside the
autoscaler. The controller is left untouched. An EfficiencyEstimator opens a short
window after each scale-out and checks whether CPU-per-replica dropped, p99
recovered, errors fell, and new replicas are doing real work — classifying the
event **HELPING / NEUTRAL / NOT_HELPING**. A deterministic, conservative
futility guard records what it *would* have capped — only when evidence is
overwhelming (NOT_HELPING for ≥5 consecutive cycles **and** ≥20 replicas), never on
a single bad cycle, never on scale-in, resetting instantly on improvement. It runs
in shadow, reads the Prometheus you already have, and touches nothing — adoptable
with a single read-only token.

**Who it's for.** Platform/SRE teams running unattended autoscaling as a
production control loop, especially in dependency-heavy microservice environments
(queues, caches, third-party APIs, AI inference backends).

**Proof points.**
- Across simulation (19 adversarial scenarios), offline replay of a **real Azure
  inference trace**, and a real-dynamics calibration: **0 harmful false positives,
  0 SLO regressions**, and it never mislabeled a genuinely-helpful scale-out while
  catching severe futility.
- Occupies the empty "decision-quality" layer no incumbent fills; positioned as a
  read-only **control-path interlock**, not an analytics dashboard.
- **760 passing tests**; shadow / recommend modes and a live-shadow harness
  (kind + Prometheus + Chaos Mesh).
- *Honest scope:* this is a **reliability/safety** play, **not** cost-optimization
  (measured savings are "marginal" and deliberately not the pitch); no
  production/customer validation; a pre-registered kill signal is defined.

---

# Cross-cutting & adjacent modules

*Modules that either apply across the whole platform or extend it into a new
surface. Included because the investor asked for the **entire** module set.*

---

## 4.1 Model Selection & Governed Inference — a cross-cutting policy service  🟢

**Problem.** Enterprises now run many models at once — frontier APIs, private
models, small local models, specialized models — across providers, sizes, costs,
and risk levels. Today's routers optimize only for cost, latency, benchmark
quality, or uptime. They don't answer the questions a risk/compliance team has:
*Is this model permitted for this task? Does it meet the required quality
threshold or is it just cheaper? May sensitive data go to this provider? Can the
decision be audited and reproduced?* As enterprises shift from AI assistants to AI
agents, model choice stops being a scoring problem and becomes a **governance
decision** about which intelligence is allowed to reason and act.

**How we're solving it.** A layered control plane that separates four decisions
usually collapsed into one: **Capability** (can a model do the task at all?),
**Selection** (among *eligible* models, which gives best policy-defined utility?),
**Assertion governance** (is the output supported enough to deliver?), and
**Action governance** (handed to ActionGate). **Hard constraints filter *first***
— quality, privacy, deployment, risk — and optimization runs only over the
survivors, so a cheaper model can never win by trading away quality or controls. A
minimal evidence-obligation policy (~12 transparent, monotonic rules) sets what
evidence each claim type requires, and model-generated statements are barred from
verifying themselves. The full flow produces a deterministic, replayable audit
trace.

**Who it's for.** Enterprise risk/security/compliance teams running multi-model AI
in regulated domains. Phase 1 targets **non-enforcing shadow pilots** where AI
already recommends but doesn't autonomously execute (cyber ops, financial ops,
enterprise IT, support escalation, approval/refund workflows).

**Proof points.**
- Frozen evaluation passed **10/10 pre-registered criteria**: clean-allow 0% → 50%,
  over-qualification 85.5% → 0%, unsafe high-risk allows **0**, self-verification
  escapes **0 of 13**, monotonicity violations **0 of 528**.
- Beats a risk-only baseline and a richer classifier on safety — **0 vs 52 of 85**
  unsafe allows — and was deliberately *reduced* to ~12 transparent rules after the
  larger classifier failed to justify its complexity.
- *Honest status:* technical validation complete, but **real human validation not
  yet performed** — two calibration rounds were correctly *blocked* (no real
  reviewers; eligibility gate excluded a stakeholder). External pilot still gated.
- *Governance note:* this is a **cross-cutting policy service** at research
  maturity — **not** an eleventh canonical component.

---

## 4.2 Conscious Generation — the research architecture behind steering  🔵

**Problem.** The same failure the Steering Controller targets, attacked one layer
deeper: LLMs answer under the wrong meaning-frame because they don't explicitly
isolate *which* semantic domain a question lives in, the rejected-domain boundary,
or the primary-vs-secondary ranking — and every post-hoc mitigation acts *after*
the model has already committed to a distribution.

**How we're solving it.** Intervene earlier and more cheaply — at the meaning-frame,
deterministically. A `MATCH = C × R × S` engine (C and R from a deterministic
12-D phonemic profile of the term, S from embedding similarity) classifies
candidate domains as primary / secondary / weak / rejected with frozen thresholds
*before* generation; the model then answers inside the chosen frame, and an
answer-audit gate decides pass / rewrite / escalate with traceable diagnostics
(secondary-meaning promoted, rejected-domain drift, frame-label parroting, generic
escape). Behind this shippable layer sits a patent-backed research architecture
(`mistral_cg`) betting that next-token probability is better computed as the
**integrated agreement of multiple semantic fields** than a single projection —
explicitly an IP/research bet, off by default.

**Who it's for.** The productized layer is the **LLM Steering Controller** (§1.2);
this card documents the research module and its IP for completeness. The
architecture is self-hostable on open-weight substrates (Mistral/Llama/Qwen).

**Proof points.**
- Same measured internal eval as the Steering Controller (Mistral-7B, 110-item
  polysemy set): primary-frame **0.609 → 0.736**, rejected-domain **0.855 → 0.909**,
  factuality **0.945 → 0.964**.
- **Disciplined negative results** as a product boundary: a pre-registered policy
  gate from the diagnostics **did not beat** the existing audit gate (F1 0.341 vs
  0.526), so diagnostics stay explanation-only; deeper hidden-state ("Bhava")
  tracks were pre-registered and **intentionally closed as negative.**
- One retained-not-productized finding: raw pre-answer hidden states predict some
  within-model failures (frame-violation AUROC ≈ 0.76) — correlational, single-model,
  **not wired into runtime control.**
- *Honest status:* the product **does not depend** on any speculative hidden-state
  or "consciousness" claim; human validation of the audit gate is the pending step.

---

## 4.3 CTM+ / PCAM — coherence-aware memory tiering  🟡

**Problem.** Compute and memory scaled up, but the decisions about *which data
lives where* are still made by 1970s-era algorithms (LRU, FIFO) across the Linux
page cache, GPU HBM, and LLM inference servers. LRU only knows **recency** — not
workload phase structure, not whether a hot-tier move is cost-justified, not
whether "cold" data is about to be hot again, not whether evicting a token will
tank p99. At scale that's a P&L line item: a single LLM inference query costs
roughly **10× a search query**, and an enterprise at 100K queries/day quietly
spends **$1M+/year** on inference alone — plus oversized HBM buys and GPU memory
sitting at 72% instead of 89% utilization.

**How we're solving it.** Replace the single recency signal with a **coherence-aware
controller**: a phase integrator that learns access rhythm, an O(1) sub-10ns
coherence scorer, ARC-style dual shadow tiers that auto-balance recency vs
frequency, phase-aware victim selection across four orthogonal signals (recency,
frequency, attention, position) with weights that shift between LLM prefill and
decode, and a "will I regret this?" verification gate that gives SREs a safety
story to turn it on. **The same core algorithm** ships into five hot paths — Linux
kernel, GPU HBM tiering, vLLM KV-cache eviction, PostgreSQL buffer pools, DeepSpeed
ZeRO-Offload — because "which bytes go in which tier?" is structurally the same
problem everywhere. Runs as firmware/kernel module on existing hardware; FPGA/ASIC
is the long-term path, not the adoption ask.

**Who it's for.** Hyperscalers and AI-infra teams paying a fast-growing memory
bill — LLM inference serving, GPU HBM tiering, database buffer pools, training
memory. Lead use case: **fitting more concurrent inference requests onto the same
silicon.**

**Proof points.**
- **LLM inference (vLLM):** +18% tokens/sec, **+50% concurrent requests on the same
  GPU (32 → 48)**, GPU memory efficiency 72% → 89%.
- **Database (TPC-C style):** transactions/sec +13.6%, p99 −29%; hit-rate up to
  **+17.8%** on hotspot/batch-ML workloads.
- **5-year TCO:** $1.84M (31%) saved on a 100-GPU cluster, ~$5.19M/yr at 1,000 GPUs.
  Working today across simulator, kernel module, CUDA, and vLLM + DeepSpeed, with a
  bit-parity PCAM runtime (276 tests green).
- *Honest scope:* on generic synthetic traces with no semantic structure, CTM+
  **matches LRU and slightly loses to ARC** — the expected result, since it's built
  to exploit phase structure. FPGA prototype and a live single-GPU throughput run
  are the next milestones.

---

## 4.4 PSE — deterministic engine for naming & verbal identity  🔵

**Problem.** Every product, company, feature — and now every AI agent — needs names
and verbal identity, but that work happens in chatbots and spreadsheets:
non-reproducible, unconstrained, unaudited, and blind to whether a name is even
**available**. The toolchain fails three ways: no control (you can't specify
"grounded then opening, four syllables, no harsh onsets" and get reproducible
results), no explanation (no inspectable rationale for legal/brand sign-off), and
no memory (nothing measures how forms land and feeds it back). As AI commoditizes
the *writing* of names, durable value moves to what models structurally can't
provide — determinism, guaranteed availability, governance, and compounding
outcome data.

**How we're solving it.** An intermediate representation / DSL for sound-form design
on three pillars: **deterministic symbolic control** (parse any word into a
structured "trajectory" via a frozen, versioned engine, and *invert* it — specify
constraints, get forms that satisfy them, checked against real
trademark/domain/handle availability); **AI-assisted authoring** (render a profile
into on-brand prose over the deterministic scaffold, under a hard honesty filter,
never improvised); and **observation-driven improvement** (log every generated form
and human reaction into an observation graph reporting *measured associations* with
confidence). The keystone is a neutral, versioned **Trajectory Schema** everything
depends on — so the symbolic vocabulary can be improved or replaced without
touching APIs, SDK, or customer integrations.

**Who it's for.** Brand and product teams, agencies, and increasingly **AI-agent
platforms** that must name and brand at machine scale via API. Wedge: governed
brand/product naming + sonic branding (a budgeted, sign-off-heavy spend);
expansion into agent identities, voice/speech design, and accessibility/TTS.

**Proof points.**
- Uniquely offers, vs prompting/LLMs and embeddings: **deterministic reproducible
  outputs, hard-constraint satisfaction, an explainable audit trail, editable
  symbolic control, and inverse design** — and composes with those approaches
  rather than competing.
- Moat ranked honestly: (1) the proprietary, model-independent **observation
  graph** (the only true data-network-effect moat); (2) governance/reproducibility
  with on-prem outputs; (3) availability-grounded constraint engine. Explicitly
  *not* moats: the AI renderer and the SDK.
- *Honesty section:* **no intrinsic sound meaning is claimed**, the vocabulary is
  engineered/editable (not a scientifically-validated ontology), and observations
  are "measured associations," never universal truths.
- *Honest status:* the deterministic engine and architecture are specified/working;
  the commercial surfaces (studio UI, observation platform, enterprise APIs) are
  the build ahead. Seed-to-A stage.

---

# Summary — module map at a glance

| # | Module | Layer | The one problem it kills | Status |
|---|--------|-------|--------------------------|--------|
| 1.1 | **Hybrid LLM** | Specialized AI | One probabilistic call doing four jobs → reliability breaks | 🟢 |
| 1.2 | **LLM Steering Controller** | Specialized AI | Models answer under the wrong frame, non-reproducibly | 🟡 |
| 1.3 | **Agent Runtime** | Specialized AI | Every runtime represents actions differently → no common governance | 🟢 |
| 1.4 | **Autonomous Runtime (BCVF)** | Specialized AI | Predictors disagree; planner can't tell which to trust | 🟡 |
| 2.1 | **Context Minimization** | Control Plane | Compressing agent context silently flips authorization decisions | 🟢 |
| 2.2 | **Truth Assurance Platform** | Control Plane | No independent proof an answer was supported before delivery | 🔵 |
| 2.3 | **ActionGate** | Control Plane | Nothing binds policy + approval + credential to one exact action | 🟢 |
| 2.4 | **Autonomous Control Plane** | Control Plane | Authorized ≠ safe *right now* against live state | 🟢 |
| 3.1 | **KVPro** | Infrastructure | 4-bit KV-cache density without losing answer quality | 🟢 |
| 3.2 | **Cloud Scaling Controller** | Infrastructure | Autoscalers can't tell if scaling out actually helped | 🟡 |
| 4.1 | **Model Selection & Governed Inference** | Cross-cutting | Routers optimize cost, not "is this model *permitted*?" | 🟢 |
| 4.2 | **Conscious Generation** | Research | Meaning-frame control, one layer deeper (steering's IP) | 🔵 |
| 4.3 | **CTM+ / PCAM** | Adjacent (memory) | 1970s cache algorithms waste modern AI memory | 🟡 |
| 4.4 | **PSE** | Adjacent (naming) | Naming/verbal identity is unreproducible and unaudited | 🔵 |

**The through-line for the investor:** these are not fourteen unrelated tools.
The runtimes *propose*, the control plane *governs the exact assertion and
action*, and the infrastructure *runs it efficiently* — a single governed loop in
which, at any point, you can name which module is responsible. A competitor
cloning one box inherits none of the compounding, because the value is in the
**governed loop**, not any single component.

*Sources: the per-module VC briefs in this repository (`*_VC_BRIEF.md`) and
`UGENCE_PLATFORM_OVERVIEW.md`. All metrics are from our own repositories/CI on
synthetic or internal corpora unless a card states otherwise; production and
third-party validation are, in most cases, the funded next step — not a current
claim.*
