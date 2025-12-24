"""
Semantic Bhava Layer with Astrological Correspondences
========================================================

The Bhava system draws from Vedic astrology where "Bhava" means
"house" or "state of being". Each Bhava represents relational
dynamics between ontological layers, mapped to planetary energies.

12-Dimensional Ontological-Planetary Correspondences:
(Lowest → Highest: Potential → Absolving)

O1_POTENTIAL    → Pluto (Yama) - Dormant, latent capacity
O2_IDENTITY     → Moon (Chandra) - Tagging, labels, roles
O3_EXECUTION    → Mars (Mangala) - Action, karma, consequences
O4_STRUCTURE    → Venus (Shukra) - Forming, embodiment, patterns
O5_COGNITION    → Mercury (Budha) - Perception, attention, emotion
O6_AGENCY       → Sun (Surya) - Direction, control, authorship
O7_REASONING    → Saturn (Shani) - Discrimination, logic, inference
O8_PURPOSE      → Jupiter (Guru) - Meaning, motivation, why
O9_WITNESSES    → Ketu - Meta-observation, awareness, reflection
O10_UNIFYING    → Rahu - Coherence, synthesis, harmony
O11_INTEGRATION → Uranus (Varuna) - Resolution, consolidation
O12_ABSOLVING   → Neptune (Brahman) - Termination, dissolution, release

Bhava Pairs (11 pairs × 12 sub-layers = 132D):
Each Bhava pair has 12 sub-layers matching the ontological layer names.
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
# PLANETARY CORRESPONDENCES (12D)
# =============================================================================

PLANETARY_MAP = {
    "O1_POTENTIAL": {
        "planet": "Pluto",
        "sanskrit": "Yama",
        "vedic": "Dormant",
        "energy": "latent",
        "element": "void",
        "quality": "hidden",
        "keywords": ["potential", "dormant", "latent", "unrealized"],
    },
    "O2_IDENTITY": {
        "planet": "Moon",
        "sanskrit": "Chandra",
        "vedic": "Tagging",
        "energy": "classification",
        "element": "water",
        "quality": "cardinal",
        "keywords": ["identity", "labels", "roles", "references"],
    },
    "O3_EXECUTION": {
        "planet": "Mars",
        "sanskrit": "Mangala",
        "vedic": "Action",
        "energy": "action",
        "element": "fire",
        "quality": "cardinal",
        "keywords": ["execution", "behavior", "consequence", "karma"],
    },
    "O4_STRUCTURE": {
        "planet": "Venus",
        "sanskrit": "Shukra",
        "vedic": "Forming",
        "energy": "structure",
        "element": "earth/water",
        "quality": "fixed",
        "keywords": ["structure", "form", "embodiment", "pattern"],
    },
    "O5_COGNITION": {
        "planet": "Mercury",
        "sanskrit": "Budha",
        "vedic": "Perception",
        "energy": "perception",
        "element": "air",
        "quality": "mutable",
        "keywords": ["cognition", "attention", "emotion", "perception"],
    },
    "O6_AGENCY": {
        "planet": "Sun",
        "sanskrit": "Surya",
        "vedic": "Direction",
        "energy": "will",
        "element": "fire",
        "quality": "fixed",
        "keywords": ["agency", "control", "intent", "authorship"],
    },
    "O7_REASONING": {
        "planet": "Saturn",
        "sanskrit": "Shani",
        "vedic": "Discrimination",
        "energy": "logic",
        "element": "earth",
        "quality": "cardinal",
        "keywords": ["reasoning", "discrimination", "logic", "inference"],
    },
    "O8_PURPOSE": {
        "planet": "Jupiter",
        "sanskrit": "Guru",
        "vedic": "Meaning",
        "energy": "meaning",
        "element": "fire/ether",
        "quality": "mutable",
        "keywords": ["purpose", "meaning", "motivation", "why"],
    },
    "O9_WITNESSES": {
        "planet": "Ketu",
        "sanskrit": "Ketu",
        "vedic": "Meta-Observation",
        "energy": "awareness",
        "element": "ether",
        "quality": "spiritual",
        "keywords": ["witness", "meta-awareness", "reflection", "monitoring"],
    },
    "O10_UNIFYING": {
        "planet": "Rahu",
        "sanskrit": "Rahu",
        "vedic": "Coherence",
        "energy": "synthesis",
        "element": "air/ether",
        "quality": "obsessive",
        "keywords": ["unifying", "coherence", "synthesis", "harmony"],
    },
    "O11_INTEGRATION": {
        "planet": "Uranus",
        "sanskrit": "Varuna",
        "vedic": "Resolution",
        "energy": "consolidation",
        "element": "air",
        "quality": "revolutionary",
        "keywords": ["integration", "resolution", "consolidation", "completion"],
    },
    "O12_ABSOLVING": {
        "planet": "Neptune",
        "sanskrit": "Brahman",
        "vedic": "Termination",
        "energy": "dissolution",
        "element": "water/ether",
        "quality": "transcendent",
        "keywords": ["absolving", "termination", "release", "dissolution"],
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
    "semi-sextile": AspectType("Semi-Sextile", 30, "subtle", 4, 0.4),
    "sextile": AspectType("Sextile", 60, "harmonious", 6, 0.6),
    "square": AspectType("Square", 90, "challenging", 8, 0.8),
    "trine": AspectType("Trine", 120, "harmonious", 8, 0.9),
    "quincunx": AspectType("Quincunx", 150, "adjustment", 4, 0.5),
    "opposition": AspectType("Opposition", 180, "polarizing", 8, 1.0),
}


def get_aspect_between(layer_i: int, layer_j: int) -> AspectType:
    """
    Determine the astrological aspect between two ontological layers.
    Uses circular distance on the 12-layer wheel (30° per layer).
    """
    diff = abs(layer_i - layer_j)
    circular_diff = min(diff, 12 - diff)
    angle = circular_diff * 30

    if angle == 0:
        return ASPECTS["conjunction"]
    elif angle == 30:
        return ASPECTS["semi-sextile"]
    elif angle == 60:
        return ASPECTS["sextile"]
    elif angle == 90:
        return ASPECTS["square"]
    elif angle == 120:
        return ASPECTS["trine"]
    elif angle == 150:
        return ASPECTS["quincunx"]
    else:
        return ASPECTS["opposition"]


# =============================================================================
# BHAVA PAIR DEFINITIONS (12 sub-layers per pair)
# =============================================================================

# The 12 sub-layer names match the ontological layers
SUB_LAYER_NAMES = (
    "potential",     # O1 - Dormant aspect
    "identity",      # O2 - Tagging aspect
    "execution",     # O3 - Action aspect
    "structure",     # O4 - Forming aspect
    "cognition",     # O5 - Perception aspect
    "agency",        # O6 - Direction aspect
    "reasoning",     # O7 - Discrimination aspect
    "purpose",       # O8 - Meaning aspect
    "witnesses",     # O9 - Meta-observation aspect
    "unifying",      # O10 - Coherence aspect
    "integration",   # O11 - Resolution aspect
    "absolving",     # O12 - Termination aspect
)


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
    Define the 11 primary Bhava pairs with semantic meaning.
    Each pair has 12 sub-layers matching the ontological layer names.
    """
    from symbolu.ontological.types import LAYER_NAMES

    pairs = []

    # 11 Bhava pair definitions (O1↔O2 through O11↔O12)
    pair_definitions = [
        {
            # B1: O1_POTENTIAL ↔ O2_IDENTITY
            "name": "Potential-Identity",
            "description": "How dormant capacity becomes labeled/classified",
        },
        {
            # B2: O2_IDENTITY ↔ O3_EXECUTION
            "name": "Identity-Execution",
            "description": "How labels drive action and karma",
        },
        {
            # B3: O3_EXECUTION ↔ O4_STRUCTURE
            "name": "Execution-Structure",
            "description": "How actions crystallize into form",
        },
        {
            # B4: O4_STRUCTURE ↔ O5_COGNITION
            "name": "Structure-Cognition",
            "description": "How form enables perception",
        },
        {
            # B5: O5_COGNITION ↔ O6_AGENCY
            "name": "Cognition-Agency",
            "description": "How perception enables control",
        },
        {
            # B6: O6_AGENCY ↔ O7_REASONING
            "name": "Agency-Reasoning",
            "description": "How control applies logic",
        },
        {
            # B7: O7_REASONING ↔ O8_PURPOSE
            "name": "Reasoning-Purpose",
            "description": "How logic serves meaning",
        },
        {
            # B8: O8_PURPOSE ↔ O9_WITNESSES
            "name": "Purpose-Witnesses",
            "description": "How meaning enables meta-observation",
        },
        {
            # B9: O9_WITNESSES ↔ O10_UNIFYING
            "name": "Witnesses-Unifying",
            "description": "How observation enables coherence",
        },
        {
            # B10: O10_UNIFYING ↔ O11_INTEGRATION
            "name": "Unifying-Integration",
            "description": "How coherence leads to resolution",
        },
        {
            # B11: O11_INTEGRATION ↔ O12_ABSOLVING
            "name": "Integration-Absolving",
            "description": "How resolution enables termination",
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
            sub_layers=list(SUB_LAYER_NAMES),  # All 12 sub-layers
        ))

    return pairs


BHAVA_PAIRS = define_bhava_pairs()


# =============================================================================
# SEMANTIC BHAVA LAYER (PyTorch) - 12D
# =============================================================================

if PYTORCH_AVAILABLE:

    class SemanticBhavaLayer(nn.Module):
        """
        Semantically-grounded Bhava layer with 12D structure.

        Architecture:
            12D Ontological → 11 Pair Modules → 132D Semantic Bhava

        Each pair module:
            - Takes the two relevant ontological dimensions
            - Computes 12 sub-layer activations
            - Applies aspect-based modulation
        """

        def __init__(
            self,
            ontological_dim: int = 12,
            sub_layers_per_pair: int = 12,
            hidden_dim: int = 32,
        ):
            super().__init__()

            self.ontological_dim = ontological_dim
            self.num_pairs = ontological_dim - 1  # 11 pairs
            self.sub_layers_per_pair = sub_layers_per_pair
            self.bhava_dim = self.num_pairs * sub_layers_per_pair  # 132

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
                num_heads=3,  # 12 is divisible by 3
                batch_first=True,
            )

            # Store pair definitions for interpretability
            self.pair_names = [p.name for p in BHAVA_PAIRS]
            self.sub_layer_names = SUB_LAYER_NAMES

        def forward(self, onto: torch.Tensor) -> Dict[str, torch.Tensor]:
            """
            Compute semantic Bhava from ontological vector.

            Args:
                onto: Ontological probabilities (batch, 12)

            Returns:
                Dict with:
                - bhava: Full 132D vector
                - pairs: List of 11 pair outputs (each batch, 12)
                - attended: Cross-attended Bhava
            """
            batch_size = onto.shape[0]

            # Compute each pair's sub-layers
            pair_outputs = []
            for i, module in enumerate(self.pair_modules):
                # Extract the two relevant ontological dimensions
                pair_input = onto[:, i:i+2]  # (batch, 2)

                # Compute sub-layer activations
                sub_layers = module(pair_input)  # (batch, 12)

                # Apply aspect modulation
                sub_layers = sub_layers * self.aspect_weights[i]

                pair_outputs.append(sub_layers)

            # Stack pairs for attention
            pairs_stacked = torch.stack(pair_outputs, dim=1)  # (batch, 11, 12)

            # Cross-pair attention (how pairs influence each other)
            attended, _ = self.cross_attention(
                pairs_stacked, pairs_stacked, pairs_stacked
            )

            # Combine: original + attended
            combined = pairs_stacked + 0.3 * attended

            # Flatten to 132D
            bhava = combined.view(batch_size, -1)  # (batch, 132)

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
                                "name": self.sub_layer_names[idx],
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
        12D Ontological Engine with semantically-grounded Bhava.

        Combines:
        - Evidential classification (12D + uncertainty)
        - Semantic Bhava layer (132D with interpretable sub-layers)
        - Planetary correspondence analysis
        - Astrological aspect modulation
        """

        def __init__(
            self,
            encoder_dim: int = 384,
            hidden_dims: Tuple[int, ...] = (256, 128),
            ontological_dim: int = 12,
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

            # Evidential head (12D)
            self.evidential = nn.Linear(prev_dim, ontological_dim)

            # Semantic Bhava layer (132D)
            self.bhava = SemanticBhavaLayer(
                ontological_dim=ontological_dim,
                sub_layers_per_pair=12,
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
                "vedic": planetary["vedic"],
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
12D ASTROLOGICAL ONTOLOGICAL ENGINE
============================================================

Ontological Layers (Potential → Absolving):
  O1_POTENTIAL    → Pluto (Yama)      - Dormant, latent
  O2_IDENTITY     → Moon (Chandra)    - Tagging, labels
  O3_EXECUTION    → Mars (Mangala)    - Action, karma
  O4_STRUCTURE    → Venus (Shukra)    - Forming, embodiment
  O5_COGNITION    → Mercury (Budha)   - Perception, attention
  O6_AGENCY       → Sun (Surya)       - Direction, control
  O7_REASONING    → Saturn (Shani)    - Discrimination, logic
  O8_PURPOSE      → Jupiter (Guru)    - Meaning, motivation
  O9_WITNESSES    → Ketu              - Meta-observation
  O10_UNIFYING    → Rahu              - Coherence, synthesis
  O11_INTEGRATION → Uranus (Varuna)   - Resolution
  O12_ABSOLVING   → Neptune (Brahman) - Termination

Bhava Pairs (11 × 12 sub-layers = 132D):
  B1:  Potential-Identity (O1↔O2)
  B2:  Identity-Execution (O2↔O3)
  B3:  Execution-Structure (O3↔O4)
  B4:  Structure-Cognition (O4↔O5)
  B5:  Cognition-Agency (O5↔O6)
  B6:  Agency-Reasoning (O6↔O7)
  B7:  Reasoning-Purpose (O7↔O8)
  B8:  Purpose-Witnesses (O8↔O9)
  B9:  Witnesses-Unifying (O9↔O10)
  B10: Unifying-Integration (O10↔O11)
  B11: Integration-Absolving (O11↔O12)

Sub-layers (12 per pair):
  potential, identity, execution, structure,
  cognition, agency, reasoning, purpose,
  witnesses, unifying, integration, absolving

Total Parameters: {total_params:,}
============================================================
"""
