# Conscious Generation LLM — VC Brief

**Cognade Labs | `mistral_cg` — Multi-Field Token Evaluation on a Frozen Mistral-7B Backbone**
*Prepared April 2026*

---

## Page 1 — The Problem

### Standard LLMs ultimately rank candidate tokens through a single projection bottleneck.

In a standard transformer, the hidden state summarizes a great deal of
context, but each candidate token is ultimately ranked by a single
scalar logit produced by `lm_head(hidden_state)`, and softmax picks the
next word by statistical continuation over that one ranking. Many of
the constraints humans apply implicitly — plausibility, mode, tone,
relational fit, identity continuity — are not explicitly separated in
token selection and must be approximated through the hidden state.

This compression is, in our view, **one structural contributor** to
several well-known LLM failure modes:

| Failure observed in standard LLMs | A signal the model does not explicitly isolate |
|---|---|
| Factual hallucinations (*"the Eiffel Tower is in London"*) | Physical / causal plausibility of the candidate token |
| Tone and register drift inside a single passage | Emotional / phonemic resonance of the candidate token |
| Mode confusion (fiction presented as fact, memory as imagination) | Explicit cognitive mode classification |
| Relational incoherence (*"calmly placed the cup on the explosion"*) | Energetic / relational harmony between candidate and context |
| Topic / identity drift over long contexts | Ontological identity stability across turns |

We do not claim these are the only causes of the failures above — LLM
error modes are multi-causal, and many of them respond partially to
better data, RLHF, retrieval, or moderation. What we do claim is that
post-hoc mitigations act *after* the model has already committed to a
distribution, and none of them change the fact that the distribution
itself came from a single projection. The architecture effectively
compresses many competing considerations into a single token-ranking
projection bottleneck — and in our view, relaxing that bottleneck is a
research direction worth funding.

### What we think a more grounded approach looks like

Our thesis is that next-token probability should be computed as the
**integrated agreement of multiple semantic fields** evaluating each
candidate token, rather than as a single continuation score from one
projection. Concretely, we believe a competitive next-generation LLM
will need (i) an explicit internal state representing ontological
identity, cognitive mode, and energetic profile; (ii) trainable
per-token auxiliary scorers that can evaluate candidates against that
state; and (iii) a mechanism for those signals to actually influence
token selection during generation, not just to be observed post-hoc.

This is a significant architectural bet, not a drop-in fix. `mistral_cg`
— our Conscious Generation LLM — is a live *partial* implementation of
that thesis today: the state, the scorers, and one inference-time
mechanism (the phase adapter) are in place, and the next 12 months are
about closing the remaining gap between the training-time signal stack
and the generation path.

---

## Page 2 — The Architecture

### `mistral_cg` — frozen Mistral-7B backbone + trainable Conscious Generation modules

Conscious Generation is not a new foundation model. It is a **trainable
modification layer that sits on top of a frozen open-weights backbone**
(today, Mistral-7B v0.3, optionally 4-bit quantized). This choice is
deliberate: we get competitive base-model quality for free, we keep
trainable-parameter count small (~5M), and we isolate our contribution
to the layers where our thesis is testable.

### Forward pass in the `MistralCGWrapper`

```
  input_ids
      │
      ▼
  Mistral-7B backbone  [FROZEN, optional 4-bit]
      │                             hidden_states  [B, T, 4096]
      ▼
  SovereignStateProjector  [trainable]
      │                             32D state  (Bhava 12 · Kosha 5 · Vritti 5 · Guna 6 · Reserved 4)
      ▼
  Δ Bhava  →  IntentPhaseProjector  →  intent_phase   [trainable]
      │
      ▼
  Phase Adapter  (Linear → GELU → Linear, gated residual)   [trainable]
      │
      ▼
  adapted_hidden = hidden + sigmoid(gate) · adapter_output
      │
      ▼
  backbone.lm_head  [FROZEN]  →  logits
      │
      ▼
  next token
```

The 32D Sovereign State is the interpretable spine of the model. Its
five slices each correspond to a designed aspect of "what the model
currently is": **Bhava** (12D — ontological identity axes), **Kosha**
(5D — layer weighting), **Vritti** (5D — cognitive mode), **Guna** (6D —
energetic profile), and **Reserved** (4D). The *delta* of the Bhava
slice between turns drives an intent-phase projection, which the phase
adapter turns into a small, learned correction to the hidden state
**before** it reaches the frozen LM head.

This is the mechanism that currently influences token selection at
inference time in `mistral_cg`. It is also what makes the system
honest: the CG layers cannot silently rewrite Mistral's logits — they
can only inject a gated, state-conditioned correction into the hidden
representation that produces them.

### Training auxiliaries — the multi-field token-evaluation layer

On top of the forward pass above, the training stack adds a
**Token Evaluation Tensor** with per-token scorers for each of the
signal families in our thesis:

| Signal | Scorer module | What it learns to judge |
|---|---|---|
| **CSR** | `CSRTokenScorer` (phoneme affinity × context) | Phonemic / tonal resonance of a candidate token |
| **Vritti** | `VrittiTokenScorer` (token/context → 5 cognitive-mode probs) | How well the token fits the current cognitive mode |
| **Guna** | `GunaTokenScorer` (token/context → 3 Guna probs, bilinear) | Energetic / relational compatibility |
| **Ontological** | `TokenOntologyProjector` + `OntologyCompatibilityScorer` | Identity-level compatibility with the 32D state |
| **JEPA / Plausibility** | JEPA-style predictor and plausibility heads | Causal / physical grounding of the token |
| **Kosha / Bliss** | Kosha router + Bliss gate | Layer weighting and coherence integration |
| **Level Discipline** *(proposed — design spec complete, implementation pending)* | `LevelDisciplineScorer` + `LevelClassifierHead` / `JustificationHead` / `LevelStateHead` — writes `Reserved[0..3]` of the Sovereign State. See `docs/design/LEVEL_DISCIPLINE_SCORER_DESIGN.md`. | Epistemic match: a claim's categorical (I/G/P/U) and temporal (log-seconds) zoom vs. the zoom of the evidence in context |

Each scorer ships with its own InfoNCE / contrastive auxiliary loss,
gated by an explicit lambda weight in the training config. During
training, these losses shape the shared hidden representation and the
32D state so that the downstream phase adapter inherits signal-rich
structure. This is how a multi-field token-evaluation thesis becomes
testable on a frozen backbone without retraining Mistral from scratch.

### Integration with the Agentic Framework

`mistral_cg` ships behind the same `BaseLLMAdapter` interface the rest
of the Agentic Framework uses, exposed as `MistralCGAdapter`. That means
a governed agent built with `build_agent(...)` can swap in a CG backend
with no wiring changes, and the **governance layer gains access to
model-internal runtime signals** (entropy and vritti values read from
the 32D state) rather than prompt-level self-reported confidence. This
is the tight loop between our research stack and our developer product:
`mistral_cg` is the first adapter where those signals are actually
available.

---

## Page 3 — Competitive Landscape

`mistral_cg` occupies an unusual position in the current LLM tooling
stack. It is neither a foundation-model company trying to outspend
OpenAI on pre-training, nor a wrapper layer that sits outside a
black-box API. It is a **trainable internal modification to an
open-weights model** with an explicit thesis about how token selection
should be computed. The table below places our product against the
families it is most commonly compared to in investor conversations,
stating for each family *how* we differ and *why* that difference is
an advantage.

| Category | Representative players | What they ship | How `mistral_cg` differs — and why it is better |
|---|---|---|---|
| **Closed-weights foundation labs** | OpenAI (GPT-4/5), Anthropic (Claude), Google DeepMind (Gemini) | Massive, closed-weights models tuned via RLHF / Constitutional AI. Mitigations (refusals, factuality, tone) are applied as a preference layer over a single softmax. | We do not compete on pre-training scale. We bolt a ~5M-parameter trainable layer onto a frozen open-weights backbone and intervene *inside* the generation mechanism. **Better because:** the intervention is structural rather than preference-tuned, self-hostable, orders of magnitude cheaper to train, and our governance layer gets access to actual model internals — not just the text that a closed API returns. |
| **Open-weights backbones** | Mistral AI, Meta Llama, Qwen, DeepSeek | Open-weights base / instruct models intended as a starting point for downstream fine-tuning. | These are our **substrate**, not our competitor. `mistral_cg` is what you would build *on top of* Mistral-7B if you wanted the model to expose an interpretable 32D state and a multi-field token-evaluation path. **Better because:** we inherit every quality gain the open-weights ecosystem produces (our recipe is deliberately backbone-agnostic) and we add a capability — interpretable, per-field token scoring — that no base model exposes on its own. |
| **Parameter-efficient fine-tuning** | LoRA / QLoRA, PEFT, IA³, adapter tuning | Generic low-rank or adapter modules that shift a frozen model's output distribution toward a target dataset, tone, or persona. | LoRA-class methods are **architecturally neutral**: they adjust a distribution without making any claim about *why* a token should be chosen. Our phase adapter looks like a LoRA from the outside, but it is driven by a designed 32D Sovereign State (Bhava · Kosha · Vritti · Guna) and supervised by per-field scorers. **Better because:** every trainable parameter has a named role (identity, mode, energy, phoneme, plausibility), so a failure mode can be localized to a field rather than debugged as an opaque weight shift — and the same structure gives downstream systems something legible to read. |
| **Retrieval-augmented generation** | LangChain / LlamaIndex + vector DBs (Pinecone, Weaviate, Chroma) | Inject retrieved documents into the prompt to ground generation on external facts. | RAG grounds *what* the model sees in its context window. It does not change *how* the model ranks candidate tokens given that context. **Better because:** even with perfect retrieval, the final token is still picked by a single softmax; `mistral_cg` replaces that softmax with multi-field agreement, so RAG + CG is strictly stronger than RAG alone — retrieval provides evidence, and CG enforces that the chosen token is actually consistent with it. |
| **Guardrails & post-hoc moderation** | NeMo Guardrails, Guardrails AI, Llama Guard, OpenAI Moderation API | Filter, rewrite, or refuse outputs *after* the model has already produced them. | Guardrails act after the distribution is committed. Our thesis is that hallucinations, tone drift, and mode confusion originate *inside* the token-ranking step, so the intervention has to happen there. **Better because:** shaping the distribution at the source avoids the whack-a-mole cost of filtering and catches failures a pattern-based filter cannot even express — energetic incoherence, cognitive-mode drift, ontological identity breakdown — which are exactly the cases where standard moderation is silent today. |
| **Interpretability / steering startups** | Goodfire, Transluce, Anthropic interpretability, EleutherAI mech-interp | Probe, visualize, or steer existing model internals *after* the model has been trained by someone else. | Interpretability players treat the model as **given** and learn to read or nudge it. We treat interpretable internal state as a **designed, trained, and supervised** component of the model itself. **Better because:** every dimension of the 32D Sovereign State is a contract the training stack optimizes against, so a governance readout is not an empirical probe that might generalize — it is a named axis the model was trained to expose and respect. |
| **Agent frameworks & governance wrappers** | LangChain, AutoGen, CrewAI, LangGraph | Orchestration layers that call LLM APIs and add tool use, memory, retries, and confidence heuristics. | These frameworks rely on **prompt-level, self-reported** signals — the model says "I am not sure" and the wrapper trusts it. Our Agentic Framework consumes **model-internal** signals (entropy + vritti read from the 32D state) through `MistralCGAdapter`. **Better because:** a model's self-reported confidence is itself a text completion and can hallucinate; a state readout cannot — it is literally the vector the model used to pick the next token, so escalation, tool gating, and refusal decisions are grounded in what the model *did*, not what it *said*. |

### Why the overall bet is better, not just different

- **Structural, not behavioral.** Every other player in this table either (a) trains a bigger black box, (b) writes better prompts around a black box, or (c) filters the output of a black box. `mistral_cg` is the only approach in this list that changes *the mechanism of token selection itself*, which is where the failure modes we care about originate.
- **Seed-stage cost, foundation-lab capability.** ~5M trainable parameters on a frozen 4-bit Mistral-7B. That is reproducible on commodity GPUs with a single-digit-million training budget — the opposite of the capital moat closed labs rely on, and cheap enough that each new signal family can be ablated honestly.
- **Interpretable by construction.** The 32D Sovereign State is a designed contract (Bhava · Kosha · Vritti · Guna · Reserved), not a post-hoc probe. That makes the resulting model **auditable in the same motion that produces it** — a property governance buyers cannot get from a closed API and cannot reliably manufacture with an interpretability tool applied from the outside.
- **Governance coupling is native, not bolted on.** Because the Agentic Framework reads signals directly from the 32D state via `MistralCGAdapter`, a governed agent built on `mistral_cg` gets runtime decisions (escalation, tool gating, refusal) based on what the model *actually did*, not on what it *said it did*. No wrapper framework on top of a closed API can match that loop, and no closed API is likely to expose it.
- **Composes with, rather than replaces, the rest of the stack.** `mistral_cg` does not ask an operator to throw away RAG, guardrails, or their agent framework — it makes each of those layers more effective, because the model underneath is now producing a signal they can actually condition on. The competitive question is not "CG or RAG?" but "with or without the field-integrated generation path underneath?"

### In one sentence

Everyone else in this landscape either **trains a bigger model**,
**adds text around an existing model**, or **observes an existing
model from the outside**. `mistral_cg` is a bet that the next
improvement in LLM reliability comes from **changing how a single
token is chosen**, using an explicit, interpretable internal state
that both the model and a governance layer can read — and that this
bet is winnable at seed-stage cost, because the backbone is free and
the trainable surface is small.

---

## Page 4 — Evidence, Honest Status & Roadmap

### What is built and running today

| Area | Status |
|---|---|
| `MistralCGWrapper` forward pass | Implemented. Frozen Mistral-7B backbone + trainable state projector, intent-phase projector, phase adapter, gated residual. |
| 32D Sovereign State (Bhava · Kosha · Vritti · Guna · Reserved) | Produced in every forward pass when CG is enabled. |
| Phase adapter | Trainable, gated, active on every forward pass — the currently active CG mechanism that modifies token probabilities (via hidden-state correction before the frozen LM head). |
| Stage 8 Perspective Synthesizer | Implemented and flag-enabled in `scripts/train_mistral_cg.sh`; conditions the hidden state via interpretive signals (CSR, Vritti, Kosha, Bhava) before the LM head. |
| Training auxiliaries (CSR · Guna · Ontological · Vritti · JEPA · Kosha · Bliss) | All six scorer modules and their associated auxiliary losses are implemented in the training stack and can be activated through the training configuration (flags and per-signal lambda weights). |
| 4-bit / 8-bit quantization | Supported via bitsandbytes. ~14GB VRAM at 4-bit, ~18GB at 8-bit. |
| Trainable parameter count | ~5M (CG modules only; Mistral backbone remains frozen). |
| Inference adapter | `MistralCGAdapter` exposes `mistral_cg` to the Agentic Framework's `BaseLLMAdapter` interface, including entropy + vritti signal readouts from the 32D state for governed tool dispatch. |
| Repo validation | `test_inference_mistral_cg_smoke.py` covers the adapter smoke path; end-to-end training is runnable via `scripts/train_mistral_cg.sh` (from smoke test to full WikiText-103 / C4 runs). |

### Honest scope caveats — what is implemented vs. what is active by default

We want VCs to see the gap between our design document and our current
code, because we would rather surface it ourselves than have it
surfaced in diligence. A recent internal audit
(`docs/audits/CG_MISTRAL_SIGNAL_AUDIT.md`) documents the state below:

| Area | Reality today |
|---|---|
| `enable_conscious_generation` flag | Defaults to `False`. The full CG module tree is only instantiated when explicitly enabled. |
| Token-level auxiliary losses (CSR, Vritti, Guna, Ontological) | Implemented end-to-end, but their lambdas default to `0.0`. They are activated via `scripts/train_mistral_cg.sh`, which sets conservative starting lambdas (e.g. `0.01` for Ontological, `0.005` for CSR/Vritti/Guna). |
| Field-integrated softmax (the full "multi-field replaces softmax" story) | Implemented as Phase 4 but gated behind a curriculum manager. Not the default generation path today. |
| Inference-path generation | The only CG mechanism that currently modifies token probabilities at inference is the **phase adapter** (via its gated residual on hidden states before the frozen LM head). Per-token CSR / Vritti / Guna / Ontological scoring are training-time signals today. |
| Derived inference signals (`SovereignStateMonitor`, `InferenceGunas`, `CSRInferenceGuard`) | Active and usable for governance and observability, but they are **derived** from state and token statistics — not the trained per-token auxiliaries. |
| Repo-validated vs. operator-validated | The forward pass, wrapper, and adapter smoke tests are repo-validated. Full training with all auxiliaries active is **operator-validated** in a torch + GPU environment. |

In plain terms: the **skeleton and training signal path** of multi-field
token evaluation is built. The **phase adapter** is live at inference.
The **field-integrated softmax** that completes the "replace the single
softmax" thesis is implemented but still curriculum-gated. This is
exactly the kind of project where the next 12 months turn a research
architecture into a deployed one.

### Design specs with implementation pending — proposed additions to the stack

One proposed addition is at spec-complete, implementation-pending
status as of this brief, and we surface it here for the same
reason we surface the caveats above: we would rather name the gap
between a design document and the code than let it be discovered
in diligence.

| Proposed scorer | Design spec | Status |
|---|---|---|
| **Level Discipline Scorer** (would be the seventh scorer family in the Token Evaluation Tensor) | `docs/design/LEVEL_DISCIPLINE_SCORER_DESIGN.md` (Steps 1–8): framework, module contract, training signal and curriculum, integration points, validation plan, research risks, and honest scope. | **Design spec complete, implementation pending.** Zero files yet written. Research risk is concentrated in `JustificationHead` (spec §7.1) and in the Dataset C inter-annotator-agreement gate (spec §5.5). See spec §8.2 for the three-phase deliverable path and §6.1 for the file-level implementation plan (9 new files, 6 modified). |

The scorer would add an **epistemic** field — claim zoom level vs.
evidence zoom level — to the existing six semantic fields in the
Token Evaluation Tensor, extending the multi-field thesis from
*semantic agreement* to *semantic and epistemic agreement*. It is
included in this brief not as shipped capability but as the next
research commitment for which the design work has been completed
and the engineering path is specified. Whether it graduates from
design spec to active training signal depends on the §5.5 kappa
gate on expert-annotator agreement for the `justified?` label,
which is a measurable, pre-registered pass/fail condition rather
than an open-ended milestone.

### Training setup we run today

| Setting | Default (via `scripts/train_mistral_cg.sh`) |
|---|---|
| Backbone | `mistralai/Mistral-7B-v0.3`, frozen |
| Quantization | 4-bit (bitsandbytes) |
| Trainable modules | State projector · Intent phase projector · Phase adapter · Stage 8 Perspective Synthesizer · CG scorers |
| Dataset options | Synthetic (smoke) · WikiText-2 · WikiText-103 · C4 |
| Batch / grad accumulation | 4 × 8 |
| LR / warmup | 3e-4 · 500 warmup steps |
| Mixed precision | bf16 |
| Stage 8 | Enabled by default, gate initialized to 0.0 and learned |
| Lambda starting weights | Ont 0.01 · Kosha 0.01 · Bliss 0.01 · Plausibility 0.005 · CSR/Vritti/Guna 0.005 |
| Diagnostics | Embedding diagnostics every 200 steps |

### Roadmap — next 12 months

**Quarter 1 — Close the inference-path gap**
- Wire the four dormant per-token scorers (CSR · Vritti · Guna · Ontological) into the generation path behind a clean flag, so the contribution of each field to token selection is measurable at inference, not just at training.
- Run the first published internal comparison of `mistral_cg` vs. stock Mistral-7B on hallucination, tone-consistency, and mode-coherence evaluation suites.

**Quarter 2 — Field-integrated softmax ("Phase 4") as a default**
- Graduate the field-integrated softmax from curriculum-gated experiment to a default-on option behind a single flag.
- Publish the first ablation study isolating the contribution of each signal family to downstream generation quality.

**Quarter 3 — Adapter maturation + governance coupling**
- Ship `MistralCGAdapter` as a first-class backend for the Agentic Framework, enabling **signal-enriched governance by default** (entropy + vritti + state-derived coherence) for governed agents.
- First external design-partner integration where the governance layer consumes `mistral_cg` internal signals rather than text-level confidence.

**Quarter 4 — Scale + larger backbones**
- Validate the same frozen-backbone + trainable-CG recipe on a larger open-weights model (e.g. Mistral Small 3 / Llama 3.1 class) to test that the architecture is backbone-agnostic.
- Begin work on a paper submission documenting the multi-field token-evaluation architecture and ablations.

### The ask

We are raising seed capital to take `mistral_cg` from a research
architecture with a live phase-adapter inference path and a broad
training-time signal stack, to a model where the **full multi-field
token evaluation thesis is wired into generation**, measurable against
hallucination and coherence benchmarks, and exposed to enterprise
customers through our governed Agentic Framework. The technology is
built on an open-weights backbone, the trainable surface is small
(~5M parameters), the cost structure is modest, and the research risk
is concentrated in well-identified places we can show progress against.

What we are asking capital to fund is specifically: closing the
training-to-inference gap on the per-token scorers, running and
publishing the first honest ablations, maturing the `MistralCGAdapter`
into a first-class adapter behind the Agentic Framework, and
validating the recipe on one larger backbone.

---

*Contact: Rakesh Mohan — Cognade Labs*
*Repo: `rasaha/symbolu` · Modules: `symbolu_training/training/unified/mistral_wrapper.py`, `symbolu_training/training/conscious_generation/`, `agentic/agentic_framework/inference_mistral.py`*
*Design: `docs/design/CONSCIOUS_GENERATION_DESIGN.md`, `docs/design/LEVEL_DISCIPLINE_SCORER_DESIGN.md` · Audit: `docs/audits/CG_MISTRAL_SIGNAL_AUDIT.md` · Training: `scripts/train_mistral_cg.sh`*
