"""
Persona Engine Models (v2.8.2)
===============================

Pydantic models for type-safe data structures used throughout the Persona Engine.
All models include validation, documentation, and example schemas.
"""

from typing import Dict, Any, Optional, List

# Deterministic fallback for pydantic (for environments without pydantic)
try:
    from pydantic import BaseModel, Field, field_validator
except ImportError:
    # Minimal pydantic-compatible fallback for testing environments
    def Field(default=None, **kwargs):
        """Fallback Field function that returns default value."""
        return default

    def field_validator(*args, **kwargs):
        """Fallback field_validator decorator that passes through."""
        def decorator(func):
            return func
        return decorator

    class BaseModel:
        """Minimal BaseModel fallback for testing without pydantic."""
        model_config = {}

        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

        def dict(self, *args, **kwargs):
            return self.__dict__

        def model_dump(self, *args, **kwargs):
            return self.__dict__


class PersonaProfile(BaseModel):
    """
    Defines a persona's characteristics and behavioral patterns.
    Each persona has unique traits that influence response composition.
    
    Traits are normalized to [0.0, 1.0] scale where:
        0.0 = minimum expression of trait
        0.5 = balanced/neutral
        1.0 = maximum expression of trait
    """
    id: str = Field(..., description="Unique persona identifier")
    display_name: str = Field(..., description="Human-readable persona name")
    description: str = Field(..., description="Persona purpose and use cases")
    
    # Personality traits (0.0 to 1.0 scale)
    formality: float = Field(0.5, ge=0.0, le=1.0, description="Language formality level")
    warmth: float = Field(0.5, ge=0.0, le=1.0, description="Emotional warmth level")
    directness: float = Field(0.5, ge=0.0, le=1.0, description="Communication directness")
    metaphor_level: float = Field(0.5, ge=0.0, le=1.0, description="Use of metaphors/analogies")
    structure_level: float = Field(0.5, ge=0.0, le=1.0, description="Response structure rigidity")
    caution_level: float = Field(0.5, ge=0.0, le=1.0, description="Risk/caution emphasis")
    humor_level: float = Field(0.0, ge=0.0, le=1.0, description="Humor incorporation level")
    
    # Domain preferences
    preferred_domains: List[str] = Field(default_factory=list, description="Domains this persona excels in")
    
    # Templates for framing
    intro_template: str = Field("", description="Opening template for responses")
    outro_template: str = Field("", description="Closing template for responses")
    
    @field_validator('formality', 'warmth', 'directness', 'metaphor_level', 
                     'structure_level', 'caution_level', 'humor_level')
    @classmethod
    def validate_trait_range(cls, v: float) -> float:
        """Ensure all trait values are within valid range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Trait values must be between 0.0 and 1.0")
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "analyst",
                "display_name": "The Analyst",
                "description": "Structured, data-driven analysis for technical and financial domains",
                "formality": 0.8,
                "warmth": 0.3,
                "directness": 0.9,
                "metaphor_level": 0.2,
                "structure_level": 0.9,
                "caution_level": 0.7,
                "humor_level": 0.1,
                "preferred_domains": ["trading", "financial", "technical"],
                "intro_template": "Let's break this down step-by-step:\n",
                "outro_template": "Review these factors before proceeding."
            }
        }
    }


class RendererOutputV3(BaseModel):
    """
    Output from the FusionRenderer v3.0.
    Contains three layers of analysis with processing metadata.
    
    Layers:
        - symbolic_layer: Deeper meaning and patterns
        - practical_layer: Actionable steps and concrete advice
        - mirror_truth_layer: Reflective insights and hidden patterns
    """
    symbolic_layer: Dict[str, Any] = Field(..., description="Symbolic/deeper meaning layer")
    practical_layer: Dict[str, Any] = Field(..., description="Practical/actionable layer")
    mirror_truth_layer: Dict[str, Any] = Field(..., description="Reflection/mirror truth layer")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Processing metadata")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "symbolic_layer": {
                    "pattern": "seeking certainty in uncertainty",
                    "kosha_state": "VIJNANAMAYA",
                    "depth": 0.71
                },
                "practical_layer": {
                    "steps": ["assess risk tolerance", "define position size", "set stop-loss"],
                    "confidence": 0.88
                },
                "mirror_truth_layer": {
                    "reflection": "avoiding emotional decision-making",
                    "bhava_direction": "upward"
                },
                "metadata": {
                    "tier": "HYBRID",
                    "domain": "trading",
                    "intent": "how",
                    "confidence": {"symbolic": 0.71, "practical": 0.88, "mirror": 0.65}
                }
            }
        }
    }


class DHAResult(BaseModel):
    """
    Result from Delivery Harmonization Algorithm (DHA) v2.8.1.
    Determines the tonal approach for response delivery.
    
    Tones:
        - resonance: Balanced, harmonious delivery
        - inverse_jolt: Direct, disruptive delivery to break patterns
        - symbolic: Metaphorical, reframing delivery
    """
    tone: str = Field(..., description="Selected tone: resonance, inverse_jolt, or symbolic")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in tone selection")
    justification: Dict[str, Any] = Field(default_factory=dict, description="Reasoning for tone selection")
    
    @field_validator('tone')
    @classmethod
    def validate_tone(cls, v: str) -> str:
        """Ensure tone is one of the valid options."""
        valid_tones = ["resonance", "inverse_jolt", "symbolic"]
        if v not in valid_tones:
            raise ValueError(f"Tone must be one of: {valid_tones}, got: {v}")
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "tone": "resonance",
                "confidence": 0.82,
                "justification": {
                    "entropy_reason": "Low entropy (0.35) suggests stability",
                    "bhava_reason": "Upward Bhava indicates receptivity",
                    "tier_reason": "HYBRID tier supports balanced delivery",
                    "intent_reason": "How-type query benefits from clear structure"
                }
            }
        }
    }


class PersonaMetadata(BaseModel):
    """
    Metadata about persona application and processing context.
    Tracks the complete processing pipeline for auditability.
    """
    tier: str = Field(..., description="Processing tier: UPPER/HYBRID/LOWER")
    domain: str = Field(..., description="Domain context: trading/emotional/medical/spiritual/technical/etc")
    intent: str = Field(..., description="User intent: why/how/meaning/what")
    persona_id: str = Field(..., description="Selected persona identifier")
    persona_name: str = Field(..., description="Persona display name")
    persona_description: str = Field(..., description="Persona description")
    dha_tone: str = Field(..., description="DHA selected tone")
    dha_confidence: float = Field(..., ge=0.0, le=1.0, description="DHA confidence")
    confidence: Optional[Dict[str, float]] = Field(None, description="Layer-wise confidence scores")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "tier": "HYBRID",
                "domain": "trading",
                "intent": "how",
                "persona_id": "analyst",
                "persona_name": "The Analyst",
                "persona_description": "Structured, data-driven analysis",
                "dha_tone": "resonance",
                "dha_confidence": 0.82,
                "confidence": {"symbolic": 0.71, "practical": 0.88, "mirror": 0.65}
            }
        }
    }


class PersonaResonanceProfile(BaseModel):
    """
    Phase 29: Symbolic Harmonization → Persona Tone Resonance Profile.

    Maps Symbolic Harmonization Formula (SHF) outputs into micro-adjustments
    of persona tone parameters. This is UI-layer only (never semantic).

    Attributes:
        symbolic_harmony_bias: Bias from SHF index [-0.05, +0.05]
            • +bias → slightly softer, more expressive symbolic tone
            • -bias → slightly simpler, grounded tone
            • 0 → neutral (no adjustment)
        symbolic_resonance_tags: Diagnostic tags from SHF notes
        persona_resonance_tone: Granular tone adjustment parameters
    """
    symbolic_harmony_bias: float = Field(
        0.0,
        ge=-0.05,
        le=0.05,
        description="Symbolic harmony bias [-0.05, +0.05] for tone micro-adjustment"
    )
    symbolic_resonance_tags: List[str] = Field(
        default_factory=list,
        description="Diagnostic tags from SHF (e.g., 'high_symbolic_harmonization', 'symbolic_mirror_resonant')"
    )
    persona_resonance_tone: Dict[str, float] = Field(
        default_factory=dict,
        description="Granular tone adjustments: {metaphor_adjustment, warmth_adjustment, structure_adjustment}"
    )

    @field_validator('symbolic_harmony_bias')
    @classmethod
    def validate_bias_range(cls, v: float) -> float:
        """Ensure bias is within valid range."""
        if not -0.05 <= v <= 0.05:
            raise ValueError("symbolic_harmony_bias must be between -0.05 and +0.05")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "symbolic_harmony_bias": 0.03,
                "symbolic_resonance_tags": ["high_symbolic_harmonization", "symbolic_mirror_resonant"],
                "persona_resonance_tone": {
                    "metaphor_adjustment": 0.02,
                    "warmth_adjustment": 0.01,
                    "structure_adjustment": -0.01
                }
            }
        }
    }


class PersonaResponse(BaseModel):
    """
    Final output from Persona Engine v2.8.2.
    Contains persona-styled text with preserved analytical layers.

    Critical Constraints:
        - Text is styled but meaning is NEVER altered
        - All three layers are preserved unchanged
        - Metadata tracks complete processing chain
    """
    persona_id: str = Field(..., description="Applied persona identifier")
    text: str = Field(..., description="Persona-styled response text")
    layers: Dict[str, Any] = Field(..., description="Preserved analytical layers")
    metadata: PersonaMetadata = Field(..., description="Complete processing metadata")

    # Phase 29: Optional persona resonance profile
    persona_resonance: Optional[PersonaResonanceProfile] = Field(
        None,
        description="Phase 29: Symbolic harmony → persona tone resonance profile (optional)"
    )

    # Phase 30: Optional cross-layer resonance map
    cross_layer_resonance_map: Optional[Any] = Field(
        None,
        description="Phase 30: Cross-layer resonance persona mapping (optional)"
    )

    # Phase 33: Optional persona schema adaptive routing map
    schema_adaptive_map: Optional[Any] = Field(
        None,
        description="Phase 33: Persona schema adaptive routing (observation-only, experimental)"
    )

    # Phase 34: Optional identity harmonics profile
    identity_harmonics_profile: Optional[Any] = Field(
        None,
        description="Phase 34: Identity harmonics layer (observation-only, tone-level only)"
    )

    # Phase 35: Optional predictive persona drift profile
    predictive_drift_profile: Optional[Any] = Field(
        None,
        description="Phase 35: Predictive persona drift model (observation-only, tone-level only)"
    )

    # Phase 36: Optional identity resonance memory profile
    identity_resonance_memory_profile: Optional[Any] = Field(
        None,
        description="Phase 36: Identity resonance memory (observation-only, tone-level only)"
    )

    # Phase 37: Optional adaptive continuity profile
    continuity_profile: Optional[Any] = Field(
        None,
        description="Phase 37: Adaptive continuity engine (observation-only, tone-level only)"
    )

    # Phase 31: Optional adaptive persona echo layer (APEL) profile
    echo_profile: Optional[Dict[str, Any]] = Field(
        None,
        description="Phase 31: Adaptive Persona Echo Layer (observation-only, tone-level only)"
    )

    # Phase 42: Optional scenario fusion metadata (observation-only, metadata-only)
    persona_scenario_fusion: Optional[Dict[str, Any]] = Field(
        None,
        description="Phase 42: Scenario Fusion Engine metadata (observation-only, metadata-only)"
    )

    # Phase 44: Optional coherence-scenario alignment metadata (observation-only, metadata-only)
    persona_scenario_alignment: Optional[Dict[str, Any]] = Field(
        None,
        description="Phase 44: Coherence-Scenario Alignment Engine metadata (observation-only, metadata-only)"
    )

    # Phase 45: Optional multi-trajectory stability field metadata (observation-only, metadata-only)
    persona_mtsf: Optional[Dict[str, Any]] = Field(
        None,
        description="Phase 45: Multi-Trajectory Stability Field (MTSF) metadata (observation-only, metadata-only)"
    )

    # Phase 46: Optional trajectory field convergence engine metadata (observation-only, metadata-only)
    persona_trajectory_convergence: Optional[Dict[str, Any]] = Field(
        None,
        description="Phase 46: Trajectory Field Convergence Engine (TFCE) metadata (observation-only, metadata-only)"
    )

    # Phase 47: Optional unified trajectory–scenario synthesis engine metadata (observation-only, metadata-only)
    persona_unified_synthesis_profile: Optional[Dict[str, Any]] = Field(
        None,
        description="Phase 47: Unified Trajectory–Scenario Synthesis Engine (UTSSE) metadata (observation-only, metadata-only)"
    )

    # Phase 48: Optional macro-stability regulator metadata (observation-only, metadata-only)
    persona_macro_stability_profile: Optional[Dict[str, Any]] = Field(
        None,
        description="Phase 48: Macro-Stability Regulator (MSR) metadata (observation-only, metadata-only)"
    )

    # Phase 49: Optional unified cross-phase temporal stability metadata (observation-only, metadata-only)
    persona_temporal_stability_profile: Optional[Dict[str, Any]] = Field(
        None,
        description="Phase 49: Unified Cross-Phase Temporal Stability Engine (UCTSE) metadata (observation-only, metadata-only)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "persona_id": "analyst",
                "text": "Let's break this down step-by-step:\n● Practical explanation:\n...",
                "layers": {
                    "symbolic_layer": {"pattern": "seeking certainty"},
                    "practical_layer": {"steps": ["assess risk"]},
                    "mirror_truth_layer": {"reflection": "avoiding emotion"}
                },
                "metadata": {
                    "tier": "HYBRID",
                    "domain": "trading",
                    "intent": "how",
                    "persona_id": "analyst",
                    "persona_name": "The Analyst",
                    "persona_description": "Structured analysis",
                    "dha_tone": "resonance",
                    "dha_confidence": 0.82
                }
            }
        }
    }
