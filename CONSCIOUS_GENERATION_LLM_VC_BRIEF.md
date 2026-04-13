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

## Page 3 — Evidence, Honest Status & Roadmap

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
*Design: `docs/design/CONSCIOUS_GENERATION_DESIGN.md` · Audit: `docs/audits/CG_MISTRAL_SIGNAL_AUDIT.md` · Training: `scripts/train_mistral_cg.sh`*
