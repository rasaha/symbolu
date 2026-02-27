"""
LSTB Anti-Collapse Objectives Benchmarks (V11.0)

Tests all anti-collapse training objectives from LSTB Section 5:
    1. VICReg (§5a): Variance-Invariance-Covariance regularization
    2. Contrastive Alignment (§5b): Paraphrase-based alignment
    3. InfoNCE (§5c): Mutual Information maximization
    4. Structured Supervision (§5d): Kosha/Vritti/Bhava loss
    5. Combined training: All losses together with curriculum

CLI Usage::

    python train_hard_probes.py --test-anti-collapse
    python train_hard_probes.py --test-anti-collapse --ac-ablation

References:
    - LATENT_SEMANTIC_TOKEN_BRIDGE_DESIGN.md §5a-§5d
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Optional, Tuple

try:
    from symbolu.jepa.state_projector import SovereignStateProjector
    from symbolu.jepa.losses import VICRegLoss, JEPAPredictionLoss
    JEPA_AVAILABLE = True
except ImportError:
    JEPA_AVAILABLE = False


# =============================================================================
# CONTRASTIVE ALIGNMENT LOSS (§5b)
# =============================================================================

class ContrastiveAlignmentLoss(nn.Module):
    """
    Contrastive alignment using paraphrase pairs.

    L = -log(exp(sim(z_i, z_j+)/τ) / Σ_k exp(sim(z_i, z_k-)/τ))

    Where z_j+ is from a paraphrase (same meaning, different tokens)
    and z_k- is from unrelated text.
    """

    def __init__(self, temperature: float = 0.07):
        super().__init__()
        self.temperature = temperature

    def forward(
        self,
        z_anchor: torch.Tensor,   # [B, D]
        z_positive: torch.Tensor,  # [B, D]
        z_negatives: torch.Tensor = None,  # [B, N, D] or None (use in-batch)
    ) -> torch.Tensor:
        # Normalize
        z_a = F.normalize(z_anchor, dim=-1)
        z_p = F.normalize(z_positive, dim=-1)

        # Positive similarity
        pos_sim = (z_a * z_p).sum(dim=-1) / self.temperature  # [B]

        if z_negatives is not None:
            z_n = F.normalize(z_negatives, dim=-1)
            neg_sim = torch.bmm(z_n, z_a.unsqueeze(-1)).squeeze(-1) / self.temperature  # [B, N]
            logits = torch.cat([pos_sim.unsqueeze(-1), neg_sim], dim=-1)  # [B, 1+N]
        else:
            # In-batch negatives
            sim_matrix = z_a @ z_p.T / self.temperature  # [B, B]
            logits = sim_matrix  # diagonal = positives

        # InfoNCE loss
        labels = torch.zeros(z_anchor.shape[0], dtype=torch.long, device=z_anchor.device)
        if z_negatives is not None:
            loss = F.cross_entropy(logits, labels)
        else:
            loss = F.cross_entropy(logits, torch.arange(z_anchor.shape[0], device=z_anchor.device))

        return loss


# =============================================================================
# INFONCE MUTUAL INFORMATION (§5c)
# =============================================================================

class InfoNCELoss(nn.Module):
    """
    Maximize mutual information between Sovereign State z and hidden state h.

    L_MI = -E[log(exp(f(z, h)) / Σ_j exp(f(z_j, h)))]

    This prevents the projection from discarding information.
    """

    def __init__(self, z_dim: int = 32, h_dim: int = 768, temperature: float = 0.1):
        super().__init__()
        self.temperature = temperature
        # Bilinear scoring function
        self.score_fn = nn.Bilinear(z_dim, h_dim, 1)

    def forward(
        self,
        z: torch.Tensor,  # [B, D_z] sovereign states
        h: torch.Tensor,  # [B, D_h] hidden states
    ) -> torch.Tensor:
        B = z.shape[0]

        # Compute scores for all pairs
        # f(z_i, h_j) for all i, j
        z_expand = z.unsqueeze(1).expand(-1, B, -1)  # [B, B, D_z]
        h_expand = h.unsqueeze(0).expand(B, -1, -1)  # [B, B, D_h]

        scores = self.score_fn(
            z_expand.reshape(-1, z.shape[-1]),
            h_expand.reshape(-1, h.shape[-1]),
        ).reshape(B, B) / self.temperature  # [B, B]

        # Diagonal elements are positive pairs
        labels = torch.arange(B, device=z.device)
        loss = F.cross_entropy(scores, labels)

        return loss


# =============================================================================
# STRUCTURED SUPERVISION LOSS (§5d)
# =============================================================================

class StructuredSupervisionLoss(nn.Module):
    """
    Structured supervision that anchors Sovereign State dimensions to meaning.

    L_structured = KL(z_kosha || kosha_target) + KL(z_vritti || vritti_target)
                 + CE(z_bhava, bhava_label)

    This provides both anti-collapse AND interpretability in one loss.
    """

    def __init__(
        self,
        kosha_weight: float = 1.0,
        vritti_weight: float = 1.0,
        bhava_weight: float = 0.5,
    ):
        super().__init__()
        self.kosha_weight = kosha_weight
        self.vritti_weight = vritti_weight
        self.bhava_weight = bhava_weight

    def forward(
        self,
        z: torch.Tensor,                    # [B, 32] sovereign state
        kosha_target: torch.Tensor = None,   # [B, 5] soft labels
        vritti_target: torch.Tensor = None,  # [B, 5] soft labels
        bhava_label: torch.Tensor = None,    # [B] class index
    ) -> Dict[str, torch.Tensor]:
        losses = {}
        total = torch.tensor(0.0, device=z.device)

        if kosha_target is not None:
            kosha_pred = F.softmax(z[:, 12:17], dim=-1)
            kl_kosha = F.kl_div(
                kosha_pred.log(), kosha_target, reduction='batchmean'
            )
            losses['kosha_kl'] = kl_kosha
            total = total + self.kosha_weight * kl_kosha

        if vritti_target is not None:
            vritti_pred = F.softmax(z[:, 17:22], dim=-1)
            kl_vritti = F.kl_div(
                vritti_pred.log(), vritti_target, reduction='batchmean'
            )
            losses['vritti_kl'] = kl_vritti
            total = total + self.vritti_weight * kl_vritti

        if bhava_label is not None:
            bhava_logits = z[:, 0:12]
            ce_bhava = F.cross_entropy(bhava_logits, bhava_label)
            losses['bhava_ce'] = ce_bhava
            total = total + self.bhava_weight * ce_bhava

        losses['total'] = total
        return losses


# =============================================================================
# TESTS
# =============================================================================

def test_vicreg_collapse_modes(device: torch.device) -> Dict[str, float]:
    """Test VICReg against different collapse modes."""
    vicreg = VICRegLoss() if JEPA_AVAILABLE else None
    D = 32
    B = 64
    results = {}

    def compute_vicreg(x, y):
        if vicreg is not None:
            return vicreg(x, y, return_components=True)
        # Fallback
        repr_loss = F.mse_loss(x, y)
        std_x = torch.sqrt(x.var(dim=0) + 1e-4)
        std_y = torch.sqrt(y.var(dim=0) + 1e-4)
        std_loss = (F.relu(1.0 - std_x).mean() + F.relu(1.0 - std_y).mean()) / 2
        x_c = x - x.mean(dim=0)
        cov_x = (x_c.T @ x_c) / (B - 1)
        cov_loss = cov_x.flatten()[:-1].view(D - 1, D + 1)[:, 1:].flatten().pow(2).sum() / D
        return {'total': repr_loss + 25 * std_loss + cov_loss,
                'invariance': repr_loss, 'variance': std_loss, 'covariance': cov_loss}

    # Mode 1: Point collapse (all representations same)
    x_collapsed = torch.ones(B, D, device=device) * 0.5
    y_normal = torch.randn(B, D, device=device)
    loss_collapsed = compute_vicreg(x_collapsed, y_normal)
    results['point_collapse_variance'] = loss_collapsed['variance'].item()
    results['point_collapse_total'] = loss_collapsed['total'].item()

    # Mode 2: Dimensional collapse (some dims constant)
    x_dim_collapse = torch.randn(B, D, device=device)
    x_dim_collapse[:, :16] = 0.5  # Half the dims collapsed
    loss_dim = compute_vicreg(x_dim_collapse, y_normal)
    results['dim_collapse_variance'] = loss_dim['variance'].item()

    # Mode 3: Correlated dimensions
    x_correlated = torch.randn(B, 1, device=device).expand(-1, D) + torch.randn(B, D, device=device) * 0.1
    loss_corr = compute_vicreg(x_correlated, y_normal)
    results['correlated_covariance'] = loss_corr['covariance'].item()

    # Mode 4: Healthy (diverse, decorrelated)
    x_healthy = torch.randn(B, D, device=device)
    y_healthy = x_healthy + torch.randn(B, D, device=device) * 0.1
    loss_healthy = compute_vicreg(x_healthy, y_healthy)
    results['healthy_total'] = loss_healthy['total'].item()
    results['healthy_variance'] = loss_healthy['variance'].item()
    results['healthy_covariance'] = loss_healthy['covariance'].item()

    # Verify detection
    results['point_collapse_detected'] = loss_collapsed['variance'].item() > loss_healthy['variance'].item()
    results['correlation_detected'] = loss_corr['covariance'].item() > loss_healthy['covariance'].item()

    return results


def test_contrastive_alignment(device: torch.device) -> Dict[str, float]:
    """Test contrastive alignment with synthetic paraphrases."""
    loss_fn = ContrastiveAlignmentLoss(temperature=0.07)
    D = 32
    B = 16
    results = {}

    # Positive pairs (paraphrases -> similar states)
    z_anchor = torch.randn(B, D, device=device)
    z_positive = z_anchor + torch.randn(B, D, device=device) * 0.1  # Similar
    z_negative = torch.randn(B, D, device=device)  # Random/different

    # Loss with real positive pairs
    loss_pos = loss_fn(z_anchor, z_positive)
    results['loss_positive_pairs'] = loss_pos.item()

    # Loss with random "positive" pairs (should be higher)
    loss_rand = loss_fn(z_anchor, z_negative)
    results['loss_random_pairs'] = loss_rand.item()

    # Positive pairs should have lower loss
    results['contrastive_discriminates'] = loss_pos.item() < loss_rand.item()

    # Gradient flows
    z_a = z_anchor.clone().requires_grad_(True)
    z_p = z_positive.clone().requires_grad_(True)
    loss = loss_fn(z_a, z_p)
    loss.backward()
    results['gradient_flows'] = z_a.grad is not None and z_a.grad.norm().item() > 0

    return results


def test_infonce(device: torch.device) -> Dict[str, float]:
    """Test InfoNCE mutual information maximization."""
    z_dim, h_dim = 32, 256  # Use smaller h_dim for testing
    B = 16

    loss_fn = InfoNCELoss(z_dim=z_dim, h_dim=h_dim).to(device)
    results = {}

    # Matched pairs (z_i corresponds to h_i)
    h = torch.randn(B, h_dim, device=device)
    # z = projection of h (strong mutual information)
    proj = nn.Linear(h_dim, z_dim).to(device)
    with torch.no_grad():
        z_matched = proj(h)

    loss_matched = loss_fn(z_matched, h)
    results['loss_matched'] = loss_matched.item()

    # Random pairs (z_i has no relation to h_i)
    z_random = torch.randn(B, z_dim, device=device)
    loss_random = loss_fn(z_random, h)
    results['loss_random'] = loss_random.item()

    # Matched should have lower loss (higher MI)
    results['infonce_discriminates'] = loss_matched.item() < loss_random.item()

    # Baseline: log(B) for random pairing
    results['baseline_loss'] = math.log(B)

    return results


def test_structured_supervision(device: torch.device) -> Dict[str, float]:
    """Test structured supervision loss."""
    loss_fn = StructuredSupervisionLoss()
    B = 16
    results = {}

    # Create sovereign states
    z = torch.randn(B, 32, device=device)

    # Create targets
    kosha_target = F.softmax(torch.randn(B, 5, device=device), dim=-1)
    vritti_target = F.softmax(torch.randn(B, 5, device=device), dim=-1)
    bhava_label = torch.randint(0, 12, (B,), device=device)

    # Full loss
    loss_full = loss_fn(z, kosha_target, vritti_target, bhava_label)
    results['loss_total'] = loss_full['total'].item()
    results['loss_kosha'] = loss_full['kosha_kl'].item()
    results['loss_vritti'] = loss_full['vritti_kl'].item()
    results['loss_bhava'] = loss_full['bhava_ce'].item()

    # Partial losses
    loss_kosha_only = loss_fn(z, kosha_target=kosha_target)
    loss_vritti_only = loss_fn(z, vritti_target=vritti_target)

    results['kosha_only_loss'] = loss_kosha_only['total'].item()
    results['vritti_only_loss'] = loss_vritti_only['total'].item()

    # Check that aligned state has lower loss
    z_aligned = z.clone()
    z_aligned[:, 12:17] = kosha_target  # Perfect kosha alignment
    loss_aligned = loss_fn(z_aligned, kosha_target=kosha_target)
    results['aligned_kosha_loss'] = loss_aligned['kosha_kl'].item()
    results['alignment_reduces_loss'] = loss_aligned['kosha_kl'].item() < loss_full['kosha_kl'].item()

    return results


def test_combined_training(device: torch.device, num_steps: int = 100) -> Dict[str, float]:
    """Test all anti-collapse losses combined in a training loop."""
    hidden_dim = 256
    B, T = 8, 16
    D = 32

    # Model
    projector = SovereignStateProjector(hidden_dim=hidden_dim, state_dim=D).to(device) if JEPA_AVAILABLE else nn.Sequential(
        nn.Linear(hidden_dim, hidden_dim // 2), nn.GELU(), nn.Linear(hidden_dim // 2, D)
    ).to(device)

    # Losses
    vicreg = VICRegLoss() if JEPA_AVAILABLE else None
    contrastive = ContrastiveAlignmentLoss()
    infonce = InfoNCELoss(z_dim=D, h_dim=hidden_dim).to(device)
    structured = StructuredSupervisionLoss()

    optimizer = torch.optim.AdamW(
        list(projector.parameters()) + list(infonce.parameters()),
        lr=1e-3,
    )

    results = {'losses': []}

    for step in range(num_steps):
        # Generate data
        h = torch.randn(B, hidden_dim, device=device)
        h_paraphrase = h + torch.randn_like(h) * 0.1

        # Project
        z = projector(h) if not isinstance(projector, nn.Sequential) else projector(h)
        z_para = projector(h_paraphrase) if not isinstance(projector, nn.Sequential) else projector(h_paraphrase)

        # VICReg
        l_vicreg = vicreg(z, z_para) if vicreg else F.mse_loss(z, z_para)

        # Contrastive
        l_contrastive = contrastive(z, z_para)

        # InfoNCE
        l_infonce = infonce(z, h)

        # Structured (with synthetic targets)
        kosha_t = F.softmax(torch.randn(B, 5, device=device), dim=-1)
        l_structured = structured(z, kosha_target=kosha_t)['total']

        # Combined
        loss = 0.5 * l_vicreg + 0.3 * l_contrastive + 0.1 * l_infonce + 0.1 * l_structured

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        results['losses'].append(loss.item())

    results['initial_loss'] = results['losses'][0]
    results['final_loss'] = results['losses'][-1]
    results['loss_decreased'] = results['losses'][-1] < results['losses'][0]
    results['loss_reduction_ratio'] = results['losses'][0] / (results['losses'][-1] + 1e-8)

    # Check representation health after training
    with torch.no_grad():
        h_test = torch.randn(64, hidden_dim, device=device)
        z_test = projector(h_test) if not isinstance(projector, nn.Sequential) else projector(h_test)
        per_dim_std = z_test.std(dim=0)
        results['post_train_min_std'] = per_dim_std.min().item()
        results['post_train_mean_std'] = per_dim_std.mean().item()
        results['post_train_collapsed_dims'] = (per_dim_std < 0.01).sum().item()

    del results['losses']
    return results


# =============================================================================
# MAIN BENCHMARK RUNNER
# =============================================================================

def run_anti_collapse_benchmarks(
    args,
    config,
    device: str,
) -> Dict[str, any]:
    """Run all anti-collapse objective benchmarks."""
    print("\n" + "=" * 70)
    print("V11.0: ANTI-COLLAPSE OBJECTIVES BENCHMARKS")
    print("=" * 70)

    device = torch.device(device)
    results = {}

    # TEST 1: VICReg
    print("\n--- TEST 1: VICReg Collapse Mode Detection ---")
    vicreg_results = test_vicreg_collapse_modes(device)
    results['vicreg'] = vicreg_results
    print(f"  Point collapse variance loss: {vicreg_results['point_collapse_variance']:.4f}")
    print(f"  Healthy variance loss: {vicreg_results['healthy_variance']:.4f}")
    print(f"  Point collapse detected: {vicreg_results['point_collapse_detected']}")
    print(f"  Correlation detected: {vicreg_results['correlation_detected']}")

    # TEST 2: Contrastive
    print("\n--- TEST 2: Contrastive Alignment ---")
    contrastive_results = test_contrastive_alignment(device)
    results['contrastive'] = contrastive_results
    print(f"  Positive pair loss: {contrastive_results['loss_positive_pairs']:.4f}")
    print(f"  Random pair loss: {contrastive_results['loss_random_pairs']:.4f}")
    print(f"  Discriminates: {contrastive_results['contrastive_discriminates']}")

    # TEST 3: InfoNCE
    print("\n--- TEST 3: InfoNCE Mutual Information ---")
    infonce_results = test_infonce(device)
    results['infonce'] = infonce_results
    print(f"  Matched loss: {infonce_results['loss_matched']:.4f}")
    print(f"  Random loss: {infonce_results['loss_random']:.4f}")
    print(f"  Baseline (log B): {infonce_results['baseline_loss']:.4f}")
    print(f"  Discriminates: {infonce_results['infonce_discriminates']}")

    # TEST 4: Structured Supervision
    print("\n--- TEST 4: Structured Supervision ---")
    structured_results = test_structured_supervision(device)
    results['structured'] = structured_results
    print(f"  Total loss: {structured_results['loss_total']:.4f}")
    print(f"  Kosha KL: {structured_results['loss_kosha']:.4f}")
    print(f"  Vritti KL: {structured_results['loss_vritti']:.4f}")
    print(f"  Bhava CE: {structured_results['loss_bhava']:.4f}")
    print(f"  Alignment reduces loss: {structured_results['alignment_reduces_loss']}")

    # TEST 5: Combined Training
    print("\n--- TEST 5: Combined Training Loop ---")
    num_steps = getattr(args, 'ac_train_steps', 100)
    combined_results = test_combined_training(device, num_steps=num_steps)
    results['combined'] = combined_results
    print(f"  Initial loss: {combined_results['initial_loss']:.4f}")
    print(f"  Final loss: {combined_results['final_loss']:.4f}")
    print(f"  Loss decreased: {combined_results['loss_decreased']}")
    print(f"  Reduction ratio: {combined_results['loss_reduction_ratio']:.2f}x")
    print(f"  Post-train min std: {combined_results['post_train_min_std']:.4f}")
    print(f"  Collapsed dims: {combined_results['post_train_collapsed_dims']}")

    # SUMMARY
    print("\n" + "=" * 70)
    print("ANTI-COLLAPSE BENCHMARK SUMMARY")
    print("=" * 70)
    all_pass = all([
        vicreg_results['point_collapse_detected'],
        vicreg_results['correlation_detected'],
        contrastive_results['contrastive_discriminates'],
        infonce_results['infonce_discriminates'],
        structured_results['alignment_reduces_loss'],
        combined_results['loss_decreased'],
    ])
    print(f"  All detection tests pass: {all_pass}")
    print(f"  Combined training healthy: {combined_results['post_train_collapsed_dims'] == 0}")

    return results


def run_anti_collapse_benchmark_integration(args, config):
    """CLI routing wrapper."""
    device = getattr(args, 'device', 'cuda' if torch.cuda.is_available() else 'cpu')
    results = run_anti_collapse_benchmarks(args, config, device)
    print("\n" + "=" * 70)
    print("BENCHMARK COMPLETE")
    print("=" * 70)
    return results
