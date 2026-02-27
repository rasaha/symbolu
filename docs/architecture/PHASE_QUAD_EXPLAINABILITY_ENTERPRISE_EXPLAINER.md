# Phase Quad Explainability — Explainer

**Source:** `PHASE_QUAD_EXPLAINABILITY_ENTERPRISE.md` (2026-02-25, V2.0.0)
**Purpose:** Explains Phase Quad's explainability architecture to someone
who knows ML/AI but hasn't been inside the SymbolU codebase.

---

## The Problem: Transformers Are Black Boxes

Standard transformer LLMs have a single computation path — stacked
self-attention layers. Explaining *why* a model produced a given output
requires post-hoc tools (attention visualisation, saliency maps, probing
classifiers) that are approximate, fragile, and disconnected from the
actual computation.

Enterprise deployments in regulated industries (finance, healthcare, legal)
need explanations that are **structural** (derived from the computation
itself), not **forensic** (reconstructed after the fact).

Phase Quad is designed so that explainability is a byproduct of the
architecture, not an add-on.

---

## Core Idea: Three Named Paths Instead of One

Where a standard transformer has one computation path (self-attention →
FFN, repeated), Phase Quad splits processing into **three named paths**
that combine additively:

| Path | What It Does | Cost | Analogy |
|---|---|---|---|
| **Local Attention** | Standard windowed self-attention | O(n·w) | Reading the current page |
| **Phase Accumulator** | Continuous phase rotation tracking long-range rhythm | O(n) | Remembering the chapter's arc |
| **Quad Retrieval** | Key-value lookup into external memory blocks | O(n·k) | Checking reference material |

Every output token gets a **path attribution triple** — what fraction of
its representation came from each path:

```
local_ratio=0.45, phase_ratio=0.30, quad_ratio=0.25
```

This is not a post-hoc estimate. It falls directly out of the gating
scalars that weight the three paths during the forward pass.

---

## Explicit Gate Scalars

Each path is controlled by learned scalar gates that are **inspectable at
inference time**:

- **Amplitude gates** — how much each attention head contributes
- **Phase rotation** — angular displacement tracking sequential structure
- **Proposal gates** — whether to write to external memory
- **Quad read gate** — whether to read from external memory
- **Alignment modulator** — how strongly retrieval results are trusted

These aren't hidden inside matrix multiplications. They are named,
logged, and policy-checkable.

---

## Stability Signals (Phase Quad's Native Telemetry)

Because phase is a first-class quantity (not a metaphor), the system
produces stability diagnostics that have no equivalent in standard
transformers:

| Signal | What It Measures | Healthy Range |
|---|---|---|
| **R_k** (mean resultant length) | Phase coherence across heads | > 0.3 |
| **Phase drift** | Rate of angular change between layers | < 0.5 rad/layer |
| **Head redundancy** | How many heads are doing the same thing | < 0.7 |
| **Amp-phase correlation** | Whether amplitude and phase agree | > 0.2 |
| **Phase confidence** | Certainty of the phase estimate | > 0.5 |
| **Cache hit rate** | How often retrieval finds relevant blocks | context-dependent |

When R_k drops (heads are incoherent) or phase drift spikes (the model's
internal rhythm is breaking down), these are **early warning signals** —
detectable before the output degrades.

---

## Four Explanation Layers (Telemetry Contract)

The document defines a structured telemetry API with four layers, each
serving a different consumer:

| Layer | What It Answers | Consumer |
|---|---|---|
| **A — Path Attribution** | "Which computation path dominated?" | Product teams, dashboards |
| **B — Attention Provenance** | "What content blocks were retrieved and how relevant were they?" | RAG systems, grounding audits |
| **C — Stability & Drift** | "Is the model's internal state coherent?" | Ops/SRE, safety monitors |
| **D — Policy & Confidence** | "What confidence band is this in, and did any policy trigger?" | Compliance, enterprise policy engines |

Each layer exports as flat JSON for logging backends. Layers are
independent — an enterprise can consume Layer A without needing Layer C.

---

## The 32D Sovereign State (Structured Bottleneck)

At each layer, hidden states are projected into a 32-dimensional
**Sovereign State** vector with three separated planes:

| Plane | Dims | Role |
|---|---|---|
| **Phase Plane** | 12D | Ontological aspect distribution (what kind of thing) |
| **Control Plane** | 16D | Kosha depth, Vritti mode, Guna balance (how to process) |
| **Learning Plane** | 4D | Sankalpa / intent (what the system is trying to do) |

This acts as an **information bottleneck** — the 32D vector is small
enough to inspect, structured enough to reason about, and rich enough
to carry the cognitive state. It's the system's self-report, available
every layer.

---

## Confidence-Gated Escalation

A **ConfidenceGate** module converts internal signals into a behavioural
confidence score that drives escalation:

| Confidence Band | Behaviour |
|---|---|
| **High** (> 0.7) | Respond directly, full autonomy |
| **Medium** (0.3–0.7) | Flag uncertainty, may request clarification |
| **Low** (< 0.3) | Escalate to human, withhold autonomous action |

This is policy-checkable: an enterprise can set the threshold for
escalation, and the confidence score is part of the telemetry payload.

---

## Policies as Code

The document specifies an `EnterprisePolicyEngine` that evaluates
`PolicyRule` objects against telemetry:

```python
PolicyRule(
    name="require_grounding",
    condition=lambda t: t["quad_ratio"] < 0.1,  # no retrieval used
    action="flag",
    message="Response not grounded in retrieved content"
)
```

Rules are composable, domain-specific, and follow a
**most-restrictive-action-wins** logic. 11 built-in rules cover common
enterprise concerns (grounding thresholds, stability requirements,
confidence minimums, drift detection).

This is the key enterprise value proposition: **the same signals that
make the model work are the signals that make it auditable.**

---

## Enterprise Use Cases

The document maps telemetry to five enterprise classes:

1. **Regulated industries** — prove grounding (quad_ratio), prove stability
   (R_k), prove confidence (escalation level) for audit trails
2. **Customer support** — detect over-reliance on stale context via cache
   hit rate and phase drift
3. **Knowledge work / search** — enforce minimum grounding thresholds
   before surfacing answers
4. **DevOps copilots** — trace code suggestions back to retrieved blocks
   with attention provenance
5. **Security / insider risk** — detect adversarial drift and prompt
   injection via stability anomalies

---

## Vs. Standard Transformer Explainability

| Capability | Standard Transformer | Phase Quad |
|---|---|---|
| Path attribution | Not available (single path) | Native (three named paths) |
| Stability signals | Not available | R_k, phase drift, head redundancy |
| Confidence gating | Post-hoc calibration | Structural (ConfidenceGate module) |
| Policy enforcement | External wrapper | Inline telemetry + policy engine |
| Temporal reasoning | Positional encoding (opaque) | Phase accumulator (inspectable angle) |
| Adversarial detection | Separate classifier needed | Drift / coherence anomalies |

The honest caveat: Phase Quad hasn't yet been validated at frontier scale
(>100B parameters). The architectural properties hold in current
implementations, but scaling behaviour is an open question.

---

## Key Insight

Most explainability work tries to reverse-engineer a black box after the
fact. Phase Quad's claim is different: **if you split computation into
named paths with explicit gates, explainability is free.** You don't need
a separate interpretability tool because the forward pass *is* the
explanation — every output carries its own attribution, stability report,
and confidence score as structural byproducts of how the computation
was organized.

Whether this scales to frontier performance while maintaining these
properties is the central open question.
