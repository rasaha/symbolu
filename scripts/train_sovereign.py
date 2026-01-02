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
import math
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

# Default quality sample prompts
DEFAULT_SAMPLE_PROMPTS = [
    "The history of the Roman Empire began when",
    "In computer science, algorithms are",
    "The weather today is expected to be",
]


def generate_sample(
    model: nn.Module,
    tokenizer: SovereignTokenizer,
    prompt: str,
    device: torch.device,
    max_new_tokens: int = 50,
    temperature: float = 0.8,
    top_p: float = 0.9,
) -> str:
    """
    Generate text from a prompt using the Sovereign model.

    Uses nucleus (top-p) sampling with temperature for diverse outputs.
    The SovereignTokenizer generates C/S/R/G signals for each token.
    """
    model.eval()

    with torch.no_grad():
        # Get initial encoding with signals
        batch = tokenizer.process_batch([prompt], max_length=512)

        input_ids = batch["input_ids"].to(device)
        c_signals = batch["c_signals"].to(device)
        s_signals = batch["s_signals"].to(device)
        r_signals = batch["r_signals"].to(device)
        g_states = batch["g_states"].to(device)

        # Generate tokens one by one
        for _ in range(max_new_tokens):
            # Forward pass
            token_logits, _, _, _ = model(
                input_ids, c_signals, s_signals, r_signals, g_states
            )

            # Get next token logits (last position)
            next_logits = token_logits[:, -1, :] / temperature

            # Top-p (nucleus) sampling
            sorted_logits, sorted_indices = torch.sort(next_logits, descending=True)
            cumsum = torch.cumsum(torch.softmax(sorted_logits, dim=-1), dim=-1)

            # Remove tokens with cumulative probability above threshold
            sorted_indices_to_remove = cumsum > top_p
            sorted_indices_to_remove[:, 1:] = sorted_indices_to_remove[:, :-1].clone()
            sorted_indices_to_remove[:, 0] = False

            # Set removed tokens to -inf
            indices_to_remove = sorted_indices_to_remove.scatter(
                1, sorted_indices, sorted_indices_to_remove
            )
            next_logits[indices_to_remove] = float("-inf")

            # Sample next token
            probs = torch.softmax(next_logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)

            # Decode the new token to get its signals
            new_token_str = tokenizer.tokenizer.decode(next_token[0])
            new_batch = tokenizer.process_batch([new_token_str], max_length=16)

            # Append new token and its signals
            input_ids = torch.cat([input_ids, next_token], dim=1)
            c_signals = torch.cat([c_signals, new_batch["c_signals"][:, :1].to(device)], dim=1)
            s_signals = torch.cat([s_signals, new_batch["s_signals"][:, :1].to(device)], dim=1)
            r_signals = torch.cat([r_signals, new_batch["r_signals"][:, :1].to(device)], dim=1)
            g_states = torch.cat([g_states, new_batch["g_states"][:, :1].to(device)], dim=1)

            # Stop at EOS
            if next_token.item() == tokenizer.tokenizer.eos_token_id:
                break

    # Decode full sequence (skip prompt tokens)
    prompt_len = batch["input_ids"].shape[1]
    generated_ids = input_ids[0, prompt_len:]
    generated_text = tokenizer.tokenizer.decode(generated_ids, skip_special_tokens=True)

    model.train()
    return generated_text


def run_quality_samples(
    model: nn.Module,
    tokenizer: SovereignTokenizer,
    prompts: list,
    device: torch.device,
    step: int,
):
    """
    Generate sample outputs to monitor training quality.

    This provides a qualitative check that the model is learning
    meaningful language patterns, not just minimizing perplexity.
    """
    print("")
    print("=" * 60)
    print(f"  📝 QUALITY SAMPLES (Step {step})")
    print("=" * 60)

    for prompt in prompts:
        try:
            generated = generate_sample(
                model, tokenizer, prompt, device,
                max_new_tokens=50,
                temperature=0.8,
                top_p=0.9,
            )
            # Clean up and truncate for display
            generated = generated.strip().replace("\n", " ")[:200]
            print(f'  Prompt: "{prompt}"')
            print(f'  Output: "{generated}"')
            print("")
        except Exception as e:
            print(f"  Sampling failed for prompt '{prompt[:30]}...': {e}")

    print("=" * 60)
    print("")


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


def train_epoch(
    model, dataloader, optimizer, loss_fn, device, epoch,
    tokenizer=None, sample_every=0, sample_prompts=None, global_step=0
):
    """Train for one epoch with optional quality sampling."""
    model.train()
    total_loss = 0
    num_batches = 0
    step = global_step

    pbar = tqdm(dataloader, desc=f"Epoch {epoch+1}")
    for batch in pbar:
        step += 1

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

        # Update progress bar with PPL
        token_ppl = math.exp(loss_output.token) if loss_output.token < 20 else float('inf')
        pbar.set_postfix({
            "step": step,
            "loss": f"{loss_output.total.item():.4f}",
            "PPL": f"{token_ppl:.2f}",
            "r": f"{loss_output.r_signal:.4f}",
        })

        # Quality sampling
        if sample_every > 0 and step % sample_every == 0 and tokenizer is not None:
            run_quality_samples(model, tokenizer, sample_prompts or DEFAULT_SAMPLE_PROMPTS, device, step)

    avg_loss = total_loss / num_batches
    ppl = math.exp(avg_loss) if avg_loss < 20 else float('inf')
    return avg_loss, ppl, step


@torch.no_grad()
def validate(model, dataloader, loss_fn, device):
    """Run validation and compute perplexity."""
    model.eval()
    total_loss = 0
    total_tokens = 0

    for batch in tqdm(dataloader, desc="Validating", leave=False):
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

        # Accumulate token loss for PPL calculation
        batch_size, seq_len = target_tokens.shape
        total_loss += loss_output.token * batch_size * seq_len
        total_tokens += batch_size * seq_len

    model.train()

    avg_loss = total_loss / total_tokens if total_tokens > 0 else float('inf')
    ppl = math.exp(avg_loss) if avg_loss < 20 else float('inf')
    return avg_loss, ppl


def main():
    parser = argparse.ArgumentParser(description="Train Sovereign Model on Wikitext")
    parser.add_argument("--epochs", type=int, default=3, help="Number of epochs")
    parser.add_argument("--batch_size", type=int, default=8, help="Batch size")
    parser.add_argument("--lr", type=float, default=3e-4, help="Learning rate")
    parser.add_argument("--max_length", type=int, default=128, help="Max sequence length")
    parser.add_argument("--max_samples", type=int, default=None, help="Max training samples")
    parser.add_argument("--n_layers", type=int, default=6, help="Number of transformer layers")
    parser.add_argument("--save_dir", type=str, default="checkpoints/sovereign", help="Save directory")
    parser.add_argument("--sample_every", type=int, default=100, help="Generate quality samples every N steps (0=disabled)")
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

    # Load datasets
    print("\n3. Loading datasets...")
    train_texts = load_wikitext("train", max_samples=args.max_samples)
    val_texts = load_wikitext("validation", max_samples=args.max_samples // 10 if args.max_samples else None)

    # Create dataset and dataloader
    print("\n4. Creating dataloaders...")
    train_dataset = WikitextSovereignDataset(train_texts, tokenizer, max_length=args.max_length)
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0,  # NLTK not fork-safe
        drop_last=True,
        collate_fn=sovereign_collate_fn,
    )
    val_dataset = WikitextSovereignDataset(val_texts, tokenizer, max_length=args.max_length)
    val_loader = DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,
        drop_last=False,
        collate_fn=sovereign_collate_fn,
    )
    print(f"   Train batches: {len(train_loader)}, Val batches: {len(val_loader)}")

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
        optimizer, T_max=args.epochs * len(train_loader)
    )

    # Training loop
    print("\n" + "=" * 70)
    print("TRAINING")
    print("=" * 70)
    if args.sample_every > 0:
        print(f"Quality samples every {args.sample_every} steps")

    os.makedirs(args.save_dir, exist_ok=True)
    best_val_ppl = float("inf")
    global_step = 0

    for epoch in range(args.epochs):
        # Train
        train_loss, train_ppl, global_step = train_epoch(
            model, train_loader, optimizer, loss_fn, device, epoch,
            tokenizer=tokenizer,
            sample_every=args.sample_every,
            sample_prompts=DEFAULT_SAMPLE_PROMPTS,
            global_step=global_step,
        )
        scheduler.step()

        # Validate
        val_loss, val_ppl = validate(model, val_loader, loss_fn, device)

        print(f"\n{'='*60}")
        print(f"  Epoch {epoch+1}/{args.epochs} Complete")
        print(f"  Train Loss: {train_loss:.4f} | Train PPL: {train_ppl:.2f}")
        print(f"  Val Loss:   {val_loss:.4f} | Val PPL:   {val_ppl:.2f}")
        print(f"  Steps: {global_step}")
        print(f"{'='*60}")

        # Save checkpoint based on val PPL
        if val_ppl < best_val_ppl:
            best_val_ppl = val_ppl
            checkpoint_path = os.path.join(args.save_dir, "best_model.pt")
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "train_loss": train_loss,
                "train_ppl": train_ppl,
                "val_loss": val_loss,
                "val_ppl": val_ppl,
            }, checkpoint_path)
            print(f"  📦 New best! Val PPL: {val_ppl:.2f} → Saved to {checkpoint_path}")

    print("\n" + "=" * 70)
    print("TRAINING COMPLETE")
    print(f"Best Val PPL: {best_val_ppl:.2f}")
    print("=" * 70)


if __name__ == "__main__":
    main()
