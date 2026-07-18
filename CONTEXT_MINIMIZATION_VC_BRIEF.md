# ActionGate Context Minimization — VC Brief

**Ugence Labs | The Context Layer for Autonomous Enterprise Agents**
*Version 1.0.0 — Updated July 2026 (external / evidence-based)*

> **Product family.** ActionGate Context Minimization is part of the **AI Control Plane** in the
> Ugence Labs platform (canonical taxonomy in `UGENCE_PLATFORM_OVERVIEW.md`). It is a *complementary*
> product to the ActionGate
> authorization engine, not the same product, and the two have separate
> responsibilities: **ActionGate decides whether an agent's action may commit;
> Context Minimization shrinks the *context* an agent reads before it ever gets
> that far — without changing any authorization decision that context would
> produce.** Its boundary is narrow and stands on its own: **extractive context
> compression that is provably authorization-preserving against a deterministic
> gate, cutting real token cost without paraphrase, summarization, or rewriting.**
> This brief describes the project as it exists in the repository today — its
> implemented mechanism, its cross-model validation state, and what remains
> unproved.

---

## Page 1 — The Problem & The Category

### Enterprise agents re-send authorization-bearing context on every step — and compressing it the usual way silently breaks authorization.

Enterprise AI agents repeatedly send the same authorization-bearing context —
policies, approvals, state, evidence, and history — to an LLM on **every step**.
As agents move into production and fleets grow, this repeated context is becoming
**one of the largest recurring inference costs in enterprise AI.**

Existing compression reduces that cost by **rewriting or summarizing** the
context — and in doing so can **silently change the authorization decision the
context would produce.** A dropped policy clause, a "FORBID" softened to a "prefer
not to," a removed payment amount: the token bill falls, and a decision moves with
it — the payment that should not have gone out, the deletion that should have been
blocked, the scope that should not have been granted.

**ActionGate Context Minimization is the first deterministic context layer that
removes only information proven irrelevant to authorization — reducing cost
without changing decisions.** It is extractive (it never rewrites), every keep/drop
choice is gated by a deterministic authorization engine, and it fails closed.

### The category: three layers of enterprise AI infrastructure

We believe enterprise AI infrastructure resolves into three foundational layers
that sit **around** the model rather than competing with it:

| Layer | What it governs | Ugence Labs product |
|---|---|---|
| **Context Layer** | what the model is allowed to *read* | **Context Minimization** |
| **Reasoning Layer** | the model's inference itself | *(the LLM — not ours)* |
| **Execution Layer** | what the model is allowed to *do* | **ActionGate** |

Ugence Labs builds **two of the three** — the deterministic layers on either side
of the model. Context Minimization governs the context going in; ActionGate
governs the action coming out. This brief is about the Context Layer; the two are
tied together into a company-level thesis on Page 4.

### Why every enterprise agent needs this

**Every enterprise agent already assembles context before calling an LLM, and
every enterprise agent already executes actions after the LLM responds.** These
two insertion points exist regardless of the underlying model — which is exactly
what makes both products **horizontal infrastructure** rather than point
solutions: the same two layers front a finance agent, an infrastructure agent, and
an access agent alike, no matter which model sits between them.

**In one line:** *ActionGate Context Minimization cuts the token cost of running
authorization-bearing agents by removing only the context a deterministic gate
proves is inert — and failing closed everywhere else.*

---

### Why the economics matter to an enterprise

The value is not "cheaper summaries." It is a **structural cost reduction on the
single most repeated expense in an agent stack**, taken without adding a review
burden:

- **The cost is recurring and multiplicative.** Context is re-sent on every turn,
  across every workflow, across every deployed agent. A per-turn reduction
  compounds over turns, over concurrent workflows, and over a growing fleet — this
  is the line item that scales fastest as agent adoption grows.
- **The savings are operational, not just per-call.** Because the reduction is in
  the *input context* re-transmitted each turn, it lowers the marginal cost of
  every agent decision an enterprise makes at scale — the more autonomous the
  agent, the more turns it takes, the larger the base the reduction applies to.
- **Safety is structural, so the savings don't create new labor.** A lossy
  summarizer forces a choice — pay for the tokens, or pay a human to check that
  compression didn't change anything. Because this compressor is
  authorization-invariant by construction and fails closed, the cost comes off
  *without* standing up a human-review step to catch flipped decisions. That is
  what makes it usable in compliance-sensitive workflows rather than only in
  low-stakes ones.

We deliberately do **not** put a dollar ROI on this. The measured lever is a
**32–50% reduction in the context tokens** re-sent per turn (see Page 4); what
that is worth depends on an enterprise's agent volume and model pricing, which we
will size with design partners on their real traffic rather than assert here.

---

## Page 2 — The Product & Architecture

### Context Minimization is the context layer of the agent stack, not a standalone compressor.

Positioned correctly, this is **infrastructure that sits between context
assembly and the model** in every authorization-bearing agent — the layer that
decides *what the model is allowed to read* before it reads it. It is not an
application an enterprise adopts for one workflow; it is a middleware stage the
whole fleet passes through.

```
              Enterprise Context
                      │
                      ▼
            Context Minimization
                      │
                      ▼
                     LLM
                      │
                      ▼
                 ActionGate
                      │
                      ▼
             Enterprise Systems
```

Each layer has one job:

- **Enterprise Context** — the policy, state, evidence, and history assembled for
  the agent's turn.
- **Context Minimization** — removes only the spans a deterministic gate proves are
  irrelevant to authorization; fails closed. *(This product.)*
- **LLM** — reads a smaller, authorization-invariant context and proposes an action.
- **ActionGate** — makes and enforces the deterministic authorization decision on
  that action.
- **Enterprise Systems** — the payment, deployment, access change, or ticket that
  actually executes.

**Two complementary products, separate responsibilities.** Context Minimization
and ActionGate are distinct layers of the same stack:

- **Context Minimization** operates *before* the model reads — it reduces the
  context and guarantees the reduction is authorization-invariant.
- **ActionGate** operates *after* the model acts — it makes and enforces the
  actual authorization decision on the resulting action.

Context Minimization does not run the agent, hold credentials, or make the
authorization decision; those belong to ActionGate. Its guarantee is precisely
*"the smaller context I hand the model produces the same authorization envelope
and decision the full context would."*

The relationship is tighter than "two products in the same portfolio":
**Context Minimization uses ActionGate as the deterministic oracle that proves
authorization equivalence.** ActionGate is not a downstream consumer here — it is
the *ground truth* the compressor checks itself against on every reduction. That
is exactly why this is not "just another compressor": a generic compressor has
nothing that can tell it whether a dropped span mattered, whereas this one has a
deterministic engine that computes the answer.

```
        ActionGate
            │
   proves authorization equivalence
            │
            ▼
     Context Minimization
   drops only authorization-invariant spans
            │
            ▼
           LLM
```

Because the oracle is deterministic rather than a second model's opinion, the
check is reproducible and byte-exact — the compressor keeps a span whenever
dropping it would change the gate's envelope or decision, and only then.

### How it works

Every context is decomposed into **spans**, each span is classified as
**protected or droppable** by running the *real deterministic gate* over
ablations of the context, droppable spans are removed to hit a token budget, and
a **fail-closed invariance check** verifies the compressed context yields the
byte-identical authorization envelope and decision as the original — restoring
spans if it does not. The compressor **never rewrites, paraphrases, or
summarizes**; it only removes spans the gate has proven inert.

```
  Context Assembly output  (policy · state · evidence · history · instructions)
        │
        ▼
  Span decomposition        ──►  context split into ablatable spans
        ▼
  Protected-span detection  ──►  multi-stage extractor + trainable detector label
        │                        each span PROTECTED | DROPPABLE by running the
        │                        REAL gate over span ablations
        ▼
  Protected-span mask        ──►  load-bearing spans (amounts, scopes, approvals,
        │                         negations, policy conditions, freshness) are
        │                         never eligible to drop
        ▼
  Extractive budget fill     ──►  drop droppable spans to hit the token budget
        │                         (KEEP-or-DROP only — no rewrite / paraphrase)
        ▼
  Fail-closed invariance     ──►  re-run the gate on the compressed context; require
        │                         a byte-identical envelope + decision; on ANY
        │                         divergence, RESTORE spans (fail safe)
        ▼
  Smaller context  +  frozen fingerprint of the exact compressor/policy used
```

The pipeline — **decompose → detect → mask → fill → verify → restore** — is a
deterministic contract exercised end-to-end by the test suite, not a bag of
heuristics. A protected span cannot be dropped; a detector miss that would move a
decision is caught by the invariance check and undone; and because the mechanism
is extractive, no span is ever reworded.

### What the guarantee rests on

Four properties do the work; all are grounded in the repo, and the important
distinction is *why* each is trustworthy — some are true by construction, some
are measured.

1. **The safety property is structural, not statistical.** Preservation of the
   protected spans and of the authorization envelope is computed by the
   *deterministic gate* over the compressed context; the downstream model is not
   part of that computation. So *authorization-preserving compression never flips a
   gate decision* is a property of the compressor+gate, true for **any** reader.
   **(DEFINITIONAL in basis; MEASURED as a consistency check.)**
2. **Extractive only — no rewrite surface.** Spans are kept or dropped, never
   reworded, so the compressor introduces no hallucinated or softened facts.
   **(MEASURED.)**
3. **Fail-closed on uncertainty.** When the detector is unsure a span is
   load-bearing, the span is retained; a detector miss that would change a decision
   is caught and undone. The cost of uncertainty is tokens, never a decision.
   **(MEASURED.)**
4. **Model-portable by construction.** Because the gate, not the reader, computes
   preservation, the safety guarantee holds across model families without
   re-tuning. **(DEFINITIONAL; MEASURED as consistency checks on 3 real models.)**

> **Measured detail (Page 4 has the full table).** The protected-span detector
> reaches held-out recall/precision of 100%/100% via a fail-closed hybrid; the
> exact compressor, corpus, prompts, budgets, scorer, and policy are hashed into a
> single frozen fingerprint so every cross-model run is verifiably the *identical*
> benchmark; a model-agnostic harness drives that frozen compressor through real
> downstream tasks on any model or API.

### Optional inputs — additive, never load-bearing

The compressor can consume optional signals (a task hint, a customer salience
prior) to choose *which droppable spans to drop first*. Two rules hold without
exception: an optional signal can only reorder *already-droppable* spans, never
promote a protected span to droppable; and the guarantee holds with **no**
optional signal present, because it is enforced by the mask and the invariance
check, not by any ordering heuristic.

### Developer surface

The integration boundary is a single compression call with a token budget, plus a
fingerprint pinning exactly what ran:

```python
from actiongate_context_ablation import compressor_bench as CB

# run the frozen extractive compressor at a set of token budgets, scored by the
# REAL deterministic gate (decision + envelope preservation)
report = CB.render_report_md(CB.run_bench())

# cross-model: drive the SAME frozen compressor through real downstream tasks
from actiongate_context_ablation import real_llm_bench as R
from actiongate_context_ablation.llm_client import TransformersLLMClient
res = R.run(TransformersLLMClient("Qwen/Qwen2.5-7B-Instruct"))  # or any API client
```

The harness (Python 3.11+) ships with a frozen corpus, frozen prompts, frozen
budgets, and a benchmark fingerprint, so an integrator can verify byte-for-byte
that their run is the specified benchmark. A separately-frozen **V2 absolute-utility
benchmark** (`ACTIONGATE_REAL_LLM_ABSOLUTE_UTILITY_V2`) repairs three
under-specified tasks and re-freezes the measurement surface; the original V1
fingerprint is preserved unchanged so prior results stay reproducible.

---

## Page 3 — Why Now, Why Infrastructure, and the Competitive Landscape

### Why now

Four forces are converging, and they are the reason this layer is needed now
rather than later. (We size none of these as a market number; each is a directional
condition, not a TAM claim.)

- **Autonomous agents dramatically increase context volume.** Multi-turn,
  tool-calling agents re-send heavy context on every step, so the tokens consumed
  per unit of work are rising far faster than in single-shot LLM usage.
- **Enterprises are actually deploying tool-calling agents.** These agents are
  moving from demos into workflows that touch payments, infrastructure, and
  access — production systems, not experiments.
- **Inference cost is becoming a material line item.** As agent fleets scale, the
  repeated context re-transmission turns into a real, recurring operating expense
  that a CFO notices.
- **Authorization-bearing context is growing fastest.** The context that carries
  policy, approvals, and evidence — precisely the context where a careless
  compression flips a decision — is exactly the context expanding as agents take on
  consequential actions.

Together these make "compress the context, but never move an authorization
decision" a problem enterprises are hitting *now*, and one that generic
compression cannot solve safely.

### Why this becomes infrastructure, not an application

An application solves one workflow. **This is middleware every authorization-bearing
agent passes through**, because every such agent has the same shape:

```
        Context           (assembled per turn: policy · state · evidence · history)
           │
           ▼
   Context Minimization    (reduce it — authorization-invariant, fail-closed)
           │
           ▼
      Authorization        (decide/enforce the resulting action)
```

If an enterprise runs agents that take consequential actions, it has context, it
has an authorization step, and the layer between them is where cost is removed
without moving decisions. That is a horizontal position — the same stage serves
finance agents, infra agents, and access agents alike — which is what makes it
infrastructure rather than a point solution. It is model-portable (the guarantee
does not depend on the downstream model) and domain-agnostic (it operates on
authorization-bearing context, whatever the domain), so one layer fronts the whole
fleet.

### The competitive landscape — a comparison of categories, not vendors

The useful comparison is against **product categories**, because each category
optimizes a fundamentally different objective. The others optimize *text quality*
or *capacity*; Context Minimization optimizes *authorization safety of the
reduction*.

| Category | What it optimizes | What it does **not** provide |
|---|---|---|
| **Summarization** | Fidelity of a shorter *rewritten* text (human/ROUGE) | Any guarantee about the downstream decision; rewriting adds paraphrase/hallucination risk |
| **Prompt / token compression** | Perplexity / answer-retention under a token budget | Decision-equivalence against a deterministic gate; a rare-but-critical span can be dropped |
| **Retrieval / rerank** | Relevance of retrieved chunks (similarity) | Decision-relevance — a low-similarity clause (one "FORBID") can be decision-critical |
| **Long-context models** | Raw context capacity (spend, don't compress) | Any cost reduction, and any authorization-safety story |

The pattern across the table: every mature category is graded on *how good the
text is* or *how much text fits*. None is graded on *"does the reduced context
produce the same authorization decision?"* — which is the one property that makes
compression usable in a workflow where a moved decision is a real-world consequence.
Context Minimization borrows their mechanics (span extraction, budget-constrained
dropping) but binds them to a **deterministic authorization-equivalence check** none
of them run, and adds a **fail-closed floor** and an **extractive-only** constraint
none of them have.

### Where the moat is — and is not

**The moat is the authorization-invariance contract, not the compression ratio.**
We are careful *not* to claim the moat is "span dropping" or a better ratio — those
have precedents. The durable, honest framing is architectural: **an extractive
compressor whose keep/drop choices are gated by a deterministic authorization
engine's envelope and decision, with a fail-closed floor and a frozen,
cross-model-verified benchmark.** Compression proven inert against the exact
decision it could corrupt is the differentiator — not the token count.

**Where it does not compete.** It does not try to win on summary fluency, maximum
compression ratio, or long-context capacity. It wins on the property those optimize
away: *provable authorization-invariance of the reduction*, verified cross-model on
a frozen benchmark.

**In one sentence:** Summarizers chase fidelity, prompt compressors chase
perplexity, retrieval chases relevance, and long-context models just spend the
tokens — Context Minimization removes tokens only where a deterministic
authorization gate proves the removal cannot change the decision, and fails closed
everywhere else.

### Why this is difficult to replicate

Put in business terms first:

> **Competitors can build compressors. Competitors can build authorization
> engines. The hard part is *proving that compression never changes an
> authorization decision* — and that proof requires both systems working
> together.** A compressor alone has nothing to check itself against; an
> authorization engine alone does not reduce cost. The defensible asset is the
> proven equivalence between the two, plus the frozen evidence that it holds.

That is why the differentiation is **not any single algorithm** — the
span-extraction and budget-fill mechanics are, on their own, replicable. What is
hard to reproduce is the **complete system**, because the measured properties
emerge only when six pieces work together:

1. a **deterministic authorization engine** to serve as the ground-truth oracle;
2. a **protected-span detector** that identifies load-bearing spans;
3. an **extractive-only compressor** that can keep or drop but never rewrite;
4. **fail-closed verification** that restores any span whose removal would move a
   decision;
5. a **frozen, reproducible benchmark** that pins the exact compressor, corpus,
   prompts, budgets, scorer, and policy by fingerprint; and
6. **cross-model validation** demonstrating the result holds across model families.

A competitor can copy any one piece — token dropping is well understood, and a
detector or a benchmark can be rebuilt. What is substantially harder is assembling
*all six* into a system that produces the measured properties: the authorization
oracle has to exist and be deterministic, the detector and the fail-closed check
have to compose into a guarantee rather than a heuristic, and the whole thing has
to be frozen and re-verified across models so the numbers mean something. The
depth is in the **integration and the evidence discipline**, not in a clever
transform.

This is a real head start, **not an insurmountable moat.** The pieces are
individually reproducible; what a fast follower would have to rebuild is the
combination *and* the frozen, cross-model-verified evidence that it actually
preserves authorization — and that is where the lead compounds, because the
oracle (ActionGate) and the benchmark discipline already exist here.

---

## Page 4 — Evidence & Roadmap

### What is proven, in plain terms

Before the numbers, the three claims that matter:

1. **It works.** On the real gate, the protected method preserves 100% of
   authorization decisions and envelopes at every compression budget, while
   removing a meaningful fraction of tokens.
2. **It replicates across models.** Three real open-weight models independently
   confirm the same result, with no utility regression — verdict
   `CONSISTENT_REPLICATION`.
3. **The harm it prevents is real.** A protection-*unaware* control (compression
   that ignores the gate) flips a small but consistent fraction of decisions on
   every model — the exact failure this product removes.

The recommendation is an honest **`LIMITED_GO`**, not GO — for a reason stated
plainly below.

### Evidence classification (unchanged, load-bearing distinctions)

| Signal / capability | Evidence | Status |
|---|---|---|
| Decision + envelope preservation (protected method) | Real gate over naturalistic corpus, 100% at every budget | **MEASURED** |
| Fail-closed restoration on detector miss | Adversarial-miss test | **MEASURED** |
| Protected-span detector (recall/precision to 100%) | Held-out extractor/detector benchmark | **MEASURED** |
| Cross-model utility non-regression | Frozen benchmark, 3 real models, spread 2.8% | **MEASURED** (n=3, consistent) |
| Protection-unaware harm (1.3–2.6% decision flips) | Same frozen benchmark, control arm | **MEASURED** |
| Safety generalizes to unrun readers | Computed by the gate, not the LLM | **DEFINITIONAL** (by construction) |
| V2 absolute-utility benchmark | Frozen, three tasks repaired | **IMPLEMENTED** (results pending real runs) |
| Llama-3.1-8B / Gemma-2-9b utility | Not yet run | **NOT STARTED** (cannot change the structural guarantee) |
| Real customer data | Corpus is authored-synthetic/naturalistic | **NOT STARTED** |
| Third-party external audit | Not run | **NOT STARTED** |

*Classification key: **MEASURED** = supported by this repo's frozen
benchmark/tests; **DEFINITIONAL** = true by construction of the compressor+gate,
independent of the downstream model; **IMPLEMENTED** = code exists, results
pending; **NOT STARTED** = not yet built/run.*

> **Measured detail — the numbers behind the three claims (all from this repo's
> frozen benchmark, not third-party benchmarks).**
>
> - **Authorization-invariance:** on the naturalistic corpus through the real gate,
>   **100% decision invariance and 100% protected-span recall at every budget**, up
>   to **~66% token reduction** (the non-protected fraction); fail-closed restoration
>   recovers an adversarial detector miss; a protection-*unaware* baseline corrupts
>   decisions in up to ~51% of contexts where this compressor corrupts none.
> - **Cross-model replication (`CONSISTENT_REPLICATION`, 3/3 real models —
>   Qwen2.5-7B-Instruct, Qwen2.5-14B-Instruct, Mistral-7B-Instruct-v0.3):**
>   protected−original task delta **+1.6% / +2.1% / +4.4%** (utility non-regression),
>   spread **2.8%** across models; protected decision preservation **100%** at
>   20/30/40% budgets; **32–50%** token reduction.
> - **Protection-unaware harm:** the control flips **1.3–2.6%** of authorization
>   decisions at the same budgets on every real model.
> - **Extraction quality:** held-out extractor instability **41%→1.9%**; held-out
>   protected-span **recall 7.5%→100%, precision 5.9%→100%** (fail-closed hybrid);
>   deployable ceiling **51%→61%** (≈ oracle ceiling).
> - **Frozen benchmarks:** V1 fingerprint `sha256:ac4e0692…`; separately-frozen V2
>   absolute-utility benchmark `ACTIONGATE_REAL_LLM_ABSOLUTE_UTILITY_V2`
>   (`sha256:4b947848…`) repairing three under-specified tasks; every cross-model run
>   verified identical by fingerprint.
> - **Test suite:** **135 tests — 133 passing, 2 skipped** (the two that need a real
>   GPU model skip cleanly): gate path, effect/ablation detection, extractor,
>   protected detector, real-LLM harness, cross-model loader, frozen-invariance, V2,
>   RunPod machinery.

### Why `LIMITED_GO` and not GO (the caveat, stated straight)

The three real models replicate the hypothesis in the same direction every time:
protected compression preserves 100% of decisions with no utility regression and
beats protection-unaware compression. The compressor-prototype recommendation
nonetheless remains **`LIMITED_GO`** — deliberately *not* GO — for one honest
reason: **absolute downstream task accuracy is depressed by a model-side ceiling on
one task (tool-argument generation) and by three originally under-specified tasks,
not by the compression.** The load-bearing quantities (the protected−original delta
and the protected-vs-unaware decision-preservation gap) are clean; the
absolute-accuracy caveat is why we say *proceed to broader validation*, not *ship on
these numbers*. The V2 benchmark repairs the under-specified tasks so future runs
measure absolute utility cleanly.

### Honest limitations

| Limitation | Why it exists | Status |
|---|---|---|
| `LIMITED_GO`, not GO | Absolute task accuracy depressed by a model-side tool-arg ceiling + originally under-specified tasks, not by compression | V2 benchmark repairs the tasks; broader validation next |
| Two models pending (Llama-3.1-8B, Gemma-2-9b) | Not yet run; would broaden empirical utility evidence only | Cannot change the structural guarantee; on roadmap |
| Synthetic / naturalistic corpus | No real customer context yet | Real-data validation is the next evidence step |
| Utility is empirical (n=3) | It is a model property, so measured not derived | Broaden model + corpus coverage |
| No third-party audit | Only internal frozen-benchmark evidence so far | External review on roadmap |
| Guarantee scoped to the ActionGate gate | It is *decision-equivalence against that gate*, not against arbitrary downstream logic | By design; the gate is the safety oracle |

### Representative use cases

- **Cost reduction on high-volume agent authorization.** Cut a measured 32–50% of
  the tokens re-sent every turn (policy, state, evidence, ticket history) with a
  proven guarantee that no authorization decision changes.
- **Safe compression for compliance-sensitive agents.** Where a flipped decision is
  a payment, a deletion, or a scope escalation, the fail-closed extractive design
  makes "the summary changed the decision" structurally impossible.
- **Model-portable context budgeting.** Because the guarantee is model-independent
  by construction, the same frozen compressor can front any downstream model without
  re-tuning the safety property.

#### An illustrative workflow (not benchmark evidence)

To make the shape concrete — *this is an illustration of the mechanism, not a
measured result:*

> **Enterprise infrastructure agent.** An agent is asked to execute a production
> change. Its assembled context carries the **change ticket**, the **deployment
> history**, the **approvals**, the governing **policy**, and the **rollback plan**.
>
> Context Minimization runs the deterministic gate over that context, identifies
> which spans are load-bearing for the authorization decision (e.g. the approval
> status, the policy conditions, the change scope), and **removes only the spans
> proven authorization-invariant** — verbose history narration, redundant
> restatements — while the protected spans and the fail-closed check hold everything
> the decision depends on.
>
> Result: a **smaller context**, the **identical authorization outcome**, and
> **lower inference cost** for that turn — with no rewriting and no chance the
> reduction moved the decision.

The measured savings and decision-preservation numbers behind this shape are on the
frozen benchmark above; this scenario simply shows where they land in a real
workflow.

### Roadmap — a maturity timeline, not a coding schedule

The prototype phase — frozen extractive compressor, protected-span detector,
real-gate invariance proof, model-agnostic harness, and a cross-model-verified
frozen benchmark — already exists. What remains turns a validated prototype into a
deployable infrastructure layer.

| Maturity target | Realistic duration (focused team) | What it means |
|---|---|---|
| **Research prototype** | **Already achieved** | Frozen extractive compressor, 100% authorization-invariance at every budget, `CONSISTENT_REPLICATION` across 3 real models, 135 tests, V1+V2 frozen benchmarks. |
| **Broadened validation** | ~1 month | Run Llama-3.1-8B + Gemma-2-9b; run the V2 absolute-utility benchmark end-to-end; publish clean absolute-utility numbers alongside the (already clean) invariance and delta numbers. |
| **Real-data pilot** | 2–3 months | Validate on one design partner's real authorization context (not synthetic), measure real token/cost savings and confirm zero decision flips on their traffic. |
| **Production capability** | 4–6 months | Harden the detector, add customer salience priors as *ordering-only* inputs, integrate as a pre-read context stage in the ActionGate runtime, external review. |

**Parallel note (honesty over reach).** The authorization-invariance property is
the one thing that already generalizes by construction; every roadmap item above
*broadens the empirical utility evidence* (more models, more corpora, cleaner
absolute numbers) — none of them can change the structural guarantee, and we say so
rather than implying the unrun models are results.

### The ask

We are raising to take ActionGate Context Minimization from a
cross-model-validated research prototype to a production context layer for
enterprise agents. The mechanism is implemented and measured today — a frozen
extractive compressor with 100% decision and envelope preservation at every budget,
`CONSISTENT_REPLICATION` across three real open-weight models with 32–50% token
reduction and no utility regression, a fail-closed protected-span detector, and
V1+V2 frozen benchmarks. Capital is earmarked for broadened model coverage, the V2
absolute-utility runs, a real-customer-data pilot, and the external review that
turns a validated prototype into a deployable cost-and-safety layer for autonomous
agents.

We are deliberate about what is proved and what is not. **The authorization
guarantee is structural** — it comes from how the deterministic gate validates the
compressed context, rather than from statistical behavior of the language model, so
it holds for any reader. **Utility non-regression is empirical** — replicated on
every model measured so far, and honestly labeled `LIMITED_GO` until absolute
accuracy is measured clean on the repaired benchmark and confirmed on real data.
Authorization-invariant compression — not merely cheaper summarization — is what
lets an enterprise cut agent context cost without ever moving a decision it cannot
afford to move.

### The strategic picture

Step back and the two Ugence Labs products form one coherent story for autonomous
enterprise agents. The positioning statement, in two lines:

> ## ActionGate governs execution.
> ## Context Minimization governs context.

One decides what an agent is allowed to *do*; the other decides what an agent is
allowed to *read*, and guarantees that decision is preserved — the Execution Layer
and the Context Layer from Page 1, the two deterministic layers on either side of
the model.

**Why Ugence Labs becomes the company customers buy both from.** Together, Context
Minimization and ActionGate create a **deterministic control plane around
enterprise AI.** One governs what the model reads; the other governs what the model
is allowed to do. As enterprises deploy larger fleets of autonomous agents, we
believe these two layers become foundational infrastructure that sits *around*
every model rather than competing with any model — the context going in and the
action coming out both governed by the same authoritative, reproducible engine
instead of left to a language model's statistical behavior. That is the position
this raise is meant to build: not a compressor, but the Context Layer of
deterministic infrastructure for enterprise agents — bought alongside the Execution
Layer, from one company.

---

*Contact: Rakesh Mohan — Ugence Labs*
*Repo: `rasaha/symbolu` · Module: `experiments/actiongate_context_ablation/`*
*v1.0.0 · frozen benchmark `sha256:ac4e0692…` (V1) / `ACTIONGATE_REAL_LLM_ABSOLUTE_UTILITY_V2` `sha256:4b947848…` · cross-model `CONSISTENT_REPLICATION` (3 real models) · compressor recommendation `LIMITED_GO`*
