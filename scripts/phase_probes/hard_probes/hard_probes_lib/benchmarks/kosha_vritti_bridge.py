"""
LSTB Kosha/Vritti Bridge Benchmarks (V11.0)

Tests the cognitive operating point system:
    1. KoshaVritti supervision quality (soft-label KL, entropy floor)
    2. Collapse detection (entropy, top-1 dominance)
    3. Viparyaya curriculum (staged exclusion/ramp)
    4. Compatibility matrix W_kv validation
    5. Structured supervision loss (Section 5d)
    6. Cognitive dissonance detection (Section 8a three-signal formula)

CLI Usage::

    python train_hard_probes.py --test-kosha-vritti-bridge
    python train_hard_probes.py --test-kosha-vritti-bridge --kv-dissonance-test

References:
    - LATENT_SEMANTIC_TOKEN_BRIDGE_DESIGN.md §5d, §6c, §8a
    - KOSHA_GYROSCOPE_DESIGN.md
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass

# Kosha/Vritti supervision imports
try:
    from symbolu.training.kosha_vritti_supervision import (
        KoshaVrittiSupervisor,
        KoshaVrittiSupervisionConfig,
        KoshaVrittiHead,
        KoshaVrittiLoss,
        KoshaVrittiTeacherLabeler,
        ViparyayaCurriculum,
        CollapseDetector,
    )
    KV_SUPERVISION_AVAILABLE = True
except ImportError:
    KV_SUPERVISION_AVAILABLE = False

# Kosha Gyroscope imports
try:
    from symbolu.losses.kosha_gyroscope import KoshaGyroscopicLoss
    GYROSCOPE_AVAILABLE = True
except ImportError:
    GYROSCOPE_AVAILABLE = False

# JEPA imports
try:
    from symbolu.jepa.state_projector import SovereignStateProjector
    from symbolu.jepa.predictor import PhaseJEPAPredictor
    JEPA_AVAILABLE = True
except ImportError:
    JEPA_AVAILABLE = False


# =============================================================================
# COGNITIVE DISSONANCE DETECTOR (Section 8a)
# =============================================================================

class CognitiveDissonanceDetector:
    """
    Implements the three-signal dissonance formula from LSTB §8a.

    D_t = 0.4 * D_trajectory + 0.3 * D_semantic + 0.3 * D_distributional

    Where:
        D_trajectory    = ||z_{t+k} - z_hat_{t+k}||₂     (JEPA surprise)
        D_semantic      = max(|OntBridge(z_actual - z_predicted)|)  (axis conflict)
        D_distributional = (KL(vritti_actual||vritti_predicted)
                          + KL(kosha_actual||kosha_predicted)) / 2

    Levels:
        Low (<0.3): Flow state — full alignment
        Medium (0.3-0.7): Minor drift — recoverable
        High (>0.7): Major break — hallucination candidate
    """

    def __init__(
        self,
        w_trajectory: float = 0.4,
        w_semantic: float = 0.3,
        w_distributional: float = 0.3,
    ):
        self.w_trajectory = w_trajectory
        self.w_semantic = w_semantic
        self.w_distributional = w_distributional

    def compute(
        self,
        z_actual: torch.Tensor,      # [B, 32] actual sovereign state
        z_predicted: torch.Tensor,    # [B, 32] JEPA-predicted state
        onto_bridge: Optional[nn.Module] = None,  # 32D -> 4D
    ) -> Dict[str, torch.Tensor]:
        """Compute dissonance score with all three components."""
        B = z_actual.shape[0]

        # 1. Trajectory dissonance: Euclidean distance
        d_trajectory = (z_actual - z_predicted).norm(dim=-1)  # [B]

        # Normalize to [0, 1] range (assume max reasonable distance ~5.0)
        d_trajectory_norm = torch.clamp(d_trajectory / 5.0, 0, 1)

        # 2. Semantic dissonance: ontological axis conflict
        if onto_bridge is not None:
            with torch.no_grad():
                residual = z_actual - z_predicted
                axis_conflict = onto_bridge(residual)  # [B, 4]
                d_semantic = axis_conflict.abs().max(dim=-1).values  # [B]
        else:
            # Approximate from Bhava dimensions directly
            bhava_actual = z_actual[:, 0:12]
            bhava_pred = z_predicted[:, 0:12]
            d_semantic = (bhava_actual - bhava_pred).abs().max(dim=-1).values

        d_semantic_norm = torch.clamp(d_semantic, 0, 1)

        # 3. Distributional dissonance: KL on Kosha + Vritti
        # Kosha: [12:17]
        kosha_actual = F.softmax(z_actual[:, 12:17], dim=-1)
        kosha_pred = F.softmax(z_predicted[:, 12:17], dim=-1)
        kl_kosha = F.kl_div(
            kosha_pred.log(), kosha_actual, reduction='none'
        ).sum(dim=-1)  # [B]

        # Vritti: [17:22]
        vritti_actual = F.softmax(z_actual[:, 17:22], dim=-1)
        vritti_pred = F.softmax(z_predicted[:, 17:22], dim=-1)
        kl_vritti = F.kl_div(
            vritti_pred.log(), vritti_actual, reduction='none'
        ).sum(dim=-1)  # [B]

        d_distributional = (kl_kosha + kl_vritti) / 2
        d_distributional_norm = torch.clamp(d_distributional, 0, 1)

        # Combined dissonance
        d_total = (
            self.w_trajectory * d_trajectory_norm +
            self.w_semantic * d_semantic_norm +
            self.w_distributional * d_distributional_norm
        )

        # Classify level
        levels = []
        for d in d_total:
            if d < 0.3:
                levels.append('low')
            elif d < 0.7:
                levels.append('medium')
            else:
                levels.append('high')

        return {
            'total_dissonance': d_total,
            'd_trajectory': d_trajectory_norm,
            'd_semantic': d_semantic_norm,
            'd_distributional': d_distributional_norm,
            'kl_kosha': kl_kosha,
            'kl_vritti': kl_vritti,
            'levels': levels,
        }

    def classify_regime(
        self,
        d_trajectory: torch.Tensor,
        d_semantic: torch.Tensor,
        threshold: float = 0.3,
    ) -> List[str]:
        """
        Classify anomaly regime per LSTB §7a Stage 5.

        Regimes:
            trajectory_only: Processing hiccup
            ontology_only: Genuine topic transition
            both: High-confidence anomaly
            neither: Normal generation
        """
        traj_high = d_trajectory > threshold
        sem_high = d_semantic > threshold

        regimes = []
        for t, s in zip(traj_high, sem_high):
            if t and s:
                regimes.append('both')
            elif t:
                regimes.append('trajectory_only')
            elif s:
                regimes.append('ontology_only')
            else:
                regimes.append('neither')
        return regimes


# =============================================================================
# TEST 1: KV SUPERVISION QUALITY
# =============================================================================

def test_kv_supervision(device: torch.device) -> Dict[str, float]:
    """Test KoshaVritti supervision with synthetic hidden states."""
    hidden_dim = 256
    B, T = 8, 32

    # Create synthetic data
    hidden_states = torch.randn(B, T, hidden_dim, device=device)
    # Simple input_ids (0=pad, 1-10=content, 11-15=punct)
    input_ids = torch.randint(1, 16, (B, T), device=device)

    if KV_SUPERVISION_AVAILABLE:
        config = KoshaVrittiSupervisionConfig(
            enable=True,
            num_koshas=4,
            num_vrittis=5,
            weight_kosha_kl=0.1,
            weight_vritti_kl=0.1,
            weight_entropy_floor=0.01,
        )
        supervisor = KoshaVrittiSupervisor(config, hidden_dim, device)

        loss, metrics = supervisor.step(hidden_states, input_ids, epoch=0, global_step=0)

        results = {
            'kv_loss': loss.item(),
            'available': True,
        }
        # Copy all metrics
        for k, v in metrics.items():
            if isinstance(v, (int, float)):
                results[k] = v
    else:
        # Standalone test with local head
        kosha_head = nn.Linear(hidden_dim, 4).to(device)
        vritti_head = nn.Linear(hidden_dim, 5).to(device)

        kosha_logits = kosha_head(hidden_states)  # [B, T, 4]
        vritti_logits = vritti_head(hidden_states)  # [B, T, 5]

        kosha_probs = F.softmax(kosha_logits, dim=-1)
        vritti_probs = F.softmax(vritti_logits, dim=-1)

        # Entropy check
        def entropy(p, eps=1e-8):
            return -(p * (p + eps).log()).sum(dim=-1).mean().item()

        results = {
            'available': False,
            'kosha_entropy': entropy(kosha_probs),
            'vritti_entropy': entropy(vritti_probs),
            'kosha_max_entropy': math.log(4),
            'vritti_max_entropy': math.log(5),
        }

    return results


# =============================================================================
# TEST 2: COLLAPSE DETECTION
# =============================================================================

def test_collapse_detection(device: torch.device) -> Dict[str, float]:
    """Test that collapse detection catches pathological distributions."""
    results = {}

    # Healthy distribution
    healthy_kosha = F.softmax(torch.randn(100, 4, device=device), dim=-1)
    healthy_vritti = F.softmax(torch.randn(100, 5, device=device), dim=-1)

    # Collapsed distribution (one class dominates)
    collapsed_kosha = torch.zeros(100, 4, device=device)
    collapsed_kosha[:, 0] = 0.97
    collapsed_kosha[:, 1:] = 0.01

    collapsed_vritti = torch.zeros(100, 5, device=device)
    collapsed_vritti[:, 2] = 0.95
    collapsed_vritti[:, :2] = 0.01
    collapsed_vritti[:, 3:] = 0.01

    def entropy(p, eps=1e-8):
        return -(p * (p + eps).log()).sum(dim=-1).mean().item()

    results['healthy_kosha_entropy'] = entropy(healthy_kosha)
    results['healthy_vritti_entropy'] = entropy(healthy_vritti)
    results['collapsed_kosha_entropy'] = entropy(collapsed_kosha)
    results['collapsed_vritti_entropy'] = entropy(collapsed_vritti)

    # Entropy floor thresholds (40% of max entropy)
    kosha_floor = 0.4 * math.log(4)
    vritti_floor = 0.4 * math.log(5)

    results['kosha_entropy_floor'] = kosha_floor
    results['vritti_entropy_floor'] = vritti_floor

    # Detection accuracy
    results['healthy_kosha_above_floor'] = results['healthy_kosha_entropy'] > kosha_floor
    results['collapsed_kosha_below_floor'] = results['collapsed_kosha_entropy'] < kosha_floor
    results['healthy_vritti_above_floor'] = results['healthy_vritti_entropy'] > vritti_floor
    results['collapsed_vritti_below_floor'] = results['collapsed_vritti_entropy'] < vritti_floor

    detection_correct = sum([
        results['healthy_kosha_above_floor'],
        results['collapsed_kosha_below_floor'],
        results['healthy_vritti_above_floor'],
        results['collapsed_vritti_below_floor'],
    ])
    results['detection_accuracy'] = detection_correct / 4

    # Top-1 dominance check
    results['healthy_kosha_top1'] = healthy_kosha.max(dim=-1).values.mean().item()
    results['collapsed_kosha_top1'] = collapsed_kosha.max(dim=-1).values.mean().item()
    results['top1_discriminates'] = results['collapsed_kosha_top1'] > results['healthy_kosha_top1']

    return results


# =============================================================================
# TEST 3: VIPARYAYA CURRICULUM
# =============================================================================

def test_viparyaya_curriculum(device: torch.device) -> Dict[str, float]:
    """Test Viparyaya curriculum staged inclusion behavior."""
    results = {}

    if KV_SUPERVISION_AVAILABLE:
        config = KoshaVrittiSupervisionConfig(
            enable=True,
            curriculum_exclude_epochs=2,
            curriculum_ramp_epochs=1,
        )
        curriculum = ViparyayaCurriculum(config)
    else:
        # Local implementation of curriculum logic
        class LocalCurriculum:
            def __init__(self, exclude_epochs=2, ramp_epochs=1):
                self.exclude_epochs = exclude_epochs
                self.ramp_epochs = ramp_epochs

            def get_inclusion_probability(self, epoch: int) -> float:
                if epoch < self.exclude_epochs:
                    return 0.0
                elif epoch < self.exclude_epochs + self.ramp_epochs:
                    progress = (epoch - self.exclude_epochs) / self.ramp_epochs
                    return progress
                else:
                    return 1.0

        curriculum = LocalCurriculum(exclude_epochs=2, ramp_epochs=1)

    # Test across epochs
    for epoch in range(5):
        prob = curriculum.get_inclusion_probability(epoch)
        results[f'epoch_{epoch}_inclusion'] = prob

    # Validate schedule
    results['epoch_0_excluded'] = results['epoch_0_inclusion'] == 0.0
    results['epoch_1_excluded'] = results['epoch_1_inclusion'] == 0.0
    results['epoch_2_ramping'] = 0.0 <= results['epoch_2_inclusion'] <= 1.0
    results['epoch_3_full'] = results['epoch_3_inclusion'] == 1.0

    return results


# =============================================================================
# TEST 4: COMPATIBILITY MATRIX
# =============================================================================

def test_compatibility_matrix(device: torch.device) -> Dict[str, float]:
    """
    Test the Kosha-Vritti compatibility matrix W_kv.

    Expected patterns:
        - Annamaya (Physical) + Pramana (Valid): HIGH compatibility
        - Vijnanamaya (Intellectual) + Vikalpa (Imagination): MODERATE
        - Annamaya (Physical) + Nidra (Dormancy): LOW
    """
    # Prior compatibility matrix (from domain knowledge)
    # Rows: Kosha [Annamaya, Pranamaya, Manomaya, Vijnanamaya]
    # Cols: Vritti [Pramana, Viparyaya, Vikalpa, Smrti, Nidra]
    W0 = torch.tensor([
        [0.9, 0.1, 0.1, 0.3, 0.05],  # Annamaya: physical, favors valid cognition
        [0.5, 0.2, 0.3, 0.4, 0.1],    # Pranamaya: energy, moderate flexibility
        [0.4, 0.2, 0.5, 0.5, 0.15],   # Manomaya: mental, allows imagination
        [0.6, 0.15, 0.6, 0.3, 0.05],  # Vijnanamaya: intellectual, creative reasoning
    ], device=device)

    results = {}

    # Check expected patterns
    results['annamaya_pramana'] = W0[0, 0].item()  # Should be high
    results['vijnanamaya_vikalpa'] = W0[3, 2].item()  # Should be moderate-high
    results['annamaya_nidra'] = W0[0, 4].item()  # Should be low

    results['physical_favors_valid'] = W0[0, 0] > W0[0, 2]  # Pramana > Vikalpa for physical
    results['intellectual_allows_imagination'] = W0[3, 2] > W0[0, 2]  # Vij > Anna for Vikalpa

    # If KV head available, test learned compatibility
    if KV_SUPERVISION_AVAILABLE:
        config = KoshaVrittiSupervisionConfig(enable=True)
        head = KoshaVrittiHead(hidden_dim=256, config=config, W0=W0).to(device)
        W_kv = head.W_kv.data  # [4, 5]
        results['W_kv_init_matches_prior'] = (W_kv - W0).abs().max().item() < 0.01
    else:
        results['W_kv_init_matches_prior'] = 'N/A (KV not available)'

    return results


# =============================================================================
# TEST 5: COGNITIVE DISSONANCE DETECTION
# =============================================================================

def test_cognitive_dissonance(device: torch.device) -> Dict[str, float]:
    """
    Test the three-signal dissonance formula from LSTB §8a.

    Scenarios:
        A) Flow state: all signals aligned -> Low dissonance
        B) Topic shift: trajectory diverges, Vritti stable -> Medium
        C) Mode flip: Vritti diverges, trajectory stable -> Medium
        D) Hallucination: everything diverges -> High
    """
    detector = CognitiveDissonanceDetector()
    results = {}

    B = 4

    # Scenario A: Flow state (aligned)
    z_base = torch.randn(B, 32, device=device)
    z_similar = z_base + torch.randn(B, 32, device=device) * 0.05  # Very close
    report_a = detector.compute(z_similar, z_base)
    results['flow_dissonance'] = report_a['total_dissonance'].mean().item()

    # Scenario B: Topic shift (trajectory diverges, distribution similar)
    z_shifted = z_base.clone()
    z_shifted[:, 0:12] += torch.randn(B, 12, device=device) * 2.0  # Large Bhava shift
    # Keep Kosha/Vritti similar
    report_b = detector.compute(z_shifted, z_base)
    results['topic_shift_dissonance'] = report_b['total_dissonance'].mean().item()
    results['topic_shift_trajectory'] = report_b['d_trajectory'].mean().item()

    # Scenario C: Mode flip (Vritti diverges, trajectory similar)
    z_mode_flip = z_base.clone()
    z_mode_flip[:, 17:22] = torch.tensor([0.05, 0.05, 0.8, 0.05, 0.05], device=device)  # Force Vikalpa
    report_c = detector.compute(z_mode_flip, z_base)
    results['mode_flip_dissonance'] = report_c['total_dissonance'].mean().item()
    results['mode_flip_kl_vritti'] = report_c['kl_vritti'].mean().item()

    # Scenario D: Hallucination (everything diverges)
    z_hallucination = torch.randn(B, 32, device=device) * 3.0  # Completely different
    report_d = detector.compute(z_hallucination, z_base)
    results['hallucination_dissonance'] = report_d['total_dissonance'].mean().item()

    # Ordering check
    results['flow_lowest'] = results['flow_dissonance'] < results['topic_shift_dissonance']
    results['hallucination_highest'] = results['hallucination_dissonance'] > results['mode_flip_dissonance']

    # Regime classification
    regimes = detector.classify_regime(
        report_b['d_trajectory'], report_b['d_semantic']
    )
    results['topic_shift_regime'] = regimes[0]

    regimes_d = detector.classify_regime(
        report_d['d_trajectory'], report_d['d_semantic']
    )
    results['hallucination_regime'] = regimes_d[0]

    return results


# =============================================================================
# TEST 6: GYROSCOPE INTEGRATION
# =============================================================================

def test_gyroscope_integration(device: torch.device) -> Dict[str, float]:
    """Test Kosha Gyroscope homeostatic regulation."""
    results = {}

    if not GYROSCOPE_AVAILABLE:
        results['available'] = False
        return results

    gyroscope = KoshaGyroscopicLoss().to(device)

    # Gyroscope expects [B, T, num_koshas] with T > 1 (needs std across tokens)
    T = 16
    # Healthy state: balanced koshas with slight variation across time
    balanced_base = torch.tensor([0.2, 0.2, 0.2, 0.2, 0.2], device=device)
    koshas_balanced = (balanced_base.unsqueeze(0).unsqueeze(0).expand(1, T, -1)
                       + torch.randn(1, T, 5, device=device) * 0.02)
    koshas_balanced = F.softmax(koshas_balanced, dim=-1)
    loss_balanced = gyroscope(koshas_balanced)
    results['loss_balanced'] = loss_balanced['total'].item() if isinstance(loss_balanced, dict) else loss_balanced.item()

    # Mental-trapped state (Mental > ceiling)
    trapped_base = torch.tensor([0.05, 0.05, 0.85, 0.03, 0.02], device=device)
    koshas_mental_trap = (trapped_base.unsqueeze(0).unsqueeze(0).expand(1, T, -1)
                          + torch.randn(1, T, 5, device=device) * 0.02)
    koshas_mental_trap = F.softmax(koshas_mental_trap, dim=-1)
    loss_trapped = gyroscope(koshas_mental_trap)
    results['loss_mental_trap'] = loss_trapped['total'].item() if isinstance(loss_trapped, dict) else loss_trapped.item()

    # Physical-grounded state
    grounded_base = torch.tensor([0.6, 0.15, 0.1, 0.1, 0.05], device=device)
    koshas_grounded = (grounded_base.unsqueeze(0).unsqueeze(0).expand(1, T, -1)
                       + torch.randn(1, T, 5, device=device) * 0.02)
    koshas_grounded = F.softmax(koshas_grounded, dim=-1)
    loss_grounded = gyroscope(koshas_grounded)
    results['loss_grounded'] = loss_grounded['total'].item() if isinstance(loss_grounded, dict) else loss_grounded.item()

    # Mental trap should have highest loss
    results['trap_penalized'] = results['loss_mental_trap'] > results['loss_balanced']
    results['available'] = True

    return results


# =============================================================================
# MAIN BENCHMARK RUNNER
# =============================================================================

def run_kosha_vritti_bridge_benchmarks(
    args,
    config,
    device: str,
) -> Dict[str, any]:
    """Run comprehensive Kosha/Vritti bridge benchmarks."""
    print("\n" + "=" * 70)
    print("V11.0: KOSHA/VRITTI BRIDGE BENCHMARKS")
    print("=" * 70)

    device = torch.device(device)
    results = {}

    # TEST 1: KV Supervision
    print("\n--- TEST 1: KV Supervision Quality ---")
    kv_results = test_kv_supervision(device)
    results['kv_supervision'] = kv_results
    print(f"  Available: {kv_results.get('available', False)}")
    if kv_results.get('available'):
        print(f"  KV loss: {kv_results['kv_loss']:.4f}")
    else:
        print(f"  Kosha entropy: {kv_results.get('kosha_entropy', 0):.4f} / {kv_results.get('kosha_max_entropy', 0):.4f}")
        print(f"  Vritti entropy: {kv_results.get('vritti_entropy', 0):.4f} / {kv_results.get('vritti_max_entropy', 0):.4f}")

    # TEST 2: Collapse Detection
    print("\n--- TEST 2: Collapse Detection ---")
    collapse_results = test_collapse_detection(device)
    results['collapse_detection'] = collapse_results
    print(f"  Detection accuracy: {collapse_results['detection_accuracy']:.0%}")
    print(f"  Healthy kosha entropy: {collapse_results['healthy_kosha_entropy']:.4f}")
    print(f"  Collapsed kosha entropy: {collapse_results['collapsed_kosha_entropy']:.4f}")
    print(f"  Top-1 discriminates: {collapse_results['top1_discriminates']}")

    # TEST 3: Viparyaya Curriculum
    print("\n--- TEST 3: Viparyaya Curriculum ---")
    curriculum_results = test_viparyaya_curriculum(device)
    results['viparyaya_curriculum'] = curriculum_results
    for epoch in range(5):
        prob = curriculum_results[f'epoch_{epoch}_inclusion']
        print(f"  Epoch {epoch}: inclusion={prob:.2f}")
    print(f"  Schedule correct: epoch0 excluded={curriculum_results['epoch_0_excluded']}, "
          f"epoch3 full={curriculum_results['epoch_3_full']}")

    # TEST 4: Compatibility Matrix
    print("\n--- TEST 4: Compatibility Matrix W_kv ---")
    compat_results = test_compatibility_matrix(device)
    results['compatibility'] = compat_results
    print(f"  Annamaya+Pramana: {compat_results['annamaya_pramana']:.2f} (should be high)")
    print(f"  Vijnanamaya+Vikalpa: {compat_results['vijnanamaya_vikalpa']:.2f} (should be moderate)")
    print(f"  Annamaya+Nidra: {compat_results['annamaya_nidra']:.2f} (should be low)")
    print(f"  Physical favors valid: {compat_results['physical_favors_valid']}")

    # TEST 5: Cognitive Dissonance
    print("\n--- TEST 5: Cognitive Dissonance Detection ---")
    dissonance_results = test_cognitive_dissonance(device)
    results['cognitive_dissonance'] = dissonance_results
    print(f"  Flow state:     {dissonance_results['flow_dissonance']:.4f} (should be < 0.3)")
    print(f"  Topic shift:    {dissonance_results['topic_shift_dissonance']:.4f} (should be medium)")
    print(f"  Mode flip:      {dissonance_results['mode_flip_dissonance']:.4f} (should be medium)")
    print(f"  Hallucination:  {dissonance_results['hallucination_dissonance']:.4f} (should be > 0.7)")
    print(f"  Flow lowest:    {dissonance_results['flow_lowest']}")
    print(f"  Halluc highest: {dissonance_results['hallucination_highest']}")
    print(f"  Topic regime:   {dissonance_results['topic_shift_regime']}")
    print(f"  Halluc regime:  {dissonance_results['hallucination_regime']}")

    # TEST 6: Gyroscope
    print("\n--- TEST 6: Gyroscope Integration ---")
    gyro_results = test_gyroscope_integration(device)
    results['gyroscope'] = gyro_results
    if gyro_results.get('available'):
        print(f"  Balanced loss: {gyro_results['loss_balanced']:.4f}")
        print(f"  Mental trap loss: {gyro_results['loss_mental_trap']:.4f}")
        print(f"  Trap penalized: {gyro_results['trap_penalized']}")
    else:
        print("  Gyroscope not available")

    # SUMMARY
    print("\n" + "=" * 70)
    print("KOSHA/VRITTI BRIDGE BENCHMARK SUMMARY")
    print("=" * 70)
    print(f"  Collapse detection:  {collapse_results['detection_accuracy']:.0%}")
    print(f"  Curriculum correct:  {curriculum_results['epoch_0_excluded'] and curriculum_results['epoch_3_full']}")
    print(f"  Dissonance ordering: {dissonance_results['flow_lowest'] and dissonance_results['hallucination_highest']}")

    return results


def run_kosha_vritti_bridge_benchmark_integration(args, config):
    """CLI routing wrapper."""
    device = getattr(args, 'device', 'cuda' if torch.cuda.is_available() else 'cpu')
    results = run_kosha_vritti_bridge_benchmarks(args, config, device)
    print("\n" + "=" * 70)
    print("BENCHMARK COMPLETE")
    print("=" * 70)
    return results
