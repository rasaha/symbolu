# Latent Semantic Token Bridge (LSTB) — Explainer

**Source:** `LATENT_SEMANTIC_TOKEN_BRIDGE_DESIGN.md` (2026-02-25)
**Purpose:** This document explains the LSTB to someone who knows ML/AI but
hasn't been inside the SymbolU codebase.

---

## The Problem: Two Worlds That Don't Talk

Modern LLMs reason in **token space** — they predict the next word.
SymbolU's cognitive systems reason in **latent semantic space** — they track
meaning, intent, and epistemic state as continuous 32-dimensional vectors.

These two spaces have fundamentally different units, objectives, and failure
modes:

| Property | Token Space (LLM) | Latent Semantic Space (SymbolU) |
|---|---|---|
| Unit | Discrete token IDs | Continuous 32D state vector |
| Objective | Next-token prediction | State trajectory prediction |
| Where meaning lives | Distributed across attention | Structured coordinates |
| Failure mode | Hallucination (confident nonsense) | Collapse (everything maps to same point) |

The LSTB is the **bridge** between these two worlds — a bidirectional
translation layer that lets token-level processing inform semantic reasoning
and vice versa.

---

## What the 32D "Sovereign State" Encodes

SymbolU's core representation is a 32-dimensional vector with structured
partitions, each grounded in Sanskrit cognitive science:

| Dims | Name | What It Tracks |
|---|---|---|
| 0–11 | **Bhavas** | 12 ontological aspects (what kind of thing is being processed) |
| 12–16 | **Koshas** | 5 consciousness sheaths (processing depth — surface to core) |
| 17–21 | **Vrittis** | 5 mental modifications (is this perception? inference? memory?) |
| 22–27 | **Gunas** | 6 energy states (active / balanced / inert) |
| 28–31 | **Sankalpa** | 4 goal/intent dimensions (what the system is trying to do) |

This isn't arbitrary — each partition has a distinct activation function
(softmax, sigmoid, tanh) enforcing the right mathematical constraints for
its semantic role.

---

## Architecture: Three Options, Staged Delivery

The design proposes three bridge architectures with increasing ambition:

### Option A: Read-Only Bridge (Probe + Monitor)
- LLM hidden states are **projected** into 32D space and observed
- Ontological/JEPA systems read but never write back to the LLM
- **Status: ~80% implemented.** This is what the hard probes validate today
- Analogy: a dashboard monitoring engine telemetry

### Option B: Causal Conditioning (Phase Rotation)
- Bridge becomes **bidirectional** — semantic state rotates the LLM's
  hidden states via learned phase shifts
- The 32D state *influences* next-token prediction without replacing it
- **Status: designed, not yet trained**
- Analogy: a co-pilot that nudges the steering wheel

### Option C: Latent Reasoning Loop
- LLM pauses token generation, reasons in continuous latent space for
  multiple steps, then resumes
- Inspired by Meta's Coconut (Chain of Continuous Thought)
- **Status: research frontier**
- Analogy: "thinking silently" before speaking

The recommended path is **A → B → C**, with kill gates at each stage: if
probes can't detect meaningful structure in hidden states (A fails), there's
no point building a write-back channel (B).

---

## The Subsystems Feeding the Bridge

The bridge doesn't operate alone. Multiple systems produce signals it
integrates, organized by an explicit **authority gradient**:

### Authority Hierarchy

```
DEFINES meaning  → Ontology Head (12D projection) — the ONLY authority
ROUTES priors    → Kosha (soft router / weighting lens)
WEAK priors      → CSR, JEPA, Vritti, Guna — bounded perturbations
MEASURED         → Bliss (coherence functional) — never injected
```

### Weak Priors (Bounded Contributors)

1. **JEPA** (Joint Embedding Predictive Architecture) — predicts *where*
   the latent state is heading. Provides trajectory forecasts that detect
   when the LLM is about to go off-track. Enters hidden state as a
   bounded prior, not as ontology axis definition.

2. **CSR** (Consonant-Syllable Resonance) — a weak acoustic prior that
   extracts ontological affinity vectors from phoneme patterns via
   Sanskrit varna semantics. CSR injects small, bounded perturbations
   into transformer hidden states, gated by confidence and Bliss
   coherence. CSR has NO authority — it cannot define ontology axes.

3. **Vritti** — cognitive-mode typing (valid cognition / imagination /
   misperception / inertness / memory). A distribution that weights
   templates, penalties, hedging, and recursion mode.

4. **Guna** — Pranamaya energy modulation. Gain/entropy/temperature-like
   modulation (stability vs. acceleration). NOT "bliss."

### Router

5. **Kosha** — soft router / weighting lens. Kosha produces weights that
   determine how much each weak prior matters ("depth emphasis"), not
   "what is true."

### Authority

6. **Ontological Axes** — validated semantic coordinates. The 12D Bhava
   subspace provides interpretable dimensions for measuring where a
   representation sits in meaning-space. This is the ONLY layer allowed
   to define meaning axes.

### Coherence Measure

7. **Bliss** — the integrated representational surface where all weak
   priors reconcile. Bliss is measured (not injected) as a scalar
   functional: B = mean(cosine agreement with priors) − β·(cross-layer
   instability). When B drops, injection strengths automatically decrease
   to prevent runaway.

---

## Three-Signal Governance (Disagreement Detection)

The system's key safety mechanism is a **three-signal governor** that
detects when the LLM's token-level behavior diverges from semantic
expectations:

| Signal | What It Measures | Detection AUC |
|---|---|---|
| **Trajectory** | Is the latent state going where JEPA predicted? | 0.515 (weak alone) |
| **Ontology** | Has the representation drifted from its semantic cluster? | 0.717 |
| **Residual** | Does the prediction error have coherent semantic structure? | 0.793 |

No single signal is reliable. The governor uses **disagreement** between
signals — when trajectory says "fine" but ontology says "drifting", that
conflict itself is the strongest indicator of trouble. This is analogous to
instrument cross-checks in aviation.

---

## Anti-Collapse Training

The biggest risk in bridging continuous and discrete spaces is
**representation collapse** — the bridge learns to map everything to the
same point (trivial solution, zero loss, zero information).

The design specifies four anti-collapse objectives:

```
L_total = L_tok + α·L_JEPA + β·L_VICReg + γ·L_structured + δ·L_contrastive
```

- **L_tok**: standard next-token prediction (keeps the LLM working)
- **L_JEPA**: latent trajectory prediction (keeps semantic space predictive)
- **L_VICReg**: variance-invariance-covariance regularization (prevents
  collapse by enforcing that dimensions stay decorrelated and spread out)
- **L_structured**: Kosha/Vritti supervision (forces the 32D partitions to
  track their designated cognitive roles)
- **L_contrastive**: pulls aligned token-semantic pairs together, pushes
  misaligned pairs apart

---

## Bliss Governance and Injection Discipline

All weak priors (CSR, JEPA, Vritti, Guna) are injected into the hidden
state under strict discipline:

1. **Normalize** the prior vector (L2 per token)
2. **Small init** for projection weights (std=0.01)
3. **Confidence gate** (each prior carries a confidence scalar)
4. **Post-LayerNorm** injection (never pre-LN)
5. **Small λ** (start ≤ 0.05, ramp slowly)
6. **Bliss-gated**: λ_eff = λ · σ(γ(B − τ))

When Bliss (coherence) drops, injection strengths automatically decrease.
This prevents any single prior from "taking over" the representation.

Bliss is NOT another term in the loss function or relevance equation.
It modulates the gates that feed the priors — the downstream scoring
stack (relevance, redundancy, domain jumps) is unchanged.

---

## What's Proven vs. What's Not

**Validated (Phase 2):**
- Hidden states contain extractable ontological structure (probe AUC > 0.7)
- 32D Sovereign State dimensions are non-degenerate (VICReg holds)
- Three-signal disagreement detection works on synthetic data
- Phoneme CSR produces discriminable acoustic-ontological features

**Not yet proven:**
- Whether the bridge transfers to real (non-synthetic) data
- Whether Phase B write-back actually improves generation quality
- Whether anti-collapse training scales
- Whether latent reasoning (Phase C) is feasible at all
- Whether Bliss coherence functional improves training stability
- Whether weak-prior injection discipline prevents authority inversion

The document is honest about this: each phase has an explicit kill gate.
If the probes fail, the architecture proposal is wrong and should be
revised, not forced.

---

## Key Insight

Most hybrid AI architectures bolt symbolic systems onto neural nets as
post-hoc interpretability tools. The LSTB proposes something different:
**the symbolic structure is the reasoning space**, and the token-level
LLM is the I/O interface. The bridge isn't an add-on — it's the claim
that continuous structured reasoning and discrete token prediction can
be two views of the same process, connected by a learnable
bidirectional projection.

Whether that claim holds is what the phased validation is designed to
answer.
