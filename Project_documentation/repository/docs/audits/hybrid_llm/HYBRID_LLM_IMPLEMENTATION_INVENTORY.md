# Hybrid LLM vNext — Implementation Inventory & Algorithm Reconstruction

**Audit date:** 2026-08-03 · **HEAD:** `69b3bb94` · Machine-readable twin: [`artifacts/hybrid_llm_implementation_inventory.json`](artifacts/hybrid_llm_implementation_inventory.json)

This document establishes **exactly what algorithms exist**, classifies each, and reconstructs the
core equations **from source**, not from class names or docstrings. All line citations are to
`symbolu/phase_transformer.py` (byte-identical to `symbolu_core/phase_transformer.py` except import
paths). The two most consequential complexity claims below were verified firsthand during the audit.

> **Two implementation families.** A **production family** lives in `phase_transformer.py` (~11k lines,
> versioned V9–V20, several N×N materializations, docstrings that overstate complexity), and a **clean
> reference family** lives in `symbolu/lightweight_phase/` and `experiments/phase_lc/` (auditable,
> `register_shape`-guarded, genuinely sub-quadratic). They implement the *same core equations* but
> diverge sharply on the N×N and decode questions. Where they disagree, the clean family is the reliable
> reference and the production docstrings are the unreliable ones.

---

## 1. "Hybrid LLM" denotes at least five unrelated systems

The label is overloaded. These must **not** be merged into one product identity:

| # | Meaning | Where | Primary category |
|---|---|---|---|
| H-arch | Phase(O(n)) + sliding-window(local) [+ Quad] attention in ONE model | `HybridPhaseTransformer`, `run_hybrid_wiki103.sh`, `train_hybrid_7b.py`, `--model_type hybrid` | MODEL_ARCHITECTURE |
| H-router | Route a query to internal specialized 7B sub-models by phoneme/ontology | `symbolu/hybrid/router.py` (`SemanticRouter`) | MODEL_ROUTER |
| H-handover | Two-tier on-prem-O(n) → frontier-API **handover** scaffold | `agentic/hybrid_handover/` | FRONTIER_HANDOVER |
| H-tokenevent | Dual attention: token path + **event** path over EvidenceRecords | `experiments/hybrid_token_event_attention/` | ATTENTION_OR_SEQUENCE_MIXER (experiment) |
| H-misc | RAG / renderer plumbing | `symbolu/mechanical/renderer/varna_hybrid_renderer.py`, `.../pipeline/rag_hybrid_integration.py` | DOCUMENTATION/PLUMBING |

The repo's own terminology audit already draws this boundary:
`Project_documentation/repository/docs/audits/model_selection/HYBRID_LLM_AND_CONTROL_PLANE_BOUNDARY.md` fixes **"Hybrid LLM = capability
#9 (local/frontier handover)"**, distinct from **"Model Selection = capability #8 (policy-bounded
provider selection)."** Similarly, **"Phase"** the attention mechanism is distinct from the hundreds of
project-"Phase 2/3/47" governance references (`test_phase47_*`, `AGENT_RUNTIME_PHASE3_*`,
`restoration/docs/phase_reports/`) that have nothing to do with it.

**Only H-arch is a model architecture.** The canonical Hybrid LLM package must eventually adopt one
precise identity; this audit treats H-arch as the model family under review and classifies the rest as
adjacent systems.

## 2. Classification summary (full detail in the JSON)

- **MODEL_ARCHITECTURE:** `BindingCacheTransformer`, `OntologicalBindingCacheTransformer`, `HybridPhaseTransformer`, `GCTTransformer`, `lightweight_phase` staged model.
- **ATTENTION_OR_SEQUENCE_MIXER:** `PhaseAttentionLayer`, `LightweightPhaseAttention`, `BindingCacheQuadQuery`, `LocalWindowAttention`/`LocalAttention`, `hybrid_token_event_attention`.
- **MEMORY_SUBSYSTEM:** `BindingCachePhaseState`, `SlotMemoryGCT`, `BoundedBindingSlots`.
- **MODEL_ROUTER:** `SemanticRouter` (H-router), Model Selection Policy (#8).
- **FRONTIER_HANDOVER:** `agentic/hybrid_handover/` (#9), SEEB benchmark.
- **GOVERNANCE_COMPONENT:** LLM Steering Controller (CRS).
- **TRAINING_HARNESS:** `train_unified_llm.py` (shim), `train_unified_llm_clean.py`, `symbolu/training/unified/`, `train_hybrid_7b.py`, `run_*_wiki103.sh`.
- **BENCHMARK_ONLY:** `phase_lc` (Q/L/R/P/PL + A/B/C), `phase_guided_slots[_v2]`, `enterprise_slots_quadratic`.
- **DOCUMENTATION_ONLY:** HYBRID_LLM_VC_BRIEF v1/v2/v3, FALSIFICATION, COMPARATIVE, CLAIM_LEDGER.
- **LEGACY_OR_SUPERSEDED:** reimplemented Phase core without the normalizer (discarded), v1/v2 "HybridPhaseTransformer as product" framing (superseded by v3).

## 3. Reconstructed algorithms (from code)

### A. Local-window attention
- **Clean** (`lightweight_phase/local_window.py:38-98`): left-pad + `unfold` → `scores [B,H,N,W]` (78-82); explicitly "never materializes [N,N]"; carries a `LocalWindowState` ring of the last W tokens for O(1) streaming. **Genuine O(N·W).**
- **Production** (`phase_transformer.py:3778-3862`): `scores = matmul(Q,K^T) # [B,H,N,N]` (3838) + full N×N windowed mask (3842-3852). **Materializes N×N despite its "O(n*w)" docstring (3874).**
- **7B `LocalAttention`** (`:5162+`): `flash` backend O(N·W) (5248-5253); `sdpa`/`unfold` build an N×N mask — admitted "still O(n²) in mask creation" (5266). Complexity depends on whether flash-attn is installed.

### B. Phase recurrent attention (the "Phase core")
`PhaseAttentionLayer` (`:1905-2771`). Reconstructed from the tensor ops:
- Amplitude/phase projections: `phi = pi*sin(phi_raw)` (bounded, 2307-2312); `a_q = 0.05 + 0.95·σ(·)`, `a_k = σ(·)` (2291-2302).
- Complex key/query via `torch.polar` (2407-2408): `q = a_q·e^{+iφ_q}`, `k = a_k·e^{−iφ_k}` (conjugate); `v_complex = v + 0i`; `kv = k·v_complex`.
- **State (recurrence):** no-decay `S_t = cumsum_t(kv)` (2468-2501); decay `S = parallel_ema_scan(kv, γ)`, `γ = 0.97 + 0.0295·σ(decay_logit)` per head (chunked O(N/chunk) scan, `:699-744`).
- **Normalizer (denominator):** `A_t = cumsum(a_k)`; `normalizer = clamp(a_q·A_t, 0.1).detach()` (2549-2584) — **detached**, no gradient.
- **Readout:** `out_t = Re(q_t·S_t)/normalizer = Σ_{j≤t} a_q a_k cos(φ_q−φ_k) v_j / Σ_{j≤t} a_k`.
- **State size:** `[B,1,H,D_h]` complex + `[B,1,H,D_h]` real — **BOUNDED, constant in N.** No N×N.
- **Fidelity note:** an earlier `experiments/phase_lc` ladder used a reimplementation that **omitted the amplitude-normalization denominator** and was **discarded**; all reported A/B/C numbers use the real layer (`experiments/phase_lc/REPORT_ABC.md:71-76`). Production Phase matches the frozen lightweight reference to ≤2.4e-7.

### C. Binding Cache / Phase–Quad design
- **Write side** `BindingCachePhaseState` (`:3197-3504`): key-side-only Phase recurrence; `memory_state = cumsum(k·v)` / EMA; returns `.real [B,N,D]`. No N×N.
- **Read side** `BindingCacheQuadQuery` (`:3507-3775`): **quadratic softmax attention** — Q from tokens, K/V from Phase memory. **Verified firsthand:** `scores = torch.matmul(Q, K.transpose(-2,-1)) # [B,H,N,N]` (3686); full `triu(ones(N,N))` causal mask (3690-3694); **Top-K is taken over the already-materialized N×N matrix** (3712-3713); `V_expanded → [B,H,N,N,D_h]` (3731). The docstring "reduces O(n²) to O(nk)" (3699) and the "O(nk) Top-K cache" claim (3511, 4121) are **false as implemented** — real cost is **O(N²) time + O(N²·D_h) memory**; Top-K only narrows the softmax/gather width, not score construction.
- **Fusion** `BindingCacheBlock/Transformer` (`:3865-4464`): each block = `x + local_out(N×N) + mem_out(N×N)` → dominated by **two** N×N ops per layer; **no KV/state cache** — `forward` always runs the full `[B,N]`.

> **Directive:** do not call Top-K selection linear when a complete N×N matrix is first materialized.
> `BindingCacheQuadQuery` fails this test and is recorded as **quadratic** throughout the audit.

### D. Bounded binding slots
- **Clean `BoundedBindingSlots`** (`lightweight_phase/binding_slots.py:63-205`) — the most complete: state `keys, values, source[B,M], version[B,M], usage[B,M], active[B,M]`; **hard LRU eviction** (120-139), **collision-match → supersede** with `version++` (130-139, 164), **source-identity** written (166), streaming read-then-write per token; O(N·M·D), never N×N (`register_shape("slot_scores",(B,M),n_seq_axes=0)`). M=32 default.
- **Production `SlotMemoryGCT`** (`:8458-10088`): bounded `slot_keys/slot_vals [B,K,D]`, K=64; competitive **EMA soft write** with top-k hard routing (STE) and a semantic-coherence gate; cosine addressing; **read never writes**. **No hard deletion, no version counter, no source identity** — overwrite is soft EMA only. It is a **training-time module** (slots re-initialized per forward; no decode persistence wired).

### E. Hybrid token/event attention
`experiments/hybrid_token_event_attention/` — a model-architecture *experiment*, **Phase-free in every arm**. A "token" is a text token; an "**event**" is a validated `EvidenceRecord` (`event_schema.py`). The event pathway exists **both** learned (`event_attention.py`, bounded K≤16 slot self-attention) and rule-based (`deterministic_event_reasoner.py`, frozen mapper). Measured (CPU): governed event path **+0.63** over vanilla token, **+0.38** on retrieval text (decisive); event-to-event *interaction* over pooling **marginal** (+0.017 all / +0.046 relational, just under the +0.05 bar) but causally confirmed; deterministic reasoner = 1.000 on oracle. Real-Mistral RM1 harness is **RESOURCE_BLOCKED** in-sandbox.

### F. The "unified" model
`train_unified_llm.py` is a **965-byte shim** re-exporting `symbolu.training.unified.train`. `create_model`
(`symbolu_training/training/unified/model_factory.py:113-585`) is a **dispatcher on `config.model_type`**,
**not** hard-wired to Phase:

| `model_type` | Class | Note |
|---|---|---|
| `ontological` (**DEFAULT**, `config.py:31`) | `SymbolU12LLMWithBhava` | standard attention + 12D ontological + 144D bhava |
| `phase` | `PhaseTransformer` | opt-in |
| `hybrid` | `HybridPhaseTransformer` | opt-in (Mechanism H-arch) |
| `standard` | `StandardTransformer` | O(n²) baseline |
| `gct` | `GCTTransformer` | separate quadratic arch |
| `binding_cache` / `ontological_binding_cache` | `BindingCacheTransformer` / ontological | opt-in |
| `mistral_hybrid` / `mistral_cg` | frozen-Mistral wrapper | opt-in |

**Do not infer architecture from the filename:** by default the unified trainer trains the *ontological
SymbolU* model, not the Phase/Hybrid transformer. It is a mixture/dispatcher.

## 4. Decode-path finding (verified firsthand)

`HybridPhaseTransformer.forward_with_cache` (`:7706-7769`): when **`local_layers > 0`** (config default 4;
7B uses 16), decode calls `cache.append_tokens(input_ids)` then `self.forward(full_input_ids)` — i.e.
**full-prefix replay** over the growing buffer (7746-7752). The true O(1) recurrent path
(`forward_chunk` + `PhaseStateCache`) is reachable **only for `local_layers == 0`**, and **no shipped
config sets that.** `BindingCacheTransformer`/`BindingCacheInferenceEngine` likewise regenerate over the
full prefix each step (`binding_cache_inference.py:547`). So the advertised "O(1) constant-state decode"
is **not exercised by any shipped configuration** — it is full-prefix replay presented as recurrent
decode. Bounded-state decode is real **only** for the pure-Phase and lightweight arms, which no product
config selects.

## 5. Parameter counts & checkpoints

- Presets (`config.py:1413`): tiny 256/6/4 · small 512/8/8 · medium 768/12/12 · large 1024/16/16 (ff = 4·embed) → ≤~200M-class.
- 7B config (`train_hybrid_7b.py:92-103`): 4096×32L×32H, ff 11008 → LLaMA-7B-shaped; **"7B" is the config, not a trained checkpoint.**
- **Committed model checkpoints for the Phase/Hybrid family: zero** (`experiments/phase_lc/REPORT.md`: "*.pt/*.ckpt/*.safetensors count: 0"). No trained-LM weights or training logs exist.

## 6. Misleading-name flags (integrity)

- `BindingCacheQuadQuery` — advertised O(nk); **is O(N²)**.
- `LocalWindowAttention` (production) — advertised O(n·w); **materializes N×N**.
- `GCT` — shipped beside Phase/"hybrid"; **separate O(n²)+gating arch**, not Phase, not O(n).
- "Hybrid" — five unrelated systems (§1).
- "Model selection" (#8) — governance provider-policy engine, **not** Hybrid-LLM/router (#9).
- `train_unified_llm.py` — a shim; **defaults to the ontological model, not Phase**.
- in-house "O(n) hybrid model" in `hybrid_handover/` — a **deterministic rules stand-in**, not a neural model.

These flags feed the audit-integrity checks: no quadratic path may be recorded as linear, and no
full-prefix replay may be recorded as constant-time decode.
