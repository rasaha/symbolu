#!/usr/bin/env python3
"""
Long Range Arena (LRA) Benchmark Training Script
=================================================

Train and evaluate SymbolU models on LRA tasks to demonstrate
long-range dependency learning with O(n) attention.

LRA Tasks:
----------
- listops: Hierarchical math operations (2K tokens)
- text: IMDb sentiment classification (4K tokens)
- retrieval: Document matching (4K tokens)
- image: CIFAR-10 as pixel sequence (1K tokens)
- pathfinder: Path detection (1K tokens)
- pathx: Extended pathfinder (16K tokens) - THE HEADLINE TASK

Usage:
------
    # Quick validation (8K, 2000 steps)
    python train_lra.py --task pathfinder --model_type hybrid \
        --seq_len 8192 --max_steps 2000

    # Headline result (16K Path-X)
    python train_lra.py --task pathx --model_type hybrid \
        --seq_len 16384 --max_steps 5000 --gradient_checkpointing

    # Full benchmark
    python train_lra.py --task pathx --model_type hybrid \
        --seq_len 16384 --max_steps 20000 --gradient_checkpointing

Author: SymbolU Team
Date: December 2025
"""

import argparse
import collections
import json
import math
import os
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Optional, Tuple, List

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader, TensorDataset
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR

import numpy as np

# Local imports
sys.path.insert(0, str(Path(__file__).parent))

from symbolu.phase_transformer import (
    PhaseTransformer,
    HybridPhaseTransformer,
    TransformerConfig,
    LocalTransformerBlock,
    HybridTransformerBlock,
    PhaseTransformerBlock,
)


# =============================================================================
# PERFORMANCE OPTIMIZATIONS
# =============================================================================
# TF32 for faster matrix multiplications on Ampere+ GPUs (A100, H100)
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True

# cuDNN autotuning for optimal convolution algorithms
torch.backends.cudnn.benchmark = True


# =============================================================================
# LRA TASK CONFIGURATIONS
# =============================================================================

LRA_TASKS = {
    "listops": {
        "seq_len": 2048,
        "num_classes": 10,
        "vocab_size": 32,
        "description": "Hierarchical math operations",
    },
    "text": {
        "seq_len": 4096,
        "num_classes": 2,
        "vocab_size": 256,  # byte-level
        "description": "IMDb sentiment classification",
    },
    "retrieval": {
        "seq_len": 4096,
        "num_classes": 2,
        "vocab_size": 256,
        "description": "Document matching",
    },
    "image": {
        "seq_len": 1024,
        "num_classes": 10,
        "vocab_size": 256,
        "description": "CIFAR-10 pixel sequence",
    },
    "pathfinder": {
        "seq_len": 1024,
        "num_classes": 2,
        "vocab_size": 256,
        "description": "Path detection in images",
    },
    "pathx": {
        "seq_len": 16384,
        "num_classes": 2,
        "vocab_size": 256,
        "description": "Extended pathfinder (16K) - HARDEST",
    },
}


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class LRAConfig:
    """Configuration for LRA training."""

    # Task
    task: str = "pathfinder"
    seq_len: Optional[int] = None  # Override task default

    # Model
    model_type: str = "hybrid"  # phase, hybrid
    num_refine: int = 1  # Iterative refinement passes per block
    model_size: str = "small"
    embed_dim: Optional[int] = None  # None = use preset
    num_layers: Optional[int] = None  # None = use preset
    num_heads: Optional[int] = None  # None = use preset
    ff_dim: Optional[int] = None  # None = use preset
    dropout: float = 0.1

    # Hybrid-specific
    local_layers: int = 2
    window_size: int = 256
    local_backend: str = "unfold"
    alpha_local: float = 0.8
    alpha_phase: float = 0.2

    # Layer pattern for hybrid models (Grok's suggestion)
    # local_first: L-L-L-L-H-H-H-H (default, current behavior)
    # interleave: L-H-L-H-L-H-L-H (alternating for text tasks)
    # phase_first: H-H-H-H-L-L-L-L (global context first)
    layer_pattern: str = "local_first"

    # Byte n-gram convolution for text task (Grok's suggestion)
    # Adds 1D conv layer to capture local byte patterns before transformer
    use_byte_conv: bool = False
    byte_conv_kernel: int = 5  # Kernel size for byte n-gram conv

    # Phase attention temperature (from patent formulas analysis)
    # Lower temperature = sharper attention (helps classification)
    # Higher temperature = smoother attention (default for generation)
    phase_temperature: float = 1.0

    # Pooling type for classification head
    # mean: Average pooling (default, good for structural tasks)
    # attention: SoftmaxAttentionPooler (sharp attention, best for classification)
    # cls: First token (CLS-style)
    # last: Last token
    pool_type: str = "mean"

    # Training
    batch_size: int = 32
    gradient_accumulation: int = 1
    max_steps: int = 20000
    warmup_steps: int = 1000
    learning_rate: float = 1e-4
    weight_decay: float = 0.01
    max_grad_norm: float = 1.0

    # Memory
    gradient_checkpointing: bool = False
    mixed_precision: str = "bf16"

    # Logging
    log_every: int = 100
    eval_every: int = 500
    save_every: int = 2000
    checkpoint_dir: str = "checkpoints_lra"

    # Hardware
    device: str = "auto"
    num_workers: int = 4
    seed: int = 42


MODEL_PRESETS = {
    "tiny": {"embed_dim": 128, "num_layers": 4, "num_heads": 2, "ff_dim": 512},
    "small": {"embed_dim": 256, "num_layers": 6, "num_heads": 4, "ff_dim": 1024},
    "medium": {"embed_dim": 512, "num_layers": 8, "num_heads": 8, "ff_dim": 2048},
    "large": {"embed_dim": 768, "num_layers": 12, "num_heads": 12, "ff_dim": 3072},
}


# =============================================================================
# SYNTHETIC LRA DATA GENERATION
# =============================================================================

def generate_pathfinder_data(
    num_samples: int,
    seq_len: int,
    difficulty: str = "medium",
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Generate synthetic Pathfinder-like data.

    Task: Given a sequence representing an image with dots and lines,
    determine if there's a connected path between two marked endpoints.

    This is a simplified version for testing. For full benchmark,
    download actual LRA datasets.
    """
    # Image dimensions (square root of seq_len, approximately)
    img_size = int(np.sqrt(seq_len))
    if img_size * img_size < seq_len:
        img_size += 1

    X = []
    y = []

    for _ in range(num_samples):
        # Create blank image
        img = np.zeros(seq_len, dtype=np.int64)

        # Randomly decide if path exists
        has_path = np.random.rand() > 0.5

        if has_path:
            # Create a path from start to end
            path_len = seq_len // 4
            start = np.random.randint(0, seq_len // 2)

            # Simple path: linear with some noise
            path_positions = []
            pos = start
            for i in range(path_len):
                path_positions.append(pos)
                # Move forward with some variation
                step = np.random.randint(1, 4)
                pos = min(pos + step, seq_len - 1)

            # Mark path
            for p in path_positions:
                img[p] = 128 + np.random.randint(-20, 20)

            # Mark endpoints distinctly
            img[path_positions[0]] = 255
            img[path_positions[-1]] = 255

            label = 1
        else:
            # Create disconnected segments
            for _ in range(3):
                start = np.random.randint(0, seq_len - 50)
                length = np.random.randint(10, 50)
                for i in range(length):
                    if start + i < seq_len:
                        img[start + i] = 128 + np.random.randint(-20, 20)

            # Mark two random points as "endpoints" (not connected)
            p1 = np.random.randint(0, seq_len // 2)
            p2 = np.random.randint(seq_len // 2, seq_len)
            img[p1] = 255
            img[p2] = 255

            label = 0

        # Add noise
        noise_mask = np.random.rand(seq_len) < 0.05
        img[noise_mask] = np.random.randint(0, 64, size=noise_mask.sum())

        X.append(img)
        y.append(label)

    return torch.tensor(np.array(X), dtype=torch.long), torch.tensor(y, dtype=torch.long)


def generate_listops_data(
    num_samples: int,
    seq_len: int,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Generate synthetic ListOps-like data.

    Task: Evaluate nested mathematical expressions.
    Example: [MAX 2 [MIN 3 4] 5] -> 5

    Simplified version for testing.
    """
    # Vocabulary: digits 0-9, operations (MIN, MAX, MED, SM), brackets, padding
    # 0-9: digits, 10: MIN, 11: MAX, 12: MED, 13: SM, 14: [, 15: ], 16: PAD

    X = []
    y = []

    ops = {10: min, 11: max, 12: lambda x: sorted(x)[len(x)//2] if x else 0}

    for _ in range(num_samples):
        seq = np.full(seq_len, 16, dtype=np.int64)  # PAD

        # Generate a simple expression
        depth = np.random.randint(2, 5)
        expr_tokens = []
        values_stack = []

        def generate_expr(d):
            if d == 0 or np.random.rand() < 0.3:
                # Terminal: digit
                val = np.random.randint(0, 10)
                return [val], val
            else:
                # Non-terminal: operation
                op = np.random.choice([10, 11])  # MIN or MAX
                num_args = np.random.randint(2, 4)

                tokens = [14, op]  # [ OP
                vals = []
                for _ in range(num_args):
                    sub_tokens, sub_val = generate_expr(d - 1)
                    tokens.extend(sub_tokens)
                    vals.append(sub_val)
                tokens.append(15)  # ]

                if op == 10:
                    result = min(vals)
                else:
                    result = max(vals)

                return tokens, result

        tokens, result = generate_expr(depth)

        # Truncate or pad
        if len(tokens) > seq_len:
            tokens = tokens[:seq_len]

        seq[:len(tokens)] = tokens

        X.append(seq)
        y.append(result % 10)  # Class 0-9

    return torch.tensor(np.array(X), dtype=torch.long), torch.tensor(y, dtype=torch.long)


def generate_text_data(
    num_samples: int,
    seq_len: int,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Generate synthetic text classification data.

    Task: Binary sentiment classification based on keyword patterns.
    Simplified version - actual LRA uses byte-level IMDb.
    """
    # Positive and negative patterns
    positive_words = [ord(c) for c in "goodgreatexcellentamazinglovewonderful"]
    negative_words = [ord(c) for c in "badterribleawfulhateworst"]
    neutral = [ord(c) for c in "thequickbrownfoxjumpsoverthelazydog "]

    X = []
    y = []

    for _ in range(num_samples):
        seq = np.zeros(seq_len, dtype=np.int64)

        # Fill with neutral text
        for i in range(seq_len):
            seq[i] = np.random.choice(neutral)

        # Decide sentiment
        is_positive = np.random.rand() > 0.5

        # Insert sentiment words at random positions
        keywords = positive_words if is_positive else negative_words
        num_insertions = np.random.randint(3, 8)

        for _ in range(num_insertions):
            pos = np.random.randint(0, seq_len - 20)
            word_len = np.random.randint(4, 10)
            for j in range(word_len):
                if pos + j < seq_len:
                    seq[pos + j] = np.random.choice(keywords)

        X.append(seq)
        y.append(1 if is_positive else 0)

    return torch.tensor(np.array(X), dtype=torch.long), torch.tensor(y, dtype=torch.long)


def load_lra_data(
    task: str,
    seq_len: int,
    num_train: int = 50000,
    num_val: int = 5000,
) -> Tuple[DataLoader, DataLoader, int]:
    """
    Load or generate LRA data.

    Returns train_loader, val_loader, num_classes
    """
    task_info = LRA_TASKS[task]
    num_classes = task_info["num_classes"]

    print(f"Generating {task} data (seq_len={seq_len})...")

    if task in ["pathfinder", "pathx"]:
        train_X, train_y = generate_pathfinder_data(num_train, seq_len)
        val_X, val_y = generate_pathfinder_data(num_val, seq_len)
    elif task == "listops":
        train_X, train_y = generate_listops_data(num_train, seq_len)
        val_X, val_y = generate_listops_data(num_val, seq_len)
    elif task == "text":
        train_X, train_y = generate_text_data(num_train, seq_len)
        val_X, val_y = generate_text_data(num_val, seq_len)
    else:
        # Default to pathfinder-style for other tasks
        train_X, train_y = generate_pathfinder_data(num_train, seq_len)
        val_X, val_y = generate_pathfinder_data(num_val, seq_len)

    print(f"  Train: {len(train_X)} samples")
    print(f"  Val: {len(val_X)} samples")
    print(f"  Classes: {num_classes}")

    train_dataset = TensorDataset(train_X, train_y)
    val_dataset = TensorDataset(val_X, val_y)

    num_workers = 4
    train_loader = DataLoader(
        train_dataset,
        batch_size=32,  # Will be overridden
        shuffle=True,
        num_workers=num_workers,
        pin_memory=True,
        drop_last=True,
        prefetch_factor=2 if num_workers > 0 else None,
        persistent_workers=num_workers > 0,
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=32,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True,
        prefetch_factor=2 if num_workers > 0 else None,
        persistent_workers=num_workers > 0,
    )

    return train_loader, val_loader, num_classes


# =============================================================================
# SOFTMAX ATTENTION POOLER (Principled Classification Head)
# =============================================================================

class SoftmaxAttentionPooler(nn.Module):
    """
    Attention-based pooling using standard dot-product softmax attention.

    This is the principled fix for Phase attention's classification weakness:
    - Phase attention: smooth (phases converge → uniform attention)
    - Softmax attention: sharp (can focus on specific tokens)

    Uses a learnable query that attends over the sequence to find
    the most relevant tokens for classification (e.g., "not" in "not good").

    Architecture:
        query: [1, d_model] learnable parameter
        keys:  [B, N, d_model] from encoder hidden states
        values: [B, N, d_model] from encoder hidden states

        attention = softmax(query @ keys.T / sqrt(d))  # Sharp!
        output = attention @ values  # [B, d_model]
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int = 4,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads

        # Learnable query for classification (like CLS token but explicit)
        self.query = nn.Parameter(torch.randn(1, 1, embed_dim) * 0.02)

        # Project keys and values
        self.key_proj = nn.Linear(embed_dim, embed_dim)
        self.value_proj = nn.Linear(embed_dim, embed_dim)

        # Output projection
        self.out_proj = nn.Linear(embed_dim, embed_dim)
        self.dropout = nn.Dropout(dropout)

        # Temperature for sharpness (lower = sharper)
        self.temperature = nn.Parameter(torch.ones(1))

    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        """
        Args:
            hidden_states: [B, N, embed_dim] encoder output

        Returns:
            pooled: [B, embed_dim] classification-ready representation
        """
        B, N, D = hidden_states.shape

        # Expand query to batch
        query = self.query.expand(B, -1, -1)  # [B, 1, D]

        # Project keys and values
        keys = self.key_proj(hidden_states)    # [B, N, D]
        values = self.value_proj(hidden_states)  # [B, N, D]

        # Multi-head reshape
        query = query.view(B, 1, self.num_heads, self.head_dim).transpose(1, 2)  # [B, H, 1, d]
        keys = keys.view(B, N, self.num_heads, self.head_dim).transpose(1, 2)    # [B, H, N, d]
        values = values.view(B, N, self.num_heads, self.head_dim).transpose(1, 2)  # [B, H, N, d]

        # Compute attention scores (standard dot-product)
        scale = (self.head_dim ** -0.5) / self.temperature.clamp(min=0.1)
        scores = torch.matmul(query, keys.transpose(-2, -1)) * scale  # [B, H, 1, N]

        # SHARP softmax attention (not Phase's smooth mean-field!)
        attn_weights = F.softmax(scores, dim=-1)  # [B, H, 1, N]
        attn_weights = self.dropout(attn_weights)

        # Weighted sum of values
        context = torch.matmul(attn_weights, values)  # [B, H, 1, d]

        # Reshape and project
        context = context.transpose(1, 2).contiguous().view(B, 1, D)  # [B, 1, D]
        output = self.out_proj(context.squeeze(1))  # [B, D]

        return output


# =============================================================================
# PHASE PROTOTYPE CLASSIFIER (USE Formula-Inspired)
# =============================================================================

class PhasePrototypeClassifier(nn.Module):
    """
    Classification using phase alignment with learned class prototypes.

    Inspired by USE (Unified Semantic Encoding) phase locking formula:
        C[entity, attribute] = 1.0 → phase locked (same phase)
        C[entity, wrong_attr] = 0.0 → orthogonal (90° apart)

    For classification:
        - Each class has a learned phase prototype
        - Document phase is computed from token phases
        - Classification = which prototype is document phase closest to?

    This preserves Phase attention philosophy while enabling discrimination
    through phase-prototype alignment (orthogonal classes in phase space).

    Key insight: Classes are initialized π apart (orthogonal), so the
    document phase must commit to one side or the other - no averaging!
    """

    def __init__(
        self,
        embed_dim: int,
        num_classes: int,
        num_heads: int = 4,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_classes = num_classes
        self.num_heads = num_heads

        # Phase projection: hidden states → phase angles
        # Multi-head for richer phase representation
        self.phase_proj = nn.Sequential(
            nn.Linear(embed_dim, embed_dim),
            nn.GELU(),
            nn.Linear(embed_dim, num_heads),
        )

        # Learnable class prototypes in phase space
        # Initialize evenly spaced around the circle for maximum separation
        # For binary: 0 and π (orthogonal)
        # For 10-class: 0, 0.628, 1.257, ... (evenly spaced)
        initial_phases = torch.linspace(0, 2 * math.pi * (num_classes - 1) / num_classes, num_classes)
        self.class_phases = nn.Parameter(initial_phases.unsqueeze(0).expand(num_heads, -1).clone())
        # Shape: [num_heads, num_classes]

        # Attention weights for token importance (which tokens matter for phase)
        self.token_importance = nn.Sequential(
            nn.Linear(embed_dim, embed_dim // 2),
            nn.GELU(),
            nn.Linear(embed_dim // 2, 1),
        )

        # Temperature for sharper classification
        self.temperature = nn.Parameter(torch.ones(1) * 0.5)

        # Final projection to combine heads
        self.head_weights = nn.Parameter(torch.ones(num_heads) / num_heads)

        self.dropout = nn.Dropout(dropout)

        print(f"  PhasePrototypeClassifier: {num_classes} classes, {num_heads} heads")
        print(f"  Class phase prototypes initialized {360/num_classes:.1f}° apart")

    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        """
        Args:
            hidden_states: [B, N, embed_dim] encoder output

        Returns:
            logits: [B, num_classes]
        """
        B, N, D = hidden_states.shape

        # Compute token phases [B, N, num_heads]
        token_phases = self.phase_proj(hidden_states)
        token_phases = torch.tanh(token_phases) * math.pi  # Bound to [-π, π]

        # Compute token importance weights [B, N, 1]
        importance = self.token_importance(hidden_states)
        importance = F.softmax(importance, dim=1)  # Normalize across sequence
        importance = self.dropout(importance)

        # Weighted circular mean for document phase
        # Use complex representation for proper circular averaging
        # z = exp(i*θ), then angle(mean(z)) gives circular mean
        complex_phases = torch.exp(1j * token_phases)  # [B, N, num_heads]
        weighted_complex = complex_phases * importance  # [B, N, num_heads]
        doc_complex = weighted_complex.sum(dim=1)  # [B, num_heads]
        doc_phase = torch.angle(doc_complex)  # [B, num_heads]

        # Compute similarity to each class prototype using phase difference
        # [B, num_heads, 1] - [num_heads, num_classes] → [B, num_heads, num_classes]
        phase_diffs = doc_phase.unsqueeze(2) - self.class_phases.unsqueeze(0)

        # Cosine similarity in phase space
        similarities = torch.cos(phase_diffs)  # [B, num_heads, num_classes]

        # Combine heads with learned weights
        head_weights = F.softmax(self.head_weights, dim=0)
        logits = (similarities * head_weights.view(1, -1, 1)).sum(dim=1)  # [B, num_classes]

        # Temperature scaling for sharper decisions
        logits = logits / self.temperature.clamp(min=0.1)

        return logits


# =============================================================================
# MODEL WITH CLASSIFICATION HEAD
# =============================================================================

class LRAClassifier(nn.Module):
    """
    Wrapper that adds classification head to transformer encoder.

    Supports:
    - Softmax attention pooler for sharp classification
    - Phase prototype classifier (USE formula-inspired)
    - Byte n-gram convolution for text tasks (Grok's suggestion)

    Pool types:
    - mean: Average all positions (default, works for structural tasks)
    - attention: SoftmaxAttentionPooler (sharp attention, for classification)
    - phase_prototype: PhasePrototypeClassifier (USE-inspired, classes as orthogonal phases)
    - cls: Use first token (CLS-style)
    - last: Use last token
    """

    def __init__(
        self,
        encoder: nn.Module,
        embed_dim: int,
        num_classes: int,
        vocab_size: int,
        num_heads: int = 4,
        pool: str = "mean",  # mean, attention, phase_prototype, cls, last
        num_refine: int = 1,  # Iterative refinement passes per block
        use_byte_conv: bool = False,  # Add 1D conv for byte n-grams
        byte_conv_kernel: int = 5,  # Kernel size for byte n-gram conv
        dropout: float = 0.1,
    ):
        super().__init__()
        self.encoder = encoder
        self.pool = pool
        self.num_classes = num_classes
        self.num_refine = num_refine
        self.use_byte_conv = use_byte_conv
        self.embed_dim = embed_dim

        # Replace embedding if vocab size differs
        if hasattr(encoder, 'embed'):
            old_vocab = encoder.embed.num_embeddings
            if old_vocab != vocab_size:
                encoder.embed = nn.Embedding(vocab_size, embed_dim)

        # Byte n-gram convolution layer (Grok's suggestion)
        # Captures local byte patterns (e.g., "not" in "not good") before transformer
        if use_byte_conv:
            self.byte_conv = nn.Sequential(
                nn.Conv1d(embed_dim, embed_dim, kernel_size=byte_conv_kernel,
                          padding=byte_conv_kernel // 2, groups=1),
                nn.GELU(),
                nn.Conv1d(embed_dim, embed_dim, kernel_size=byte_conv_kernel,
                          padding=byte_conv_kernel // 2, groups=1),
            )
        else:
            self.byte_conv = None

        # Softmax attention pooler (principled fix for classification)
        # Uses standard dot-product attention instead of Phase's smooth attention
        if pool == "attention":
            self.attention_pooler = SoftmaxAttentionPooler(
                embed_dim=embed_dim,
                num_heads=num_heads,
                dropout=dropout,
            )
            self.phase_prototype = None
            print("  Using SoftmaxAttentionPooler for classification (sharp attention)")
        elif pool == "phase_prototype":
            # USE formula-inspired: classes as orthogonal phase prototypes
            # Document phase aligns with correct class prototype
            self.phase_prototype = PhasePrototypeClassifier(
                embed_dim=embed_dim,
                num_classes=num_classes,
                num_heads=num_heads,
                dropout=dropout,
            )
            self.attention_pooler = None
            print("  Using PhasePrototypeClassifier (USE formula: orthogonal class phases)")
        else:
            self.attention_pooler = None
            self.phase_prototype = None

        # Classification head (not used for phase_prototype)
        self.classifier = nn.Sequential(
            nn.Linear(embed_dim, embed_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(embed_dim, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: [B, seq_len] input token ids

        Returns:
            logits: [B, num_classes]
        """
        # Get encoder output
        # For transformers that return logits, we need hidden states
        if hasattr(self.encoder, 'get_hidden_states'):
            hidden = self.encoder.get_hidden_states(x)
        else:
            # Use embedding + layers directly
            B, N = x.shape

            # Embedding (handle different naming conventions)
            if hasattr(self.encoder, 'token_embed'):
                h = self.encoder.token_embed(x)
            elif hasattr(self.encoder, 'embed'):
                h = self.encoder.embed(x)
            else:
                raise AttributeError("Encoder has no embed or token_embed attribute")

            # Position embedding
            if hasattr(self.encoder, 'pos_embed'):
                pos = torch.arange(N, device=x.device)
                h = h + self.encoder.pos_embed(pos)

            # Byte n-gram convolution (Grok's suggestion)
            # Applied AFTER embedding, BEFORE transformer layers
            # Captures local byte patterns like "not", "good", "bad"
            if self.byte_conv is not None:
                # Conv1d expects [B, C, N], we have [B, N, C]
                h_conv = h.transpose(1, 2)  # [B, embed_dim, N]
                h_conv = self.byte_conv(h_conv)  # [B, embed_dim, N]
                h = h + h_conv.transpose(1, 2)  # Residual connection [B, N, embed_dim]

            # Dropout
            if hasattr(self.encoder, 'embed_dropout'):
                h = self.encoder.embed_dropout(h)

            # Process through layers with iterative refinement (full-pass)
            # Each refinement pass goes through ALL blocks, like Universal Transformer
            for _ in range(self.num_refine):
                if hasattr(self.encoder, 'layers'):
                    for layer in self.encoder.layers:
                        h = layer(h)
                elif hasattr(self.encoder, 'blocks'):
                    for block in self.encoder.blocks:
                        h = block(h)

            hidden = h  # [B, N, embed_dim]

        # Phase prototype classifier bypasses pooling - does both pooling and classification
        if self.pool == "phase_prototype":
            # USE formula-inspired: classify by phase alignment with class prototypes
            logits = self.phase_prototype(hidden)  # [B, num_classes]
            return logits

        # Pool sequence to single vector
        if self.pool == "attention":
            # Use SoftmaxAttentionPooler (sharp, discriminative attention)
            pooled = self.attention_pooler(hidden)  # [B, embed_dim]
        elif self.pool == "mean":
            pooled = hidden.mean(dim=1)  # [B, embed_dim]
        elif self.pool == "cls":
            pooled = hidden[:, 0]
        elif self.pool == "last":
            pooled = hidden[:, -1]
        else:
            pooled = hidden.mean(dim=1)

        # Classify
        logits = self.classifier(pooled)

        return logits


class InterleavedHybridEncoder(nn.Module):
    """
    Custom hybrid encoder with configurable layer patterns.

    Supports Grok's suggestions for text classification:
    - interleave: L-H-L-H-L-H-L-H (alternating local and hybrid)
    - phase_first: H-H-H-H-L-L-L-L (global context first, then local refine)
    """

    def __init__(
        self,
        vocab_size: int,
        embed_dim: int,
        num_layers: int,
        num_heads: int,
        ff_dim: int,
        max_seq_len: int,
        dropout: float,
        layer_pattern: str,  # interleave, phase_first
        window_size: int,
        local_backend: str,
        alpha_local: float,
        alpha_phase: float,
        temperature: float = 1.0,  # Lower = sharper attention
    ):
        super().__init__()

        self.config = TransformerConfig(
            vocab_size=vocab_size,
            embed_dim=embed_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            ff_dim=ff_dim,
            max_seq_len=max_seq_len,
            dropout=dropout,
            temperature=temperature,  # Pass temperature for sharper attention
        )

        # Embeddings
        self.token_embed = nn.Embedding(vocab_size, embed_dim)
        self.pos_embed = nn.Embedding(max_seq_len, embed_dim)
        self.embed_dropout = nn.Dropout(dropout)

        # Build blocks based on pattern
        self.blocks = nn.ModuleList()

        for i in range(num_layers):
            if layer_pattern == "interleave":
                # L-H-L-H-L-H: even=local, odd=hybrid
                if i % 2 == 0:
                    self.blocks.append(LocalTransformerBlock(
                        self.config, window_size=window_size, backend=local_backend))
                else:
                    self.blocks.append(HybridTransformerBlock(
                        self.config, window_size=window_size, local_backend=local_backend,
                        alpha_local=alpha_local, alpha_phase=alpha_phase))
            elif layer_pattern == "phase_first":
                # H-H-H-H-L-L-L-L: first half hybrid, second half local
                if i < num_layers // 2:
                    self.blocks.append(HybridTransformerBlock(
                        self.config, window_size=window_size, local_backend=local_backend,
                        alpha_local=alpha_local, alpha_phase=alpha_phase))
                else:
                    self.blocks.append(LocalTransformerBlock(
                        self.config, window_size=window_size, backend=local_backend))
            else:
                raise ValueError(f"Unknown layer pattern: {layer_pattern}")

        # Final norm
        self.final_norm = nn.LayerNorm(embed_dim)

        # LM head (not used for classification, but needed for structure)
        self.lm_head = nn.Linear(embed_dim, vocab_size, bias=False)

        print(f"  InterleavedHybridEncoder: {layer_pattern} pattern")
        pattern_str = "".join(["L" if isinstance(b, LocalTransformerBlock) else "H"
                               for b in self.blocks])
        print(f"  Layer pattern: {pattern_str}")


def create_lra_model(config: LRAConfig, num_classes: int, vocab_size: int, device: torch.device) -> nn.Module:
    """Create model for LRA task."""

    preset = MODEL_PRESETS.get(config.model_size, MODEL_PRESETS["small"])
    embed_dim = config.embed_dim or preset["embed_dim"]
    num_layers = config.num_layers or preset["num_layers"]
    num_heads = config.num_heads or preset["num_heads"]
    ff_dim = config.ff_dim or preset["ff_dim"]

    seq_len = config.seq_len or LRA_TASKS[config.task]["seq_len"]

    if config.model_type == "phase":
        encoder = PhaseTransformer(
            vocab_size=vocab_size,
            embed_dim=embed_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            ff_dim=ff_dim,
            max_seq_len=seq_len,
            dropout=config.dropout,
            temperature=config.phase_temperature,  # Sharper attention for classification
        )
    elif config.model_type == "hybrid":
        # Check layer pattern
        if config.layer_pattern in ["interleave", "phase_first"]:
            # Use custom interleaved encoder (Grok's suggestion)
            encoder = InterleavedHybridEncoder(
                vocab_size=vocab_size,
                embed_dim=embed_dim,
                num_layers=num_layers,
                num_heads=num_heads,
                ff_dim=ff_dim,
                max_seq_len=seq_len,
                dropout=config.dropout,
                layer_pattern=config.layer_pattern,
                window_size=config.window_size,
                local_backend=config.local_backend,
                alpha_local=config.alpha_local,
                alpha_phase=config.alpha_phase,
                temperature=config.phase_temperature,  # Sharper attention for classification
            )
        else:
            # Default: local_first pattern (L-L-L-L-H-H-H-H)
            encoder = HybridPhaseTransformer(
                vocab_size=vocab_size,
                embed_dim=embed_dim,
                num_layers=num_layers,
                num_heads=num_heads,
                ff_dim=ff_dim,
                max_seq_len=seq_len,
                dropout=config.dropout,
                local_layers=config.local_layers,
                window_size=config.window_size,
                local_backend=config.local_backend,
                alpha_local=config.alpha_local,
                alpha_phase=config.alpha_phase,
                temperature=config.phase_temperature,  # Sharper attention for classification
            )
    else:
        raise ValueError(f"Unknown model type: {config.model_type}")

    # Enable gradient checkpointing after model creation
    if config.gradient_checkpointing:
        if hasattr(encoder, 'gradient_checkpointing_enable'):
            encoder.gradient_checkpointing_enable()
        else:
            for module in encoder.modules():
                if hasattr(module, 'gradient_checkpointing'):
                    module.gradient_checkpointing = True

    # Auto-enable byte_conv for text task if not explicitly set
    use_byte_conv = config.use_byte_conv
    if config.task == "text" and not use_byte_conv:
        print("  Note: Consider --use_byte_conv for text task (Grok's suggestion)")

    # Auto-suggest attention pooler for text classification
    pool_type = config.pool_type
    if config.task == "text" and pool_type == "mean":
        print("  Note: Consider --pool_type attention for text classification")

    model = LRAClassifier(
        encoder=encoder,
        embed_dim=embed_dim,
        num_classes=num_classes,
        vocab_size=vocab_size,
        num_heads=num_heads,
        pool=pool_type,
        num_refine=config.num_refine,
        use_byte_conv=use_byte_conv,
        byte_conv_kernel=config.byte_conv_kernel,
        dropout=config.dropout,
    )

    return model.to(device)


# =============================================================================
# TRAINING
# =============================================================================

def train_lra(config: LRAConfig):
    """Main training loop for LRA."""

    # Early banner
    print(f"\n{'='*70}")
    print("   LRA BENCHMARK TRAINING")
    print("   Long Range Arena for Efficient Attention")
    print(f"{'='*70}")

    torch.manual_seed(config.seed)
    np.random.seed(config.seed)

    # Device
    if config.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(config.device)

    # Task info
    task_info = LRA_TASKS[config.task]
    seq_len = config.seq_len or task_info["seq_len"]
    vocab_size = task_info["vocab_size"]

    print(f"\n  Task: {config.task.upper()} - {task_info['description']}")
    print(f"  Sequence Length: {seq_len:,}")
    print(f"  Classes: {task_info['num_classes']}")
    print(f"  Model Type: {config.model_type.upper()}")
    print(f"  Model Size: {config.model_size}")
    print(f"  Batch Size: {config.batch_size}")
    print(f"  Max Steps: {config.max_steps:,}")
    print(f"  Learning Rate: {config.learning_rate}")
    print(f"  Device: {device}")
    print(f"  Gradient Checkpointing: {config.gradient_checkpointing}")
    print(f"  Mixed Precision: {config.mixed_precision}")
    print()

    # Load data
    train_loader, val_loader, num_classes = load_lra_data(
        config.task, seq_len,
        num_train=50000, num_val=5000,
    )

    # Override batch size with performance optimizations
    train_loader = DataLoader(
        train_loader.dataset,
        batch_size=config.batch_size,
        shuffle=True,
        num_workers=config.num_workers,
        pin_memory=True,
        drop_last=True,
        prefetch_factor=2 if config.num_workers > 0 else None,
        persistent_workers=config.num_workers > 0,
    )
    val_loader = DataLoader(
        val_loader.dataset,
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=config.num_workers,
        pin_memory=True,
        prefetch_factor=2 if config.num_workers > 0 else None,
        persistent_workers=config.num_workers > 0,
    )

    # Create model
    model = create_lra_model(config, num_classes, vocab_size, device)
    num_params = sum(p.numel() for p in model.parameters())
    print(f"\n  Model Parameters: {num_params:,} ({num_params/1e6:.1f}M)")

    # Optimizer
    optimizer = AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )

    # Scheduler
    scheduler = CosineAnnealingLR(
        optimizer,
        T_max=config.max_steps - config.warmup_steps,
        eta_min=config.learning_rate * 0.1,
    )

    # Mixed precision
    scaler = torch.cuda.amp.GradScaler() if config.mixed_precision != "none" else None
    autocast_dtype = torch.bfloat16 if config.mixed_precision == "bf16" else torch.float16

    # Checkpoint directory
    ckpt_dir = Path(config.checkpoint_dir) / config.task
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    # Save config
    with open(ckpt_dir / "config.json", "w") as f:
        json.dump(asdict(config), f, indent=2)

    print(f"\n{'='*70}")
    print("   STARTING TRAINING")
    print(f"{'='*70}\n")

    # Training state
    global_step = 0
    best_val_acc = 0.0
    best_loss = float('inf')
    spike_count = 0
    train_iter = iter(train_loader)

    model.train()
    step_start_time = time.time()
    running_loss = 0.0
    running_correct = 0
    running_total = 0

    while global_step < config.max_steps:
        # Get batch
        try:
            x, y = next(train_iter)
        except StopIteration:
            train_iter = iter(train_loader)
            x, y = next(train_iter)

        x, y = x.to(device), y.to(device)

        # Forward
        with torch.cuda.amp.autocast(dtype=autocast_dtype):
            logits = model(x)
            loss = F.cross_entropy(logits, y)

        # Backward
        if scaler is not None:
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), config.max_grad_norm)
            scaler.step(optimizer)
            scaler.update()
        else:
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), config.max_grad_norm)
            optimizer.step()

        optimizer.zero_grad()

        if global_step >= config.warmup_steps:
            scheduler.step()

        # Track metrics
        global_step += 1
        running_loss += loss.item()
        preds = logits.argmax(dim=-1)
        running_correct += (preds == y).sum().item()
        running_total += y.size(0)

        # Logging
        if global_step % config.log_every == 0:
            elapsed = time.time() - step_start_time
            avg_loss = running_loss / config.log_every
            acc = running_correct / running_total * 100
            lr = optimizer.param_groups[0]["lr"]

            # Memory
            if device.type == "cuda":
                mem = torch.cuda.max_memory_allocated() / (1024**3)
                mem_str = f" | VRAM: {mem:.1f}GB"
            else:
                mem_str = ""

            print(f"Step {global_step:>6} | Loss: {avg_loss:.4f} | "
                  f"Acc: {acc:.1f}% | LR: {lr:.2e}{mem_str}")

            # Adaptive LR on loss spike
            if avg_loss < best_loss:
                best_loss = avg_loss
            elif global_step > config.warmup_steps:
                if avg_loss > best_loss * 2.0:
                    # MAJOR SPIKE: 0.7x LR + momentum reset
                    spike_count += 1
                    old_lr = optimizer.param_groups[0]['lr']
                    new_lr = old_lr * 0.7
                    optimizer.state = collections.defaultdict(dict)
                    for pg in optimizer.param_groups:
                        pg['lr'] = new_lr
                    print(f"  🚨 MAJOR spike ({avg_loss:.4f} > {best_loss:.4f}*2)! LR: {old_lr:.2e} → {new_lr:.2e} + momentum reset")
                elif avg_loss > best_loss * 1.5:
                    # MODERATE SPIKE: 0.7x LR + momentum reset
                    spike_count += 1
                    old_lr = optimizer.param_groups[0]['lr']
                    new_lr = old_lr * 0.7
                    optimizer.state = collections.defaultdict(dict)
                    for pg in optimizer.param_groups:
                        pg['lr'] = new_lr
                    print(f"  ⚠️ Loss spike ({avg_loss:.4f} > {best_loss:.4f}*1.5)! LR: {old_lr:.2e} → {new_lr:.2e} + momentum reset")
                elif avg_loss > best_loss * 1.3:
                    # MINOR SPIKE: 0.85x LR only
                    old_lr = optimizer.param_groups[0]['lr']
                    new_lr = old_lr * 0.85
                    for pg in optimizer.param_groups:
                        pg['lr'] = new_lr
                    print(f"  ⚡ Minor spike ({avg_loss:.4f} > {best_loss:.4f}*1.3). LR: {old_lr:.2e} → {new_lr:.2e}")

            running_loss = 0.0
            running_correct = 0
            running_total = 0
            step_start_time = time.time()

        # Evaluation
        if global_step % config.eval_every == 0:
            val_loss, val_acc = evaluate_lra(model, val_loader, device, autocast_dtype)
            print(f"  --> Val Loss: {val_loss:.4f} | Val Acc: {val_acc:.1f}%")

            if val_acc > best_val_acc:
                best_val_acc = val_acc
                torch.save({
                    "model": model.state_dict(),
                    "step": global_step,
                    "val_acc": val_acc,
                }, ckpt_dir / "best.pt")
                print(f"  --> New best! Saved to {ckpt_dir / 'best.pt'}")

            model.train()

        # Save checkpoint
        if global_step % config.save_every == 0:
            torch.save({
                "model": model.state_dict(),
                "optimizer": optimizer.state_dict(),
                "step": global_step,
            }, ckpt_dir / f"step_{global_step}.pt")

    # Final evaluation
    val_loss, val_acc = evaluate_lra(model, val_loader, device, autocast_dtype)

    print(f"\n{'='*70}")
    print("   TRAINING COMPLETE")
    print(f"{'='*70}")
    print(f"  Task: {config.task}")
    print(f"  Sequence Length: {seq_len:,}")
    print(f"  Total Steps: {global_step:,}")
    print(f"  Best Val Accuracy: {best_val_acc:.1f}%")
    print(f"  Final Val Accuracy: {val_acc:.1f}%")

    # Save final
    torch.save({
        "model": model.state_dict(),
        "step": global_step,
        "val_acc": val_acc,
        "best_val_acc": best_val_acc,
    }, ckpt_dir / "final.pt")

    return best_val_acc


def evaluate_lra(
    model: nn.Module,
    val_loader: DataLoader,
    device: torch.device,
    autocast_dtype: torch.dtype,
) -> Tuple[float, float]:
    """Evaluate on validation set."""
    model.eval()

    total_loss = 0.0
    total_correct = 0
    total_samples = 0

    with torch.no_grad():
        for x, y in val_loader:
            x, y = x.to(device), y.to(device)

            with torch.cuda.amp.autocast(dtype=autocast_dtype):
                logits = model(x)
                loss = F.cross_entropy(logits, y)

            total_loss += loss.item() * y.size(0)
            preds = logits.argmax(dim=-1)
            total_correct += (preds == y).sum().item()
            total_samples += y.size(0)

    avg_loss = total_loss / total_samples
    accuracy = total_correct / total_samples * 100

    return avg_loss, accuracy


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="LRA Benchmark Training",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Task
    parser.add_argument("--task", type=str, default="pathfinder",
                       choices=list(LRA_TASKS.keys()),
                       help="LRA task")
    parser.add_argument("--seq_len", type=int, default=None,
                       help="Override sequence length")

    # Model
    parser.add_argument("--model_type", type=str, default="hybrid",
                       choices=["phase", "hybrid"],
                       help="Model architecture")
    parser.add_argument("--num_refine", type=int, default=1,
                       help="Iterative refinement passes per block (2-3 for ListOps)")
    parser.add_argument("--model_size", type=str, default="small",
                       choices=["tiny", "small", "medium", "large"],
                       help="Model size preset")

    # Training
    parser.add_argument("--batch_size", type=int, default=32,
                       help="Batch size")
    parser.add_argument("--max_steps", type=int, default=20000,
                       help="Maximum training steps")
    parser.add_argument("--learning_rate", type=float, default=1e-4,
                       help="Learning rate")

    # Memory
    parser.add_argument("--gradient_checkpointing", action="store_true",
                       help="Enable gradient checkpointing")
    parser.add_argument("--local_backend", type=str, default="unfold",
                       choices=["auto", "flash", "sdpa", "unfold"],
                       help="LocalAttention backend")
    parser.add_argument("--window_size", type=int, default=256,
                       help="Local attention window size")

    # Layer pattern (Grok's suggestion for text tasks)
    parser.add_argument("--layer_pattern", type=str, default="local_first",
                       choices=["local_first", "interleave", "phase_first"],
                       help="Layer ordering pattern: local_first (L-L-H-H), "
                            "interleave (L-H-L-H), phase_first (H-H-L-L)")

    # Byte n-gram convolution (Grok's suggestion for text tasks)
    parser.add_argument("--use_byte_conv", action="store_true",
                       help="Add 1D conv layer for byte n-gram patterns (good for text)")
    parser.add_argument("--byte_conv_kernel", type=int, default=5,
                       help="Kernel size for byte n-gram conv (default: 5 bytes)")

    # Alpha weights for hybrid attention
    parser.add_argument("--alpha_local", type=float, default=0.8,
                       help="Weight for local attention in hybrid layers")
    parser.add_argument("--alpha_phase", type=float, default=0.2,
                       help="Weight for phase attention in hybrid layers")

    # Phase attention temperature (patent formula enhancement)
    parser.add_argument("--phase_temperature", type=float, default=1.0,
                       help="Temperature for phase attention: lower=sharper (0.1-0.5 for classification)")

    # Pooling type for classification (principled fix for Phase attention)
    parser.add_argument("--pool_type", type=str, default="mean",
                       choices=["mean", "attention", "phase_prototype", "cls", "last"],
                       help="Pooling type: mean (default), attention (softmax pooler), phase_prototype (USE formula: orthogonal class phases)")

    # Logging
    parser.add_argument("--log_every", type=int, default=100,
                       help="Log every N steps")
    parser.add_argument("--eval_every", type=int, default=500,
                       help="Evaluate every N steps")
    parser.add_argument("--checkpoint_dir", type=str, default="checkpoints_lra",
                       help="Checkpoint directory")

    # Other
    parser.add_argument("--seed", type=int, default=42)

    args = parser.parse_args()

    config = LRAConfig(
        task=args.task,
        seq_len=args.seq_len,
        model_type=args.model_type,
        num_refine=args.num_refine,
        model_size=args.model_size,
        batch_size=args.batch_size,
        max_steps=args.max_steps,
        learning_rate=args.learning_rate,
        gradient_checkpointing=args.gradient_checkpointing,
        local_backend=args.local_backend,
        window_size=args.window_size,
        layer_pattern=args.layer_pattern,
        use_byte_conv=args.use_byte_conv,
        byte_conv_kernel=args.byte_conv_kernel,
        alpha_local=args.alpha_local,
        alpha_phase=args.alpha_phase,
        phase_temperature=args.phase_temperature,
        pool_type=args.pool_type,
        log_every=args.log_every,
        eval_every=args.eval_every,
        checkpoint_dir=args.checkpoint_dir,
        seed=args.seed,
    )

    train_lra(config)


if __name__ == "__main__":
    main()
