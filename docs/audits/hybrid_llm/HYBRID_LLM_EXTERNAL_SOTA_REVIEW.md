# Hybrid LLM vNext — External State-of-the-Art Review

**Audit date:** 2026-08-03 · Machine-readable twins:
[`artifacts/hybrid_llm_external_architecture_matrix.json`](artifacts/hybrid_llm_external_architecture_matrix.json) ·
[`artifacts/hybrid_llm_primary_source_registry.json`](artifacts/hybrid_llm_primary_source_registry.json)

Every technical conclusion below cites a primary source (`SRC-*`) in the registry. Secondary explainers
were used only to *discover* primary sources.

> **Access limitation (recorded honestly).** arXiv abstract/HTML pages returned **HTTP 403** through the
> audit egress proxy. Primary-source facts were captured from the arXiv listing metadata, **official code
> repositories** (GitHub), **official model repositories** (Hugging Face), and **official framework
> blogs/docs** (vLLM, FLA), cross-checked across independent results. The Gated DeltaNet-2 facts (license,
> checkpoints, results, update rule) come directly from the **official NVlabs GitHub README**; Kimi Linear
> licensing/checkpoints from the **official moonshotai Hugging Face repos**.

## 1. The frontier has moved to erase/write-decoupled delta-rule linear attention in hybrid stacks

The dominant 2024→2026 trajectory is a **delta-rule linear-attention family** with progressively finer
memory control, deployed as a **hybrid** with a small fraction of full/latent attention:

```
DeltaNet (2024-06)  --gated decay-->  Gated DeltaNet (2024-12)
   --channel-wise gating-->  KDA / Kimi Linear (2025-10)
   --decoupled erase+write gates-->  Gated DeltaNet-2 (2026-05)
```

In parallel, **state-space models** advanced (Mamba-2 → Mamba-3, complex-valued MIMO state), and
**production hybrids** standardized a **3:1 linear:full** layer ratio (Qwen3-Next, Kimi Linear) or a very
low attention ratio over Mamba (Nemotron-H ~8%, Jamba 1:8).

## 2. Candidate families (newest live versions)

### Recurrent / linear-attention cores
- **DeltaNet** (`SRC-DELTANET-2024`, NeurIPS'24): delta rule `S_t = S_{t-1}(I − β_t k_t k_t^T) + β_t k_t v_t^T`; corrects the addressed key. No forgetting gate. MIT kernels in FLA.
- **Gated DeltaNet (GDN)** (`SRC-GDN-2024`, ICLR'25, NVIDIA/MIT): adds a **scalar** decay gate `α_t` (adaptive forgetting). Surpasses Mamba-2 and DeltaNet on LM, recall, length extrapolation. **This is the mechanism most production hybrids actually ship** (Qwen3-Next). MIT kernels.
- **Kimi Delta Attention (KDA) / Kimi Linear** (`SRC-KIMI-LINEAR-2025`, Moonshot): refines GDN's scalar gate into **channel-wise** gating via a Diagonal-Plus-Low-Rank (DPLR) transition and a bespoke chunkwise algorithm; deployed as a **3:1 KDA:MLA** hybrid. Open **48B-A3B** MoE checkpoints (Base+Instruct, ~5.7T tokens), **MIT license**, KDA kernel in FLA, vLLM/SGLang support; reports **−75% KV cache** and **up to 6× decode throughput at 1M ctx**, matching/surpassing full attention across short/long/RL regimes.
- **Gated DeltaNet-2 (GDN-2)** (`SRC-GDN2-2026`, NVlabs, 2026-05): **decouples erase and write** into a **channel-wise erase gate `b_t`** (key-side removal) and **channel-wise write gate `w_t`** (value-side insertion), plus KDA-inherited channel-wise decay; **reduces to KDA** when the gates collapse to a shared scalar and to GDN when decay also collapses. Chunkwise WY with channel-wise decay absorbed into asymmetric erase factors; gate-aware backward pass. At **1.3B / 100B FineWeb-Edu**, **best overall** vs Mamba-2/GDN/KDA/Mamba-3 (Wiki ppl **15.90**, LMB **11.41** recurrent) and **best RULER multi-key retrieval** (MK-NIAH-1@4K 37.8 recurrent / 48.0 hybrid); ablations show the **erase gate drives most of the gain**. **License: NVIDIA Source Code License-NC (non-commercial); no released checkpoints** — a packaging blocker.
- **Mamba-2 / Mamba-3** (`SRC-MAMBA2-2024`, `SRC-MAMBA3-2026`): structured SSM; Mamba-3 adds complex-valued state + MIMO + exponential-trapezoidal discretization, matching Mamba-2 ppl at **half the state / half decode cost**. Apache-2.0. On the GDN-2 paper's own table, Mamba-3 MIMO (16.45/11.66) trails GDN-2.

### Production hybrid stacks
- **Qwen3-Next** (`SRC-QWEN3NEXT-2025`): **3:1 GDN:gated-full-attention**; open weights (Apache), vLLM (Sep 2025) + SGLang native, hybrid KV-cache manager; successor **Qwen3.5-397B-A17B** (Feb 2026). The reference production GDN hybrid.
- **MiniMax-M1** (`SRC-MINIMAX-M1-2025`): Lightning-Attention + softmax MoE hybrid, 1M native context, open weights.
- **Nemotron-H** (`SRC-NEMOTRONH-2025`): ~8% attention / ~92% Mamba-2; up to 3× throughput; open weights. **Jamba** (`SRC-JAMBA-2024`): 1:7 attention:Mamba + MoE; open weights.

### Efficient full-attention (the periodic global layer of every hybrid)
Sliding-window (SWA), grouped-query (GQA), multi-query (MQA), and **multi-head latent attention (MLA)** —
MLA is the compressed-KV global layer in Kimi Linear.

### The July 2026 comparative study
`SRC-LINATT-SURVEY-2026` (arXiv 2607.07953) directly compares **softmax, DeltaNet, GDN, KDA, GDN-2** at
350M/15B (plus 1.3B/3B DeltaNet) on expressivity, decay, erase/write control, throughput, and complexity,
with a **cross-layer routing** analysis. Two conclusions matter for us: **(a)** GDN-2 posts the best
overall averages among recurrent families; **(b)** **hybrid stacks improve validation loss but reintroduce
a portion of the quadratic sequence-length cost** relative to pure recurrent stacks — i.e. the hybrid win
is a *cost/quality trade*, not free.

## 3. Critical counter-evidence: MiniMax-M2 reverted to full attention

`SRC-MINIMAX-M2-2026`: MiniMax's **M2 dropped the M1/Text-01 Lightning-Attention hybrid and returned to
full multi-head attention on all layers**, reporting that **no efficient-attention variant reliably
matched full-attention quality in production** (reasoning/coding/agent tasks). This is a sober, primary
data point: linear-attention hybrids are strong and efficient, but "linear beats full" is **not**
unconditional at production scale. It argues for a **conservative full-attention fallback** and for
treating quality parity as an evidence gate, not an assumption.

## 4. "Latest" vs "greatest"

- **Latest** (newest documented, audit date): **Gated DeltaNet-2** (2026-05) for the mechanism; the July
  2026 comparative study for the analysis; Mamba-3 (2026-03) for SSMs.
- **Greatest** (strongest total evidence for a deployable, licensable core): **Kimi Linear / KDA-MLA**.
  It is the only candidate that combines (i) **released, MIT-licensed, production-scale checkpoints**
  (48B-A3B, 5.7T tokens), (ii) **mature multi-backend kernels** (FLA) with **vLLM + SGLang** support,
  (iii) a **channel-wise gated delta-rule core** only one refinement behind GDN-2, and (iv) a **hybrid
  design that preserves an exact global path** (MLA) — matching/surpassing full attention in its own
  evaluation.
- **GDN-2 is latest and posts the best recurrent-family retrieval numbers, but** its evidence is a
  **single 1.3B/100B point**, it has **no released checkpoints**, and its license is **non-commercial** —
  it is a research frontier, not yet a packageable core.

## 5. Kernel / runtime maturity (packaging-relevant)

`SRC-FLA-LIB`: `flash-linear-attention` provides reference kernels for **DeltaNet, GDN, KDA, and (May 2026)
GDN-2**; TileLang backend for GDN/KDA (Apr 2026); context-parallel for KDA/GDN (Mar 2026). **vLLM**
integrates FLA Triton kernels with a hybrid KV-cache manager; **vLLM and SGLang** auto-dispatch GDN/KDA
kernels for Qwen3-Next / Kimi Linear. So the GDN/KDA branch has **real, maintained, inference-runtime-ready
kernels** — a decisive advantage over any bespoke internal mechanism.

## 6. Bearing on the internal Phase mechanism

Every modern candidate is a **fast-weight associative memory with an explicit correction/erase mechanism**
(delta rule; channel-wise erase in GDN-2). The internal **Phase** mechanism is a **complex-valued diagonal
linear recurrence with a detached amplitude normalizer and no delta correction and no erase gate** — it
cannot correct or supersede a prior key→value association, exactly the capability the frontier has been
racing to improve. This structural gap, combined with the internal evidence (Phase = micro-scale fluency
only, no retrieval, decorative), is why Phase is treated as historical research and the canonical core is
selected from the modern delta-rule family. The common-notation document formalizes this comparison.
