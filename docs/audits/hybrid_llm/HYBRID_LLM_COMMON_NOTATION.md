# Hybrid LLM vNext — Common Notation & Mechanism Comparison

**Audit date:** 2026-08-03

To compare internal and external mechanisms on the same footing, express every recurrent sequence mixer as
a **fast-weight associative memory**:

```
S_t = F_t(S_{t-1}) + W_t          # state transition (forget/erase) + write
y_t = R(q_t, S_t)                 # read
```

where `S_t` is a bounded matrix (or diagonal/complex) state, `F_t` is the transition (decay/erase), `W_t`
the write, and `R` the read. The capabilities that matter for the intended use (long-context retrieval,
relational binding, supersession/version replacement) hinge on **how much independent control each
mechanism has over forgetting, erasing, writing, and collision handling.**

## 1. Mechanism specializations

Let `k_t, q_t` be (projected) keys/queries, `v_t` values, `β_t` a write strength, `α_t`/`γ_t` decay.

| Mechanism | `F_t(S)` (forget/erase) | `W_t` (write) | `R(q,S)` (read) | State |
|---|---|---|---|---|
| **DeltaNet** | `S(I − β_t k_t k_tᵀ)` (delta correction on the addressed key) | `β_t k_t v_tᵀ` | `q_tᵀ S` | matrix `d_k×d_v` |
| **Gated DeltaNet** | `α_t · S(I − β_t k_t k_tᵀ)` (**scalar** decay + delta) | `β_t k_t v_tᵀ` | `q_tᵀ S` | matrix |
| **KDA / Kimi Linear** | **channel-wise** gated `S(I − …)` via DPLR transition | channel-wise gated `k_t v_tᵀ` | `q_tᵀ S` (KDA layers) + MLA global | matrix + DPLR |
| **Gated DeltaNet-2** | channel-wise decay **+ decoupled channel-wise erase gate `b_t`** (key-side) | **decoupled channel-wise write gate `w_t`** (value-side) | `q_tᵀ S` | matrix |
| **Mamba-2** | input-dependent diagonal decay `A_t` | `B_t x_t` | `C_tᵀ S` | diagonal/structured |
| **Mamba-3** | **complex-valued** state transition + MIMO | MIMO input | complex read | complex, ~½ size |
| **Phase (internal)** | `cumsum` (no forgetting) or scalar EMA `γ`; **no delta, no erase** | `k_t v_t` with `k=a_k e^{−iφ_k}` (complex) | `Re(q_t·S)/detach(a_q·Σa_k)` | complex diagonal `[B,1,H,D_h]` |
| **Bounded slots (internal, clean)** | LRU eviction + collision-match supersede (`version++`) | competitive write to addressed slot(s) | softmax over slot keys | `M` slots (keys,values,source,version,usage,active) |

## 2. Capability matrix

| Capability | DeltaNet | GDN | KDA | GDN-2 | Mamba-2/3 | **Phase** | **Bounded slots (clean)** |
|---|---|---|---|---|---|---|---|
| Forgetting | none | scalar | channel-wise | channel-wise | input-dep | scalar EMA (opt) | usage/LRU |
| Erasing (correct a prior assoc.) | delta (tied) | delta (tied) | delta (tied) | **decoupled `b_t`** | none explicit | **none** | overwrite/evict |
| Writing | scalar β | scalar β | channel-wise | **decoupled `w_t`** | input gate | complex kv | competitive |
| Overwrite / supersession | implicit | implicit | implicit | **explicit** | no | **no** | **explicit `version++`** |
| Collision handling | delta | delta | delta | erase+write | — | interference (uncontrolled) | address match |
| Source identity | no | no | no | no | no | no | **yes** |
| Channel-wise control | no | no | **yes** | **yes** | partial | no | n/a |
| Correct an incorrect prior association | partial | partial | partial | **best** | no | **no** | yes (discrete) |
| Optimized contemporary kernels | FLA | FLA | FLA + vLLM/SGLang | FLA | mamba-ssm | **none** | **none** |
| Released production checkpoints | small | yes | **yes (MIT)** | **no** | yes | **none** | none |

## 3. Answering the Phase-vs-modern questions directly

1. **What does complex Phase encoding give that DeltaNet-style memory does not?** A phase-rotation
   addressing scheme (interference-based) — but with **no explicit correction/erase**. It buys a different
   *addressing* prior, not a *capability* the delta rule lacks; the delta rule additionally offers exact
   correction, which Phase cannot.
2. **Is Phase a constrained fast-weight memory?** Yes — it is a diagonal complex linear recurrence with a
   detached normalizer, a strict special case of the fast-weight form with **no `(I − βkkᵀ)` term**.
3. **Explicit delta-rule correction?** **No.**
4. **Can it erase an incorrect prior association?** **No** — writes accumulate; there is no key-addressed removal.
5. **Separately control forgetting/erasing/writing?** **No** — a single scalar EMA at most; GDN-2 controls all three channel-wise.
6. **Does its normalization improve stability?** The detached `clamp(a_q·Σa_k, 0.1)` denominator bounds
   readout scale, but is not a learned stability mechanism comparable to gated decay; no matched evidence
   it helps at scale.
7. **Unique interference behavior from complex addressing?** Plausibly, but unmeasured at matched budget;
   internally it produced **no retrieval** and was **decorative**.
8. **Benefit at matched params/compute?** **Not demonstrated.** The matched `phase_lc` ladder shows a
   fluency-only PPL gain and no retrieval; the decisive control (R = gated real linear recurrence) exists
   precisely to isolate what complex phase adds, and Phase did not beat it on any relational task.
9. **Can Phase use optimized contemporary linear-attention kernels?** **No** — it is not delta-rule and
   has no FLA/vLLM path; it would need bespoke kernels.
10. **Worth retaining as the canonical recurrent core?** **No.** It is a strictly weaker special case of
    the modern family on every capability that matters, with no kernel path and no released evidence of
    superiority.

**Phase classification (binding directive applied):** `RESEARCH_ONLY` / `LEGACY_BENCHMARK` /
`EXCLUDED_FROM_PACKAGING`. The disposition vocabulary options `CANONICAL_CORE`, `OPTIONAL_AUXILIARY`, and
`MODERNIZE_PHASE_CORE` are **not available** under the directive and are not selected.

## 4. Bounded slots vs modern linear memory

- **Do slots provide discrete addressability absent in Phase?** Yes — content-addressed slots with hard
  eviction, `version++` supersession, and source identity (the clean `BoundedBindingSlots`).
- **Would GDN-2 / KDA remove the need for slots?** For *smooth* associative recall and correction,
  largely yes — a channel-wise erase/write delta state already supports revising key→value bindings.
  Slots remain distinctive only for **discrete, inspectable, metadata-carrying** memory (source, version)
  — i.e. an **enterprise-memory** feature, not a basic-LM requirement.
- **Better as a small external associative memory?** Yes — treat slots as an **optional auxiliary/sidecar**
  over a modern recurrent backbone, not as the backbone.
- **Disposition (independent of Phase):** `EXPERIMENT_REQUIRED` → `OPTIONAL_ENTERPRISE_MEMORY`. Current
  evidence supports only fragile single-fact recall (1/3 seeds); slots may enter the package only after
  meeting predefined multi-seed thresholds for binding, source, supersession, multi-key retrieval, and
  causal slots-off degradation. **The backbone must not depend on slots for basic language modeling.**
