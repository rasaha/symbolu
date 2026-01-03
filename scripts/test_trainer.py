#!/usr/bin/env python3
"""
Test script for Sovereign Trainer initialization.

Usage:
    python scripts/test_trainer.py
"""

import torch
import torch.nn as nn
from symbolu.sovereign.embedding import SovereignEmbedding, SovereignEmbeddingConfig, SovereignOutputHead
from symbolu.sovereign.trainer import SovereignTrainer, SovereignTrainerConfig


class SovereignTransformer(nn.Module):
    """Simple Sovereign Transformer for testing."""

    def __init__(self, config, n_heads=16):
        super().__init__()
        self.embedding = SovereignEmbedding(config)
        self.transformer = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(
                d_model=config.d_model,
                nhead=n_heads,
                dim_feedforward=config.d_model * 4,
                batch_first=True,
            ),
            num_layers=4,
        )
        self.output_head = SovereignOutputHead(config)

    def forward(self, input_ids, c_signals, s_signals, r_signals, g_states, attention_mask=None):
        x = self.embedding(input_ids, c_signals, s_signals, r_signals, g_states)
        x = self.transformer(x)
        return self.output_head(x)


def main():
    print("=" * 70)
    print("SOVEREIGN TRAINER INITIALIZATION TEST")
    print("=" * 70)

    # Create embedding config
    embed_config = SovereignEmbeddingConfig(
        vocab_size=50257,
        d_model=1024,
    )

    # Create model
    print("\n1. Creating SovereignTransformer...")
    model = SovereignTransformer(embed_config)

    # Create trainer config
    trainer_config = SovereignTrainerConfig(
        batch_size=8,
        learning_rate=3e-4,
        max_epochs=3,
    )

    # Create trainer
    print("2. Creating SovereignTrainer...")
    trainer = SovereignTrainer(model, trainer_config)

    # Print info
    print(f"\n3. Model Info:")
    print(f"   Parameters: {sum(p.numel() for p in model.parameters()):,}")
    print(f"   Device: {trainer.device}")

    # Test forward pass with dummy data
    print("\n4. Testing forward pass...")
    B, Seq = 2, 16
    device = trainer.device
    dummy_batch = {
        "input_ids": torch.randint(0, 50257, (B, Seq)).to(device),
        "c_signals": torch.randn(B, Seq, 32).to(device),
        "s_signals": torch.randint(0, 17, (B, Seq)).to(device),
        "r_signals": torch.randint(0, 12, (B, Seq)).to(device),
        "g_states": torch.softmax(torch.randn(B, Seq, 3), dim=-1).to(device),
    }

    model.eval()
    with torch.no_grad():
        token_logits, r_logits, s_logits, c_pred = model(
            dummy_batch["input_ids"],
            dummy_batch["c_signals"],
            dummy_batch["s_signals"],
            dummy_batch["r_signals"],
            dummy_batch["g_states"],
        )

    print(f"   Token logits shape: {token_logits.shape}")
    print(f"   R logits shape: {r_logits.shape}")
    print(f"   S logits shape: {s_logits.shape}")
    print(f"   C prediction shape: {c_pred.shape}")

    print("\n" + "=" * 70)
    print("[PASS] Trainer initialized successfully!")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    exit(main())
