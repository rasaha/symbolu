# FUSION RENDERER v3.0 - QUICK REFERENCE
==========================================

## Import
```python
from fusion_renderer import (
    FusionRenderer, FusionOutput, RenderMode, Domain
)
```

## Basic Usage
```python
# Create renderer
renderer = FusionRenderer(mode=RenderMode.STANDARD)

# Render
output = renderer.render(fusion_output)

# Access layers
print(output.symbolic_layer.theme)
print(output.practical_layer.key_facts)
print(output.mirror_truth_layer.alignment_score)
```

## Modes
```python
RenderMode.MINIMAL    # Practical only
RenderMode.STANDARD   # All 3 layers (default)
RenderMode.SYMBOLIC   # Deep analysis
RenderMode.REGULATED  # Compliance-safe
```

## Domains
```python
Domain.GENERAL      # Default
Domain.FINANCE      # Regulated
Domain.MEDICAL      # Regulated
Domain.LEGAL        # Regulated
Domain.EDUCATION
Domain.PSYCHOLOGY
```

## Layer Access
```python
# Symbolic Layer (WHY)
output.symbolic_layer.theme
output.symbolic_layer.archetype
output.symbolic_layer.causal_patterns
output.symbolic_layer.meaning_vectors
output.symbolic_layer.dominant_channel
output.symbolic_layer.reasoning_depth

# Practical Layer (WHAT/HOW)
output.practical_layer.key_facts
output.practical_layer.constraints
output.practical_layer.procedures
output.practical_layer.coherence_score
output.practical_layer.domain
output.practical_layer.actionable_items

# Mirror-Truth Layer (REFLECTION)
output.mirror_truth_layer.contradictions
output.mirror_truth_layer.entropy_measures
output.mirror_truth_layer.tensions
output.mirror_truth_layer.alignment_score
output.mirror_truth_layer.stability_indicator
output.mirror_truth_layer.reflection
```

## JSON Output
```python
json_str = output.to_json(indent=2)
parsed = json.loads(json_str)
```

## Statistics
```python
stats = renderer.get_stats()
print(stats['total_renders'])
print(stats['avg_render_time_ms'])
```

## Common Patterns

### Mode Selection
```python
# Fast responses
renderer = FusionRenderer(mode=RenderMode.MINIMAL)

# Regulated domains
renderer = FusionRenderer(
    mode=RenderMode.REGULATED,
    domain=Domain.FINANCE
)

# Deep analysis
renderer = FusionRenderer(mode=RenderMode.SYMBOLIC)
```

### Error Handling
```python
try:
    output = renderer.render(fusion_output)
except ValueError as e:
    print(f"Invalid input: {e}")
```

### Batch Processing
```python
renderer = FusionRenderer()
outputs = [renderer.render(fo) for fo in fusion_outputs]
stats = renderer.get_stats()
```

## Testing
```bash
# Run all tests
pytest test_fusion_renderer.py -v

# Run specific test
pytest test_fusion_renderer.py::TestSymbolicLayer -v

# With coverage
pytest test_fusion_renderer.py --cov=fusion_renderer
```

## Examples
```bash
python examples.py
```

## Key Constraints
- Channel weights must sum to 1.0
- All FusionOutput fields required
- Output is deterministic (same input → same output)
- No LLM involvement (100% deterministic)

## Performance
| Mode | Time | Memory |
|------|------|--------|
| MINIMAL | ~2ms | ~1MB |
| STANDARD | ~5ms | ~2MB |
| SYMBOLIC | ~7ms | ~3MB |
| REGULATED | ~4ms | ~2MB |
