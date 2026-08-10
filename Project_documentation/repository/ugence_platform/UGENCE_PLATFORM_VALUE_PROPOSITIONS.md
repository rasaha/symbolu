# Ugence Platform — Value Propositions (Honest Edition)

**Ugence Labs | The Governed AI Platform**
*Per-module value propositions with maturity stated as plainly as the repository supports.*
*Version 1.0 — July 2026*

> **Purpose and discipline.** This document states, for each of the ten platform
> components, (a) the value proposition — the problem it solves and for whom — and
> (b) an honest maturity read grounded in the repository's own code, tests, and
> results docs, including the places where a later internal audit walks back or
> contradicts an earlier brief. It is written to survive technical diligence, not to
> win a first meeting. Canonical architecture: `UGENCE_PLATFORM_OVERVIEW.md`.
>
> **Portfolio-wide caveat, stated once so it need not be repeated ten times.** As of
> this version: **no component has a production deployment, a paying customer, a
> design partner, real-world/field data, or a third-party benchmark.** Every
> quantitative result below is *self-generated* on this repository's own code and CI,
> most of it on *synthetic or naturalistic corpora*. That is not disqualifying for the
> stage — but any reader should treat "validated" throughout as "validated internally,
> on our own data," unless explicitly stated otherwise.

---

## How to read the maturity labels

| Label | Means |
|---|---|
| **Built + internally measured** | Real, runnable code **and** preregistered or GPU-measured experiments — but on synthetic/self-generated data; no real-world or third-party validation. |
| **Built, decisive validation pending/blocked** | Code exists and passes internal/mock tests, but the experiment that would prove the core claim has **not** run (usually blocked on a real model, real sensor, or real cluster). |
| **Emerging / specified** | Architecture is documented; at most one layer has a synthetic prototype. Not yet an efficacy claim. |
| **Claim contested by own audit** | The repository's own later, preregistered audit **walks back or inverts** the headline claim. Flagged explicitly — this is where honesty matters most. |

---

# Layer 1 — Specialized AI Systems (reason, steer, execute)

## 1. Hybrid LLM — long-context reasoning substrate

**Value proposition.** A long-context transformer that fuses linear "phase" attention,
sliding-window attention, and a conditional top-K quadratic branch **serially over one
shared memory state**, so the platform reasons over long horizons without paying the
O(n²) attention tax on every token. The structural bet: information is carried in
**phase angle**, not a decaying running sum, so long-range recall need not pay the
decay tax that bounds linear/state-space models.

**Who it's for.** Teams with long, *ordered* context (agentic tool chains, long chat
history, ordered reasoning) where position matters and RAG is brittle.

**Maturity — Built + internally measured (mechanism); head-to-head pending.**
- **Built:** end-to-end training and inference stack (`symbolu/phase_transformer.py`,
  `train_hybrid_7b.py`), 46M reference config and a runnable 7B recipe.
- **Measured (mechanism-level only):** a ~240K-param *pure-phase* model reaches 100%
  needle-in-haystack retrieval at 2K and 10K token distances **on a controlled
  synthetic task** — this validates the phase-memory *mechanism*, not the full LM.

**The honest catch.** The headline retrieval result is a **pilot-scale mechanism
signal**, not a system result: it is not replicated on the 46M or 7B models. The
comparisons that would prove competitiveness — LRA/Path-X, matched-parameter PPL and
retrieval vs. Mistral-7B and Mamba-2, an inference-throughput report — are **roadmap,
not done**. The defensible claim today is a *complexity class* (O(n) long-range path +
conditional quadratic), not a benchmark win. (See `HYBRID_LLM_COMPARATIVE_MODELS_ANALYSIS.md`.)

## 2. LLM Steering Controller — deterministic generation framing & audit

**Value proposition.** A deterministic, model-agnostic layer that clips onto any LLM
(open or closed, no weight changes) and fixes *which meaning-frame* a model answers in —
same input → same framing, with a logged reason for every steering decision. It sells
**consistency, auditability, and cross-vendor portability**, explicitly *not* higher
intelligence or answer quality.

**Who it's for.** Enterprises that need model outputs kept inside a correct domain/policy
frame with an audit trail, across multiple model vendors.

**Maturity — Built (product layer); weakly validated. Research layer: claim contested by own audit.**
- **Built & true by construction:** the deterministic C×R×S match-filter + framed-prompt
  + answer-audit engine exists in code (`scripts/cg_wrapper_ablation/csr_match_filter/`).
  Determinism and auditability are properties of rule-based code, so they hold by
  construction.
- **Weakly validated:** one favorable run on a single model (Mistral-7B), scored by a
  **deterministic rubric, not humans** (primary-frame correctness 0.61→0.74).

**The honest catch.** Two real problems a diligence reader should probe: (1) the data
file behind the only positive number (`robustness_eval_v2.json`) is **not committed to
the repo**, and the favorable "real-output audit" is **derived from rubric residuals,
not an empirical run** — so the headline is not independently reproducible here; **human
validation does not yet exist** (the results doc is an empty skeleton). (2) The entire
"Conscious Generation" research layer (Guna/Vritti/Kosha/Bhava) has been **specified and
then falsified or parked in the repo's own results**: the internal signal is
`CSR_REDUNDANT`, the inference wrapper is `ACTIVE_NO_EFFECT` (state never moved), a
CSR-based policy gate scored *worse* than the existing audit gate, and the hidden-state
"Bhava" readout is at chance. The one retained IP thread (the multiplicative
match-filter) is **explicitly untested**. Sell the deterministic frame-control; do not
sell "consciousness."

## 3. Agent Runtime — supervised digital execution that proposes governed actions

**Value proposition.** A code-first agent runtime that turns an enterprise goal into a
planned, tool-using workflow and emits a **Canonical Execution Request (CER)** — a
hashable, framework-independent action object — which an external control plane governs.
The differentiated engineering is that **final allow/deny lives outside the runtime**,
bound to the CER by content hash, so governance is consistent across heterogeneous agent
frameworks.

**Who it's for.** Enterprises running multiple agent frameworks that need one canonical,
signable execution contract to govern them uniformly.

**Maturity — Built (deterministic core); real-model validation blocked.**
- **Built:** a real v1 action loop + 5-layer per-tool gateway (~9.2k LOC), and a v2
  migration that produces the proposer→CER→control-plane loop with **0 governance-boundary
  violations** and a preregistered **parity corpus (16/16 agreement)**.

**The honest catch.** **Every phase that needs a real model is honestly reported as
`BLOCKED_NO_REAL_MODEL`** — no live inference has ever run (no credentials/egress), so
"proposal quality" is self-labeled `NOT ASSESSABLE`. The v1 test suite is **not green in
a clean run** (state-pollution failures) and **nothing runs in CI**. The runtime's own
readiness audit flags several marketed features as overstated: "replayable trace" is an
analytics rollup, "cost caps" never fire, "streaming" isn't token streaming, and the
CG-signal differentiators are self-graded as non-predictive (entropy AUROC 0.457,
Vritti 0.500). The honest core — deterministic governed execution + CER — is real; the
cognition and the real-model proof are not yet there.

## 4. Autonomous Runtime — supervised physical execution (predictor-trust arbitration)

**Value proposition (as pitched).** A pure-NumPy arbitration layer between an autonomy
stack's multiple trajectory predictors and its planner, using a "BCVF" consistency cost
to flag which predictor is failing when predictors disagree — planner-agnostic, tunable
without retraining.

**Who it's for.** Robotics/autonomy integrators wanting a predictor-trust safety-adjacent
signal that a safety case can point to.

**Maturity — Claim contested by own audit.**
- **Built:** substantial real code (~4,700 LOC kernel + safety-state, ROS2/DDS, replay,
  real-time-budget frameworks; ~1,117 internal tests).

**The honest catch — this is the most important honesty flag in the portfolio.** The
repository's own **preregistered, code-grounded audit inverts the core claim**:
- The action-selection BCVF variant selected a **hard-inadmissible (unsafe)** candidate
  in 3 of 4 scenarios → verdict **`REPLACE_ACTION_BCVF`**.
- The predictor-trust BCVF variant **loses to a trivial deterministic baseline**
  (recall 0.90 vs 1.00; false-alarm 0.67 vs 0.04) → demoted to an off-by-default feature.
- The advertised "safety invariance" (zero trust signal under constant/linear-drift
  disagreement) **protects a *harmful* error class** and holds only noiseless; with
  realistic noise it leaks and produces a dangerous miss on a precise biased sensor.
- All numbers are synthetic straight-line motion; **"nothing here proves real-sensor
  safety."** LLM-transfer of the idea is a clean null (AUC ≈ 0.48–0.53).

The *engineering* is real and honestly documented; the *scientific value claim* is not
currently supported by the company's own evidence. Position this as a deterministic
reliability architecture with BCVF as an internal latency feature — which is exactly
what `ROBOTICS_V2_MIGRATION_PLAN.md` now does.

---

# Layer 2 — AI Control Plane (govern the interaction boundary)

## 5. Context Minimization — decision-invariant context compression

**Value proposition.** An **extractive** (keep-or-drop, never rewrite) context compressor
that removes only spans a deterministic gate proves cannot change its decision, failing
closed on any uncertainty — cutting authorization-context token cost (claimed 32–66%)
while guaranteeing a **byte-identical** downstream gate decision, which summarizers cannot.

**Who it's for.** Teams paying for large authorization-bearing agent context who need cost
reduction *without* risking a silently flipped decision.

**Maturity — Built + internally measured (real GPU LLM runs); LIMITED_GO.**
- **Built:** ~50-module package, **135 tests**, full decompose→detect→mask→fill→verify
  pipeline.
- **Measured:** committed real open-weight GPU runs (Qwen-7B and Qwen-14B, `is_real:true`,
  ~3,808 records each) — genuine LLM evaluations, not mocks.

**The honest catch.** The self-assigned verdict is **`LIMITED_GO`, not GO**: absolute
downstream task accuracy is depressed on some tasks (e.g. tool-argument generation ~37%).
The "100% decision invariance" headline is **partly a corpus artifact** — the synthetic
corpus puts filler in decision-neutral spans, so removing them is trivially invariant;
"invariance will require the fail-closed loop to fire for real, and precision will drop"
on mixed real content. The safety guarantee is **definitional** (equivalence *against the
gate*, not arbitrary downstream logic). No real customer data, no third-party audit.

## 6. Truth Assurance Platform (TAP) — assertion governance before delivery

**Value proposition.** A modular reliability layer *above* the model that validates
whether a completed response is sufficiently grounded in evidence **before it is
delivered** — deliver / qualify / abstain — with append-only provenance. It is the
assertion-side analogue of ActionGate's action-side authorization, and directly targets
the #1 enterprise blocker on gen-AI adoption: *"we can't prove the output is grounded."*

**Who it's for.** Regulated/high-stakes enterprises that need evidence-grounded,
provenance-backed answers, not model self-report.

**Maturity — Emerging / specified.**
- The architecture (Intent → Retrieval → Relationship/Governance/Claim/Response truth →
  Safety) is **documented specification**; **only the Claim Validation layer** has a
  self-contained prototype, **on synthetic data**.

**The honest catch.** TAP is the **least mature** component and is labeled so throughout
the platform docs. Its one prototype's own verdict records *"production deployment: NO."*
There is **no** claim that the full pipeline is validated, that it eliminates
hallucination, or that it is production-ready. It is funded as *research* — turning each
remaining layer into a measured, single-layer experiment against corpora that do not yet
exist. Strategically it is well-aimed (it targets the exact trust gap slowing incumbent
adoption), but that is a *thesis*, not yet a result.

## 7. ActionGate — deterministic pre-commit action authorization

**Value proposition.** A deterministic gate that authorizes *the exact action* an agent is
about to take — allow / deny / approve / escalate — before commit, with identity bound to
a content hash so what was proposed is provably what is authorized and what executes.
Same envelope + same signed policy + same evidence → same decision, every time; all other
components (simulators, AI advisors, behavioral evidence) plug in only as *evidence
producers* and can never self-approve.

**Who it's for.** Any enterprise that needs an external, auditable, tamper-evident
authorization boundary in front of one or many agent runtimes.

**Maturity — Built + internally measured (the strongest-built governance product).**
- **TRL 4 with a TRL-5 subsystem.** Correctness-complete reference engine with a written
  spec, **24/24 conformance vectors**, 183 passing tests, deterministic decisions,
  replay/TOCTOU caught in tests; runtime integrations (gateway + MCP + Kubernetes);
  red-team detecting **12/12 injected attacks**; a hardened isolated tier (~2,850 LOC)
  with Ed25519 custody-split signing, durable replay stores, a signed audit ledger, mTLS,
  and a 30-attack red-team.

**The honest catch.** The **hardened tier is not the default and is unverified in the
audit** (its `ecdsa` dependency is absent here; those tests skip) — the default runtime is
still reference-grade (HMAC, in-memory). It is **single-node** (no HA/scale/perf
evidence), **operationally blind** (no logging/metrics/tracing), has **no external
REST/gRPC API**, and is **audit-strong but ops-weak** on compliance (no HSM/KMS,
encryption-at-rest, WORM, or RBAC). The novel engineering is done; what remains is
conventional product hardening.

## 8. Autonomous Control Plane (ACP) — operational-safety clearance for physical action

**Value proposition.** A deterministic decision runtime for physical autonomy that applies
a **non-compensatory hard-admissibility filter → lexicographic selection → `NO_SAFE_ACTION`
fallback**, so an unsafe action *structurally cannot win* and every decision carries one
dispositive reason — replacing opaque probabilistic action scoring with an explainable,
fail-closed, bit-reproducible gate.

**Who it's for.** Robotics/industrial-automation teams needing an explainable,
deterministic clearance layer against live operational safety state.

**Maturity — Built (shadow-mode prototype); INSUFFICIENT_EVIDENCE for production.**
- Real code (~2,000 LOC core) exists despite the design folders being labeled
  "design-only." Strongest positive: the frozen decision core ran **hash-identical across
  two genuinely different domains** (robotics and cloud/K8s) → `ACP_GENERALIZES`.

**The honest catch.** Everything is **shadow-only, OFF by default, and not wired into any
production loop.** The live path emits **stub trajectories** (a fixed-velocity planner
that cannot even produce a violating trajectory), corpora are tiny (14–19 synthetic
scenarios), there are **no real sensors or live cluster**, and **WCET/latency is asserted,
not measured** (hard-real-time would need a C++/Rust port). The self-assigned verdicts are
`SHADOW_CONTINUE` and `INSUFFICIENT_EVIDENCE` — *"do not deploy to production on this
evidence."* Note also that **behavioral biometrics** (a BCVF evidence source for this
layer) is an *instrument built and test-covered* but with **no real pilot run and no
validated identity claim** (its coupling hypothesis currently shows near-zero identity
gain on synthetic data).

---

# Layer 3 — AI Infrastructure (run it efficiently, never govern)

## 9. KVPro — quality-safe INT4 KV-cache compression

**Value proposition.** A post-hoc, drop-in KV-cache compressor that stores the cache in
INT4 while keeping ~4% of the highest-attention channels at full precision, preserving
long-context retrieval quality where naive 4-bit codecs collapse — roughly **2× KV density**
(→ more concurrent long-context sessions per GPU). Positioned as a **capacity/quality**
tool, explicitly **not** a speed tool.

**Who it's for.** LLM-serving teams memory-bound on long-context KV cache who need more
concurrent sessions without a quality cliff.

**Maturity — Built + GPU-measured (the most credibly validated result in the portfolio).**
- Real GPU measurements with named repro scripts: needle **15/15 == bf16** on 3 of 4
  models; **MMLU 0.0-pt delta with 100% per-question agreement** at 1,000 Q; hard-needle
  0.964 vs naive-int4 0.915; **+20.4 pt** token agreement vs naive int4; **1.83× net
  density** demonstrated live under saturation. Includes an **audited bug-fix history**
  (three decode bugs found and fixed; prior benchmarks openly superseded).

**The honest catch — disclosed candidly in the repo.** Throughput is **negative**
(~0.13–0.67× bf16; worst case ~0.22×), and the recovery ceiling never reaches
full-precision parity — this is a capacity play, not a latency play. Density carries a
structural **+4.4 GB HBM "sidecar tax,"** so it is capacity-negative except at the KV
block limit. Competitive superiority is **n=1** (one head-to-head where a rival codec
collapsed; KVPro not re-measured on that harness), and the CacheGen end-to-end comparison
is **open** (CacheGen is *more* faithful on average except on the protected channels). The
v2 program (throughput recovery, tensor parallelism, 70B, warm-tier serving) is
**GPU-blocked and unvalidated**. The internal positioning memo says it plainly: *"we do
not win on compression ratio or on 'perfect quality,' and we must stop claiming either."*

## 10. Cloud Scaling Controller — scaling-decision quality (anti-thrash interlock)

**Value proposition.** A coherence-gated scaling controller that **stops futile scale-outs
before they ship** and scales only when scaling actually helps — a safety interlock for
infrastructure, not a FinOps dashboard. Its differentiator is adaptive damping that refuses
to chase volatile demand.

**Who it's for.** Platform teams whose autoscaler thrashes on volatile load and
over-provisions.

**Maturity — Built + internally benchmarked (simulation).**
- A benchmark harness vs. a HPA baseline across six traffic patterns reports the core
  thesis holding: **7.8× average cost efficiency** (1.07× vs 8.32× optimal), **zero
  oscillations** across all patterns, and **+3 max overshoot vs HPA's +203**.

**The honest catch.** The controller's default is tuned for **stability over
responsiveness** to a fault: reaction time is **200 cycles (effectively never reacts)** in
the default profile, and it has a **higher SLO-breach rate** than HPA because it
under-provisions. The docs show this is a single-parameter fix (`G_base` 1.0→2.0 recovers
40% of reaction time while keeping the stability advantage), but the shipped default is
under-actuated. All results are from a **simulation** against synthetic traffic patterns
and an oracle-optimal baseline — **not a real cloud, real workload, or real cost data.**

---

## Portfolio-level honest read

**What is genuinely strong today**
- **ActionGate** — real, tested, red-teamed deterministic authorization; the most
  product-ready governance component (the remaining work is conventional hardening).
- **KVPro v1** — real GPU-measured quality-at-density with an audited bug history and
  candid disclosure of its throughput/HBM downsides.
- **The architectural spine** — the CER contract + external, deterministic governance
  boundary is real code with 0 boundary violations in test, and it is the platform's
  most defensible idea.

**What is a promising thesis but not yet a result**
- **Hybrid LLM** (mechanism validated at pilot scale; system benchmarks are roadmap),
  **Context Minimization** (`LIMITED_GO`), **Cloud Scaling Controller** (sim-only),
  **TAP** (emerging, one synthetic-prototype layer).

**Where the repo's own evidence contradicts the pitch — disclose proactively**
- **Autonomous Runtime / robotics BCVF** — the preregistered audit inverts the safety-value
  claim (underperforms a trivial deterministic baseline; "invariance" guards a harmful
  class).
- **LLM Steering Controller's "Conscious Generation" layer** — self-falsified
  (`CSR_REDUNDANT`, `ACTIVE_NO_EFFECT`, Bhava collapse); only the deterministic
  frame-control product survives, and even that lacks committed data and human validation.

**The one caveat that applies to all ten:** every number here is self-generated, mostly on
synthetic data; there is no production deployment, paying customer, real-world dataset, or
third-party benchmark yet. The honest value of this portfolio is **disciplined engineering
plus unusually rigorous internal falsification** — a foundation to validate against real
data, not a set of proven products. Selling it as the former is credible; selling it as the
latter would not survive the repo's own audits.

---

*Ugence Labs — the governed AI platform.*
*Sources: each module's VC brief, readiness/implementation audit, and machine-readable
results under the repository; canonical taxonomy in `UGENCE_PLATFORM_OVERVIEW.md`.*
