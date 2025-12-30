#!/usr/bin/env python3
"""
Retrieval-Enriched Training Script for Phase Attention.

This script wraps train.py to add hybrid training with retrieval tasks.

Usage:
    # First generate retrieval data
    python retrieval_dataset.py --output retrieval_train.json --num_samples 10000

    # Then run hybrid training
    python train_retrieval.py --model_type hybrid --model_size tiny \
        --dataset wikitext103 --max_seq_len 131072 \
        --batch_size 1 --gradient_accumulation 1 \
        --max_steps 10000 --use_coherence_loss \
        --gradient_checkpointing --local_backend unfold \
        --window_size 128 --warmup_steps 300 \
        --log_every 10 --eval_every 50 \
        --retrieval_ratio 0.1 \
        --resume checkpoints/best.pt
"""

import os

# Set CUDA memory and tokenizer environment variables before importing torch
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import sys
import json
import random
import argparse
from pathlib import Path

import torch
from torch.utils.data import Dataset

# Import from train.py
sys.path.insert(0, str(Path(__file__).parent))


class HybridTextDataset(Dataset):
    """
    Hybrid dataset that mixes language modeling with retrieval tasks.

    - retrieval_ratio=0.1 means 10% retrieval, 90% language modeling
    """

    def __init__(
        self,
        lm_tokens: torch.Tensor,
        seq_len: int,
        retrieval_json_path: str = "retrieval_train.json",
        retrieval_ratio: float = 0.1,
        tokenizer=None,
        seed: int = 42,
    ):
        self.lm_tokens = lm_tokens
        self.seq_len = seq_len
        self.retrieval_ratio = retrieval_ratio
        self.tokenizer = tokenizer
        self.rng = random.Random(seed)

        # Language modeling samples
        self.num_lm_samples = len(lm_tokens) // seq_len

        # Load retrieval data
        self.retrieval_samples = []
        if os.path.exists(retrieval_json_path):
            with open(retrieval_json_path, 'r') as f:
                self.retrieval_samples = json.load(f)
            print(f"Loaded {len(self.retrieval_samples)} retrieval samples")
            print(f"Hybrid ratio: {100*(1-retrieval_ratio):.0f}% LM + {100*retrieval_ratio:.0f}% Retrieval")
        else:
            print(f"Warning: {retrieval_json_path} not found. Using pure LM training.")
            self.retrieval_ratio = 0.0

        # Total virtual size
        self.num_samples = self.num_lm_samples

    def __len__(self):
        return self.num_samples

    def __getitem__(self, idx):
        # Decide whether to return retrieval or LM sample
        if self.retrieval_samples and self.rng.random() < self.retrieval_ratio:
            return self._get_retrieval_sample()
        else:
            return self._get_lm_sample(idx)

    def _get_lm_sample(self, idx):
        """Get language modeling sample."""
        start = idx * self.seq_len
        end = start + self.seq_len + 1
        chunk = self.lm_tokens[start:end]

        x = chunk[:-1]
        y = chunk[1:]

        return x, y

    def _get_retrieval_sample(self):
        """Get retrieval training sample."""
        sample = self.rng.choice(self.retrieval_samples)
        text = sample["text"]

        # Tokenize
        if self.tokenizer is not None:
            tokens = self.tokenizer.encode(text)
        else:
            # Fallback: split by space (less accurate)
            tokens = [hash(w) % 50257 for w in text.split()]

        # Convert to tensor
        tokens = torch.tensor(tokens, dtype=torch.long)

        # Pad or truncate to seq_len + 1
        if len(tokens) > self.seq_len + 1:
            tokens = tokens[:self.seq_len + 1]
        elif len(tokens) < self.seq_len + 1:
            padding = torch.zeros(self.seq_len + 1 - len(tokens), dtype=torch.long)
            tokens = torch.cat([tokens, padding])

        x = tokens[:-1]
        y = tokens[1:]

        return x, y


def patch_create_dataloaders():
    """
    Monkey-patch train.py's create_dataloaders to use HybridTextDataset.
    """
    import train

    original_create_dataloaders = train.create_dataloaders

    def hybrid_create_dataloaders(config):
        """Create hybrid train and validation dataloaders."""
        # Get retrieval ratio from environment or config
        retrieval_ratio = float(os.environ.get("RETRIEVAL_RATIO", "0.1"))
        retrieval_json = os.environ.get("RETRIEVAL_JSON", "retrieval_train.json")

        # Load tokens (original behavior)
        train_tokens = train.load_dataset_tokens(config, "train")
        val_tokens = train.load_dataset_tokens(config, "validation" if config.dataset != "c4" else "validation")

        # Load tokenizer for retrieval samples
        tokenizer = train.load_tokenizer(config)

        # Create hybrid dataset for training
        train_dataset = HybridTextDataset(
            lm_tokens=train_tokens,
            seq_len=config.max_seq_len,
            retrieval_json_path=retrieval_json,
            retrieval_ratio=retrieval_ratio,
            tokenizer=tokenizer,
        )

        # Keep validation as pure LM
        val_dataset = train.TextDataset(val_tokens, config.max_seq_len)

        # Create dataloaders
        train_loader = train.DataLoader(
            train_dataset,
            batch_size=config.batch_size,
            shuffle=True,
            num_workers=config.num_workers,
            pin_memory=config.pin_memory,
            drop_last=True,
        )

        val_loader = train.DataLoader(
            val_dataset,
            batch_size=config.batch_size,
            shuffle=False,
            num_workers=config.num_workers,
            pin_memory=config.pin_memory,
            drop_last=True,
        )

        return train_loader, val_loader

    # Apply patch
    train.create_dataloaders = hybrid_create_dataloaders
    print("Patched create_dataloaders for hybrid retrieval training")


def main():
    # Parse our custom args first
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--retrieval_ratio", type=float, default=0.1,
                        help="Ratio of retrieval samples (default: 0.1 = 10%%)")
    parser.add_argument("--retrieval_json", type=str, default="retrieval_train.json",
                        help="Path to retrieval training data")

    args, remaining = parser.parse_known_args()

    # Set environment variables for the patched function
    os.environ["RETRIEVAL_RATIO"] = str(args.retrieval_ratio)
    os.environ["RETRIEVAL_JSON"] = args.retrieval_json

    # Patch the dataloader
    patch_create_dataloaders()

    # Now import and run train.py with remaining args
    sys.argv = [sys.argv[0]] + remaining

    import train
    config = train.parse_args()
    train.train(config)


if __name__ == "__main__":
    main()
