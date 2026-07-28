# Ugence Labs / Symbolu — Evidence-Led Problem Catalogue

**State the problem confidently. State the mechanism precisely. State the
evidence conservatively. State the pilot objective measurably.**

*Prepared for investor review. This is not a product brochure — it is an
evidence-led catalogue. Every capability is presented as a problem it attacks, a
specific mechanism, the evidence that actually exists today, an honest conclusion
about what can be claimed, and the measurable objective a customer pilot must
prove.*

---

## How to read this document

Ugence has **implemented and internally evaluated** a portfolio of governance and
efficiency capabilities spanning assertion reliability, evidence integrity, human
authority, decision accountability, and execution control. Most modules today
carry strong **software proof** and early **controlled evidence**. The next stage
is **bounded enterprise shadow pilots** to establish operational effectiveness,
false-positive rates, integration cost, and measurable business impact.

### Two questions every card separates

| Has the mechanism been built correctly? | Does it create customer value? |
|---|---|
| Tests · interface contracts · invariants · failure injection · deterministic replay · benchmarks | Reduced manual review · fewer unsupported assertions · more violations detected · faster audit reconstruction · lower incident rate · faster agent deployment |
| **Where most modules are today (software proof)** | **What the pilots are designed to prove (business proof)** |

### Maturity taxonomy (a module may carry several labels)

| Label | Meaning |
|---|---|
| **Implemented** | Capability exists and passes code-level or integration tests |
| **Internally Validated** | Tested on synthetic, benchmark, or internal data |
| **Pilot Ready** | Packaged sufficiently for customer shadow-mode evaluation |
| **Pilot Validated** | Demonstrated in a bounded customer environment |
| **Production Validated** | Operating successfully in a live customer workflow |
| **Research** | Hypothesis, prototype, or experimental capability |

> **Evidence honesty.** Unless a card says otherwise, all metrics are from our own
> repositories and CI, on synthetic or internally-authored corpora — not
> third-party benchmarks and not production deployments. No module below is
> currently **Pilot Validated** or **Production Validated**. That gap is the ask,
> not a hidden weakness.

---

## Portfolio at a glance — problem area × evidence stage

| Problem area | Modules | Furthest evidence stage today |
|---|---|---|
| **Assertion reliability** | Hybrid LLM, Truth Assurance Platform | Internally Validated (synthetic) |
| **Evidence & provenance** | Truth Assurance Platform, Decision Governance | Implemented · Internally Validated |
| **Decision authority & accountability** | Decision Governance Middleware | Implemented · Internally Validated |
| **Execution authorization** | ActionGate, Autonomous Control Plane | Implemented · Internally Validated · Pilot Ready (ActionGate) |
| **Context & inference efficiency** | Context Minimization, KVPro | Internally Validated (real GPUs / cross-model) |
| **Runtime orchestration** | Agent Runtime, Autonomous Runtime, LLM Steering Controller | Implemented · Internally Validated · Pilot Ready |
| **Infrastructure efficiency** | KVPro, Cloud Scaling Controller, CTM+/PCAM | Internally Validated (+ hardware Research) |
| **Model governance (cross-cutting)** | Model Selection & Governed Inference | Implemented · Internally Validated |
| **Advanced intelligence research** | Conscious Generation, CTM+/PCAM hardware, PSE | Research + partial Implemented |

**Flagship shadow-mode pilot:** *AI-Assisted Hiring* (see final section) — the
origin domain that proved the Decision Governance model and now consumes it as
one validated application.

---

# Layer 1 — Specialized AI Systems *(reason · steer · execute — proposes; never authorizes itself)*

---

## 1.1 Hybrid LLM
**Implemented · Internally Validated**

**Problem.** In most agentic stacks a single language model is trusted, in one
probabilistic loop, to interpret evidence, admit facts, decide, and trigger
actions — collapsing four distinct duties into one generative call. This is where
enterprise reliability breaks: a "request" is read as an "approval," a stale
policy looks current, or an agent authorizes its own action. These are
separation-of-duties failures, not problems a bigger model fixes.

**Ugence mechanism.** Hybrid LLM computes what is knowable *exactly* with
deterministic parsing and confines the model to the few genuinely semantic fields
where it may only *propose* provenance-linked, span-verified records. Model output
becomes provisional evidence that must be validated before it is trusted; an
assertion-governance layer independently checks each explanation against evidence
and hard authority ceilings before decision governance and ActionGate act.

**Current evidence.** On a synthetic procurement corpus: **0.00 unsupported-fact
admission** at every simulated interpreter-quality level (ungoverned baseline
0.35 / 17.7%); assertion governance **100% recall** on unsupported/authority-
exceeding claims at 1.00 supported precision (vs 0.00 for prompt-only grounding);
deterministic field computation lifts outcome correctness **0.64 → 1.00** and
conflict F1 **0.26 → 1.00**.

**Evidence basis.** Code tests + synthetic, controlled corpus using a **simulated
interpreter, not a live model**.

**Honest conclusion.** The separation-of-duties architecture is built and,
under controlled conditions, admits zero unsupported facts where an ungoverned
baseline admits many. Live-model interpretation and generalization beyond the
synthetic corpus are not yet established.

**Next validation step.** Run the pipeline with a live model on real
system-of-record data and measure unsupported-fact admission, outcome correctness,
and reviewer agreement against the deterministic baseline.

---

## 1.2 LLM Steering Controller
**Implemented · Internally Validated**

**Problem.** LLMs often fail not because they write badly but because they answer
under the **wrong meaning-frame** — promoting a secondary reading, drifting into
an adjacent domain, or padding with generic text. Post-hoc fixes (RLHF, retrieval,
moderation) act only after the model has committed and are stochastic, so behavior
can't be reproduced, tested, or audited — a governance problem, not just quality.

**Ugence mechanism.** A deterministic, model-agnostic layer that fixes the frame
*before* generation: a rule-based C×R×S engine matches input to a frame
(primary/secondary/weak/rejected) using frozen thresholds so the same input always
yields the same frame; the answer is generated inside it; a deterministic audit
gate then passes, rewrites, or escalates, emitting a logged reason for every
decision. No weight changes, no retraining.

**Current evidence.** Internal eval (Mistral-7B-Instruct-v0.3, 110-item polysemy
set, deterministic rubric): primary-frame correctness **0.609 → 0.736**,
rejected-domain avoidance **0.855 → 0.909**, factuality preserved
**0.945 → 0.964**.

**Evidence basis.** Code tests + single-model, single-set internal rubric scoring
(not human-rated, not cross-model).

**Honest conclusion.** The controller demonstrated deterministic frame correction
with improved framing and preserved factuality on one open model under a fixed
rubric. Its differentiators — determinism, auditability, model-agnosticism — are
true *by construction*; its measured quality gains are single-model and not yet
human-validated.

**Next validation step.** Human-rated evaluation across multiple model families,
plus a head-to-head against learned control-vector steering on a shared task.

---

## 1.3 Agent Runtime
**Implemented · Internally Validated · Pilot Ready**

**Problem.** Enterprises increasingly run several agent runtimes at once
(LangGraph, CrewAI, AutoGen, Bedrock, Vertex, OpenAI Agents), each representing a
chosen action differently and enforcing policy inside its own loop. Governance
fragments — there is no single, stable answer to *what an agent is about to do,
who authorized it, and whether it is safe.*

**Ugence mechanism.** The runtime converts reasoning — planning, decomposition,
memory, reflection, tool use — into a **Canonical Execution Request (CER)** as its
native output: a runtime-independent, hashable object with a deterministic
content-hash identity. Because the CER is emitted natively there is no translation
seam; execution is decided *outside* the runtime by the control plane, and the
governed result returns for memory and reflection.

**Current evidence.** **1,550+ tests**; CER identity proven **cross-runtime and
cross-domain** — native Ugence + real LangGraph + real OpenAI Agents adapters
produce identical action identity across three execution profiles, plus a
clean-room implementation reproducing byte-identical digests. Advisory-evidence
signals are measured (risk taxonomy AUROC ≈ 0.82; next-token entropy AUROC 0.857)
and used only to *raise scrutiny*, never to authorize; a related internal-signal
pilot (N=30) moved AUROC from **0.893 → 0.916, which was not statistically
significant** (p=0.183) — reported as an honest negative, not a headline.

**Evidence basis.** Code tests + synthetic cross-runtime/cross-domain corpora +
clean-room differential conformance.

**Honest conclusion.** A runtime-independent execution contract is built and
demonstrated to produce identical, independently-reproducible action identities
across three real runtimes. "Runtime independence" here is demonstrated
interoperability in the repo — **not** a claim of market adoption, and the CER is
not yet an adopted industry standard.

**Next validation step.** A customer running two runtimes in parallel, proving one
governance decision applies identically to both, with audit reconstruction across
runtimes.

---

## 1.4 Autonomous Runtime (BCVF Autonomy Runtime)
**Implemented · Internally Validated · Pilot Ready**

**Problem.** Modern AV, drone, robot, and humanoid stacks all feed **multiple
predictors into one planner**. When predictors disagree — exactly where the
failures that matter live — the planner has no principled way to decide which to
trust. Today that gap is bespoke glue code, rebuilt per stack, and it is where
disengagements and safety-case escalations concentrate.

**Ugence mechanism.** A drop-in arbitration layer that, at each planning step,
detects the *shape* of predictor disagreement — distinguishing harmless
constant-offset and linear-drift from **accelerating divergence** — under a stated
invariance (constant and linear-drift disagreement produce exactly zero trust
signal; only acceleration above the noise floor moves a weight). It down-weights
suspect predictors, plans against a trust-weighted consensus, and emits a
frame-by-frame audit trace.

**Current evidence.** Vs baselines, the only arbitrator with **zero
false-attribution** on invariant disagreements (BCVF 0.000 where Majority-Vote
scores a catastrophic 16.7, EKF 1.1) and **8–19× faster per tick** (~3.7µs);
certification-grade sweep **0% false-positive / 0% false-negative** across 1,320
cells (22 configs × 60 seeds), every per-config 95% CI lower bound ≥ 0.90;
**1,117 tests passing**, CPU-only; a SOTIF/ISO 26262 traceability template maps
41 artifacts to 12 standard clauses. Ships ROS 2 schemas, a DDS QoS profile, and a
CycloneDX SBOM.

**Evidence basis.** Code tests + synthetic and realistic-noise predictor
scenarios; no real-sensor data yet.

**Honest conclusion.** The arbitration mechanism demonstrated zero false-
attribution and certification-grade characterization on synthetic and
realistic-noise scenarios, with the safety-case artifacts a Tier-1/OEM asks for.
It has no production deployment; it explicitly does **not** transfer to LLM
hallucination routing (clean null, AUC ≈ 0.5); and it cannot alone catch a stealth
spoof below the kernel threshold.

**Next validation step.** A real-sensor pilot on a Tier-1/OEM stack measuring
false-attribution, disengagement reduction, and per-tick latency against the
program's existing arbitration glue.

---

# Layer 2 — AI Control Plane *(govern the interaction boundary — external, deterministic, identical across runtimes)*

> **Why governance is external.** A runtime is optimized to *produce* good
> assertions and actions; governance must be willing to *reject* them,
> deterministically, under rules the runtime cannot edit at runtime. Those are
> opposing objectives — so one external control plane sits in front of many
> runtimes and gives the enterprise one consistent answer.

---

## 2.1 Context Minimization
**Implemented · Internally Validated**

**Problem.** Enterprise agents re-send the same authorization-bearing context —
policies, approvals, state, evidence — to an LLM on every step, making repeated
context one of the largest recurring inference costs at fleet scale. Compressing it
by summarizing can silently change the authorization the context would produce (a
dropped clause, a softened "FORBID," a removed amount) — the token bill falls and a
decision moves with it.

**Ugence mechanism.** An **extractive** compressor that removes only spans a
deterministic authorization gate *proves* are irrelevant: each span is classified
by running the real ActionGate over ablations of the context; droppable spans are
cut to a budget; then a **fail-closed invariance check** re-runs the gate and
requires a byte-identical authorization decision, restoring spans if it diverges.
It never rewrites or summarizes — keep-or-drop only — so the guarantee is
structural and model-portable.

**Current evidence.** On the real gate: **100% decision invariance and 100%
protected-span recall** at every budget, up to ~66% token reduction (a
protection-unaware baseline corrupts up to ~51% of decisions where this corrupts
none). **Cross-model replication** (`CONSISTENT_REPLICATION`) on 3 open-weight
models (Qwen2.5-7B/14B, Mistral-7B) with **32–50% token reduction** and utility
non-regression; 135 tests (133 passing).

**Evidence basis.** Code tests + frozen, fingerprinted cross-model benchmarks
(synthetic/naturalistic corpus).

**Honest conclusion.** The compressor demonstrated authorization-preserving token
reduction with 100% decision invariance across three real models under a frozen
benchmark. Recommendation is **`LIMITED_GO`**: absolute downstream accuracy is
depressed by a model-side tool-argument ceiling (repaired in a V2 benchmark), not
by the compression; the moat is the invariance contract, "a real head start, not
an insurmountable moat."

**Next validation step.** Two more model families and a real-customer-data pilot
measuring token cost saved, decision-preservation rate, and any human-review
reduction — plus a third-party audit.

---

## 2.2 Truth Assurance Platform (TAP)
**Internally Validated (synthetic) · Research (emerging)**

**Problem.** Enterprises can generate fluent AI answers but cannot **independently
prove** an answer was supported before it reached a user, customer, or regulator —
today that judgment is usually made by the same model that produced the answer. In
regulated, high-consequence workflows, an unsupported statement presented as fact
is an admissibility problem, not a productivity one.

**Ugence mechanism.** An external, model-independent layer that inspects a
*completed* response and decides **DELIVER / QUALIFY / ABSTAIN** without generating
text: ClaimIntegrity decomposes the response without altering meaning,
ScopeIntegrity handles exception/scope spans, EvidenceAssurance checks each claim
for support/contradiction/staleness/gaps, and AssertionGate applies a risk-aware
delivery decision — all with a replayable provenance record.

**Current evidence.** Mechanism-level synthetic results (preregistered,
hash-pinned): preservation-first splitting yields **0.068** unsafe delivery vs
**0.864** for parser extraction; a ~4-rule scope gate cuts the residual
**0.068 → 0.000**; EvidenceAssurance drives correlated-failure escape to **0.000**
where baselines escape 0.67–1.00. A disclosed "no-tell" ceiling failure
(fabricated provenance) still escapes 1.000.

**Evidence basis.** Code tests + **synthetic, self-authored corpora with simulated
stand-ins** for LLMs/parsers. No human agreement, no real-customer data.

**Honest conclusion.** TAP is designed to detect unsupported or inadequately-
evidenced assertions before release, and its mechanism choices move the safety
endpoint by an order of magnitude in synthetic testing. It is an **emerging**
capability: architecture specified, one layer prototyped on synthetic data;
production efficacy is not established and no ROI is claimed.

**Next validation step.** One bounded enterprise shadow deployment on real data
measuring unsafe-delivery rate, QUALIFY/ABSTAIN precision, and human-reviewer load
concentrated on flagged outputs.

---

## 2.3 ActionGate
**Implemented · Internally Validated · Pilot Ready**

**Problem.** It is easy to give an LLM tools, but there is no unified way to bind
policy, human approval, current state, credential issuance, and execution to **one
exact agent-generated action.** Monitoring only reports what an agent *did* after
the fact and holds no credential, so it cannot stop a harmful action; static RBAC
grants a standing role, not approval of one specific action.

**Ugence mechanism.** A deterministic decision-and-enforcement layer at the tool
boundary. Every action is reduced to a canonical envelope, hashed into a stable
identity, and evaluated by a frozen state machine returning one of six outcomes
(ALLOW … ESCALATE_TO_HUMAN … DENY). Hard invariants are non-compensatory; human
approvals are cryptographically bound to the exact action hash; the agent never
holds a durable credential — a single-use, narrowly-scoped credential is minted
just-in-time, with commit-time state re-verification closing the time-of-check/
time-of-use gap, all written to a tamper-evident, hash-chained record.

**Current evidence.** **274 dedicated tests** across five packages
(123+39+43+30+39); isolated red-team verdict `ISOLATED_GATE_THESIS_SUPPORTED` —
**27/27 attacks blocked, all actually executed** (no hard-coded passes). On the
decisive-attack baseline the design blocks attacks that static RBAC,
admission-only, and time-window-JIT each block only **1 of**. Strongest validated
surface: Kubernetes/infrastructure actions against a real control plane.

**Evidence basis.** Code tests + isolated mechanical red-team (attacks executed,
not asserted) on synthetic/internal scenarios.

**Honest conclusion.** ActionGate demonstrated the ability to identify and block
unauthorized or policy-conflicting actions in controlled scenarios, with an
authorization unit that is an *action, not a principal* ("Just-Enough
Authorization"). It does not yet establish production risk reduction; independent
architectural validation sits at `SUPPORTED_WITH_LIMITATIONS` (single-host store,
trusted signing root, pure-Python crypto), and cross-domain breadth beyond
Kubernetes is roadmap.

**Next validation step.** Shadow mode against a live enterprise agent, measuring
unauthorized-action detection, false blocks, human-escalation rate, latency, and
policy-owner agreement.

---

## 2.4 Autonomous Control Plane (ACP)
**Implemented · Internally Validated**

**Problem.** Even a correctly *authorized* action can be operationally unsafe at
the moment of execution — during a freeze window, under current load, with too
large a blast radius, or against drifted state. "Is it allowed?" and "is it safe
right now?" are different questions; collapsing them yields a fleet you cannot
certify, insure, or audit.

**Ugence mechanism.** ACP clears an already-authorized CER against **live
operational state**. A domain-neutral core plus a thin deterministic per-domain
safety adapter (Kubernetes: blast radius, freeze window, readiness, state-drift;
database: reachability, row-bound, replication, migration conflict,
rollback-available) returns PROCEED / HOLD / REOBSERVE. Two invariants hold the
plane together: an ActionGate denial is never overridden, and **ACP can only
*hold* — it can never mint authorization** — so an action proceeds iff both pass.

**Current evidence.** Runtime independence: three real runtimes produce identical
action identity; the control plane contains **zero runtime-specific tokens**
(CI-verified). Cross-domain: `database.mutation.v1` governed with **0 lines
changed in ActionGate**. Independent implementability: a clean-room CER
implementation reproduces byte-identical digests with **0 identity-affecting
ambiguities** across 77 differential items.

**Evidence basis.** Code tests + clean-room differential conformance; ACP runs
against authored fixtures in **shadow-only** mode and actuates nothing.

**Honest conclusion.** The operational-safety-clearance mechanism is built,
runtime-independent, and cross-domain, verified against fixtures. It has no live
cluster/database telemetry yet — a reference control plane with a proven contract,
not a certified production deployment.

**Next validation step.** Live telemetry from a real cluster/database measuring
correct HOLDs on genuinely unsafe windows, false holds, and clearance latency.

---

## 2.5 Decision Governance Middleware
**Implemented · Internally Validated** *(Research: automated semantic mapping, proxy-attribute detection)*

**Problem.** Enterprises are wiring AI into consequential decisions (hiring,
lending, claims, clinical review, procurement), but a single such decision is
produced by a pipeline of models, retrieval, rules, APIs, and human reviewers — so
no single model-reasoning trace can explain or make an organization accountable for
it. Recommendations silently become decisions, prohibited information leaks into
evaluations, and a regulator or appeal cannot reconstruct which evidence was
admitted, which policy version applied, who held authority, and what executed.

**Ugence mechanism.** A model-independent control layer governing the decision
*case* lifecycle, enforced through architecture invariants: **recommendation
(advisory, `actor_type = AI`) is type-level separated from binding decision
(`actor_type = HUMAN`)** — a `Decision` authored by an AI/service principal is
unrepresentable and audited as a security violation. It distinguishes *available*
information from *admissible* evidence (admissibility states plus quarantine that
withholds prohibited fields and audits them **by count, never by value**), pins
immutable versioned rubric contracts with segregation of duties, and keeps
assessment / recommendation / decision / execution as four independent append-only
records.

**Current evidence.** In Phase 5A the domain-neutral chain was extracted into a
reusable, version-frozen kernel (`decision_governance/`, `__version__ = 1.0.0`,
two independent domains depending on it). Extraction is **identity-preserving** —
byte-identical decision hashes pinned in tests (517 baseline → 528 after
extraction, no existing assertion modified). The AI-Hiring reference application
that originated the model passes its full suite (**413/413** at the Phase-4A
snapshot; **553/553** at terminal freeze). *(Note: 55 = new tests added in Phase 4A
within AI-Hiring, 413 = the AI-Hiring module suite total at that snapshot — not
kernel-dedicated counts; the kernel's own dedicated tests are 6 files / 29
functions.)*

**Evidence basis.** Code tests (deterministic unit/contract/boundary) + synthetic
walkthroughs (e.g. prohibited-field quarantine). No internal corpus, benchmark,
shadow pilot, or production usage claimed.

**Honest conclusion.** Decision Governance provides the records, authority
controls, and review workflow required to make AI-assisted decisions traceable and
governable — built and tested for one domain, refactored into a domain-neutral,
version-frozen kernel with a second domain already depending on it. The
decision→action→execution linkage to the live control plane (ActionGate/ACP) is
**specified but not yet built end-to-end**; the module provides controls that *may
support* compliance — it does not ensure compliance or assert bias-freedom.

**Next validation step.** Prove the chain end-to-end on a real system of record —
close the decision→CER→ActionGate/ACP→execution→reconciliation loop, reuse the
kernel unchanged in a second non-hiring domain, and test the quarantine/no-AI-
binding guarantees against messy real data. *(Flagship pilot below.)*

---

# Layer 3 — AI Infrastructure *(run it efficiently — never governs)*

---

## 3.1 KVPro
**Implemented · Internally Validated**

**Problem.** At long context (32K+), the **KV-cache — not model weights —**
dominates LLM serving cost and caps concurrency. The obvious fix, 4-bit KV, hasn't
shipped *at quality*: fp8 sacrifices accuracy on outlier-heavy models and only
reaches 2×, while naive int4 collapses token-agreement vs bf16 to 0.53. The gap
between "4-bit density" and "maintained quality" binds exactly the fastest-growing
segments (long-context, agentic, RAG).

**Ugence mechanism.** A quality-safe, post-hoc KV compressor — a one-line vLLM
backend, no retraining. A ~30-second calibration identifies the ~4% of K-channels
carrying most of the attention signal and keeps them at bf16 while quantizing the
rest to int4; a forked flash-attention kernel dequantizes on the fly and splices
protected channels back, producing output bit-comparable to bf16 per (layer,
head). Positioned as a **capacity + quality** tool, deployed by routing memory-
bound long-context traffic to KVPro and latency-critical chat to bf16.

**Current evidence.** Demonstrated **~2.0× raw / ~1.8× net KV density** on real
H100/A100 GPUs; **15/15 needle == bf16** across a 4-model portfolio (Qwen/Mistral/
Llama, 7–14B), academic benchmarks at **0.0-pt delta** with 100% per-question
agreement, **+20 pts** token-agreement over naive int4. A leading denser 4-bit
method **collapses to 0%** hard-retrieval where KVPro and bf16 hold 100%.

**Evidence basis.** Benchmarks measured on **real GPU hardware** (own hardware, not
third-party) + code tests.

**Honest conclusion.** KVPro demonstrated ~2.0× raw / ~1.8× net density with
quality preservation that **varies by model and workload**, on real hardware.
Trade-off stated plainly: decode is throughput-negative (**~0.13–0.67× bf16**) on
the current unoptimized path — throughput recovery is a funded v2 item with bounded
upside; patent-pending; pre-revenue.

**Next validation step.** A serving-provider pilot measuring GPUs saved per
concurrency target, quality parity on that provider's own traffic, and net
throughput after v2 optimization.

---

## 3.2 Cloud Scaling Controller (Autoscaling Safety Interlock)
**Implemented · Internally Validated · Pilot Ready**

**Problem.** Every production autoscaler (HPA, KEDA, Karpenter, CAST AI) knows
*when* to add replicas but cannot tell whether adding them **fixed anything.** When
latency is bad for reasons more replicas can't fix — a saturated dependency, lock
contention, a collapsed queue — the controller keeps scaling out while the incident
gets worse. The feedback loop that would catch a futile decision doesn't exist.

**Ugence mechanism.** Three **read-only, zero-write** layers beside the autoscaler.
The controller is untouched. An EfficiencyEstimator opens a short window after each
scale-out and classifies it **HELPING / NEUTRAL / NOT_HELPING** (did CPU-per-replica
drop, p99 recover, errors fall, new replicas do real work?). A conservative
futility guard records what it *would* have capped — only on overwhelming evidence
(NOT_HELPING ≥5 cycles **and** ≥20 replicas), never on one bad cycle, resetting on
improvement. Reads existing Prometheus; adoptable with one read-only token.

**Current evidence.** Across simulation (19 adversarial scenarios), offline replay
of a **real Azure inference trace**, and a real-dynamics calibration: **0 harmful
false positives, 0 SLO regressions**, never mislabeled a genuinely-helpful
scale-out, while catching severe futility. **760 passing tests**; shadow/recommend
modes and a live-shadow harness (kind + Prometheus + Chaos Mesh).

**Evidence basis.** Code tests + simulation + offline replay of a real production
trace; no live-cluster deployment yet.

**Honest conclusion.** The interlock demonstrated zero harmful false positives and
correct futility detection across simulation and a real trace replay. It is a
reliability/safety play, **not** cost-optimization (measured savings are marginal
and deliberately not the pitch); no production/customer validation, and a
pre-registered kill signal is defined.

**Next validation step.** A shadow deployment on live clusters accumulating
cluster-months to establish a sustained zero-false-positive record and count
genuine futile-runaway episodes caught.

---

# Cross-cutting & adjacent modules

---

## 4.1 Model Selection & Governed Inference
**Implemented · Internally Validated** *(cross-cutting policy service, research maturity)*

**Problem.** Enterprises run many models at once across providers, sizes, costs,
and risk levels. Today's routers optimize only for cost, latency, benchmark
quality, or uptime — not *is this model permitted for this task, does it meet the
required quality threshold, may sensitive data go to this provider, can the
decision be audited?* As enterprises shift from assistants to agents, model choice
becomes a governance decision.

**Ugence mechanism.** A layered control plane separating four decisions usually
collapsed into one — Capability, Selection (among *eligible* models), Assertion
governance, and Action governance (to ActionGate). **Hard constraints filter
first**; optimization runs only over survivors, so a cheaper model can't win by
trading away quality or controls. A minimal evidence-obligation policy (~12
transparent, monotonic rules) sets what evidence each claim type requires, and
model-generated statements can't verify themselves.

**Current evidence.** Frozen evaluation passed **10/10 pre-registered criteria**:
over-qualification 85.5% → 0%, unsafe high-risk allows **0**, self-verification
escapes **0 of 13**, monotonicity violations **0 of 528**. Beats a risk-only
baseline and a richer classifier on safety — **0 vs 52 of 85** unsafe allows — and
was deliberately reduced to ~12 rules after the larger classifier failed to justify
its complexity.

**Evidence basis.** Code tests + frozen synthetic evaluation.

**Honest conclusion.** The governed-selection architecture is built and passes its
pre-registered safety criteria in synthetic evaluation. **Real human validation is
not yet performed** — two calibration rounds were correctly *blocked* (no real
reviewers; eligibility gate excluded a stakeholder). It is a cross-cutting policy
service at research maturity, not an eleventh canonical component.

**Next validation step.** A shadow pilot with real reviewers (cyber/financial/IT
ops) measuring selection agreement, unsafe-allow rate, and reviewer trust.

---

## 4.2 Conscious Generation
**Implemented · Internally Validated · Research**

**Problem.** The same wrong-meaning-frame failure the Steering Controller targets,
one layer deeper: LLMs don't explicitly isolate which semantic domain a question
lives in, the rejected-domain boundary, or the primary-vs-secondary ranking, and
every post-hoc mitigation acts after the model has already committed.

**Ugence mechanism.** Intervene at the meaning-frame, deterministically: a
`MATCH = C × R × S` engine classifies candidate domains before generation; the
model answers inside the chosen frame; an audit gate decides pass/rewrite/escalate
with traceable diagnostics. Behind the shippable layer sits a patent-backed
research architecture (`mistral_cg`) betting that next-token probability is better
computed as the integrated agreement of multiple semantic fields — an IP/research
bet, off by default.

**Current evidence.** Same measured internal eval as the Steering Controller
(Mistral-7B, 110-item set): primary-frame **0.609 → 0.736**, rejected-domain
**0.855 → 0.909**. **Disciplined negatives** as product boundary: a pre-registered
policy gate **did not beat** the audit gate (F1 0.341 vs 0.526), so diagnostics stay
explanation-only; deeper hidden-state ("Bhava") tracks were pre-registered and
**intentionally closed as negative**.

**Evidence basis.** Code tests + single-model internal rubric; research tracks
pre-registered.

**Honest conclusion.** The shippable layer works and matches the Steering
Controller's results; the deeper architecture is an explicit research/IP bet that
the **product does not depend on**. Retained-not-productized finding: raw
pre-answer hidden states predict some within-model failures (AUROC ≈ 0.76) —
correlational, single-model, not wired into runtime control.

**Next validation step.** Human validation of the audit gate (a de-biased labeling
packet exists); the research architecture remains a longer-horizon bet.

---

## 4.3 CTM+ / PCAM
**Implemented · Internally Validated · Research (hardware)**

**Problem.** Compute and memory scaled up, but which data lives where is still
decided by 1970s-era algorithms (LRU, FIFO) across the Linux page cache, GPU HBM,
and LLM inference servers. LRU knows only recency — not workload phase structure,
not whether a hot-tier move is cost-justified, not whether evicting a token will
tank p99. At scale that is a direct memory-bill line item.

**Ugence mechanism.** Replace the single recency signal with a coherence-aware
controller (phase integrator, O(1) sub-10ns scorer, ARC-style dual shadow tiers,
phase-aware victim selection across recency/frequency/attention/position, and a
"will I regret this?" gate). The **same core algorithm** ships into five hot paths
— Linux kernel, GPU HBM tiering, vLLM KV-cache eviction, PostgreSQL buffer pools,
DeepSpeed ZeRO-Offload — because "which bytes go in which tier?" is structurally the
same problem everywhere.

**Current evidence.** vLLM: +18% tokens/sec, **+50% concurrent requests on the same
GPU (32 → 48)**, memory efficiency 72% → 89%. Database (TPC-C style):
transactions/sec +13.6%, p99 −29%, hit-rate up to **+17.8%** on hotspot/batch-ML.
Modeled 5-year TCO: $1.84M (31%) saved on a 100-GPU cluster. Working across
simulator, kernel module, CUDA, and vLLM + DeepSpeed; bit-parity PCAM runtime (276
tests green).

**Evidence basis.** Benchmarks + code tests across five integrations; TCO is
modeled.

**Honest conclusion.** CTM+ demonstrated concurrency and hit-rate gains over LRU on
phase-structured workloads across five integrations. Honest boundary: on generic
synthetic traces with **no** semantic structure it **matches LRU and slightly loses
to ARC** — expected, since it exploits phase structure. FPGA/ASIC is a research
path, not the adoption ask.

**Next validation step.** A live single-GPU throughput closure run and an FPGA
prototype; a hyperscaler workload trial measuring concurrency gain on real traffic.

---

## 4.4 PSE — deterministic engine for naming & verbal identity
**Implemented (core) · Research**

**Problem.** Every product, company, feature — and now every AI agent — needs names
and verbal identity, but that work happens in chatbots and spreadsheets:
non-reproducible, unconstrained, unaudited, and blind to whether a name is even
**available**. As AI commoditizes the *writing* of names, durable value moves to
what models structurally can't provide — determinism, guaranteed availability,
governance, and compounding outcome data.

**Ugence mechanism.** An intermediate representation / DSL for sound-form design:
deterministic symbolic control (parse any word into a versioned "trajectory," and
*invert* it — specify constraints, get available forms), AI-assisted authoring over
the deterministic scaffold under a hard honesty filter, and an observation graph
that logs every form and human reaction as *measured associations*. The keystone is
a neutral, versioned Trajectory Schema everything depends on.

**Current evidence.** The deterministic engine, trajectory/rendering architecture,
honesty filter, and observation-capture design are specified and in working form;
uniquely offers (vs prompting/embeddings) deterministic reproducible outputs,
hard-constraint satisfaction, an explainable audit trail, editable control, and
inverse design.

**Evidence basis.** Working engine + architecture; commercial surfaces are design/
build-ahead. No customer outcome data yet.

**Honest conclusion.** The deterministic core is built; the commercial surfaces
(studio UI, observation platform, enterprise APIs) are the build ahead. Explicitly
claims **no intrinsic sound meaning** and no scientific validation of the
vocabulary — observations are measured associations, never universal truths. The
"schema as interchange standard" is a high-variance bet, a moat only if an
ecosystem adopts it.

**Next validation step.** Ship the observation platform and accumulate the
model-independent observation graph (the only true data-network-effect moat);
first design-partner customers on governed brand/product naming.

---

# Flagship shadow-mode pilot — AI-Assisted Hiring

*The origin domain that proved the Decision Governance model. Presented as the
flagship **application** of Decision Governance + ActionGate, not a separate
product — the governance core was extracted out of it into the reusable kernel, and
hiring now consumes that kernel directly.*
**Implemented · Internally Validated · Pilot Ready** *(not Pilot Validated: no real shadow-pilot run yet)*

**Problem.** Enterprises running AI-assisted hiring cannot reliably reconstruct
*why* a given hiring action was taken — which evidence was used, which advisory AI
recommendation applied, which human actually authorized the binding decision,
whether it was authorized under runtime controls, and whether what executed matched
what was authorized. Advisory output and binding decisions get conflated, override
rationale is lost, and there is no append-only chain to hand an auditor.

**Ugence mechanism.** A full pass through the Decision Governance kernel
(DecisionCase → ActionRequest → CER → authorization → Execution → Reconciliation)
plus the ActionGate/control-plane port, enforcing the hard AI-advisory /
human-binding separation and emitting one append-only, hash-linked audit event per
stage. A bounded shadow pilot replays a synthetic cohort through this exact
lifecycle using **offline deterministic adapters — no production HRIS writes,
emails, payroll, or identity provisioning.**

**Current evidence.** Working code: the AI-Hiring reference application is
terminal/frozen at **553/553 tests passing**. A validation harness replays a
**12-case synthetic cohort deterministically** and asserts that authorization
denials, reconciliation mismatches, and evidence-insufficiency cases are all
surfaced (never silently passed); an audit-completeness check verifies 7 critical
records including hash-chain integrity, and a reconstruction test proves a broken
link fails reconstruction. Fairness analysis is descriptive-only and the 12-case
cohort is explicitly flagged too small for any fairness conclusion.

**Evidence basis.** Code tests + synthetic shadow-pilot design (in-memory
repositories, offline deterministic adapters, static identity stand-in). No
production data, no real customer pilot.

**Honest conclusion.** For hiring, in deliberative human-authority mode, the
decision contract — admissible-evidence boundary, pinned rubric version,
type-enforced no-AI-binding-decision, four append-only records, reconstructable
lineage — is built and tested on a bounded synthetic cohort with deterministic
replay. It is **not** yet shown running against a real hiring workflow, has no
production persistence or real identity provider, and makes no fairness or
legal-compliance claim.

**Next validation step / pilot success measures.** Run the existing harness in true
shadow mode alongside a live hiring workflow (real ATS/HRIS read feeds, real
identity provider, durable append-only audit backend, cryptographic hash-chain).
Instrumented measures, portable to a real cohort: reconstruction completeness,
audit-completeness ratio (zero critical-record failures on executed cases),
evidence-insufficiency rate, authorization-denial rate, reconciliation-mismatch /
duplicate-execution rate, override rate, and time to produce a complete audit
package per case. A real group size ≥ 10 per label also unlocks deferred
fairness/counterfactual-invariance checks.

---

# The portfolio statement (accurate and commercially strong)

> **Ugence has implemented and internally evaluated a portfolio of governance
> capabilities addressing assertion reliability, evidence integrity, human
> authority, decision accountability, and execution control — plus efficiency
> substrates that make long-context AI affordable. The mechanisms are built and,
> in controlled conditions, do what they are specified to do. The next stage is
> bounded enterprise shadow pilots to validate operational effectiveness,
> false-positive rates, integration cost, and measurable business impact.**

These are not fourteen unrelated tools: the runtimes *propose*, the control plane
*governs the exact assertion and action*, the infrastructure *runs it
efficiently*, and Decision Governance *records who was accountable* — a single
governed loop in which, at any point, you can name which module is responsible.
The defensibility is in the governed loop and the compounding evidence it
generates, not in any single box.

*Sources: the per-module VC briefs in this repository (`*_VC_BRIEF.md`),
`UGENCE_PLATFORM_OVERVIEW.md`, `UGENCE_DECISION_GOVERNANCE_MIDDLEWARE.md`,
`docs/Decision_Governance_Kernel.md`, and the `ai_hiring/` validation track. All
metrics are from our own repositories/CI on synthetic, internal, or (for KVPro and
CTM+) own-hardware benchmarks unless a card states otherwise. No module is
currently Pilot Validated or Production Validated; that is the funded next step.*
