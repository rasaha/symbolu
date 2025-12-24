# SOULPI Fusion Renderer v3.0

**The deterministic bridge between FusionEngine cognition and presentation layers.**

## 📋 Overview

The Fusion Renderer is a critical component of the SOULPI v2.8.3 architecture that transforms raw `FusionOutput` from the FusionEngine into structured, human-interpretable format through three distinct layers. It maintains 100% deterministic behavior without LLM involvement, ensuring explainability and patent protection.

### Core Purpose
- Transform FusionEngine output into structured presentation format
- Maintain complete determinism (no LLM)
- Preserve meaning without modification
- Expose contradictions without resolving them
- Propagate metadata exactly

## 🏗️ Architecture

### Three-Layer Structure

1. **Symbolic Layer** - The "WHY"
   - Theme and core meaning
   - Archetype identification
   - Causal patterns
   - Meaning vectors
   - Reasoning depth

2. **Practical Layer** - The "WHAT/HOW"
   - Key facts
   - Constraints
   - Procedures
   - Coherence score
   - Actionable items

3. **Mirror-Truth Layer** - Reflective Synthesis
   - Contradictions
   - Entropy measures
   - Tensions
   - Alignment score
   - Stability assessment
   - Meta-reflection

### Operating Modes

| Mode | Symbolic | Practical | Mirror-Truth | Use Case |
|------|----------|-----------|--------------|----------|
| `MINIMAL` | ❌ | ✅ | ❌ | Fast, action-oriented |
| `STANDARD` | ✅ | ✅ | ✅ | Balanced (default) |
| `SYMBOLIC` | ✅✅ | ✅ | ✅ | Deep analysis |
| `REGULATED` | ⚠️ | ✅✅ | ⚠️ | Compliance-safe |

## 🚀 Quick Start

### Basic Usage

```python
from fusion_renderer import FusionRenderer, FusionOutput, RenderMode

# Create FusionOutput (from FusionEngine)
fusion_output = FusionOutput(
    query="How can AI improve healthcare?",
    merged_response="AI can improve healthcare through...",
    hrm_content={"reasoning": "Healthcare AI represents..."},
    lcm_content={"content": "AI improves diagnostics..."},
    moe_content={"content": "Healthcare requires FDA approval..."},
    channel_weights={"hrm": 0.4, "lcm": 0.35, "moe": 0.25},
    conflict_resolution=[],
    metadata={}
)

# Render with standard mode
renderer = FusionRenderer(mode=RenderMode.STANDARD)
output = renderer.render(fusion_output)

# Access layers
print(output.symbolic_layer.theme)
print(output.practical_layer.key_facts)
print(output.mirror_truth_layer.alignment_score)
```

### Mode Selection

```python
# Minimal mode (practical only)
renderer = FusionRenderer(mode=RenderMode.MINIMAL)

# Symbolic mode (deep analysis)
renderer = FusionRenderer(mode=RenderMode.SYMBOLIC)

# Regulated mode (finance, medical, legal)
renderer = FusionRenderer(
    mode=RenderMode.REGULATED,
    domain=Domain.FINANCE
)
```

### JSON Output

```python
output = renderer.render(fusion_output)
json_str = output.to_json(indent=2)
print(json_str)
```

## 📊 Algorithm Flow

```
Step 1: Validate Input
   ↓
Step 2: Build Symbolic Layer
   - Extract theme from HRM
   - Identify archetype
   - Extract causal patterns
   - Compute meaning vectors
   ↓
Step 3: Build Practical Layer
   - Extract key facts from LCM
   - Extract constraints from MoE
   - Extract procedures
   - Compute coherence
   ↓
Step 4: Build Mirror-Truth Layer
   - Detect contradictions
   - Compute entropy measures
   - Identify tensions
   - Compute alignment
   ↓
Step 5: Propagate Metadata
   ↓
Step 6: Apply Mode Overrides
   ↓
Output: RenderedOutput
```

## 🔬 Key Features

### 1. Deterministic Processing
- No random number generation
- Same input → Same output (always)
- Hash-based selections for consistency

### 2. Layer Weights by Mode
```python
MODE_WEIGHTS = {
    MINIMAL:   {"symbolic": 0.0, "practical": 1.0, "mirror": 0.0},
    STANDARD:  {"symbolic": 0.33, "practical": 0.34, "mirror": 0.33},
    SYMBOLIC:  {"symbolic": 0.6, "practical": 0.2, "mirror": 0.2},
    REGULATED: {"symbolic": 0.1, "practical": 0.8, "mirror": 0.1}
}
```

### 3. Domain Awareness
```python
# Regulated domains
REGULATED_DOMAINS = {Domain.FINANCE, Domain.MEDICAL, Domain.LEGAL}

# Domain-specific rendering
renderer = FusionRenderer(domain=Domain.MEDICAL)
# Automatically applies safety constraints
```

### 4. Metadata Preservation
All metadata from FusionEngine is propagated exactly, with additional rendering metadata:
- `render_mode`
- `render_domain`
- `is_regulated`
- `layer_weights`

## 📦 Installation

```bash
# Dependencies
pip install numpy

# Optional (for testing)
pip install pytest
```

## 🧪 Testing

```bash
# Run all tests
pytest test_fusion_renderer.py -v

# Run specific test class
pytest test_fusion_renderer.py::TestSymbolicLayer -v

# Run with coverage
pytest test_fusion_renderer.py --cov=fusion_renderer
```

### Test Coverage
- ✅ Unit tests for each layer builder
- ✅ Integration tests for full pipeline
- ✅ Mode-specific behavior validation
- ✅ Determinism verification
- ✅ Edge case handling
- ✅ Statistics tracking

## 📖 Examples

Run the examples file to see all usage scenarios:

```bash
python examples.py
```

Examples include:
1. Basic rendering (all modes)
2. Mode comparison
3. Domain-specific rendering
4. JSON output
5. Layer-by-layer access
6. Statistics tracking
7. Error handling

## 🔍 API Reference

### Classes

#### `FusionRenderer`
Main rendering class.

**Constructor:**
```python
FusionRenderer(
    mode: RenderMode = RenderMode.STANDARD,
    domain: Domain = Domain.GENERAL
)
```

**Methods:**
- `render(fusion_output: FusionOutput) -> RenderedOutput`
- `get_stats() -> Dict[str, Any]`

#### `FusionOutput` (Input)
Raw output from FusionEngine.

**Fields:**
- `query: str`
- `merged_response: str`
- `hrm_content: Dict[str, Any]`
- `lcm_content: Dict[str, Any]`
- `moe_content: Dict[str, Any]`
- `channel_weights: Dict[str, float]`
- `conflict_resolution: List[Dict[str, Any]]`
- `metadata: Dict[str, Any]`

#### `RenderedOutput` (Output)
Structured output with three layers.

**Fields:**
- `query: str`
- `mode: str`
- `symbolic_layer: Optional[SymbolicLayer]`
- `practical_layer: Optional[PracticalLayer]`
- `mirror_truth_layer: Optional[MirrorTruthLayer]`
- `metadata: Dict[str, Any]`
- `render_timestamp: float`

**Methods:**
- `to_dict() -> Dict`
- `to_json(indent: int = 2) -> str`

### Enums

#### `RenderMode`
- `MINIMAL` - Practical layer only
- `STANDARD` - All three layers
- `SYMBOLIC` - Symbolic expanded
- `REGULATED` - Compliance-safe

#### `Domain`
- `GENERAL`
- `FINANCE`
- `MEDICAL`
- `LEGAL`
- `EDUCATION`
- `PSYCHOLOGY`

## 🔐 Patent Protection

This module is part of the Symbol-U AGI patent-protected system.

**Core Constraints:**
- ✅ 100% deterministic (no LLM in core logic)
- ✅ Preserves meaning without modification
- ✅ Exposes contradictions, doesn't resolve them
- ✅ Metadata propagation exact

**Patent Alignment:**
- Section §147: Mirror logic operations
- Section §150: Three-force balancing
- Section §235: Adaptive rendering
- Section §302: Layer decomposition

## 📊 Performance

Typical rendering times (on standard hardware):

| Mode | Average Time | Memory |
|------|-------------|--------|
| MINIMAL | ~2ms | ~1MB |
| STANDARD | ~5ms | ~2MB |
| SYMBOLIC | ~7ms | ~3MB |
| REGULATED | ~4ms | ~2MB |

## 🔄 Integration

### Upstream: FusionEngine
```python
from fusion_engine import FusionEngine

# FusionEngine produces FusionOutput
fusion_engine = FusionEngine()
fusion_output = fusion_engine.process(query, hrm, lcm, moe)

# Pass to Renderer
renderer = FusionRenderer()
rendered = renderer.render(fusion_output)
```

### Downstream: Persona/DHA Engine
```python
from persona_engine import PersonaEngine

# Renderer output feeds Persona Engine
persona_engine = PersonaEngine()
final_output = persona_engine.render(
    rendered_output=rendered,
    persona="professional"
)
```

## 🐛 Troubleshooting

### Common Issues

**1. Channel weights don't sum to 1.0**
```python
# Error: Channel weights must sum to 1.0, got 1.1
# Fix: Ensure weights are normalized
weights = {"hrm": 0.5, "lcm": 0.3, "moe": 0.2}  # ✓ Sums to 1.0
```

**2. Missing required fields**
```python
# Error: FusionOutput missing required field: channel_weights
# Fix: Include all required fields
fusion_output = FusionOutput(
    query="...",
    merged_response="...",
    hrm_content={},
    lcm_content={},
    moe_content={},
    channel_weights={"hrm": 0.33, "lcm": 0.33, "moe": 0.34},  # Required
    conflict_resolution=[],
    metadata={}
)
```

**3. Empty content handling**
```python
# The renderer handles empty content gracefully with defaults
fusion_output = FusionOutput(
    query="Test",
    merged_response="Test",
    hrm_content={},  # Empty is OK
    lcm_content={},  # Empty is OK
    moe_content={},  # Empty is OK
    channel_weights={"hrm": 0.33, "lcm": 0.33, "moe": 0.34},
    conflict_resolution=[],
    metadata={}
)
```

## 📝 Version History

### v3.0 (Current)
- Initial release
- Three-layer architecture
- Four operating modes
- Domain awareness
- Complete test suite
- Patent-protected algorithms

## 🤝 Contributing

This module is part of the SOULPI v2.8.3 framework. For contributions:
1. Maintain deterministic behavior
2. Preserve patent-protected algorithms
3. Add tests for new features
4. Update documentation

## 📄 License

Patent-protected technology. See LICENSE file for details.

## 👨‍💻 Author

Rakesh Mohan - Symbol-U AGI System

## 🔗 Related Modules

- `fusion_engine.py` - Upstream processor
- `persona_engine.py` - Downstream renderer
- `dha_engine.py` - Delivery handler
- `mlcr_module.py` - Multi-layer consciousness router

---

**Note:** This is a deterministic module with zero LLM involvement. All behavior is explainable and reproducible.
