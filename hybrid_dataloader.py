#!/usr/bin/env python3
"""
Hybrid Data Loader for Retrieval-Enriched Training.

Mixes WikiText (language modeling) with synthetic retrieval tasks
to teach Phase Attention models long-range memory.

Usage:
    # Generate retrieval data first
    python retrieval_dataset.py --output retrieval_train.json --num_samples 10000

    # Then use this loader in training
    from hybrid_dataloader import HybridDataset, create_hybrid_dataloader

Google's Recommended Curriculum:
    Stage 1 (Warm-up): 90% WikiText + 10% Retrieval
    Stage 2 (Annealing): 95% Long docs + 5% Retrieval
"""

import json
import random
from pathlib import Path
from typing import List, Dict, Optional, Iterator
import torch
from torch.utils.data import Dataset, DataLoader, IterableDataset


class RetrievalDataset(Dataset):
    """Dataset for synthetic retrieval tasks."""

    def __init__(self, json_path: str, tokenizer, max_length: int = 4096):
        self.tokenizer = tokenizer
        self.max_length = max_length

        with open(json_path, 'r') as f:
            self.samples = json.load(f)

        print(f"Loaded {len(self.samples)} retrieval samples from {json_path}")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        sample = self.samples[idx]
        text = sample["text"]

        # Tokenize
        tokens = self.tokenizer.encode(text)

        # Truncate if needed
        if len(tokens) > self.max_length:
            tokens = tokens[:self.max_length]

        return {
            "input_ids": torch.tensor(tokens, dtype=torch.long),
            "task_type": sample["task_type"],
        }


class HybridIterableDataset(IterableDataset):
    """
    Iterable dataset that mixes WikiText with retrieval data.

    Yields samples with configurable ratio:
    - retrieval_ratio=0.1 means 10% retrieval, 90% WikiText
    """

    def __init__(
        self,
        wikitext_dataset,
        retrieval_json_path: str,
        tokenizer,
        max_length: int = 4096,
        retrieval_ratio: float = 0.1,
        seed: int = 42,
    ):
        self.wikitext_dataset = wikitext_dataset
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.retrieval_ratio = retrieval_ratio
        self.rng = random.Random(seed)

        # Load retrieval data
        with open(retrieval_json_path, 'r') as f:
            self.retrieval_samples = json.load(f)

        print(f"HybridDataset: {1-retrieval_ratio:.0%} WikiText + {retrieval_ratio:.0%} Retrieval")
        print(f"  WikiText samples: {len(wikitext_dataset)}")
        print(f"  Retrieval samples: {len(self.retrieval_samples)}")

    def __iter__(self) -> Iterator[Dict]:
        wiki_iter = iter(self.wikitext_dataset)
        retrieval_idx = 0

        while True:
            # Decide which dataset to sample from
            if self.rng.random() < self.retrieval_ratio:
                # Sample from retrieval
                sample = self.retrieval_samples[retrieval_idx % len(self.retrieval_samples)]
                retrieval_idx += 1

                text = sample["text"]
                tokens = self.tokenizer.encode(text)

                if len(tokens) > self.max_length:
                    tokens = tokens[:self.max_length]

                yield {
                    "input_ids": torch.tensor(tokens, dtype=torch.long),
                    "is_retrieval": True,
                    "task_type": sample.get("task_type", "unknown"),
                }
            else:
                # Sample from WikiText
                try:
                    wiki_sample = next(wiki_iter)
                except StopIteration:
                    wiki_iter = iter(self.wikitext_dataset)
                    wiki_sample = next(wiki_iter)

                yield {
                    "input_ids": wiki_sample["input_ids"],
                    "is_retrieval": False,
                    "task_type": "language_model",
                }


def create_hybrid_dataloader(
    wikitext_dataset,
    retrieval_json_path: str,
    tokenizer,
    batch_size: int = 1,
    max_length: int = 4096,
    retrieval_ratio: float = 0.1,
    num_workers: int = 0,
    seed: int = 42,
) -> DataLoader:
    """
    Create a DataLoader that yields mixed WikiText + Retrieval batches.

    Args:
        wikitext_dataset: The base WikiText dataset
        retrieval_json_path: Path to retrieval_train.json
        tokenizer: Tokenizer for encoding
        batch_size: Batch size (usually 1 for 128K context)
        max_length: Maximum sequence length
        retrieval_ratio: Fraction of batches that are retrieval tasks (default 0.1 = 10%)
        num_workers: DataLoader workers
        seed: Random seed for reproducibility

    Returns:
        DataLoader yielding mixed batches
    """
    dataset = HybridIterableDataset(
        wikitext_dataset=wikitext_dataset,
        retrieval_json_path=retrieval_json_path,
        tokenizer=tokenizer,
        max_length=max_length,
        retrieval_ratio=retrieval_ratio,
        seed=seed,
    )

    def collate_fn(batch):
        """Collate with padding."""
        input_ids = [item["input_ids"] for item in batch]
        is_retrieval = [item["is_retrieval"] for item in batch]
        task_types = [item["task_type"] for item in batch]

        # Pad to max length in batch
        max_len = max(len(ids) for ids in input_ids)
        padded = torch.zeros(len(input_ids), max_len, dtype=torch.long)

        for i, ids in enumerate(input_ids):
            padded[i, :len(ids)] = ids

        return {
            "input_ids": padded,
            "is_retrieval": is_retrieval,
            "task_types": task_types,
        }

    return DataLoader(
        dataset,
        batch_size=batch_size,
        collate_fn=collate_fn,
        num_workers=num_workers,
    )


# =============================================================================
# Integration with train.py
# =============================================================================

def patch_train_dataloader(train_py_path: str = "train.py"):
    """
    Print instructions for patching train.py to use hybrid data.

    This doesn't modify train.py directly - just shows what to change.
    """
    instructions = """
# =============================================================================
# HOW TO INTEGRATE HYBRID DATALOADER INTO train.py
# =============================================================================

1. First, generate the retrieval dataset:
   ```
   python retrieval_dataset.py --output retrieval_train.json --num_samples 10000
   ```

2. Add this import at the top of train.py:
   ```python
   from hybrid_dataloader import HybridIterableDataset
   ```

3. Find the section where the dataset is created (around line 800-900).
   Look for something like:
   ```python
   if config.dataset == "wikitext103":
       dataset = ...
   ```

4. After creating the base dataset, wrap it with HybridIterableDataset:
   ```python
   # Add hybrid retrieval training (10% retrieval tasks)
   retrieval_path = "retrieval_train.json"
   if os.path.exists(retrieval_path):
       from hybrid_dataloader import HybridIterableDataset
       logger.info("Using hybrid training: 90% WikiText + 10% Retrieval")
       dataset = HybridIterableDataset(
           wikitext_dataset=dataset,
           retrieval_json_path=retrieval_path,
           tokenizer=tokenizer,
           max_length=config.max_seq_len,
           retrieval_ratio=0.1,  # 10% retrieval
       )
   ```

5. Run training as usual:
   ```
   python train.py --resume checkpoints/best.pt ...
   ```

# =============================================================================
# ALTERNATIVE: Quick test without modifying train.py
# =============================================================================

You can also test the hybrid data separately:
   ```
   python -c "
   from hybrid_dataloader import create_hybrid_dataloader
   from datasets import load_dataset
   import tiktoken

   # Load base dataset
   wiki = load_dataset('wikitext', 'wikitext-103-v1', split='train')
   tokenizer = tiktoken.get_encoding('gpt2')

   # Create hybrid loader
   loader = create_hybrid_dataloader(
       wikitext_dataset=wiki,
       retrieval_json_path='retrieval_train.json',
       tokenizer=tokenizer,
       retrieval_ratio=0.1,
   )

   # Check distribution
   retrieval_count = 0
   for i, batch in enumerate(loader):
       if batch['is_retrieval'][0]:
           retrieval_count += 1
       if i >= 100:
           break
   print(f'Retrieval ratio: {retrieval_count}%')
   "
   ```
"""
    print(instructions)
    return instructions


if __name__ == "__main__":
    # Demo mode - show integration instructions
    patch_train_dataloader()
