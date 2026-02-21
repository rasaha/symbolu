#!/usr/bin/env python3
"""
Training script for all three attention models with real dataset benchmarks.

Trains and evaluates:
  1. Quadratic (Standard) - O(n²) softmax attention
  2. Phase (Linear)       - O(n) phase-based cumsum attention
  3. Sliding-Window       - O(n*w) binding cache (local + phase + quad)

Each model is trained with and without Spanda to measure the benefit delta.

Dataset options:
  --dataset wikitext2    (default, ~2M tokens)
  --dataset wikitext103  (larger, ~100M tokens)
  --dataset synthetic    (HardProbeDataset, no HF dependency)

Usage:
  python scripts/train_three_attention_benchmark.py --dataset synthetic --max_steps 100
  python scripts/train_three_attention_benchmark.py --dataset wikitext2 --max_steps 1000
  python scripts/train_three_attention_benchmark.py --models phase sliding_window --dataset synthetic
"""

import argparse
import json
import math
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "Spanda"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "phase_probes" / "hard_probes"))

# Core attention models from train_hard_probes
from train_hard_probes import (
    HardVocabulary,
    HardProbeDataset,
    HardProbeTransformer,
    SplitType,
    evaluate as evaluate_classifier,
    LocalWindowAttention,
    BindingCacheLMBlock,
    BindingCacheLMTransformer,
)

# Spanda modules
from spanda.state import SpandaState
from spanda.emission import AnchorEmission
from spanda.regularizers import SpandaRegularizers

# Optional: real datasets
try:
    from symbolu.phase_transformer import PhaseTransformer, StandardTransformer, TransformerConfig
    PHASE_TRANSFORMER_AVAILABLE = True
except ImportError:
    PHASE_TRANSFORMER_AVAILABLE = False

try:
    from datasets import load_dataset as hf_load_dataset
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class TrainConfig:
    """Configuration for three-model benchmark."""
    # Model
    d_model: int = 128
    num_heads: int = 4
    num_layers: int = 3
    d_ff: int = 256
    max_seq_len: int = 128
    vocab_size: int = 0  # Set by dataset
    window_size: int = 32  # For sliding window

    # Training
    max_steps: int = 500
    batch_size: int = 16
    lr: float = 3e-4
    weight_decay: float = 0.01
    grad_clip: float = 1.0
    eval_interval: int = 100
    warmup_steps: int = 50

    # Spanda
    psi_dim: int = 64
    decay_gamma: float = 0.99

    # Dataset
    dataset: str = "synthetic"
    train_samples: int = 2000
    test_samples: int = 500
    seq_len: int = 64

    # Output
    output_dir: str = "results/three_attention_benchmark"
    seed: int = 42
    device: str = ""

    def __post_init__(self):
        if not self.device:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"


# =============================================================================
# DATASETS
# =============================================================================

class SyntheticLMDataset(Dataset):
    """Wraps HardProbeDataset for LM-style training (next-token prediction)."""

    def __init__(self, vocab: HardVocabulary, split: SplitType, num_samples: int,
                 max_seq_len: int, chain_length: Tuple[int, int], seed: int = 42):
        self.dataset = HardProbeDataset(
            vocab, split, num_samples, max_seq_len,
            chain_length=chain_length, bind_ratio=0.6, seed=seed,
        )
        self.vocab_size = vocab.vocab_size

    def __len__(self):
        return len(self.dataset)

    def __getitem__(self, idx):
        input_ids, target, schema = self.dataset[idx]
        # For LM: shift input for next-token prediction
        return input_ids[:-1], input_ids[1:]


class WikiTextLMDataset(Dataset):
    """WikiText dataset for language modeling."""

    def __init__(self, tokens: List[int], seq_len: int):
        self.tokens = tokens
        self.seq_len = seq_len
        self.num_samples = max(1, len(tokens) // seq_len - 1)

    def __len__(self):
        return self.num_samples

    def __getitem__(self, idx):
        start = idx * self.seq_len
        end = start + self.seq_len + 1
        chunk = self.tokens[start:end]
        if len(chunk) < self.seq_len + 1:
            chunk = chunk + [0] * (self.seq_len + 1 - len(chunk))
        return torch.tensor(chunk[:-1], dtype=torch.long), torch.tensor(chunk[1:], dtype=torch.long)


class CharTokenizer:
    """Simple character-level tokenizer (no network dependency)."""

    def __init__(self, text: str):
        chars = sorted(set(text))
        self.char_to_idx = {c: i for i, c in enumerate(chars)}
        self.idx_to_char = {i: c for c, i in self.char_to_idx.items()}
        self.vocab_size = len(chars)

    def encode(self, text: str) -> List[int]:
        return [self.char_to_idx.get(c, 0) for c in text]


def load_wikitext(dataset_name: str, seq_len: int):
    """Load and tokenize WikiText dataset."""
    if not HF_AVAILABLE:
        raise ImportError("Install: pip install datasets")

    # Try tokenizers in order of preference, handle network errors
    tokenizer_obj = None
    vocab_size = None

    if TIKTOKEN_AVAILABLE:
        try:
            tokenizer_obj = tiktoken.get_encoding("gpt2")
            def encode(text):
                return tokenizer_obj.encode(text, allowed_special={"<|endoftext|>"})
            vocab_size = tokenizer_obj.max_token_value + 1
            print("  Using tiktoken GPT-2 tokenizer")
        except Exception as e:
            print(f"  tiktoken failed ({e}), falling back...")
            tokenizer_obj = None

    if tokenizer_obj is None:
        try:
            from transformers import GPT2Tokenizer
            tokenizer_obj = GPT2Tokenizer.from_pretrained("gpt2")
            def encode(text):
                return tokenizer_obj.encode(text)
            vocab_size = tokenizer_obj.vocab_size
            print("  Using HF GPT-2 tokenizer")
        except Exception as e:
            print(f"  HF tokenizer failed ({e}), falling back to char-level...")
            tokenizer_obj = None

    if dataset_name == "wikitext2":
        ds_train = hf_load_dataset("wikitext", "wikitext-2-raw-v1", split="train")
        ds_val = hf_load_dataset("wikitext", "wikitext-2-raw-v1", split="validation")
    elif dataset_name == "wikitext103":
        ds_train = hf_load_dataset("wikitext", "wikitext-103-raw-v1", split="train")
        ds_val = hf_load_dataset("wikitext", "wikitext-103-raw-v1", split="validation")
    else:
        raise ValueError(f"Unknown dataset: {dataset_name}")

    train_text = " ".join(t for t in ds_train["text"] if t and t.strip())
    val_text = " ".join(t for t in ds_val["text"] if t and t.strip())

    # If no subword tokenizer available, use char-level
    if tokenizer_obj is None:
        char_tok = CharTokenizer(train_text + val_text)
        def encode(text):
            return char_tok.encode(text)
        vocab_size = char_tok.vocab_size
        print(f"  Using char-level tokenizer (vocab_size={vocab_size})")

    train_tokens = encode(train_text)
    val_tokens = encode(val_text)

    print(f"  [{dataset_name}] train: {len(train_tokens):,} tokens")
    print(f"  [{dataset_name}] val:   {len(val_tokens):,} tokens")

    return (
        WikiTextLMDataset(train_tokens, seq_len),
        WikiTextLMDataset(val_tokens, seq_len),
        vocab_size,
    )


# =============================================================================
# SPANDA WRAPPERS (standalone, no backbone.config dependency)
# =============================================================================

class SpandaClassifierWrapper(nn.Module):
    """Wraps HardProbeTransformer with Spanda Psi classification head."""

    def __init__(self, backbone: HardProbeTransformer, num_classes: int,
                 psi_dim: int = 64, decay_gamma: float = 0.99):
        super().__init__()
        self.backbone_embedding = backbone.token_emb
        self.backbone_pos_emb = backbone.pos_emb
        self.backbone_dropout = backbone.dropout
        self.backbone_layers = backbone.layers
        self.backbone_norm = backbone.norm
        self.use_phase = backbone.use_phase
        d_model = backbone.token_emb.embedding_dim

        self.spanda_state = SpandaState(embed_dim=d_model, psi_dim=psi_dim, decay_gamma=decay_gamma)
        self.regularizers = SpandaRegularizers(alpha=1e-4, beta=1e-4)
        self.class_anchors = nn.Parameter(torch.randn(num_classes, psi_dim) * 0.1)
        self.log_temperature = nn.Parameter(torch.tensor(math.log(psi_dim / 10.0)))
        self._reg_losses = {}

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.backbone_dropout(self.backbone_embedding(input_ids) + self.backbone_pos_emb(pos))
        for layer in self.backbone_layers:
            x = layer(x, input_ids if self.use_phase else None)
        h = self.backbone_norm(x)

        psi, delta = self.spanda_state(h)
        psi_last = psi[:, -1, :]
        self._reg_losses = self.regularizers(delta)

        tau = self.log_temperature.exp()
        anchors = F.normalize(self.class_anchors, dim=-1)
        psi_norm_sq = (psi_last ** 2).sum(dim=-1, keepdim=True)
        dot = psi_last @ anchors.T
        anchor_norm_sq = torch.ones(anchors.size(0), device=anchors.device)
        logits = (2 * dot - anchor_norm_sq.unsqueeze(0) - psi_norm_sq) / tau
        return logits

    @property
    def reg_losses(self):
        return self._reg_losses


class SpandaLMWrapper(nn.Module):
    """Wraps BindingCacheLMTransformer with Spanda anchor emission."""

    def __init__(self, backbone: BindingCacheLMTransformer,
                 psi_dim: int = 64, decay_gamma: float = 0.99):
        super().__init__()
        self.backbone = backbone
        d_model = backbone.d_model
        vocab_size = backbone.vocab_size
        self.spanda_state = SpandaState(embed_dim=d_model, psi_dim=psi_dim, decay_gamma=decay_gamma)
        self.anchor_emission = AnchorEmission(vocab_size=vocab_size, embed_dim=d_model, psi_dim=psi_dim)
        self.regularizers = SpandaRegularizers(alpha=1e-4, beta=1e-4)
        self._reg_losses = {}

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.backbone.dropout(self.backbone.token_emb(input_ids) + self.backbone.pos_emb(pos))
        for layer in self.backbone.layers:
            x = layer(x)
        h = self.backbone.norm(x)

        psi, delta = self.spanda_state(h)
        logits = self.anchor_emission(psi, self.backbone.token_emb.weight)
        self._reg_losses = self.regularizers(delta)
        return logits

    @property
    def reg_losses(self):
        return self._reg_losses


# =============================================================================
# MODEL FACTORY
# =============================================================================

def create_models(config: TrainConfig, vocab_size: int, num_classes: int = None,
                  operation_tokens: List[int] = None):
    """Create all model pairs (baseline + Spanda) for benchmarking."""
    device = config.device
    models = {}

    # 1. Quadratic (Standard) attention
    quad_base = HardProbeTransformer(
        vocab_size=vocab_size, d_model=config.d_model, num_heads=config.num_heads,
        num_layers=config.num_layers, d_ff=config.d_ff, dropout=0.0,
        max_seq_len=config.max_seq_len, num_classes=num_classes, use_phase=False,
    ).to(device)

    quad_backbone = HardProbeTransformer(
        vocab_size=vocab_size, d_model=config.d_model, num_heads=config.num_heads,
        num_layers=config.num_layers, d_ff=config.d_ff, dropout=0.0,
        max_seq_len=config.max_seq_len, num_classes=num_classes, use_phase=False,
    )
    quad_spanda = SpandaClassifierWrapper(
        quad_backbone, num_classes, psi_dim=config.psi_dim, decay_gamma=config.decay_gamma,
    ).to(device)

    models["quadratic"] = {"baseline": quad_base, "spanda": quad_spanda, "type": "classifier"}

    # 2. Phase (Linear) attention
    phase_base = HardProbeTransformer(
        vocab_size=vocab_size, d_model=config.d_model, num_heads=config.num_heads,
        num_layers=config.num_layers, d_ff=config.d_ff, dropout=0.0,
        max_seq_len=config.max_seq_len, num_classes=num_classes, use_phase=True,
        operation_tokens=operation_tokens, bounded_phase=True,
    ).to(device)

    phase_backbone = HardProbeTransformer(
        vocab_size=vocab_size, d_model=config.d_model, num_heads=config.num_heads,
        num_layers=config.num_layers, d_ff=config.d_ff, dropout=0.0,
        max_seq_len=config.max_seq_len, num_classes=num_classes, use_phase=True,
        operation_tokens=operation_tokens, bounded_phase=True,
    )
    phase_spanda = SpandaClassifierWrapper(
        phase_backbone, num_classes, psi_dim=config.psi_dim, decay_gamma=config.decay_gamma,
    ).to(device)

    models["phase"] = {"baseline": phase_base, "spanda": phase_spanda, "type": "classifier"}

    # 3. Sliding-window (Binding Cache) attention
    sw_base = BindingCacheLMTransformer(
        vocab_size=vocab_size, d_model=config.d_model, num_heads=config.num_heads,
        num_layers=config.num_layers, d_ff=config.d_ff, dropout=0.0,
        max_seq_len=config.max_seq_len, bounded_phase=True, top_k=16,
        use_cache=True, decay_gamma=0.9, window_size=config.window_size,
    ).to(device)

    sw_backbone = BindingCacheLMTransformer(
        vocab_size=vocab_size, d_model=config.d_model, num_heads=config.num_heads,
        num_layers=config.num_layers, d_ff=config.d_ff, dropout=0.0,
        max_seq_len=config.max_seq_len, bounded_phase=True, top_k=16,
        use_cache=True, decay_gamma=0.9, window_size=config.window_size,
    )
    sw_spanda = SpandaLMWrapper(
        sw_backbone, psi_dim=config.psi_dim, decay_gamma=config.decay_gamma,
    ).to(device)

    models["sliding_window"] = {"baseline": sw_base, "spanda": sw_spanda, "type": "lm"}

    return models


# =============================================================================
# TRAINING
# =============================================================================

def train_classifier_model(model, train_loader, vocab, device, config, use_spanda_reg=False):
    """Train a classification model. Returns list of per-step losses."""
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.lr, weight_decay=config.weight_decay)
    model.train()
    losses = []
    step = 0
    while step < config.max_steps:
        for batch in train_loader:
            if step >= config.max_steps:
                break
            input_ids, targets, _ = batch
            input_ids = input_ids.to(device)
            targets = targets.to(device)

            target_idx = torch.tensor([
                vocab.entity_to_idx(t.item()) if t.item() in vocab.entities else 0
                for t in targets
            ], device=device)

            logits = model(input_ids)
            ce_loss = F.cross_entropy(logits, target_idx)

            total_loss = ce_loss
            if use_spanda_reg and hasattr(model, 'reg_losses'):
                reg = model.reg_losses.get("total_reg", 0.0)
                if isinstance(reg, torch.Tensor):
                    total_loss = ce_loss + reg

            total_loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), config.grad_clip)
            optimizer.step()
            optimizer.zero_grad()
            losses.append(ce_loss.item())

            if step % config.eval_interval == 0 and step > 0:
                avg = sum(losses[-config.eval_interval:]) / config.eval_interval
                ppl = math.exp(min(avg, 20))
                print(f"    Step {step:>5d} | loss={avg:.4f} | ppl={ppl:.1f}")

            step += 1
    return losses


def train_lm_model(model, train_loader, device, config, vocab_size, use_spanda_reg=False):
    """Train a language model. Returns list of per-step losses."""
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.lr, weight_decay=config.weight_decay)
    model.train()
    losses = []
    step = 0
    while step < config.max_steps:
        for batch in train_loader:
            if step >= config.max_steps:
                break
            input_ids, targets = batch
            input_ids = input_ids.to(device)
            targets = targets.to(device)

            logits = model(input_ids)
            ce_loss = F.cross_entropy(logits.view(-1, vocab_size), targets.view(-1))

            total_loss = ce_loss
            if use_spanda_reg and hasattr(model, 'reg_losses'):
                reg = model.reg_losses.get("total_reg", 0.0)
                if isinstance(reg, torch.Tensor):
                    total_loss = ce_loss + reg

            total_loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), config.grad_clip)
            optimizer.step()
            optimizer.zero_grad()
            losses.append(ce_loss.item())

            if step % config.eval_interval == 0 and step > 0:
                avg = sum(losses[-config.eval_interval:]) / config.eval_interval
                ppl = math.exp(min(avg, 20))
                print(f"    Step {step:>5d} | loss={avg:.4f} | ppl={ppl:.1f}")

            step += 1
    return losses


@torch.no_grad()
def eval_lm(model, val_loader, device, vocab_size):
    """Evaluate LM perplexity."""
    model.eval()
    total_loss = 0.0
    n = 0
    for batch in val_loader:
        input_ids, targets = batch
        input_ids = input_ids.to(device)
        targets = targets.to(device)
        logits = model(input_ids)
        loss = F.cross_entropy(logits.view(-1, vocab_size), targets.view(-1))
        total_loss += loss.item()
        n += 1
        if n >= 50:
            break
    avg = total_loss / max(n, 1)
    return {"loss": avg, "perplexity": math.exp(min(avg, 20))}


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Three-Attention Model Benchmark")
    parser.add_argument("--dataset", default="synthetic", choices=["synthetic", "wikitext2", "wikitext103"])
    parser.add_argument("--max_steps", type=int, default=200)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--d_model", type=int, default=128)
    parser.add_argument("--num_heads", type=int, default=4)
    parser.add_argument("--num_layers", type=int, default=3)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--seq_len", type=int, default=64)
    parser.add_argument("--window_size", type=int, default=16)
    parser.add_argument("--psi_dim", type=int, default=64)
    parser.add_argument("--decay_gamma", type=float, default=0.99)
    parser.add_argument("--eval_interval", type=int, default=50)
    parser.add_argument("--output_dir", default="results/three_attention_benchmark")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--models", nargs="*", default=None,
        help="Which models to run (default: all). Options: quadratic, phase, sliding_window",
    )
    args = parser.parse_args()

    torch.manual_seed(args.seed)

    config = TrainConfig(
        d_model=args.d_model, num_heads=args.num_heads, num_layers=args.num_layers,
        d_ff=args.d_model * 2, max_seq_len=max(args.seq_len + 20, 128),
        max_steps=args.max_steps, batch_size=args.batch_size, lr=args.lr,
        seq_len=args.seq_len, window_size=args.window_size,
        psi_dim=args.psi_dim, decay_gamma=args.decay_gamma,
        eval_interval=args.eval_interval, output_dir=args.output_dir, seed=args.seed,
        dataset=args.dataset,
    )

    device = config.device
    model_names = args.models or ["quadratic", "phase", "sliding_window"]

    print("=" * 70)
    print("THREE-ATTENTION MODEL BENCHMARK + SPANDA BENEFIT ANALYSIS")
    print("=" * 70)
    print(f"  Dataset:     {config.dataset}")
    print(f"  Models:      {', '.join(model_names)}")
    print(f"  d_model:     {config.d_model}")
    print(f"  num_layers:  {config.num_layers}")
    print(f"  max_steps:   {config.max_steps}")
    print(f"  window_size: {config.window_size} (sliding-window)")
    print(f"  psi_dim:     {config.psi_dim} (Spanda)")
    print(f"  decay_gamma: {config.decay_gamma} (Spanda)")
    print(f"  device:      {device}")
    print()

    # ---- Load data ----
    if config.dataset == "synthetic":
        vocab = HardVocabulary()
        num_classes = len(vocab.entities)
        operation_tokens = [vocab.NEG, vocab.PERMUTE, vocab.OVERWRITE]
        vocab_size = vocab.vocab_size

        train_ds = HardProbeDataset(
            vocab, SplitType.TRAIN, config.train_samples, config.seq_len + 10,
            chain_length=(3, 5), bind_ratio=0.6, seed=42,
        )
        test_ds = HardProbeDataset(
            vocab, SplitType.TEST_ROLES, config.test_samples, config.seq_len + 10,
            chain_length=(3, 5), bind_ratio=0.6, seed=100,
        )
        persist_ds = HardProbeDataset(
            vocab, SplitType.TRAIN, config.test_samples, 80,
            chain_length=(6, 8), bind_ratio=1.0, seed=200,
        )

        # Classifier loader (for quad/phase)
        cls_train_loader = DataLoader(train_ds, batch_size=config.batch_size, shuffle=True)
        cls_test_loader = DataLoader(test_ds, batch_size=config.batch_size, shuffle=False)
        cls_persist_loader = DataLoader(persist_ds, batch_size=config.batch_size, shuffle=False)

        # LM loader (for sliding window) - wraps same data for next-token prediction
        lm_train_ds = SyntheticLMDataset(
            vocab, SplitType.TRAIN, config.train_samples, config.seq_len + 10,
            chain_length=(3, 5), seed=42,
        )
        lm_val_ds = SyntheticLMDataset(
            vocab, SplitType.TEST_ROLES, config.test_samples, config.seq_len + 10,
            chain_length=(3, 5), seed=100,
        )
        lm_train_loader = DataLoader(lm_train_ds, batch_size=config.batch_size, shuffle=True)
        lm_val_loader = DataLoader(lm_val_ds, batch_size=config.batch_size, shuffle=False)

        print(f"  Synthetic: {len(train_ds)} train, {len(test_ds)} test, {len(persist_ds)} persist")
        print(f"  Vocab:     {vocab_size} tokens, {num_classes} entity classes")
    else:
        # WikiText real dataset
        lm_train_ds, lm_val_ds, vocab_size = load_wikitext(config.dataset, config.seq_len)
        lm_train_loader = DataLoader(lm_train_ds, batch_size=config.batch_size, shuffle=True, drop_last=True)
        lm_val_loader = DataLoader(lm_val_ds, batch_size=config.batch_size, shuffle=False, drop_last=True)
        config.vocab_size = vocab_size

        # No classifier data for real datasets
        vocab = None
        num_classes = None
        operation_tokens = None
        cls_train_loader = None
        cls_test_loader = None

        print(f"  WikiText:  {len(lm_train_ds)} train, {len(lm_val_ds)} val chunks")
        print(f"  Vocab:     {vocab_size} tokens")

    print()

    # ---- Run experiments ----
    results = {}

    for model_name in model_names:
        print(f"\n{'='*70}")
        print(f"  MODEL: {model_name.upper()}")
        print(f"{'='*70}")

        if model_name in ("quadratic", "phase") and config.dataset != "synthetic":
            print(f"  SKIPPING {model_name} (classifier model requires synthetic dataset)")
            continue

        for variant in ["baseline", "spanda"]:
            is_spanda = variant == "spanda"
            label = f"{model_name}_{variant}"
            print(f"\n  --- {label} ---")

            # Create model
            if model_name == "quadratic":
                if is_spanda:
                    backbone = HardProbeTransformer(
                        vocab_size=vocab_size, d_model=config.d_model, num_heads=config.num_heads,
                        num_layers=config.num_layers, d_ff=config.d_ff, dropout=0.0,
                        max_seq_len=config.max_seq_len, num_classes=num_classes, use_phase=False,
                    )
                    model = SpandaClassifierWrapper(
                        backbone, num_classes, psi_dim=config.psi_dim, decay_gamma=config.decay_gamma,
                    ).to(device)
                else:
                    model = HardProbeTransformer(
                        vocab_size=vocab_size, d_model=config.d_model, num_heads=config.num_heads,
                        num_layers=config.num_layers, d_ff=config.d_ff, dropout=0.0,
                        max_seq_len=config.max_seq_len, num_classes=num_classes, use_phase=False,
                    ).to(device)

            elif model_name == "phase":
                if is_spanda:
                    backbone = HardProbeTransformer(
                        vocab_size=vocab_size, d_model=config.d_model, num_heads=config.num_heads,
                        num_layers=config.num_layers, d_ff=config.d_ff, dropout=0.0,
                        max_seq_len=config.max_seq_len, num_classes=num_classes, use_phase=True,
                        operation_tokens=operation_tokens, bounded_phase=True,
                    )
                    model = SpandaClassifierWrapper(
                        backbone, num_classes, psi_dim=config.psi_dim, decay_gamma=config.decay_gamma,
                    ).to(device)
                else:
                    model = HardProbeTransformer(
                        vocab_size=vocab_size, d_model=config.d_model, num_heads=config.num_heads,
                        num_layers=config.num_layers, d_ff=config.d_ff, dropout=0.0,
                        max_seq_len=config.max_seq_len, num_classes=num_classes, use_phase=True,
                        operation_tokens=operation_tokens, bounded_phase=True,
                    ).to(device)

            elif model_name == "sliding_window":
                if is_spanda:
                    backbone = BindingCacheLMTransformer(
                        vocab_size=vocab_size, d_model=config.d_model, num_heads=config.num_heads,
                        num_layers=config.num_layers, d_ff=config.d_ff, dropout=0.0,
                        max_seq_len=config.max_seq_len, bounded_phase=True, top_k=16,
                        use_cache=True, decay_gamma=0.9, window_size=config.window_size,
                    )
                    model = SpandaLMWrapper(
                        backbone, psi_dim=config.psi_dim, decay_gamma=config.decay_gamma,
                    ).to(device)
                else:
                    model = BindingCacheLMTransformer(
                        vocab_size=vocab_size, d_model=config.d_model, num_heads=config.num_heads,
                        num_layers=config.num_layers, d_ff=config.d_ff, dropout=0.0,
                        max_seq_len=config.max_seq_len, bounded_phase=True, top_k=16,
                        use_cache=True, decay_gamma=0.9, window_size=config.window_size,
                    ).to(device)

            param_count = sum(p.numel() for p in model.parameters())
            print(f"  Parameters: {param_count:,}")

            # Train
            t0 = time.time()
            if model_name in ("quadratic", "phase"):
                losses = train_classifier_model(
                    model, cls_train_loader, vocab, device, config, use_spanda_reg=is_spanda,
                )
            else:
                losses = train_lm_model(
                    model, lm_train_loader, device, config, vocab_size, use_spanda_reg=is_spanda,
                )
            train_time = time.time() - t0

            # Evaluate
            final_loss = sum(losses[-20:]) / min(20, len(losses))
            final_ppl = math.exp(min(final_loss, 20))

            eval_result = {"final_loss": final_loss, "final_ppl": final_ppl, "params": param_count, "time_s": train_time}

            if model_name in ("quadratic", "phase") and cls_test_loader:
                test_acc = evaluate_classifier(model, cls_test_loader, vocab, device)
                eval_result["test_acc"] = test_acc
                print(f"  Test accuracy (held-out roles): {test_acc:.4f}")

            if model_name == "sliding_window":
                val_metrics = eval_lm(model, lm_val_loader, device, vocab_size)
                eval_result["val_loss"] = val_metrics["loss"]
                eval_result["val_ppl"] = val_metrics["perplexity"]
                print(f"  Val loss: {val_metrics['loss']:.4f} | Val PPL: {val_metrics['perplexity']:.1f}")

            print(f"  Final train loss: {final_loss:.4f} | PPL: {final_ppl:.1f}")
            print(f"  Train time: {train_time:.1f}s")

            results[label] = eval_result
            del model
            torch.cuda.empty_cache() if torch.cuda.is_available() else None

    # ---- Summary ----
    print(f"\n\n{'='*80}")
    print("SPANDA BENEFIT SUMMARY")
    print(f"{'='*80}")
    print(f"{'Model':<25} {'Variant':<10} {'Loss':>8} {'PPL':>8} {'Acc':>8} {'Params':>10} {'Time':>8}")
    print(f"{'-'*80}")

    for key, r in sorted(results.items()):
        parts = key.rsplit("_", 1)
        model_name = parts[0]
        variant = parts[1]
        acc_str = f"{r.get('test_acc', r.get('val_loss', 0)):.4f}" if "test_acc" in r or "val_loss" in r else "N/A"
        print(f"{model_name:<25} {variant:<10} {r['final_loss']:>8.4f} {r['final_ppl']:>8.1f} "
              f"{acc_str:>8} {r['params']:>10,} {r['time_s']:>7.1f}s")

    # Compute deltas
    print(f"\n{'='*80}")
    print("SPANDA BENEFIT DELTAS")
    print(f"{'='*80}")
    print(f"{'Architecture':<25} {'Loss Delta':>12} {'Direction':>12} {'Expected':>12}")
    print(f"{'-'*80}")

    expected = {"quadratic": "marginal", "phase": "uncertain", "sliding_window": "highest"}

    for model_name in model_names:
        base_key = f"{model_name}_baseline"
        spanda_key = f"{model_name}_spanda"
        if base_key in results and spanda_key in results:
            loss_delta = results[spanda_key]["final_loss"] - results[base_key]["final_loss"]
            direction = "BETTER" if loss_delta < -0.01 else ("WORSE" if loss_delta > 0.01 else "NEUTRAL")
            print(f"{model_name:<25} {loss_delta:>+12.4f} {direction:>12} {expected.get(model_name, ''):>12}")

            if "test_acc" in results[base_key] and "test_acc" in results[spanda_key]:
                acc_delta = results[spanda_key]["test_acc"] - results[base_key]["test_acc"]
                acc_dir = "BETTER" if acc_delta > 0.01 else ("WORSE" if acc_delta < -0.01 else "NEUTRAL")
                print(f"{'  (accuracy)':<25} {acc_delta:>+12.4f} {acc_dir:>12}")

    print(f"{'='*80}")

    # Save results
    os.makedirs(config.output_dir, exist_ok=True)
    results_path = os.path.join(config.output_dir, "results.json")
    with open(results_path, "w") as f:
        json.dump({"config": asdict(config), "results": results}, f, indent=2)
    print(f"\nResults saved to {results_path}")


if __name__ == "__main__":
    main()
