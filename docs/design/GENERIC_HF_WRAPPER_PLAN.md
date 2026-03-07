# Plan: Generalize MistralCGWrapper → HuggingFaceCGWrapper

## Goal
Replace the Mistral-specific wrapper with a generic one that works with **any** HuggingFace `AutoModelForCausalLM` — enabling A/B testing across Mistral, Qwen2.5, Llama 3.1, Gemma 2, Phi-3, etc.

## Why
- Current `MistralCGWrapper` has zero Mistral-specific code — it already uses `AutoModelForCausalLM` and `AutoTokenizer`
- The only Mistral-specific things are: the class name, docstring, print messages, and config field names
- Generalizing is a clean rename + config update, not an architectural change

## Changes

### 1. Create `symbolu/training/unified/hf_wrapper.py` (rename from `mistral_wrapper.py`)

- Rename class `MistralCGWrapper` → `HuggingFaceCGWrapper`
- Rename internal method `_load_mistral` → `_load_backbone`
- Update docstring and print messages to say "HuggingFace backbone" instead of "Mistral"
- Rename attribute `mistral_hidden_dim` → `backbone_hidden_dim`
- Rename `mistral_config` → `backbone_config`
- Keep `MistralCGWrapper` as a backward-compatible alias: `MistralCGWrapper = HuggingFaceCGWrapper`

### 2. Update `config.py` — add generic config fields

Add new generic fields alongside existing Mistral ones (backward compat):
```python
# Generic HuggingFace CG Wrapper (--model_type hf_cg)
hf_model_name: str = "mistralai/Mistral-7B-v0.3"   # Any HuggingFace model ID
hf_quantize: str = "none"                            # "none", "4bit", "8bit"
hf_device_map: str = "auto"
hf_trust_remote_code: bool = False
hf_phase_adapter_hidden: int = 1024
```

Keep existing `mistral_*` fields as aliases (read from `hf_*` if `mistral_*` not explicitly set).

### 3. Update `model_factory.py`

- Add new model type `"hf_cg"` alongside `"mistral_cg"`
- Both use `HuggingFaceCGWrapper`
- `mistral_cg` reads from `config.mistral_*` fields (backward compat)
- `hf_cg` reads from `config.hf_*` fields

### 4. Add model-specific presets (convenience)

In config or docs, document tested model IDs:
```
mistralai/Mistral-7B-v0.3      # 7B, 4096 hidden, 32 heads
Qwen/Qwen2.5-7B                # 7B, 4096 hidden, 32 heads, strong multilingual
meta-llama/Llama-3.1-8B         # 8B, 4096 hidden, 32 heads (needs access token)
google/gemma-2-9b               # 9B, 3584 hidden, 16 heads (different shape)
microsoft/Phi-3-medium-4k       # 14B, 5120 hidden, 40 heads
```

### 5. Handle model-specific quirks

Some models need `trust_remote_code=True` (Qwen, Phi). Add auto-detection:
```python
TRUST_REMOTE_CODE_MODELS = ["Qwen", "Phi", "chatglm", "baichuan"]

def _needs_trust_remote_code(model_name: str) -> bool:
    return any(prefix in model_name for prefix in TRUST_REMOTE_CODE_MODELS)
```

Some models have different `lm_head` access patterns. The current fallback in `forward()` already handles this:
```python
if hasattr(self.backbone, 'lm_head'):
    logits = self.backbone.lm_head(adapted_hidden)
else:
    logits = backbone_out.logits  # fallback
```

### 6. Update `train_unified_llm.py` CLI help / docs

Add examples:
```bash
# Qwen2.5-7B with conscious generation
python train_unified_llm.py \
    --model_type hf_cg \
    --hf_model_name Qwen/Qwen2.5-7B \
    --hf_quantize 4bit \
    --enable_conscious_generation \
    --lambda_ont 0.01

# Llama-3.1-8B with conscious generation
python train_unified_llm.py \
    --model_type hf_cg \
    --hf_model_name meta-llama/Llama-3.1-8B \
    --hf_quantize 4bit \
    --enable_conscious_generation \
    --lambda_ont 0.01
```

## What NOT to change
- The CG module architecture (Phase 1-4) — unchanged
- The training loop — unchanged
- The output dict format — unchanged
- The `mistral_cg` model type — kept as alias for backward compat

## Testing
After implementation, verify with:
1. `--model_type mistral_cg` still works (backward compat)
2. `--model_type hf_cg --hf_model_name Qwen/Qwen2.5-7B` loads correctly
3. CG modules attach and train normally with new backbone

## Files Modified
1. `symbolu/training/unified/hf_wrapper.py` (new, based on `mistral_wrapper.py`)
2. `symbolu/training/unified/mistral_wrapper.py` (kept, imports from `hf_wrapper`)
3. `symbolu/training/unified/config.py` (add `hf_*` fields)
4. `symbolu/training/unified/model_factory.py` (add `hf_cg` model type)
5. `docs/TRAIN_UNIFIED_LLM.md` (add examples)
