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

The Guna direction signal depends on the **context's Bhava position**, which changes every step. This means it cannot be fully cached in R_tok — the direction is context-dependent.

Options:
1. **Cache token positions only:** Store `tok_position` (V,1) in cache. Compute `delta = tok_position - ctx_position` on the fly. Minimal cache addition.
2. **No additional cache:** Compute from existing 12D affinity (already available as CSR affinity table) and context Bhava (already available as o_ctx[0:12]). Zero cache change.

**Recommendation: Option 2.** The CSR affinity table already exists (built at startup, 32K × 12D). The context Bhava is already available in the TET forward pass. Computing the weighted mean position is a single dot product — negligible cost.

---

## What This Changes in CRS

| CRS Component | Current | After R-Guna decomposition |
|---------------|---------|---------------------------|
| R input | R_tok (cached 16D) | R_tok (cached 16D) + 12D affinity + context Bhava |
| R output | Single scalar per candidate | Single scalar (Guna-modulated) |
| R interpretation | "How compatible is this phoneme structure?" | "How compatible, AND is it uplifting/activating/inert for this context?" |
| Cache changes | None | None (use existing CSR affinity table) |
| New parameters | None | `guna_weight` (1 scalar), `k` and `sigma` (2 sharpness params) |
| Column 3 in T | CRS combined (unchanged) | CRS combined with Guna-aware R (unchanged public shape) |

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

### Required update: `varna_bridge_map_v2.json`

The current `varna_bridge_map_v1.json` captures only a single `bridge_meaning` per consonant (e.g., `"hope_pressure"` for Ka). This is the **Sattvic expression only**.

The updated v2 schema should capture all three Guna expressions per consonant:

```json
{
  "meta": {
    "source": "Sanskrit Varna Mala",
    "version": "3.0",
    "purpose": "Phase-1b substrate bridge with tri-Guna expressions",
    "migration_note": "Added guna_expressions per consonant (Phase 5 R-branch target)"
  },
  "consonants": {
    "ka": {
      "type": "consonant",
      "aspirated": false,
      "varna_group": "ka_varga",
      "bridge_meaning": "hope_pressure",
      "guna_expressions": {
        "sattva": {
          "vritti": "Āśā (Hope)",
          "quality": "forward-seeking clarity, trust in potential",
          "dominant_layers": ["O3_EXECUTION", "O4_STRUCTURE", "O8_PURPOSE"]
        },
        "rajas": {
          "vritti": "Anxiety / Restless anticipation",
          "quality": "agitated forward-seeking, urgent projection",
          "dominant_layers": ["O5_COGNITION", "O6_AGENCY"]
        },
        "tamas": {
          "vritti": "Doubt / Frozen anticipation",
          "quality": "blocked forward-seeking, hope collapsed into uncertainty",
          "dominant_layers": ["O1_POTENTIAL", "O9_WITNESSES"]
        }
      },
      "layers": {
        "O3_EXECUTION": "forward-seeking activation",
        "O2_IDENTITY": "possibility classification",
        ...
      }
    },
    "kha": {
      "type": "consonant",
      "aspirated": true,
      "varna_group": "ka_varga",
      "bridge_meaning": "worry_pressure",
      "guna_expressions": {
        "sattva": {
          "vritti": "Vigilant discernment",
          "quality": "clear-eyed caution, wise alertness",
          "dominant_layers": ["O7_REASONING", "O8_PURPOSE"]
        },
        "rajas": {
          "vritti": "Worry / Anxious scanning",
          "quality": "agitated obstacle-detection, restless vigilance",
          "dominant_layers": ["O3_EXECUTION", "O5_COGNITION"]
        },
        "tamas": {
          "vritti": "Paranoia / Frozen fear",
          "quality": "paralyzed by perceived obstacles, inert dread",
          "dominant_layers": ["O1_POTENTIAL", "O12_ABSOLVING"]
        }
      },
      "layers": { ... }
    },
    "ga": {
      "type": "consonant",
      "aspirated": false,
      "varna_group": "ka_varga",
      "bridge_meaning": "action_pressure",
      "guna_expressions": {
        "sattva": {
          "vritti": "Ceṣṭā (Purposeful action)",
          "quality": "clear kinetic momentum, dharmic activity",
          "dominant_layers": ["O3_EXECUTION", "O6_AGENCY", "O8_PURPOSE"]
        },
        "rajas": {
          "vritti": "Compulsive action / Driven momentum",
          "quality": "agitated doing, action for action's sake",
          "dominant_layers": ["O3_EXECUTION", "O5_COGNITION"]
        },
        "tamas": {
          "vritti": "Inertia / Resistance to action",
          "quality": "blocked momentum, stagnation despite potential",
          "dominant_layers": ["O1_POTENTIAL", "O4_STRUCTURE"]
        }
      },
      "layers": { ... }
    }
  }
}
```

### Schema for `guna_expressions`

Every consonant entry should have:

```json
"guna_expressions": {
  "sattva": {
    "vritti": "<Sattvic expression of this phoneme's mental propensity>",
    "quality": "<brief description of the clarified/uplifted form>",
    "dominant_layers": ["<O-layers where Sattvic expression is strongest>"]
  },
  "rajas": {
    "vritti": "<Rajasic expression — agitated/active form>",
    "quality": "<brief description of the energized/restless form>",
    "dominant_layers": ["<O-layers where Rajasic expression is strongest>"]
  },
  "tamas": {
    "vritti": "<Tamasic expression — inert/obscured form>",
    "quality": "<brief description of the blocked/collapsed form>",
    "dominant_layers": ["<O-layers where Tamasic expression is strongest>"]
  }
}
```

### Consonants requiring three-Guna expressions

All consonants in `ARPABET_TO_VARNA` need this treatment:

| Varga | Consonants | Current single Vritti | Needs 3 Guna expressions |
|-------|-----------|----------------------|-------------------------|
| Ka-varga (Guttural) | ka, kha, ga, gha, ṅa | Hope, Worry, Action, ... | YES |
| Ca-varga (Palatal) | ca, cha, ja, jha, ña | Scatter, ... | YES |
| Ṭa-varga (Retroflex) | ṭa, ṭha, ḍa, ḍha, ṇa | Overstatement, Shyness, ... | YES |
| Ta-varga (Dental) | ta, tha, da, dha, na | Melancholy, Craving, ... | YES |
| Pa-varga (Labial) | pa, pha, ba, bha, ma | Revulsion, Fear, Indifference, ... | YES |
| Semi-vowels | ya, ra, la, va | Lack of confidence, Annihilation, Cruelty, Dharma | YES |
| Sibilants | śa, ṣa, sa, ha | Material greed, Escapism, Darkness | YES |

Total: ~40 consonants × 3 Guna states = ~120 expressions to document.

### Cross-reference with polarity map

The `varna_polarity_map_v1.json` can be used to **validate** the new Guna expressions:

- Layers marked `constructive` for a consonant should align with that consonant's `sattva.dominant_layers`
- Layers marked `transitional` should align with `rajas.dominant_layers`
- Layers marked `degenerative` should align with `tamas.dominant_layers`

This provides a consistency check between the two data sources.

### How the updated JSON will be consumed (Phase 5)

```python
# In VarnaCSRBridge (or new GunaBridge):
def get_guna_vectors(self, varna: str) -> Dict[str, List[float]]:
    """Return three 12D vectors: one per Guna expression."""
    entry = self._data['consonants'][varna]
    guna_expr = entry['guna_expressions']
    return {
        'sattva': self._layers_to_vector(guna_expr['sattva']['dominant_layers']),
        'rajas': self._layers_to_vector(guna_expr['rajas']['dominant_layers']),
        'tamas': self._layers_to_vector(guna_expr['tamas']['dominant_layers']),
    }

# In R-branch Guna-aware computation:
# token_guna_vectors: (V, 3, 12) — three 12D vectors per token
# context_guna_3d: (..., 3) — context Guna distribution
# effective_affinity = sum_g context_guna[g] * token_guna_vectors[:, g, :]
```

---

## Not In Scope

- Vowel Guna decomposition (vowels map to consciousness states, not Vritti propensities — different Guna logic, may need separate treatment)
- Changing the 12D affinity vectors themselves (the current vectors remain as the "default/combined" affinity; Guna vectors are additional)
- Modifying the CSR phoneme provider in Phase 5 (it continues to provide the combined 12D; Guna-aware R reads from the new JSON)
- Changing cache shapes or checkpoint keys

---

*This design document is for Phase 5+. Do not implement until Phase 4 is complete.*
