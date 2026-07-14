# ActionGate Context Minimization — VC Brief

**Ugence Labs | The Context Layer for Autonomous Enterprise Agents**
*Version 1.0.0 — Updated July 2026 (external / evidence-based)*

> **Product family.** ActionGate Context Minimization is part of the Ugence Labs
> autonomous-systems portfolio. It is a *complementary* product to the ActionGate
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

## Page 1 — The Problem

### Enterprise agents are getting expensive, and the obvious fix quietly breaks authorization.

**The business problem comes first.** Enterprises are now putting autonomous,
tool-calling agents into production — agents that approve payments, change
infrastructure, grant access, file and act on tickets. Every one of these agents
is expensive to run, and the expense has a specific shape: on **every turn**, the
agent re-sends the same heavy context — the governing policy, the running state,
the supporting evidence, the ticket and approval history, the standing
instructions. A single agent workflow can make dozens of such turns, and an
enterprise runs many workflows in parallel. The context is re-transmitted again
and again, and input tokens dominate the bill.

The industry's reflex is to **compress that context** to cut the cost:
summarize the transcript, paraphrase the policy, drop "low-salience" spans, or
hand the whole thing to a smaller model to rewrite shorter. This does save money.
It also introduces a risk that is invisible to the tools creating it: **the
compression can change what the agent decides to do.** A summarizer that drops
one clause of a policy, a paraphrase that softens a "FORBID" into a "prefer not
to," or a salience filter that removes the amount field of a payment can silently
alter the authorized action. The token bill went down; a decision moved with it —
and in an authorization-bearing workflow, the moved decision is the payment that
should not have gone out, the deletion that should have been blocked, the scope
that should not have been granted.

That failure is undetectable to the compressor that caused it. Summarization
quality is graded on text-similarity metrics (ROUGE, human fidelity), never on
*"would an authorization gate reach the same verdict on the shorter context?"*
The question an enterprise buyer actually needs answered is not "is the summary
faithful?" but "**can I cut context cost without ever moving an authorization
decision?**" — and no general-purpose compressor is built to answer it.

**ActionGate Context Minimization is built to answer exactly that.** It removes
tokens *only where a deterministic authorization gate proves the removal cannot
change the decision*, it never rewrites text, and it fails closed — retaining a
span whenever its detector is unsure. Compression becomes a cost lever an
enterprise can pull without taking on authorization risk.

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
                        User
                          │
                          ▼
                       Planner
                          │
                          ▼
                  Context Assembly            (policy · state · evidence · history · instructions)
                          │
                          ▼
        ██  ActionGate Context Minimization  ██   ← removes only spans a deterministic
                          │                          gate proves inert; fails closed
                          ▼
                         LLM                    (reads a smaller, authorization-invariant context)
                          │
                          ▼
                      ActionGate               (authorizes / denies the resulting action)
                          │
                          ▼
                  Enterprise System            (payment · deployment · access · ticket)
```

**Two complementary products, separate responsibilities.** Context Minimization
and ActionGate are distinct layers of the same stack:

- **Context Minimization** operates *before* the model reads — it reduces the
  context and guarantees the reduction is authorization-invariant.
- **ActionGate** operates *after* the model acts — it makes and enforces the
  actual authorization decision on the resulting action.

Context Minimization does not run the agent, hold credentials, or make the
authorization decision; those belong to ActionGate. Its guarantee is precisely
*"the smaller context I hand the model produces the same authorization envelope
and decision the full context would."* It uses the real deterministic gate as its
**oracle** — the thing it proves invariance against — not as a capability it
claims to be.

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

We are deliberate about what is proved and what is not. **The safety property is
definitional** — it holds for any reader because the gate, not the model, computes
it. **Utility non-regression is empirical** — replicated on every model measured so
far, and honestly labeled `LIMITED_GO` until absolute accuracy is measured clean on
the repaired benchmark and confirmed on real data. Authorization-invariant
compression — not merely cheaper summarization — is what lets an enterprise cut
agent context cost without ever moving a decision it cannot afford to move.

---

*Contact: Rakesh Mohan — Ugence Labs*
*Repo: `rasaha/symbolu` · Module: `experiments/actiongate_context_ablation/`*
*v1.0.0 · frozen benchmark `sha256:ac4e0692…` (V1) / `ACTIONGATE_REAL_LLM_ABSOLUTE_UTILITY_V2` `sha256:4b947848…` · cross-model `CONSISTENT_REPLICATION` (3 real models) · compressor recommendation `LIMITED_GO`*
