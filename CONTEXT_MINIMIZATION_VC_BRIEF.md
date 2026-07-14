# ActionGate Context Minimization — VC Brief

**Ugence Labs | Decision-Safe Context Compression for Autonomous AI Agents**
*Version 1.0.0 — Updated July 2026 (external / evidence-based)*

> **Product family.** ActionGate Context Minimization is part of the Ugence Labs
> autonomous-systems portfolio. It is a *sibling* of the ActionGate authorization
> engine, not the same product: ActionGate decides whether an agent's action may
> commit; Context Minimization shrinks the *context* an agent reads *without
> changing any ActionGate decision that context would produce.* Its product
> boundary is narrow and stands on its own: **extractive context compression that
> is provably decision-safe against a deterministic authorization gate, delivering
> real token savings without paraphrase, summarization, or rewriting.** This brief
> describes the project as it exists in the repository today — its implemented
> mechanism, its cross-model validation state, and what remains unproved.

---

## Page 1 — The Problem

### Autonomous-agent stacks compress context to save tokens, but no compressor can promise it did not change what the agent decides to *do*.

Long-context agents are expensive. Every tool-calling turn re-sends policy,
prior state, evidence, ticket history, and instructions, and the industry's
reflex is to **compress**: summarize the transcript, paraphrase the policy,
drop "low-salience" spans, or hand the context to a smaller model to
rewrite. These techniques cut tokens — and they are all *lossy in an
uncontrolled way.* A summarizer that drops one clause of a policy, a
paraphrase that softens a "FORBID", or a salience filter that removes the
amount field of a payment can silently change the action the downstream
agent takes. The compression saved money; it also moved a decision.

That risk is invisible to the tools that produce it. Summarization quality
is measured against ROUGE or a human rubric, not against *"would an
authorization gate reach the same verdict on the compressed context?"* The
question a security- or cost-conscious buyer actually needs answered is not
"is the summary faithful?" but "**is the summary decision-safe?**" — and no
general-purpose compressor is built to answer it.

The questions a buyer asks about context compression map poorly onto what
summarizers and salience filters provide:

| The question a buyer asks | What summarization / salience compression offers |
|---|---|
| *"Can compression be guaranteed never to flip an authorization decision, not just usually?"* | No guarantee; quality is measured against text-similarity metrics, not decision equivalence. |
| *"Are the load-bearing spans (amounts, scopes, approvals, negations) protected, or merely likely to survive?"* | Salience is probabilistic; a rare-but-critical span can be dropped as "low-salience." |
| *"If the detector misses a critical span, does the system fail safe or ship the lossy context anyway?"* | Typically ships whatever the model produced; there is no fail-closed floor. |
| *"Does the compressor rewrite text — introducing paraphrase and hallucination risk — or only remove it?"* | Most rewrite/summarize, which is exactly where hallucinated or softened facts enter. |
| *"Does the guarantee hold across model families, or only the one it was tuned on?"* | Rarely tested cross-model; tuned to one reader. |

The gap is not compression ratio and not summary fluency. It is a missing
**decision-safety contract**: a way to remove tokens that is *structurally
prevented* from changing what a deterministic authorization gate decides —
and that fails safe when its span detector is unsure.

### Why bolting decision-safety onto an existing summarizer is hard

Retrofitting this onto a summarization or salience pipeline runs into three
structural problems. First, **the safety property must be enforced by
construction, not measured after the fact** — a compressor that is "usually"
decision-safe is not safe, because the one flipped decision is the payment
that shouldn't have gone out. Second, **the compressor must not rewrite** —
any paraphrase or abstractive summary re-introduces exactly the
hallucination and softening risk it was meant to remove, so the mechanism
has to be *extractive only* (spans are kept or dropped, never reworded).
Third, **detector error must fail closed** — when the protected-span
detector is uncertain whether a span is load-bearing, the system must retain
it, so a detector miss costs tokens, never a decision.

Our position is that decision-safe compression belongs in an **extractive
compressor bound to a deterministic authorization gate**, where a
protected-span mask and a fail-closed decision-invariance check make it
*definitionally* impossible for compression to alter a gate decision. That
is the category this project is built for.

**In one line:** *ActionGate Context Minimization is an extractive context
compressor that removes tokens only where a deterministic authorization gate
proves the removal cannot change the decision — and fails closed everywhere
else.*

---

## Page 2 — The Architecture

### Decision-safe compression at the context boundary, not a better summarizer

The compressor sits between an agent's context and the model that reads it.
Every context is decomposed into **units** (spans), each unit is classified
as **protected or droppable** by running the *real deterministic ActionGate
gate* over ablations of the context, droppable spans are removed to hit a
token budget, and a **fail-closed decision-invariance check** verifies that
the compressed context produces the byte-identical ActionGate envelope and
decision as the original. If it does not, the affected spans are restored.
The compressor **never rewrites, paraphrases, or summarizes** — it only
removes spans the gate has proven inert.

### The implemented compression flow

```
  agent context  (policy · state · evidence · ticket history · instructions)
        │
        ▼
  Unit decomposition        ──►  context split into ablatable spans (units)
        │
        ▼
  Protected-span detection  ──►  multi-stage extractor + trainable detector
        │                        label each span PROTECTED | DROPPABLE by
        │                        running the REAL gate over span ablations
        │                        (envelope / decision / assurance effect)
        ▼
  P0 protected-span mask     ──►  protected spans are never eligible to drop
        │                        (load-bearing: amounts, scopes, approvals,
        │                         negations, policy conditions, freshness)
        ▼
  Extractive budget fill     ──►  drop droppable spans to hit token budget
        │                        (KEEP-or-DROP only — no rewrite/paraphrase)
        ▼
  Fail-closed invariance     ──►  re-run the gate on the compressed context;
        │                        require byte-identical envelope + decision;
        │                        on ANY divergence, RESTORE spans (fail safe)
        ▼
  Compressed context  +  frozen fingerprint of the exact compressor/policy used
```

The pipeline — **decompose → detect → mask → fill → verify → restore** — is
a deterministic contract exercised end-to-end by the test suite, not a set
of optional heuristics. A protected span cannot be dropped; a detector miss
that would change a decision is caught by the invariance check and undone;
and because the mechanism is extractive, no span is ever reworded.

### The technical properties decision-safety rests on

1. **The safety property is structural, not statistical.** Protected-span
   preservation and envelope-preservation are computed by the *deterministic
   ActionGate gate* over the compressed context; the downstream LLM is not
   part of that computation. *Protected compression never flips an ActionGate
   decision* is therefore a property of the compressor+gate, true by
   construction for **any** reader. **(MEASURED — 100% decision + envelope
   preservation at every budget.)**
2. **Extractive only — no rewrite surface.** Spans are kept or dropped,
   never paraphrased or summarized, so the compressor introduces no
   hallucinated or softened facts. **(MEASURED.)**
3. **P0 protected-span mask.** Load-bearing spans (amounts, scopes,
   approvals, negations/exceptions, policy conditions, reversibility,
   freshness) are masked as protected and are never eligible for removal.
   **(MEASURED.)**
4. **Fail-closed decision-invariance.** If the compressed context would
   produce a different envelope or decision, the affected spans are restored
   — a detector miss costs tokens, never a decision. An adversarial
   detector-miss test confirms restoration. **(MEASURED.)**
5. **Trainable protected-span detector with a hard floor.** A multi-stage
   extractor plus a trained detector raises held-out protected-span recall to
   100% and precision to 100% via a fail-closed hybrid; the fail-closed floor
   holds even if the learned detector regresses. **(MEASURED — recall
   7.5%→100%, precision 5.9%→100%.)**
6. **Frozen, fingerprinted benchmark.** The exact compressor, corpus,
   prompts, budgets, scorer, and policy are hashed into a single fingerprint,
   so every cross-model run is verifiably the *identical* benchmark, not a
   re-tuned one. **(MEASURED.)**
7. **Model-agnostic validation harness.** One `LLMClient` interface drives
   the frozen compressor through real downstream tasks on any open-weight
   model or API, so the same benchmark runs unchanged across model families.
   **(MEASURED — 3 real models.)**

### Optional inputs — additive, never load-bearing

The compressor can consume optional signals (a task hint, a customer
salience prior) to choose *which droppable spans to drop first* under a
budget. Two rules hold without exception: an optional signal can only change
*ordering among already-droppable spans*, never promote a protected span to
droppable; and the decision-safety guarantee holds with **no** optional
signal present, because it is enforced by the mask and the invariance check,
not by the ordering heuristic.

### Developer surface — one frozen compressor, deterministic decisions

At the API level the boundary is a single compression call with a token
budget, plus a fingerprint that pins exactly what ran:

```python
from actiongate_context_ablation import compressor_bench as CB

# run the frozen extractive compressor at a set of token budgets, scored
# by the REAL deterministic ActionGate gate (decision + envelope preservation)
report = CB.render_report_md(CB.run_bench())
# → 100% decision invariance + 100% protected recall at every budget

# cross-model: drive the SAME frozen compressor through real downstream tasks
from actiongate_context_ablation import real_llm_bench as R
from actiongate_context_ablation.llm_client import TransformersLLMClient
res = R.run(TransformersLLMClient("Qwen/Qwen2.5-7B-Instruct"))  # or any API client
```

The harness is Python 3.11+, ships with a frozen corpus, frozen prompts,
frozen budgets, and a benchmark fingerprint, so an integrator can verify
byte-for-byte that their run is the specified benchmark. A separately-frozen
**V2 absolute-utility benchmark** (`ACTIONGATE_REAL_LLM_ABSOLUTE_UTILITY_V2`)
repairs three under-specified tasks and re-freezes the measurement surface;
the original V1 fingerprint is preserved unchanged so prior results stay
reproducible.

**Honest surface note.** The compressor is deliberately scoped: it decides
*which spans to keep*, it does not run the agent, hold credentials, or make
the authorization decision — those belong to the ActionGate engine (a
separate product). Decision-safety here means *this compression does not
change what that engine would decide*, which is a property this project
proves against the real gate, not a claim to be the gate.

---

## Page 3 — Competitive Landscape

### The category: decision-safe context compression, not another summarizer

ActionGate Context Minimization is best described as **decision-safe,
extractive context compression for authorization-bearing agent context** —
a compressor whose product promise is a *safety* property (compression never
changes an authorization decision), not a *quality* score (the summary reads
well). It is deliberately **not** positioned as "a better summarization
model" or "a cheaper long-context model." Summarizers and long-context
models optimize fidelity or window size; neither offers a structural
guarantee about downstream decisions, and inviting that comparison would set
expectations around fluency and recall benchmarks that miss the point. It is
also not "just prompt compression" (LLMLingua-style token dropping) — those
optimize perplexity/answer-retention, not *decision equivalence against a
deterministic gate.*

The distinction is which question is answered. A summarizer answers *"is
this a faithful shorter text?"*. ActionGate Context Minimization answers
*"can I prove this shorter text yields the same authorization decision?"* —
a different, narrower, safety-first problem.

### Where it sits in the agent stack

```
  Long context        ──►  raw policy · state · evidence · history · instructions
       │
  Compression choice
       │
  ┌────────────────────────────────────────────────────────────────────┐
  │  Generic compression   ──►  summarize / paraphrase / salience-drop  │
  │  (LLMLingua, summary models, RAG rerank)  — optimizes fidelity/perplexity
  └────────────────────────────────────────────────────────────────────┘
       │
  ═══════════════════════════════════════════════════════════════════════
       the compressed context feeds an agent that takes consequential actions
  ═══════════════════════════════════════════════════════════════════════
       │
       ▼
  ██  ActionGate Context Minimization  ██  ← removes only spans a deterministic
       │                                     gate proves inert; fails closed
       ▼
  Downstream reader (any model)  ──►  same envelope, same decision, fewer tokens
```

It operates **after context is assembled but before the model reads it**,
and it is the only layer in that path whose contract is stated in terms of
the *downstream authorization decision* rather than text similarity.

### Adjacent categories, not one competitor

| Category | Examples | What they optimize |
|---|---|---|
| **Prompt/token compression** | LLMLingua, Selective-Context | Perplexity / answer-retention under a token budget |
| **Summarization models** | Abstractive summarizers, map-reduce summary chains | Human/ROUGE fidelity of a shorter text |
| **Retrieval / rerank** | RAG rerankers, context pruners | Relevance of retrieved chunks |
| **Long-context models** | Large-window LLMs | Raw context capacity (spend, don't compress) |

This project combines pieces of these — span extraction, budget-constrained
dropping — but binds them to a *deterministic decision-equivalence check*
that none of them run. The table below states, per family, how it differs
and why that matters to a buyer who cares about what the agent *does*, not
just what it reads.

| Category | Representative players | What they ship | How Context Minimization differs — and why it matters |
|---|---|---|---|
| **Prompt/token compression** | LLMLingua, Selective-Context | Drop/keep tokens to cut length while retaining answer quality. | They optimize perplexity/answer-retention; they make **no guarantee about an authorization decision** and can drop a rare critical span. **Why it matters:** this project's keep/drop is gated by a deterministic decision-invariance check and a fail-closed protected mask, so a critical span cannot be silently dropped. |
| **Summarization models** | Abstractive summarizers | Rewrite context into a shorter faithful text. | Rewriting **re-introduces** paraphrase/hallucination/softening — exactly the risk that flips decisions. **Why it matters:** this compressor is **extractive only**; it never rewords, so it adds no hallucination surface. |
| **Retrieval / rerank** | RAG rerankers, pruners | Select relevant chunks by similarity. | Relevance ≠ decision-relevance; a low-similarity clause (a single "FORBID") can be decision-critical. **Why it matters:** protection here is defined by *effect on the gate's envelope/decision*, not by similarity. |
| **Long-context models** | Large-window LLMs | Fit more tokens instead of compressing. | Spends tokens rather than saving them; no decision-safety story. **Why it matters:** this project **saves** 32–50% of tokens with a proven decision-safety floor. |

### Feature-level differentiation

In the table below, "No" means *not the product family's native abstraction*
— not that it is impossible to approximate through custom configuration.

| Capability | Context Minimization | Prompt compression | Summarizers | Retrieval / rerank |
|---|---|---|---|---|
| **Structural guarantee** compression never flips an authorization decision | **Yes** — mask + invariance check | No | No | No |
| **Extractive only** (no rewrite/paraphrase surface) | **Yes** | Partial (token-level) | No (abstractive) | Yes (selects), N/A |
| **Fail-closed** on detector uncertainty | **Yes** — restore spans | No | No | No |
| Protection defined by **effect on a deterministic gate** | **Yes** | No (perplexity) | No (fidelity) | No (similarity) |
| **Cross-model** guarantee verified on a frozen benchmark | **Yes** — 3 real models | Rarely | Rarely | Rarely |
| Compression ratio / fluency | Competitive (32–50%) | **Strong** | **Strong** | N/A |

### How the compression primitive differs

This project does not claim a new compression algorithm; the differentiation
is the *unit of the guarantee* and *what it is checked against.*

1. **The safety unit is a decision, not a similarity score.** Generic
   compressors ask *"is the shorter text close to the original?"* This asks
   *"does the shorter text produce the **same authorization decision**?"* —
   checked by running the real deterministic gate. **(MEASURED — 100%
   decision/envelope preservation at every budget.)**
2. **Extractive by construction, not by preference.** The mechanism can only
   keep or drop spans, so it structurally cannot introduce paraphrase or
   hallucination. **(MEASURED.)**
3. **Fail-closed is the default, not an option.** A detector miss that would
   change a decision is caught and undone; the cost of uncertainty is tokens,
   never a flipped decision. **(MEASURED — adversarial-miss restoration.)**
4. **The guarantee is model-independent by construction.** Because the gate,
   not the reader, computes preservation, the decision-safety property holds
   for any downstream model — a claim with definitional, not merely
   empirical, confidence. **(MEASURED as consistency checks on 3 models;
   definitional in basis.)**
5. **Utility is empirically replicated, not assumed.** Downstream task
   utility is a property of the model, so it is *measured*: protected ≥
   original at every budget on every model tested, task-delta spread 2.8%.
   **(MEASURED — n=3, consistent.)**

### Where the moat is — and is not

**The moat is the decision-safety contract, not the compression ratio.** We
are careful *not* to claim the moat is "span dropping" or a better ratio —
those have many precedents. The stronger, honest framing is architectural:
**an extractive compressor whose keep/drop decisions are gated by a
deterministic authorization engine's envelope and decision, with a
fail-closed floor and a frozen, cross-model-verified benchmark.** That
binding — compression proven inert against the exact decision it could
corrupt — is the durable differentiator, not the token count.

**Primary — what the product rests on (all MEASURED):**
- **Structural decision-safety.** 100% decision and envelope preservation at
  every budget, enforced by the mask + invariance check, holding for any
  reader by construction.
- **Real, replicated savings without regression.** 32–50% token reduction
  with protected ≥ original utility on three real models, while a
  protection-*unaware* control flips 1.3–2.6% of decisions — the harm the
  protection prevents is real and consistent.

**Honest scope — where it does not compete.** It does not try to win on
summary fluency, maximum compression ratio, or long-context capacity. It
wins on the one property those optimize away: *provable decision-safety of
the compression*, verified cross-model on a frozen benchmark.

### In one sentence

Prompt compressors chase perplexity, summarizers chase fidelity, and
long-context models just spend the tokens — ActionGate Context Minimization
removes tokens only where a deterministic authorization gate proves the
removal cannot change the decision, and fails closed everywhere else.

---

## Page 4 — Evidence & Roadmap

### What is measured today (v1.0.0, internal evidence)

| Area | Current state |
|---|---|
| **Structural decision-safety** | On the naturalistic corpus through the real gate: **100% decision invariance and 100% protected-span recall at every budget**, up to **~66% token reduction** (the non-protected fraction); fail-closed restoration recovers an adversarial detector miss; a protection-*unaware* baseline corrupts decisions in up to ~51% of contexts where this compressor corrupts none. |
| **Extraction quality** | Multi-stage extractor + trained protected-span detector: held-out extractor instability **41%→1.9%**; held-out protected-span **recall 7.5%→100%, precision 5.9%→100%** (fail-closed hybrid); deployable ceiling **51%→61%** (≈ oracle ceiling). |
| **Cross-model replication** | **`CONSISTENT_REPLICATION`** — 3/3 real models replicate on the frozen benchmark: Qwen2.5-7B-Instruct, Qwen2.5-14B-Instruct, Mistral-7B-Instruct-v0.3. Protected−original task delta **+1.6% / +2.1% / +4.4%** (utility non-regression), spread **2.8%** across models; protected decision preservation **100%** at 20/30/40% budgets; **32–50%** token reduction. |
| **Protection-unaware harm** | On every real model the protection-*unaware* control flips **1.3–2.6%** of ActionGate decisions at the same budgets — the harm the protected mask prevents, measured, not asserted. |
| **Frozen benchmarks** | V1 frozen fingerprint `sha256:ac4e0692…`; separately-frozen **V2 absolute-utility** benchmark `ACTIONGATE_REAL_LLM_ABSOLUTE_UTILITY_V2` (`sha256:4b947848…`) repairing three under-specified tasks; every cross-model run verified identical by fingerprint. |
| **Test suite** | **135 tests — 133 passing, 2 skipped** (the two that need a real GPU model skip cleanly without that infrastructure): gate path, effect/ablation detection, extractor, protected detector, real-LLM harness, cross-model loader, frozen-invariance, V2, RunPod machinery. |

All numbers above are from this repository and its frozen benchmark — not
third-party benchmarks. No external audit has been run yet (see roadmap).

### Cross-model status: `CONSISTENT_REPLICATION` — with a stated ceiling

The three real models replicate the hypothesis in the same direction every
time: protected compression preserves 100% of decisions with no utility
regression and beats protection-unaware compression. The compressor-prototype
recommendation nonetheless remains **`LIMITED_GO`** — deliberately *not* GO —
for one honest reason: absolute downstream task accuracy is depressed by a
model-side ceiling on one task (tool-argument generation) and by three
originally under-specified tasks, **not** by the compression. The load-bearing
quantities (the protected−original delta and the protected-vs-unaware
decision-preservation gap) are clean; the absolute-accuracy caveat is why we
say *proceed to broader validation*, not *ship on these numbers*. The V2
benchmark repairs the under-specified tasks so future runs measure absolute
utility cleanly.

### Evidence classification

| Signal / capability | Evidence | Status |
|---|---|---|
| Decision + envelope preservation (protected method) | Real gate over naturalistic corpus, 100% at every budget | **MEASURED** |
| Fail-closed restoration on detector miss | Adversarial-miss test | **MEASURED** |
| Protected-span detector (recall/precision to 100%) | Held-out extractor/detector benchmark | **MEASURED** |
| Cross-model utility non-regression | Frozen benchmark, 3 real models, spread 2.8% | **MEASURED** (n=3, consistent) |
| Protection-unaware harm (1.3–2.6% decision flips) | Same frozen benchmark, control arm | **MEASURED** |
| Decision-safety generalizes to unrun readers | Computed by the gate, not the LLM | **DEFINITIONAL** (by construction) |
| V2 absolute-utility benchmark | Frozen, three tasks repaired | **IMPLEMENTED** (results pending real runs) |
| Llama-3.1-8B / Gemma-2-9b utility | Not yet run | **NOT STARTED** (cannot change the structural guarantee) |
| Real customer data | Corpus is authored-synthetic/naturalistic | **NOT STARTED** |
| Third-party external audit | Not run | **NOT STARTED** |

*Classification key: **MEASURED** = supported by this repo's frozen
benchmark/tests; **DEFINITIONAL** = true by construction of the
compressor+gate, independent of the downstream model; **IMPLEMENTED** = code
exists, results pending; **NOT STARTED** = not yet built/run.*

### Honest limitations

| Limitation | Why it exists | Status |
|---|---|---|
| `LIMITED_GO`, not GO | Absolute task accuracy depressed by a model-side tool-arg ceiling + originally under-specified tasks, not by compression | V2 benchmark repairs the tasks; broader validation next |
| Two models pending (Llama-3.1-8B, Gemma-2-9b) | Not yet run; would broaden empirical utility evidence only | Cannot change the structural guarantee; on roadmap |
| Synthetic / naturalistic corpus | No real customer context yet | Real-data validation is the next evidence step |
| Utility is empirical (n=3) | It is a model property, so measured not derived | Broaden model + corpus coverage |
| No third-party audit | Only internal frozen-benchmark evidence so far | External review on roadmap |
| Decision-safety scoped to the ActionGate gate | Guarantee is *decision-equivalence against that gate*, not against arbitrary downstream logic | By design; the gate is the safety oracle |

### Representative use cases

The mechanism is domain-agnostic on authorization-bearing context; each use
case pairs it with a real context source:

- **Cost reduction on high-volume agent authorization.** Cut 32–50% of the
  tokens re-sent every turn (policy, state, evidence, ticket history) with a
  proven guarantee that no authorization decision changes.
- **Safe compression for compliance-sensitive agents.** Where a flipped
  decision is a payment, a deletion, or a scope escalation, the fail-closed
  extractive design makes "the summary changed the decision" structurally
  impossible.
- **Model-portable context budgeting.** Because decision-safety is
  model-independent by construction, the same frozen compressor can front any
  downstream reader without re-tuning the safety property.

### Roadmap — a maturity timeline, not a coding schedule

The prototype phase — frozen extractive compressor, protected-span detector,
real-gate decision-safety proof, model-agnostic harness, and a
cross-model-verified frozen benchmark — already exists. What remains is the
work that turns a validated prototype into a deployable capability:
real-customer-data validation, broader model coverage, absolute-utility
measurement on the repaired V2 benchmark, and external review.

| Maturity target | Realistic duration (focused team) | What it means |
|---|---|---|
| **Research prototype** | **Already achieved** | Frozen extractive compressor, 100% decision-safety at every budget, `CONSISTENT_REPLICATION` across 3 real models, ~135 tests, V1+V2 frozen benchmarks. |
| **Broadened validation** | ~1 month | Run Llama-3.1-8B + Gemma-2-9b; run the V2 absolute-utility benchmark end-to-end; publish clean absolute-utility numbers alongside the (already clean) decision-safety and delta numbers. |
| **Real-data pilot** | 2–3 months | Validate on one design partner's real authorization context (not synthetic), measure real token/cost savings and confirm zero decision flips on their traffic. |
| **Production capability** | 4–6 months | Harden the detector, add customer salience priors as *ordering-only* inputs, integrate as a pre-read compression stage in the ActionGate runtime, external review. |

**Parallel note (honesty over reach).** The decision-safety property is the
one thing that already generalizes by construction; every roadmap item above
*broadens the empirical utility evidence* (more models, more corpora, cleaner
absolute numbers) — none of them can change the structural guarantee, and we
state that rather than implying the unrun models are results.

### The ask

We are raising to take ActionGate Context Minimization from a
cross-model-validated research prototype to a production context-compression
capability. The mechanism is implemented and measured today — a frozen
extractive compressor with 100% decision and envelope preservation at every
budget, `CONSISTENT_REPLICATION` across three real open-weight models with
32–50% token reduction and no utility regression, a fail-closed protected-span
detector, and V1+V2 frozen benchmarks. Capital is earmarked for broadened
model coverage, the V2 absolute-utility runs, a real-customer-data pilot, and
the external review that turns a decision-safe prototype into a deployable
cost-and-safety layer for autonomous agents.

We are deliberate about what is proved and what is not. **Decision-safety is
definitional** — it holds for any reader because the gate, not the model,
computes it. **Utility non-regression is empirical** — replicated on every
model measured so far, and honestly labeled `LIMITED_GO` until absolute
accuracy is measured clean on the repaired benchmark and confirmed on real
data. Decision-safe compression — not merely cheaper summarization — is what
lets an enterprise cut agent context cost without ever moving a decision it
cannot afford to move.

---

*Contact: Rakesh Mohan — Ugence Labs*
*Repo: `rasaha/symbolu` · Module: `experiments/actiongate_context_ablation/`*
*v1.0.0 · frozen benchmark `sha256:ac4e0692…` (V1) / `ACTIONGATE_REAL_LLM_ABSOLUTE_UTILITY_V2` `sha256:4b947848…` · cross-model `CONSISTENT_REPLICATION` (3 real models) · compressor recommendation `LIMITED_GO`*
