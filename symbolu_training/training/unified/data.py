from __future__ import annotations

import logging
import os
import random
import time
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

try:
    from symbolu_training.training.text_utils import clean_wikitext_artifacts
    WIKITEXT_CLEANUP_AVAILABLE = True
except ImportError:
    WIKITEXT_CLEANUP_AVAILABLE = False

logger = logging.getLogger(__name__)

# Field mappings for known HuggingFace reasoning datasets.
# Each entry maps dataset_name -> (question_field, answer_field, optional_subset).
REASONING_HF_REGISTRY = {
    "meta-math/MetaMathQA": {
        "question": "query",
        "answer": "response",
        "subset": None,
        "split": "train",
        "description": "395K math problems with diverse reasoning paths",
    },
    "nvidia/OpenMathInstruct-2": {
        "question": "problem",
        "answer": "generated_solution",
        "subset": None,
        "split": "train",
        "description": "14M math reasoning examples from Llama",
    },
    "AI-MO/NuminaMath-CoT": {
        "question": "problem",
        "answer": "solution",
        "subset": None,
        "split": "train",
        "description": "860K competition math with chain-of-thought",
    },
    "kaist-ai/CoT-Collection": {
        "question": "source",
        "answer": "rationale",
        "subset": None,
        "split": "train",
        "description": "1.84M chain-of-thought across 1,060 tasks",
    },
    "TIGER-Lab/MathInstruct": {
        "question": "instruction",
        "answer": "output",
        "subset": None,
        "split": "train",
        "description": "262K math with CoT + program-of-thought",
    },
    "microsoft/orca-math-word-problems-200k": {
        "question": "question",
        "answer": "answer",
        "subset": None,
        "split": "train",
        "description": "200K word problems with multi-agent verification",
    },
}


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


class ReasoningHFStreamingDataset(IterableDataset):
    """Streaming dataset for HuggingFace reasoning datasets.

    Formats Q&A pairs into text for next-token prediction:
        Question: <question>
        Solution: <answer>

    Supports auto-detection of field names for known datasets
    (MetaMathQA, OpenMathInstruct-2, NuminaMath-CoT, etc.)
    and manual field specification for custom datasets.
    """

    def __init__(
        self,
        tokenizer,
        seq_length: int = 1024,
        dataset_name: str = "meta-math/MetaMathQA",
        dataset_subset: str = None,
        split: str = "train",
        question_field: str = None,
        answer_field: str = None,
        cache_dataset: bool = False,
        max_examples: int = 0,
    ):
        self.tokenizer = tokenizer
        self.seq_length = seq_length
        self.dataset_name = dataset_name
        self.dataset_subset = dataset_subset
        self.split = split
        self.cache_dataset = cache_dataset
        self.max_examples = max_examples
        self._cached_dataset = None

        # Auto-detect fields from registry, or use provided overrides
        registry_entry = REASONING_HF_REGISTRY.get(dataset_name, {})
        self.question_field = question_field or registry_entry.get("question", "question")
        self.answer_field = answer_field or registry_entry.get("answer", "answer")

        if dataset_subset is None and registry_entry.get("subset"):
            self.dataset_subset = registry_entry["subset"]
        if registry_entry.get("split"):
            self.split = split or registry_entry["split"]

    def _load_dataset(self):
        from datasets import load_dataset

        kwargs = {
            "split": self.split,
            "streaming": not self.cache_dataset,
        }
        if self.dataset_subset:
            kwargs["name"] = self.dataset_subset

        return load_dataset(self.dataset_name, **kwargs)

    def _format_example(self, example: dict) -> str:
        question = example.get(self.question_field, "")
        answer = example.get(self.answer_field, "")
        if not question and not answer:
            return ""
        return f"Question: {question}\nSolution: {answer}"

    def __iter__(self):
        if self.cache_dataset and self._cached_dataset is None:
            print(f"  [ReasoningHF] Downloading and caching {self.dataset_name}...")
            self._cached_dataset = self._load_dataset()
            print(f"  [ReasoningHF] Cached. Size: {len(self._cached_dataset):,} examples")

        dataset = self._cached_dataset if self.cache_dataset else self._load_dataset()
        buffer = []
        count = 0

        for example in dataset:
            if self.max_examples > 0 and count >= self.max_examples:
                break

            text = self._format_example(example)
            if not text:
                continue

            tokens = self.tokenizer.encode(text)
            buffer.extend(tokens)
            count += 1

            while len(buffer) >= self.seq_length + 1:
                chunk = buffer[:self.seq_length + 1]
                buffer = buffer[self.seq_length:]

                input_ids = torch.tensor(chunk[:-1], dtype=torch.long)
                labels = torch.tensor(chunk[1:], dtype=torch.long)

                yield {"input_ids": input_ids, "labels": labels}


class InterleavedMixedDataset(IterableDataset):
    """Interleaves multiple streaming datasets with weighted sampling.

    Each batch is drawn from one dataset, selected by weighted probability.
    This ensures the model sees both language modeling and reasoning data
    throughout training rather than in separate phases.

    Usage:
        --dataset mixed --mix_datasets "wikitext103:0.7,reasoning_hf:0.3"

    Supports mixing any combination of:
        - wikitext103, wikitext2 (static, wrapped as iterators)
        - fineweb (streaming)
        - reasoning_hf (streaming, uses --dataset_name)
        - reasoning (synthetic CoT)
    """

    def __init__(
        self,
        sources: List[Tuple[IterableDataset, float]],
        seed: int = 42,
    ):
        """
        Args:
            sources: List of (dataset, weight) tuples. Weights are normalized.
            seed: Random seed for reproducibility.
        """
        total_weight = sum(w for _, w in sources)
        self.sources = [(ds, w / total_weight) for ds, w in sources]
        self.seed = seed

    def __iter__(self):
        rng = random.Random(self.seed)
        # Create iterators for all sources
        iterators = []
        weights = []
        for ds, w in self.sources:
            iterators.append(iter(ds))
            weights.append(w)

        active = list(range(len(iterators)))

        while active:
            # Weighted random selection among active sources
            active_weights = [weights[i] for i in active]
            total = sum(active_weights)
            active_weights = [w / total for w in active_weights]

            r = rng.random()
            cumulative = 0.0
            chosen_idx = active[0]
            for i, w in zip(active, active_weights):
                cumulative += w
                if r <= cumulative:
                    chosen_idx = i
                    break

            try:
                item = next(iterators[chosen_idx])
                # Normalize to dict format
                if isinstance(item, (tuple, list)):
                    yield {"input_ids": item[0], "labels": item[1]}
                else:
                    yield item
            except StopIteration:
                active.remove(chosen_idx)


class _StaticToStreamingAdapter(IterableDataset):
    """Wraps a static TextDataset as an IterableDataset with shuffling."""

    def __init__(self, static_dataset: TextDataset):
        self.static_dataset = static_dataset

    def __iter__(self):
        indices = list(range(len(self.static_dataset)))
        random.shuffle(indices)
        for idx in indices:
            x, y = self.static_dataset[idx]
            yield {"input_ids": x, "labels": y}


def _build_source_dataset(
    source_name: str,
    config,
    tokenizer,
    effective_seq_len: int,
    split: str = "train",
    max_examples: int = 0,
) -> IterableDataset:
    """Build a single source dataset by name for use in mixed training."""

    if source_name in ["wikitext103", "wikitext2"]:
        cache_dir = Path("data_cache")
        cache_dir.mkdir(exist_ok=True)
        tokenizer_name = getattr(tokenizer, 'name_or_path', 'unknown').replace('/', '_')
        cache_path = cache_dir / f"{source_name}_{tokenizer_name}.pt"

        if cache_path.exists():
            cached_data = torch.load(cache_path, weights_only=True)
            tokens = cached_data['train' if split == 'train' else 'val']
        else:
            if source_name == "wikitext103":
                ds = load_dataset("wikitext", "wikitext-103-v1")
            else:
                ds = load_dataset("wikitext", "wikitext-2-v1")

            hf_split = "train" if split == "train" else "validation"
            text = "\n".join(ds[hf_split]["text"])
            if WIKITEXT_CLEANUP_AVAILABLE:
                text = clean_wikitext_artifacts(text)
            tokens = torch.tensor(tokenizer.encode(text), dtype=torch.long)

            # Cache both splits
            train_text = "\n".join(ds["train"]["text"])
            val_text = "\n".join(ds["validation"]["text"])
            if WIKITEXT_CLEANUP_AVAILABLE:
                train_text = clean_wikitext_artifacts(train_text)
                val_text = clean_wikitext_artifacts(val_text)
            train_tokens = torch.tensor(tokenizer.encode(train_text), dtype=torch.long)
            val_tokens = torch.tensor(tokenizer.encode(val_text), dtype=torch.long)
            torch.save({"train": train_tokens, "val": val_tokens}, cache_path)

        static_ds = TextDataset(tokens, effective_seq_len)
        return _StaticToStreamingAdapter(static_ds)

    elif source_name == "fineweb":
        return FineWebStreamingDataset(
            tokenizer=tokenizer,
            seq_length=effective_seq_len,
            dataset_name=config.dataset_name,
            dataset_subset=config.dataset_subset,
            split="train",
            cache_dataset=config.cache_dataset,
        )

    elif source_name == "reasoning_hf":
        ds_name = config.dataset_name
        subset = config.dataset_subset if config.dataset_subset != "sample-10BT" else None
        return ReasoningHFStreamingDataset(
            tokenizer=tokenizer,
            seq_length=effective_seq_len,
            dataset_name=ds_name,
            dataset_subset=subset,
            split="train",
            cache_dataset=config.cache_dataset,
            max_examples=max_examples,
        )

    elif source_name == "reasoning":
        tokenizer_name = getattr(tokenizer, 'name_or_path', 'unknown').replace('/', '_')
        cache_path = Path("data_cache") / f"reasoning_{tokenizer_name}.pt"

        if cache_path.exists():
            cached_data = torch.load(cache_path, weights_only=True)
            tokens = cached_data['train' if split == 'train' else 'val']
        else:
            from symbolu_training.training.scripts.generate_reasoning_dataset import generate_examples
            examples = generate_examples(50000, seed=42)
            split_idx = int(len(examples) * 0.95)
            separator = "\n\n"
            train_tokens = torch.tensor(
                tokenizer.encode(separator.join(examples[:split_idx])), dtype=torch.long
            )
            val_tokens = torch.tensor(
                tokenizer.encode(separator.join(examples[split_idx:])), dtype=torch.long
            )
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            torch.save({"train": train_tokens, "val": val_tokens}, cache_path)
            tokens = train_tokens if split == "train" else val_tokens

        static_ds = TextDataset(tokens, effective_seq_len)
        return _StaticToStreamingAdapter(static_ds)

    else:
        raise ValueError(f"Unknown source for mixed dataset: {source_name}")


def parse_mix_datasets(mix_str: str) -> List[Tuple[str, float]]:
    """Parse mix_datasets string like 'wikitext103:0.7,reasoning_hf:0.3'.

    Returns list of (dataset_name, weight) tuples.
    """
    sources = []
    for part in mix_str.split(","):
        part = part.strip()
        if ":" in part:
            name, weight = part.rsplit(":", 1)
            sources.append((name.strip(), float(weight)))
        else:
            sources.append((part.strip(), 1.0))
    return sources


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
                try:
                    ds = load_dataset("wikitext", "wikitext-103-v1")
                except Exception as e:
                    # Check full exception chain for disk space errors
                    _exc = e
                    _is_disk_full = False
                    while _exc is not None:
                        if "No space left on device" in str(_exc) or (isinstance(_exc, OSError) and _exc.errno == 28):
                            _is_disk_full = True
                            break
                        _exc = getattr(_exc, '__cause__', None) or getattr(_exc, '__context__', None)
                    if _is_disk_full:
                        print(f"  ⚠️  WikiText-103 failed (disk full), falling back to WikiText-2...")
                        ds = load_dataset("wikitext", "wikitext-2-v1")
                    else:
                        raise
            else:
                ds = load_dataset("wikitext", "wikitext-2-v1")

            def tokenize(split):
                text = "\n".join(ds[split]["text"])
                # V9.8.4: Clean WikiText Moses tokenization artifacts BEFORE tokenizing
                # This prevents the model from learning @,@ @-@ @.@ and = = = patterns
                if WIKITEXT_CLEANUP_AVAILABLE:
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

    elif config.dataset == "mixed":
        # Interleaved mixed training from multiple sources
        mix_str = getattr(config, 'mix_datasets', '')
        if not mix_str:
            raise ValueError("--dataset mixed requires --mix_datasets, e.g. 'wikitext103:0.7,reasoning_hf:0.3'")

        source_specs = parse_mix_datasets(mix_str)
        print(f"  Mixed training with {len(source_specs)} sources:")

        # Build train sources
        train_sources = []
        for name, weight in source_specs:
            print(f"    - {name}: weight={weight:.2f}")
            ds = _build_source_dataset(name, config, tokenizer, effective_seq_len, split="train")
            train_sources.append((ds, weight))

        # Build val sources (with limited examples for streaming ones)
        val_sources = []
        for name, weight in source_specs:
            ds = _build_source_dataset(
                name, config, tokenizer, effective_seq_len,
                split="val", max_examples=2000,
            )
            val_sources.append((ds, weight))

        train_dataset = InterleavedMixedDataset(train_sources, seed=42)
        val_dataset = InterleavedMixedDataset(val_sources, seed=123)

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

        print(f"  Interleaved dataloaders created (batch_size={config.batch_size})")
        return train_loader, val_loader

    elif config.dataset == "reasoning_hf":
        # Production reasoning datasets from HuggingFace
        # Uses dataset_name to select: meta-math/MetaMathQA, nvidia/OpenMathInstruct-2, etc.
        dataset_name = config.dataset_name
        registry_entry = REASONING_HF_REGISTRY.get(dataset_name)

        if registry_entry:
            print(f"  Dataset: {dataset_name}")
            print(f"  Description: {registry_entry['description']}")
        else:
            print(f"  Dataset: {dataset_name} (custom — using question_field/answer_field)")

        print(f"  Sequence length: {effective_seq_len}")
        print(f"  Mode: {'Cached (local)' if config.cache_dataset else 'Streaming'}")

        train_dataset = ReasoningHFStreamingDataset(
            tokenizer=tokenizer,
            seq_length=effective_seq_len,
            dataset_name=dataset_name,
            dataset_subset=config.dataset_subset if config.dataset_subset != "sample-10BT" else None,
            split="train",
            cache_dataset=config.cache_dataset,
        )

        # Validation: stream a separate portion (most reasoning datasets have only train split)
        val_dataset = ReasoningHFStreamingDataset(
            tokenizer=tokenizer,
            seq_length=effective_seq_len,
            dataset_name=dataset_name,
            dataset_subset=config.dataset_subset if config.dataset_subset != "sample-10BT" else None,
            split="train",
            cache_dataset=config.cache_dataset,
            max_examples=2000,
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

        # List available datasets if user might want to try others
        if not registry_entry:
            print(f"  Available presets: {', '.join(REASONING_HF_REGISTRY.keys())}")

        return train_loader, val_loader

    elif config.dataset == "reasoning":
        # Synthetic reasoning dataset (chain-of-thought examples)
        # Generated by: python -m symbolu.training.scripts.generate_reasoning_dataset
        tokenizer_name = getattr(tokenizer, 'name_or_path', 'unknown').replace('/', '_')
        cache_path = Path("data_cache") / f"reasoning_{tokenizer_name}.pt"

        if cache_path.exists():
            print(f"  Loading cached reasoning data from {cache_path}...")
            cache_start = time.time()
            cached_data = torch.load(cache_path, weights_only=True)
            train_tokens = cached_data['train']
            val_tokens = cached_data['val']
            cache_time = time.time() - cache_start
            print(f"  Loaded {len(train_tokens):,} train + {len(val_tokens):,} val tokens in {cache_time:.1f}s")
        else:
            # Auto-generate if no cached file exists
            print(f"  No cached reasoning dataset at {cache_path}. Generating...")
            from symbolu_training.training.scripts.generate_reasoning_dataset import generate_examples
            examples = generate_examples(50000, seed=42)
            split_idx = int(len(examples) * 0.95)
            separator = "\n\n"
            train_text = separator.join(examples[:split_idx])
            val_text = separator.join(examples[split_idx:])
            train_tokens = torch.tensor(tokenizer.encode(train_text), dtype=torch.long)
            val_tokens = torch.tensor(tokenizer.encode(val_text), dtype=torch.long)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            torch.save({"train": train_tokens, "val": val_tokens}, cache_path)
            size_mb = cache_path.stat().st_size / (1024 * 1024)
            print(f"  Generated and cached {len(train_tokens):,} train + {len(val_tokens):,} val tokens ({size_mb:.1f} MB)")

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
        raise ValueError(f"Unknown dataset: {config.dataset}. Use 'wikitext103', 'wikitext2', 'fineweb', 'mixed', 'reasoning_hf', 'reasoning', or 'synthetic'")
