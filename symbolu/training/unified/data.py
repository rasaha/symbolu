from __future__ import annotations

import logging
import os
import random
import torch
from pathlib import Path
from torch.utils.data import Dataset, DataLoader, IterableDataset
from typing import Dict, List, Optional, Any, Tuple

try:
    from transformers import AutoTokenizer
    from datasets import load_dataset
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False

logger = logging.getLogger(__name__)


class TextDataset(Dataset):
    """Dataset for language modeling."""

    def __init__(self, tokens: torch.Tensor, seq_len: int):
        self.tokens = tokens
        self.seq_len = seq_len
        # Need seq_len+1 tokens per sample (input[:-1] + target[1:] shift)
        self.num_samples = (len(tokens) - 1) // seq_len

    def __len__(self):
        return self.num_samples

    def __getitem__(self, idx):
        start = idx * self.seq_len
        end = start + self.seq_len + 1
        chunk = self.tokens[start:end]
        return chunk[:-1], chunk[1:]


class FineWebStreamingDataset(IterableDataset):
    """Streaming FineWeb dataset for efficient training on large datasets.

    Supports:
    - HuggingFaceFW/fineweb (CC-based web text)
    - HuggingFaceFW/fineweb-edu (educational content)
    - Any streaming-compatible HuggingFace dataset

    Args:
        cache_dataset: If True, download and cache dataset locally (slower first run,
                       faster subsequent runs, no network required). If False, stream
                       data on-the-fly (faster start, requires network).
    """

    def __init__(
        self,
        tokenizer,
        seq_length: int = 2048,
        dataset_name: str = "HuggingFaceFW/fineweb",
        dataset_subset: str = "sample-10BT",
        split: str = "train",
        cache_dataset: bool = False,
    ):
        self.tokenizer = tokenizer
        self.seq_length = seq_length
        self.dataset_name = dataset_name
        self.dataset_subset = dataset_subset
        self.split = split
        self.cache_dataset = cache_dataset
        self._cached_dataset = None

    def _load_dataset(self):
        """Load dataset (streaming or cached)."""
        from datasets import load_dataset

        if self.cache_dataset:
            # Download and cache locally (stored in ~/.cache/huggingface/datasets/)
            return load_dataset(
                self.dataset_name,
                name=self.dataset_subset,
                split=self.split,
                streaming=False,
            )
        else:
            # Stream dataset to avoid loading everything into memory
            return load_dataset(
                self.dataset_name,
                name=self.dataset_subset,
                split=self.split,
                streaming=True,
            )

    def __iter__(self):
        if self.cache_dataset and self._cached_dataset is None:
            print(f"  [FineWeb] Downloading and caching dataset locally...")
            print(f"  [FineWeb] This may take a while on first run, but will be fast on subsequent runs.")
            self._cached_dataset = self._load_dataset()
            print(f"  [FineWeb] Dataset cached. Size: {len(self._cached_dataset):,} examples")

        dataset = self._cached_dataset if self.cache_dataset else self._load_dataset()
        buffer = []

        for example in dataset:
            # Tokenize text
            text = example.get("text", "")
            if not text:
                continue

            tokens = self.tokenizer.encode(text)
            buffer.extend(tokens)

            # Yield chunks of seq_length + 1 (for input/target)
            while len(buffer) >= self.seq_length + 1:
                chunk = buffer[:self.seq_length + 1]
                buffer = buffer[self.seq_length:]

                input_ids = torch.tensor(chunk[:-1], dtype=torch.long)
                labels = torch.tensor(chunk[1:], dtype=torch.long)

                yield {"input_ids": input_ids, "labels": labels}


def cache_validation_batches(dataloader, num_batches: int = 20) -> list:
    """Pre-cache validation batches to avoid re-resolving streaming dataset.

    This eliminates the 7-minute "Resolving data files" delay during validation
    when using streaming FineWeb datasets.
    """
    print(f"  Caching {num_batches} validation batches...")
    cached = []
    data_iter = iter(dataloader)
    for i in range(num_batches):
        try:
            batch = next(data_iter)
            # Handle different batch formats
            if isinstance(batch, dict):
                cached.append({
                    "input_ids": batch["input_ids"].clone(),
                    "labels": batch["labels"].clone(),
                })
            else:
                # Tuple format (input_ids, labels)
                cached.append({
                    "input_ids": batch[0].clone(),
                    "labels": batch[1].clone(),
                })
        except StopIteration:
            break
    print(f"  Cached {len(cached)} validation batches")
    return cached


def load_data(
    config: UnifiedTrainingConfig,
    tokenizer,
    seq_len_override: Optional[int] = None,
) -> Tuple[DataLoader, DataLoader]:
    """Load and tokenize dataset.

    Supports:
    - wikitext103: WikiText-103 (static, ~100M tokens)
    - wikitext2: WikiText-2 (static, ~2M tokens)
    - fineweb: Streaming FineWeb/FineWeb-edu (uses dataset_name and dataset_subset)

    V9.7.0: Implements tokenization caching for WikiText datasets.
    First run tokenizes and saves to disk (~2-5 min).
    Subsequent runs load from cache (<5 sec).

    V2.3.4: Added seq_len_override for sequence length curriculum.
    """
    # V2.3.4: Use override if provided, otherwise use config
    effective_seq_len = seq_len_override if seq_len_override is not None else config.max_seq_len
    print(f"Loading {config.dataset} dataset...")

    if config.dataset in ["wikitext103", "wikitext2"]:
        # V9.7.0: Check for cached tokenized data
        cache_dir = Path("data_cache")
        cache_dir.mkdir(exist_ok=True)

        # Include tokenizer name in cache path to avoid mismatches
        tokenizer_name = getattr(tokenizer, 'name_or_path', 'unknown').replace('/', '_')
        cache_path = cache_dir / f"{config.dataset}_{tokenizer_name}.pt"

        if cache_path.exists():
            print(f"  📦 Loading cached tokenized data from {cache_path}...")
            cache_start = time.time()
            cached_data = torch.load(cache_path, weights_only=True)
            train_tokens = cached_data['train']
            val_tokens = cached_data['val']
            cache_time = time.time() - cache_start
            print(f"  ✅ Loaded {len(train_tokens):,} train + {len(val_tokens):,} val tokens in {cache_time:.1f}s")
        else:
            print(f"  ⏳ No cache found. Tokenizing {config.dataset} (this only happens once)...")
            tokenize_start = time.time()

            # Static WikiText datasets
            if config.dataset == "wikitext103":
                ds = load_dataset("wikitext", "wikitext-103-v1")
            else:
                ds = load_dataset("wikitext", "wikitext-2-v1")

            def tokenize(split):
                text = "\n".join(ds[split]["text"])
                # V9.8.4: Clean WikiText Moses tokenization artifacts BEFORE tokenizing
                # This prevents the model from learning @,@ @-@ @.@ and = = = patterns
                if GRADIENT_THROTTLE_AVAILABLE:
                    text = clean_wikitext_artifacts(text)
                if hasattr(tokenizer, "encode"):
                    tokens = tokenizer.encode(text)
                else:
                    tokens = tokenizer(text)["input_ids"]
                return torch.tensor(tokens, dtype=torch.long)

            train_tokens = tokenize("train")
            val_tokens = tokenize("validation")

            tokenize_time = time.time() - tokenize_start
            print(f"  ✅ Tokenized {len(train_tokens):,} train + {len(val_tokens):,} val tokens in {tokenize_time:.1f}s")

            # Save to cache for next time
            print(f"  💾 Saving tokenized cache to {cache_path}...")
            torch.save({'train': train_tokens, 'val': val_tokens}, cache_path)
            cache_size_mb = cache_path.stat().st_size / (1024 * 1024)
            print(f"  ✅ Cache saved ({cache_size_mb:.1f} MB). Next startup will be <5s!")

        train_dataset = TextDataset(train_tokens, effective_seq_len)
        val_dataset = TextDataset(val_tokens, effective_seq_len)

        train_loader = DataLoader(
            train_dataset,
            batch_size=config.batch_size,
            shuffle=True,
            num_workers=config.num_workers,
            pin_memory=True,
            drop_last=True,
            prefetch_factor=2 if config.num_workers > 0 else None,
            persistent_workers=config.num_workers > 0,
        )

        val_loader = DataLoader(
            val_dataset,
            batch_size=config.batch_size,
            shuffle=False,
            num_workers=config.num_workers,
            pin_memory=True,
            drop_last=True,
            prefetch_factor=2 if config.num_workers > 0 else None,
            persistent_workers=config.num_workers > 0,
        )

        return train_loader, val_loader

    elif config.dataset == "fineweb":
        # Streaming or cached FineWeb dataset
        print(f"  Dataset: {config.dataset_name}")
        print(f"  Subset: {config.dataset_subset}")
        print(f"  Sequence length: {effective_seq_len}")
        print(f"  Mode: {'Cached (local)' if config.cache_dataset else 'Streaming'}")

        # Create streaming/cached datasets for train and val
        train_dataset = FineWebStreamingDataset(
            tokenizer=tokenizer,
            seq_length=effective_seq_len,
            dataset_name=config.dataset_name,
            dataset_subset=config.dataset_subset,
            split="train",
            cache_dataset=config.cache_dataset,
        )

        # For validation, we use a small portion of train (FineWeb doesn't have val split)
        val_dataset = FineWebStreamingDataset(
            tokenizer=tokenizer,
            seq_length=effective_seq_len,
            dataset_name=config.dataset_name,
            dataset_subset=config.dataset_subset,
            split="train",  # Use train split, will cache limited batches
            cache_dataset=config.cache_dataset,
        )

        train_loader = DataLoader(
            train_dataset,
            batch_size=config.batch_size,
            num_workers=4,
            pin_memory=True,
            prefetch_factor=4,
        )

        val_loader = DataLoader(
            val_dataset,
            batch_size=config.batch_size,
            num_workers=2,
            pin_memory=True,
            prefetch_factor=2,
        )

        print(f"  Streaming dataloaders created (batch_size={config.batch_size})")

        return train_loader, val_loader

    elif config.dataset == "synthetic":
        # Offline synthetic dataset (random tokens for architecture validation)
        vocab_size = getattr(tokenizer, 'vocab_size', 256)
        num_train = max(200_000, effective_seq_len * config.batch_size * 100)
        num_val = max(20_000, effective_seq_len * config.batch_size * 10)
        print(f"  Generating synthetic data: {num_train:,} train + {num_val:,} val tokens (vocab={vocab_size})")
        train_tokens = torch.randint(1, vocab_size, (num_train,))
        val_tokens = torch.randint(1, vocab_size, (num_val,))

        train_dataset = TextDataset(train_tokens, effective_seq_len)
        val_dataset = TextDataset(val_tokens, effective_seq_len)

        train_loader = DataLoader(
            train_dataset,
            batch_size=config.batch_size,
            shuffle=True,
            num_workers=0,
            drop_last=True,
        )
        val_loader = DataLoader(
            val_dataset,
            batch_size=config.batch_size,
            shuffle=False,
            num_workers=0,
            drop_last=True,
        )
        return train_loader, val_loader

    else:
        raise ValueError(f"Unknown dataset: {config.dataset}. Use 'wikitext103', 'wikitext2', 'fineweb', or 'synthetic'")
