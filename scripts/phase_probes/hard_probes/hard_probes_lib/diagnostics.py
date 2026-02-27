"""
Diagnostic modules for monitoring phase learning and consciousness.

Contains:
    - SRK fallback implementations (OntologicalBridge, PhaseExtractionHook, etc.)
    - KoshaDiagnostics: 5-layer consciousness monitoring
    - WitnessDiagnostics: Sakshi observer tracking
    - SRKPhaseLearningMonitor: Per-layer phase learning progression
    - LayerInfluenceDiagnostics: Phase vs quad contribution analysis

CLI Usage::

    # Enable SRK monitoring
    python train_hard_probes.py --real-language --enable-srk --probe-layers

    # Enable Kosha consciousness diagnostics
    python train_hard_probes.py --real-language --enable-kosha \\
        --kosha-target INTELLECTUAL

    # Enable Witness observation
    python train_hard_probes.py --real-language --enable-witness
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Dict, List, Optional
from enum import Enum
from dataclasses import dataclass, field

from .imports import (
    SRK_AVAILABLE, KOSHA_AVAILABLE, SOVEREIGN_STATE_DIM,
    KOSHA_NAMES, KOSHA_VEDIC_NAMES, KOSHA_INDICES, KOSHA_SLICE,
)

# =============================================================================
# LOCAL SRK COMPONENT IMPLEMENTATIONS (Fallback when imports fail)
# =============================================================================

if not SRK_AVAILABLE:
    # Local implementation of OntologicalBridge for Layer 4
    class OntologicalBridge(nn.Module):
        """
        L4: DNA Bridge - Projects hidden states to 12D ontological space.

        Creates a foundational ontological "signature" early in processing,
        grounding the model's internal representation in the 12 Aspects.
        """
        def __init__(self, hidden_dim: int, onto_dim: int = 12):
            super().__init__()
            self.hidden_dim = hidden_dim
            self.onto_dim = onto_dim
            self.onto_proj = nn.Linear(hidden_dim, onto_dim, bias=False)
            self.onto_norm = nn.LayerNorm(onto_dim)

        def forward(self, hidden_states: torch.Tensor) -> Tuple[torch.Tensor, Dict[str, float]]:
            """Project hidden states to 12D ontological space."""
            onto_repr = self.onto_proj(hidden_states)  # [B, N, 12]
            onto_repr = self.onto_norm(onto_repr)

            with torch.no_grad():
                aspect_means = onto_repr.mean(dim=[0, 1])
                diversity = aspect_means.std().item()
                metrics = {
                    'onto_diversity': diversity,
                    'onto_mean_activation': aspect_means.abs().mean().item(),
                }
            return onto_repr, metrics

    # Local implementation of PhaseExtractionHook for Layer 7
    class PhaseExtractionHook(nn.Module):
        """
        L7: CSR Alignment - Extracts phase information from attention.

        Non-invasive hook that captures rotational phase from Q-K interaction
        for phase coherence analysis.
        """
        def __init__(self, hidden_dim: int, num_heads: int = 8):
            super().__init__()
            self.hidden_dim = hidden_dim
            self.num_heads = num_heads
            self.phase_proj = nn.Linear(hidden_dim, num_heads)
            self._last_phases = None

        def forward(self, hidden_states: torch.Tensor) -> Tuple[torch.Tensor, Dict[str, float]]:
            """Extract phase representation from hidden states."""
            phases = self.phase_proj(hidden_states)  # [B, N, num_heads]
            # Normalize to [-π, π] using sin
            phases = math.pi * torch.sin(phases)
            self._last_phases = phases.detach()

            with torch.no_grad():
                # Compute phase coherence (mean resultant length)
                z = torch.exp(1j * phases.float())
                R_k = torch.abs(z.mean(dim=1)).mean().item()
                metrics = {
                    'phase_coherence': R_k,
                    'phase_std': phases.std().item(),
                }
            return phases, metrics

    # Local implementation of WitnessArbitrator for Layer 9
    class WitnessArbitrator(nn.Module):
        """
        L9: Witness Arbitrator - Cross-domain attention arbitration.

        Performs domain arbitration based on consciousness/attention patterns.
        Does NOT look at words, only CONSTRAINTS.
        """
        def __init__(self, hidden_dim: int, state_dim: int = 32):
            super().__init__()
            self.hidden_dim = hidden_dim
            self.state_dim = state_dim
            self.witness_proj = nn.Linear(hidden_dim, state_dim, bias=False)
            self.witness_norm = nn.LayerNorm(state_dim)

        def forward(self, hidden_states: torch.Tensor) -> Tuple[torch.Tensor, Dict[str, float]]:
            """Perform witness arbitration on hidden states."""
            witnessed = self.witness_proj(hidden_states)  # [B, N, state_dim]
            witnessed = self.witness_norm(witnessed)

            with torch.no_grad():
                # Compute arbitration metrics
                state_mean = witnessed.mean(dim=[0, 1])
                metrics = {
                    'witness_activation': state_mean.abs().mean().item(),
                    'witness_variance': witnessed.var().item(),
                }
            return witnessed, metrics

    # Local implementation of SynthesisGate for Layer 11
    class SynthesisGate(nn.Module):
        """
        L11: Synthesis Gate - Final output integration and quality filter.

        Detects entropy collapse (stuttering) and filters low-quality outputs.
        """
        def __init__(self, hidden_dim: int):
            super().__init__()
            self.hidden_dim = hidden_dim
            self.gate_proj = nn.Linear(hidden_dim, hidden_dim)
            self.quality_proj = nn.Linear(hidden_dim, 1)

        def forward(self, hidden_states: torch.Tensor) -> Tuple[torch.Tensor, Dict[str, float]]:
            """Apply synthesis gate to hidden states."""
            gate = torch.sigmoid(self.gate_proj(hidden_states))
            quality = torch.sigmoid(self.quality_proj(hidden_states))
            gated = hidden_states * gate

            with torch.no_grad():
                metrics = {
                    'synthesis_gate_mean': gate.mean().item(),
                    'synthesis_quality': quality.mean().item(),
                }
            return gated, metrics


# =============================================================================
# LOCAL KOSHA SYSTEM IMPLEMENTATIONS (V10.3.4)
# =============================================================================
# Full Kosha (5-sheath) consciousness model with diagnostics

if not KOSHA_AVAILABLE:
    class KoshaShiftController(nn.Module):
        """
        Kosha steering controller - shifts state toward target consciousness layer.

        The 5 Koshas (consciousness sheaths):
        - MATERIAL (Annamaya): Physical grounding, syntax, data layer
        - VITAL (Pranamaya): Energy flow, momentum, activation patterns
        - MENTAL (Manomaya): Semantic meaning, pattern recognition
        - INTELLECTUAL (Vijnanamaya): Deep reasoning, wisdom patterns
        - BLISSFUL (Anandamaya): Unity, coherence, creative synthesis
        """

        def __init__(
            self,
            state_dim: int = 32,
            target_kosha: str = 'INTELLECTUAL',
            dampen_material: float = 0.5,
            boost_target: float = 0.4,
        ):
            super().__init__()
            self.state_dim = state_dim
            self.target_kosha = target_kosha
            self.dampen_material = dampen_material
            self.boost_target = boost_target

            # Kosha indices in 32D state [12:17]
            self.kosha_indices = {
                'MATERIAL': 12, 'VITAL': 13, 'MENTAL': 14,
                'INTELLECTUAL': 15, 'BLISSFUL': 16
            }

            # Learnable steering weights
            self.kosha_steering = nn.Parameter(torch.zeros(5))

        def get_kosha_activations(self, state: torch.Tensor) -> torch.Tensor:
            """Extract kosha activations from 32D state. Returns [B, 5]."""
            return state[:, 12:17]

        def get_dominant_kosha(self, state: torch.Tensor) -> Tuple[str, int]:
            """Return name and index of dominant kosha."""
            kosha_acts = self.get_kosha_activations(state)
            dominant_idx = kosha_acts.mean(dim=0).argmax().item()
            names = ['MATERIAL', 'VITAL', 'MENTAL', 'INTELLECTUAL', 'BLISSFUL']
            return names[dominant_idx], dominant_idx

        def escalate_to_intellect(self, state: torch.Tensor) -> torch.Tensor:
            """Shift state toward intellectual kosha for reasoning."""
            state = state.clone()
            # Dampen material layer
            state[:, 12] = state[:, 12] * (1 - self.dampen_material)
            # Boost intellectual layer
            state[:, 15] = state[:, 15] + self.boost_target
            return state

        def forward(
            self,
            state: torch.Tensor,
            target: str = None,
        ) -> Tuple[torch.Tensor, Dict[str, float]]:
            """
            Apply kosha steering to state.

            Args:
                state: [B, 32] Sovereign state
                target: Target kosha name (default: self.target_kosha)

            Returns:
                steered_state: [B, 32]
                metrics: dict with kosha diagnostics
            """
            target = target or self.target_kosha

            # Get current kosha activations
            kosha_acts = self.get_kosha_activations(state)

            with torch.no_grad():
                dominant_name, dominant_idx = self.get_dominant_kosha(state)
                metrics = {
                    'dominant_kosha': dominant_idx,
                    'kosha_material': kosha_acts[:, 0].mean().item(),
                    'kosha_vital': kosha_acts[:, 1].mean().item(),
                    'kosha_mental': kosha_acts[:, 2].mean().item(),
                    'kosha_intellectual': kosha_acts[:, 3].mean().item(),
                    'kosha_blissful': kosha_acts[:, 4].mean().item(),
                }

            # Apply steering based on target
            if target == 'INTELLECTUAL':
                steered_state = self.escalate_to_intellect(state)
            else:
                steered_state = state

            return steered_state, metrics

    class KoshaGyroscopicLoss(nn.Module):
        """
        Homeostatic self-regulation for Kosha balance.

        Implements harmonic pentad constraints to keep koshas in healthy ranges:
        - Floor/ceiling for each kosha prevents collapse/dominance
        - Three-stage logic: Bliss damper → Physical gate → Reality rip
        - Dynamic gain scheduling based on PPL
        """

        def __init__(
            self,
            # v2.3.0: Floor/Ceiling for each Kosha (harmonic pentad)
            floor_material: float = 0.382,
            ceiling_material: float = 0.618,
            floor_vital: float = 0.236,
            ceiling_vital: float = 0.786,
            floor_mental: float = 0.236,
            ceiling_mental: float = 0.382,
            floor_intellectual: float = 0.250,
            ceiling_intellectual: float = 0.618,
            floor_bliss: float = 0.236,
            ceiling_bliss: float = 0.618,
            # Dynamic gain scheduling
            base_gain: float = 0.15,
            max_gain: float = 3.0,
            ppl_ceiling: float = 100.0,
            target_ppl: float = 30.0,
        ):
            super().__init__()

            # Store floor/ceiling constraints
            self.floors = torch.tensor([
                floor_material, floor_vital, floor_mental,
                floor_intellectual, floor_bliss
            ])
            self.ceilings = torch.tensor([
                ceiling_material, ceiling_vital, ceiling_mental,
                ceiling_intellectual, ceiling_bliss
            ])

            # Gain scheduling
            self.base_gain = base_gain
            self.max_gain = max_gain
            self.ppl_ceiling = ppl_ceiling
            self.target_ppl = target_ppl

            # Current gain (updated by set_ppl)
            self.current_gain = base_gain

        def set_ppl(self, ppl: float):
            """Update gain based on current PPL."""
            # Linear interpolation from base_gain (high PPL) to max_gain (target PPL)
            if ppl >= self.ppl_ceiling:
                self.current_gain = self.base_gain
            elif ppl <= self.target_ppl:
                self.current_gain = self.max_gain
            else:
                t = (self.ppl_ceiling - ppl) / (self.ppl_ceiling - self.target_ppl)
                self.current_gain = self.base_gain + t * (self.max_gain - self.base_gain)

        def forward(
            self,
            kosha_activations: torch.Tensor,  # [B, 5]
        ) -> Tuple[torch.Tensor, Dict[str, float]]:
            """
            Compute gyroscopic loss to maintain kosha homeostasis.

            Returns:
                loss: scalar
                metrics: dict with violation counts
            """
            device = kosha_activations.device
            floors = self.floors.to(device)
            ceilings = self.ceilings.to(device)

            # Floor violations (kosha too low)
            floor_violations = F.relu(floors - kosha_activations)
            floor_loss = floor_violations.sum(dim=-1).mean()

            # Ceiling violations (kosha too high)
            ceiling_violations = F.relu(kosha_activations - ceilings)
            ceiling_loss = ceiling_violations.sum(dim=-1).mean()

            # Total loss with gain
            total_loss = self.current_gain * (floor_loss + ceiling_loss)

            with torch.no_grad():
                metrics = {
                    'kosha_floor_violations': (floor_violations > 0).sum().item(),
                    'kosha_ceiling_violations': (ceiling_violations > 0).sum().item(),
                    'kosha_gyro_loss': total_loss.item(),
                    'kosha_gyro_gain': self.current_gain,
                }

            return total_loss, metrics

    class KoshaPhaseCorrector(nn.Module):
        """
        Inference-time phase correction for Kosha stability.

        Applies direct phase rotation when a kosha becomes overactive,
        forcing re-grounding in the appropriate consciousness layer.
        """

        def __init__(
            self,
            overactive_threshold: float = 0.75,
            correction_strength: float = 0.3,
            max_correction_per_step: float = 0.2,
        ):
            super().__init__()
            self.overactive_threshold = overactive_threshold
            self.correction_strength = correction_strength
            self.max_correction_per_step = max_correction_per_step

        def forward(
            self,
            kosha_activations: torch.Tensor,  # [B, 5]
        ) -> Tuple[torch.Tensor, Dict[str, float]]:
            """
            Apply phase correction for overactive koshas.

            Returns:
                corrected: [B, 5] corrected activations
                metrics: dict with correction stats
            """
            # Detect overactive koshas
            overactive = kosha_activations > self.overactive_threshold

            # Apply correction (scale down overactive)
            correction = torch.where(
                overactive,
                kosha_activations * (1 - self.correction_strength),
                kosha_activations
            )

            # Clamp correction magnitude
            delta = (correction - kosha_activations).clamp(
                -self.max_correction_per_step,
                self.max_correction_per_step
            )
            corrected = kosha_activations + delta

            with torch.no_grad():
                metrics = {
                    'kosha_corrections': overactive.sum().item(),
                    'kosha_correction_magnitude': delta.abs().mean().item(),
                }

            return corrected, metrics


# =============================================================================
# KOSHA DIAGNOSTICS (V10.3.4)
# =============================================================================

class KoshaDiagnostics(nn.Module):
    """
    Full diagnostic tracking for the 5-layer Kosha consciousness model.

    Tracks:
    - Per-kosha activation levels over training
    - Kosha transitions (shifts between consciousness layers)
    - Homeostatic health (floor/ceiling violations)
    - Dominant kosha per layer

    Maps transformer layers to koshas:
    - L0-L2:  MATERIAL (Annamaya) - syntax, tokens
    - L3-L4:  VITAL (Pranamaya) - energy flow
    - L5-L6:  MENTAL (Manomaya) - semantics
    - L7-L8:  INTELLECTUAL (Vijnanamaya) - reasoning
    - L9+:    BLISSFUL (Anandamaya) - integration
    """

    def __init__(
        self,
        hidden_dim: int,
        num_layers: int,
        state_dim: int = 32,
        device: torch.device = None,
    ):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.state_dim = state_dim

        # Kosha projector: hidden → 5D kosha space
        self.kosha_projector = nn.Linear(hidden_dim, 5)

        # Kosha shift controller
        self.kosha_controller = KoshaShiftController(state_dim=state_dim)

        # Gyroscopic loss for homeostasis
        self.gyroscope = KoshaGyroscopicLoss()

        # Phase corrector
        self.corrector = KoshaPhaseCorrector()

        # History for trend analysis
        self.history = {
            'kosha_activations': [],  # List of [5] tensors
            'dominant_kosha': [],     # List of kosha names
            'gyro_loss': [],
            'transitions': [],        # (from_kosha, to_kosha, step)
        }

        self._last_dominant = None

        if device:
            self.to(device)

    def layer_to_expected_kosha(self, layer_idx: int) -> str:
        """Map layer index to expected dominant kosha."""
        if layer_idx <= 2:
            return 'MATERIAL'
        elif layer_idx <= 4:
            return 'VITAL'
        elif layer_idx <= 6:
            return 'MENTAL'
        elif layer_idx <= 8:
            return 'INTELLECTUAL'
        else:
            return 'BLISSFUL'

    def forward(
        self,
        hidden_states: torch.Tensor,  # [B, N, D]
        layer_idx: int,
        step: int = 0,
    ) -> Dict[str, float]:
        """
        Compute kosha diagnostics for a layer's hidden states.

        Returns dict with:
        - kosha_<name>: activation level for each kosha
        - dominant_kosha: index of dominant kosha
        - kosha_alignment: whether dominant matches expected for layer
        - gyro_loss: homeostatic loss value
        """
        # Project to kosha space
        kosha_acts = torch.sigmoid(self.kosha_projector(hidden_states))  # [B, N, 5]
        kosha_acts = kosha_acts.mean(dim=1)  # [B, 5] - average over sequence

        # Get dominant kosha
        dominant_idx = kosha_acts.mean(dim=0).argmax().item()
        kosha_names = ['MATERIAL', 'VITAL', 'MENTAL', 'INTELLECTUAL', 'BLISSFUL']
        dominant_name = kosha_names[dominant_idx]

        # Check alignment with expected
        expected = self.layer_to_expected_kosha(layer_idx)
        aligned = (dominant_name == expected)

        # Compute gyroscopic loss
        gyro_loss, gyro_metrics = self.gyroscope(kosha_acts)

        # Track transitions
        if self._last_dominant is not None and dominant_name != self._last_dominant:
            self.history['transitions'].append((self._last_dominant, dominant_name, step))
        self._last_dominant = dominant_name

        # Build metrics
        metrics = {
            'kosha_material': kosha_acts[:, 0].mean().item(),
            'kosha_vital': kosha_acts[:, 1].mean().item(),
            'kosha_mental': kosha_acts[:, 2].mean().item(),
            'kosha_intellectual': kosha_acts[:, 3].mean().item(),
            'kosha_blissful': kosha_acts[:, 4].mean().item(),
            'dominant_kosha': dominant_idx,
            'dominant_kosha_name': dominant_name,
            'expected_kosha': expected,
            'kosha_alignment': 1.0 if aligned else 0.0,
            'gyro_loss': gyro_loss.item(),
            **gyro_metrics,
        }

        # Store history
        self.history['kosha_activations'].append(
            kosha_acts.mean(dim=0).detach().cpu().tolist()
        )
        self.history['dominant_kosha'].append(dominant_name)
        self.history['gyro_loss'].append(gyro_loss.item())

        return metrics

    def get_summary(self) -> Dict[str, any]:
        """Get summary statistics over training history."""
        if not self.history['kosha_activations']:
            return {}

        # Convert to arrays
        acts = torch.tensor(self.history['kosha_activations'])  # [num_obs, 5]

        # Compute trends
        if len(acts) >= 2:
            early = acts[:len(acts)//2].mean(dim=0)
            late = acts[len(acts)//2:].mean(dim=0)
            trends = late - early
        else:
            trends = torch.zeros(5)

        # Count dominant kosha occurrences
        from collections import Counter
        dominant_counts = Counter(self.history['dominant_kosha'])

        # Std requires at least 2 samples
        std_activations = acts.std(dim=0).tolist() if len(acts) >= 2 else [0.0] * 5

        return {
            'mean_activations': acts.mean(dim=0).tolist(),
            'std_activations': std_activations,
            'trends': trends.tolist(),
            'dominant_counts': dict(dominant_counts),
            'num_transitions': len(self.history['transitions']),
            'transitions': self.history['transitions'][-10:],  # Last 10
            'mean_gyro_loss': sum(self.history['gyro_loss']) / max(1, len(self.history['gyro_loss'])),
        }

    def print_report(self, step: int):
        """Print formatted kosha diagnostics report."""
        summary = self.get_summary()
        if not summary:
            return

        kosha_names = ['MATERIAL', 'VITAL', 'MENTAL', 'INTELLECTUAL', 'BLISSFUL']
        vedic_names = ['Annamaya', 'Pranamaya', 'Manomaya', 'Vijnanamaya', 'Anandamaya']

        print(f"\n      ╔═══════════════════════════════════════════════════════════════════╗")
        print(f"      ║  KOSHA CONSCIOUSNESS DIAGNOSTICS @ Step {step:<6}                 ║")
        print(f"      ╠═══════════════════════════════════════════════════════════════════╣")
        print(f"      ║  Layer    Kosha (Sheath)      Activation   Trend    Status       ║")
        print(f"      ╠═══════════════════════════════════════════════════════════════════╣")

        means = summary['mean_activations']
        trends = summary['trends']

        for i, (name, vedic, mean, trend) in enumerate(zip(kosha_names, vedic_names, means, trends)):
            trend_symbol = "↑" if trend > 0.01 else ("↓" if trend < -0.01 else "→")
            health = "HEALTHY" if 0.2 < mean < 0.8 else ("LOW" if mean < 0.2 else "HIGH")
            health_symbol = "✓" if health == "HEALTHY" else "⚠️"
            print(f"      ║  {i:2}    {name:12} ({vedic:11})  {mean:5.3f}    {trend:+.3f}{trend_symbol}  {health} {health_symbol}  ║")

        print(f"      ╠═══════════════════════════════════════════════════════════════════╣")

        # Dominant kosha statistics
        counts = summary.get('dominant_counts', {})
        total = sum(counts.values()) or 1
        print(f"      ║  Dominant Kosha Distribution:                                     ║")
        for name in kosha_names:
            count = counts.get(name, 0)
            pct = 100 * count / total
            bar = "█" * int(pct / 5)
            print(f"      ║    {name:12}: {pct:5.1f}% {bar:<20}                  ║")

        print(f"      ╠═══════════════════════════════════════════════════════════════════╣")
        print(f"      ║  Transitions: {summary['num_transitions']}  |  Gyro Loss: {summary['mean_gyro_loss']:.4f}                  ║")
        print(f"      ╚═══════════════════════════════════════════════════════════════════╝")


# =============================================================================
# WITNESS DIAGNOSTICS (V10.3.4)
# =============================================================================

class WitnessDiagnostics(nn.Module):
    """
    Full diagnostic tracking for the Witness (Sakshi) observer system.

    The Witness observes thought patterns without attachment, detecting:
    - Domain arbitration (cross-domain reasoning quality)
    - Constraint identification (bottleneck detection)
    - Vritti status (epistemic reliability)
    - Meta-cognitive monitoring

    Vritti indices in 32D state [17:22]:
    - FACT: Verified truth
    - MISCONCEPTION: Believed but wrong
    - IMAGINATION: Creative/hypothetical
    - VOID: Unknown/uncertain
    - MEMORY: Retrieved from context
    """

    def __init__(
        self,
        hidden_dim: int,
        state_dim: int = 32,
        constraint_threshold: float = 0.85,
        device: torch.device = None,
    ):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.state_dim = state_dim
        self.constraint_threshold = constraint_threshold

        # Witness projector: hidden → state
        self.witness_projector = nn.Linear(hidden_dim, state_dim)

        # Vritti classifier: hidden → 5 epistemic states
        self.vritti_classifier = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 5),
            nn.Softmax(dim=-1),
        )

        # Constraint detector
        self.constraint_detector = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1),
            nn.Sigmoid(),
        )

        # Meta-cognitive confidence
        self.confidence_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 4),
            nn.ReLU(),
            nn.Linear(hidden_dim // 4, 1),
            nn.Sigmoid(),
        )

        # History
        self.history = {
            'vritti_distributions': [],
            'constraint_scores': [],
            'confidence_scores': [],
            'witness_states': [],
        }

        if device:
            self.to(device)

    def forward(
        self,
        hidden_states: torch.Tensor,  # [B, N, D]
        step: int = 0,
    ) -> Dict[str, float]:
        """
        Compute witness diagnostics for hidden states.

        Returns dict with:
        - vritti_<name>: probability for each epistemic state
        - constraint_score: bottleneck detection score
        - witness_confidence: meta-cognitive confidence
        - witness_activation: overall witness activity
        """
        B, N, D = hidden_states.shape

        # Average over sequence for diagnostics
        hidden_avg = hidden_states.mean(dim=1)  # [B, D]

        # Vritti classification
        vritti_probs = self.vritti_classifier(hidden_avg)  # [B, 5]

        # V10.3.7: Compute vritti entropy for regularization
        # Higher entropy = more balanced distribution across epistemic states
        eps = 1e-8
        vritti_entropy = -(vritti_probs * torch.log(vritti_probs + eps)).sum(dim=-1)  # [B]
        # Max entropy for 5 classes = log(5) ≈ 1.609
        max_entropy = torch.log(torch.tensor(5.0, device=vritti_probs.device))
        normalized_entropy = vritti_entropy / max_entropy  # [B], range [0, 1]

        # Store for loss computation (with gradient)
        self._last_vritti_probs = vritti_probs
        self._last_vritti_entropy = vritti_entropy

        # Constraint detection
        constraint_score = self.constraint_detector(hidden_avg)  # [B, 1]

        # Meta-cognitive confidence
        confidence = self.confidence_head(hidden_avg)  # [B, 1]

        # Witness state projection
        witness_state = self.witness_projector(hidden_avg)  # [B, 32]

        vritti_names = ['FACT', 'MISCONCEPTION', 'IMAGINATION', 'VOID', 'MEMORY']

        metrics = {
            'vritti_fact': vritti_probs[:, 0].mean().item(),
            'vritti_misconception': vritti_probs[:, 1].mean().item(),
            'vritti_imagination': vritti_probs[:, 2].mean().item(),
            'vritti_void': vritti_probs[:, 3].mean().item(),
            'vritti_memory': vritti_probs[:, 4].mean().item(),
            'dominant_vritti': vritti_probs.mean(dim=0).argmax().item(),
            'dominant_vritti_name': vritti_names[vritti_probs.mean(dim=0).argmax().item()],
            'constraint_score': constraint_score.mean().item(),
            'constraint_detected': (constraint_score > self.constraint_threshold).float().mean().item(),
            'witness_confidence': confidence.mean().item(),
            'witness_activation': witness_state.abs().mean().item(),
            # V10.3.7: Entropy metrics
            'vritti_entropy': vritti_entropy.mean().item(),
            'vritti_entropy_normalized': normalized_entropy.mean().item(),
        }

        # Store history
        self.history['vritti_distributions'].append(
            vritti_probs.mean(dim=0).detach().cpu().tolist()
        )
        self.history['constraint_scores'].append(constraint_score.mean().item())
        self.history['confidence_scores'].append(confidence.mean().item())

        return metrics

    def get_entropy_loss(self, lambda_entropy: float = 0.1) -> torch.Tensor:
        """
        V10.3.7: Compute entropy regularization loss to prevent vritti collapse.

        Returns negative entropy (to be added to loss, encouraging higher entropy).
        Higher entropy = more balanced distribution across 5 vritti states.

        Args:
            lambda_entropy: Weight for entropy regularization (default: 0.1)

        Returns:
            Entropy loss tensor (negative entropy scaled by lambda)
        """
        if not hasattr(self, '_last_vritti_entropy') or self._last_vritti_entropy is None:
            return torch.tensor(0.0)

        # We want to MAXIMIZE entropy, so we return NEGATIVE entropy
        # Adding this to loss will encourage higher entropy (more balanced distribution)
        entropy_loss = -lambda_entropy * self._last_vritti_entropy.mean()
        return entropy_loss

    def get_summary(self) -> Dict[str, any]:
        """Get summary statistics over training history."""
        if not self.history['vritti_distributions']:
            return {}

        vritti = torch.tensor(self.history['vritti_distributions'])  # [num_obs, 5]
        constraints = torch.tensor(self.history['constraint_scores'])
        confidences = torch.tensor(self.history['confidence_scores'])

        # Std requires at least 2 samples
        has_enough_samples = len(vritti) >= 2

        return {
            'mean_vritti': vritti.mean(dim=0).tolist(),
            'std_vritti': vritti.std(dim=0).tolist() if has_enough_samples else [0.0] * 5,
            'mean_constraint': constraints.mean().item(),
            'std_constraint': constraints.std().item() if has_enough_samples else 0.0,
            'mean_confidence': confidences.mean().item(),
            'std_confidence': confidences.std().item() if has_enough_samples else 0.0,
            'high_constraint_ratio': (constraints > self.constraint_threshold).float().mean().item(),
        }

    def print_report(self, step: int):
        """Print formatted witness diagnostics report."""
        summary = self.get_summary()
        if not summary:
            return

        vritti_names = ['FACT', 'MISCONCEPTION', 'IMAGINATION', 'VOID', 'MEMORY']

        print(f"\n      ╔═══════════════════════════════════════════════════════════════════╗")
        print(f"      ║  WITNESS (SAKSHI) OBSERVER DIAGNOSTICS @ Step {step:<6}            ║")
        print(f"      ╠═══════════════════════════════════════════════════════════════════╣")
        print(f"      ║  Vritti (Epistemic State)      Mean Prob   Std      Status        ║")
        print(f"      ╠═══════════════════════════════════════════════════════════════════╣")

        means = summary['mean_vritti']
        stds = summary['std_vritti']

        for i, (name, mean, std) in enumerate(zip(vritti_names, means, stds)):
            bar = "█" * int(mean * 20)
            dominant = "★" if mean == max(means) else " "
            print(f"      ║  {name:18}        {mean:5.3f}    {std:5.3f}    {bar:<12} {dominant}║")

        print(f"      ╠═══════════════════════════════════════════════════════════════════╣")
        print(f"      ║  Constraint Detection:                                            ║")
        print(f"      ║    Mean Score: {summary['mean_constraint']:.3f}  (threshold: {self.constraint_threshold})      ║")
        print(f"      ║    Detection Rate: {summary['high_constraint_ratio']*100:.1f}%                              ║")
        print(f"      ╠═══════════════════════════════════════════════════════════════════╣")
        print(f"      ║  Meta-Cognitive Confidence: {summary['mean_confidence']:.3f} ± {summary['std_confidence']:.3f}      ║")
        print(f"      ╚═══════════════════════════════════════════════════════════════════╝")


# =============================================================================
# SRK PHASE LEARNING MONITOR
# =============================================================================

class SRKPhaseLearningMonitor(nn.Module):
    """
    Monitors how phase learning progresses at different layers.

    Attaches SRK components at specified layers and tracks:
    - Phase coherence (R_k metric)
    - Ontological diversity (12D Bhava representation)
    - Layer-wise contributions to final output
    - Consciousness/attention patterns

    Usage:
        monitor = SRKPhaseLearningMonitor(config, hidden_dim, num_heads, device)
        metrics = monitor.observe(layer_hidden_states)  # List of [B, N, D] per layer
    """

    def __init__(
        self,
        config: SRKPhaseLearningConfig,
        hidden_dim: int,
        num_heads: int,
        device: torch.device,
    ):
        super().__init__()
        self.config = config
        self.hidden_dim = hidden_dim
        self.num_heads = num_heads

        # Create components
        if config.enable_dna_bridge:
            self.dna_bridge = OntologicalBridge(hidden_dim).to(device)
        else:
            self.dna_bridge = None

        if config.enable_phase_hook:
            self.phase_hook = PhaseExtractionHook(hidden_dim, num_heads).to(device)
        else:
            self.phase_hook = None

        if config.enable_witness:
            self.witness = WitnessArbitrator(hidden_dim, config.state_dim).to(device)
        else:
            self.witness = None

        if config.enable_synthesis:
            self.synthesis = SynthesisGate(hidden_dim).to(device)
        else:
            self.synthesis = None

        # Training history
        self.metrics_history = []

    def observe(
        self,
        layer_hidden_states: List[torch.Tensor],  # List of [B, N, D] per layer
    ) -> Dict[str, float]:
        """
        Observe phase learning at each SRK-monitored layer.

        Args:
            layer_hidden_states: Hidden states from each layer [B, N, D]

        Returns:
            Dictionary of metrics from all SRK components
        """
        metrics = {}
        num_layers = len(layer_hidden_states)

        # L4: DNA Bridge (if layer exists)
        if self.dna_bridge is not None and self.config.dna_bridge_layer < num_layers:
            h = layer_hidden_states[self.config.dna_bridge_layer]
            _, dna_metrics = self.dna_bridge(h)
            metrics.update({f'L{self.config.dna_bridge_layer}_dna_{k}': v for k, v in dna_metrics.items()})

        # L7: Phase Hook (if layer exists)
        if self.phase_hook is not None and self.config.csr_alignment_layer < num_layers:
            h = layer_hidden_states[self.config.csr_alignment_layer]
            _, phase_metrics = self.phase_hook(h)
            metrics.update({f'L{self.config.csr_alignment_layer}_csr_{k}': v for k, v in phase_metrics.items()})

        # L9: Witness Arbitrator (if layer exists)
        if self.witness is not None and self.config.witness_layer < num_layers:
            h = layer_hidden_states[self.config.witness_layer]
            _, witness_metrics = self.witness(h)
            metrics.update({f'L{self.config.witness_layer}_witness_{k}': v for k, v in witness_metrics.items()})

        # L11: Synthesis Gate (if layer exists)
        if self.synthesis is not None and self.config.synthesis_layer < num_layers:
            h = layer_hidden_states[self.config.synthesis_layer]
            _, synthesis_metrics = self.synthesis(h)
            metrics.update({f'L{self.config.synthesis_layer}_synth_{k}': v for k, v in synthesis_metrics.items()})

        # Track history for trend analysis
        self.metrics_history.append(metrics.copy())

        return metrics

    def get_phase_learning_summary(self) -> Dict[str, any]:
        """
        Generate a summary of phase learning progress.

        Returns trends and statistics across training.
        """
        if not self.metrics_history:
            return {}

        summary = {
            'num_observations': len(self.metrics_history),
        }

        # Compute trends for key metrics
        for key in self.metrics_history[-1].keys():
            values = [m.get(key, 0) for m in self.metrics_history]
            if values:
                summary[f'{key}_initial'] = values[0]
                summary[f'{key}_final'] = values[-1]
                summary[f'{key}_trend'] = values[-1] - values[0]  # Positive = increased

        return summary

    def print_phase_learning_report(self):
        """Print a formatted report of phase learning progress."""
        summary = self.get_phase_learning_summary()
        if not summary:
            print("  No SRK observations recorded yet.")
            return

        print("\n  ╔══════════════════════════════════════════════════════════════════╗")
        print("  ║  SRK PHASE LEARNING REPORT (V10.3.0)                             ║")
        print("  ╠══════════════════════════════════════════════════════════════════╣")
        print(f"  ║  Observations: {summary['num_observations']:>6}                                         ║")
        print("  ╠══════════════════════════════════════════════════════════════════╣")

        # Component reports
        if self.config.enable_dna_bridge:
            key_base = f'L{self.config.dna_bridge_layer}_dna_'
            div_trend = summary.get(f'{key_base}onto_diversity_trend', 0)
            print(f"  ║  L{self.config.dna_bridge_layer}: DNA Bridge (Ontology)                                    ║")
            print(f"  ║    Diversity trend: {div_trend:+.4f} ({'↑' if div_trend > 0 else '↓'})                            ║")

        if self.config.enable_phase_hook:
            key_base = f'L{self.config.csr_alignment_layer}_csr_'
            coh_trend = summary.get(f'{key_base}phase_coherence_trend', 0)
            print(f"  ║  L{self.config.csr_alignment_layer}: CSR Alignment (Phase Hook)                              ║")
            print(f"  ║    Coherence trend: {coh_trend:+.4f} ({'↑' if coh_trend > 0 else '↓'})                             ║")

        if self.config.enable_witness:
            key_base = f'L{self.config.witness_layer}_witness_'
            act_trend = summary.get(f'{key_base}witness_activation_trend', 0)
            print(f"  ║  L{self.config.witness_layer}: Witness Arbitrator (Consciousness)                        ║")
            print(f"  ║    Activation trend: {act_trend:+.4f} ({'↑' if act_trend > 0 else '↓'})                            ║")

        if self.config.enable_synthesis:
            key_base = f'L{self.config.synthesis_layer}_synth_'
            gate_trend = summary.get(f'{key_base}synthesis_gate_mean_trend', 0)
            print(f"  ║  L{self.config.synthesis_layer}: Synthesis Gate (Integration)                             ║")
            print(f"  ║    Gate mean trend: {gate_trend:+.4f} ({'↑' if gate_trend > 0 else '↓'})                             ║")

        print("  ╚══════════════════════════════════════════════════════════════════╝")


# =============================================================================
# V10.3.1: LAYER INFLUENCE DIAGNOSTICS
# =============================================================================
# Analyzes whether each SRK component layer influences phase learning
# CONSTRUCTIVELY (helps) or DESTRUCTIVELY (hurts)
#
# Influence Classification:
#   CONSTRUCTIVE (+): Component helps phase learning
#   NEUTRAL (○):      Component has minimal effect
#   DESTRUCTIVE (-):  Component hurts phase learning

class InfluenceType(Enum):
    """Classification of layer influence on phase learning."""
    CONSTRUCTIVE = "CONSTRUCTIVE"
    NEUTRAL = "NEUTRAL"
    DESTRUCTIVE = "DESTRUCTIVE"


@dataclass
class LayerInfluenceMetrics:
    """Metrics for a single layer's influence on phase learning."""
    layer_idx: int
    component_name: str
    influence_type: InfluenceType
    influence_score: float  # -1.0 (destructive) to +1.0 (constructive)

    # Detailed metrics
    phase_preservation: float  # How much phase signal is preserved (0-1)
    phase_amplification: float  # Phase signal amplification factor
    gradient_flow: float  # Gradient magnitude through this layer
    entropy_delta: float  # Change in representation entropy

    # Diagnostic flags
    causes_collapse: bool  # True if layer causes phase collapse
    causes_diffusion: bool  # True if layer diffuses phase signal
    is_bottleneck: bool  # True if layer blocks gradient flow

    def get_influence_symbol(self) -> str:
        """Get symbol for influence type."""
        if self.influence_type == InfluenceType.CONSTRUCTIVE:
            return "+"
        elif self.influence_type == InfluenceType.DESTRUCTIVE:
            return "-"
        else:
            return "○"

    def get_influence_bar(self, width: int = 20) -> str:
        """Get visual bar representation of influence score."""
        # Score ranges from -1 to +1, map to 0 to width
        normalized = (self.influence_score + 1) / 2  # 0 to 1
        filled = int(normalized * width)
        center = width // 2

        bar = ""
        for i in range(width):
            if i == center:
                bar += "│"
            elif i < center and i >= filled:
                bar += "◀" if filled < center else "─"
            elif i > center and i <= filled:
                bar += "▶" if filled > center else "─"
            elif i < filled and i < center:
                bar += "█"
            elif i > filled and i > center:
                bar += "░"
            else:
                bar += "░" if i < center else "░"

        return bar


class LayerInfluenceDiagnostics:
    """
    Diagnoses whether each SRK layer influences phase learning constructively
    or destructively.

    Constructive Influence (helps phase learning):
    - Increases phase coherence (R_k metric)
    - Maintains ontological diversity
    - Preserves phase signal through layer
    - Allows healthy gradient flow

    Destructive Influence (hurts phase learning):
    - Causes phase collapse (uniform phases)
    - Reduces ontological diversity
    - Diffuses or erases phase signal
    - Blocks gradient flow (vanishing gradients)

    Usage:
        diagnostics = LayerInfluenceDiagnostics(config)
        influence = diagnostics.analyze(
            layer_hidden_states,
            prev_metrics,
            curr_metrics
        )
    """

    def __init__(self, config: SRKPhaseLearningConfig):
        self.config = config

        # Thresholds for influence classification
        self.constructive_threshold = 0.2   # Score > 0.2 = constructive
        self.destructive_threshold = -0.2   # Score < -0.2 = destructive

        # Phase health thresholds
        self.collapse_threshold = 0.1       # R_k < 0.1 = collapsed
        self.diffusion_threshold = 0.95     # R_k > 0.95 = diffused (too uniform)
        self.gradient_threshold = 1e-6      # Gradient < this = blocked

        # History for trend analysis
        self.influence_history: List[Dict[int, LayerInfluenceMetrics]] = []

    def compute_phase_metrics(
        self,
        hidden_states: torch.Tensor,
        num_heads: int = 8,
    ) -> Dict[str, float]:
        """
        Compute phase-related metrics from hidden states.

        Returns metrics useful for influence analysis.
        """
        with torch.no_grad():
            B, N, D = hidden_states.shape

            # Compute pseudo-phase from hidden states
            # Using the first few dimensions as "phase-like" signal
            phase_dims = min(D, num_heads * 4)
            phase_signal = hidden_states[..., :phase_dims]

            # Phase coherence approximation (mean resultant length)
            # Treat normalized hidden states as unit vectors
            normalized = F.normalize(phase_signal, dim=-1)
            mean_vector = normalized.mean(dim=1)  # [B, phase_dims]
            coherence = torch.norm(mean_vector, dim=-1).mean().item()

            # Phase variance (spread of phase signal)
            phase_var = phase_signal.var(dim=-1).mean().item()

            # Entropy of hidden state distribution
            # Use softmax to get "probability-like" distribution
            probs = F.softmax(hidden_states.abs().mean(dim=1), dim=-1)  # [B, D]
            entropy = -(probs * torch.log(probs + 1e-10)).sum(dim=-1).mean().item()
            max_entropy = math.log(D)
            normalized_entropy = entropy / max_entropy

            # Signal magnitude
            signal_norm = hidden_states.norm(dim=-1).mean().item()

            return {
                'coherence': coherence,
                'phase_var': phase_var,
                'entropy': normalized_entropy,
                'signal_norm': signal_norm,
            }

    def analyze_layer_influence(
        self,
        layer_idx: int,
        component_name: str,
        input_hidden: torch.Tensor,
        output_hidden: torch.Tensor,
        num_heads: int = 8,
    ) -> LayerInfluenceMetrics:
        """
        Analyze influence of a single layer on phase learning.

        Compares input and output hidden states to determine if the layer
        is helping or hurting phase learning.
        """
        # Compute metrics before and after layer
        input_metrics = self.compute_phase_metrics(input_hidden, num_heads)
        output_metrics = self.compute_phase_metrics(output_hidden, num_heads)

        # Phase preservation: how much of input phase survives
        # Compare coherence before/after
        coherence_ratio = output_metrics['coherence'] / (input_metrics['coherence'] + 1e-6)
        phase_preservation = min(coherence_ratio, 2.0) / 2.0  # Clamp to [0, 1]

        # Phase amplification: ratio of signal norms
        amplification = output_metrics['signal_norm'] / (input_metrics['signal_norm'] + 1e-6)

        # Entropy delta: change in representation entropy
        entropy_delta = output_metrics['entropy'] - input_metrics['entropy']

        # Gradient flow approximation (using variance as proxy)
        var_ratio = output_metrics['phase_var'] / (input_metrics['phase_var'] + 1e-6)
        gradient_flow = min(var_ratio, 2.0) / 2.0

        # Detect problematic conditions
        causes_collapse = output_metrics['coherence'] < self.collapse_threshold
        causes_diffusion = output_metrics['coherence'] > self.diffusion_threshold
        is_bottleneck = gradient_flow < self.gradient_threshold

        # Compute influence score
        # Positive factors: preserves phase, maintains diversity, good gradient flow
        # Negative factors: collapses phase, reduces diversity, blocks gradients
        influence_score = 0.0

        # Phase preservation contribution (-0.5 to +0.5)
        influence_score += (phase_preservation - 0.5)

        # Entropy contribution: slight increase is good, large increase is bad
        if -0.1 < entropy_delta < 0.1:
            influence_score += 0.2  # Stable entropy is good
        elif entropy_delta > 0.3:
            influence_score -= 0.3  # Large entropy increase = diffusion
        elif entropy_delta < -0.3:
            influence_score -= 0.2  # Large entropy decrease = collapse

        # Gradient flow contribution
        if gradient_flow > 0.3:
            influence_score += 0.2
        elif gradient_flow < 0.1:
            influence_score -= 0.3

        # Penalty for collapse/diffusion
        if causes_collapse:
            influence_score -= 0.5
        if causes_diffusion:
            influence_score -= 0.2

        # Clamp to [-1, 1]
        influence_score = max(-1.0, min(1.0, influence_score))

        # Classify influence type
        if influence_score > self.constructive_threshold:
            influence_type = InfluenceType.CONSTRUCTIVE
        elif influence_score < self.destructive_threshold:
            influence_type = InfluenceType.DESTRUCTIVE
        else:
            influence_type = InfluenceType.NEUTRAL

        return LayerInfluenceMetrics(
            layer_idx=layer_idx,
            component_name=component_name,
            influence_type=influence_type,
            influence_score=influence_score,
            phase_preservation=phase_preservation,
            phase_amplification=amplification,
            gradient_flow=gradient_flow,
            entropy_delta=entropy_delta,
            causes_collapse=causes_collapse,
            causes_diffusion=causes_diffusion,
            is_bottleneck=is_bottleneck,
        )

    def analyze_all_layers(
        self,
        layer_hidden_states: List[torch.Tensor],
        num_heads: int = 8,
    ) -> Dict[int, LayerInfluenceMetrics]:
        """
        Analyze influence for all configured SRK layers.

        Args:
            layer_hidden_states: List of hidden states from each layer

        Returns:
            Dictionary mapping layer index to influence metrics
        """
        results = {}
        num_layers = len(layer_hidden_states)

        # Analyze DNA Bridge layer
        if self.config.enable_dna_bridge and self.config.dna_bridge_layer < num_layers:
            layer_idx = self.config.dna_bridge_layer
            input_h = layer_hidden_states[max(0, layer_idx - 1)] if layer_idx > 0 else layer_hidden_states[0]
            output_h = layer_hidden_states[layer_idx]
            results[layer_idx] = self.analyze_layer_influence(
                layer_idx, "DNA Bridge", input_h, output_h, num_heads
            )

        # Analyze CSR Alignment layer
        if self.config.enable_phase_hook and self.config.csr_alignment_layer < num_layers:
            layer_idx = self.config.csr_alignment_layer
            input_h = layer_hidden_states[max(0, layer_idx - 1)]
            output_h = layer_hidden_states[layer_idx]
            results[layer_idx] = self.analyze_layer_influence(
                layer_idx, "CSR Alignment", input_h, output_h, num_heads
            )

        # Analyze Witness Arbitrator layer
        if self.config.enable_witness and self.config.witness_layer < num_layers:
            layer_idx = self.config.witness_layer
            input_h = layer_hidden_states[max(0, layer_idx - 1)]
            output_h = layer_hidden_states[layer_idx]
            results[layer_idx] = self.analyze_layer_influence(
                layer_idx, "Witness Arbitrator", input_h, output_h, num_heads
            )

        # Analyze Synthesis Gate layer
        if self.config.enable_synthesis and self.config.synthesis_layer < num_layers:
            layer_idx = self.config.synthesis_layer
            input_h = layer_hidden_states[max(0, layer_idx - 1)]
            output_h = layer_hidden_states[layer_idx]
            results[layer_idx] = self.analyze_layer_influence(
                layer_idx, "Synthesis Gate", input_h, output_h, num_heads
            )

        # Store in history
        self.influence_history.append(results)

        return results

    def print_influence_report(
        self,
        influence_metrics: Dict[int, LayerInfluenceMetrics],
        step: int = 0,
    ):
        """Print formatted influence report for all layers."""
        print(f"\n      ╔══════════════════════════════════════════════════════════════════╗")
        print(f"      ║  SRK LAYER INFLUENCE DIAGNOSTICS @ Step {step:<6}                  ║")
        print(f"      ╠══════════════════════════════════════════════════════════════════╣")
        print(f"      ║  Layer  Component           Influence    Score   Flags          ║")
        print(f"      ╠══════════════════════════════════════════════════════════════════╣")

        for layer_idx in sorted(influence_metrics.keys()):
            m = influence_metrics[layer_idx]
            symbol = m.get_influence_symbol()

            # Build flags string
            flags = []
            if m.causes_collapse:
                flags.append("COLLAPSE")
            if m.causes_diffusion:
                flags.append("DIFFUSE")
            if m.is_bottleneck:
                flags.append("BLOCKED")
            flags_str = ",".join(flags) if flags else "OK"

            # Influence type with color indicator
            if m.influence_type == InfluenceType.CONSTRUCTIVE:
                inf_str = f"[{symbol}] CONSTRUCTIVE"
            elif m.influence_type == InfluenceType.DESTRUCTIVE:
                inf_str = f"[{symbol}] DESTRUCTIVE"
            else:
                inf_str = f"[{symbol}] NEUTRAL    "

            print(f"      ║  L{layer_idx:<4} {m.component_name:<18} {inf_str}  {m.influence_score:+.2f}   {flags_str:<14} ║")

        print(f"      ╠══════════════════════════════════════════════════════════════════╣")

        # Summary
        constructive = sum(1 for m in influence_metrics.values() if m.influence_type == InfluenceType.CONSTRUCTIVE)
        destructive = sum(1 for m in influence_metrics.values() if m.influence_type == InfluenceType.DESTRUCTIVE)
        neutral = sum(1 for m in influence_metrics.values() if m.influence_type == InfluenceType.NEUTRAL)

        total_score = sum(m.influence_score for m in influence_metrics.values())
        avg_score = total_score / len(influence_metrics) if influence_metrics else 0

        if avg_score > 0.1:
            overall = "CONSTRUCTIVE overall"
        elif avg_score < -0.1:
            overall = "DESTRUCTIVE overall"
        else:
            overall = "NEUTRAL overall"

        print(f"      ║  Summary: {constructive} constructive, {neutral} neutral, {destructive} destructive        ║")
        print(f"      ║  Average Score: {avg_score:+.3f} → {overall:<20}                  ║")
        print(f"      ╚══════════════════════════════════════════════════════════════════╝")

    def print_detailed_layer_report(
        self,
        influence_metrics: Dict[int, LayerInfluenceMetrics],
    ):
        """Print detailed per-layer breakdown."""
        print(f"\n      Detailed Layer Analysis:")
        print(f"      " + "-" * 60)

        for layer_idx in sorted(influence_metrics.keys()):
            m = influence_metrics[layer_idx]
            print(f"\n      L{layer_idx}: {m.component_name}")
            print(f"        Influence: {m.influence_type.value} (score: {m.influence_score:+.3f})")
            print(f"        Phase Preservation:  {m.phase_preservation:.3f} {'✓' if m.phase_preservation > 0.5 else '⚠️'}")
            print(f"        Phase Amplification: {m.phase_amplification:.3f}x")
            print(f"        Gradient Flow:       {m.gradient_flow:.3f} {'✓' if m.gradient_flow > 0.1 else '⚠️'}")
            print(f"        Entropy Delta:       {m.entropy_delta:+.3f}")

            # Interpretation
            if m.influence_type == InfluenceType.CONSTRUCTIVE:
                print(f"        → This layer HELPS phase learning")
                if m.phase_preservation > 0.7:
                    print(f"          Good phase preservation through layer")
                if m.gradient_flow > 0.3:
                    print(f"          Healthy gradient flow")
            elif m.influence_type == InfluenceType.DESTRUCTIVE:
                print(f"        → This layer HURTS phase learning")
                if m.causes_collapse:
                    print(f"          ⚠️ Causing phase collapse!")
                if m.causes_diffusion:
                    print(f"          ⚠️ Causing phase diffusion!")
                if m.is_bottleneck:
                    print(f"          ⚠️ Blocking gradient flow!")
            else:
                print(f"        → This layer has MINIMAL effect on phase")

    def get_influence_summary(self) -> Dict[str, any]:
        """Get summary of influence trends over training."""
        if not self.influence_history:
            return {}

        summary = {'num_observations': len(self.influence_history)}

        # Track per-layer trends
        for layer_idx in self.influence_history[-1].keys():
            scores = [h[layer_idx].influence_score for h in self.influence_history if layer_idx in h]
            if scores:
                summary[f'L{layer_idx}_score_initial'] = scores[0]
                summary[f'L{layer_idx}_score_final'] = scores[-1]
                summary[f'L{layer_idx}_score_trend'] = scores[-1] - scores[0]

                # Count influence type changes
                types = [h[layer_idx].influence_type for h in self.influence_history if layer_idx in h]
                summary[f'L{layer_idx}_constructive_pct'] = sum(1 for t in types if t == InfluenceType.CONSTRUCTIVE) / len(types)
                summary[f'L{layer_idx}_destructive_pct'] = sum(1 for t in types if t == InfluenceType.DESTRUCTIVE) / len(types)

        return summary


# =============================================================================
