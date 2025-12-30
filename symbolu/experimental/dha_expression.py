#!/usr/bin/env python3
"""
DHA Expression Controller
=========================

Implements Google's insight: DHA as the "Expression Controller" that modulates
HOW understanding is delivered based on USER state, not just content.

Key Insight:
------------
- Internal State-Delta determines WHAT the system understands
- DHA Expression determines HOW that understanding is delivered
- Uses the SAME Chitta-Vritti framework, applied to USER state with temporal tracking

Architecture:
-------------
Single-turn: Content Vritti = User Vritti (no history)
Multi-turn:  Content Vritti ≠ User Vritti (accumulated over conversation)

This module reuses:
- v2.7 State Evolution for temporal tracking: θ_{t+1} = (1-α)·θ_t + α·θ*_t
- v2.8 Chitta-Vritti for cognitive mode detection
- BidirectionalGunaMapper for expression style (Sattvic/Rajasic/Tamasic delivery)

Usage:
------
    from symbolu.experimental import UserStateTracker, DHAExpressionModulator

    # Track user state over conversation
    user_tracker = UserStateTracker(decay_rate=0.4)

    # Each turn: update user state from content Vritti
    user_vritti = user_tracker.update(content_vritti)

    # Modulate expression based on user state
    modulator = DHAExpressionModulator()
    expression_delta = modulator(
        state_delta=raw_state_delta,
        user_vritti=user_vritti
    )
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum


# =============================================================================
# EXPRESSION STYLE ENUM
# =============================================================================

class ExpressionStyle(Enum):
    """How to deliver the response based on user state."""
    SATTVIC = "sattvic"      # Gentle, harmonious, nurturing
    RAJASIC = "rajasic"      # Direct, active, assertive
    TAMASIC = "tamasic"      # Reserved, cautious, minimal


@dataclass
class UserProfile:
    """Accumulated user state for expression modulation."""
    vritti: torch.Tensor           # [5] accumulated Vritti distribution
    resistance: float              # 0-1, derived from Viparyaya
    readiness: float               # 0-1, derived from Pramāṇa
    confusion: float               # 0-1, derived from Vikalpa
    engagement: float              # 0-1, inverse of Nidrā
    turn_count: int                # Number of turns tracked

    @property
    def expression_style(self) -> ExpressionStyle:
        """Determine expression style from user state."""
        if self.resistance > 0.5:
            return ExpressionStyle.SATTVIC  # High resistance → gentle
        elif self.readiness > 0.6:
            return ExpressionStyle.RAJASIC  # High readiness → direct
        elif self.engagement < 0.3:
            return ExpressionStyle.TAMASIC  # Low engagement → reserved
        else:
            return ExpressionStyle.SATTVIC  # Default to gentle


# =============================================================================
# USER STATE TRACKER (v2.7 Temporal Evolution Applied to User Vritti)
# =============================================================================

class UserStateTracker(nn.Module):
    """
    Tracks user's cognitive state across conversation turns.

    Uses v2.7 State Evolution mechanism:
        user_vritti_{t+1} = (1 - α) · user_vritti_t + α · content_vritti_t

    This allows the system to remember:
    - User was skeptical 2 turns ago (Viparyaya)
    - User has been confused throughout (Vikalpa)
    - User is becoming more receptive (Pramāṇa increasing)
    """

    def __init__(
        self,
        decay_rate: float = 0.4,
        window_size: int = 5,
    ):
        """
        Args:
            decay_rate: α in the evolution equation (0.3-0.5 recommended)
            window_size: Maximum turns to track (for bounded memory)
        """
        super().__init__()
        self.decay_rate = decay_rate
        self.window_size = window_size

        # Initialize user state (uniform Vritti)
        self.register_buffer(
            'user_vritti',
            torch.ones(5) / 5  # [Pramāṇa, Viparyaya, Vikalpa, Smṛti, Nidrā]
        )
        self.turn_count = 0

    def reset(self):
        """Reset user state for new conversation."""
        self.user_vritti = torch.ones(5, device=self.user_vritti.device) / 5
        self.turn_count = 0

    def update(self, content_vritti: torch.Tensor) -> torch.Tensor:
        """
        Update user state with new content Vritti.

        Args:
            content_vritti: [5] Vritti from current turn's content

        Returns:
            Updated user Vritti [5]
        """
        # Ensure correct shape
        if content_vritti.dim() > 1:
            content_vritti = content_vritti.squeeze()
        content_vritti = content_vritti.to(self.user_vritti.device)

        # v2.7 State Evolution: θ_{t+1} = (1-α)·θ_t + α·θ*_t
        self.user_vritti = (
            (1 - self.decay_rate) * self.user_vritti +
            self.decay_rate * content_vritti
        )

        # Renormalize to valid probability distribution
        self.user_vritti = F.softmax(self.user_vritti, dim=-1)

        self.turn_count = min(self.turn_count + 1, self.window_size)

        return self.user_vritti.clone()

    def get_profile(self) -> UserProfile:
        """Extract user profile from accumulated state."""
        vritti = self.user_vritti

        return UserProfile(
            vritti=vritti.clone(),
            resistance=vritti[1].item(),    # Viparyaya = skepticism/resistance
            readiness=vritti[0].item(),     # Pramāṇa = clarity/readiness
            confusion=vritti[2].item(),     # Vikalpa = confusion/branching
            engagement=1.0 - vritti[4].item(),  # 1 - Nidrā = engagement
            turn_count=self.turn_count,
        )

    def get_resistance_score(self) -> float:
        """
        Compute resistance score for DHA modulation.

        High resistance when:
        - Viparyaya (skepticism) is high
        - Vikalpa (confusion) is high
        - Pramāṇa (clarity) is low
        """
        vritti = self.user_vritti
        resistance = (
            0.5 * vritti[1].item() +  # Viparyaya weight
            0.3 * vritti[2].item() +  # Vikalpa weight
            0.2 * (1 - vritti[0].item())  # Inverse Pramāṇa weight
        )
        return min(1.0, max(0.0, resistance))


# =============================================================================
# DHA EXPRESSION MODULATOR
# =============================================================================

class DHAExpressionModulator(nn.Module):
    """
    Pre-rendering filter that modulates State-Delta for user-appropriate delivery.

    Google's Three Axes:
    1. Ego State → Vocabulary & Authority (tone)
    2. Resistance Level → Information Density (dilution)
    3. Readiness → Pacing & Depth (Bodha vs Anumāna)

    Implementation:
    - Takes raw State-Delta (what to communicate)
    - Takes User Profile (who we're communicating to)
    - Returns Communication-Delta (how to communicate)
    """

    def __init__(
        self,
        max_damping: float = 0.5,
        smoothing_factor: float = 0.3,
    ):
        """
        Args:
            max_damping: Maximum dampening when resistance is high (0.5 = halve intensity)
            smoothing_factor: How much to smooth transitions when confusion is high
        """
        super().__init__()
        self.max_damping = max_damping
        self.smoothing_factor = smoothing_factor

        # Guna weights for expression style
        # [Sattva, Rajas, Tamas] for each style
        self.register_buffer('style_to_guna', torch.tensor([
            [0.7, 0.2, 0.1],  # SATTVIC: high clarity, gentle
            [0.3, 0.6, 0.1],  # RAJASIC: high activity, direct
            [0.2, 0.2, 0.6],  # TAMASIC: high inertia, reserved
        ]))

    def forward(
        self,
        state_delta: torch.Tensor,
        user_vritti: torch.Tensor,
        user_profile: Optional[UserProfile] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Modulate state-delta for user-appropriate expression.

        Args:
            state_delta: Raw state delta from understanding [B, state_dim] or [state_dim]
            user_vritti: User's accumulated Vritti [5] or [B, 5]
            user_profile: Optional pre-computed profile

        Returns:
            Dict with:
            - 'communication_delta': Modulated delta for expression
            - 'damping_factor': How much we dampened
            - 'expression_guna': [Sattva, Rajas, Tamas] for this delivery
            - 'style': ExpressionStyle enum value
        """
        # Handle batched or single input
        batched = state_delta.dim() > 1
        if not batched:
            state_delta = state_delta.unsqueeze(0)
            user_vritti = user_vritti.unsqueeze(0)

        B = state_delta.size(0)
        device = state_delta.device

        # Extract user signals from Vritti
        resistance = user_vritti[:, 1]   # Viparyaya
        confusion = user_vritti[:, 2]    # Vikalpa
        readiness = user_vritti[:, 0]    # Pramāṇa
        engagement = 1 - user_vritti[:, 4]  # 1 - Nidrā

        # 1. Compute damping factor based on resistance
        # High resistance → dampen the delta (softer delivery)
        damping = 1.0 - (resistance * self.max_damping)  # [B]

        # 2. Apply damping to state delta
        damping_expanded = damping.unsqueeze(-1)  # [B, 1]
        communication_delta = state_delta * damping_expanded

        # 3. Smooth transitions if confusion is high
        # (When user is confused, don't make big jumps)
        if hasattr(self, '_prev_delta') and self._prev_delta is not None:
            smoothing = confusion * self.smoothing_factor  # [B]
            smoothing_expanded = smoothing.unsqueeze(-1)  # [B, 1]
            communication_delta = (
                (1 - smoothing_expanded) * communication_delta +
                smoothing_expanded * self._prev_delta
            )

        # Store for next turn's smoothing
        self._prev_delta = communication_delta.detach().clone()

        # 4. Determine expression style and Guna
        # High resistance → Sattvic (gentle)
        # High readiness, low resistance → Rajasic (direct)
        # Low engagement → Tamasic (reserved)

        style_weights = torch.zeros(B, 3, device=device)
        style_weights[:, 0] = resistance + confusion * 0.5  # Sattvic weight
        style_weights[:, 1] = readiness * (1 - resistance)   # Rajasic weight
        style_weights[:, 2] = (1 - engagement) * 0.5         # Tamasic weight
        style_weights = F.softmax(style_weights, dim=-1)

        # Compute expression Guna as weighted combination
        expression_guna = style_weights @ self.style_to_guna.to(device)  # [B, 3]

        # Determine dominant style
        dominant_style_idx = style_weights.argmax(dim=-1)  # [B]
        styles = [
            ExpressionStyle.SATTVIC,
            ExpressionStyle.RAJASIC,
            ExpressionStyle.TAMASIC,
        ]

        # Unbatch if needed
        if not batched:
            communication_delta = communication_delta.squeeze(0)
            damping = damping.squeeze(0)
            expression_guna = expression_guna.squeeze(0)
            dominant_style = styles[dominant_style_idx.item()]
        else:
            dominant_style = [styles[i.item()] for i in dominant_style_idx]

        return {
            'communication_delta': communication_delta,
            'damping_factor': damping,
            'expression_guna': expression_guna,
            'style': dominant_style,
        }

    def get_delivery_guidance(
        self,
        user_profile: UserProfile,
    ) -> Dict[str, Any]:
        """
        Get human-readable delivery guidance based on user state.

        Returns guidance for:
        - Tone (ego state adjustment)
        - Density (information dilution)
        - Pacing (Bodha vs Anumāna)
        """
        guidance = {
            'style': user_profile.expression_style.value,
            'resistance': user_profile.resistance,
            'readiness': user_profile.readiness,
        }

        # Tone guidance
        if user_profile.resistance > 0.5:
            guidance['tone'] = "Use nurturing, non-confrontational language"
            guidance['authority'] = "Peer-level (Adult ego state)"
        elif user_profile.readiness > 0.6:
            guidance['tone'] = "Direct and confident delivery"
            guidance['authority'] = "Expert-level (Parent ego state)"
        else:
            guidance['tone'] = "Supportive and encouraging"
            guidance['authority'] = "Collaborative (Adult ego state)"

        # Density guidance
        if user_profile.resistance > 0.5:
            guidance['density'] = "LOW - Use metaphors, avoid raw data"
            guidance['cognitive_load'] = "Minimal - one concept at a time"
        elif user_profile.confusion > 0.4:
            guidance['density'] = "MEDIUM - Balance explanation with examples"
            guidance['cognitive_load'] = "Moderate - build incrementally"
        else:
            guidance['density'] = "HIGH - Can include technical details"
            guidance['cognitive_load'] = "Full - complete information"

        # Pacing guidance
        if user_profile.readiness > 0.6:
            guidance['pacing'] = "BODHA - Jump to conclusion"
            guidance['structure'] = "State answer first, then support"
        else:
            guidance['pacing'] = "ANUMĀNA - Step-by-step logic"
            guidance['structure'] = "Build argument before conclusion"

        return guidance


# =============================================================================
# INTEGRATED DHA EXPRESSION CONTROLLER
# =============================================================================

class DHAExpressionController(nn.Module):
    """
    Complete DHA Expression Controller combining:
    - UserStateTracker (temporal accumulation)
    - DHAExpressionModulator (delivery optimization)

    This is the "High-EQ Interlocutor" layer between understanding and expression.
    """

    def __init__(
        self,
        decay_rate: float = 0.4,
        max_damping: float = 0.5,
    ):
        super().__init__()
        self.user_tracker = UserStateTracker(decay_rate=decay_rate)
        self.modulator = DHAExpressionModulator(max_damping=max_damping)

    def reset_conversation(self):
        """Reset for new conversation."""
        self.user_tracker.reset()
        self.modulator._prev_delta = None

    def forward(
        self,
        state_delta: torch.Tensor,
        content_vritti: torch.Tensor,
    ) -> Dict[str, Any]:
        """
        Process a turn: update user state and modulate expression.

        Args:
            state_delta: Raw understanding delta [state_dim]
            content_vritti: Vritti from current content [5]

        Returns:
            Dict with modulation results and user profile
        """
        # Update user state with content Vritti
        user_vritti = self.user_tracker.update(content_vritti)

        # Get user profile
        profile = self.user_tracker.get_profile()

        # Modulate expression
        result = self.modulator(
            state_delta=state_delta,
            user_vritti=user_vritti,
            user_profile=profile,
        )

        # Add profile and guidance
        result['user_profile'] = profile
        result['delivery_guidance'] = self.modulator.get_delivery_guidance(profile)

        return result


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    print("DHA Expression Controller Demo")
    print("=" * 50)

    # Create controller
    controller = DHAExpressionController(decay_rate=0.4)

    # Simulate multi-turn conversation
    turns = [
        # Turn 1: User is skeptical (high Viparyaya)
        torch.tensor([0.1, 0.6, 0.2, 0.1, 0.0]),  # Vritti
        # Turn 2: User is still skeptical but engaging
        torch.tensor([0.2, 0.5, 0.2, 0.1, 0.0]),
        # Turn 3: User becomes more receptive (Pramāṇa rising)
        torch.tensor([0.5, 0.2, 0.2, 0.1, 0.0]),
        # Turn 4: User is ready for conclusion
        torch.tensor([0.7, 0.1, 0.1, 0.1, 0.0]),
    ]

    state_delta = torch.randn(124)  # Simulated understanding

    print("\nMulti-turn Expression Modulation:")
    print("-" * 50)

    for i, content_vritti in enumerate(turns):
        result = controller(state_delta, content_vritti)
        profile = result['user_profile']
        guidance = result['delivery_guidance']

        print(f"\nTurn {i+1}:")
        print(f"  User Resistance: {profile.resistance:.2f}")
        print(f"  User Readiness:  {profile.readiness:.2f}")
        print(f"  Expression Style: {result['style'].value}")
        print(f"  Damping Factor:  {result['damping_factor']:.2f}")
        print(f"  Pacing: {guidance['pacing']}")
        print(f"  Tone: {guidance['tone']}")
