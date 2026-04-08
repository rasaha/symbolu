# Minimum Safe CSR+Guna-First Inference Design Spec

**Date:** 2026-04-07
**Type:** Design evaluation (no implementation)
**Scope:** Mistral CG inference path only

---

## 1. Executive Summary

**CSR+Guna as the causal basis for live inference faces a fundamental
asymmetry: Guna is available and meaningful in the 32D state at
inference time; CSR is not.**

The 32D sovereign state contains Guna at positions [22:28] (6D,
sigmoid-normalized), computed by the `SovereignStateProjector` on
every forward pass, already extracted by `sovereign_bridge.py` into
stability signals. CSR, by contrast, is entirely external to the 32D
state — it requires phoneme affinity vectors from the `CSRPhonemeProvider`
and pipeline-level C_s/M/H signals that do not exist in
`MistralCGAdapter.call()`.

The honest recommendation is: **promote state-Guna only via sampling
modulation, using the Vritti gate pattern. Keep CSR indirect. Do not
force CSR onto the live path — the signal does not exist at the right
abstraction level.**

This preserves the causal direction (CSR→Guna is the training-time
structural cause; the state projector's learned Guna already reflects
CSR influence absorbed during training) while acknowledging that direct
CSR inference requires infrastructure that doesn't exist yet.

---

## 2. Candidate Mechanism Comparison

### 2.1 Signal Availability at Inference

| Signal | In 32D state? | Available in MistralCGAdapter? | Requires external input? |
|--------|--------------|-------------------------------|-------------------------|
| **Guna** (state[22:28]) | Yes, 6D sigmoid | Yes — every forward pass | No |
| **CSR** (C_s, M, H) | No | No — requires pipeline context | Yes: phoneme provider, coherence engine, entropy wiring |
| **Formula-derived Guna** (CSR→S/R/T) | No | No — requires C_s, M, H | Yes: same as CSR |

### 2.2 Mechanism Evaluation

| Mechanism | Signal source | Conceptual alignment | Architectural fit | Safety | Complexity | Traceability | Value |
|-----------|--------------|---------------------|-------------------|--------|------------|-------------|-------|
| **A. Guna sampling modulation** | state[22:28] | Good — Guna is the causal expression layer | Excellent — follows Vritti gate pattern exactly | High — bounded, off by default | Very low — ~20 lines | Full — metadata events | Moderate-high |
| **B. Guna post-forward residual** | state[22:28] | Good but broadens scope | Poor — requires logit-space intervention | Medium — modifies logits | Medium | Good | Medium |
| **C. CSR latent conditioning** | External CSR provider | Best — uses structural cause directly | Very poor — CSR not available at inference | Low — large new surface | Very high — new provider, new forward path | Good if built | Low (for now) |
| **D. CSR+Guna candidate reranking** | Both | Best | Very poor — requires TwoStageGenerator | Low | Very high | Good if built | Low (premature) |
| **E. Defer CSR+Guna entirely** | N/A | N/A | N/A | Safest | Zero | N/A | No value added |

### 2.3 Detailed Mechanism Analysis

#### A. Guna Sampling-Parameter Modulation (Recommended)

**What it does:** Read state[22:28] after each forward pass. Compute a
composite stability signal (e.g. `turbulence = activity*w1 + velocity*w2
+ accel*w3`). When turbulence exceeds a threshold, tighten sampling
(cool temperature, reduce top-k). When lucidity is high, optionally
relax constraints slightly.

**Why it fits:**
- Identical pattern to the existing Vritti gate (lines 559-576 of
  `llm_adapters.py`)
- Guna is already in the state — zero additional compute
- `_guna_to_stability()` in `sovereign_bridge.py` already implements
  the composite signal derivation
- The mapping is concrete: turbulence → tighter sampling is semantically
  clear

**Safety:** Bounded, off by default, cool-only (like Vritti gate), no
logit modification, no state rewrite, no recursion risk.

#### B. Post-Forward Residual Gate

**What it does:** Project Guna into a small (vocab-size or embed-dim)
vector that multiplicatively gates logits before sampling.

**Why not (for now):**
- Modifies logits directly — larger blast radius than sampling-only
- Requires a learned projection head (new trainable parameters at
  inference)
- Unclear how to train the projection without end-to-end inference
  tuning
- The Vritti gate deliberately avoids logit modification for safety

#### C. CSR Latent Conditioning

**What it does:** Run the CSR phoneme provider at inference time,
inject CSR embeddings into hidden states or use them to condition the
adapter.

**Why not (now):**
- CSR phoneme provider is training infrastructure (~2800 lines), not
  designed for low-latency inference
- Requires loading G2P models, phoneme dictionaries, pre-computed
  affinity tables
- Latency impact is significant (per-token phoneme lookup + scoring)
- No existing wiring in MistralCGAdapter
- The prior promotion audit explicitly recommended against CSR first

#### D. CSR+Guna Candidate Reranking

**What it does:** After base logits, extract top-K candidates and
rescore via CSR + Guna scoring heads (effectively wiring
TwoStageGenerator).

**Why not (now):**
- Activates the full TwoStageGenerator pipeline (currently dormant)
- Requires all primitive scorers loaded and invoked per token
- Requires TokenPrimitiveCache populated with vocab embeddings
- Large blast radius — replaces the sampling path entirely
- Both the TwoStageGenerator audit and the promotion audit recommended
  against this as a first step

#### E. Defer Entirely

**Why this is tempting:**
- Current Vritti gate is working and validated
- Guna semantics for generation control are less clear-cut than Vritti
- No user request for Guna-based sampling yet

**Why this is not quite right:**
- The directional model identifies CSR→Guna as the causal axis
- The Ontology→Vritti prior was just implemented at training time
- Having no live Guna signal means the energetic axis has zero
  inference representation, while the cognitive axis has both Bhava
  (direct) and Vritti (gate)
- A small Guna gate is low-risk and provides the minimal energetic
  axis representation

---

## 3. Signal Roles

### What CSR should do live: Nothing (yet)

CSR is the structural cause on the energetic axis. At training time, CSR
shapes the model's learned representations (phoneme grounding, resonance
scoring). At inference time, CSR's influence is already **baked into the
model's weights and the state projector's Guna output**. The learned
Guna[22:28] already reflects CSR influence absorbed during training —
this is the training-inference handoff.

Direct CSR at inference would require the phoneme provider, which is
training infrastructure. Forcing it onto the inference path is both
unnecessary (the model already learned from it) and architecturally
expensive.

### What Guna should do live: Bounded sampling modulation

Guna[22:28] provides six independent signals about the model's
energetic state. The most actionable composite is **turbulence** (high
ACTIVITY + VELOCITY + ACCEL) which maps directly to "the model's
internal state is volatile — tighten sampling to stabilize output."

Concrete mapping:
- `turbulence > threshold` → cool temperature (parallel to Vritti gate)
- `lucidity high + stable high` → no action (already stable)
- Default: no effect (gate off or below threshold)

### What Ontology/Vritti should remain responsible for

- **Bhava (Ontology):** Direct causal link via phase adapter → logit
  residual. This is the structural backbone and should not be displaced.
- **Vritti:** Epistemic reliability gate (ERROR/IMAGINATION → cool
  temperature). This operates on the cognitive axis and should not be
  merged with Guna.

### How to avoid collapsing causal and effect axes

The key invariant: **the two gates read different slices and produce
independent effects.**

- Vritti gate: reads state[17:22], computes `error_risk`, modulates
  `effective_temperature`
- Guna gate: reads state[22:28], computes `turbulence`, modulates
  `effective_temperature` (or top-k)

Both can fire in the same step. When both fire, the most conservative
(coolest temperature, smallest top-k) wins. This is additive
conservatism, not axis collapse.

The gates are conceptually distinct:
- Vritti asks: "Is the model confused?" (cognitive quality)
- Guna asks: "Is the model volatile?" (energetic stability)

---

## 4. Minimum Safe Promotion Target

### Promote state-Guna only, via sampling modulation

**What:** A `Guna stability gate` that reads state[22:28], computes a
turbulence composite, and cools temperature/tightens top-k when
turbulence exceeds a threshold.

**Why Guna first (not CSR):**
- Guna is in the 32D state, available on every forward pass
- CSR is not available at inference without major new infrastructure
- The model's learned Guna already reflects training-time CSR influence
- This matches the directional model: CSR→Guna is the cause direction,
  and the training-time causal flow has already been captured in the
  state projector's learned parameters

**Why not CSR first:**
- CSR signals (C_s, M, H) don't exist in the 32D state
- The phoneme provider is training-only infrastructure
- Forcing CSR onto the inference path adds ~2800 lines of dependency
  for marginal live benefit
- The prior inference promotion audit explicitly scored CSR as "poor
  architectural fit, high risk, do NOT promote first"

**Why not CSR-derived Guna:**
- The formula-based CSR→Guna derivation (`guna_derivation.py`)
  requires C_s, M, H as inputs, which come from external pipeline
  signals not available in `MistralCGAdapter`
- The state-projected Guna[22:28] already encodes what the model
  learned about energetic dynamics from training — this IS the
  inference-appropriate Guna representation

**Why not neither:**
- The energetic axis currently has zero live inference representation
- A Guna gate is low-risk (same pattern as the validated Vritti gate)
- It provides the minimal causal-axis representation needed for
  directional alignment

---

## 5. Proposed Inference Insertion Point

### Location: Adjacent to the Vritti gate in `MistralCGAdapter.call()`

**File:** `agentic/agentic_framework/llm_adapters.py`

**Exact insertion:** After the Vritti gate block (lines 559-576), before
temperature application (line 578). The Guna gate would read
`state[0, 22:28]` from the same `outputs.get('state')` tensor already
fetched by the Vritti gate.

```
[current control flow]
Line 551-557: repetition penalty
Line 559-576: Vritti gate → may cool effective_temperature
Line 578-580: temperature application (uses effective_temperature)
Line 582-590: top-k filtering
Line 592-607: top-p filtering

[proposed control flow]
Line 551-557: repetition penalty
Line 559-576: Vritti gate → may cool effective_temperature
NEW:          Guna gate → may further cool effective_temperature
                          or reduce effective_top_k
Line 578-580: temperature application
Line 582-590: top-k filtering (using effective_top_k if modified)
Line 592-607: top-p filtering
```

**Key property:** Both gates read from the same state tensor, both
produce conservative-only modulation, and the most conservative
result wins. No interaction between gates — they are independent.

### Alternative: Separate effective_top_k path

If the Guna gate modulates top-k rather than (or in addition to)
temperature, the generation loop would need a small addition: an
`effective_top_k` variable alongside `effective_temperature`, modified
by the Guna gate before the top-k filtering step.

---

## 6. Safety Constraints

| Constraint | Specification |
|------------|--------------|
| **Off by default** | `enable_guna_gate: bool = False` (config flag) |
| **Bounded effect only** | Temperature can only decrease, top-k can only decrease. No warming, no broadening. |
| **No logit modification** | Gate modulates sampling parameters only — logits tensor is never touched |
| **No state rewrite** | Gate reads state, never writes. No same-pass recursion. |
| **Confidence threshold** | Gate fires only when turbulence exceeds a hardcoded threshold (e.g. 0.6). Below threshold, zero effect. |
| **Neutral on ambiguous states** | When Guna signals are near-uniform (sigmoid midpoint ~0.5 for all components), turbulence is moderate and gate does not fire. Verified: uniform sigmoid → activity=0.5, velocity=0.5, accel=0.5 → turbulence = 0.5*0.3 + 0.5*0.3 + 0.5*0.2 = 0.40 < 0.6 threshold. |
| **Greedy bypass** | Gate is skipped entirely when temperature=0 (same as Vritti gate) |
| **Full trace metadata** | Every firing logged in `last_cg_metadata['guna_gate_events']` with step, turbulence value, action, base/effective parameters |
| **No interaction with Vritti gate** | Both gates independently modulate effective_temperature. No cross-gate communication. |

---

## 7. Anti-Roadmap: What NOT to Do First

| Do not... | Why |
|-----------|-----|
| **Promote CSR as the causal basis for live inference** | CSR signals (C_s, M, H) are not in the 32D state. The phoneme provider is training infrastructure. Forcing it onto inference adds massive complexity for marginal benefit. The model's learned Guna already reflects CSR's training-time influence. |
| **Promote Ontology/Vritti as the causal basis when the canonical model says CSR+Guna are cause** | Vritti is already live as an epistemic gate — this is its correct role as the *effect* axis readout. Adding Guna as a separate energetic gate is the right way to represent the causal axis, not expanding Vritti's scope. |
| **Activate all dormant primitive heads** | The six-primitive TokenEvaluationTensor and TwoStageGenerator are training infrastructure. Per-token primitive scoring at inference is premature and high-risk. |
| **Widen to full raw state control** | Do not feed all 32D to a learned gate. Read specific slices (Guna[22:28]) for specific, bounded actions. |
| **Introduce TwoStageGenerator first** | It replaces the entire sampling path. Individual gates (Vritti, Guna) are much safer incremental steps. |
| **Make CSR/Guna rewrite hidden state** | The Mistral backbone is frozen. CG signals should modulate sampling parameters, not inject into the forward pass. |
| **Create an unbounded second control stack** | The Guna gate should be a peer of the Vritti gate (same pattern, different slice), not a separate control framework. |
| **Use the formula-based CSR→Guna derivation at inference** | It requires pipeline-level C_s/M/H that don't exist in MistralCGAdapter. Use the state-projected Guna instead — it's the inference-appropriate representation. |

---

## 8. Final Recommendation

**Promote state-Guna via sampling modulation next, using the Vritti
gate pattern. Keep CSR indirect.**

The minimum safe CSR+Guna-first inference mechanism is a **Guna
stability gate** that reads the 6D Guna slice from the already-computed
32D sovereign state and modulates sampling parameters (temperature
and/or top-k) when the model's energetic state indicates turbulence.
This requires approximately 20 lines of code in the same location as the
existing Vritti gate, follows the identical pattern, and provides the
minimum energetic-axis representation at inference.

CSR should remain off the live generation path. CSR's causal influence
on Guna is a training-time relationship — the state projector's learned
Guna[22:28] already incorporates whatever CSR grounding the model
absorbed. Direct CSR at inference would require loading the phoneme
provider (~2800 lines, G2P models, phoneme dictionaries) for signal
construction, which is architecturally inappropriate for the current
MistralCGAdapter. If direct CSR inference is ever desired, it requires
a separate design phase to build lightweight CSR signal extraction from
the model's hidden states — not the full phoneme provider.

**Decision rule:** Promote Guna only via sampling modulation, keep CSR
indirect. This is the smallest coherent patch that gives the energetic
(causal) axis live inference representation, consistent with the
directional model's structure, without requiring infrastructure that
doesn't exist.
