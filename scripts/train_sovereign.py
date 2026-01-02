#!/usr/bin/env python3
"""
Train Sovereign Model on Wikitext-2 Dataset.

Usage:
    python scripts/train_sovereign.py --epochs 3 --batch_size 8

This script:
1. Downloads Wikitext-2 dataset via HuggingFace
2. Preprocesses with SovereignTokenizer (generates C/S/R/G signals)
3. Trains using multi-objective loss with PID Governor
"""

import argparse
import os
import sys
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from symbolu.sovereign.embedding import (
    SovereignEmbedding,
    SovereignEmbeddingConfig,
    SovereignOutputHead,
)
from symbolu.sovereign.tagger import SovereignTokenizer
from symbolu.sovereign.train_loss import MultiObjectiveLoss, TrainingLossConfig


def sovereign_collate_fn(batch):
    """Custom collate function that pads tensors to the same length."""
    # Find max sequence length in this batch
    max_len = max(item["input_ids"].shape[0] for item in batch)

    # Pad each tensor to max_len
    padded_batch = {
        "input_ids": [],
        "c_signals": [],
        "s_signals": [],
        "r_signals": [],
        "g_states": [],
        "attention_mask": [],
    }

    for item in batch:
        seq_len = item["input_ids"].shape[0]
        pad_len = max_len - seq_len

        # Pad input_ids with 0 (typically pad token)
        padded_batch["input_ids"].append(
            torch.nn.functional.pad(item["input_ids"], (0, pad_len), value=0)
        )
        # Pad c_signals [seq, 32] -> pad on seq dimension
        padded_batch["c_signals"].append(
            torch.nn.functional.pad(item["c_signals"], (0, 0, 0, pad_len), value=0)
        )
        # Pad s_signals [seq]
        padded_batch["s_signals"].append(
            torch.nn.functional.pad(item["s_signals"], (0, pad_len), value=0)
        )
        # Pad r_signals [seq]
        padded_batch["r_signals"].append(
            torch.nn.functional.pad(item["r_signals"], (0, pad_len), value=0)
        )
        # Pad g_states [seq, 3] -> pad on seq dimension
        padded_batch["g_states"].append(
            torch.nn.functional.pad(item["g_states"], (0, 0, 0, pad_len), value=0)
        )
        # Pad attention_mask [seq]
        padded_batch["attention_mask"].append(
            torch.nn.functional.pad(item["attention_mask"], (0, pad_len), value=0)
        )

    # Stack into batch tensors
    return {
        "input_ids": torch.stack(padded_batch["input_ids"]),
        "c_signals": torch.stack(padded_batch["c_signals"]),
        "s_signals": torch.stack(padded_batch["s_signals"]),
        "r_signals": torch.stack(padded_batch["r_signals"]),
        "g_states": torch.stack(padded_batch["g_states"]),
        "attention_mask": torch.stack(padded_batch["attention_mask"]),
    }


class SovereignTransformer(nn.Module):
    """Sovereign Transformer for training."""

    def __init__(self, config, n_heads=16, n_layers=6):
        super().__init__()
        self.embedding = SovereignEmbedding(config)
        self.transformer = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(
                d_model=config.d_model,
                nhead=n_heads,
                dim_feedforward=config.d_model * 4,
                batch_first=True,
                dropout=0.1,
            ),
            num_layers=n_layers,
        )
        self.output_head = SovereignOutputHead(config)

    def forward(self, input_ids, c_signals, s_signals, r_signals, g_states, attention_mask=None):
        x = self.embedding(input_ids, c_signals, s_signals, r_signals, g_states)

        # Create causal mask
        seq_len = x.size(1)
        causal_mask = torch.triu(
            torch.ones(seq_len, seq_len, device=x.device), diagonal=1
        ).bool()

        x = self.transformer(x, mask=causal_mask)
        return self.output_head(x)


class WikitextSovereignDataset(Dataset):
    """Dataset that preprocesses Wikitext with Sovereign signals."""

    def __init__(self, texts, tokenizer, max_length=128):
        self.texts = texts
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        text = self.texts[idx]

        # Process with SovereignTokenizer
        # Note: padding and truncation are handled internally by process_batch
        batch = self.tokenizer.process_batch(
            [text],
            max_length=self.max_length,
        )

        # Remove batch dimension
        return {
            "input_ids": batch["input_ids"][0],
            "c_signals": batch["c_signals"][0],
            "s_signals": batch["s_signals"][0],
            "r_signals": batch["r_signals"][0],
            "g_states": batch["g_states"][0],
            "attention_mask": batch["attention_mask"][0],
        }


def load_wikitext(split="train", max_samples=None):
    """Load Wikitext-2 dataset."""
    try:
        from datasets import load_dataset
    except ImportError:
        print("Installing datasets...")
        os.system("pip install datasets")
        from datasets import load_dataset

    print(f"Loading Wikitext-2 ({split})...")
    dataset = load_dataset("wikitext", "wikitext-2-raw-v1", split=split)

    # Filter empty lines and short texts
    texts = [t for t in dataset["text"] if len(t.strip()) > 50]

    if max_samples:
        texts = texts[:max_samples]

    print(f"Loaded {len(texts)} samples")
    return texts


def train_epoch(model, dataloader, optimizer, loss_fn, device, epoch):
    """Train for one epoch."""
    model.train()
    total_loss = 0
    num_batches = 0

    pbar = tqdm(dataloader, desc=f"Epoch {epoch+1}")
    for batch in pbar:
        # Move to device
        input_ids = batch["input_ids"].to(device)
        c_signals = batch["c_signals"].to(device)
        s_signals = batch["s_signals"].to(device)
        r_signals = batch["r_signals"].to(device)
        g_states = batch["g_states"].to(device)

        # Shift for next-token prediction
        target_tokens = input_ids[:, 1:].contiguous()
        target_r = r_signals[:, 1:].contiguous()
        target_s = s_signals[:, 1:].contiguous()
        target_c = c_signals[:, 1:].contiguous()

        input_ids = input_ids[:, :-1]
        c_signals = c_signals[:, :-1]
        s_signals = s_signals[:, :-1]
        r_signals = r_signals[:, :-1]
        g_states = g_states[:, :-1]

        # Forward pass
        optimizer.zero_grad()
        token_logits, r_logits, s_logits, c_pred = model(
            input_ids, c_signals, s_signals, r_signals, g_states
        )

        # Compute loss
        loss_output = loss_fn(
            token_logits=token_logits,
            r_logits=r_logits,
            s_logits=s_logits,
            c_pred=c_pred,
            target_tokens=target_tokens,
            target_r=target_r,
            target_s=target_s,
            target_c=target_c,
        )

        # Backward pass
        loss_output.total.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

        total_loss += loss_output.total.item()
        num_batches += 1

        # Update progress bar
        pbar.set_postfix({
            "loss": f"{loss_output.total.item():.4f}",
            "token": f"{loss_output.token:.4f}",
            "r": f"{loss_output.r_signal:.4f}",
        })

    return total_loss / num_batches


def main():
    parser = argparse.ArgumentParser(description="Train Sovereign Model on Wikitext")
    parser.add_argument("--epochs", type=int, default=3, help="Number of epochs")
    parser.add_argument("--batch_size", type=int, default=8, help="Batch size")
    parser.add_argument("--lr", type=float, default=3e-4, help="Learning rate")
    parser.add_argument("--max_length", type=int, default=128, help="Max sequence length")
    parser.add_argument("--max_samples", type=int, default=None, help="Max training samples")
    parser.add_argument("--n_layers", type=int, default=6, help="Number of transformer layers")
    parser.add_argument("--save_dir", type=str, default="checkpoints/sovereign", help="Save directory")
    args = parser.parse_args()

    # Device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # Create model
    print("\n1. Creating model...")
    embed_config = SovereignEmbeddingConfig(
        vocab_size=50257,
        d_model=1024,
    )
    model = SovereignTransformer(embed_config, n_layers=args.n_layers)
    model.to(device)
    print(f"   Parameters: {sum(p.numel() for p in model.parameters()):,}")

    # Create tokenizer
    print("\n2. Creating SovereignTokenizer...")
    tokenizer = SovereignTokenizer()

    # Load dataset
    print("\n3. Loading dataset...")
    train_texts = load_wikitext("train", max_samples=args.max_samples)

    # Create dataset and dataloader
    print("\n4. Creating dataset...")
    dataset = WikitextSovereignDataset(train_texts, tokenizer, max_length=args.max_length)
    dataloader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0,  # NLTK not fork-safe
        drop_last=True,
        collate_fn=sovereign_collate_fn,
    )
    print(f"   Batches per epoch: {len(dataloader)}")

    # Create loss and optimizer
    print("\n5. Setting up training...")
    loss_config = TrainingLossConfig(
        lambda_token=1.0,
        lambda_r=0.1,
        lambda_s=0.1,
        lambda_c=0.05,
    )
    loss_fn = MultiObjectiveLoss(loss_config)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=args.epochs * len(dataloader)
    )

    # Training loop
    print("\n" + "=" * 70)
    print("TRAINING")
    print("=" * 70)

    os.makedirs(args.save_dir, exist_ok=True)
    best_loss = float("inf")

    for epoch in range(args.epochs):
        avg_loss = train_epoch(model, dataloader, optimizer, loss_fn, device, epoch)
        scheduler.step()

        print(f"\nEpoch {epoch+1}/{args.epochs} - Avg Loss: {avg_loss:.4f}")

        # Save checkpoint
        if avg_loss < best_loss:
            best_loss = avg_loss
            checkpoint_path = os.path.join(args.save_dir, "best_model.pt")
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "loss": avg_loss,
            }, checkpoint_path)
            print(f"   Saved best model to {checkpoint_path}")

    print("\n" + "=" * 70)
    print("TRAINING COMPLETE")
    print(f"Best loss: {best_loss:.4f}")
    print("=" * 70)


if __name__ == "__main__":
    main()
