"""
Semantic Bhava Layer with Astrological Correspondences
========================================================

The Bhava system draws from Vedic astrology where "Bhava" means
"house" or "state of being". Each Bhava represents relational
dynamics between ontological layers, mapped to planetary energies.

Patent-Exact Ontological-Planetary Correspondences:
(Lowest → Highest: Karma → Brahman)

Concrete Layers (O1-O5):
- O1_EXECUTION    → Mars (Mangala) - Karma, actions, consequences
- O2_IDENTITY     → Moon (Chandra) - Identification, labels, roles
- O3_FORM         → Venus (Shukra) - Body, structure, embodiment
- O4_COGNITION    → Mercury (Budha) - Mind, attention, perception
- O5_AGENCY       → Sun (Surya) - Ego, control, intent, authorship

Abstract Layers (O6-O10):
- O6_REASONING    → Saturn (Shani) - Intellect, logic, inference
- O7_PURPOSE      → Jupiter (Guru) - Soul, meaning, motivation
- O8_OBSERVATION  → Ketu - Witness, meta-awareness, reflection
- O9_CORE         → Rahu - Atman, unified self-reference
- O10_UNIVERSAL   → Neptune/Brahman - Coherence, absoluteness, unity

Directional Semantics:
- Upward recursion (Execution → Universal): Cause tracing, insight surfacing
- Downward recursion (Universal → Execution): Consequence projection, grounding

Bhava Pairs (9 pairs × 10 sub-layers = 90D):
- Adjacent layers: Conjunction (synthesis)
- 2-apart: Sextile (60°) - Harmonious flow
- 3-apart: Square (90°) - Creative tension
- 4-apart: Trine (120°) - Natural ease
- 5-apart: Opposition (180°) - Polarity/balance
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False


# =============================================================================
# PLANETARY CORRESPONDENCES
# =============================================================================

# Patent-Exact Planetary Correspondences
# Karma → Identification → Body → Mind → Ego → Intellect → Soul → Witness → Atman → Brahman
PLANETARY_MAP = {
    "O1_EXECUTION": {
        "planet": "Mars",
        "sanskrit": "Mangala",
        "vedic": "Karma",
        "energy": "action",
        "element": "fire",
        "quality": "cardinal",
        "keywords": ["execution", "behavior", "consequence", "output"],
    },
    "O2_IDENTITY": {
        "planet": "Moon",
        "sanskrit": "Chandra",
        "vedic": "Identification",
        "energy": "classification",
        "element": "water",
        "quality": "cardinal",
        "keywords": ["labels", "roles", "references", "self-object"],
    },
    "O3_FORM": {
        "planet": "Venus",
        "sanskrit": "Shukra",
        "vedic": "Body",
        "energy": "structure",
        "element": "earth/water",
        "quality": "fixed",
        "keywords": ["form", "embodiment", "representation", "physical"],
    },
    "O4_COGNITION": {
        "planet": "Mercury",
        "sanskrit": "Budha",
        "vedic": "Mind",
        "energy": "perception",
        "element": "air",
        "quality": "mutable",
        "keywords": ["attention", "emotion", "perception", "mental"],
    },
    "O5_AGENCY": {
        "planet": "Sun",
        "sanskrit": "Surya",
        "vedic": "Ego",
        "energy": "will",
        "element": "fire",
        "quality": "fixed",
        "keywords": ["control", "intent", "authorship", "decision"],
    },
    "O6_REASONING": {
        "planet": "Saturn",
        "sanskrit": "Shani",
        "vedic": "Intellect",
        "energy": "logic",
        "element": "earth",
        "quality": "cardinal",
        "keywords": ["logic", "inference", "analysis", "structure"],
    },
    "O7_PURPOSE": {
        "planet": "Jupiter",
        "sanskrit": "Guru",
        "vedic": "Soul",
        "energy": "meaning",
        "element": "fire/ether",
        "quality": "mutable",
        "keywords": ["meaning", "motivation", "direction", "why"],
    },
    "O8_OBSERVATION": {
        "planet": "Ketu",
        "sanskrit": "Ketu",
        "vedic": "Witness",
        "energy": "awareness",
        "element": "ether",
        "quality": "spiritual",
        "keywords": ["meta-awareness", "reflection", "monitoring", "witness"],
    },
    "O9_CORE": {
        "planet": "Rahu",
        "sanskrit": "Rahu",
        "vedic": "Atman",
        "energy": "self",
        "element": "air/ether",
        "quality": "stable",
        "keywords": ["unified-self", "stable-identity", "core", "essence"],
    },
    "O10_UNIVERSAL": {
        "planet": "Neptune",
        "sanskrit": "Brahman",
        "vedic": "Brahman",
        "energy": "unity",
        "element": "ether",
        "quality": "transcendent",
        "keywords": ["coherence", "absoluteness", "unity", "universal"],
    },
}


# =============================================================================
# ASPECT DEFINITIONS
# =============================================================================

@dataclass
class AspectType:
    """Astrological aspect between two layers."""
    name: str
    angle: int  # degrees
    nature: str  # harmonious, challenging, neutral
    orb: int  # allowed deviation
    strength: float  # 0-1


ASPECTS = {
    "conjunction": AspectType("Conjunction", 0, "synthesis", 8, 1.0),
    "sextile": AspectType("Sextile", 60, "harmonious", 6, 0.6),
    "square": AspectType("Square", 90, "challenging", 8, 0.8),
    "trine": AspectType("Trine", 120, "harmonious", 8, 0.9),
    "opposition": AspectType("Opposition", 180, "polarizing", 8, 1.0),
}


def get_aspect_between(layer_i: int, layer_j: int) -> AspectType:
    """
    Determine the astrological aspect between two ontological layers.

    Uses circular distance on the 10-layer wheel (36° per layer).
    """
    # Distance on a 10-point circle
    diff = abs(layer_i - layer_j)
    circular_diff = min(diff, 10 - diff)

    # Map to aspect (each layer = 36°)
    angle = circular_diff * 36

    if angle == 0:
        return ASPECTS["conjunction"]
    elif angle <= 72:  # 1-2 steps
        return ASPECTS["sextile"]
    elif angle <= 108:  # 3 steps
        return ASPECTS["square"]
    elif angle <= 144:  # 4 steps
        return ASPECTS["trine"]
    else:  # 5 steps (180°)
        return ASPECTS["opposition"]


# =============================================================================
# BHAVA PAIR DEFINITIONS
# =============================================================================

@dataclass
class BhavaPair:
    """A Bhava pair representing the relationship between two layers."""
    index: int
    layer_a: str
    layer_b: str
    aspect: AspectType
    name: str
    description: str
    sub_layers: List[str]


def define_bhava_pairs() -> List[BhavaPair]:
    """
    Define the 9 primary Bhava pairs with semantic meaning.

    Following the adjacent-layer model (O1↔O2, O2↔O3, etc.)
    """
    from symbolu.ontological.types import LAYER_NAMES

    pairs = []

    # Patent-Exact Bhava Pair Definitions
    # Upward: Execution → Universal (cause tracing, insight surfacing)
    # Downward: Universal → Execution (consequence projection, grounding)
    pair_definitions = [
        {
            # B1: O1_EXECUTION ↔ O2_IDENTITY (Karma-Identification)
            "name": "Execution-Identity",
            "description": "How actions create labels and roles",
            "sub_layers": [
                "consequence",     # Action's result
                "attribution",     # Assigning ownership
                "labeling",        # Naming the action
                "role",            # Action-derived identity
                "reference",       # Pointing to actor
                "distinction",     # Self-object separation
                "ownership",       # Claiming the action
                "memory",          # Recording who did what
                "pattern",         # Recurring action-identity
                "archive",         # Stored karma-identity links
            ]
        },
        {
            # B2: O2_IDENTITY ↔ O3_FORM (Identification-Body)
            "name": "Identity-Form",
            "description": "How labels crystallize into structure",
            "sub_layers": [
                "embodiment",      # Identity takes form
                "representation",  # Symbolic form of identity
                "structure",       # Organized identity
                "pattern",         # Formal repetition
                "shape",           # Contour of identity
                "composition",     # Parts of form
                "architecture",    # Structural identity
                "manifestation",   # Identity made visible
                "boundary",        # Form's limits
                "crystallization", # Fixed form
            ]
        },
        {
            # B3: O3_FORM ↔ O4_COGNITION (Body-Mind)
            "name": "Form-Cognition",
            "description": "How structure enables perception",
            "sub_layers": [
                "perception",      # Form perceived
                "attention",       # Focus on form
                "sensation",       # Bodily awareness
                "emotion",         # Feeling about form
                "model",           # Mental representation
                "pattern",         # Cognitive structure
                "recognition",     # Knowing the form
                "memory",          # Form remembered
                "imagination",     # Form visualized
                "abstraction",     # Form conceptualized
            ]
        },
        {
            # B4: O4_COGNITION ↔ O5_AGENCY (Mind-Ego)
            "name": "Cognition-Agency",
            "description": "How perception enables control",
            "sub_layers": [
                "intention",       # Mental aim
                "decision",        # Choosing to act
                "will",            # Force of mind
                "authorship",      # Mental ownership
                "control",         # Directing cognition
                "authority",       # Mental command
                "focus",           # Concentrated will
                "planning",        # Strategic cognition
                "ownership",       # Claiming thoughts
                "direction",       # Cognitive steering
            ]
        },
        {
            # B5: O5_AGENCY ↔ O6_REASONING (Ego-Intellect)
            "name": "Agency-Reasoning",
            "description": "How will applies logic",
            "sub_layers": [
                "analysis",        # Breaking down intent
                "inference",       # Reasoning from will
                "validation",      # Checking decisions
                "structure",       # Organized agency
                "logic",           # Reasoned control
                "discipline",      # Structured will
                "rigor",           # Strict reasoning
                "consistency",     # Non-contradictory will
                "judgment",        # Reasoned decision
                "accountability",  # Logical responsibility
            ]
        },
        {
            # B6: O6_REASONING ↔ O7_PURPOSE (Intellect-Soul)
            "name": "Reasoning-Purpose",
            "description": "How logic serves meaning",
            "sub_layers": [
                "meaning",         # Why this logic
                "motivation",      # Reason's drive
                "direction",       # Purpose of reasoning
                "alignment",       # Logic matches purpose
                "wisdom",          # Deep reasoning
                "philosophy",      # Underlying principles
                "ethics",          # Moral reasoning
                "teleology",       # Purpose-oriented logic
                "fulfillment",     # Reasoning's goal
                "transcendence",   # Beyond mere logic
            ]
        },
        {
            # B7: O7_PURPOSE ↔ O8_OBSERVATION (Soul-Witness)
            "name": "Purpose-Observation",
            "description": "How meaning enables awareness",
            "sub_layers": [
                "reflection",      # Purpose observed
                "contemplation",   # Deep awareness of why
                "insight",         # Seeing purpose
                "perspective",     # Broader view of meaning
                "witness",         # Observing purpose
                "detachment",      # Distance from motive
                "clarity",         # Clear seeing of why
                "monitoring",      # Tracking purpose
                "meta-awareness",  # Aware of being aware
                "presence",        # Fully present to meaning
            ]
        },
        {
            # B8: O8_OBSERVATION ↔ O9_CORE (Witness-Atman)
            "name": "Observation-Core",
            "description": "How awareness reveals stable self",
            "sub_layers": [
                "recognition",     # Seeing true self
                "identity",        # Stable self-reference
                "integration",     # Parts become self
                "unity",           # One self across contexts
                "stability",       # Unchanging core
                "essence",         # What remains
                "continuity",      # Self across time
                "coherence",       # Self-consistency
                "grounding",       # Rooted in self
                "presence",        # Being the self
            ]
        },
        {
            # B9: O9_CORE ↔ O10_UNIVERSAL (Atman-Brahman)
            "name": "Core-Universal",
            "description": "How self connects to absolute",
            "sub_layers": [
                "unity",           # Self meets universal
                "dissolution",     # Ego boundaries fade
                "coherence",       # Total integration
                "absoluteness",    # Beyond particulars
                "transcendence",   # Beyond self
                "completion",      # Nothing more needed
                "peace",           # Final rest
                "liberation",      # Freedom from limits
                "oneness",         # No separation
                "brahman",         # Ultimate unity
            ]
        },
    ]

    for i, defn in enumerate(pair_definitions):
        layer_a = LAYER_NAMES[i]
        layer_b = LAYER_NAMES[i + 1]
        aspect = get_aspect_between(i, i + 1)

        pairs.append(BhavaPair(
            index=i,
            layer_a=layer_a,
            layer_b=layer_b,
            aspect=aspect,
            name=defn["name"],
            description=defn["description"],
            sub_layers=defn["sub_layers"],
        ))

    return pairs


BHAVA_PAIRS = define_bhava_pairs()


# =============================================================================
# SEMANTIC BHAVA LAYER (PyTorch)
# =============================================================================

if PYTORCH_AVAILABLE:

    class SemanticBhavaLayer(nn.Module):
        """
        Semantically-grounded Bhava layer with astrological structure.

        Architecture:
            10D Ontological → 9 Pair Modules → 90D Semantic Bhava

        Each pair module:
            - Takes the two relevant ontological dimensions
            - Computes 10 sub-layer activations
            - Applies aspect-based modulation
        """

        def __init__(
            self,
            ontological_dim: int = 10,
            sub_layers_per_pair: int = 10,
            hidden_dim: int = 32,
        ):
            super().__init__()

            self.ontological_dim = ontological_dim
            self.num_pairs = ontological_dim - 1  # 9 pairs
            self.sub_layers_per_pair = sub_layers_per_pair
            self.bhava_dim = self.num_pairs * sub_layers_per_pair  # 90

            # One module per Bhava pair
            self.pair_modules = nn.ModuleList([
                nn.Sequential(
                    nn.Linear(2, hidden_dim),  # Two ontological dims
                    nn.GELU(),
                    nn.Linear(hidden_dim, sub_layers_per_pair),
                    nn.Tanh(),
                )
                for _ in range(self.num_pairs)
            ])

            # Aspect modulation weights (learnable, initialized by aspect strength)
            aspect_strengths = torch.tensor([
                get_aspect_between(i, i + 1).strength
                for i in range(self.num_pairs)
            ])
            self.aspect_weights = nn.Parameter(aspect_strengths)

            # Cross-pair attention for non-adjacent interactions
            self.cross_attention = nn.MultiheadAttention(
                embed_dim=sub_layers_per_pair,
                num_heads=2,
                batch_first=True,
            )

            # Store pair definitions for interpretability
            self.pair_names = [p.name for p in BHAVA_PAIRS]
            self.sub_layer_names = [p.sub_layers for p in BHAVA_PAIRS]

        def forward(self, onto: torch.Tensor) -> Dict[str, torch.Tensor]:
            """
            Compute semantic Bhava from ontological vector.

            Args:
                onto: Ontological probabilities (batch, 10)

            Returns:
                Dict with:
                - bhava: Full 90D vector
                - pairs: List of 9 pair outputs (each batch, 10)
                - attended: Cross-attended Bhava
            """
            batch_size = onto.shape[0]
            device = onto.device

            # Compute each pair's sub-layers
            pair_outputs = []
            for i, module in enumerate(self.pair_modules):
                # Extract the two relevant ontological dimensions
                pair_input = onto[:, i:i+2]  # (batch, 2)

                # Compute sub-layer activations
                sub_layers = module(pair_input)  # (batch, 10)

                # Apply aspect modulation
                sub_layers = sub_layers * self.aspect_weights[i]

                pair_outputs.append(sub_layers)

            # Stack pairs for attention
            pairs_stacked = torch.stack(pair_outputs, dim=1)  # (batch, 9, 10)

            # Cross-pair attention (how pairs influence each other)
            attended, _ = self.cross_attention(
                pairs_stacked, pairs_stacked, pairs_stacked
            )

            # Combine: original + attended
            combined = pairs_stacked + 0.3 * attended

            # Flatten to 90D
            bhava = combined.view(batch_size, -1)  # (batch, 90)

            return {
                "bhava": bhava,
                "pairs": pair_outputs,
                "attended": attended,
                "pair_activations": pairs_stacked,
            }

        def interpret(
            self,
            bhava_output: Dict[str, torch.Tensor],
            top_k: int = 3,
        ) -> List[Dict[str, Any]]:
            """
            Interpret the Bhava activations semantically.

            Returns top activated sub-layers with their meanings.
            """
            interpretations = []

            for batch_idx in range(bhava_output["bhava"].shape[0]):
                sample_interp = []

                for pair_idx, pair_act in enumerate(bhava_output["pairs"]):
                    activations = pair_act[batch_idx].cpu().numpy()

                    # Get top activated sub-layers
                    top_indices = np.argsort(np.abs(activations))[-top_k:][::-1]

                    pair_info = {
                        "pair": self.pair_names[pair_idx],
                        "top_sub_layers": [
                            {
                                "name": self.sub_layer_names[pair_idx][idx],
                                "activation": float(activations[idx]),
                            }
                            for idx in top_indices
                        ]
                    }
                    sample_interp.append(pair_info)

                interpretations.append(sample_interp)

            return interpretations

        def get_pair_by_name(self, name: str) -> Optional[BhavaPair]:
            """Get a Bhava pair definition by name."""
            for pair in BHAVA_PAIRS:
                if pair.name == name:
                    return pair
            return None


    class AstrologicalOntologicalEngine(nn.Module):
        """
        Ontological Engine with semantically-grounded Bhava.

        Combines:
        - Evidential classification (10D + uncertainty)
        - Semantic Bhava layer (90D with interpretable sub-layers)
        - Planetary correspondence analysis
        - Astrological aspect modulation
        """

        def __init__(
            self,
            encoder_dim: int = 384,
            hidden_dims: Tuple[int, ...] = (256, 128),
            ontological_dim: int = 10,
            dropout: float = 0.1,
        ):
            super().__init__()

            self.encoder_dim = encoder_dim
            self.ontological_dim = ontological_dim

            # MLP backbone
            layers = []
            prev_dim = encoder_dim
            for hidden_dim in hidden_dims:
                layers.extend([
                    nn.Linear(prev_dim, hidden_dim),
                    nn.LayerNorm(hidden_dim),
                    nn.GELU(),
                    nn.Dropout(dropout),
                ])
                prev_dim = hidden_dim
            self.backbone = nn.Sequential(*layers)
            self.hidden_dim = prev_dim

            # Evidential head
            self.evidential = nn.Linear(prev_dim, ontological_dim)

            # Semantic Bhava layer
            self.bhava = SemanticBhavaLayer(
                ontological_dim=ontological_dim,
                sub_layers_per_pair=10,
            )

            # Encoder (lazy loaded)
            self._encoder = None

        @property
        def encoder(self):
            if self._encoder is None:
                from symbolu.ontological.encoder import get_encoder
                self._encoder = get_encoder("minilm")
            return self._encoder

        def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
            """Forward pass with semantic Bhava."""
            hidden = self.backbone(x)

            # Evidential classification
            evidence = F.softplus(self.evidential(hidden))
            alpha = evidence + 1.0
            S = torch.sum(alpha, dim=1, keepdim=True)
            prob = alpha / S
            uncertainty = self.ontological_dim / S.squeeze(-1)

            # Semantic Bhava
            bhava_output = self.bhava(prob)

            return {
                "ontological": prob,
                "evidence": evidence,
                "alpha": alpha,
                "uncertainty": uncertainty,
                "bhava": bhava_output["bhava"],
                "bhava_pairs": bhava_output["pairs"],
                "bhava_attended": bhava_output["attended"],
                "hidden": hidden,
            }

        def analyze(self, text: str) -> Dict[str, Any]:
            """
            Analyze text with full astrological interpretation.
            """
            self.eval()

            from symbolu.ontological.types import LAYER_NAMES

            embedding = self.encoder.encode(text)
            x = torch.tensor(embedding, dtype=torch.float32).unsqueeze(0)

            device = next(self.parameters()).device
            x = x.to(device)

            with torch.no_grad():
                output = self.forward(x)

            probs = output["ontological"].squeeze(0).cpu().numpy()
            uncertainty = output["uncertainty"].item()

            # Dominant layer
            dominant_idx = int(np.argmax(probs))
            dominant_layer = LAYER_NAMES[dominant_idx]

            # Planetary correspondence
            planetary = PLANETARY_MAP[dominant_layer]

            # Bhava interpretation
            bhava_interp = self.bhava.interpret({
                "bhava": output["bhava"],
                "pairs": output["bhava_pairs"],
            })

            # Find strongest Bhava pair
            pair_strengths = [
                p.abs().mean().item()
                for p in output["bhava_pairs"]
            ]
            strongest_pair_idx = int(np.argmax(pair_strengths))
            strongest_pair = BHAVA_PAIRS[strongest_pair_idx]

            return {
                # Classification
                "dominant_layer": dominant_layer,
                "confidence": float(probs[dominant_idx]),
                "uncertainty": uncertainty,

                # Planetary (Patent-Exact)
                "planet": planetary["planet"],
                "sanskrit": planetary["sanskrit"],
                "vedic": planetary["vedic"],  # Karma, Identification, Body, etc.
                "energy": planetary["energy"],
                "element": planetary["element"],
                "keywords": planetary["keywords"],

                # Bhava
                "dominant_bhava": strongest_pair.name,
                "bhava_description": strongest_pair.description,
                "active_sub_layers": bhava_interp[0][strongest_pair_idx]["top_sub_layers"],

                # Vectors
                "ontological_vector": probs.tolist(),
                "bhava_vector": output["bhava"].squeeze(0).cpu().numpy().tolist(),
            }

        def summary(self) -> str:
            """Model summary."""
            total_params = sum(p.numel() for p in self.parameters())

            return f"""
============================================================
ASTROLOGICAL ONTOLOGICAL ENGINE (Patent-Exact)
============================================================

Ontological Layers (Karma → Brahman):
  O1_EXECUTION   → Mars (Mangala)    - Karma, actions
  O2_IDENTITY    → Moon (Chandra)    - Identification, labels
  O3_FORM        → Venus (Shukra)    - Body, structure
  O4_COGNITION   → Mercury (Budha)   - Mind, perception
  O5_AGENCY      → Sun (Surya)       - Ego, control
  O6_REASONING   → Saturn (Shani)    - Intellect, logic
  O7_PURPOSE     → Jupiter (Guru)    - Soul, meaning
  O8_OBSERVATION → Ketu              - Witness, awareness
  O9_CORE        → Rahu              - Atman, unified self
  O10_UNIVERSAL  → Neptune (Brahman) - Coherence, unity

Bhava Pairs (9 × 10 sub-layers = 90D):
  B1: Execution-Identity (Karma↔Identification)
  B2: Identity-Form (Identification↔Body)
  B3: Form-Cognition (Body↔Mind)
  B4: Cognition-Agency (Mind↔Ego)
  B5: Agency-Reasoning (Ego↔Intellect)
  B6: Reasoning-Purpose (Intellect↔Soul)
  B7: Purpose-Observation (Soul↔Witness)
  B8: Observation-Core (Witness↔Atman)
  B9: Core-Universal (Atman↔Brahman)

Directional Flow:
  Upward:   Execution → Universal (cause tracing)
  Downward: Universal → Execution (grounding)

Total Parameters: {total_params:,}
============================================================
"""
