"""
SOULPI Persona Engine (v2.8.2)
==============================

The Persona Engine is SOULPI's expression layer that receives deterministic
cognition and tone selection, then produces persona-styled final messages
without changing meaning.

Pipeline Position:
    MLCR → Hybrid Fusion Engine → FusionRenderer v3.0 → 
    DHA Tone Engine v2.8.1 → Persona Engine v2.8.2 → 
    LLM Enhancement Layer (optional) → Final Output

Key Components:
    - PersonaEngine: Main engine for applying persona styling
    - PersonaSelector: Logic for choosing appropriate persona
    - PersonaRegistry: Storage and retrieval of persona profiles
    - Default personas: sage, analyst, coach, friendly, regulator, neutral

Version: 2.8.2
Author: Rakesh Mohan
Date: December 2025
"""

from .engine import PersonaEngine
from .selector import PersonaSelector
from .registry import PersonaRegistry, get_default_registry
from .models import (
    PersonaProfile,
    RendererOutputV3,
    DHAResult,
    PersonaResponse,
    PersonaMetadata
)

__version__ = "2.8.2"
__all__ = [
    "PersonaEngine",
    "PersonaSelector",
    "PersonaRegistry",
    "get_default_registry",
    "PersonaProfile",
    "RendererOutputV3",
    "DHAResult",
    "PersonaResponse",
    "PersonaMetadata"
]
