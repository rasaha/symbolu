# A Layer-Aware, Validation-First Training Strategy for Symbol-U

Adversarial first-principles analysis of **where** the Symbol-U signals
(Vritti, Aspect/Ontology, Guna, Kosha) should live inside a decoder Transformer and
**when** they should be allowed to influence generation. Not a defense of the
patent; the working hypothesis is the null one — *the typed signals may be
arbitrary latent clusters until proven otherwise.*

Platform: the existing clean-softmax implementation. Supporting code added (additive,
defaults preserve current behavior): per-layer accessor `hidden_all_layers`, a
`control_layer` tap, a `stopgrad_heads` flag, and `run_layer_probe.py`.

---

## Q1 — Should every Transformer layer be influenced by Symbol-U signals?

**No.** Letting every signal influence every layer everywhere is the worst choice
on both ML and scientific grounds. Modern decoder LMs have a well-documented depth
specialization (logit-/tuned-lens, induction heads, ROME's mid-layer factual MLPs,
layer-wise probing literature). Injecting control across all layers (a) corrupts the
substrate later layers depend on, (b) makes attribution impossible (you can never say
*where* a signal mattered), and (c) maximizes the chance that an arbitrary cluster
silently steers the model. Control should be **localized to the zone where the signal
— if real — actually emerges**, and nowhere else.

### Early layers (bottom ~⅓)
**Responsibilities:** token/detokenization, morphology, character/byte statistics,
local n-gram and induction patterns, positional/local syntax.
**Should Symbol-U influence these? NO.** Vritti/Guna/Kosha are claimed to be
cognitive/affective/semantic — abstractions that *cannot* exist before the model has
even resolved token identity and morphology. Forcing typed control here perturbs the
exact features every downstream layer is built on, and any "improvement" would be the
model re-learning to undo the perturbation. Early layers should be a **plain
Transformer**. (At most: *probe* them to confirm the signals are NOT yet present.)

### Middle layers (~⅓–⅔)
**Responsibilities:** semantic composition, entity formation / coreference, concept
features, factual association, contextual meaning. This is where linguistic-probe
accuracy for most "meaning" features peaks.
**Should Symbol-U influence these? PROBE FIRST, control only if validated.** If any
typed signal is genuinely semantic, **Aspect/Ontology** (and possibly **Guna** as a
coarse semantic/affective axis) should *emerge* here. The correct action is
diagnostic: attach validation heads, measure grounding against controls. Allow
control here **only** for heads that pass grounding — and even then prefer to defer
the actuators to later layers.

### Late layers (top ~⅓)
**Responsibilities:** aggregation toward the next token, task/format shaping,
reasoning/planning features, "promotion" of features toward the vocabulary.
**Should Symbol-U influence these? YES — this is the natural home for control.**
Mechanisms that *shape the response* belong late: **recursive refinement** (refining
the to-be-emitted state), **deferred-insight memory** (a read over accumulated
context), and **DHA** (delivery/tone) all act on the near-output representation.
Signals that qualify: late-layer **validated** Aspect/Vritti representations.

### Output layer
**Modify hidden state only — never vocabulary logits directly.** Architecturally,
writing a symbolic signal into the logits means an unvalidated/miscalibrated head
*directly* perturbs `P(token)`: it cannot be cleanly regularized, it destroys
calibration, it is catastrophic if the head is wrong, and it cannot be ablated
without changing the output distribution. A hidden-state (residual) edit is bounded,
goes through the trained unembedding, can be residual-regularized, and is reversible
for analysis. **Hidden-state-only is strictly safer.**

---

## Q2 — Validation heads first, or control heads immediately?

| Criterion | Design A (heads → entropy → control → gen) | Design B (heads → supervised validation → only validated heads control) |
|---|---|---|
| Stability | Lower — unvalidated signals perturb the LM from step 0 | Higher — control is gated on a passed grounding test |
| Interpretability | Low — can't tell if a signal means anything | High — grounding metrics define what each head is |
| Scientific validity | Weak — unfalsifiable ("it helped" ≠ "it's real") | Strong — a head must beat shuffled/majority controls to earn control |
| Optimization | Premature coupling; the LM loss can co-opt heads into arbitrary gates | Clean separation; backbone optimized first, heads probed, control added last |
| Risk of arbitrary latent clusters | **High** — exactly what Design A produces | **Low** — grounding is the filter that rejects arbitrary clusters |
| Generation quality | Risk of corruption by unvalidated noise | Protected — only validated, late signals touch generation |

**Design B (validation-first) is the scientifically stronger architecture.** Its only
cost is more stages; its payoff is that every claim ("Vritti exists at layer N",
"it helps generation") is *testable*. Design A's apparent simplicity hides the core
failure mode below.

---

## Q3 — Can unvalidated heads become arbitrary latent clusters?

- **Can Vritti become an arbitrary clustering?** **Yes.** With no grounded labels, a
  5-way head trained end-to-end becomes whatever 5-way partition minimizes the
  downstream objective (or, with stop-gradient, whatever its own random init + the
  backbone geometry happen to separate). Nothing ties it to "valid cognition /
  misperception / …".
- **Can Aspect become arbitrary?** **Yes**, identically — a 10-way head is even freer.
- **Can entropy over arbitrary clusters still appear useful?** **Yes — and this is the
  trap.** Entropy of an arbitrary categorical is still a real, input-varying scalar; it
  correlates with *something* (sequence position, local difficulty), so it can gate
  memory/refinement and "help on 94% of batches" — exactly what the capacity-matched
  study observed, where entropy-gated refinement nonetheless **lost** to a plain
  recurrent block at equal compute. Usefulness-as-a-gate does **not** imply the
  categories are real.
- **Should entropy be trusted before grounding? NO.** Entropy is a function of the
  head; if the head is ungrounded, its entropy is ungrounded. The layer-probe below
  makes this concrete: a head trained on **shuffled** labels still reaches the
  majority baseline with high confidence — confidence/entropy alone never distinguish
  structure from an arbitrary cluster. Only a control (shuffled labels / majority
  baseline) does.

---

## Q4 — Layer-wise probing experiment (run)

`run_layer_probe.py`: train a small char backbone, **freeze** it, attach identical
linear probe heads to **every** layer, train only the probes, measure
accuracy / macro-F1 / ECE / entropy-error correlation / confidence per layer, with a
**shuffled-label control** at every layer.

> **Honesty constraint:** there are NO real Vritti/Aspect labels for natural text, so
> the experiment probes two *synthetic stand-ins* — a **surface** feature (char class:
> identity/morphology-like) and a **contextual** feature (token-length-so-far:
> composition-like) — to demonstrate the methodology and controls. It is a template
> for the real experiment once grounded labels exist; it does **not** measure real
> Vritti.

### Results (6-layer backbone, 250 backbone steps, CPU, seed 0)

| feature | per-layer acc (block1→6, final) | shuffled control acc | calibration (ECE) | reading |
|---|---|---|---|---|
| surface (5-way) | 0.94 at **every** layer (flat) | **0.36–0.45** (= majority class) | 0.01–0.03 | decodable everywhere, far above its majority/shuffled baseline → genuine, **distributed** |
| contextual (10-way) | 0.29–0.32 (peak final-norm 0.323) | 0.16–0.29 | 0.17 mid → **0.06 final** | weakly decodable, low margin over control; best **calibrated at the final layer** → composition-like, **emerges late but weak** |

**Critical methodological finding:** the shuffled control does **not** sit at uniform
chance (0.20 / 0.10) — it sits at the **majority-class frequency** (~0.40 / ~0.20).
If you (naively) compare probe accuracy to uniform chance, *every* head looks
"informative." The correct baseline is the shuffled/majority control, and the real
margin is `acc(real) − acc(shuffled)`: **+0.54 for the surface feature** (clear
structure) but only **+0.03–0.12 for the contextual feature** (ambiguous at this
scale). 

**Answers:**
- *Where does a surface/identity feature emerge?* Everywhere — **distributed**, present
  from block 1. (Consistent with token identity living throughout the residual stream.)
- *Where does a composition feature emerge?* Weakly and **late** (final-layer best
  accuracy *and* best calibration), but the margin over control is small — at this
  toy scale its localization is not crisp.
- *Are signals distributed or localized?* Feature-dependent: strong surface features
  are distributed; weak contextual features are late-leaning but noisy. **You cannot
  assume a layer a priori — you must probe, with controls.**

The load-bearing lesson for Symbol-U: a probe will decode *something* confidently at
*every* layer. Only the shuffled/majority control separates real structure from an
arbitrary cluster. This is the empirical core of the validation-first argument.

---

## Q5 — Staged activation policy

| Stage | Active modules | Active losses | Stop-gradient boundary | Gradients allowed | Pass / Fail |
|---|---|---|---|---|---|
| **0 — pretrain** | backbone only | next-token CE | n/a | backbone | val loss decreases & stabilizes; else FAIL |
| **1 — frozen probes** | backbone (frozen) + typed heads | head CE on **grounded** labels | full stop-grad: backbone frozen, heads read detached activations (`stopgrad_heads=True`) | probe heads only | each head **beats its shuffled/majority control** by a margin on held-out data; else that head FAILS (stays diagnostic) |
| **2 — joint aux** | backbone + heads | CE + λ·head-supervision | heads still `stopgrad_heads=True` from the **control path**; supervision gradients may flow to backbone (representation shaping) but heads **cannot influence generation** | backbone + heads (via supervision only) | LM loss not harmed (≤ baseline + ε) **and** head grounding holds; else FAIL |
| **3 — gated control** | + entropy → memory / refinement, fed **only by validated heads at a late `control_layer`** | CE + supervision + contribution + residual-reg | control reads validated heads; non-validated heads remain detached/diagnostic | backbone + heads + actuators | each actuator must **beat its capacity-matched control** (`run_capacity_study`) at equal FLOPs; else demote that actuator to diagnostic |
| **4 — full joint** | full path, late-layer control only | all of the above | only late-layer validated representations may influence generation; early/mid stay control-free | all | end-to-end val loss ≤ best earlier stage **and** stability across ≥2 seeds; else roll back to Stage 3 |

The decisive gates are Stage 1 (grounding vs shuffled control) and Stage 3 (beating a
capacity-matched control). Symbol-U currently **fails Stage 3** (the capacity study
showed refinement loses to plain recurrence, memory ties a plain FFN), so under this
policy refinement/memory would remain at Stage-2/diagnostic, not control.

---

## Q6 — Supervised-only vs diagnostic-only vs control

| Signal | Initial role | Why |
|---|---|---|
| **Vritti** | **Supervised-only → diagnostic** | No grounded labels exist; until it beats a shuffled control it is an arbitrary 5-way cluster. Never a control before grounding. |
| **Aspect / Ontology** | **Supervised-only → diagnostic** | Most plausibly semantic (probe the middle layers), but a 10-way head is the *most* free to become arbitrary; demands the strongest grounding. |
| **Guna** | **Diagnostic-only** | Affective/energy axis; least likely to be linearly grounded in a text LM; treat as derived/observed, not a controller. |
| **Kosha** | **Diagnostic-only** | "Awareness layer" readiness — no text supervision; observe, don't steer. |
| **Entropy** | **Diagnostic-only until its heads are validated** | Entropy of an ungrounded head is ungrounded; trustworthy only over validated categoricals. |
| **Recursive refinement** | **Diagnostic / demoted** | Active and stable, but loses to plain recurrent depth at equal compute — no demonstrated novel computation; keep behind contribution+residual-reg, late-layer only, until it beats its control. |
| **Deferred-Insight memory** | **Diagnostic / demoted** | Ties a same-size FFN; same demotion. Only promote if a long-range recall task shows an advantage a pointwise FFN cannot match. |
| **DHA** | **Supervised-only (preference), hidden-state-only, late** | Delivery/tone is a late, output-shaping signal; train from preference labels, never touch logits directly, and keep off until preference data exists. |

---

## Final recommendation — the architecture to build from scratch today

1. **Untouched zones:** the **early layers (bottom ~⅓)** stay a pure standard
   Transformer — no typed heads, no entropy, no control. They build the substrate.
2. **Probe-only zones:** the **middle layers (~⅓–⅔)** carry **diagnostic** validation
   heads (stop-gradient from the control path) that are graded against shuffled/
   majority controls. Nothing here influences generation.
3. **Control zones:** **only the late layers (top ~⅓)** may host control, and only
   from heads that passed grounding (Stage 1) *and* beat a capacity-matched control
   (Stage 3). Actuators (refinement, memory, DHA) act here on the residual stream.
4. **Never modify vocabulary logits directly** — control edits **hidden states only**;
   the trained unembedding maps to tokens. This is strictly safer (bounded,
   regularizable, ablatable, calibration-preserving).
5. **Yes — "validation-first, control-later" is the scientifically stronger
   architecture.** It is the only design under which "the Symbol-U signals are genuine
   computational structure" is a *falsifiable* claim rather than an assumption. It
   maximizes the chance of discovering real structure precisely because it is built to
   detect — and reject — arbitrary latent clusters.

### Concrete changes already added to the clean-softmax platform (no redesign)
- `SoftmaxTransformerLM.hidden_all_layers(ids)` — per-layer accessor for probing
  (zero behavior change).
- `ExpConfig.control_layer` — tap a specific layer/zone for the typed heads/entropy
  (default −1 = final, current behavior). Use a **late** index for Stage-3/4 control.
- `ExpConfig.stopgrad_heads` — make the typed heads **diagnostic/validation-only**
  (no gradient into the backbone): this *is* Design B / Stages 1–2.
- `run_layer_probe.py` — the layer-wise probing harness with shuffled-label controls.

### Proposed (not built — small, additive) to complete the strategy
- **Per-head layer assignment** (extend `control_layer` from one int to a per-signal
  map) so Aspect can be probed mid while refinement/DHA read late — a few lines in
  `model.forward`.
- **A grounding gate** that records each head's `acc − shuffled_acc` and only enables
  its control path when the margin clears a threshold (operationalizes Stage 1→3).
- **A real labeled corpus** for Vritti/Aspect — without it, every result above the
  shuffled control is, by construction, unfalsifiable. This is the single highest-
  leverage missing ingredient.
