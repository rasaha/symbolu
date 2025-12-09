"""
Mechanical Layer
=================

Non-patented mechanical processing components:
- MLCR: Multi-Level Consciousness Router
- Fusion: FusionRenderer integration
- Renderer: Rule-based and LLM renderers
- DHA: Delivery Hierarchy Architecture
- Persona: Voice selection
- Router: Ontology routing
- Logging: Explainability and audit
- Schemas: Message and state schemas
- Pipeline: v3.0 linear pipeline orchestrator

Core Bridge provides connection to Symbol-U core.
"""

# CoreBridge requires symbolu.core which may not be available
# Make import optional to allow submodules to work independently
try:
    from mechanical.core_bridge import CoreBridge
    __all__ = ["CoreBridge"]
except ImportError:
    # symbolu.core not available - CoreBridge won't be exported
    __all__ = []
