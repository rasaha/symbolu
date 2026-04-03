"""
Persona Engine Snapshot Tests (v1.0)
======================================

Deterministic snapshot tests for PersonaEngine.
These tests lock the behavioral contract of the Persona layer.

Test Categories:
    1. Standard persona role snapshot (neutral persona)
    2. Supportive persona style snapshot (friendly persona)
    3. Strict persona tone snapshot (regulator persona)

Key Properties Tested:
    - Persona voice/template selection
    - Layer ordering based on tone
    - Format and structure
    - Role cues and shaping logic
    - Style transformation (deterministic)

CRITICAL: These tests are LLM-free and fully deterministic.
"""

import pytest
import json
from pathlib import Path
from typing import Dict, Any

# Import snapshot utilities from renderer
from symbolu_core.renderer.tests.snapshot_utils import assert_snapshot

# Import PersonaEngine and models
from symbolu_core.mechanical.persona.engine import PersonaEngine
from symbolu_core.mechanical.persona.models import (
    RendererOutputV3,
    DHAResult,
    PersonaProfile,
    PersonaResponse
)
from symbolu_core.mechanical.persona.registry import PersonaRegistry
from symbolu_core.mechanical.persona.default_personas import (
    NEUTRAL_PERSONA,
    FRIENDLY_PERSONA,
    REGULATOR_PERSONA,
    ANALYST_PERSONA,
    SAGE_PERSONA
)


# =============================================================================
# SNAPSHOT DIRECTORY
# =============================================================================

SNAPSHOT_DIR = Path(__file__).parent.parent / "snapshots"


# =============================================================================
# DETERMINISTIC TEST FIXTURES
# =============================================================================

def create_standard_renderer_output() -> RendererOutputV3:
    """
    Create a deterministic RendererOutputV3 for testing.
    No randomness, timestamps, or UUIDs.
    """
    return RendererOutputV3(
        symbolic_layer={
            "pattern": "seeking_clarity_through_analysis",
            "kosha_state": "VIJNANAMAYA",
            "depth": 0.72,
            "archetypes": ["seeker", "analyst"],
            "symbolic_threads": [
                "uncertainty drives the question",
                "knowledge dispels fear"
            ]
        },
        practical_layer={
            "steps": [
                "Define the core objective",
                "Gather relevant data points",
                "Analyze patterns and correlations",
                "Formulate actionable recommendations"
            ],
            "confidence": 0.85,
            "domain_fit": "technical",
            "complexity": "moderate"
        },
        mirror_truth_layer={
            "reflection": "beneath the technical query lies a desire for certainty",
            "bhava_direction": "upward",
            "hidden_patterns": [
                "fear of making wrong decisions",
                "need for external validation"
            ],
            "growth_edge": "trusting internal judgment"
        },
        metadata={
            "tier": "HYBRID",
            "domain": "technical",
            "intent": "how",
            "confidence": {
                "symbolic": 0.72,
                "practical": 0.85,
                "mirror": 0.68
            }
        }
    )


def create_emotional_renderer_output() -> RendererOutputV3:
    """
    Create a renderer output for emotional/supportive context.
    """
    return RendererOutputV3(
        symbolic_layer={
            "pattern": "navigating_emotional_uncertainty",
            "kosha_state": "MANOMAYA",
            "depth": 0.65,
            "archetypes": ["caregiver", "healer"],
            "symbolic_threads": [
                "emotions seeking expression",
                "connection as healing"
            ]
        },
        practical_layer={
            "steps": [
                "Acknowledge the feelings present",
                "Create space for expression",
                "Identify support resources",
                "Take small comfort steps"
            ],
            "confidence": 0.78,
            "domain_fit": "emotional",
            "complexity": "sensitive"
        },
        mirror_truth_layer={
            "reflection": "the heart seeks understanding before advice",
            "bhava_direction": "inward",
            "hidden_patterns": [
                "longing for connection",
                "fear of vulnerability"
            ],
            "growth_edge": "allowing oneself to be supported"
        },
        metadata={
            "tier": "UPPER",
            "domain": "emotional",
            "intent": "meaning",
            "confidence": {
                "symbolic": 0.65,
                "practical": 0.78,
                "mirror": 0.82
            }
        }
    )


def create_regulated_renderer_output() -> RendererOutputV3:
    """
    Create a renderer output for regulated/medical context.
    """
    return RendererOutputV3(
        symbolic_layer={
            "pattern": "navigating_health_decisions",
            "kosha_state": "ANNAMAYA",
            "depth": 0.55,
            "archetypes": ["guardian", "protector"],
            "symbolic_threads": [
                "body as vessel requiring care",
                "responsibility for wellbeing"
            ]
        },
        practical_layer={
            "steps": [
                "Document current symptoms accurately",
                "Research qualified healthcare providers",
                "Prepare questions for medical consultation",
                "Follow professional medical guidance"
            ],
            "confidence": 0.92,
            "domain_fit": "medical",
            "complexity": "regulated"
        },
        mirror_truth_layer={
            "reflection": "health concerns require professional expertise",
            "bhava_direction": "cautious",
            "hidden_patterns": [
                "desire for reassurance",
                "anxiety about unknown outcomes"
            ],
            "growth_edge": "trusting medical professionals"
        },
        metadata={
            "tier": "LOWER",
            "domain": "medical",
            "intent": "how",
            "confidence": {
                "symbolic": 0.55,
                "practical": 0.92,
                "mirror": 0.61
            }
        }
    )


def create_dha_result(tone: str = "resonance", confidence: float = 0.82) -> DHAResult:
    """
    Create a deterministic DHAResult for testing.
    """
    justifications = {
        "resonance": {
            "entropy_reason": "Low entropy (0.35) suggests stability",
            "bhava_reason": "Upward Bhava indicates receptivity",
            "tier_reason": "HYBRID tier supports balanced delivery",
            "intent_reason": "How-type query benefits from clear structure"
        },
        "inverse_jolt": {
            "entropy_reason": "High entropy (0.78) indicates confusion",
            "bhava_reason": "Stagnant Bhava requires disruption",
            "tier_reason": "Pattern breaking needed",
            "intent_reason": "Direct truth delivery required"
        },
        "symbolic": {
            "entropy_reason": "Medium entropy allows metaphorical exploration",
            "bhava_reason": "Inward Bhava suits reflective delivery",
            "tier_reason": "UPPER tier supports symbolic framing",
            "intent_reason": "Why/meaning query benefits from metaphor"
        }
    }

    return DHAResult(
        tone=tone,
        confidence=confidence,
        justification=justifications.get(tone, justifications["resonance"])
    )


def create_explain_log(
    tier: str = "HYBRID",
    domain: str = "technical",
    intent: str = "how"
) -> Dict[str, Any]:
    """
    Create a deterministic MLCR explain log for persona selection.
    """
    return {
        "tier": tier,
        "domain": domain,
        "intent": intent,
        "entropy": {"total_entropy": 0.35, "semantic_entropy": 0.32, "ontology_entropy": 0.38},
        "ontology_mass": {"upper": 0.4, "lower": 0.6},
        "kosha_signature": [0.1, 0.2, 0.5, 0.15, 0.05],
        "processing_path": "MLCR -> Fusion -> Renderer -> DHA -> Persona",
        "decision_log": [
            "Input classified as technical domain",
            "Intent detected as how-type query",
            "HYBRID tier selected for balanced processing"
        ]
    }


def persona_response_to_snapshot_string(response: PersonaResponse) -> str:
    """
    Convert PersonaResponse to deterministic snapshot string.
    Excludes non-deterministic fields.
    """
    lines = [
        "=" * 70,
        "PERSONA ENGINE SNAPSHOT",
        "=" * 70,
        "",
        f"Persona ID: {response.persona_id}",
        "",
        "--- STYLED TEXT ---",
        response.text,
        "",
        "--- LAYERS (preserved, unmodified) ---",
        json.dumps(response.layers, indent=2, sort_keys=True),
        "",
        "--- METADATA ---",
        f"Tier: {response.metadata.tier}",
        f"Domain: {response.metadata.domain}",
        f"Intent: {response.metadata.intent}",
        f"Persona Name: {response.metadata.persona_name}",
        f"Persona Description: {response.metadata.persona_description}",
        f"DHA Tone: {response.metadata.dha_tone}",
        f"DHA Confidence: {response.metadata.dha_confidence}",
        "",
        "=" * 70
    ]

    return "\n".join(lines)


# =============================================================================
# TEST 1: STANDARD PERSONA (NEUTRAL) SNAPSHOT
# =============================================================================

class TestPersonaStandardSnapshot:
    """
    Test standard/neutral persona application.

    Characteristics:
        - Balanced traits (all 0.5 except humor at 0.0)
        - Minimal personality injection
        - Objective layer presentation
        - Default practical -> symbolic -> mirror ordering
    """

    def test_persona_standard_snapshot(self):
        """
        Snapshot test for neutral persona with resonance tone.

        Expected behavior:
            - Neutral voice with objective intro
            - Practical layer first (neutral prefers practical)
            - Standard headers without tone modifications
            - Minimal outro
        """
        # Create engine with explicit neutral persona
        engine = PersonaEngine()

        # Create deterministic inputs
        renderer_output = create_standard_renderer_output()
        dha_result = create_dha_result(tone="resonance", confidence=0.82)
        explain_log = create_explain_log(tier="HYBRID", domain="technical", intent="how")

        # Force neutral persona selection
        response = engine.apply(
            renderer_output=renderer_output,
            dha_result=dha_result,
            explain_log=explain_log,
            user_persona_override="neutral"
        )

        # Convert to snapshot string
        snapshot_output = persona_response_to_snapshot_string(response)

        # Assert against snapshot
        snapshot_path = SNAPSHOT_DIR / "persona_standard.snap"
        assert_snapshot(snapshot_output, snapshot_path)

    def test_persona_standard_analyst_snapshot(self):
        """
        Snapshot test for analyst persona (standard for technical domain).

        Expected behavior:
            - Analyst voice with step-by-step intro
            - Practical layer first (analyst prefers practical)
            - High structure in presentation
            - Clear action-oriented outro
        """
        engine = PersonaEngine()

        renderer_output = create_standard_renderer_output()
        dha_result = create_dha_result(tone="resonance", confidence=0.85)
        explain_log = create_explain_log(tier="HYBRID", domain="trading", intent="how")

        # Force analyst persona selection
        response = engine.apply(
            renderer_output=renderer_output,
            dha_result=dha_result,
            explain_log=explain_log,
            user_persona_override="analyst"
        )

        snapshot_output = persona_response_to_snapshot_string(response)
        snapshot_path = SNAPSHOT_DIR / "persona_analyst.snap"
        assert_snapshot(snapshot_output, snapshot_path)


# =============================================================================
# TEST 2: SUPPORTIVE PERSONA (FRIENDLY) SNAPSHOT
# =============================================================================

class TestPersonaSupportiveSnapshot:
    """
    Test supportive/friendly persona application.

    Characteristics:
        - High warmth (0.95)
        - Low formality (0.3)
        - Empathetic layer ordering (mirror first)
        - Supportive intro/outro templates
    """

    def test_persona_supportive_snapshot(self):
        """
        Snapshot test for friendly persona with resonance tone.

        Expected behavior:
            - Warm, empathetic intro
            - Mirror layer first (friendly prefers empathy)
            - Supportive headers
            - Encouraging outro
        """
        engine = PersonaEngine()

        # Create emotional context
        renderer_output = create_emotional_renderer_output()
        dha_result = create_dha_result(tone="resonance", confidence=0.78)
        explain_log = create_explain_log(tier="UPPER", domain="emotional", intent="meaning")

        # Force friendly persona selection
        response = engine.apply(
            renderer_output=renderer_output,
            dha_result=dha_result,
            explain_log=explain_log,
            user_persona_override="friendly"
        )

        snapshot_output = persona_response_to_snapshot_string(response)
        snapshot_path = SNAPSHOT_DIR / "persona_supportive.snap"
        assert_snapshot(snapshot_output, snapshot_path)

    def test_persona_supportive_with_symbolic_tone_snapshot(self):
        """
        Snapshot test for friendly persona with symbolic tone.

        Expected behavior:
            - Tone override takes precedence
            - Symbolic layer first (due to symbolic tone)
            - Metaphorical headers
        """
        engine = PersonaEngine()

        renderer_output = create_emotional_renderer_output()
        # Symbolic tone overrides persona ordering preference
        dha_result = create_dha_result(tone="symbolic", confidence=0.71)
        explain_log = create_explain_log(tier="UPPER", domain="emotional", intent="why")

        response = engine.apply(
            renderer_output=renderer_output,
            dha_result=dha_result,
            explain_log=explain_log,
            user_persona_override="friendly"
        )

        snapshot_output = persona_response_to_snapshot_string(response)
        snapshot_path = SNAPSHOT_DIR / "persona_supportive_symbolic.snap"
        assert_snapshot(snapshot_output, snapshot_path)


# =============================================================================
# TEST 3: STRICT PERSONA (REGULATOR) SNAPSHOT
# =============================================================================

class TestPersonaStrictSnapshot:
    """
    Test strict/regulator persona application.

    Characteristics:
        - Very high caution (0.95)
        - High formality (0.9)
        - Risk-aware messaging
        - Professional disclaimers
    """

    def test_persona_strict_snapshot(self):
        """
        Snapshot test for regulator persona with resonance tone.

        Expected behavior:
            - Important/cautionary intro
            - Practical layer first (regulator follows default)
            - Professional, formal headers
            - Disclaimer outro
        """
        engine = PersonaEngine()

        # Create regulated context
        renderer_output = create_regulated_renderer_output()
        dha_result = create_dha_result(tone="resonance", confidence=0.88)
        explain_log = create_explain_log(tier="LOWER", domain="medical", intent="how")

        # Force regulator persona selection
        response = engine.apply(
            renderer_output=renderer_output,
            dha_result=dha_result,
            explain_log=explain_log,
            user_persona_override="regulator"
        )

        snapshot_output = persona_response_to_snapshot_string(response)
        snapshot_path = SNAPSHOT_DIR / "persona_strict.snap"
        assert_snapshot(snapshot_output, snapshot_path)

    def test_persona_strict_with_inverse_jolt_snapshot(self):
        """
        Snapshot test for regulator persona with inverse_jolt tone.

        Expected behavior:
            - Tone override takes precedence
            - Mirror layer first (due to inverse_jolt)
            - Direct truth headers
        """
        engine = PersonaEngine()

        renderer_output = create_regulated_renderer_output()
        # Inverse jolt tone overrides persona ordering
        dha_result = create_dha_result(tone="inverse_jolt", confidence=0.75)
        explain_log = create_explain_log(tier="LOWER", domain="medical", intent="why")

        response = engine.apply(
            renderer_output=renderer_output,
            dha_result=dha_result,
            explain_log=explain_log,
            user_persona_override="regulator"
        )

        snapshot_output = persona_response_to_snapshot_string(response)
        snapshot_path = SNAPSHOT_DIR / "persona_strict_jolt.snap"
        assert_snapshot(snapshot_output, snapshot_path)


# =============================================================================
# TEST 4: SAGE PERSONA SNAPSHOT
# =============================================================================

class TestPersonaSageSnapshot:
    """
    Test sage persona application for philosophical/symbolic context.

    Characteristics:
        - High metaphor level (0.9)
        - Symbolic layer preference
        - Reflective intro/outro
    """

    def test_persona_sage_snapshot(self):
        """
        Snapshot test for sage persona with resonance tone.

        Expected behavior:
            - Reflective, philosophical intro
            - Symbolic layer first (sage preference)
            - Metaphorical headers
            - Contemplative outro
        """
        engine = PersonaEngine()

        # Create philosophical context
        renderer_output = RendererOutputV3(
            symbolic_layer={
                "pattern": "seeking_meaning_in_existence",
                "kosha_state": "ANANDAMAYA",
                "depth": 0.88,
                "archetypes": ["sage", "mystic"],
                "symbolic_threads": [
                    "the question contains its answer",
                    "silence speaks louder than words"
                ]
            },
            practical_layer={
                "steps": [
                    "Observe without judgment",
                    "Allow space for insight",
                    "Trust the process of understanding"
                ],
                "confidence": 0.65,
                "domain_fit": "philosophical",
                "complexity": "profound"
            },
            mirror_truth_layer={
                "reflection": "the seeker and the sought are one",
                "bhava_direction": "transcendent",
                "hidden_patterns": [
                    "mind seeking to understand itself",
                    "duality dissolving into unity"
                ],
                "growth_edge": "embracing not-knowing"
            },
            metadata={
                "tier": "UPPER",
                "domain": "spiritual",
                "intent": "meaning",
                "confidence": {
                    "symbolic": 0.88,
                    "practical": 0.65,
                    "mirror": 0.79
                }
            }
        )

        dha_result = create_dha_result(tone="resonance", confidence=0.81)
        explain_log = create_explain_log(tier="UPPER", domain="spiritual", intent="meaning")

        response = engine.apply(
            renderer_output=renderer_output,
            dha_result=dha_result,
            explain_log=explain_log,
            user_persona_override="sage"
        )

        snapshot_output = persona_response_to_snapshot_string(response)
        snapshot_path = SNAPSHOT_DIR / "persona_sage.snap"
        assert_snapshot(snapshot_output, snapshot_path)


# =============================================================================
# TEST 5: COACH PERSONA SNAPSHOT
# =============================================================================

class TestPersonaCoachSnapshot:
    """
    Test coach persona application for action-oriented context.

    Characteristics:
        - Very high directness (0.95)
        - Action-oriented layer ordering (mirror first)
        - Motivational framing
    """

    def test_persona_coach_snapshot(self):
        """
        Snapshot test for coach persona with resonance tone.

        Expected behavior:
            - Action-oriented intro
            - Mirror layer first (coach prefers action focus)
            - Direct, motivational headers
            - Call-to-action outro
        """
        engine = PersonaEngine()

        renderer_output = RendererOutputV3(
            symbolic_layer={
                "pattern": "overcoming_resistance_to_action",
                "kosha_state": "PRANAMAYA",
                "depth": 0.58,
                "archetypes": ["warrior", "achiever"],
                "symbolic_threads": [
                    "action dissolves doubt",
                    "momentum builds momentum"
                ]
            },
            practical_layer={
                "steps": [
                    "Define your target outcome",
                    "Break it into first action",
                    "Execute immediately",
                    "Iterate and improve"
                ],
                "confidence": 0.91,
                "domain_fit": "execution",
                "complexity": "straightforward"
            },
            mirror_truth_layer={
                "reflection": "you already know what to do - start now",
                "bhava_direction": "outward",
                "hidden_patterns": [
                    "procrastination as fear avoidance",
                    "perfectionism blocking progress"
                ],
                "growth_edge": "starting before feeling ready"
            },
            metadata={
                "tier": "LOWER",
                "domain": "execution",
                "intent": "action",
                "confidence": {
                    "symbolic": 0.58,
                    "practical": 0.91,
                    "mirror": 0.74
                }
            }
        )

        dha_result = create_dha_result(tone="resonance", confidence=0.86)
        explain_log = create_explain_log(tier="LOWER", domain="execution", intent="action")

        response = engine.apply(
            renderer_output=renderer_output,
            dha_result=dha_result,
            explain_log=explain_log,
            user_persona_override="coach"
        )

        snapshot_output = persona_response_to_snapshot_string(response)
        snapshot_path = SNAPSHOT_DIR / "persona_coach.snap"
        assert_snapshot(snapshot_output, snapshot_path)


# =============================================================================
# TEST 6: LAYER ORDERING VERIFICATION
# =============================================================================

class TestPersonaLayerOrdering:
    """
    Test that layer ordering follows documented rules.

    Priority:
        1. Tone overrides (inverse_jolt -> mirror first, symbolic -> symbolic first)
        2. Persona preferences
        3. Default ordering
    """

    def test_tone_override_takes_precedence(self):
        """
        Verify that tone overrides persona preference.

        inverse_jolt tone should put mirror first regardless of persona.
        """
        engine = PersonaEngine()

        # Analyst normally prefers practical first
        renderer_output = create_standard_renderer_output()
        dha_result = create_dha_result(tone="inverse_jolt", confidence=0.80)
        explain_log = create_explain_log()

        response = engine.apply(
            renderer_output=renderer_output,
            dha_result=dha_result,
            explain_log=explain_log,
            user_persona_override="analyst"
        )

        # Check that "Direct truth:" appears before "Practical explanation:"
        text = response.text
        direct_truth_pos = text.find("Direct truth:")
        practical_pos = text.find("Practical explanation:")

        assert direct_truth_pos < practical_pos, (
            "inverse_jolt tone should put mirror (Direct truth) before practical"
        )

    def test_symbolic_tone_orders_symbolic_first(self):
        """
        Verify that symbolic tone puts symbolic layer first.
        """
        engine = PersonaEngine()

        renderer_output = create_standard_renderer_output()
        dha_result = create_dha_result(tone="symbolic", confidence=0.75)
        explain_log = create_explain_log()

        response = engine.apply(
            renderer_output=renderer_output,
            dha_result=dha_result,
            explain_log=explain_log,
            user_persona_override="neutral"
        )

        text = response.text
        symbolic_pos = text.find("Deeper symbolic insight:")
        practical_pos = text.find("Practical explanation:")

        assert symbolic_pos < practical_pos, (
            "symbolic tone should put symbolic layer before practical"
        )


# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
