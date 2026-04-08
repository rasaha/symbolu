# Design Document: `cg` Model Type — Full Conscious Generation Architecture

## Problem Statement

The codebase has three model families that each provide *part* of the full Conscious Generation (CG) stack, but none combines everything:

| Feature | `ontological` | `hybrid` | `ontological_hybrid` |
|---------|:---:|:---:|:---:|
| 32D Sovereign State | Yes (via Bhava 12D + 144D relationships) | No | Yes |
| Phase-Quad Attention | Partial (PhaseAttentionLayer, O(n)) | Yes (full cosine modes) | Yes (via inner `hybrid`) |
| Local + Global Attention | No (no sliding window) | Yes | Yes |
| Slot Memory / Global Tokens | No (R-Signal 48D instead) | Yes | Yes |
| CG Phase 1 (L_ont) | Yes | Yes (with warning) | Yes |
| CG Phase 3 (Kosha/Bliss/JEPA/CSR/Vritti/Guna) | **No** (no `last_hidden_state`/`state`) | **No** (no `state`) | Yes |
| CG Phase 4 (Field-Integrated Softmax) | **No** | **No** | Yes |
| CG Curriculum | Partial (L_ont only) | Partial | Yes |
| Dual-Channel Attention | No | Yes | Yes |
| GQA (Grouped Query Attention) | No | No | Yes (`n_kv_heads`) |
| Decorrelation Loss | No | Yes | Yes |
| Bhava Relationships (144D) | Yes (BhavaRelationshipModule) | No | No |
| R-Signal (48D nerve) | Yes (Authority→Sensory) | No | No |
| Witness Layer | Yes (meta-cognition) | No | No |

**Goal**: Create a `cg` model type that is a *union* of all capabilities.

---

## Architecture Gap Analysis

### What CG Phase 3/4 Requires from the Model

The CG loss block (train.py:4730-4950) needs exactly 3 outputs:

```python
logits          = outputs['logits']           # [B, T, V]
last_hidden_state = outputs['last_hidden_state']  # [B, T, embed_dim]
state           = outputs['state']            # [B, T, 32] or [B, 32]
```

Plus access to:
- `model.conscious_gen` — ModuleDict of CG scorers/losses (attached by model_factory)
- Embedding layer via `model.token_embed.weight` or `model.wte.weight` or `model.embed.weight`

### Why `ontological` Fails CG

`SymbolU12LLMWithBhava.forward()` returns:

| Key | Shape | CG-compatible? |
|-----|-------|:-:|
| `logits` | [B, T, V] | Yes |
| `ontological_probs` | [B, 12] | No (CG needs 32D `state`) |
| `bhava_vector` | [B, 144] | No (not `last_hidden_state`) |
| `r_signal` | [B, 48] | No |
| `layer_embeddings` | List[B, 768] | Not exposed as `last_hidden_state` |

Missing: `last_hidden_state` (per-token), `state` (32D Sovereign).

### Why `hybrid` Fails CG

`HybridPhaseTransformer.forward()` returns:

| Key | Shape | CG-compatible? |
|-----|-------|:-:|
| `logits` | [B, T, V] | Yes |
| `last_hidden_state` | [B, T, D] | Yes (when `return_last_hidden=True`) |
| — | — | No `state` key at all |

Missing: `state` (no Sovereign State projector).

### Why `ontological_hybrid` Works

`OntologicalHybridTransformer.forward()` returns:

| Key | Shape | CG-compatible? |
|-----|-------|:-:|
| `logits` | [B, T, V] | Yes |
| `last_hidden_state` | [B, T, D] | Yes (from inner `hybrid`) |
| `state` | [B, 32] | Yes (from `state_projector`) |
| `delta_S` | [B, 32] | Yes (bonus: state delta) |
| `delta_bhava` | [B, 12] | Yes (bonus: Bhava delta) |
| `intent_phase` | [B, H] | Yes (bonus: phase rotation) |

This is the only model type where CG Phase 3/4 fully activates.

---

## Design: `cg` Model Type

### Principle

The `cg` model type starts from `OntologicalHybridTransformer` (which already works with CG) and adds the missing `ontological`-only features:

1. Bhava Relationship Module (144D inter-layer relationships)
2. R-Signal nerve (48D Authority→Sensory)
3. Witness Layer (meta-cognition confidence)
4. Harmonic phase hierarchy (layer-specific frequency modulation)

### Architecture

```
Input: token_ids [B, T]
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ Token Embedding + Position Embedding [B, T, D]      │
│ (self.token_embed, self.pos_embed)                  │
└─────────────┬───────────────────────────────────────┘
              │
    ┌─────────▼──────────┐
    │ LOCAL LAYERS (0..L) │  ← Sliding window attention
    │ (Authority Tier)    │  ← Accumulate R-Signal [B, 48]
    │                     │  ← Collect layer_embeddings for Bhava
    └─────────┬──────────┘
              │
    ┌─────────▼──────────┐
    │ WITNESS LAYER       │  ← Meta-cognition (confidence)
    │ (between Local &    │  ← Dominant R-Signal contribution
    │  Phase layers)      │  ← Returns witness_confidence [B, 1]
    └─────────┬──────────┘
              │
    ┌─────────▼──────────┐
    │ PHASE LAYERS (L..N) │  ← Phase-Quad cosine attention
    │ (Sensory Tier)      │  ← intent_phase from ΔBhava
    │                     │  ← R-Signal injected as phase bias
    │                     │  ← Slot memory read/write
    └─────────┬──────────┘
              │
    ┌─────────▼──────────┐
    │ BHAVA UNIFICATION   │  ← BhavaRelationshipModule(layer_embeddings)
    │                     │  ← Produces: bhava_vector [B, 144]
    │                     │  ←           relationship_matrix [B, 12, 12]
    │                     │  ←           coherence_matrix [B, 12, 12]
    └─────────┬──────────┘
              │
    ┌─────────▼──────────┐
    │ OUTPUT HEAD          │
    │ LayerNorm → lm_head │
    │ → logits [B, T, V]  │
    └─────────┬──────────┘
              │
    ┌─────────▼───────────────────────────────────────┐
    │ STATE COMPUTATION (parallel path)                │
    │                                                  │
    │ SovereignStateProjector(pooled_hidden) → [B,32] │
    │   ├─ state [B, 32]  (full Sovereign State)      │
    │   ├─ delta_S [B, 32] (full delta)               │
    │   └─ delta_bhava [B, 12] (Bhava-only delta)     │
    │                                                  │
    │ IntentPhaseProjector(delta_bhava) → intent_phase │
    └─────────────────────────────────────────────────┘

Output Dict:
{
    # CG-required (Phase 3/4 compatibility)
    'logits':           [B, T, V],
    'last_hidden_state': [B, T, D],
    'state':            [B, 32],

    # Ontological State Delta
    'delta_S':          [B, 32],
    'delta_bhava':      [B, 12],
    'intent_phase':     [B, H],

    # Bhava Relationships (from ontological)
    'bhava_vector':         [B, 144],
    'relationship_matrix':  [B, 12, 12],
    'coherence_matrix':     [B, 12, 12],
    'global_coherence':     [B],

    # Witness
    'witness_confidence':   [B, 1],
    'r_signal':             [B, 48],

    # Ontological layer probabilities
    'ontological_probs':    [B, 12],

    # Standard
    'hidden_states':    List[B, T, D] (if requested),
    'decorr_loss':      scalar (if requested),
}
```

### Implementation Strategy

There are two paths:

#### Option A: Subclass OntologicalHybridTransformer (Recommended)

```python
class ConsciousGenerationTransformer(OntologicalHybridTransformer):
    """Full CG model = OntologicalHybrid + Bhava + Witness + R-Signal."""

    def __init__(self, ..., bhava_embed_dim=128, r_signal_dim=48, ...):
        super().__init__(...)  # Gets hybrid, state_projector, intent_projector

        # Add Bhava relationship module
        self.bhava_module = BhavaRelationshipModule(
            embed_dim=bhava_embed_dim,
            num_layers=self.hybrid.num_layers,
        )

        # Add Witness layer (inserted between Local and Phase layers)
        self.witness = WitnessLayerWithBhava(...)
        self.witness_r_proj = nn.Linear(embed_dim, r_signal_dim)

        # R-Signal projections per local layer
        self.r_signal_projs = nn.ModuleList([
            nn.Linear(embed_dim, r_signal_dim)
            for _ in range(self.hybrid.local_layers)
        ])

    def forward(self, input_ids, **kwargs):
        # 1. First pass: hidden states WITHOUT intent phase (same as parent)
        with torch.no_grad():
            hidden = self.hybrid.forward_hidden(input_ids, intent_phase=None)

        # 2. Compute state delta (inherited from parent)
        state, delta_S, delta_bhava = self.compute_state_delta(hidden)
        intent_phase = self.intent_projector(delta_bhava)

        # 3. Second pass: full forward WITH intent phase
        #    Modified to also collect per-layer embeddings and R-Signal
        result = self._forward_with_bhava(
            input_ids, intent_phase.detach(), **kwargs
        )

        # 4. Bhava relationships from collected layer embeddings
        layer_embs = result.pop('_layer_embeddings')  # List[B, D] x num_layers
        bhava_out = self.bhava_module(layer_embs, result.get('ontological_probs'))
        result.update({
            'bhava_vector': bhava_out['bhava_vector'],
            'relationship_matrix': bhava_out['relationship_matrix'],
            'coherence_matrix': bhava_out['coherence_matrix'],
            'global_coherence': bhava_out['global_coherence'],
        })

        # 5. Add ontological outputs (same as parent)
        result['state'] = state
        result['delta_S'] = delta_S
        result['delta_bhava'] = delta_bhava
        result['intent_phase'] = intent_phase

        return result
```

**Pros**: Reuses all existing OntologicalHybrid code. Inherits CG compatibility.
**Cons**: Needs to override the inner hybrid forward to collect layer embeddings + inject R-Signal + insert Witness.

#### Option B: Compose from Scratch

Build a new class that directly contains all submodules without nesting.

**Pros**: Cleaner forward pass, no double-forward overhead.
**Cons**: Code duplication with HybridPhaseTransformer and OntologicalHybridTransformer.

### Recommendation: Option A (Subclass)

The double-forward cost in OntologicalHybrid is already accepted. Adding Bhava + Witness + R-Signal on top is minimal overhead. The key changes needed:

1. **Override `_forward_with_bhava`** — same as `hybrid.forward()` but:
   - Collect `layer_embeddings` (mean-pooled per layer) for Bhava
   - Accumulate R-Signal through Local layers
   - Insert Witness between Local and Phase tiers
   - Inject R-Signal as phase bias into Phase layers

2. **Add Bhava computation** — post-forward, uses collected layer embeddings

3. **Keep all CG-required outputs** — `logits`, `last_hidden_state`, `state`

---

## Changes Required

### 1. New File: `symbolu/phase_transformer.py` (append class)

Add `ConsciousGenerationTransformer` class (~200 lines) that subclasses `OntologicalHybridTransformer`.

### 2. `model_factory.py` — Add `cg` Branch

```python
elif config.model_type == "cg":
    model = ConsciousGenerationTransformer(
        # All OntologicalHybridTransformer params
        vocab_size=..., embed_dim=..., num_layers=..., num_heads=...,
        # Plus new params
        bhava_embed_dim=config.bhava_embed_dim,       # 128
        r_signal_dim=config.r_signal_dim,             # 48
        num_drishti_heads=config.num_drishti_heads,    # 4
    )
```

### 3. `config.py` — Add New Fields

```python
# CG Model Type extras (Bhava + Witness + R-Signal)
bhava_embed_dim: int = 128
r_signal_dim: int = 48
num_drishti_heads: int = 4
enable_witness: bool = True
enable_bhava_relationships: bool = True
enable_r_signal: bool = True
bhava_lambda: float = 0.1       # Already exists (for ontological)
```

### 4. `train.py` — Add Forward Path

The `cg` model type would fall into the `else` branch (Phase/Hybrid path) since it returns the same dict format as `ontological_hybrid`:
- `logits` → `compute_phase_loss`
- `last_hidden_state` + `state` → CG Phase 3/4 block at line 4730

**Minimal change**: Just add `'cg'` to the decorr check:

```python
enable_decorr = (
    config.decorr_loss_weight > 0 and
    config.model_type in ('hybrid', 'ontological_hybrid', 'cg')  # Add 'cg'
)
```

And add Bhava-specific losses after the CG block:

```python
if config.model_type == 'cg' and 'bhava_vector' in outputs:
    # Bhava coherence loss (from ontological model)
    if config.bhava_lambda > 0:
        bhava_loss = compute_bhava_coherence_loss(outputs)
        loss = loss + config.bhava_lambda * bhava_loss
        metrics['bhava_loss'] = bhava_loss.item()
```

### 5. `train.py` — CLI Args

```python
parser.add_argument("--bhava_embed_dim", type=int, default=128)
parser.add_argument("--r_signal_dim", type=int, default=48)
parser.add_argument("--num_drishti_heads", type=int, default=4)
parser.add_argument("--enable_witness", action="store_true")
parser.add_argument("--enable_bhava_relationships", action="store_true")
parser.add_argument("--enable_r_signal", action="store_true")
```

---

## Training Command (Complete CG Model)

```bash
python train_unified_llm.py \
  --model_type cg \
  --model_size medium \
  --n_layer 12 --n_head 12 --n_embd 768 \
  \
  # Bhava + Witness + R-Signal (ontological features)
  --enable_bhava_relationships \
  --enable_witness \
  --enable_r_signal \
  --bhava_embed_dim 128 \
  --r_signal_dim 48 \
  --bhava_lambda 0.1 \
  \
  # Phase-Quad (hybrid features)
  --local_layers 4 \
  --window_size 256 \
  --cosine_mode decay \
  --learned_decay \
  --bounded_phase \
  --zero_mean_cosine \
  \
  # Sovereign State (ontological_hybrid features)
  --state_dim 32 \
  \
  # Full CG Pipeline (Phases 1-4)
  --enable_conscious_generation \
  --enable_cg_curriculum \
  --lambda_ont 0.1 \
  --lambda_kosha_routing 0.05 \
  --lambda_bliss_token 0.05 \
  --lambda_jepa_token 0.02 \
  --lambda_csr_token 0.02 \
  --lambda_vritti_token 0.02 \
  --lambda_guna_token 0.02 \
  \
  # Phase 4: Field-Integrated Generation
  --use_field_integrated_softmax \
  \
  # Slot Memory
  --global_tokens_enabled \
  --num_global_tokens 32 \
  --global_update_mode slots \
  \
  # Training
  --dataset openwebtext \
  --batch_size 4 \
  --gradient_accumulation 8 \
  --max_seq_len 512 \
  --lr 3e-4 \
  --max_steps 20000 \
  --enable_embedding_diagnostics \
  --embedding_diag_interval 200
```

### With Mistral Knowledge Distillation

```bash
python train_unified_llm.py \
  --model_type cg \
  --model_size medium \
  --n_layer 12 --n_head 12 --n_embd 768 \
  \
  # Distillation
  --distill_from_mistral \
  --mistral_model_name mistralai/Mistral-7B-v0.3 \
  --mistral_quantize 4bit \
  --distill_temperature 2.0 \
  --distill_alpha 0.5 \
  --distill_warmup_steps 500 \
  \
  # All CG features (same as above)
  --enable_bhava_relationships \
  --enable_witness \
  --enable_r_signal \
  --enable_conscious_generation \
  --enable_cg_curriculum \
  --lambda_ont 0.1 \
  --lambda_kosha_routing 0.05 \
  --lambda_bliss_token 0.05 \
  --lambda_jepa_token 0.02 \
  --lambda_csr_token 0.02 \
  --lambda_vritti_token 0.02 \
  --lambda_guna_token 0.02 \
  --use_field_integrated_softmax \
  --state_dim 32 \
  --local_layers 4 \
  --cosine_mode decay \
  --learned_decay \
  --bounded_phase \
  --zero_mean_cosine \
  --global_tokens_enabled \
  --num_global_tokens 32 \
  --global_update_mode slots \
  --dataset openwebtext \
  --batch_size 4 \
  --gradient_accumulation 8 \
  --max_seq_len 512 \
  --lr 3e-4 \
  --max_steps 20000
```

---

## Implementation Effort Estimate

| Component | Lines | Complexity |
|-----------|-------|-----------|
| `ConsciousGenerationTransformer` class | ~200 | Medium — subclass + override forward |
| `model_factory.py` branch | ~40 | Low — copy/adapt ontological_hybrid branch |
| `config.py` fields | ~10 | Low |
| `train.py` CLI args | ~10 | Low |
| `train.py` forward path additions | ~20 | Low — mostly adding `'cg'` to existing checks |
| Bhava loss integration | ~15 | Low — already exists in `compute_ontological_loss` |
| **Total** | **~295** | **Medium** |

The majority of the work is in the `ConsciousGenerationTransformer.forward()` method, which needs to thread R-Signal accumulation and Witness insertion through the existing hybrid layer loop.

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Double-forward cost (inherited from ontological_hybrid) | 2x FLOPs for first pass | Accept — same as existing ontological_hybrid |
| Bhava module adds ~2M params | Modest increase | Minimal vs. 85M base model |
| R-Signal injection into Phase layers requires modifying HybridPhaseBlock | Could break existing hybrid | Use optional `r_signal` kwarg with default=None |
| Witness layer adds latency between Local and Phase tiers | Sequential dependency | One layer — negligible |
| CG curriculum interaction with Bhava losses | New loss terms may destabilize early training | Add Bhava to Stage C/D only (after backbone stabilization) |

---

## Summary

The `cg` model type is the *union* of `ontological` + `ontological_hybrid`:

- From `ontological_hybrid`: Sovereign State (32D), Phase-Quad attention, Local+Global layers, Slot Memory, CG Phase 1-4, GQA, Decorrelation loss
- From `ontological`: Bhava Relationships (144D), R-Signal (48D nerve), Witness Layer, Harmonic phase hierarchy, Ontological probabilities

Implementation: Subclass `OntologicalHybridTransformer`, add Bhava/Witness/R-Signal modules, override forward to collect layer embeddings and inject R-Signal. ~295 lines of new code.
