# Phase 0 — Authoritative Quad Traceability & Compatibility Gate

**Study:** Quad Generative Regularization (CPU-only falsification study, v1.3)
**Date:** 2026-07-22
**Status of gate:** ✅ PASSED — all four compatibility questions answered YES. Implementation authorized.

This document is the mandatory Phase-0A deliverable (implementation spec §5). It records the
authoritative mathematical and executable definition of **Quad**, traces it to source, and answers
the four compatibility questions that gate the experiment. It deliberately extracts **only** the Quad
*generative scoring* component from the "Phase-Quad" architecture and does **not** implement, describe,
or test any phase / synchronization / Kuramoto / USE mechanism (spec §3, §30).

---

## 1. Authoritative Quad scoring equation

The authoritative Quad generative score is a per-head, causally-masked, scaled dot-product between a
query drawn from the current token stream and a key drawn from a memory tensor:

```
S^Q_{i,j} = ( W_q · LayerNorm_q(x_i) ) · ( W_k · LayerNorm_m(m_j) ) / sqrt(d_h)
```

- Score shape per head: `[B, H, N, N]`.
- Causal mask: `S^Q_{i,j} = -inf  where  j > i`  (`torch.triu(..., diagonal=1)`).
- The score is consumed **generatively**: Quad selects the Top-K highest-scoring candidate positions
  per query ("proposal"/"librarian" role) and, in standard mode, softmax-weights the Top-K to
  retrieve values. `get_proposals()` returns the **raw pre-softmax score** `[B, N, K]` — this is the
  authentic generative score the study supervises.

This equation is quoted verbatim from the canonical specification (see §2 items 1–2 below), steps 3–4.

## 2. Traceability table (spec §5.2 items 1–14)

| # | Item | Finding |
|---|------|---------|
| 1 | Exact Quad scoring equation | `S^Q_{i,j} = (W_q·LN_q(x_i))·(W_k·LN_m(m_j)) / √d_h`, causal-masked, Top-K selected. |
| 2 | Tensors entering the equation | `x [B,N,D]` (query source), `memory_state m [B,N,D]` (key/value source); optional `binding_salience [B,N]` (selection-only bias). |
| 3 | Tensor shapes | `Q,K,V: [B,H,N,d_h]`; `scores: [B,H,N,N]`; proposals `[B,N,K,D]`, proposal-scores `[B,N,K]`. |
| 4 | Normalization location | `LayerNorm_q` on query input, `LayerNorm_mem` on memory input **before** projection; softmax normalization is over the Top-K candidate axis (`dim=-1`) **after** scoring. |
| 5 | Difference from ordinary dot-product attention | (a) K/V come from a **separate memory tensor** `m`, not the token stream; (b) **Top-K sparse** selection (O(n·k)) instead of dense softmax; (c) selection may be biased by `binding_salience` while the **weighting uses the original unbiased scores** ("selection biased, weighting pure"). With `m=x` and `k≥N` it reduces exactly to standard causal self-attention scoring. |
| 6 | Exposes a causally valid candidate-comparable score? | **YES.** `scores[b,h,i,j]` is an explicit query-i × candidate-j matrix, causally masked, feeding `topk`. `get_proposals` returns it pre-softmax. |
| 7 | Granularity | **Per head, per layer** — one `BindingCacheQuadQuery` per block; H heads. Not global, not output-only. |
| 8 | Separable from phase/state logic? | **YES (mathematically).** The scoring block is pure scaled dot-product; it contains **no** phase/phasor/`cos(φ_i−φ_j)`/cumsum/Kuramoto operation. Phase couples in **only** by supplying the value of `memory_state` (K/V source). Feeding any `[B,N,D]` tensor as `memory_state` computes a valid Quad score without running phase dynamics. |
| 9 | Source document path | `docs/PHASE_QUAD_LOCAL_ATTENTION_ALGORITHM.md` (V11.0, "Status: Production — validated by diagnostic probe experiments"; declares `symbolu/phase_transformer.py` the "canonical implementation"; **Section 4, "Path 2 — Quad Proposal"** is the Quad scorer). Supporting: `docs/HYBRID_PHASE_QUAD_ARCHITECTURE.md`. |
| 10 | Source code path | `symbolu/phase_transformer.py` (canonical); byte-identical mirror `symbolu_core/phase_transformer.py`. |
| 11 | Relevant code symbols | `class BindingCacheQuadQuery` (L3507); `get_proposals()` (L3573, "quad-as-proposer"); `forward()` (L3650); scoring line `scores = torch.matmul(Q, Keys.transpose(-2,-1)) * self.scale` (L3610 / L3686); causal mask (L3613 / L3689); Top-K (L3628 / L3712). |
| 12 | Tests referencing the implementation | `tests/test_hard_probes_benchmark_cli.py` (imports `BindingCacheQuadQuery`, asserts `block.quad_query` path), `tests/test_claims_validation.py`, `scripts/phase_probes/hard_probes/test_hard_probes_d6_control_plane.py`; debug harness `debug_phase_quad_attention.py`. |
| 13 | Version / commit identifier | Canonical doc **V11.0** (Binding Cache Architecture); in-code version tags reach V10.14.10. Repo commit at study start: `8fb8170` (branch `claude/quad-regularization-cpu-6mv93p`). |
| 14 | Math vs. executable mismatch | **None material.** The doc's Section 4 pseudocode (steps 1–8) matches `BindingCacheQuadQuery.forward`/`get_proposals` line-for-line. The doc header cites file offset `:2891`; the actual class is at `:3507` in the current tree (offset drift only — the class name, mode, and math are exact). |

### Formulation selection (spec §5.2 "if multiple formulations exist")

| Formulation | File | Causal? | Candidate-comparable? | Phase-coupled? | Authority | Chosen? |
|---|---|---|---|---|---|---|
| `BindingCacheQuadQuery` | `symbolu/phase_transformer.py:3507` | **Yes** | **Yes** `[B,H,N,N]` | Separable (m supplies K/V only) | **Canonical / production** | **✅ Reference** |
| `QuadRetriever2D` | `symbolu_extensions/vision/quad_retriever.py:25` | No (images, by design) | Yes | Separable | Production (vision port of the above) | Cross-check only |
| `QuadraticBindingHead` (`QuadraticAttentionLayer`) | `resonant_model/heads.py:567` | No (bidirectional benchmark) | Yes (bilinear `+λ·(Ux_i)·(Wx_j)`) | **No phase at all** (phase-free control) | Research control | Confirms phase-free reduction |
| `HierarchicalQuadProposal` | `symbolu/hp_quad.py:284` | No | proposal×slot, not i×j | — | Experimental | Rejected (not per-token-pair) |
| `QuadraticAttentionWithPhaseBias` | `symbolu_core/ontological/symbolu12_bhava.py:240` | optional | scores yes, but bias is `[B,H,1,1]` (constant across candidates → non-discriminative) | **Phase-entangled** | Bhava-layer control | Rejected (entangled, non-discriminative bias) |

**Most recent / validated / production-aligned / appropriate:** `BindingCacheQuadQuery`. It is the only
formulation that is simultaneously (a) declared canonical by the production spec, (b) causal, (c)
natively candidate-comparable per token pair, and (d) test-covered in the production LLM path.

---

## 3. Phase-free reduction used by this study (spec §2, §3)

The implementation spec forbids any separate phase / state / synchronization mechanism (§2, §3) and
requires that at inference **only the ordinary trained Quad model runs**. We therefore instantiate the
authentic Quad scorer with its **mathematically separable core**: `memory_state := hidden states h`.
This is exactly the separation identified in traceability item #8 — Quad with K/V drawn from the same
hidden states it queries. The resulting per-block operation is:

```
S^Q_{i,j} = (W_q·LN_q(h_i)) · (W_k·LN_m(h_j)) / √d_h      (causal, per head)
attention = softmax_j( S^Q_{i,·} )   →   out_i = Σ_j attention_{i,j} · (W_v·LN_m(h_j))
```

No phase tensor, no Kuramoto update, no synchronization order parameter is present anywhere in the
model. The `S^Q` tensor is the authentic Quad generative score and is what the auxiliary loss (Arm D)
supervises. This is a faithful research reproduction of the canonical executable definition restricted
to its phase-independent scoring subset — **not** an invented "Quad-like" equation (§5.1).

---

## 4. Compatibility gate — the four required questions (spec §5.3)

**Q1. Is Quad separable from any phase mechanism?**
**YES.** The scoring math is pure scaled dot-product; it contains no phase operation. Phase, where it
exists in production, only supplies the `memory_state` tensor (K/V source) and a selection-only
salience bias. Setting `memory_state = hidden states` yields a complete, valid Quad score with zero
phase code. (Traceability item #8; confirmed by the phase-free `QuadraticBindingHead` control.)

**Q2. Does Quad natively expose a causally valid relational / candidate-comparable score?**
**YES.** `scores[b,h,i,j]` (`[B,H,N,N]`, causal-masked so `j ≤ i`) is a native query-i × candidate-j
matrix, and `get_proposals()` returns its pre-softmax value as the generative score. No transformation
is required to obtain `S^Q_{i,j}`.

**Q3. Can the score be supervised without changing inference computation?**
**YES.** `S^Q` is already computed in the forward attention path. Exposing it (returning the existing
tensor) adds no operation to the deployed path. The auxiliary loss is a training-only readout; with
`λ=0` the forward output, task loss, and gradients are **bit-identical** to the baseline (verified by
the Arm A vs Arm D0 equivalence test, spec §13). The auxiliary-only code is deletable after training.

**Q4. Can the score be used without forcing Quad into an artificial pairwise interpretation?**
**YES.** The score **is** natively pairwise (query position × key position). We do not impose an
artificial pairwise structure; we read the structure Quad already produces and normalize it over the
causally-visible candidate keys — precisely how Quad itself consumes the score (Top-K / softmax over
`dim=-1`).

**All four answers are YES → proceed to implementation (spec §5.3).**

---

## 5. Auxiliary objective selection (spec §8)

Because Quad natively exposes candidate-comparable scores over causally-visible candidate keys, and
because Quad's **own** consumption of the score is a softmax/Top-K over exactly that candidate axis,
the structurally-native objective is **Option B — Quad candidate classification**:

```
L_QuadAux = − (1/|Q|) Σ_i  log[  exp(S^Q_{i,j+}/τ) / Σ_{j∈C_i} exp(S^Q_{i,j}/τ)  ]
```

- `i` — a query position; `j+` — the correct earlier key position; `C_i` — the causally-visible
  candidate key positions (correct key + selected earlier-key distractors), all `< i`.
- `τ` — temperature (frozen in the pilot).
- The Quad score enters **untransformed** (no sign flip, no re-projection); this is the same softmax
  Quad applies internally, so the objective is native, not a re-interpretation.

**Rejected alternatives and why:**
- *Option A (native consistency/ordering constraint):* the canonical spec defines Quad's score use as
  Top-K + softmax retrieval, i.e. a candidate-selection distribution — it does not define a distinct
  closed-form "consistency" loss to reuse. Option B is the faithful supervised form of that native
  selection distribution, so we prefer B over inventing an "A".
- *Option C (margin loss):* appropriate only when the score is meaningful merely up to ordering.
  Quad's scores are used inside a softmax (magnitude-and-temperature meaningful), so the softmax
  classification (B) matches native semantics better. Option C is retained only as a fallback/robustness
  check if B proves numerically unstable; it is **not** the primary objective.

**Transformation of the Quad score required:** none (identity read of the existing `[B,H,N,N]` tensor,
mean-reduced over heads to `[B,N,N]` for the candidate softmax, matching `get_proposals`' head-mean).

No objective was chosen silently — this selection, its rationale, and the rejected alternatives are
recorded here per spec §8 "Selection rule".

---

## 6. What this study does NOT do (spec §3, §30 — restated for the record)

This experiment evaluates **Quad-native training regularization**. It does not implement or test USE
phase or synchronization mechanisms. Specifically absent from all code in this package: token phase
variables, phase projections, cosine phase-difference losses, Kuramoto synchronization, U1–U5 phase
dynamics, iterative U4 updates, phase clusters, coherence order parameters, USE teacher–student
distillation, KL matching to a USE teacher, and any GPU/CUDA kernel.
