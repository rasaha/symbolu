# R-Branch Guna Decomposition Design (Phase 5 Target)

**Date:** 2026-04-09
**Status:** Design only — not implemented
**Prerequisite:** Phase 3 CRS validation complete, Phase 4 CRS promotion complete
**Scope:** R branch enhancement within CRS

---

## Core Insight

Each Sanskrit consonant phoneme does not have a fixed Guna assignment. Instead, every consonant has **three Guna expressions** that emerge from the **relational position** between the token's ontological signature and the context's current ontological state.

- Token's dominant layers **above** context → **Sattvic** (uplifting, clarifying)
- Token's dominant layers **at** context → **Rajasic** (activating, energizing)
- Token's dominant layers **below** context → **Tamasic** (inertial, obscuring)

Example with Ka (क, ARPABET: K):

```
Ka 12D affinity: peaks at O3_Execution (0.9), O6_Agency (0.5)

Context at O1-O2 (early potential):   Ka is ABOVE → Sattvic → Hope (Āśā)
Context at O3 (execution):           Ka is AT    → Rajasic → Anxious action
Context at O6-O7 (agency/reasoning): Ka is BELOW → Tamasic → Doubt
```

The same phoneme "K" carries hope, anxiety, or doubt depending on where the context sits in the ontological stack. **Guna is not a property of the phoneme — it is a property of the phoneme-context relationship.**

---

## Current State (Phase 2-3)

The current R branch treats the 12D affinity as a fixed vector per token:

```
Token → ARPABET → Varna → 12D affinity (fixed)
    → token_proj MLP → R_tok (V, 16) (fixed, cached)
    → r_ctx^T M_R R_tok → scalar score (symmetric bilinear)
```

**What is lost:** The bilinear form `r_ctx^T M_R R_tok` measures *similarity* or *compatibility* but not *directionality*. It cannot distinguish "token is above context" from "token is below context" — both may produce similar magnitude scores. The Guna information (which direction the phoneme pulls relative to context) is collapsed.

**What is preserved:** The 12D affinity does encode which ontological layers each phoneme activates. The *information* for Guna derivation exists. The *computation* to extract it does not.

---

## Target Design

### Guna Direction Signal

Compute the directional relationship between token and context ontological positions:

```python
def compute_guna_direction(token_affinity_12d, context_bhava_12d):
    """
    Derive Guna quality from ontological position relationship.

    Args:
        token_affinity_12d: Token's 12D phonemic affinity (K,12) or (V,12)
        context_bhava_12d: Context's Bhava slice o_ctx[0:12] (..., 12)

    Returns:
        guna_direction: (..., K, 3) — [Sattva, Rajas, Tamas] per candidate
    """
    # Layer indices as weights for computing "center of mass"
    layer_positions = torch.arange(12, dtype=torch.float32)  # [0, 1, ..., 11]

    # Weighted mean position for context
    ctx_weights = context_bhava_12d / (context_bhava_12d.sum(-1, keepdim=True) + 1e-8)
    ctx_position = (ctx_weights * layer_positions).sum(-1)  # (...,) scalar

    # Weighted mean position for each token
    tok_weights = token_affinity_12d / (token_affinity_12d.sum(-1, keepdim=True) + 1e-8)
    tok_position = (tok_weights * layer_positions).sum(-1)  # (K,) or (V,)

    # Direction: positive = token above context = Sattvic
    delta = tok_position - ctx_position  # (..., K)

    # Guna decomposition from direction
    k = 2.0  # sharpness (tunable)
    sigma = 1.5  # Rajasic width (tunable)

    sattva = torch.sigmoid(k * delta)           # high when token above
    rajas = torch.exp(-delta.pow(2) / (2 * sigma**2))  # peaks when at same level
    tamas = torch.sigmoid(-k * delta)           # high when token below

    # Normalize to probability simplex
    total = sattva + rajas + tamas + 1e-8
    guna_direction = torch.stack([
        sattva / total,
        rajas / total,
        tamas / total,
    ], dim=-1)  # (..., K, 3)

    return guna_direction
```

### Integration into R Branch

Two possible approaches:

#### Approach A: Guna-conditioned R score (multiplicative)

R score is modulated by how well the token's derived Guna matches the context's Guna state:

```python
def compute_R_guna_aware(self, r_ctx, R_cand, token_affinity, context_bhava, context_guna_3d):
    # Standard resonance score (existing)
    R_structural = self.csr_scorer(r_ctx, R_cand)  # (..., K)

    # Guna direction signal
    guna_dir = compute_guna_direction(token_affinity, context_bhava)  # (..., K, 3)

    # Context Guna state (from sovereign state [22:28] → 3 classical)
    # context_guna_3d: (..., 3) — [Sattva, Rajas, Tamas]

    # Guna alignment: how well does token's derived Guna match context's Guna?
    guna_alignment = (guna_dir * context_guna_3d.unsqueeze(-2)).sum(-1)  # (..., K)

    # Combined: structural resonance × Guna alignment
    R_combined = R_structural * (1.0 + guna_weight * guna_alignment)

    return R_combined
```

#### Approach B: Guna as separate sub-score (additive)

R returns both structural and Guna components separately:

```python
R_structural = bilinear(r_ctx, R_cand)     # existing
R_guna = guna_alignment(token, context)    # new

R_total = w_struct * R_structural + w_guna * R_guna
```

**Recommendation: Approach A (multiplicative).** Guna modulates the strength of resonance rather than adding an independent score. A Sattvic phoneme in a Sattvic context resonates *more strongly*, not with a different kind of resonance.

### Cache Implications

Two components are needed at forward time:

1. **Token-side Guna vectors** — fixed per token, changes only at cache refresh.
   Cache as `Guna_tok (V, 3, 12)` buffer in `TokenPrimitiveCache`.
   Derived from `varna_bridge_map` weights × `varna_polarity_map` labels.
   Refreshed alongside R_tok (with EMA blending). ~1.2 MB.

2. **Context Guna state** — changes every step, cannot be cached.
   Already available: sovereign state Guna slice `o_ctx[22:28]` → 3 classical via
   `BlissTokenGate.guna_proj`. Or compute fresh: `softmax(guna_proj(o_ctx[22:28]))`.

The Guna alignment `guna_dir · context_guna_3d` is computed on the fly from
cached `Guna_tok` + live context Guna. Single dot product per candidate — negligible cost.

---

## What This Changes in CRS

| CRS Component | Current | After R-Guna decomposition |
|---------------|---------|---------------------------|
| R input | R_tok (cached 16D) | R_tok (cached 16D) + Guna affinity cache (3×12D) + context Bhava + context Guna |
| R output | Single scalar per candidate | Single scalar (Guna-modulated) |
| R interpretation | "How compatible is this phoneme structure?" | "How compatible, AND is it uplifting/activating/inert for this context?" |
| Cache changes | None | One new buffer: `Guna_tok (V, 3, 12)` — ~1.2MB |
| New parameters | None | 3 scalars: `guna_weight`, `k`, `sigma` |
| Column 3 in T | CRS combined (unchanged) | CRS combined with Guna-aware R (unchanged public shape) |

---

## Parameter and Memory Budget

Guna-R integration is intentionally lightweight. It does **not** create large weights.

### New learnable parameters: 3 total

| Parameter | Shape | Count | Purpose |
|-----------|-------|-------|---------|
| `guna_weight` | scalar | 1 | Controls how much Guna modulates R (0 = no effect, ablation switch) |
| `k` | scalar | 1 | Sharpness of Sattva/Tamas sigmoid (direction sensitivity) |
| `sigma` | scalar | 1 | Width of Rajasic Gaussian (how broadly "same level" is defined) |

For comparison: the existing CSRTokenScorer has ~9,400 parameters. Guna-R adds 3.

### New cache buffer: 1

| Buffer | Shape | Size at V=32K | Purpose |
|--------|-------|---------------|---------|
| `Guna_tok` | (V, 3, 12) | ~1.2 MB (fp16) | Pre-computed Guna-specific 12D affinity vectors per token. Derived from `varna_bridge_map` × `varna_polarity_map` at cache refresh. Not trained — pure data lookup. |

For comparison: existing total cache is ~8.8 MB. Guna_tok adds 14%.

### Existing parameters unchanged

| Component | Parameters | Changed? |
|-----------|-----------|----------|
| `CSRTokenScorer.A, .B` (bilinear M_R) | 256 | NO |
| `CSRTokenScorer.token_proj` (12D → 16D MLP) | ~768 | NO |
| `CSRTokenScorer.context_proj` ([h;o] → 16D MLP) | ~8,400 | NO |
| `CRSCombinedScorer.A_C, .B_C` (C bilinear) | 80 | NO |
| `CRSCombinedScorer.A_S, .B_S` (S bilinear) | 256 | NO |
| `CRSCombinedScorer.semantic_*_mlp` (S MLPs) | ~2,100 | NO |

### Forward pass cost

The Guna modulation adds per candidate per position:
1. One dot product: `guna_dir · context_guna_3d` → (K,) — negligible
2. One multiply: `R_structural * (1 + w * alignment)` → (K,) — negligible

No new matrix multiplications. No new attention. No new MLP forward passes.

### Why the weights stay small

The Guna signal is **computed, not learned**. The three 12D Guna vectors per token are derived deterministically from existing data files at cache refresh time. The learned part is only "how much should this matter" (3 scalars), not "what is the Guna pattern" (that's given by the Sanskrit Varna system).

This is by design: the Varna-Guna structure is **prior knowledge** from Sanskrit phonetics, not something the model discovers. The model only learns how strongly to use it.

---

## Prerequisites

1. CRS Phase 3 validation complete — S branch learning, gate stable
2. CRS Phase 4 promotion — fixed weights validated, CRS is default
3. Guna-per-consonant expressions documented (verify the directional model against traditional Sanskrit grammar sources)

---

## Validation Plan

1. Compute Guna direction for all 32K tokens at a fixed context state. Verify that consonants with known Sattvic Vrittis (e.g., Ka→Hope, Va→Dharma) get high Sattva scores when context is at lower layers.

2. Compare R scores with and without Guna modulation on a factual vs narrative text split. Expect: Guna modulation has larger effect on narrative text (where phonemic quality matters more).

3. Ablation: `guna_weight=0` should reproduce current R behavior exactly.

---

## Data Files and Lineage

### Current data files used by CRS

| File | Contents | Used by CRS R branch |
|------|----------|---------------------|
| `csr_phoneme_provider.py` | `ARPABET_TO_VARNA` (phoneme→varna+single Vritti meaning), `PHONEME_MAP_ARPABET` (static 12D vectors), `SANSKRIT_VOWEL_CALIBRATION`, `VarnaCSRBridge` class | YES — primary pipeline |
| `docs/data/varna_bridge_map_v1.json` | Per-consonant O1-O12 layer annotations with descriptions. Loaded by `VarnaCSRBridge`. | YES — loaded at runtime |
| `docs/data/varna_polarity_map_v1.json` | Per-consonant per-layer polarity: `constructive` / `transitional` / `degenerative` | NOT YET — contains proto-Guna data |
| `docs/data/varna_distortion_map_v1.json` | Distortion patterns per varna | Not used by CRS |
| `docs/data/varna_layer_interaction_v1.json` | Cross-layer interaction weights | Not used by CRS |

### Existing polarity → Guna mapping

The `varna_polarity_map_v1.json` already contains a per-layer polarity for each consonant that maps directly to the three Gunas:

| Polarity label | Guna equivalent |
|---------------|----------------|
| `constructive` | **Sattva** — uplifting, clarifying |
| `transitional` | **Rajas** — activating, energizing |
| `degenerative` | **Tamas** — inertial, obscuring |

Example from current `varna_polarity_map_v1.json` for Ka (क):

```json
"ka": {
    "O3_EXECUTION": "constructive",     ← Sattvic at execution layer
    "O2_IDENTITY": "neutral",
    "O4_STRUCTURE": "constructive",     ← Sattvic at structure layer
    "O5_COGNITION": "transitional",     ← Rajasic at cognition layer
    "O6_AGENCY": "transitional",        ← Rajasic at agency layer
    "O8_PURPOSE": "constructive",       ← Sattvic at purpose layer
    ...
}
```

This confirms: **Ka is not uniformly Sattvic**. It is Sattvic at execution/structure/purpose layers, Rajasic at cognition/agency layers, and neutral at identity/witness layers. The Guna expression depends on which ontological layer is contextually active.

### Data source: `varna_polarity_map_v1.json` (already exists)

**No new JSON file is needed.** The three-Guna data already exists in `docs/data/varna_polarity_map_v1.json` as per-consonant, per-layer polarity labels:

```
constructive  = Sattva
transitional  = Rajas
degenerative  = Tamas
neutral       = equal contribution to all three
```

Example for Ka (क):

```json
"ka": {
    "O3_EXECUTION": "constructive",     ← Sattvic at execution
    "O4_STRUCTURE": "constructive",     ← Sattvic at structure
    "O5_COGNITION": "transitional",     ← Rajasic at cognition
    "O6_AGENCY": "transitional",        ← Rajasic at agency
    "O8_PURPOSE": "constructive",       ← Sattvic at purpose
    "O10_UNIFYING": "constructive",     ← Sattvic at unifying
    "O12_ABSOLVING": "transitional",    ← Rajasic at absolving
    "O1_POTENTIAL": "neutral",          ← equal all three
    "O2_IDENTITY": "neutral",
    "O7_REASONING": "neutral",
    "O9_WITNESSES": "neutral",
    "O11_INTEGRATION": "constructive"
}
```

This shows Ka is **not uniformly Sattvic**. It is Sattvic at execution/structure/purpose layers, Rajasic at cognition/agency layers, and neutral at identity/witness layers. The Guna expression depends on which ontological layer is contextually active — exactly the relational model described above.

### How existing data will be consumed (Phase 5)

Combine `varna_bridge_map_v1.json` (layer weights) with `varna_polarity_map_v1.json` (Guna labels per layer) to produce three Guna-specific 12D affinity vectors per consonant:

```python
# In VarnaCSRBridge (extended):
def get_guna_vectors(self, varna: str) -> Dict[str, List[float]]:
    """Derive three 12D vectors from existing bridge + polarity data."""
    base_vector = self.get_vector(varna)           # existing 12D from bridge map
    polarity = self._polarity_data[varna]          # from polarity map

    sattva_vec = [0.0] * 12
    rajas_vec = [0.0] * 12
    tamas_vec = [0.0] * 12

    for layer_name, label in polarity.items():
        idx = LAYER_NAME_TO_IDX[layer_name]
        weight = base_vector[idx]                  # original layer weight

        if label == "constructive":
            sattva_vec[idx] = weight               # Sattvic at this layer
        elif label == "transitional":
            rajas_vec[idx] = weight                # Rajasic at this layer
        elif label == "degenerative":
            tamas_vec[idx] = weight                # Tamasic at this layer
        else:  # "neutral"
            # Neutral layers contribute equally to all three
            sattva_vec[idx] = weight / 3.0
            rajas_vec[idx] = weight / 3.0
            tamas_vec[idx] = weight / 3.0

    return {'sattva': sattva_vec, 'rajas': rajas_vec, 'tamas': tamas_vec}

# Result for Ka:
#   sattva_vec: strong at O3, O4, O8, O10, O11 (constructive layers)
#   rajas_vec:  strong at O5, O6, O12 (transitional layers)
#   tamas_vec:  zero (Ka has no degenerative layers)
#   neutral layers (O1, O2, O7, O9): split equally across all three

# In R-branch Guna-aware computation:
# token_guna_vectors: (V, 3, 12) — three 12D vectors per token
# context_guna_3d: (..., 3) — context Guna distribution [Sattva, Rajas, Tamas]
# effective_affinity = sum_g context_guna[g] * token_guna_vectors[:, g, :]
#
# In a Sattvic context: Ka's effective affinity emphasizes O3/O4/O8 (hope layers)
# In a Rajasic context: Ka's effective affinity emphasizes O5/O6 (anxiety layers)
# Same phoneme, different resonance — driven entirely by existing data.
```

---

## Not In Scope

- Vowel Guna decomposition (vowels map to consciousness states, not Vritti propensities — different Guna logic, may need separate treatment)
- Changing the 12D affinity vectors themselves (the current vectors remain as the "default/combined" affinity; Guna vectors are additional)
- Modifying the CSR phoneme provider in Phase 5 (it continues to provide the combined 12D; Guna-aware R reads from the new JSON)
- Changing cache shapes or checkpoint keys

---

*This design document is for Phase 5+. Do not implement until Phase 4 is complete.*
