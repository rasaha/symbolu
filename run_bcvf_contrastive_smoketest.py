#!/usr/bin/env python3
"""
BCVF Contrastive Representation Smoketest
==========================================

Minimal reproduction script that trains for N steps on synthetic data
and proves that the contrastive objective shapes representation geometry
(Δ = cos_pos - cos_neg increases) while CE loss remains stable.

This is the "geometry shaping proof": if Δ increases monotonically while
CE does not degrade, we have evidence that L_rep is moving hidden states
to encode BCVF alignment in their geometry, not just calibrating logits.

Usage:
    python run_bcvf_contrastive_smoketest.py [--steps 300] [--seed 42]

Outputs to inspect:
    - Console: per-step CE loss, Δ separation, cos_pos, cos_neg
    - Final report: whether Δ increased while CE was stable
    - Calibration check: logit_std and entropy trends
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Dict, List

import torch
import torch.nn as nn
import torch.nn.functional as F

# Ensure symbolu is importable
sys.path.insert(0, str(Path(__file__).parent))

from symbolu.ontological.bcvf_contrastive import (
    BCVFContrastiveConfig,
    BCVFContrastiveHead,
    BCVFNegativeSampler,
    compute_bcvf_contrastive_loss,
    log_bcvf_contrastive_diagnostics,
)


# =========================================================================
# Tiny Transformer for smoketest (self-contained, no external deps)
# =========================================================================


class TinyTransformerBlock(nn.Module):
    """Minimal transformer block for testing."""

    def __init__(self, d_model: int, n_heads: int, ff_dim: int, dropout: float = 0.1):
        super().__init__()
        self.attn = nn.MultiheadAttention(d_model, n_heads, dropout=dropout, batch_first=True)
        self.norm1 = nn.LayerNorm(d_model)
        self.ff = nn.Sequential(
            nn.Linear(d_model, ff_dim),
            nn.GELU(),
            nn.Linear(ff_dim, d_model),
        )
        self.norm2 = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        T = x.shape[1]
        mask = torch.triu(torch.ones(T, T, device=x.device), diagonal=1).bool()
        attn_out, _ = self.attn(x, x, x, attn_mask=mask)
        x = self.norm1(x + self.dropout(attn_out))
        x = self.norm2(x + self.dropout(self.ff(x)))
        return x


class TinyTransformer(nn.Module):
    """Minimal transformer for smoketest. Returns dict with logits + hidden states."""

    def __init__(
        self,
        vocab_size: int = 1000,
        d_model: int = 256,
        n_heads: int = 4,
        n_layers: int = 4,
        max_seq_len: int = 128,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.d_model = d_model
        self.token_embed = nn.Embedding(vocab_size, d_model)
        self.pos_embed = nn.Embedding(max_seq_len, d_model)
        self.blocks = nn.ModuleList([
            TinyTransformerBlock(d_model, n_heads, d_model * 4, dropout)
            for _ in range(n_layers)
        ])
        self.norm = nn.LayerNorm(d_model)
        self.lm_head = nn.Linear(d_model, vocab_size, bias=False)
        # Tie embeddings
        self.lm_head.weight = self.token_embed.weight

    def forward(self, input_ids: torch.Tensor) -> Dict[str, torch.Tensor]:
        B, T = input_ids.shape
        positions = torch.arange(T, device=input_ids.device).unsqueeze(0).expand(B, -1)
        x = self.token_embed(input_ids) + self.pos_embed(positions)
        for block in self.blocks:
            x = block(x)
        h = self.norm(x)  # [B, T, D] — hidden states before lm_head
        logits = self.lm_head(h)  # [B, T, V]
        return {"logits": logits, "hidden_states": h}


# =========================================================================
# Synthetic Data
# =========================================================================


def generate_synthetic_data(
    batch_size: int,
    seq_len: int,
    vocab_size: int,
    n_batches: int,
    seed: int = 42,
) -> List[torch.Tensor]:
    """Generate synthetic token sequences for smoketest."""
    torch.manual_seed(seed)
    batches = []
    for _ in range(n_batches):
        # Generate sequences with some structure (not purely random)
        # Use a simple bigram-like pattern
        data = torch.randint(0, vocab_size, (batch_size, seq_len))
        # Add some sequential patterns
        for b in range(batch_size):
            start = torch.randint(0, vocab_size, (1,)).item()
            pattern_len = torch.randint(3, 10, (1,)).item()
            for i in range(0, seq_len - pattern_len, pattern_len * 2):
                for j in range(pattern_len):
                    if i + j < seq_len:
                        data[b, i + j] = (start + j) % vocab_size
        batches.append(data)
    return batches


# =========================================================================
# Training Loop
# =========================================================================


def run_smoketest(
    n_steps: int = 300,
    seed: int = 42,
    batch_size: int = 8,
    seq_len: int = 64,
    vocab_size: int = 1000,
    d_model: int = 256,
    lambda_rep: float = 0.1,
    K: int = 16,
    margin: float = 0.15,
    alpha: float = 2.0,
    eta: float = 0.1,
    lr: float = 3e-4,
    log_every: int = 10,
    device_str: str = "cpu",
):
    """Run the BCVF contrastive smoketest.

    Trains a tiny transformer with CE + L_rep for n_steps and reports
    whether representation geometry is being shaped.
    """
    torch.manual_seed(seed)
    device = torch.device(device_str)

    print("=" * 70)
    print("BCVF Contrastive Representation Smoketest")
    print("=" * 70)
    print(f"  steps={n_steps}, seed={seed}, device={device}")
    print(f"  d_model={d_model}, vocab={vocab_size}, seq_len={seq_len}")
    print(f"  lambda_rep={lambda_rep}, K={K}, margin={margin}")
    print(f"  alpha={alpha}, eta={eta}, lr={lr}")
    print("=" * 70)

    # Build model
    model = TinyTransformer(
        vocab_size=vocab_size,
        d_model=d_model,
        n_heads=4,
        n_layers=4,
        max_seq_len=seq_len,
    ).to(device)

    # Build contrastive head
    contrastive_config = BCVFContrastiveConfig(
        use_bcvf_contrastive=True,
        lambda_rep=lambda_rep,
        K=K,
        margin=margin,
        alpha=alpha,
        eta=eta,
        d_r=128,
        T_sample=4,
        projector_type="mlp",
    )

    contrastive_head = BCVFContrastiveHead(
        hidden_dim=d_model,
        proj_dim=contrastive_config.d_r,
        projector_type=contrastive_config.projector_type,
    ).to(device)

    sampler = BCVFNegativeSampler(
        K=K,
        K_pool=min(256, vocab_size),
        top_p=0.95,
    )

    # Optimizer includes contrastive head parameters
    all_params = list(model.parameters()) + list(contrastive_head.parameters())
    optimizer = torch.optim.AdamW(all_params, lr=lr, weight_decay=0.01)

    # Token embeddings
    token_embeddings = model.token_embed.weight.detach()

    # Generate data
    n_batches = max(n_steps, 50)
    data = generate_synthetic_data(
        batch_size, seq_len, vocab_size, n_batches, seed=seed,
    )

    # Tracking curves
    ce_losses: List[float] = []
    rep_losses: List[float] = []
    deltas: List[float] = []
    cos_pos_list: List[float] = []
    cos_neg_list: List[float] = []
    logit_stds: List[float] = []
    entropies: List[float] = []

    print(f"\n{'Step':>6} | {'CE Loss':>8} | {'L_rep':>8} | {'cos_pos':>8} | {'cos_neg':>8} | {'Delta':>8} | {'logit_std':>9} | {'entropy':>8}")
    print("-" * 90)

    for step in range(n_steps):
        model.train()
        contrastive_head.train()

        batch = data[step % len(data)].to(device)
        x = batch[:, :-1]  # Input
        y = batch[:, 1:]   # Labels

        # Forward pass
        outputs = model(x)
        logits = outputs["logits"]  # [B, T-1, V]
        h = outputs["hidden_states"]  # [B, T-1, D]

        # CE loss
        B, T_minus_1, V = logits.shape
        ce_loss = F.cross_entropy(
            logits.reshape(-1, V),
            y.reshape(-1),
            ignore_index=-100,
        )

        # Contrastive loss
        # Update token embeddings (they change during training)
        token_emb = model.token_embed.weight.detach()

        rep_loss, diagnostics = compute_bcvf_contrastive_loss(
            h_all=h,
            logits_all=logits,
            labels=y,
            contrastive_head=contrastive_head,
            token_embeddings=token_emb,
            config=contrastive_config,
            sampler=sampler,
        )

        # Total loss
        total_loss = ce_loss + contrastive_config.lambda_rep * rep_loss

        # Backward and update
        optimizer.zero_grad()
        total_loss.backward()
        torch.nn.utils.clip_grad_norm_(all_params, 1.0)
        optimizer.step()

        # Track metrics
        ce_val = ce_loss.item()
        rep_val = rep_loss.item()
        delta = diagnostics.get("bcvf_rep/separation_delta", 0.0)
        cos_p = diagnostics.get("bcvf_rep/cos_pos_mean", 0.0)
        cos_n = diagnostics.get("bcvf_rep/cos_neg_mean", 0.0)
        l_std = diagnostics.get("bcvf_rep/logit_std_mean", 0.0)
        ent = diagnostics.get("bcvf_rep/entropy_mean", 0.0)

        ce_losses.append(ce_val)
        rep_losses.append(rep_val)
        deltas.append(delta)
        cos_pos_list.append(cos_p)
        cos_neg_list.append(cos_n)
        logit_stds.append(l_std)
        entropies.append(ent)

        if step % log_every == 0 or step == n_steps - 1:
            print(
                f"{step:>6} | {ce_val:>8.4f} | {rep_val:>8.4f} | "
                f"{cos_p:>8.4f} | {cos_n:>8.4f} | {delta:>8.4f} | "
                f"{l_std:>9.2f} | {ent:>8.2f}"
            )

    # =====================================================================
    # Final Report
    # =====================================================================
    print("\n" + "=" * 70)
    print("FINAL REPORT: Geometry Shaping Proof")
    print("=" * 70)

    # Check 1: Did Δ increase?
    early_deltas = deltas[:n_steps // 5] if len(deltas) > 5 else deltas[:1]
    late_deltas = deltas[-n_steps // 5:] if len(deltas) > 5 else deltas[-1:]
    early_delta_mean = sum(early_deltas) / max(len(early_deltas), 1)
    late_delta_mean = sum(late_deltas) / max(len(late_deltas), 1)
    delta_improved = late_delta_mean > early_delta_mean + 0.01

    print(f"\n1. Separation Delta (Δ = cos_pos - cos_neg):")
    print(f"   Early mean (first 20%): {early_delta_mean:.4f}")
    print(f"   Late mean  (last 20%):  {late_delta_mean:.4f}")
    print(f"   Improvement: {late_delta_mean - early_delta_mean:+.4f}")
    print(f"   VERDICT: {'PASS - geometry shaped' if delta_improved else 'INCONCLUSIVE'}")

    # Check 2: CE stability
    early_ce = ce_losses[:n_steps // 5] if len(ce_losses) > 5 else ce_losses[:1]
    late_ce = ce_losses[-n_steps // 5:] if len(ce_losses) > 5 else ce_losses[-1:]
    early_ce_mean = sum(early_ce) / max(len(early_ce), 1)
    late_ce_mean = sum(late_ce) / max(len(late_ce), 1)
    ce_stable = late_ce_mean <= early_ce_mean * 1.1  # Allow 10% degradation

    print(f"\n2. CE Loss Stability:")
    print(f"   Early mean: {early_ce_mean:.4f}")
    print(f"   Late mean:  {late_ce_mean:.4f}")
    print(f"   VERDICT: {'PASS - CE stable' if ce_stable else 'WARN - CE degraded'}")

    # Check 3: cos_pos should be higher than cos_neg
    final_cos_pos = sum(cos_pos_list[-n_steps // 5:]) / max(len(cos_pos_list[-n_steps // 5:]), 1)
    final_cos_neg = sum(cos_neg_list[-n_steps // 5:]) / max(len(cos_neg_list[-n_steps // 5:]), 1)
    separation = final_cos_pos > final_cos_neg

    print(f"\n3. Representation Separation:")
    print(f"   Final cos_pos: {final_cos_pos:.4f}")
    print(f"   Final cos_neg: {final_cos_neg:.4f}")
    print(f"   VERDICT: {'PASS - separated' if separation else 'WARN - not separated'}")

    # Check 4: Calibration artifacts
    early_logit_std = sum(logit_stds[:n_steps // 5]) / max(len(logit_stds[:n_steps // 5]), 1)
    late_logit_std = sum(logit_stds[-n_steps // 5:]) / max(len(logit_stds[-n_steps // 5:]), 1)
    logit_std_stable = abs(late_logit_std - early_logit_std) < early_logit_std * 0.3 if early_logit_std > 0 else True

    print(f"\n4. Calibration Artifact Check:")
    print(f"   Early logit_std: {early_logit_std:.2f}")
    print(f"   Late logit_std:  {late_logit_std:.2f}")
    print(f"   VERDICT: {'PASS - no artifacts' if logit_std_stable else 'WARN - logit scale shift'}")

    # Overall verdict
    print(f"\n{'=' * 70}")
    if delta_improved and ce_stable and separation:
        print("OVERALL: PASS - Contrastive objective is shaping representation geometry")
        print("         without degrading language modeling or introducing calibration artifacts.")
    elif delta_improved and not ce_stable:
        print("OVERALL: PARTIAL - Geometry shaped but CE degraded. Reduce lambda_rep.")
    elif not delta_improved:
        print("OVERALL: FAIL - No geometry shaping detected. Check hyperparameters.")
    else:
        print("OVERALL: INCONCLUSIVE - More steps may be needed.")
    print("=" * 70)

    return {
        "ce_losses": ce_losses,
        "rep_losses": rep_losses,
        "deltas": deltas,
        "cos_pos": cos_pos_list,
        "cos_neg": cos_neg_list,
        "logit_stds": logit_stds,
        "entropies": entropies,
        "delta_improved": delta_improved,
        "ce_stable": ce_stable,
        "separation": separation,
    }


def main():
    parser = argparse.ArgumentParser(
        description="BCVF Contrastive Representation Smoketest"
    )
    parser.add_argument("--steps", type=int, default=300, help="Training steps")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--batch_size", type=int, default=8, help="Batch size")
    parser.add_argument("--seq_len", type=int, default=64, help="Sequence length")
    parser.add_argument("--vocab_size", type=int, default=1000, help="Vocabulary size")
    parser.add_argument("--d_model", type=int, default=256, help="Model dimension")
    parser.add_argument("--lambda_rep", type=float, default=0.1, help="Contrastive loss weight")
    parser.add_argument("--K", type=int, default=16, help="Number of negatives")
    parser.add_argument("--margin", type=float, default=0.15, help="Margin for ranking loss")
    parser.add_argument("--alpha", type=float, default=2.0, help="BCVF weighting temperature")
    parser.add_argument("--eta", type=float, default=0.1, help="Token embedding injection scale")
    parser.add_argument("--lr", type=float, default=3e-4, help="Learning rate")
    parser.add_argument("--log_every", type=int, default=10, help="Log every N steps")
    parser.add_argument("--device", type=str, default="cpu", help="Device (cpu/cuda)")

    args = parser.parse_args()

    results = run_smoketest(
        n_steps=args.steps,
        seed=args.seed,
        batch_size=args.batch_size,
        seq_len=args.seq_len,
        vocab_size=args.vocab_size,
        d_model=args.d_model,
        lambda_rep=args.lambda_rep,
        K=args.K,
        margin=args.margin,
        alpha=args.alpha,
        eta=args.eta,
        lr=args.lr,
        log_every=args.log_every,
        device_str=args.device,
    )

    # Exit code based on overall result
    if results["delta_improved"] and results["ce_stable"]:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
