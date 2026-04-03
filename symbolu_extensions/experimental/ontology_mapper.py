#!/usr/bin/env python3
"""
Ontology Mapper: Phonemes → Bhava States
=========================================

Maps phonemic representations to ontological (Bhava) states.
This is the semantic grounding layer of Tier 3 training.

The Bhava states represent fundamental modes of meaning/being:
- What TYPE of content is this? (factual, evaluative, narrative...)
- What is the INTENT? (inform, persuade, question...)
- What is the EPISTEMIC status? (certain, speculative, unknown...)

This enables the model to reason about MEANING rather than tokens.

Architecture:
    phoneme_energy[44] + context → Bhava_probs[12] + constraints
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum, auto


# =============================================================================
# BHAVA (ONTOLOGICAL) STATES
# =============================================================================

class BhavaState(Enum):
    """
    Fundamental ontological states (modes of meaning).

    Based on SymbolU's ontological framework, these represent
    the "type of understanding" at any moment.

    These are NOT sentiment - they are deeper categories of meaning.
    """

    # === Content Type ===
    FACTUAL = auto()        # Stating facts, descriptions
    ANALYTICAL = auto()     # Explaining, analyzing, reasoning
    EVALUATIVE = auto()     # Judging, assessing, rating

    # === Rhetorical Mode ===
    NARRATIVE = auto()      # Telling a story, sequence of events
    ARGUMENTATIVE = auto()  # Making a case, persuading
    INSTRUCTIVE = auto()    # Teaching, directing, how-to

    # === Epistemic Status ===
    CERTAIN = auto()        # High confidence assertions
    SPECULATIVE = auto()    # Possibilities, hypotheticals
    QUESTIONING = auto()    # Seeking information, inquiry

    # === Affective Tone ===
    POSITIVE = auto()       # Positive valence
    NEGATIVE = auto()       # Negative valence
    NEUTRAL = auto()        # Neutral/objective tone


# Bhava state metadata
BHAVA_DESCRIPTIONS = {
    BhavaState.FACTUAL: "Stating objective facts or descriptions",
    BhavaState.ANALYTICAL: "Explaining, reasoning, or analyzing",
    BhavaState.EVALUATIVE: "Making judgments or assessments",
    BhavaState.NARRATIVE: "Telling a story or sequence",
    BhavaState.ARGUMENTATIVE: "Making a case or persuading",
    BhavaState.INSTRUCTIVE: "Teaching or giving directions",
    BhavaState.CERTAIN: "High confidence claims",
    BhavaState.SPECULATIVE: "Hypotheticals or possibilities",
    BhavaState.QUESTIONING: "Seeking information",
    BhavaState.POSITIVE: "Positive emotional valence",
    BhavaState.NEGATIVE: "Negative emotional valence",
    BhavaState.NEUTRAL: "Neutral or objective tone",
}

NUM_BHAVA_STATES = len(BhavaState)

# Bhava to index
BHAVA_TO_IDX = {state: state.value - 1 for state in BhavaState}
IDX_TO_BHAVA = {v: k for k, v in BHAVA_TO_IDX.items()}


# =============================================================================
# BHAVA TRANSITION RULES
# =============================================================================

@dataclass
class BhavaTransition:
    """
    Defines legal transitions between Bhava states.

    Not all transitions are equally likely or even valid.
    This encodes prior knowledge about meaning flow.
    """
    from_state: BhavaState
    to_state: BhavaState
    probability: float  # Prior probability of this transition
    constraint: Optional[str] = None  # Description of constraint


# Transition matrix prior (which state flows naturally follow)
# Higher values = more natural transition
BHAVA_TRANSITIONS = {
    # Factual tends to stay factual or become analytical
    (BhavaState.FACTUAL, BhavaState.FACTUAL): 0.6,
    (BhavaState.FACTUAL, BhavaState.ANALYTICAL): 0.3,
    (BhavaState.FACTUAL, BhavaState.EVALUATIVE): 0.1,

    # Analytical often leads to evaluation or stays analytical
    (BhavaState.ANALYTICAL, BhavaState.ANALYTICAL): 0.5,
    (BhavaState.ANALYTICAL, BhavaState.EVALUATIVE): 0.3,
    (BhavaState.ANALYTICAL, BhavaState.FACTUAL): 0.2,

    # Narrative tends to continue
    (BhavaState.NARRATIVE, BhavaState.NARRATIVE): 0.7,
    (BhavaState.NARRATIVE, BhavaState.EVALUATIVE): 0.2,
    (BhavaState.NARRATIVE, BhavaState.FACTUAL): 0.1,

    # Questions often lead to factual or analytical responses
    (BhavaState.QUESTIONING, BhavaState.FACTUAL): 0.4,
    (BhavaState.QUESTIONING, BhavaState.ANALYTICAL): 0.3,
    (BhavaState.QUESTIONING, BhavaState.SPECULATIVE): 0.2,

    # Speculative often becomes certain or stays speculative
    (BhavaState.SPECULATIVE, BhavaState.SPECULATIVE): 0.4,
    (BhavaState.SPECULATIVE, BhavaState.CERTAIN): 0.3,
    (BhavaState.SPECULATIVE, BhavaState.ANALYTICAL): 0.3,

    # Default: small probability for all other transitions
}


def get_transition_matrix() -> torch.Tensor:
    """
    Build the Bhava transition probability matrix.

    Returns:
        [NUM_BHAVA, NUM_BHAVA] transition probabilities
    """
    # Start with uniform small probability
    matrix = torch.ones(NUM_BHAVA_STATES, NUM_BHAVA_STATES) * 0.05

    # Fill in known transitions
    for (from_state, to_state), prob in BHAVA_TRANSITIONS.items():
        from_idx = BHAVA_TO_IDX[from_state]
        to_idx = BHAVA_TO_IDX[to_state]
        matrix[from_idx, to_idx] = prob

    # Normalize rows to sum to 1
    matrix = matrix / matrix.sum(dim=1, keepdim=True)

    return matrix


# =============================================================================
# ONTOLOGY MAPPER MODULE
# =============================================================================

class OntologyMapper(nn.Module):
    """
    Maps phoneme energy + context to Bhava (ontological) states.

    This is the bridge between acoustic perception and semantic understanding.

    Architecture:
        phoneme_energy[44] + topic_embedding[64] → Bhava_probs[12]

    The mapping captures:
    1. What TYPE of content is being expressed
    2. What INTENT underlies the expression
    3. What CONSTRAINTS apply to valid continuations

    Example:
        Input: "The company reported strong growth, but..."
        Phoneme pattern: [business domain markers]
        Output Bhava: ANALYTICAL (0.6), EVALUATIVE (0.3), NEGATIVE (0.1)
        Constraint: Next must explain downside (evaluative/negative content)
    """

    def __init__(
        self,
        num_phonemes: int = 44,
        topic_dim: int = 64,
        hidden_dim: int = 256,
        num_bhava: int = NUM_BHAVA_STATES,
        num_layers: int = 2,
        dropout: float = 0.1,
        use_transition_prior: bool = True,
    ):
        super().__init__()
        self.num_phonemes = num_phonemes
        self.topic_dim = topic_dim
        self.num_bhava = num_bhava
        self.use_transition_prior = use_transition_prior

        input_dim = num_phonemes + topic_dim

        # Main mapping network
        layers = []
        in_dim = input_dim

        for i in range(num_layers):
            out_dim = hidden_dim if i < num_layers - 1 else hidden_dim // 2
            layers.extend([
                nn.Linear(in_dim, out_dim),
                nn.LayerNorm(out_dim),
                nn.GELU(),
                nn.Dropout(dropout),
            ])
            in_dim = out_dim

        self.mapper = nn.Sequential(*layers)

        # Bhava projection
        self.bhava_proj = nn.Linear(hidden_dim // 2, num_bhava)

        # Learnable transition prior
        if use_transition_prior:
            init_matrix = get_transition_matrix()
            self.transition_prior = nn.Parameter(init_matrix)
        else:
            self.register_buffer('transition_prior', get_transition_matrix())

        # Constraint predictor: predicts what content types are LEGAL next
        self.constraint_predictor = nn.Sequential(
            nn.Linear(num_bhava, hidden_dim // 2),
            nn.GELU(),
            nn.Linear(hidden_dim // 2, num_bhava),
            nn.Sigmoid(),  # 0-1 constraint mask
        )

    def forward(
        self,
        phoneme_energy: torch.Tensor,
        topic_embedding: torch.Tensor,
        prev_bhava: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Map phonemes + topic to Bhava state probabilities.

        Args:
            phoneme_energy: [B, T, num_phonemes] phoneme distributions
            topic_embedding: [B, T, topic_dim] topic context
            prev_bhava: [B, T, num_bhava] previous Bhava state (optional)

        Returns:
            bhava_probs: [B, T, num_bhava] probability over Bhava states
            constraint_mask: [B, T, num_bhava] what's legal next (0-1)
        """
        # Concatenate inputs
        combined = torch.cat([phoneme_energy, topic_embedding], dim=-1)

        # Map to hidden
        hidden = self.mapper(combined)

        # Project to Bhava logits
        bhava_logits = self.bhava_proj(hidden)

        # Apply transition prior if previous state available
        if prev_bhava is not None and self.use_transition_prior:
            # Expected Bhava based on transition from previous
            transition_bias = torch.einsum(
                'btb,bc->btc',
                prev_bhava,
                self.transition_prior
            )
            bhava_logits = bhava_logits + transition_bias

        # Softmax to get probabilities
        bhava_probs = F.softmax(bhava_logits, dim=-1)

        # Predict constraints for next position
        constraint_mask = self.constraint_predictor(bhava_probs)

        return bhava_probs, constraint_mask

    def get_dominant_bhava(
        self,
        bhava_probs: torch.Tensor,
        threshold: float = 0.1,
    ) -> List[List[Tuple[str, float]]]:
        """
        Get dominant Bhava states at each position.

        Returns list of (state_name, probability) tuples above threshold.
        """
        B, T, _ = bhava_probs.shape
        results = []

        for b in range(B):
            seq_results = []
            for t in range(T):
                pos_results = []
                for i, prob in enumerate(bhava_probs[b, t]):
                    if prob.item() > threshold:
                        state = IDX_TO_BHAVA[i]
                        pos_results.append((state.name, prob.item()))
                pos_results.sort(key=lambda x: -x[1])
                seq_results.append(pos_results)
            results.append(seq_results)

        return results

    def compute_transition_loss(
        self,
        bhava_sequence: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute loss for Bhava transitions - penalize illegal jumps.

        Args:
            bhava_sequence: [B, T, num_bhava] sequence of Bhava probs

        Returns:
            loss: Transition violation loss
        """
        # Get consecutive pairs
        bhava_t = bhava_sequence[:, :-1]    # [B, T-1, num_bhava]
        bhava_next = bhava_sequence[:, 1:]  # [B, T-1, num_bhava]

        # Expected next based on transition matrix
        expected_next = torch.einsum(
            'btb,bc->btc',
            bhava_t,
            F.softmax(self.transition_prior, dim=-1)
        )

        # KL divergence between actual and expected
        loss = F.kl_div(
            torch.log(bhava_next + 1e-8),
            expected_next,
            reduction='batchmean'
        )

        return loss


# =============================================================================
# RHETORICAL MARKER DETECTOR
# =============================================================================

class RhetoricalMarkerDetector(nn.Module):
    """
    Detects rhetorical markers that signal Bhava transitions.

    Certain words/patterns strongly predict Bhava state changes:
    - "but", "however" → shift to EVALUATIVE/NEGATIVE
    - "because", "therefore" → shift to ANALYTICAL
    - "?" → QUESTIONING
    - "should", "must" → INSTRUCTIVE
    - "imagine", "what if" → SPECULATIVE

    This provides explicit signal for Bhava transitions.
    """

    # Marker patterns (would be learned in practice)
    CONTRAST_MARKERS = {'but', 'however', 'although', 'yet', 'despite'}
    CAUSAL_MARKERS = {'because', 'therefore', 'thus', 'hence', 'since'}
    QUESTION_MARKERS = {'?', 'who', 'what', 'where', 'when', 'why', 'how'}
    INSTRUCTION_MARKERS = {'should', 'must', 'need', 'have to', 'ought'}
    SPECULATION_MARKERS = {'might', 'could', 'perhaps', 'maybe', 'possibly', 'imagine'}
    POSITIVE_MARKERS = {'great', 'excellent', 'wonderful', 'amazing', 'good'}
    NEGATIVE_MARKERS = {'bad', 'terrible', 'awful', 'poor', 'wrong', 'fail'}

    def __init__(
        self,
        vocab_size: int = 50257,
        embed_dim: int = 256,
        num_bhava: int = NUM_BHAVA_STATES,
    ):
        super().__init__()

        # Learnable marker embeddings
        self.marker_embed = nn.Embedding(vocab_size, embed_dim)

        # Marker to Bhava mapping
        self.marker_to_bhava = nn.Sequential(
            nn.Linear(embed_dim, embed_dim // 2),
            nn.GELU(),
            nn.Linear(embed_dim // 2, num_bhava),
        )

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        """
        Detect rhetorical markers and their Bhava implications.

        Args:
            input_ids: [B, T] token indices

        Returns:
            marker_bhava: [B, T, num_bhava] Bhava shift signals from markers
        """
        marker_embeds = self.marker_embed(input_ids)
        marker_bhava = self.marker_to_bhava(marker_embeds)
        return F.softmax(marker_bhava, dim=-1)


# =============================================================================
# FULL ONTOLOGICAL PERCEPTION PIPELINE
# =============================================================================

class OntologicalPerception(nn.Module):
    """
    Complete pipeline: tokens → phonemes → Bhava states.

    This is the perception layer of Tier 3 training:
    1. Encode tokens to phoneme energy
    2. Extract topic embedding
    3. Map to Bhava states
    4. Detect rhetorical markers
    5. Output structured CognitiveState

    The output enables state-delta training in meaning space.
    """

    def __init__(
        self,
        vocab_size: int = 50257,
        embed_dim: int = 768,
        num_phonemes: int = 44,
        topic_dim: int = 64,
        num_bhava: int = NUM_BHAVA_STATES,
        dropout: float = 0.1,
    ):
        super().__init__()

        # Phoneme encoder (simplified - uses embedding projection)
        self.phoneme_proj = nn.Sequential(
            nn.Linear(embed_dim, embed_dim // 2),
            nn.GELU(),
            nn.Linear(embed_dim // 2, num_phonemes),
            nn.Softmax(dim=-1),
        )

        # Topic extractor
        self.topic_proj = nn.Sequential(
            nn.Linear(embed_dim, embed_dim // 2),
            nn.GELU(),
            nn.Linear(embed_dim // 2, topic_dim),
        )

        # Ontology mapper
        self.ontology_mapper = OntologyMapper(
            num_phonemes=num_phonemes,
            topic_dim=topic_dim,
            num_bhava=num_bhava,
            dropout=dropout,
        )

        # Rhetorical marker detector
        self.marker_detector = RhetoricalMarkerDetector(
            vocab_size=vocab_size,
            num_bhava=num_bhava,
        )

        # Dynamics predictor (coherence, entropy, etc.)
        self.dynamics_pred = nn.Sequential(
            nn.Linear(num_bhava + topic_dim, 64),
            nn.GELU(),
            nn.Linear(64, 4),  # coherence, entropy, confidence, momentum
            nn.Sigmoid(),
        )

    def forward(
        self,
        hidden_states: torch.Tensor,
        input_ids: Optional[torch.Tensor] = None,
        prev_state: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Full perception pipeline.

        Args:
            hidden_states: [B, T, embed_dim] from transformer
            input_ids: [B, T] token indices (for marker detection)
            prev_state: [B, T, state_dim] previous cognitive states

        Returns:
            Dict with:
                phoneme_energy: [B, T, num_phonemes]
                topic_embedding: [B, T, topic_dim]
                bhava_probs: [B, T, num_bhava]
                constraint_mask: [B, T, num_bhava]
                dynamics: [B, T, 4]
                full_state: [B, T, state_dim] complete cognitive state
        """
        B, T, _ = hidden_states.shape

        # Extract phoneme energy
        phoneme_energy = self.phoneme_proj(hidden_states)

        # Extract topic embedding
        topic_embedding = self.topic_proj(hidden_states)

        # Get previous Bhava if available
        prev_bhava = None
        if prev_state is not None:
            # Extract Bhava from previous state
            # Assuming state layout: [phoneme, topic, bhava, dynamics]
            bhava_start = 44 + 64  # After phoneme and topic
            prev_bhava = prev_state[:, :, bhava_start:bhava_start + NUM_BHAVA_STATES]

        # Map to Bhava states
        bhava_probs, constraint_mask = self.ontology_mapper(
            phoneme_energy, topic_embedding, prev_bhava
        )

        # Add rhetorical marker signal if input_ids provided
        if input_ids is not None:
            marker_signal = self.marker_detector(input_ids)
            bhava_probs = 0.8 * bhava_probs + 0.2 * marker_signal

        # Predict dynamics
        dynamics_input = torch.cat([bhava_probs, topic_embedding], dim=-1)
        dynamics = self.dynamics_pred(dynamics_input)

        # Assemble full cognitive state
        full_state = torch.cat([
            phoneme_energy,   # 44
            topic_embedding,  # 64
            bhava_probs,      # 12
            dynamics,         # 4
        ], dim=-1)  # Total: 124

        return {
            'phoneme_energy': phoneme_energy,
            'topic_embedding': topic_embedding,
            'bhava_probs': bhava_probs,
            'constraint_mask': constraint_mask,
            'dynamics': dynamics,
            'full_state': full_state,
        }


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

def example_usage():
    """Demonstrate ontology mapping."""

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    # Create perception pipeline
    perception = OntologicalPerception(
        vocab_size=50257,
        embed_dim=768,
    ).to(device)

    # Simulate transformer hidden states
    B, T = 2, 50
    hidden_states = torch.randn(B, T, 768, device=device)
    input_ids = torch.randint(0, 50257, (B, T), device=device)

    # Run perception
    output = perception(hidden_states, input_ids)

    print("Ontological Perception Output:")
    print(f"  Phoneme energy: {output['phoneme_energy'].shape}")
    print(f"  Topic embedding: {output['topic_embedding'].shape}")
    print(f"  Bhava probs: {output['bhava_probs'].shape}")
    print(f"  Constraint mask: {output['constraint_mask'].shape}")
    print(f"  Dynamics: {output['dynamics'].shape}")
    print(f"  Full state: {output['full_state'].shape}")

    # Show Bhava distribution for first position
    print("\nBhava distribution (first position):")
    for i, prob in enumerate(output['bhava_probs'][0, 0]):
        state = IDX_TO_BHAVA[i]
        if prob.item() > 0.05:
            print(f"  {state.name}: {prob.item():.3f}")

    # Show transition matrix
    print("\nBhava transition matrix (learned):")
    trans = F.softmax(perception.ontology_mapper.transition_prior, dim=-1)
    print(f"  Shape: {trans.shape}")
    print(f"  FACTUAL → ANALYTICAL: {trans[0, 1].item():.3f}")
    print(f"  ANALYTICAL → EVALUATIVE: {trans[1, 2].item():.3f}")


if __name__ == "__main__":
    example_usage()
