"""
Semantic Bhava Layer with Astrological Correspondences
========================================================

The Bhava system draws from Vedic astrology where "Bhava" means
"house" or "state of being". Each Bhava represents relational
dynamics between ontological layers, mapped to planetary energies.

Ontological-Planetary Correspondences:
- O1_THINKING     → Mercury (Budha) - Intellect, contemplation
- O2_FORMING      → Venus (Shukra) - Creation, beauty, art
- O3_ACTING       → Mars (Mangala) - Action, drive, execution
- O4_TAGGING      → Moon (Chandra) - Emotions, feelings, reception
- O5_DIRECTING    → Sun (Surya) - Leadership, authority, will
- O6_REASONING    → Saturn (Shani) - Logic, structure, discipline
- O7_PURPOSING    → Jupiter (Guru) - Purpose, expansion, wisdom
- O8_META_OBSERVING → Ketu - Higher awareness, detachment, insight
- O9_UNIFYING     → Rahu - Integration, desire, synthesis
- O10_ABSOLVING   → Neptune/Moksha - Dissolution, transcendence, release

Bhava Pairs as Astrological Aspects:
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

PLANETARY_MAP = {
    "O1_THINKING": {
        "planet": "Mercury",
        "sanskrit": "Budha",
        "energy": "intellect",
        "element": "air",
        "quality": "mutable",
        "keywords": ["thought", "analysis", "communication", "curiosity"],
    },
    "O2_FORMING": {
        "planet": "Venus",
        "sanskrit": "Shukra",
        "energy": "creation",
        "element": "earth/water",
        "quality": "fixed",
        "keywords": ["beauty", "art", "harmony", "attraction"],
    },
    "O3_ACTING": {
        "planet": "Mars",
        "sanskrit": "Mangala",
        "energy": "action",
        "element": "fire",
        "quality": "cardinal",
        "keywords": ["drive", "execution", "courage", "initiative"],
    },
    "O4_TAGGING": {
        "planet": "Moon",
        "sanskrit": "Chandra",
        "energy": "emotion",
        "element": "water",
        "quality": "cardinal",
        "keywords": ["feeling", "reception", "intuition", "memory"],
    },
    "O5_DIRECTING": {
        "planet": "Sun",
        "sanskrit": "Surya",
        "energy": "will",
        "element": "fire",
        "quality": "fixed",
        "keywords": ["leadership", "authority", "identity", "vitality"],
    },
    "O6_REASONING": {
        "planet": "Saturn",
        "sanskrit": "Shani",
        "energy": "structure",
        "element": "earth",
        "quality": "cardinal",
        "keywords": ["logic", "discipline", "limits", "mastery"],
    },
    "O7_PURPOSING": {
        "planet": "Jupiter",
        "sanskrit": "Guru",
        "energy": "expansion",
        "element": "fire/ether",
        "quality": "mutable",
        "keywords": ["purpose", "wisdom", "growth", "meaning"],
    },
    "O8_META_OBSERVING": {
        "planet": "Ketu",
        "sanskrit": "Ketu",
        "energy": "detachment",
        "element": "ether",
        "quality": "spiritual",
        "keywords": ["awareness", "insight", "liberation", "past"],
    },
    "O9_UNIFYING": {
        "planet": "Rahu",
        "sanskrit": "Rahu",
        "energy": "desire",
        "element": "air/ether",
        "quality": "obsessive",
        "keywords": ["integration", "ambition", "future", "synthesis"],
    },
    "O10_ABSOLVING": {
        "planet": "Neptune",
        "sanskrit": "Moksha",
        "energy": "dissolution",
        "element": "water/ether",
        "quality": "transcendent",
        "keywords": ["release", "transcendence", "completion", "surrender"],
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

    pair_definitions = [
        {
            "name": "Ideation-Manifestation",
            "description": "How thought crystallizes into form",
            "sub_layers": [
                "conception",      # Initial spark of idea
                "imagination",     # Mental visualization
                "design",          # Structural planning
                "aesthetics",      # Beauty consideration
                "materialization", # Bringing to physical
                "refinement",      # Iterative improvement
                "expression",      # Outward manifestation
                "reception",       # How it's received
                "integration",     # Becoming part of reality
                "completion",      # Finished form
            ]
        },
        {
            "name": "Creation-Action",
            "description": "How form drives movement and execution",
            "sub_layers": [
                "motivation",      # Drive to act
                "planning",        # Strategic preparation
                "initiation",      # First step
                "momentum",        # Building energy
                "adaptation",      # Adjusting course
                "persistence",     # Continuing despite obstacles
                "execution",       # Performing the action
                "impact",          # Effect of action
                "feedback",        # Response received
                "completion",      # Action finished
            ]
        },
        {
            "name": "Action-Emotion",
            "description": "How actions trigger emotional responses",
            "sub_layers": [
                "anticipation",    # Pre-action feeling
                "excitement",      # Energy of doing
                "fear",            # Risk awareness
                "satisfaction",    # Achievement feeling
                "frustration",     # Obstacle response
                "pride",           # Success emotion
                "regret",          # Missed opportunity
                "relief",          # Completion feeling
                "gratitude",       # Appreciation
                "peace",           # Post-action calm
            ]
        },
        {
            "name": "Emotion-Authority",
            "description": "How feelings inform leadership and will",
            "sub_layers": [
                "intuition",       # Gut-level knowing
                "confidence",      # Self-belief
                "empathy",         # Understanding others
                "passion",         # Driving force
                "compassion",      # Caring leadership
                "courage",         # Emotional bravery
                "authenticity",    # True expression
                "presence",        # Being fully here
                "influence",       # Affecting others
                "sovereignty",     # Self-mastery
            ]
        },
        {
            "name": "Authority-Structure",
            "description": "How leadership uses logic and discipline",
            "sub_layers": [
                "vision",          # Long-term seeing
                "strategy",        # Planned approach
                "boundaries",      # Healthy limits
                "consistency",     # Reliable patterns
                "accountability",  # Taking responsibility
                "systems",         # Organized processes
                "measurement",     # Tracking progress
                "optimization",    # Improving efficiency
                "sustainability",  # Long-term viability
                "mastery",         # Skill development
            ]
        },
        {
            "name": "Structure-Purpose",
            "description": "How logic serves meaning and growth",
            "sub_layers": [
                "alignment",       # Structure matches purpose
                "efficiency",      # Minimal waste
                "scalability",     # Room to grow
                "adaptability",    # Flexible frameworks
                "integrity",       # Structural soundness
                "wisdom",          # Deep understanding
                "teaching",        # Sharing knowledge
                "philosophy",      # Underlying principles
                "ethics",          # Moral framework
                "legacy",          # Lasting impact
            ]
        },
        {
            "name": "Purpose-Awareness",
            "description": "How meaning enables higher perception",
            "sub_layers": [
                "reflection",      # Looking back
                "contemplation",   # Deep thinking
                "meditation",      # Still awareness
                "insight",         # Sudden understanding
                "revelation",      # Deep truth revealed
                "perspective",     # Broader view
                "witness",         # Observer state
                "presence",        # Being fully aware
                "clarity",         # Clear seeing
                "enlightenment",   # Full awareness
            ]
        },
        {
            "name": "Awareness-Unity",
            "description": "How observation leads to integration",
            "sub_layers": [
                "recognition",     # Seeing patterns
                "connection",      # Finding links
                "synthesis",       # Combining elements
                "harmony",         # Balanced whole
                "coherence",       # Logical unity
                "resonance",       # Vibrating together
                "oneness",         # Experiencing unity
                "wholeness",       # Complete integration
                "emergence",       # New properties arising
                "transcendence",   # Beyond parts
            ]
        },
        {
            "name": "Unity-Release",
            "description": "How integration enables transcendence",
            "sub_layers": [
                "acceptance",      # Allowing what is
                "surrender",       # Letting go of control
                "forgiveness",     # Releasing resentment
                "gratitude",       # Appreciating all
                "completion",      # Finishing cycles
                "dissolution",     # Boundaries fade
                "liberation",      # Freedom from limits
                "peace",           # Deep calm
                "bliss",           # Joy of being
                "moksha",          # Ultimate release
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

                # Planetary
                "planet": planetary["planet"],
                "sanskrit": planetary["sanskrit"],
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
ASTROLOGICAL ONTOLOGICAL ENGINE
============================================================

Ontological Layers (Planetary Correspondences):
  O1_THINKING     → Mercury (Budha) - Intellect
  O2_FORMING      → Venus (Shukra) - Creation
  O3_ACTING       → Mars (Mangala) - Action
  O4_TAGGING      → Moon (Chandra) - Emotion
  O5_DIRECTING    → Sun (Surya) - Leadership
  O6_REASONING    → Saturn (Shani) - Structure
  O7_PURPOSING    → Jupiter (Guru) - Purpose
  O8_META_OBSERVING → Ketu - Awareness
  O9_UNIFYING     → Rahu - Integration
  O10_ABSOLVING   → Neptune/Moksha - Transcendence

Bhava Pairs (9 × 10 sub-layers = 90D):
  B1: Ideation-Manifestation (O1↔O2)
  B2: Creation-Action (O2↔O3)
  B3: Action-Emotion (O3↔O4)
  B4: Emotion-Authority (O4↔O5)
  B5: Authority-Structure (O5↔O6)
  B6: Structure-Purpose (O6↔O7)
  B7: Purpose-Awareness (O7↔O8)
  B8: Awareness-Unity (O8↔O9)
  B9: Unity-Release (O9↔O10)

Total Parameters: {total_params:,}
============================================================
"""
