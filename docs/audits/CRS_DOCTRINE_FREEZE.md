# CRS Doctrine Freeze (Phase 1.5)

**Date:** 2026-04-08
**Scope:** Design decisions only — no code changes
**Prerequisite:** Phase 1 audit (`CSR_TO_CRS_MIGRATION_AUDIT.md`) accepted
**Purpose:** Freeze every design ambiguity so Phase 2 coding is precise

---

## A. Doctrine Freeze Summary

Seven decisions are frozen here:

1. **C = bilinear compatibility over existing V_tok (5D) + Kosha slice from O_tok (5D).** No new cache buffer. C reuses the already-cached Vritti profiles and ontological codes. A small learned 10×10 bilinear matrix (or low-rank factored) is the only new parameter set. Context-side concatenates v_ctx (from VrittiTokenScorer) + kosha_ctx (O_ctx[12:17]).

2. **R = current CSRTokenScorer, delegated unchanged.** R_tok (V, d_c) survives. The bilinear form `r_t^T M_csr r_w` stays. This is temporary migration form — final doctrine may decompose R further, but Phase 2 does not touch it.

3. **S = new bilinear semantic compatibility scorer with its own S_tok cache buffer.** S_tok is a learned projection from `[e_w; bhava_w]` where bhava_w = O_tok[w, 0:12]. Context-side projects from `[h_t; bhava_ctx]`. S is NOT base logits with a wrapper — it is a real scored branch with its own learned parameters operating in the Bhava (ontological identity) subspace. S has the same architectural pattern as PlausibilityTokenScorer but with different inputs (Bhava-focused, not full o_w) and separate parameters.

4. **One combined CRS column in T (column 3), not three.** T stays ℝ^{K×6}. Column 3 changes from S_csr to CRS_combined. Internal C, R, S are logged as diagnostics but do not appear as separate T columns. Vritti column (idx 4) stays for now (redundant with C, cleaned up in Phase 3). Router stays 6 weights. Checkpoint-safe.

5. **Semantic firewall lives inside `combine_crs()`.** Not in IntegratedTokenScorer, not in Bliss. CRS owns its own semantic authority. Downstream modules see the already-gated combined score.

6. **C uses no dictionary features in Phase 2. S uses no dictionary features ever.** C operates on learned V_tok + Kosha — both neural. Dictionary-anchored Vritti propensities (from Varna consonant annotations) are a Phase 3 optional enhancement. S is fully learned and context-anchored by doctrine.

7. **Minimum viable Phase 2 = CRSCombinedScorer behind a config flag, one new cache buffer (S_tok), semantic gate with fixed threshold, three diagnostic metrics.** No router changes, no T shape changes, no Vritti column removal.

---

## B. Definition of C

### What C measures

Cognitive compatibility: does this token fit the current mental-state and consciousness-sheath context?

C is NOT "how smart is this token." C is "does the cognitive mode this token belongs to (factual, imaginative, memory-recall, etc.) match the cognitive mode the context is in, AND does the consciousness level this token operates at (material, vital, mental, intellectual, blissful) match the context's active level?"

### Functional contract

```
C(w) = c_ctx^T  M_C  c_tok(w)
```

Where:
- `c_tok(w) = [V_tok[w]; O_tok[w, 12:17]]` — 10D vector, concatenation of:
  - `V_tok[w]` (5D): Cached Vritti profile — softmax distribution over [FACT, ERROR, IMAGINATION, VOID, MEMORY]. Already computed by `VrittiTokenScorer.compute_token_repr()` and cached in `TokenPrimitiveCache.V_tok`.
  - `O_tok[w, 12:17]` (5D): Kosha distribution — softmax distribution over [MATERIAL, VITAL, MENTAL, INTELLECTUAL, BLISSFUL]. Already computed by `TokenOntologyProjector` and cached in `TokenPrimitiveCache.O_tok`.

- `c_ctx = [v_ctx; kosha_ctx]` — 10D vector, concatenation of:
  - `v_ctx` (5D): Context Vritti profile from `VrittiTokenScorer.compute_context_repr(hidden, o_ctx)`. Already computed in `TokenEvaluationTensor.forward()` at `primitives/__init__.py:149`.
  - `kosha_ctx` (5D): `softmax(o_ctx[..., 12:17])`. Already available — the `KoshaDomainRouter` extracts this at `kosha_router.py:167`.

- `M_C` ∈ ℝ^{10×10}: Learned bilinear compatibility matrix. Low-rank factored: `M_C = A_C @ B_C^T` with `A_C, B_C ∈ ℝ^{10×r}`, r=4. Total: 80 parameters.

### Token cache fields

**No new cache buffer.** C_tok is assembled at inference time from two existing caches:

```python
# Inside CRSCombinedScorer.compute_C():
c_tok = torch.cat([
    cache.get_cached_repr("V_tok", candidate_ids),   # (K, 5)
    cache.get_cached_repr("O_tok", candidate_ids)[..., 12:17],  # (K, 5)
], dim=-1)  # (K, 10)
```

### Reused modules

| Module | How reused |
|--------|-----------|
| `VrittiTokenScorer.compute_token_repr()` | Produces V_tok, already cached. C reads from cache, does NOT call scorer again. |
| `VrittiTokenScorer.compute_context_repr()` | Produces v_ctx. Already called in TET forward. CRS receives v_ctx as input, does NOT call scorer again. |
| `TokenOntologyProjector` | Produces O_tok (including Kosha[12:17]). Already cached. C reads slice from cache. |
| `KoshaDomainRouter` | Extracts kosha_ctx. CRS receives this as input from TET/IntegratedTokenScorer. |

### What C does NOT include

- Token embeddings directly. C does not project from embed_dim. It operates entirely in the 10D cognitive subspace.
- Guna energetic profile. Guna[22:28] is energetic quality, not cognitive state. It stays with GunaTokenScorer (column 5).
- Bhava ontological identity [0:12]. That belongs to S.
- Phoneme/resonance features. That belongs to R.

### Initialization

`A_C` and `B_C` initialized via `nn.init.orthogonal_(gain=0.3)`. At step 0, `M_C ≈ small-norm matrix`, so `C(w) ≈ small values` for all candidates. CRS starts dominated by R (which has pre-existing CSR weights) and S (which has its own initialization). C's signal ramps up as `M_C` learns. This is safe — C starts as a weak signal, not a random strong signal.

---

## C. Definition of R

### What R measures

Resonance compatibility: does this token's phonemic-ontological vibration structure align with the context's resonance state?

R captures the Sanskrit Varna-grounded relationship between consonant/vowel structure and the 12 ontological layers (O1–O12). A token whose phonemes activate O8_Purpose and O10_Unifying (e.g. "wife" → W/va + AY/ai + F/pha) resonates differently from one activating O1_Potential and O3_Execution (e.g. "car" → K/ka + AA/a + R/ra). R measures whether the context's resonance state is compatible with each candidate's phonemic signature.

### Functional contract

```
R(w) = r_ctx^T  M_R  R_tok[w]
```

This is exactly the existing `CSRTokenScorer.forward()` at `csr_scorer.py:104-125`:

```python
# Existing code, unchanged:
if self.use_low_rank:
    intermediate = r_ctx @ self.B   # (..., rank)
    m_r = intermediate @ self.A.t() # (..., d_c)
else:
    m_r = r_ctx @ self.M.t()        # (..., d_c)
return m_r @ R_tok.t()
```

Where:
- `R_tok[w]` (d_c=16): Cached token-side resonance representation. Computed by `CSRTokenScorer.compute_token_repr(csr_affinity)` where `csr_affinity` is the 12D phoneme affinity vector from the `CSREmbeddingProvider` pipeline (Token → G2P → ARPABET → Varna → 12D → learned `token_proj`).
- `r_ctx` (d_c=16): Context-side resonance representation. Computed by `CSRTokenScorer.compute_context_repr(hidden, o_ctx)` via MLP from `[h_t; o_t]`.
- `M_R = A_R @ B_R^T` with `A_R, B_R ∈ ℝ^{16×8}`: Learned low-rank bilinear form. These are the existing `CSRTokenScorer.A` and `CSRTokenScorer.B` parameters.

### What current CSR logic becomes R

| CSR component | Becomes | Status |
|---------------|---------|--------|
| `CSRTokenScorer.compute_token_repr()` | `CRSCombinedScorer.compute_R_token_repr()` — or simply delegated | **Unchanged** |
| `CSRTokenScorer.compute_context_repr()` | `CRSCombinedScorer.compute_R_context_repr()` — or delegated | **Unchanged** |
| `CSRTokenScorer.forward()` | Called inside `CRSCombinedScorer.compute_R()` | **Unchanged** |
| `CSRTokenScorer.A`, `.B` parameters | Loaded from existing checkpoint keys | **Unchanged** |
| `R_tok` cache buffer (V, 16) | Stays in `TokenPrimitiveCache` | **Unchanged** |
| `csr_affinity_fn` in cache | Stays — feeds `R_tok` refresh | **Unchanged** |
| 12D phoneme affinity pipeline (`csr_phoneme_provider.py`) | Stays — upstream of R | **Unchanged** |

### Implementation approach for Phase 2

`CRSCombinedScorer` holds a reference to the existing `CSRTokenScorer` instance. `compute_R()` delegates:

```python
def compute_R(self, r_ctx, R_cand):
    return self.csr_scorer(r_ctx, R_cand)  # existing forward()
```

The `CSRTokenScorer` module stays in `conscious_gen` ModuleDict under its existing key `"csr_scorer"`. `CRSCombinedScorer` receives it as a constructor argument. No parameter duplication, no key rename.

### Temporary migration form vs final doctrine

| Aspect | Phase 2 (temporary) | Final doctrine |
|--------|---------------------|----------------|
| R computation | Delegate to CSRTokenScorer as-is | May decompose into sub-signals (voiced/voiceless polarity, varga-group resonance, vowel-layer affinity) |
| R_tok contents | 16D learned projection from 12D affinity | May split into multiple sub-representations |
| Dual-polarity exposure | Collapsed inside the 12D → 16D MLP | May expose voiced/voiceless as an explicit sub-score |
| Consonant Vritti propensities | Encoded in the 12D affinity but not separately accessible | May provide per-varga Vritti hints as auxiliary features for C |

**Phase 2 rule:** R is the existing CSR scorer, invoked unchanged. No new R-specific code is written in Phase 2 except the delegation wrapper.

---

## D. Definition of S

### What S measures

Semantic compatibility: does this token make referential and contextual sense at this position in the sentence?

S is NOT "what the base model already predicts." S is a targeted scorer that measures whether the token's *ontological identity* (what kind of entity/concept it represents in the Bhava manifold) is compatible with the ontological identity the context demands.

The distinction from base logits (`S_base`):
- `S_base` reflects EVERYTHING the transformer learned — syntax, frequency, position bias, attention patterns, co-occurrence statistics. It is the raw language model probability.
- `S` isolates the *semantic identity compatibility* signal: does the Bhava signature of this token (what it IS in the ontological space) match what the context expects?

Example: After "I love my", `S_base` gives high scores to "wife", "mother", "life", "dog", "job" — all are statistically frequent completions. But `S` scores these by ontological identity: "wife" and "mother" have relational-being Bhava signatures (high O8_Purpose, O10_Unifying), while "job" has an instrumental/structural signature (high O3_Execution, O4_Structure). If the context's Bhava state is strongly relational, S differentiates them — something `S_base` alone may not do because "job" is also statistically frequent.

### Functional contract

```
S(w) = s_ctx^T  M_S  S_tok[w]
```

Where:
- `S_tok[w]` (d_s): Cached semantic representation. Computed by:
  ```
  S_tok[w] = f_S_tok([e_w; bhava_w])
  ```
  - `e_w` (embed_dim): Token embedding from the model's embedding matrix
  - `bhava_w` (12D): `O_tok[w, 0:12]` — the Bhava slice of the token's ontological code. This is the 12-dimensional ontological identity distribution (softmax-normalized) covering O1_Potential through O12_Absolving.
  - `f_S_tok`: Two-layer MLP: `Linear(embed_dim + 12, embed_dim // 4) → GELU → Linear(embed_dim // 4, d_s)`
  - `d_s = 16`

- `s_ctx` (d_s): Context-side semantic representation. Computed by:
  ```
  s_ctx = f_S_ctx([h_t; bhava_ctx])
  ```
  - `h_t` (embed_dim): Transformer hidden state at position t
  - `bhava_ctx` (12D): `o_ctx[0:12]` — the Bhava slice of the context's sovereign state
  - `f_S_ctx`: Two-layer MLP: `Linear(embed_dim + 12, embed_dim // 4) → GELU → Linear(embed_dim // 4, d_s)`
  - Architecture mirrors token-side but with separate parameters

- `M_S = A_S @ B_S^T` with `A_S, B_S ∈ ℝ^{d_s × r}`, r=8: Learned low-rank bilinear form. Same pattern as `CSRTokenScorer` and `OntologyCompatibilityScorer`.

### Why Bhava-focused, not full o_w

The 32D ontological code has structured subgroups:
- Bhava[0:12] — ontological identity (what kind of thing). **Semantic.**
- Kosha[12:17] — consciousness sheath. **Cognitive.** → belongs to C
- Vritti[17:22] — cognitive mode. **Cognitive.** → belongs to C
- Guna[22:28] — energetic quality. **Energetic.** → belongs to GunaTokenScorer
- Reserved[28:32] — feedback signals. Not scored.

Using full o_w would leak cognitive and energetic signal into S, blurring the branch boundaries. S should score *meaning compatibility*, which maps to Bhava. This gives each CRS branch a clean, non-overlapping input domain:

| Branch | Ontological input | Dimension |
|--------|-------------------|-----------|
| C | Vritti[17:22] + Kosha[12:17] | 10D |
| R | 12D phoneme affinity (external, not from o_w) | 12D |
| S | Bhava[0:12] | 12D |

### Why S is not PlausibilityTokenScorer

`PlausibilityTokenScorer` (`jepa_scorer.py`) takes `[e_w; o_w]` (full 32D ontological code) as token-side input. S takes `[e_w; bhava_w]` (12D Bhava slice only). The differences:

1. **Input scope:** PlausibilityTokenScorer sees Vritti, Kosha, Guna — cognitive and energetic signals. S sees only Bhava. Different information.
2. **Conceptual role:** PlausibilityTokenScorer measures "is this token physically/causally plausible?" S measures "is this token semantically compatible with the context's ontological identity?"
3. **Parameters:** Fully separate. No weight sharing.
4. **They coexist.** PlausibilityTokenScorer stays as column 2 in T. S lives inside CRS (column 3). They may partially correlate — that's fine. The router can learn to weight them appropriately.

### Token cache fields

**One new cache buffer required:**

```python
# In TokenPrimitiveCache.__init__():
self.register_buffer("S_tok", torch.zeros(vocab_size, semantic_dim))
```

Size: V=50,257 × d_s=16 × 2 bytes (fp16) = ~1.6 MB. Cache grows from ~7.2 MB to ~8.8 MB.

Refresh in `TokenPrimitiveCache.refresh()`:
```python
if self._semantic_scorer is not None:
    self.S_tok[start:end] = self._semantic_scorer.compute_token_repr(
        chunk_emb, o_chunk[:, 0:12]  # embedding + Bhava slice
    )
```

### Initialization

`f_S_tok` and `f_S_ctx` MLPs initialized with `xavier_normal_(gain=0.5)`, biases zeroed. `A_S` and `B_S` initialized with `orthogonal_(gain=0.5)`. At step 0, S produces small but non-zero scores. Unlike C (which starts near-zero), S should have meaningful initial discrimination because it receives the full token embedding — even with random projections, embedding-space distances provide some semantic signal from step 0.

### Checkpoint compatibility

Old checkpoints have no `S_tok` buffer and no `semantic_scorer` parameters. Loading must:
1. Initialize `S_tok` to zeros (default buffer behavior)
2. Accept missing `crs_combined_scorer.semantic_*` keys gracefully (new module not in old checkpoint)
3. The `use_crs_combined_scorer=False` default means old checkpoints load and run without CRS

---

## E. CRS Public Integration Decision

**Decision: Option A — One combined CRS column in T (column index 3).**

T stays ℝ^{K×6} with column order:
```
[S_base, S_ont, S_plausibility, CRS_combined, S_vritti, S_guna]
                                 ^^^^^^^^^^^
                                 was: S_csr
```

Internal C, R, S values are returned by `CRSCombinedScorer.forward()` for diagnostic logging but do NOT appear as separate T columns.

### Justification

**Migration risk — minimal.** T shape is unchanged. Every downstream consumer (`KoshaDomainRouter`, `BlissTokenGate`, `PrimitiveAuxiliaryLosses`, `IntegratedTokenScorer`, `FieldIntegratedSoftmax`, `KoshaRoutingLoss`) continues to operate on a 6-column tensor. No shape-dependent code breaks.

**Checkpoint safety — full.** Router parameter shapes (`nn.Linear(hidden, 6)`) are unchanged. Agreement energy β tensor stays `(15,)`. Old checkpoint loads, runs with old CSR. New checkpoint with CRS enabled loads into same shapes.

**Router complexity — unchanged.** The `KoshaDomainRouter` produces `α ∈ ℝ^6`. With three columns, it would need `α ∈ ℝ^8` (or 7 if Vritti merges with C) — new parameter shape, broken checkpoints, new routing dynamics to tune. Avoided entirely.

**Training stability — higher.** With three separate columns, the router could learn to assign low weight to S, defeating the semantic firewall. With one combined CRS column, the semantic firewall is enforced *inside* CRS before the score reaches the router. The router never sees unfiltered C, R, S — it can only modulate the already-governed CRS combined score. This is architecturally safer.

**Observability — preserved.** `CRSCombinedScorer.forward()` returns:
```python
{
    'crs_score': Tensor,  # (..., K) — goes into T[:, 3]
    'C': Tensor,          # (..., K) — logged, not in T
    'R': Tensor,          # (..., K) — logged, not in T
    'S': Tensor,          # (..., K) — logged, not in T
    'S_gate': Tensor,     # (..., K) — logged, not in T
}
```
Diagnostics log `C_mean`, `R_mean`, `S_mean`, `S_gate_mean` per step. Full branch visibility without polluting the public integration tensor.

### Why Vritti column (idx 4) stays

C internally uses V_tok + Kosha, which overlaps with what VrittiTokenScorer (column 4) computes. Under CRS, column 4 is partially redundant with CRS's C branch.

Phase 2 keeps it because:
1. Removing it changes T from 6 to 5 columns — breaks everything.
2. VrittiTokenScorer has its own separately-trained parameters and its own auxiliary loss (`L_vritti`). Removing it mid-training loses that training signal.
3. The Vritti column can serve as an independent check: if CRS's C branch and the standalone Vritti column diverge significantly, it indicates CRS is learning something new vs just repackaging.
4. Phase 3 decision: once CRS is validated, evaluate whether Vritti column adds value or should be absorbed.

---

## F. Semantic Firewall Decision

**Decision: The semantic firewall lives inside `combine_crs()`, which is a method of `CRSCombinedScorer`.**

Not in `IntegratedTokenScorer`. Not in `BlissTokenGate`. Not in any downstream module.

### Exact mechanism

```python
def combine_crs(self, C, R, S, mode="soft_gated"):
    """
    S_gate = sigmoid(k_s * (S - s_threshold))
    CRS(w) = S_gate * (w_c * C + w_r * R + w_s * S)
    """
    S_gate = torch.sigmoid(self.k_s * (S - self.s_threshold))
    weighted = self.w_c * C + self.w_r * R + self.w_s * S
    return S_gate * weighted, S_gate
```

Parameters:
- `s_threshold` (float, config): Semantic floor. Default 0.3. Fixed hyperparameter in Phase 2 (not learned).
- `k_s` (float, config): Gate sharpness. Default 10.0. Fixed in Phase 2.
- `w_c`, `w_r`, `w_s` (float, config): Branch weights. Default all 1.0. Fixed in Phase 2. Phase 3 may make them learnable or governance-modulated.

### Behavioral verification

| C | R | S | S_gate (k_s=10, thresh=0.3) | CRS |
|---|---|---|---|---|
| 0.8 | 0.9 | 0.2 | sigmoid(-1.0) = 0.27 | 0.27 × (0.8+0.9+0.2) = **0.51 → suppressed** |
| 0.6 | 0.5 | 0.9 | sigmoid(6.0) = 1.00 | 1.00 × (0.6+0.5+0.9) = **2.00 → viable** |
| 0.5 | 0.5 | 0.5 | sigmoid(2.0) = 0.88 | 0.88 × (0.5+0.5+0.5) = **1.32 → moderate** |
| 0.9 | 0.9 | 0.05 | sigmoid(-2.5) = 0.08 | 0.08 × (0.9+0.9+0.05) = **0.15 → killed** |

The non-negotiable rule holds: high R never rescues low S.

### Why not IntegratedTokenScorer

`IntegratedTokenScorer` computes `Z*(w) = B(w) × Σ α_f S_f(w)` across all 6 primitives. It treats all columns of T equally. If the semantic firewall were placed here, it would need to:
1. Know which T column is CRS (hardcoded index dependency)
2. Reach inside CRS to extract S (breaking encapsulation)
3. Apply a gate that interacts with the Bliss gate in complex ways

This mixes abstraction levels. The IntegratedTokenScorer's job is cross-primitive governance (routing + coherence). The semantic firewall's job is intra-CRS governance (semantic authority over resonance/cognition). Different concerns, different modules.

### Why not BlissTokenGate

Bliss measures **cross-primitive disagreement**: when all 6 primitives agree, Bliss is high; when they disagree, Bliss is low. Semantic failure within CRS is not cross-primitive disagreement — it's a within-branch judgment. A candidate could have CRS=low (because S gated it) and all other primitives=low (they agree it's bad) — Bliss would be *high* (low disagreement). The Bliss gate would pass it. Wrong.

The semantic firewall must fire before the CRS score enters T. Bliss and the router never see the un-gated CRS internals. This is the correct layering.

### Interaction with Bliss

After `combine_crs()` gates the score, the combined CRS value goes into T[:, 3]. Bliss then computes disagreement across all 6 columns including the already-gated CRS. This means:

- If semantic firewall suppresses a candidate (CRS → low), and other primitives also score it low → low disagreement → high Bliss. Coherent rejection. Good.
- If semantic firewall suppresses a candidate (CRS → low), but other primitives score it high → high disagreement → low Bliss. Double suppression. Also good.
- If semantic firewall passes a candidate (CRS → medium/high), Bliss operates normally on the 6-column T. No interference.

The firewall and Bliss are complementary, not conflicting.

---

## G. Dictionary Usage Doctrine

"Dictionary features" = static or semi-static per-token properties derived from lexical/ontological lookup tables, not from neural computation. Examples: Varna consonant Vritti propensities (Hope, Craving, Fear), varga-group membership, vowel consciousness-state labels.

### For C

| Aspect | Decision |
|--------|----------|
| Phase 2 dictionary features | **Not required.** |
| Why | C in Phase 2 operates on V_tok (learned Vritti profiles from embeddings) and O_tok Kosha slice (learned from TokenOntologyProjector). Both are neural. This is sufficient for minimum viable CRS. |
| What's available but deferred | The Varna system annotates every consonant with a Vritti propensity: K/ka → Āśā (Hope), P/pa → Ghrṇā (Revulsion), M/ma → Praśraya (Indulgence), etc. (`ARPABET_TO_VARNA` at `csr_phoneme_provider.py:603-667`). These could be used as dictionary-anchored C_tok priors: each token's phoneme consonants map to specific mental propensities, providing a non-learned cognitive prior. |
| Phase 3 option | Add a `C_tok_prior` (V, 5) buffer containing Vritti propensity distributions aggregated from each token's consonant phonemes. C's bilinear form could be extended to `c_tok = [V_tok; Kosha_slice; C_tok_prior]` (15D). This would give C both a learned cognitive signal AND a dictionary-anchored Vritti prior. |
| Status | **Phase 3 optional enhancement. Not phase-2 scope.** |

### For S

| Aspect | Decision |
|--------|----------|
| Phase 2 dictionary features | **Not used.** |
| Phase 3 dictionary features | **Not used.** |
| Final doctrine | **S is fully learned and context-anchored. No dictionary features, ever.** |
| Why | Semantic compatibility is fundamentally contextual. "Bank" means one thing after "river" and another after "savings." No static dictionary can capture this. S must learn from `[e_w; bhava_w]` × `[h_t; bhava_ctx]` — both sides carry contextual information via the embedding and ontological state, which are functions of the training context. Dictionary features would anchor S to context-independent meanings, which is exactly what S must NOT do. |

### For R

| Aspect | Decision |
|--------|----------|
| Dictionary features | **Already in use.** |
| What | The entire R pipeline is dictionary-grounded: `PHONEME_MAP_ARPABET` (static 12D vectors per phoneme, `csr_phoneme_provider.py:463-558`), `ARPABET_TO_VARNA` (static mapping), `VarnaCSRBridge` (static JSON → 12D lookup). These are the "dictionary" of phonemic-ontological structure. |
| How they're used | The 12D affinity vector is computed from static lookup tables, then position-weighted and aggregated per token, then passed through a *learned* projection (`CSRTokenScorer.token_proj`) to produce `R_tok`. The dictionary provides the input; the learned projection refines it. |
| Phase 2 change | **None.** This is already the correct architecture. |

### Summary table

| Branch | Dictionary in Phase 2 | Dictionary in Phase 3+ | Final doctrine |
|--------|----------------------|----------------------|----------------|
| C | No | Optional (Vritti propensity priors) | Learned primary, dictionary optional |
| R | Yes (already built: phoneme → 12D) | Yes (same) | Dictionary-grounded, learned refinement |
| S | No | No | Fully learned, no dictionaries ever |

---

## H. Minimum Viable Phase 2 CRS

The smallest correct implementation that is real CRS and not CSR under a new name.

### Required: new module

**File:** `symbolu_training/training/conscious_generation/primitives/crs_combined_scorer.py`

**Class:** `CRSCombinedScorer(nn.Module)`

Must contain:
- `compute_C(v_ctx, kosha_ctx, V_cand, Kosha_cand) → Tensor` — bilinear over 10D cognitive features from existing caches
- `compute_R(r_ctx, R_cand) → Tensor` — delegates to existing `CSRTokenScorer.forward()`
- `compute_S(s_ctx, S_cand) → Tensor` — bilinear over learned semantic representations
- `combine_crs(C, R, S) → (Tensor, Tensor)` — soft-gated combination with semantic firewall, returns (crs_score, S_gate)
- `compute_S_token_repr(embeddings, bhava) → Tensor` — for cache refresh
- `compute_S_context_repr(hidden, bhava_ctx) → Tensor` — for forward pass
- `forward(...)` → Dict with keys `'crs_score'`, `'C'`, `'R'`, `'S'`, `'S_gate'`

New parameters (not in any existing module):
- `A_C, B_C ∈ ℝ^{10×4}` — C bilinear form (80 params)
- `semantic_token_mlp` — S token-side MLP: (embed_dim + 12) → embed_dim//4 → d_s (two Linear + GELU)
- `semantic_context_mlp` — S context-side MLP: (embed_dim + 12) → embed_dim//4 → d_s
- `A_S, B_S ∈ ℝ^{d_s×8}` — S bilinear form (256 params at d_s=16)
- `s_threshold`, `k_s`, `w_c`, `w_r`, `w_s` — firewall config (fixed, not nn.Parameter)

### Required: one new cache buffer

**In `TokenPrimitiveCache`:** Add `S_tok` buffer `(V, d_s)` with `d_s=16`. Registered via `register_buffer`. Refreshed when CRS semantic scorer is registered. Default zeros for backward compatibility with old checkpoints.

### Required: config flag

**In `config.py`:**
```python
use_crs_combined_scorer: bool = False    # Replace CSR column with CRS combined scorer
semantic_dim: int = 16                   # d_s for semantic representations
crs_semantic_threshold: float = 0.3      # S floor for semantic gate
crs_gate_sharpness: float = 10.0         # k_s for sigmoid gate
```

### Required: model_factory wiring

**In `model_factory.py`:** Behind `use_crs_combined_scorer` flag:
1. Instantiate `CRSCombinedScorer`, passing the existing `csr_scorer` instance
2. Register as `conscious_gen["crs_combined_scorer"]`
3. Register CRS semantic scorer with `token_cache.set_scorers(semantic_scorer=...)`
4. Pass `crs_combined_scorer` to `TokenEvaluationTensor` (which uses it for column 3 instead of standalone `csr_scorer`)

The existing `csr_scorer` key stays in `conscious_gen`. CRS references it, does not replace it.

### Required: TET integration

**In `TokenEvaluationTensor.forward()`:** Behind flag:
```python
if self.crs_combined_scorer is not None:
    # Gather S_cand from cache
    S_cand = cache.get_cached_repr("S_tok", flat_ids).reshape(...)
    crs_result = self.crs_combined_scorer(
        v_ctx=v_ctx, kosha_ctx=_o_ctx[..., 12:17],
        V_cand=V_cand, Kosha_cand=O_cand[..., 12:17],
        r_ctx=r_ctx, R_cand=R_cand,
        hidden=hidden, o_ctx=_o_ctx, S_cand=S_cand,
    )
    s_crs = crs_result['crs_score']  # replaces s_csr in the stack
else:
    s_crs = self._score_bilinear(r_ctx, R_cand, self.csr_scorer)  # old path
```

Column 3 of T becomes `s_crs` instead of `s_csr`. All other columns unchanged.

### Required: diagnostics

Log per step (when CRS is enabled):
- `C_mean`: `crs_result['C'].mean().item()`
- `R_mean`: `crs_result['R'].mean().item()`
- `S_mean`: `crs_result['S'].mean().item()`
- `S_gate_mean`: `crs_result['S_gate'].mean().item()`

These go into the existing metrics dict, printed in the CG diagnostic line.

### Required: CRS branch losses

The existing `PrimitiveAuxiliaryLosses` trains column 3 with a contrastive loss. When CRS is enabled, column 3 is the combined CRS score — the existing loss trains the combined CRS. This is sufficient for Phase 2 minimum viability.

**Optional Phase 2 enhancement (not required for MVP):** Add per-branch losses `L_C`, `L_R`, `L_S` that train each branch individually against ground truth. This can be added after initial CRS validation.

### May be simplified

| Aspect | Phase 2 simplification |
|--------|----------------------|
| Branch weights w_c, w_r, w_s | Fixed at 1.0, 1.0, 1.0 (not learnable) |
| Semantic threshold s_threshold | Fixed hyperparameter (not learned) |
| Gate sharpness k_s | Fixed hyperparameter |
| C bilinear rank | r=4 (minimal, 80 params) |
| S MLP depth | Two layers (matching existing scorer pattern) |
| Per-branch losses | Combined CRS loss via existing PrimitiveAuxiliaryLosses is sufficient initially |
| Vritti column (idx 4) | Keep as-is, redundant but safe |
| Agreement energy pairs | Same count (15), no change |

### What makes this real CRS and not renamed CSR

The minimum viable implementation is real CRS because:

1. **Three separate branches exist.** C, R, S are computed independently with different inputs and different parameters. They are not projections of the same signal.
2. **Semantic firewall operates.** `combine_crs()` gates by S. A candidate with C=0.8, R=0.9, S=0.2 is suppressed. This behavior is not present in current CSR.
3. **S is a new scorer.** S has its own S_tok cache, its own bilinear form, its own MLP. It did not exist before. It scores Bhava-level semantic compatibility, not phonemic resonance.
4. **C uses cognitive features, not phonemic features.** C reads Vritti + Kosha, which CSR never looks at. C is a categorically different signal from R.
5. **Branch diagnostics are logged.** C_mean, R_mean, S_mean are observable. If CRS degenerates to "just R," this shows up immediately as S_mean ≈ constant and C_mean ≈ constant.

---

## I. Phase 2 Guardrails

Phase 2 must NOT:

- **Rename CSRTokenScorer.** The class stays `CSRTokenScorer`. The file stays `csr_scorer.py`. The checkpoint key stays `conscious_gen.csr_scorer.*`. CRS delegates to it. A rename causes checkpoint breakage for zero benefit.

- **Remove the Vritti column from T.** Column 4 (S_vritti) stays even though C partially subsumes it. Removing it changes T shape, breaks router, breaks losses, breaks checkpoints. Phase 3 decision.

- **Change T shape.** T stays ℝ^{K×6}. No new columns, no removed columns. Column 3 changes content (from S_csr to CRS_combined) but not shape.

- **Change router parameter shape.** `KoshaDomainRouter` stays `nn.Linear(hidden, 6)`. The router's 6 routing weights stay. The PRIMITIVE_NAMES list may update the string at index 3 from "csr" to "crs" but the count stays 6.

- **Make the semantic firewall learnable in Phase 2.** `s_threshold` and `k_s` are fixed config hyperparameters. Making them `nn.Parameter` introduces a training instability risk (the network could learn to open the gate fully, defeating the firewall). Phase 3 may revisit with careful constraints.

- **Make branch weights learnable in Phase 2.** `w_c`, `w_r`, `w_s` are fixed at 1.0. Learnable weights require regularization to prevent collapse (network learns w_s → 0, defeating semantic authority). Defer.

- **Add per-branch auxiliary losses as a requirement.** The existing `PrimitiveAuxiliaryLosses` on column 3 is sufficient for MVP. Per-branch losses are a Phase 2 optional enhancement, not a gate for shipping CRS.

- **Touch inference-side code.** `csr_inference.py`, `generation_tracer.py`, and all inference paths are out of scope. CRS lands in training only.

- **Rename `csr_phoneme_provider.py`.** The phoneme provider is infrastructure. Its name is historical. It provides R's input features. Renaming it touches 15+ import sites for zero functional benefit.

- **Break the `use_crs_combined_scorer=False` default.** When the flag is off, the system must behave exactly as it does today. CRS is opt-in. No side effects from the existence of CRS code when the flag is off.

- **Initialize S to zero or near-zero output.** S must have meaningful initial discrimination. The S MLPs should use `xavier_normal_(gain=0.5)`, not `gain=0.01`. S starts with weak but non-trivial scores derived from embedding-space distances. If S starts at zero, the semantic firewall has no signal and CRS degenerates to R-only.

---

## Addendum: Phase 1.5 Doctrine Patch (v1.1)

**Date:** 2026-04-09
**Scope:** Three targeted revisions to the frozen doctrine. No structural changes.

### A. Revised Semantic Firewall Formula

**Previous formula** (Section F, now superseded):
```python
CRS = S_gate * (w_c * C + w_r * R + w_s * S)
# With unnormalized weights (all 1.0), producing values in [0, 3]
```

**Problem:** With S=0.2 and k_s=10, S_gate=0.27, the result 0.27 × (0.8 + 0.9 + 0.2) = 0.51 is not suppressed enough. A score of 0.51 may still rank competitively.

**Revised formula (Option B with normalized weights + sigmoid on S only):**

The complete CRS scoring pipeline, written as one unified formula:

```
(1)  S_raw   = s_ctx^T M_S S_tok[w]  +  α_base · ẑ_base(w)

(2)  S_prob  = σ(S_raw)

(3)  S_gate  = σ(k_s · (S_prob − τ_s))

(4)  CRS(w)  = S_gate · (w_C · C_raw + w_R · R_raw + w_S · S_raw) · S_prob
```

Where:
- `S_raw` is the full semantic signal: learned bilinear + base-logit anchor (step 1 is `compute_S()`)
- `ẑ_base(w)` = standardized base logit for candidate w: `(logit_w − μ) / (σ + ε)` within the K-candidate set
- `S_prob` = sigmoid of the already-anchored S_raw — maps to [0, 1]
- `S_gate` = threshold gate on S_prob — fires when S_prob drops below τ_s
- Steps 2–4 are `combine_crs()` — it receives S_raw (which already contains the anchor)

```python
def combine_crs(self, C_raw, R_raw, S_raw):
    """
    S_raw already includes the base-logit anchor from compute_S().

    Semantic authority is enforced TWICE:
      1. S_gate → threshold-based suppression (sigmoid cliff)
      2. × S_prob → multiplicative scaling (structural floor)

    When S is bad: S_prob < 0.5 AND S_gate << 1 → quadratic suppression.
    When S is good: S_prob ≈ 1 AND S_gate ≈ 1 → near-unity pass-through.
    """
    S_prob = torch.sigmoid(S_raw)
    S_gate = torch.sigmoid(self.k_s * (S_prob - self.tau_s))
    weighted = self.w_c * C_raw + self.w_r * R_raw + self.w_s * S_raw
    crs = S_gate * weighted * S_prob
    return crs, S_gate, S_prob
```

**Parameters (Phase 2 defaults):**
- `τ_s = 0.5` (sigmoid midpoint — the natural boundary between "semantically acceptable" and "not")
- `k_s = 10.0` (gate sharpness)
- `α_base = 0.5` (base-logit anchor weight — minority contributor)
- `w_c = w_r = w_s = 1/3` (normalized, sum to 1)
- All fixed config hyperparameters, not learnable in Phase 2

**Key design properties:**
- S_prob is sigmoid of the COMPLETE S_raw (bilinear + anchor). Not sigmoid of partial signal. The base-logit anchor is fused into S before any gating, so the gate always operates on the full semantic judgment.
- Only S is sigmoid-normalized. C_raw and R_raw stay in their natural bilinear score space. This preserves gradient flow through C and R while making the gate and S-authority well-defined on [0, 1].
- The weighted sum uses raw scores. The CRS output's absolute scale differs from other T columns, but the router compensates via learned α weights — this is standard for mixed-scale primitive columns.
- The `* S_prob` term makes semantic authority *structural*, not just parametric. Even if k_s and threshold are imperfect, the multiplicative S_prob still suppresses low-S candidates.

### B. Worked Suppression Example

Candidate pool after "I love my", with raw bilinear scores from each CRS branch:

| Candidate | C_raw | R_raw | S_raw | S_prob | S_gate | Weighted Sum | **CRS** |
|-----------|-------|-------|-------|--------|--------|-------------|---------|
| "wife" | 1.5 | 1.8 | 1.5 | 0.82 | 0.96 | 1.60 | **1.26** |
| "mother" | 1.3 | 0.8 | 1.2 | 0.77 | 0.94 | 1.10 | **0.79** |
| "life" | 0.5 | 1.6 | 0.3 | 0.57 | 0.68 | 0.80 | **0.31** |
| "car" | -0.2 | 0.4 | -0.5 | 0.38 | 0.23 | -0.10 | **-0.01** |
| "brick" | -0.5 | 2.0 | -1.0 | 0.27 | 0.09 | 0.17 | **0.004** |

**"brick"** has perfect resonance (R_raw = 2.0 — maybe it has strong phonemic structure) but terrible semantics (S_raw = -1.0). Result: CRS = 0.004. **Destroyed.** The 2.0 resonance score is irrelevant because S_prob = 0.27 and S_gate = 0.09 jointly crush it.

**"wife"** has good scores across all three branches. CRS = 1.26. **Wins.**

**"life"** has excellent resonance (R_raw = 1.6, rhymes with "wife") but mediocre semantics (S_raw = 0.3). S_prob = 0.57, S_gate = 0.68. CRS = 0.31. **Survives but ranks below "wife" and "mother"** — resonance alone doesn't elevate it.

Suppression ratios:
- "wife" / "brick" = 315x (high resonance cannot rescue bad semantics)
- "wife" / "car" = 126x (moderately bad semantics crushed)
- "wife" / "life" = 4.1x (moderate semantics penalized proportionally)

### C. Revised S-Branch Anchoring Doctrine

**Previous doctrine** (Section D, partially superseded):
> S starts with weak but non-trivial scores derived from embedding-space distances.

**Problem:** At step 0, the bilinear term `s_ctx^T M_S S_tok[w]` produces near-zero random noise for all candidates. With S_raw ≈ 0 for everyone, S_prob ≈ 0.5 for everyone, S_gate ≈ 0.5 for everyone. The semantic firewall is blind — it halves all scores equally. This means during early training, CRS has no semantic authority, the router adapts without it, and then S "turns on" later causing a training discontinuity.

**Revised doctrine: Additive base-logit residual, fused before gating.**

This is step (1) of the unified formula in Section A above:

```
S_raw = s_ctx^T M_S S_tok[w]  +  α_base · ẑ_base(w)
```

```python
def compute_S(self, s_ctx, S_cand, base_logits_cand):
    """
    S_raw = bilinear(s_ctx, S_cand) + alpha_base * standardize(base_logits_cand)

    The base-logit residual provides semantic signal from step 0.
    The bilinear term learns to refine and can override the prior.
    S_raw is then fed to combine_crs(), which computes S_prob = sigmoid(S_raw)
    and S_gate = sigmoid(k_s * (S_prob - tau_s)). The anchor is fused INTO S_raw
    before any gating — the gate always sees the full semantic judgment.
    """
    s_bilinear = self._score_bilinear(s_ctx, S_cand)  # learned, starts ~0

    # Standardize base logits within candidate set: zero mean, unit variance
    mu = base_logits_cand.mean(dim=-1, keepdim=True)
    sigma = base_logits_cand.std(dim=-1, keepdim=True) + 1e-6
    s_base_norm = (base_logits_cand - mu) / sigma

    return s_bilinear + self.alpha_base * s_base_norm
```

**Parameter:** `alpha_base = 0.5` (fixed, not learnable in Phase 2)

**Why this works:**

At step 0:
- `s_bilinear ≈ 0` (random init)
- `s_base_norm` has meaningful spread: good-base-logit tokens get S_raw > 0, bad ones get S_raw < 0
- S_prob = sigmoid(S_raw) discriminates immediately
- Semantic firewall has signal from the first training step

After training:
- `s_bilinear` grows to O(1) magnitude, dominating the O(0.5) base residual
- S learns Bhava-level semantic compatibility that base logits don't capture
- The base residual provides a permanent gentle prior: if the learned bilinear is uncertain (near zero), the base logit breaks the tie

**Why this does NOT collapse S into raw logits:**

1. **Standardization removes absolute scale.** S sees only the relative ordering of base logits within the K-candidate shortlist, not the raw probability. A token with base logit 5.0 vs 4.8 gets the same standardized difference as 1.0 vs 0.8.
2. **alpha_base = 0.5 is a minority contributor.** The bilinear term has its own parameters, its own gradients (from CRS branch loss), and its own expressiveness (Bhava × hidden state). It dominates within ~100-200 training steps.
3. **Different information.** The base logit captures everything (syntax, frequency, co-occurrence). The bilinear term captures specifically Bhava-level ontological identity compatibility. After training, they provide complementary signals.
4. **Testable.** Log `corr(S_raw, base_logits_cand)` per step. At step 0, correlation ≈ 1.0 (dominated by base anchor). After training, correlation should drop to 0.3-0.6 as the bilinear term diverges.

**What changes in Section D's functional contract:**

The S formula becomes:
```
S_raw(w) = s_ctx^T M_S S_tok[w] + alpha_base * standardize(S_base(w))
```

All other aspects of Section D (S_tok cache, Bhava-focused input, MLP architecture, initialization) remain unchanged. The base-logit anchor is an additive term in `compute_S()`, not a change to S_tok or s_ctx.

### D. Revised Dictionary Doctrine for S

**Previous wording** (Section G, superseded):
> S uses no dictionary features ever. Fully learned, no dictionaries ever.

**Revised wording:**

S uses no dictionary features in Phase 2. S must remain primarily context-anchored and learned — semantic compatibility is fundamentally contextual and cannot be captured by static lookups.

However, the permanent prohibition is softened: future phases may introduce optional semantic ontology tags (e.g., WordNet hypernyms, Bhava-category labels) as auxiliary inputs to S_tok, provided they serve as priors that the learned component can override, not as fixed constraints. Any such features must be:
- Optional (S must work without them)
- Subordinate to the learned bilinear term
- Validated to improve, not degrade, S's contextual discrimination

**Revised summary table row:**

| Branch | Dictionary in Phase 2 | Dictionary in Phase 3+ | Final doctrine |
|--------|----------------------|----------------------|----------------|
| S | No | Optional auxiliary priors (e.g., semantic ontology tags) | Primarily learned and context-anchored; dictionary priors permitted as subordinate optional inputs |

### E. Final Phase 2 Doctrine Patch

The following changes apply to the frozen Phase 1.5 doctrine:

1. **Section F (Semantic Firewall):** Formula is now a unified 4-step pipeline:
   ```
   S_raw  = bilinear + α_base · ẑ_base     (compute_S — includes anchor)
   S_prob = σ(S_raw)                        (combine_crs step 1)
   S_gate = σ(k_s · (S_prob − τ_s))        (combine_crs step 2)
   CRS    = S_gate · weighted_sum · S_prob  (combine_crs step 3)
   ```
   The base-logit anchor is fused into S_raw before any gating. S_prob and S_gate operate on the full semantic judgment. Weights normalized (sum to 1). τ_s = 0.5. The `× S_prob` term provides structural semantic authority beyond the gate.

2. **Section D (Definition of S):** `compute_S()` returns `S_raw = bilinear + α_base · ẑ_base` with `α_base = 0.5`. S has semantic signal from step 0. The bilinear term dominates after early training. The anchor is a minority prior, not a replacement.

3. **Section G (Dictionary Doctrine):** The absolute "no dictionaries ever" for S is replaced with "no dictionaries in Phase 2; optional subordinate auxiliary priors permitted in future phases."

4. **Section I (Guardrails):** Add: "Do not set α_base > 0.7 — the base-logit anchor must remain a minority contributor to S, not the dominant signal."

All other frozen decisions (C definition, R delegation, one CRS column, firewall inside combine_crs, no T shape changes, no renames) remain unchanged.

---

*End of Phase 1.5 doctrine freeze (v1.1). Phase 2 may now implement with revised specifications.*
