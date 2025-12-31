#!/usr/bin/env python3
"""
SymbolU LLM Training Script
============================

Production training script for Phase Attention Transformer with O(n) complexity.

Features:
- Dataset support: C4, WikiText-103, WikiText-2, or custom
- AdamW optimizer with cosine LR schedule and warmup
- Gradient clipping and accumulation
- Mixed precision (FP16/BF16) training
- Checkpointing with resume support
- Wandb/TensorBoard logging
- Multi-GPU support via DDP
- Evaluation with perplexity tracking

Usage:
------
# Quick test (small model, WikiText-2)
python train.py --model_size tiny --dataset wikitext2 --max_steps 1000

# Train 50M model on C4
python train.py --model_size small --dataset c4 --max_steps 100000

# Train 100M model on RunPod A100
python train.py --model_size medium --dataset c4 --batch_size 32 --gradient_accumulation 4

# Resume from checkpoint
python train.py --resume checkpoints/latest.pt

# With wandb logging
python train.py --wandb --wandb_project symbolu --wandb_run phase_attention_50m

Model Sizes:
- tiny: 10M params (embed=256, layers=4, heads=4)  - for testing
- small: 50M params (embed=512, layers=8, heads=8)  - validation
- medium: 100M params (embed=768, layers=12, heads=12)  - target
- large: 350M params (embed=1024, layers=24, heads=16)  - scale test
- xl: 1.3B params (embed=2048, layers=24, heads=16)  - large scale
- 7b: 7B params (embed=4096, layers=32, heads=32)  - production scale

7B Training (requires A100 80GB):
python train.py --model_size 7b --dataset c4 --batch_size 1 --gradient_accumulation 64 --gradient_checkpointing --max_seq_len 2048
"""

import os

# Set CUDA memory and tokenizer environment variables before importing torch
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import sys
import math
import time
import json
import argparse
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR, LambdaLR
from torch.amp import autocast
from torch.cuda.amp import GradScaler

# =============================================================================
# PERFORMANCE: Enable hardware acceleration features
# =============================================================================
# TF32: Use TensorFloat-32 on Ampere+ GPUs (A100, H100, B200)
# Provides 2-3x speedup for FP32 math with minimal accuracy loss
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True

# cuDNN Benchmark: Auto-tune convolution algorithms for faster execution
# Small overhead on first batch, then faster for rest of training
torch.backends.cudnn.benchmark = True

# SymbolU imports
from symbolu.phase_transformer import PhaseTransformer, HybridPhaseTransformer, TransformerConfig

# Optional imports
try:
    import wandb
    WANDB_AVAILABLE = True
except ImportError:
    WANDB_AVAILABLE = False

try:
    from torch.utils.tensorboard import SummaryWriter
    TENSORBOARD_AVAILABLE = True
except ImportError:
    TENSORBOARD_AVAILABLE = False

try:
    from datasets import load_dataset
    from transformers import AutoTokenizer
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False
    print("Warning: HuggingFace datasets/transformers not installed.")
    print("Install with: pip install datasets transformers")

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False


# =============================================================================
# CONSTANTS
# =============================================================================

# Entropy constants for coherence loss (S3, S5, S8-S9)
# These control the semantic entropy regularization behavior
ENTROPY_MAX = 10.8          # log(50257) - maximum possible entropy for GPT-2 vocab
ENTROPY_TARGET = 4.0        # Target entropy for moderate confidence
ENTROPY_UPDATE_THRESHOLD = 6.0  # Entropy above this triggers update gate


class EntropyTracker:
    """
    Tracks entropy across training steps for stability loss (S8-S9).

    Encapsulates the previously global _prev_entropy state and provides
    helper methods for computing update gates and stability losses.
    """

    def __init__(self):
        self.prev_entropy: Optional[torch.Tensor] = None

    def compute_coherence_terms(
        self,
        entropy: torch.Tensor,
        device: torch.device,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, Dict[str, float]]:
        """
        Compute entropy loss, update gate, and stability loss.

        Returns:
            L_entropy: Entropy regularization loss
            update_gate: Gate for scaling coherence loss (0-1)
            L_stability: Stability loss penalizing entropy spikes
            metrics: Dict with entropy, update_gate, entropy_change
        """
        metrics = {}

        # Entropy loss - target moderate confidence
        L_entropy = (entropy - ENTROPY_TARGET).pow(2)
        metrics["entropy"] = entropy.item()

        # Update gate: high when entropy is high (uncertain/changing context)
        update_gate = torch.sigmoid((entropy - ENTROPY_UPDATE_THRESHOLD) * 2.0)

        # Stability loss from entropy change
        if self.prev_entropy is not None:
            entropy_change = entropy - self.prev_entropy
            # Combine with entropy spike detection
            change_gate = torch.sigmoid(entropy_change * 5.0)
            update_gate = torch.max(update_gate, change_gate * 0.5)
            # Penalize entropy increases (dH/dt > 0 violates S8)
            L_stability = F.relu(entropy_change)
            metrics["entropy_change"] = entropy_change.item()
        else:
            L_stability = torch.tensor(0.0, device=device)
            metrics["entropy_change"] = 0.0

        metrics["update_gate"] = update_gate.item()

        # Update state for next step
        self.prev_entropy = entropy.detach()

        return L_entropy, update_gate, L_stability, metrics

    def reset(self):
        """Reset tracker state (e.g., at start of new epoch)."""
        self.prev_entropy = None


# Global entropy tracker instance
_entropy_tracker = EntropyTracker()


class MetricsLogger:
    """
    Unified logging to wandb and TensorBoard.

    Reduces duplicated logging code throughout the training loop.
    """

    def __init__(
        self,
        config: 'TrainingConfig',
        tb_writer: Optional['SummaryWriter'] = None
    ):
        self.config = config
        self.tb_writer = tb_writer
        self.wandb_enabled = config.wandb and WANDB_AVAILABLE

    def log(self, metrics: Dict[str, float], step: int, prefix: str = "train"):
        """
        Log metrics to wandb and TensorBoard.

        Args:
            metrics: Dict of metric name -> value
            step: Current training step
            prefix: Prefix for metric names (e.g., "train", "val")
        """
        # Wandb logging
        if self.wandb_enabled:
            wandb_metrics = {f"{prefix}/{k}": v for k, v in metrics.items()}
            wandb.log(wandb_metrics, step=step)

        # TensorBoard logging
        if self.tb_writer is not None:
            for name, value in metrics.items():
                self.tb_writer.add_scalar(f"{prefix}/{name}", value, step)

    def close(self):
        """Clean up logging resources."""
        if self.wandb_enabled:
            wandb.finish()
        if self.tb_writer is not None:
            self.tb_writer.close()


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class TrainingConfig:
    """Complete training configuration."""

    # Model architecture
    model_size: str = "small"  # tiny, small, medium, large
    model_type: str = "phase"  # phase, hybrid
    vocab_size: int = 50257  # GPT-2 vocab size
    max_seq_len: int = 1024
    dropout: float = 0.1

    # Phase-specific parameters
    sync_steps: int = 3
    sync_lr: float = 0.1

    # Hybrid-specific parameters
    # NOTE: Updated defaults based on diagnostic findings:
    # - 6/6 split works better than 4/8 for semantic feature extraction
    # - Higher alpha_phase (0.6) forces the model to use long-range attention
    # - Gate init changed to 0.95 to preserve memory (learn to forget, not remember)
    local_layers: int = 6  # Number of early layers with local attention only (was 4)
    window_size: int = 256  # Local attention window size
    local_backend: str = "auto"  # LocalAttention backend: auto, flash, sdpa, unfold
    alpha_local: float = 0.4  # Weight for local attention in hybrid layers (was 0.8)
    alpha_phase: float = 0.6  # Weight for phase attention in hybrid layers (was 0.2)

    # Alpha decay schedule: Start high to force long-range learning, decay for fine-grained PPL
    alpha_phase_start: float = 0.6  # Initial phase attention weight
    alpha_phase_end: float = 0.4    # Final phase attention weight
    alpha_decay_steps: int = 10000  # Steps over which to decay alpha

    # Training hyperparameters
    batch_size: int = 16
    gradient_accumulation: int = 1
    max_steps: int = 100000
    warmup_steps: int = 2000

    # Optimizer
    learning_rate: float = 3e-4
    weight_decay: float = 0.1
    beta1: float = 0.9
    beta2: float = 0.95
    eps: float = 1e-8
    max_grad_norm: float = 1.0

    # Learning rate schedule
    lr_scheduler: str = "cosine"  # cosine, linear, constant
    min_lr_ratio: float = 0.1  # minimum LR as ratio of peak

    # Mixed precision
    mixed_precision: str = "bf16"  # none, fp16, bf16

    # Gradient checkpointing (for large models)
    gradient_checkpointing: bool = False  # Enable to reduce memory at cost of speed

    # Chunked processing (for ultra-long sequences like 10M tokens)
    chunk_size: int = 0  # 0 = disabled, otherwise process sequence in chunks of this size

    # Checkpointing
    checkpoint_dir: str = "checkpoints"
    save_every: int = 5000
    eval_every: int = 100
    log_every: int = 100

    # Dataset
    dataset: str = "wikitext2"  # c4, wikitext103, wikitext2, custom
    dataset_path: Optional[str] = None  # for custom datasets
    tokenizer: str = "gpt2"  # gpt2, tiktoken, custom

    # Evaluation
    eval_samples: int = 1000

    # Logging
    wandb: bool = False
    wandb_project: str = "symbolu"
    wandb_run: Optional[str] = None
    tensorboard: bool = False

    # Hardware
    device: str = "auto"  # auto, cuda, cpu
    num_workers: int = 4
    pin_memory: bool = True

    # Performance
    use_compile: bool = False  # Use torch.compile for 10-30% speedup (requires PyTorch 2.0+)
    compile_mode: str = "reduce-overhead"  # default, reduce-overhead, max-autotune

    # Resume
    resume: Optional[str] = None

    # Coherence Loss (S3, S1-S2, S8-S9)
    use_coherence_loss: bool = True  # Enable coherence-enhanced training
    lambda_entropy: float = 0.01     # S5: Semantic entropy weight
    lambda_coherence: float = 0.01   # S1-S2: Layer coherence weight
    lambda_stability: float = 0.001  # S8-S9: Stability constraint weight

    # Loss Type (memory-efficient options for long context)
    loss_type: str = "cross_entropy"  # cross_entropy, contrastive, infonce, state_delta
    num_negatives: int = 1024         # Number of negative samples for contrastive
    contrastive_margin: float = 1.0   # Margin for hinge loss
    contrastive_temperature: float = 0.1  # Temperature for InfoNCE

    # State-Centric Training (for 10M+ context - NO LM head required!)
    lambda_delta: float = 1.0         # State delta prediction weight
    lambda_entropy_state: float = 0.1 # Entropy change weight
    lambda_constraint: float = 0.1    # Constraint satisfaction weight
    target_entropy_rate: float = 0.5  # Target entropy rate

    # Chunked LM Head (for ultra-long contexts 1M+)
    lm_head_chunk_size: int = 0  # 0 = disabled, >0 = chunk size for LM head processing
    # Recommended: 8192 for 1M context, 4096 for 5M context

    # Seed
    seed: int = 42


# Model size presets
MODEL_PRESETS = {
    "tiny": {
        "embed_dim": 256,
        "num_layers": 4,
        "num_heads": 4,
        "ff_dim": 1024,
    },
    "small": {
        "embed_dim": 512,
        "num_layers": 8,
        "num_heads": 8,
        "ff_dim": 2048,
    },
    "medium": {
        "embed_dim": 768,
        "num_layers": 12,
        "num_heads": 12,
        "ff_dim": 3072,
    },
    "large": {
        "embed_dim": 1024,
        "num_layers": 24,
        "num_heads": 16,
        "ff_dim": 4096,
    },
    "xl": {
        "embed_dim": 2048,
        "num_layers": 24,
        "num_heads": 16,
        "ff_dim": 8192,
    },
    "7b": {
        "embed_dim": 4096,
        "num_layers": 32,
        "num_heads": 32,
        "ff_dim": 11008,  # LLaMA-style: ~2.7x hidden dim
        "use_gqa": True,
        "num_kv_heads": 8,  # Grouped Query Attention: 32/8 = 4 groups
    },
}


# =============================================================================
# LOGGING
# =============================================================================

def setup_logging(config: TrainingConfig) -> logging.Logger:
    """Set up logging configuration."""
    log_dir = Path(config.checkpoint_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"train_{timestamp}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
    )

    logger = logging.getLogger("train")
    return logger


# =============================================================================
# DATASET
# =============================================================================

class TextDataset(Dataset):
    """Dataset for language modeling."""

    def __init__(
        self,
        tokens: torch.Tensor,
        seq_len: int,
    ):
        self.tokens = tokens
        self.seq_len = seq_len
        self.num_samples = len(tokens) // seq_len

    def __len__(self):
        return self.num_samples

    def __getitem__(self, idx):
        start = idx * self.seq_len
        end = start + self.seq_len + 1
        chunk = self.tokens[start:end]

        x = chunk[:-1]  # Input
        y = chunk[1:]   # Target (shifted by 1)

        return x, y


def load_tokenizer(config: TrainingConfig):
    """Load tokenizer based on configuration."""
    if config.tokenizer == "tiktoken" and TIKTOKEN_AVAILABLE:
        enc = tiktoken.get_encoding("gpt2")
        return enc
    elif config.tokenizer == "gpt2" and HF_AVAILABLE:
        tokenizer = AutoTokenizer.from_pretrained("gpt2")
        # Suppress length warning - we handle chunking in TextDataset
        tokenizer.model_max_length = int(1e12)
        return tokenizer
    else:
        raise ValueError(f"Tokenizer {config.tokenizer} not available")


def tokenize_text(text: str, tokenizer) -> torch.Tensor:
    """Tokenize text using the appropriate tokenizer."""
    # Check if it's a tiktoken encoder (has 'encode_ordinary' method)
    if TIKTOKEN_AVAILABLE and hasattr(tokenizer, 'encode_ordinary'):
        # tiktoken
        tokens = tokenizer.encode(text, allowed_special={'<|endoftext|>'})
    else:
        # HuggingFace tokenizer
        tokens = tokenizer.encode(text)

    return torch.tensor(tokens, dtype=torch.long)


def load_dataset_tokens(config: TrainingConfig, split: str = "train") -> torch.Tensor:
    """Load and tokenize dataset."""
    if not HF_AVAILABLE:
        raise ImportError("datasets library required. Install: pip install datasets")

    print(f"Loading {config.dataset} dataset ({split} split)...")

    # Load tokenizer
    tokenizer = load_tokenizer(config)

    # Load dataset
    if config.dataset == "c4":
        # Use allenai/c4 (the newer supported version)
        dataset = load_dataset("allenai/c4", "en", split=split, streaming=True, trust_remote_code=True)
        # Stream and tokenize (limit for memory)
        all_tokens = []
        max_tokens = 50_000_000 if split == "train" else 1_000_000

        for item in dataset:
            tokens = tokenize_text(item["text"], tokenizer)
            all_tokens.append(tokens)
            if sum(len(t) for t in all_tokens) >= max_tokens:
                break

        tokens = torch.cat(all_tokens)

    elif config.dataset == "wikitext103":
        dataset = load_dataset("wikitext", "wikitext-103-v1", split=split)
        text = "\n".join(dataset["text"])
        tokens = tokenize_text(text, tokenizer)

    elif config.dataset == "wikitext2":
        dataset = load_dataset("wikitext", "wikitext-2-v1", split=split)
        text = "\n".join(dataset["text"])
        tokens = tokenize_text(text, tokenizer)

    elif config.dataset == "custom" and config.dataset_path:
        with open(config.dataset_path, 'r') as f:
            text = f.read()
        tokens = tokenize_text(text, tokenizer)

    else:
        raise ValueError(f"Unknown dataset: {config.dataset}")

    print(f"Loaded {len(tokens):,} tokens")
    return tokens


def create_dataloaders(
    config: TrainingConfig,
) -> Tuple[DataLoader, DataLoader]:
    """Create train and validation dataloaders."""

    # Load tokens
    train_tokens = load_dataset_tokens(config, "train")
    val_tokens = load_dataset_tokens(config, "validation" if config.dataset != "c4" else "validation")

    # Create datasets
    train_dataset = TextDataset(train_tokens, config.max_seq_len)
    val_dataset = TextDataset(val_tokens, config.max_seq_len)

    # Create dataloaders with performance optimizations
    # - prefetch_factor: Prefetch 2 batches per worker to hide data loading latency
    # - persistent_workers: Keep workers alive between epochs (avoids respawn overhead)
    dataloader_kwargs = dict(
        num_workers=config.num_workers,
        pin_memory=config.pin_memory,
        drop_last=True,
        prefetch_factor=2 if config.num_workers > 0 else None,
        persistent_workers=config.num_workers > 0,
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=config.batch_size,
        shuffle=True,
        **dataloader_kwargs,
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=config.batch_size,
        shuffle=False,
        **dataloader_kwargs,
    )

    return train_loader, val_loader


# =============================================================================
# MODEL
# =============================================================================

def create_model(config: TrainingConfig) -> nn.Module:
    """Create PhaseTransformer or HybridPhaseTransformer model based on configuration."""

    # Get model preset
    if config.model_size not in MODEL_PRESETS:
        raise ValueError(f"Unknown model size: {config.model_size}")

    preset = MODEL_PRESETS[config.model_size]

    # Base model kwargs
    model_kwargs = dict(
        vocab_size=config.vocab_size,
        embed_dim=preset["embed_dim"],
        num_layers=preset["num_layers"],
        num_heads=preset["num_heads"],
        ff_dim=preset["ff_dim"],
        max_seq_len=config.max_seq_len,
        dropout=config.dropout,
        sync_steps=config.sync_steps,
        sync_lr=config.sync_lr,
    )

    # Create model based on type
    if config.model_type == "hybrid":
        # Add hybrid-specific parameters
        model_kwargs.update(
            local_layers=config.local_layers,
            window_size=config.window_size,
            local_backend=config.local_backend,
            alpha_local=config.alpha_local,
            alpha_phase=config.alpha_phase,
        )
        model = HybridPhaseTransformer(**model_kwargs)
    else:
        # Default: pure phase attention
        model = PhaseTransformer(**model_kwargs)

    # Enable gradient checkpointing for large models
    if config.gradient_checkpointing:
        if hasattr(model, 'gradient_checkpointing_enable'):
            model.gradient_checkpointing_enable()
        else:
            # Manual gradient checkpointing support
            for module in model.modules():
                if hasattr(module, 'gradient_checkpointing'):
                    module.gradient_checkpointing = True

    return model


def count_parameters(model: nn.Module) -> int:
    """Count trainable parameters."""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def update_alpha_schedule(
    model: nn.Module,
    step: int,
    config: TrainingConfig,
) -> float:
    """
    Update alpha_phase across all hybrid layers based on training progress.

    Alpha decay schedule (from Gemini's recommendation):
    - Start high (0.6) to force the model to use long-range Phase attention
    - Decay to lower value (0.4) to allow local attention to sharpen PPL

    This prevents the "local shortcut" where the model ignores Phase layers.
    """
    # Calculate current alpha based on linear decay
    if step >= config.alpha_decay_steps:
        current_alpha = config.alpha_phase_end
    else:
        frac = step / config.alpha_decay_steps
        current_alpha = config.alpha_phase_start + frac * (config.alpha_phase_end - config.alpha_phase_start)

    # Update all HybridAttentionLayer modules
    for module in model.modules():
        if hasattr(module, 'alpha_phase') and hasattr(module, 'alpha_local'):
            # Update the parameters in-place
            with torch.no_grad():
                module.alpha_phase.fill_(current_alpha)
                module.alpha_local.fill_(1.0 - current_alpha)

    return current_alpha


# =============================================================================
# OPTIMIZER & SCHEDULER
# =============================================================================

def create_optimizer(model: nn.Module, config: TrainingConfig) -> AdamW:
    """Create AdamW optimizer with weight decay."""

    # Separate parameters into decay and no-decay groups
    decay_params = []
    no_decay_params = []

    for name, param in model.named_parameters():
        if not param.requires_grad:
            continue
        if 'bias' in name or 'norm' in name or 'embed' in name:
            no_decay_params.append(param)
        else:
            decay_params.append(param)

    param_groups = [
        {"params": decay_params, "weight_decay": config.weight_decay},
        {"params": no_decay_params, "weight_decay": 0.0},
    ]

    optimizer = AdamW(
        param_groups,
        lr=config.learning_rate,
        betas=(config.beta1, config.beta2),
        eps=config.eps,
    )

    return optimizer


def create_scheduler(
    optimizer: AdamW,
    config: TrainingConfig,
) -> LambdaLR:
    """Create learning rate scheduler with warmup."""

    def lr_lambda(step: int) -> float:
        # Warmup phase
        if step < config.warmup_steps:
            return step / max(1, config.warmup_steps)

        # Post-warmup: cosine decay
        progress = (step - config.warmup_steps) / max(1, config.max_steps - config.warmup_steps)

        if config.lr_scheduler == "cosine":
            # Cosine decay to min_lr_ratio
            return config.min_lr_ratio + (1 - config.min_lr_ratio) * 0.5 * (1 + math.cos(math.pi * progress))
        elif config.lr_scheduler == "linear":
            # Linear decay to min_lr_ratio
            return config.min_lr_ratio + (1 - config.min_lr_ratio) * (1 - progress)
        else:
            # Constant
            return 1.0

    scheduler = LambdaLR(optimizer, lr_lambda)
    return scheduler


# =============================================================================
# TRAINING
# =============================================================================

@dataclass
class TrainingState:
    """Training state for checkpointing."""
    step: int = 0
    epoch: int = 0
    best_val_loss: float = float('inf')
    total_tokens: int = 0
    train_losses: list = field(default_factory=list)


def compute_semantic_entropy(logits: torch.Tensor, max_positions: int = 1024) -> torch.Tensor:
    """
    Compute semantic entropy (Formula S5) using LogSumExp - NO SOFTMAX.

    Memory-efficient formula:
        H ≈ logsumexp(logits) - mean(logits)

    This avoids creating O(B·T·V) probability tensors entirely.
    At 1M context with V=50K: saves ~200GB of memory.

    The approximation uses the fact that:
        H = logsumexp(logits) - Σ p_i · logits_i
        ≈ logsumexp(logits) - E[logits]  (when distribution is peaked)
    """
    B, N, V = logits.shape

    # Sample positions if sequence is too long
    if N > max_positions:
        indices = torch.linspace(0, N - 1, max_positions, dtype=torch.long, device=logits.device)
        logits = logits[:, indices, :]  # (B, max_positions, V)

    # LogSumExp entropy: O(B·T) memory, NOT O(B·T·V)
    # logsumexp gives log(Σ exp(logits)) = log(Z) where Z is partition function
    lse = torch.logsumexp(logits, dim=-1)  # (B, T) - no V dimension!

    # Approximate expected logit using max (mode of distribution)
    # This avoids computing full softmax
    max_logits, _ = logits.max(dim=-1)  # (B, T)

    # Entropy ≈ log(Z) - mode_logit
    # For peaked distributions, this is a good approximation
    entropy = lse - max_logits

    return entropy.mean()


def compute_semantic_entropy_exact(logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
    """
    Compute exact cross-entropy based entropy using targets - NO SOFTMAX.

    Formula: H = logsumexp(logits) - logits[target]

    This is the exact entropy contribution at the target position,
    computed without materializing the full probability distribution.

    Memory: O(B·T) not O(B·T·V)
    """
    B, N, V = logits.shape

    # logsumexp over vocabulary
    lse = torch.logsumexp(logits, dim=-1)  # (B, N)

    # Get logit at target position
    target_logits = torch.gather(logits, dim=-1, index=targets.unsqueeze(-1)).squeeze(-1)  # (B, N)

    # Entropy = log(Z) - logit[target] = -log(p[target])
    entropy = lse - target_logits

    return entropy.mean()


def compute_layer_coherence(hidden_states: list) -> torch.Tensor:
    """
    Compute cross-layer coherence (Formulas S1-S2).

    C_global = Σᵢⱼ Corr(Lᵢ, Lⱼ)

    Higher coherence = layers are aligned in their representations.
    """
    if not hidden_states or len(hidden_states) < 2:
        return torch.tensor(0.0)

    coherence = 0.0
    count = 0

    for i in range(len(hidden_states) - 1):
        # Cosine similarity between adjacent layers (Formula S4)
        h_i = hidden_states[i].mean(dim=1)  # [B, D]
        h_j = hidden_states[i + 1].mean(dim=1)  # [B, D]

        cos_sim = F.cosine_similarity(h_i, h_j, dim=-1).mean()
        coherence += cos_sim
        count += 1

    return coherence / max(count, 1)


def compute_contrastive_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    num_negatives: int = 1024,
    margin: float = 1.0,
) -> torch.Tensor:
    """
    Compute contrastive loss - NO SOFTMAX, NO NORMALIZATION.

    Instead of cross-entropy over full vocabulary:
    - Score correct token higher than sampled negatives
    - Memory scales with num_negatives, NOT vocabulary size

    Loss = max(0, margin - score_pos + score_neg)

    Memory: O(B·T·num_negatives) instead of O(B·T·V)
    At 1M context: ~8GB instead of ~200GB

    Benefits:
    - Removes softmax normalization bottleneck
    - Works especially well with phase memory models
    - Scales to arbitrary vocabulary sizes
    """
    B, N, V = logits.shape
    device = logits.device

    # Get positive scores (score at target position)
    # Shape: (B, N)
    pos_scores = torch.gather(logits, dim=-1, index=targets.unsqueeze(-1)).squeeze(-1)

    # Sample random negatives
    # Shape: (B, N, num_negatives)
    neg_indices = torch.randint(0, V, (B, N, num_negatives), device=device)

    # Gather negative scores efficiently
    # Reshape logits for gathering: (B*N, V)
    logits_flat = logits.view(B * N, V)
    neg_indices_flat = neg_indices.view(B * N, num_negatives)

    # Gather: (B*N, num_negatives)
    neg_scores_flat = torch.gather(logits_flat, dim=-1, index=neg_indices_flat)

    # Reshape back: (B, N, num_negatives)
    neg_scores = neg_scores_flat.view(B, N, num_negatives)

    # Margin-based hinge loss: max(0, margin - pos + neg)
    # We want pos_score > neg_score + margin
    # Shape: (B, N, num_negatives)
    losses = F.relu(margin - pos_scores.unsqueeze(-1) + neg_scores)

    # Average over negatives, then over sequence and batch
    return losses.mean()


def compute_infonce_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    temperature: float = 0.1,
    num_negatives: int = 1024,
) -> torch.Tensor:
    """
    Compute InfoNCE contrastive loss - efficient alternative to cross-entropy.

    InfoNCE: -log(exp(pos/τ) / (exp(pos/τ) + Σ exp(neg/τ)))

    This is like cross-entropy but only over (1 + num_negatives) classes
    instead of full vocabulary.

    Memory: O(B·T·num_negatives) instead of O(B·T·V)
    """
    B, N, V = logits.shape
    device = logits.device

    # Get positive scores
    pos_scores = torch.gather(logits, dim=-1, index=targets.unsqueeze(-1)).squeeze(-1)
    pos_scores = pos_scores / temperature  # (B, N)

    # Sample negatives
    neg_indices = torch.randint(0, V, (B, N, num_negatives), device=device)

    # Gather negative scores efficiently
    logits_flat = logits.view(B * N, V)
    neg_indices_flat = neg_indices.view(B * N, num_negatives)
    neg_scores_flat = torch.gather(logits_flat, dim=-1, index=neg_indices_flat)
    neg_scores = neg_scores_flat.view(B, N, num_negatives) / temperature

    # InfoNCE: log(exp(pos) / (exp(pos) + sum(exp(neg))))
    # = pos - logsumexp([pos, neg1, neg2, ...])
    all_scores = torch.cat([pos_scores.unsqueeze(-1), neg_scores], dim=-1)  # (B, N, 1+num_neg)
    log_denominator = torch.logsumexp(all_scores, dim=-1)  # (B, N)

    # Loss = -log(p_pos) = log_denom - pos
    loss = log_denominator - pos_scores

    return loss.mean()


def compute_state_centric_loss(
    model: PhaseTransformer,
    batch: Tuple[torch.Tensor, torch.Tensor],
    device: torch.device,
    lambda_delta: float = 1.0,
    lambda_entropy: float = 0.1,
    lambda_constraint: float = 0.1,
    target_entropy_rate: float = 0.5,
) -> Tuple[torch.Tensor, Dict[str, float]]:
    """
    State-centric training loss - NO TOKEN PREDICTION (no LM head).

    Instead of:
        hidden → LM head (50K dim) → CE loss  [O(B·T·V) memory = 200GB at 1M]

    We use:
        hidden → state_delta_predictor (768 dim) → state losses  [O(B·T·d) = 3GB at 1M]

    Training signals:
    1. State delta prediction: predict h[t+1] - h[t]
    2. Entropy change: smooth information flow
    3. Constraint satisfaction: bounded norms, diversity, smoothness

    Memory savings: 50K/768 = ~65x reduction per position
    At 1M context: 200GB → 3GB

    This enables training at 10M+ context without ANY vocabulary projection.
    Tokens become a projection for inference, not the training objective.

    Args:
        model: PhaseTransformer or HybridPhaseTransformer with state_delta_predictor
        batch: (input_ids, target_ids) - targets not used for state-centric training
        device: torch device
        lambda_delta: Weight for state delta prediction loss
        lambda_entropy: Weight for entropy change loss
        lambda_constraint: Weight for constraint satisfaction loss
        target_entropy_rate: Target rate of entropy change

    Returns:
        loss: Combined state-centric loss
        metrics: Dict with all loss components
    """
    from symbolu.phase_transformer import (
        compute_entropy_change_loss,
        compute_constraint_satisfaction_loss,
    )

    x, _ = batch  # y (targets) not needed for state-centric training
    x = x.to(device)

    # Get hidden states (no LM head projection!)
    hidden_states = model.forward_hidden(x)  # [B, T, embed_dim]

    # 1. State delta prediction loss
    delta_loss, delta_metrics = model.state_delta_predictor.compute_loss(hidden_states)

    # 2. Entropy change loss (information flow regularization)
    entropy_loss, entropy_metrics = compute_entropy_change_loss(
        hidden_states, target_entropy_rate=target_entropy_rate
    )

    # 3. Constraint satisfaction loss
    constraint_loss, constraint_metrics = compute_constraint_satisfaction_loss(hidden_states)

    # Combined loss
    total_loss = (
        lambda_delta * delta_loss +
        lambda_entropy * entropy_loss +
        lambda_constraint * constraint_loss
    )

    # Compile metrics
    metrics = {
        'loss': total_loss.item(),
        'delta_loss': delta_loss.item(),
        'entropy_loss': entropy_loss.item(),
        'constraint_loss': constraint_loss.item(),
        **{k: v.item() if torch.is_tensor(v) else v for k, v in delta_metrics.items()},
        **{k: v.item() if torch.is_tensor(v) else v for k, v in entropy_metrics.items()},
        **{k: v.item() if torch.is_tensor(v) else v for k, v in constraint_metrics.items()},
    }

    return total_loss, metrics


def compute_loss_streaming(
    model: PhaseTransformer,
    batch: Tuple[torch.Tensor, torch.Tensor],
    device: torch.device,
    chunk_size: int,
    use_coherence_loss: bool = True,
    lambda_entropy: float = 0.01,
    lambda_coherence: float = 0.01,
    lambda_stability: float = 0.001,
    use_aux_reconstruction: bool = True,
    lambda_aux: float = 0.1,
) -> Tuple[None, Dict[str, float]]:
    """
    Compute loss with STREAMING chunked forward pass for ultra-long sequences (10M+ tokens).

    Key innovations:
    1. Phase contexts accumulated across chunks for true global context
    2. Per-chunk backward passes (like gradient accumulation) to avoid OOM
    3. Memory stays O(chunk_size) regardless of total sequence length
    4. AUXILIARY RECONSTRUCTION LOSS: Forces model to keep early chunk info
       high-fidelity in the streaming state by predicting early phase signatures
       from later chunks. This creates gradient signal across chunks!

    Returns None for loss (gradients already accumulated), metrics dict.
    """
    x, y = batch
    x = x.to(device)
    y = y.to(device)

    B, N = x.shape
    num_chunks = (N + chunk_size - 1) // chunk_size

    total_loss = 0.0  # Track for metrics only (not tensor)
    total_aux_loss = 0.0
    total_tokens = 0
    last_entropy = 0.0
    last_coherence = 0.0

    # Initialize streaming phase contexts (empty list signals streaming mode)
    phase_contexts = []

    # Store early chunk hidden state signatures for auxiliary reconstruction
    # This is the "memory" that later chunks must learn to reconstruct
    early_chunk_signatures = []  # List of (chunk_idx, signature_tensor)
    signature_sample_rate = max(1, num_chunks // 10)  # Sample ~10 early chunks

    for i in range(num_chunks):
        start = i * chunk_size
        end = min((i + 1) * chunk_size, N)

        x_chunk = x[:, start:end]
        y_chunk = y[:, start:end]

        # Forward pass with streaming phase context
        output = model(
            x_chunk,
            return_hidden=True,
            phase_contexts=phase_contexts,
            position_offset=start,
        )

        logits = output['logits']
        hidden_states = output.get('hidden_states', [])

        # =====================================================================
        # AUXILIARY RECONSTRUCTION LOSS
        # Store early chunk signatures, reconstruct in later chunks
        # =====================================================================
        aux_loss = torch.tensor(0.0, device=device)

        if use_aux_reconstruction and hidden_states:
            # Get current chunk's hidden state signature (mean over sequence)
            current_signature = hidden_states[-1].mean(dim=1)  # [B, D]

            # Store signatures from early chunks (first 30% of sequence)
            if i < num_chunks * 0.3 and i % signature_sample_rate == 0:
                early_chunk_signatures.append((i, current_signature.detach()))

            # In later chunks (after 50%), try to reconstruct early signatures
            # from the current accumulated phase context
            if i > num_chunks * 0.5 and early_chunk_signatures:
                # Pick a random early signature to reconstruct
                target_idx = i % len(early_chunk_signatures)
                _, target_signature = early_chunk_signatures[target_idx]

                # The model must predict early chunk info from current state
                # Use cosine similarity loss (1 - cos_sim)
                cos_sim = F.cosine_similarity(
                    current_signature, target_signature, dim=-1
                ).mean()
                aux_loss = (1.0 - cos_sim) * lambda_aux

        # Update phase contexts for next chunk - DETACH to break gradient chain
        new_contexts = output.get('phase_contexts', [])
        phase_contexts = []
        for ctx in new_contexts:
            detached_ctx = {}
            for k, v in ctx.items():
                if isinstance(v, torch.Tensor):
                    detached_ctx[k] = v.detach()
                else:
                    detached_ctx[k] = v
            phase_contexts.append(detached_ctx)

        # Compute chunk loss
        B_c, N_c, V = logits.shape
        chunk_tokens = B_c * N_c
        chunk_loss = F.cross_entropy(
            logits.view(B_c * N_c, V),
            y_chunk.view(B_c * N_c),
            ignore_index=-100,
            reduction='mean'
        )

        # Combined loss: task + auxiliary reconstruction
        combined_loss = chunk_loss + aux_loss

        # Per-chunk backward - gradients accumulate (like gradient accumulation)
        scaled_loss = combined_loss / num_chunks
        scaled_loss.backward()

        # Track metrics (no grad)
        total_loss += chunk_loss.item() * chunk_tokens
        total_aux_loss += aux_loss.item() if isinstance(aux_loss, torch.Tensor) else aux_loss
        total_tokens += chunk_tokens

        # Metrics from last chunk
        if i == num_chunks - 1 and use_coherence_loss:
            with torch.no_grad():
                last_entropy = compute_semantic_entropy(logits).item()
                last_coherence = compute_layer_coherence(hidden_states).item() if hidden_states else 0

        # Free memory immediately
        del output, logits, hidden_states, chunk_loss, scaled_loss, aux_loss, combined_loss
        if device.type == 'cuda':
            torch.cuda.empty_cache()

    # Average loss for metrics
    avg_loss = total_loss / total_tokens if total_tokens > 0 else 0.0
    avg_aux_loss = total_aux_loss / num_chunks if num_chunks > 0 else 0.0

    metrics = {
        "loss": avg_loss,
        "perplexity": math.exp(avg_loss) if avg_loss < 20 else float('inf'),
        "num_chunks": num_chunks,
        "streaming": True,
        "entropy": last_entropy,
        "coherence": last_coherence,
        "aux_recon_loss": avg_aux_loss,  # Track reconstruction quality
    }

    # Return None - gradients already accumulated via per-chunk backward
    return None, metrics


def compute_loss(
    model: PhaseTransformer,
    batch: Tuple[torch.Tensor, torch.Tensor],
    device: torch.device,
    use_coherence_loss: bool = True,
    lambda_entropy: float = 0.01,
    lambda_coherence: float = 0.01,
    lambda_stability: float = 0.001,
    loss_type: str = "cross_entropy",  # cross_entropy, contrastive, infonce
    num_negatives: int = 1024,  # for contrastive losses
    contrastive_margin: float = 1.0,  # for hinge loss
    contrastive_temperature: float = 0.1,  # for infonce
) -> Tuple[torch.Tensor, Dict[str, float]]:
    """
    Compute enhanced loss with coherence formulas (S3, S1-S2, S8-S9).

    L_coherence = L_task + λ_e·L_entropy + λ_c·L_coherence + λ_s·L_stability

    Loss types:
    - cross_entropy: Standard fused CE (O(B·T) memory via fusion)
    - contrastive: Margin-based hinge loss (O(B·T·num_neg) memory)
    - infonce: InfoNCE contrastive (O(B·T·num_neg) memory)

    For 1M context with V=50K:
    - cross_entropy: ~8GB (fused, no explicit softmax)
    - contrastive/infonce: ~8GB with num_neg=1024

    Where:
    - L_task: Task loss (CE or contrastive)
    - L_entropy: Semantic entropy via LogSumExp (S5) - NO SOFTMAX
    - L_coherence: Layer coherence (S1-S2)
    - L_stability: Entropy stability (S8)
    """
    x, y = batch
    x = x.to(device)
    y = y.to(device)

    # Forward pass with hidden states for layer coherence
    output = model(x, return_hidden=True)
    logits = output['logits']
    hidden_states = output.get('hidden_states', [])

    B, N, V = logits.shape

    # Compute task loss based on loss_type
    if loss_type == "contrastive":
        # Margin-based contrastive loss - O(B·T·num_neg) memory
        L_task = compute_contrastive_loss(
            logits, y,
            num_negatives=num_negatives,
            margin=contrastive_margin
        )
    elif loss_type == "infonce":
        # InfoNCE contrastive loss - O(B·T·num_neg) memory
        L_task = compute_infonce_loss(
            logits, y,
            temperature=contrastive_temperature,
            num_negatives=num_negatives
        )
    else:
        # Standard fused cross-entropy - O(B·T) memory (fused kernel)
        L_task = F.cross_entropy(
            logits.view(B * N, V),
            y.view(B * N),
            ignore_index=-100,
        )

    metrics = {
        "loss": L_task.item(),
        "perplexity": torch.exp(L_task).item(),
    }

    if use_coherence_loss:
        # Compute semantic entropy
        entropy = compute_semantic_entropy(logits)

        # Use entropy tracker for update gate and stability (S5, S8-S9)
        L_entropy, update_gate, L_stability, entropy_metrics = _entropy_tracker.compute_coherence_terms(
            entropy, device
        )
        metrics.update(entropy_metrics)

        # Reduce coherence loss during updates
        coherence_scale = 1.0 - update_gate

        # S1-S2: Layer Coherence - maximize cross-layer alignment
        if hidden_states:
            coherence = compute_layer_coherence(hidden_states)
            L_coherence_term = 1.0 - coherence  # Penalize low coherence
            metrics["coherence"] = coherence.item()
        else:
            L_coherence_term = torch.tensor(0.0, device=device)
            metrics["coherence"] = 0.0

        # Combined Coherence Loss (S3) with conditional gating
        loss = (L_task +
                lambda_entropy * L_entropy +
                lambda_coherence * coherence_scale * L_coherence_term +
                lambda_stability * coherence_scale * L_stability)

        metrics["loss_total"] = loss.item()
    else:
        loss = L_task

    return loss, metrics


def compute_loss_chunked_lm_head(
    model: PhaseTransformer,
    batch: Tuple[torch.Tensor, torch.Tensor],
    device: torch.device,
    lm_head_chunk_size: int = 8192,
    use_coherence_loss: bool = True,
    lambda_entropy: float = 0.01,
    lambda_coherence: float = 0.01,
    lambda_stability: float = 0.001,
) -> Tuple[torch.Tensor, Dict[str, float]]:
    """
    Compute loss with CHUNKED LM head processing for ultra-long contexts.

    For 5M context with V=50K:
    - Standard: lm_head creates (1, 5M, 50K) = 1TB tensor = OOM
    - Chunked: Process 8K tokens at a time = 1.6GB per chunk = fits in memory

    Memory breakdown per chunk (8K tokens, 50K vocab):
    - Hidden states chunk: 8K × 256 = 2MB
    - Logits chunk: 8K × 50K × 2 = 800MB (bf16)
    - Cross-entropy: fused, no extra memory
    - Total: ~1GB per chunk, easily fits

    This enables training on sequences up to 5M+ tokens on B200 (192GB).

    Args:
        model: PhaseTransformer or HybridPhaseTransformer (must have forward_hidden method)
        batch: (input_ids, targets) tuple
        device: torch device
        lm_head_chunk_size: tokens per chunk for LM head processing (default 8192)
        use_coherence_loss: whether to compute coherence losses
        lambda_*: loss weights
    """
    x, y = batch
    x = x.to(device)
    y = y.to(device)

    B, N = x.shape

    # Forward pass to get hidden states ONLY (no LM head yet)
    # This is memory-efficient: hidden is (B, N, embed_dim)
    # For 5M context with embed_dim=256: only 5GB (vs 1TB for full logits)
    hidden = model.forward_hidden(x)  # (B, N, embed_dim)

    # Get hidden states for coherence loss (if available)
    hidden_states = []
    if use_coherence_loss and hasattr(model, 'blocks'):
        # Re-run to get intermediate hidden states for coherence
        # This is a tradeoff: memory vs accuracy
        # For now, we skip layer coherence in chunked mode
        pass

    # Process LM head and cross-entropy in chunks
    total_loss = torch.tensor(0.0, device=device)
    total_tokens = 0
    entropy_sum = torch.tensor(0.0, device=device)
    entropy_samples = 0

    for chunk_start in range(0, N, lm_head_chunk_size):
        chunk_end = min(chunk_start + lm_head_chunk_size, N)
        chunk_size = chunk_end - chunk_start

        # Extract chunk of hidden states
        hidden_chunk = hidden[:, chunk_start:chunk_end, :]  # (B, chunk_size, embed_dim)

        # Compute logits for this chunk only
        chunk_logits = model.lm_head(hidden_chunk)  # (B, chunk_size, V)

        # Get targets for this chunk
        chunk_targets = y[:, chunk_start:chunk_end]  # (B, chunk_size)

        # Compute cross-entropy for this chunk (fused, memory-efficient)
        B_chunk, N_chunk, V = chunk_logits.shape
        chunk_loss = F.cross_entropy(
            chunk_logits.view(B_chunk * N_chunk, V),
            chunk_targets.view(B_chunk * N_chunk),
            ignore_index=-100,
            reduction='sum'  # Sum, then normalize later
        )

        # Count valid tokens (not -100)
        valid_tokens = (chunk_targets != -100).sum()
        total_loss = total_loss + chunk_loss
        total_tokens += valid_tokens

        # Sample entropy from a subset of positions in this chunk
        if use_coherence_loss:
            # Use LogSumExp entropy on a sample of positions
            sample_size = min(256, N_chunk)
            if N_chunk > sample_size:
                sample_indices = torch.randperm(N_chunk, device=device)[:sample_size]
                sampled_logits = chunk_logits[:, sample_indices, :]
            else:
                sampled_logits = chunk_logits

            # LogSumExp entropy (no softmax!)
            lse = torch.logsumexp(sampled_logits, dim=-1)  # (B, sample_size)
            max_logits, _ = sampled_logits.max(dim=-1)
            chunk_entropy = (lse - max_logits).mean()

            entropy_sum = entropy_sum + chunk_entropy * sample_size
            entropy_samples += sample_size

        # Explicitly delete chunk tensors to free memory immediately
        del chunk_logits, hidden_chunk

    # Normalize loss by total tokens
    if total_tokens > 0:
        L_task = total_loss / total_tokens
    else:
        L_task = total_loss

    metrics = {
        "loss": L_task.item(),
        "perplexity": torch.exp(L_task).item(),
    }

    if use_coherence_loss:
        # Compute entropy from samples
        if entropy_samples > 0:
            entropy = entropy_sum / entropy_samples
        else:
            entropy = torch.tensor(ENTROPY_TARGET, device=device)

        # Use entropy tracker for update gate and stability (S5, S8-S9)
        L_entropy, update_gate, L_stability, entropy_metrics = _entropy_tracker.compute_coherence_terms(
            entropy, device
        )
        metrics.update(entropy_metrics)

        coherence_scale = 1.0 - update_gate

        # Skip layer coherence in chunked mode (would require re-running forward)
        metrics["coherence"] = 0.0

        # Combined loss
        loss = (L_task +
                lambda_entropy * L_entropy +
                lambda_stability * coherence_scale * L_stability)

        metrics["loss_total"] = loss.item()
    else:
        loss = L_task

    return loss, metrics


def train_step(
    model: PhaseTransformer,
    batch: Tuple[torch.Tensor, torch.Tensor],
    optimizer: AdamW,
    scheduler: LambdaLR,
    scaler: Optional[GradScaler],
    config: TrainingConfig,
    device: torch.device,
    accumulation_step: int,
) -> Dict[str, float]:
    """Single training step with gradient accumulation and coherence loss."""

    # Mixed precision context
    use_amp = config.mixed_precision != "none" and device.type == "cuda"
    dtype = torch.bfloat16 if config.mixed_precision == "bf16" else torch.float16

    # Forward pass with coherence loss (S3, S1-S2, S8-S9)
    with autocast(device_type='cuda', enabled=use_amp, dtype=dtype):
        # State-centric training: NO LM head, predict state deltas instead
        if config.loss_type == "state_delta":
            loss, metrics = compute_state_centric_loss(
                model, batch, device,
                lambda_delta=config.lambda_delta,
                lambda_entropy=config.lambda_entropy_state,
                lambda_constraint=config.lambda_constraint,
                target_entropy_rate=config.target_entropy_rate,
            )
            loss = loss / config.gradient_accumulation

            # Backward pass
            if scaler is not None:
                scaler.scale(loss).backward()
            else:
                loss.backward()
        # Use streaming chunked processing for ultra-long sequences
        elif config.chunk_size > 0:
            # Streaming mode: backward already done per-chunk, returns None for loss
            loss, metrics = compute_loss_streaming(
                model, batch, device,
                chunk_size=config.chunk_size,
                use_coherence_loss=config.use_coherence_loss,
                lambda_entropy=config.lambda_entropy,
                lambda_coherence=config.lambda_coherence,
                lambda_stability=config.lambda_stability,
            )
            # loss is None - gradients already accumulated in compute_loss_streaming
        else:
            loss, metrics = compute_loss(
                model, batch, device,
                use_coherence_loss=config.use_coherence_loss,
                lambda_entropy=config.lambda_entropy,
                lambda_coherence=config.lambda_coherence,
                lambda_stability=config.lambda_stability,
                loss_type=config.loss_type,
                num_negatives=config.num_negatives,
                contrastive_margin=config.contrastive_margin,
                contrastive_temperature=config.contrastive_temperature,
            )
            loss = loss / config.gradient_accumulation

            # Backward pass (only for non-chunked mode)
            if scaler is not None:
                scaler.scale(loss).backward()
            else:
                loss.backward()

    # Gradient step (after accumulation)
    if (accumulation_step + 1) % config.gradient_accumulation == 0:
        if scaler is not None:
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), config.max_grad_norm)
            scaler.step(optimizer)
            scaler.update()
        else:
            torch.nn.utils.clip_grad_norm_(model.parameters(), config.max_grad_norm)
            optimizer.step()

        scheduler.step()
        optimizer.zero_grad()

    return metrics


@torch.no_grad()
def evaluate(
    model: PhaseTransformer,
    val_loader: DataLoader,
    config: TrainingConfig,
    device: torch.device,
) -> Dict[str, float]:
    """Evaluate model on validation set."""
    model.eval()

    total_loss = 0.0
    total_tokens = 0
    num_batches = 0
    max_batches = config.eval_samples // config.batch_size

    for batch in val_loader:
        if num_batches >= max_batches:
            break

        loss, _ = compute_loss(model, batch, device)
        total_loss += loss.item()
        total_tokens += batch[0].numel()
        num_batches += 1

    avg_loss = total_loss / max(1, num_batches)
    perplexity = math.exp(avg_loss)

    model.train()

    return {
        "val_loss": avg_loss,
        "val_perplexity": perplexity,
        "val_tokens": total_tokens,
    }


def save_checkpoint(
    model: PhaseTransformer,
    optimizer: AdamW,
    scheduler: LambdaLR,
    scaler: Optional[GradScaler],
    state: TrainingState,
    config: TrainingConfig,
    path: str,
):
    """Save training checkpoint."""
    checkpoint = {
        "model": model.state_dict(),
        "optimizer": optimizer.state_dict(),
        "scheduler": scheduler.state_dict(),
        "state": asdict(state),
        "config": asdict(config),
    }

    if scaler is not None:
        checkpoint["scaler"] = scaler.state_dict()

    torch.save(checkpoint, path)


def load_checkpoint(
    path: str,
    model: PhaseTransformer,
    optimizer: AdamW,
    scheduler: LambdaLR,
    scaler: Optional[GradScaler],
    device: torch.device,
) -> TrainingState:
    """Load training checkpoint."""
    checkpoint = torch.load(path, map_location=device)

    model.load_state_dict(checkpoint["model"])
    optimizer.load_state_dict(checkpoint["optimizer"])
    scheduler.load_state_dict(checkpoint["scheduler"])

    if scaler is not None and "scaler" in checkpoint:
        scaler.load_state_dict(checkpoint["scaler"])

    state = TrainingState(**checkpoint["state"])

    return state


# =============================================================================
# MAIN TRAINING LOOP
# =============================================================================

def train(config: TrainingConfig):
    """Main training function."""

    # Setup
    logger = setup_logging(config)

    # Device
    if config.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(config.device)

    logger.info(f"Using device: {device}")

    if device.type == "cuda":
        logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
        logger.info(f"CUDA version: {torch.version.cuda}")

    # Seed
    torch.manual_seed(config.seed)
    if device.type == "cuda":
        torch.cuda.manual_seed(config.seed)

    # Create directories
    checkpoint_dir = Path(config.checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    # Save config
    config_path = checkpoint_dir / "config.json"
    with open(config_path, 'w') as f:
        json.dump(asdict(config), f, indent=2)
    logger.info(f"Config saved to {config_path}")

    # Create model
    logger.info(f"Creating {config.model_size} model...")
    model = create_model(config)
    model = model.to(device)

    num_params = count_parameters(model)
    logger.info(f"Model parameters: {num_params:,} ({num_params/1e6:.1f}M)")

    # torch.compile for 10-30% speedup (PyTorch 2.0+)
    if config.use_compile:
        try:
            logger.info(f"Compiling model with mode='{config.compile_mode}'...")
            model = torch.compile(model, mode=config.compile_mode)
            logger.info("Model compiled successfully")
        except Exception as e:
            logger.warning(f"torch.compile failed (requires PyTorch 2.0+): {e}")

    # Create optimizer and scheduler
    optimizer = create_optimizer(model, config)
    scheduler = create_scheduler(optimizer, config)

    # Mixed precision scaler
    scaler = None
    if config.mixed_precision == "fp16" and device.type == "cuda":
        scaler = GradScaler()
        logger.info("Using FP16 mixed precision with GradScaler")
    elif config.mixed_precision == "bf16" and device.type == "cuda":
        logger.info("Using BF16 mixed precision (native)")

    # Training state
    state = TrainingState()

    # Resume from checkpoint
    if config.resume:
        logger.info(f"Resuming from {config.resume}")
        state = load_checkpoint(
            config.resume, model, optimizer, scheduler, scaler, device
        )
        logger.info(f"Resumed at step {state.step}")

    # Create dataloaders
    logger.info("Loading dataset...")
    train_loader, val_loader = create_dataloaders(config)
    logger.info(f"Train batches: {len(train_loader):,}")
    logger.info(f"Val batches: {len(val_loader):,}")

    # Wandb
    if config.wandb and WANDB_AVAILABLE:
        wandb.init(
            project=config.wandb_project,
            name=config.wandb_run or f"phase_{config.model_size}_{datetime.now().strftime('%Y%m%d_%H%M')}",
            config=asdict(config),
        )
        logger.info("Wandb initialized")

    # TensorBoard
    tb_writer = None
    if config.tensorboard and TENSORBOARD_AVAILABLE:
        tb_dir = checkpoint_dir / "tensorboard"
        tb_writer = SummaryWriter(tb_dir)
        logger.info(f"TensorBoard logging to {tb_dir}")

    # Training loop
    logger.info("=" * 60)
    logger.info("Starting training")
    if config.chunk_size > 0:
        num_chunks = (config.max_seq_len + config.chunk_size - 1) // config.chunk_size
        logger.info(f"CHUNKED MODE: {config.max_seq_len:,} tokens in {num_chunks} chunks of {config.chunk_size:,}")
    logger.info("=" * 60)

    model.train()
    train_iter = iter(train_loader)
    start_time = time.time()
    step_start_time = time.time()

    accumulation_step = 0
    running_loss = 0.0

    while state.step < config.max_steps:
        # Get batch (handle epoch boundaries)
        try:
            batch = next(train_iter)
        except StopIteration:
            state.epoch += 1
            train_iter = iter(train_loader)
            batch = next(train_iter)

        # Training step
        metrics = train_step(
            model, batch, optimizer, scheduler, scaler,
            config, device, accumulation_step
        )

        accumulation_step += 1
        running_loss += metrics["loss"]
        state.total_tokens += batch[0].numel()

        # Update step counter after gradient accumulation
        if accumulation_step % config.gradient_accumulation == 0:
            state.step += 1
            avg_loss = running_loss / config.gradient_accumulation
            state.train_losses.append(avg_loss)
            running_loss = 0.0

            # Update alpha schedule (decay from 0.6 to 0.4 for Phase Attention)
            current_alpha = update_alpha_schedule(model, state.step, config)

            # Logging
            if state.step % config.log_every == 0:
                elapsed = time.time() - step_start_time
                tokens_per_sec = (config.log_every * config.batch_size * config.max_seq_len * config.gradient_accumulation) / elapsed
                lr = scheduler.get_last_lr()[0]

                # Build log message with coherence metrics if available
                log_msg = (
                    f"Step {state.step:>6} | "
                    f"Loss: {avg_loss:.4f} | "
                    f"PPL: {math.exp(avg_loss):.2f} | "
                    f"LR: {lr:.2e} | "
                    f"Tok/s: {tokens_per_sec:.0f}"
                )

                # Add coherence metrics if enabled (S3, S1-S2, S5)
                if config.use_coherence_loss and "entropy" in metrics:
                    log_msg += f" | Ent: {metrics.get('entropy', 0):.2f}"
                    log_msg += f" | Coh: {metrics.get('coherence', 0):.3f}"

                # Add GPU memory usage for scaling experiments
                if device.type == "cuda":
                    mem_used = torch.cuda.max_memory_allocated() / (1024**3)  # GB
                    log_msg += f" | VRAM: {mem_used:.1f}GB"

                # Add alpha phase value (shows decay progress)
                log_msg += f" | α_phase: {current_alpha:.2f}"

                logger.info(log_msg)

                # Wandb logging
                if config.wandb and WANDB_AVAILABLE:
                    log_dict = {
                        "train/loss": avg_loss,
                        "train/perplexity": math.exp(avg_loss),
                        "train/learning_rate": lr,
                        "train/tokens_per_sec": tokens_per_sec,
                        "train/total_tokens": state.total_tokens,
                        "train/epoch": state.epoch,
                        "train/alpha_phase": current_alpha,
                    }
                    # Add coherence metrics
                    if config.use_coherence_loss:
                        log_dict.update({
                            "train/entropy": metrics.get("entropy", 0),
                            "train/coherence": metrics.get("coherence", 0),
                            "train/entropy_change": metrics.get("entropy_change", 0),
                        })
                    wandb.log(log_dict, step=state.step)

                # TensorBoard logging
                if tb_writer is not None:
                    tb_writer.add_scalar("train/loss", avg_loss, state.step)
                    tb_writer.add_scalar("train/perplexity", math.exp(avg_loss), state.step)
                    tb_writer.add_scalar("train/learning_rate", lr, state.step)
                    tb_writer.add_scalar("train/tokens_per_sec", tokens_per_sec, state.step)
                    # Add coherence metrics
                    if config.use_coherence_loss:
                        tb_writer.add_scalar("train/entropy", metrics.get("entropy", 0), state.step)
                        tb_writer.add_scalar("train/coherence", metrics.get("coherence", 0), state.step)

                # Note: step_start_time reset moved to after eval/checkpoint blocks
                # to exclude non-training time from throughput calculation

            # Evaluation
            if state.step % config.eval_every == 0:
                logger.info("Evaluating...")
                val_metrics = evaluate(model, val_loader, config, device)

                logger.info(
                    f"  Val Loss: {val_metrics['val_loss']:.4f} | "
                    f"Val PPL: {val_metrics['val_perplexity']:.2f}"
                )

                # Auto-reduce LR on PPL spike (50% worse than best)
                # Track best PPL (initialize if not set)
                if not hasattr(state, 'best_ppl'):
                    state.best_ppl = float('inf')

                current_ppl = val_metrics['val_perplexity']
                if current_ppl < state.best_ppl:
                    state.best_ppl = current_ppl
                elif current_ppl > state.best_ppl * 1.5 and state.step > config.warmup_steps // 2:
                    old_lr = optimizer.param_groups[0]['lr']
                    new_lr = old_lr * 0.5
                    for param_group in optimizer.param_groups:
                        param_group['lr'] = new_lr
                    logger.info(f"  ⚠️ PPL spike detected ({current_ppl:.1f} > {state.best_ppl:.1f}*1.5)! Reducing LR: {old_lr:.2e} → {new_lr:.2e}")

                # Track best
                if val_metrics['val_loss'] < state.best_val_loss:
                    state.best_val_loss = val_metrics['val_loss']
                    best_path = checkpoint_dir / "best.pt"
                    save_checkpoint(
                        model, optimizer, scheduler, scaler, state, config,
                        str(best_path)
                    )
                    logger.info(f"  New best! Saved to {best_path}")

                # Wandb logging
                if config.wandb and WANDB_AVAILABLE:
                    wandb.log({
                        "val/loss": val_metrics['val_loss'],
                        "val/perplexity": val_metrics['val_perplexity'],
                        "val/best_loss": state.best_val_loss,
                    }, step=state.step)

                # TensorBoard logging
                if tb_writer is not None:
                    tb_writer.add_scalar("val/loss", val_metrics['val_loss'], state.step)
                    tb_writer.add_scalar("val/perplexity", val_metrics['val_perplexity'], state.step)

            # Checkpointing
            if state.step % config.save_every == 0:
                ckpt_path = checkpoint_dir / f"step_{state.step}.pt"
                save_checkpoint(
                    model, optimizer, scheduler, scaler, state, config,
                    str(ckpt_path)
                )
                logger.info(f"Checkpoint saved to {ckpt_path}")

                # Also save as latest
                latest_path = checkpoint_dir / "latest.pt"
                save_checkpoint(
                    model, optimizer, scheduler, scaler, state, config,
                    str(latest_path)
                )

            # Reset throughput timer AFTER eval/checkpoint to exclude their time
            if state.step % config.log_every == 0:
                step_start_time = time.time()

    # Final save
    final_path = checkpoint_dir / "final.pt"
    save_checkpoint(
        model, optimizer, scheduler, scaler, state, config,
        str(final_path)
    )

    # Summary
    total_time = time.time() - start_time
    logger.info("=" * 60)
    logger.info("Training Complete!")
    logger.info("=" * 60)
    logger.info(f"Total steps: {state.step:,}")
    logger.info(f"Total tokens: {state.total_tokens:,}")
    logger.info(f"Total time: {total_time/3600:.2f} hours")
    logger.info(f"Avg tokens/sec: {state.total_tokens/total_time:.0f}")
    logger.info(f"Best val loss: {state.best_val_loss:.4f}")
    logger.info(f"Best val PPL: {math.exp(state.best_val_loss):.2f}")
    logger.info(f"Final checkpoint: {final_path}")

    # Cleanup
    if config.wandb and WANDB_AVAILABLE:
        wandb.finish()

    if tb_writer is not None:
        tb_writer.close()

    return state


# =============================================================================
# CLI
# =============================================================================

def parse_args() -> TrainingConfig:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Train SymbolU Phase Transformer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Model
    parser.add_argument("--model_size", type=str, default="small",
                       choices=["tiny", "small", "medium", "large", "xl", "7b"],
                       help="Model size preset")
    parser.add_argument("--model_type", type=str, default="phase",
                       choices=["phase", "hybrid"],
                       help="Model type: phase (pure O(n)) or hybrid (local + phase)")
    parser.add_argument("--vocab_size", type=int, default=50257,
                       help="Vocabulary size")
    parser.add_argument("--max_seq_len", type=int, default=1024,
                       help="Maximum sequence length")
    parser.add_argument("--dropout", type=float, default=0.1,
                       help="Dropout rate")

    # Phase parameters
    parser.add_argument("--sync_steps", type=int, default=3,
                       help="Phase synchronization steps")
    parser.add_argument("--sync_lr", type=float, default=0.1,
                       help="Phase synchronization learning rate")

    # Hybrid parameters (updated defaults for better long-range retrieval)
    parser.add_argument("--local_layers", type=int, default=6,
                       help="Number of early layers with local attention only (was 4, now 6)")
    parser.add_argument("--window_size", type=int, default=256,
                       help="Local attention window size (hybrid mode)")
    parser.add_argument("--local_backend", type=str, default="auto",
                       choices=["auto", "flash", "sdpa", "unfold"],
                       help="LocalAttention backend: flash (fastest), sdpa, unfold (fallback)")
    parser.add_argument("--alpha_local", type=float, default=0.4,
                       help="Weight for local attention in hybrid layers (was 0.8, now 0.4)")
    parser.add_argument("--alpha_phase", type=float, default=0.6,
                       help="Weight for phase attention in hybrid layers (was 0.2, now 0.6)")

    # Training
    parser.add_argument("--batch_size", type=int, default=16,
                       help="Batch size per GPU")
    parser.add_argument("--gradient_accumulation", type=int, default=1,
                       help="Gradient accumulation steps")
    parser.add_argument("--max_steps", type=int, default=100000,
                       help="Maximum training steps")
    parser.add_argument("--warmup_steps", type=int, default=2000,
                       help="Learning rate warmup steps")

    # Optimizer
    parser.add_argument("--learning_rate", type=float, default=3e-4,
                       help="Peak learning rate")
    parser.add_argument("--weight_decay", type=float, default=0.1,
                       help="Weight decay")
    parser.add_argument("--max_grad_norm", type=float, default=1.0,
                       help="Gradient clipping norm")

    # LR schedule
    parser.add_argument("--lr_scheduler", type=str, default="cosine",
                       choices=["cosine", "linear", "constant"],
                       help="Learning rate scheduler")
    parser.add_argument("--min_lr_ratio", type=float, default=0.1,
                       help="Minimum LR as ratio of peak")

    # Mixed precision
    parser.add_argument("--mixed_precision", type=str, default="bf16",
                       choices=["none", "fp16", "bf16"],
                       help="Mixed precision training")

    # Gradient checkpointing
    parser.add_argument("--gradient_checkpointing", action="store_true",
                       help="Enable gradient checkpointing (saves memory, slower)")

    # Chunked processing for ultra-long sequences
    parser.add_argument("--chunk_size", type=int, default=0,
                       help="Process sequence in chunks of this size (0=disabled). "
                            "Enables 10M+ token sequences on limited VRAM.")

    # Checkpointing
    parser.add_argument("--checkpoint_dir", type=str, default="checkpoints",
                       help="Checkpoint directory")
    parser.add_argument("--save_every", type=int, default=5000,
                       help="Save checkpoint every N steps")
    parser.add_argument("--eval_every", type=int, default=100,
                       help="Evaluate every N steps")
    parser.add_argument("--log_every", type=int, default=100,
                       help="Log every N steps")

    # Dataset
    parser.add_argument("--dataset", type=str, default="wikitext2",
                       choices=["c4", "wikitext103", "wikitext2", "custom"],
                       help="Dataset to train on")
    parser.add_argument("--dataset_path", type=str, default=None,
                       help="Path to custom dataset")
    parser.add_argument("--tokenizer", type=str, default="gpt2",
                       choices=["gpt2", "tiktoken"],
                       help="Tokenizer to use")

    # Evaluation
    parser.add_argument("--eval_samples", type=int, default=1000,
                       help="Number of evaluation samples")

    # Logging
    parser.add_argument("--wandb", action="store_true",
                       help="Enable Wandb logging")
    parser.add_argument("--wandb_project", type=str, default="symbolu",
                       help="Wandb project name")
    parser.add_argument("--wandb_run", type=str, default=None,
                       help="Wandb run name")
    parser.add_argument("--tensorboard", action="store_true",
                       help="Enable TensorBoard logging")

    # Hardware
    parser.add_argument("--device", type=str, default="auto",
                       choices=["auto", "cuda", "cpu"],
                       help="Device to use")
    parser.add_argument("--num_workers", type=int, default=4,
                       help="DataLoader workers")

    # Performance
    parser.add_argument("--compile", action="store_true", dest="use_compile",
                       help="Use torch.compile for 10-30%% speedup (PyTorch 2.0+)")
    parser.add_argument("--compile_mode", type=str, default="reduce-overhead",
                       choices=["default", "reduce-overhead", "max-autotune"],
                       help="torch.compile mode: default, reduce-overhead (faster), max-autotune (best)")

    # Resume
    parser.add_argument("--resume", type=str, default=None,
                       help="Resume from checkpoint")

    # Coherence Loss (S3, S1-S2, S8-S9)
    parser.add_argument("--use_coherence_loss", action="store_true", default=True,
                       help="Enable coherence-enhanced training (S3, S1-S2, S8-S9)")
    parser.add_argument("--no_coherence_loss", action="store_false", dest="use_coherence_loss",
                       help="Disable coherence loss")
    parser.add_argument("--lambda_entropy", type=float, default=0.01,
                       help="S5: Semantic entropy weight")
    parser.add_argument("--lambda_coherence", type=float, default=0.01,
                       help="S1-S2: Layer coherence weight")
    parser.add_argument("--lambda_stability", type=float, default=0.001,
                       help="S8-S9: Stability constraint weight")

    # Loss Type (memory-efficient options for 1M+ context)
    parser.add_argument("--loss_type", type=str, default="cross_entropy",
                       choices=["cross_entropy", "contrastive", "infonce", "state_delta"],
                       help="Loss type: cross_entropy (fused), contrastive (hinge), infonce (NCE), state_delta (no LM head)")
    parser.add_argument("--num_negatives", type=int, default=1024,
                       help="Number of negative samples for contrastive losses")
    parser.add_argument("--contrastive_margin", type=float, default=1.0,
                       help="Margin for contrastive hinge loss")
    parser.add_argument("--contrastive_temperature", type=float, default=0.1,
                       help="Temperature for InfoNCE loss")

    # State-Centric Training (for 10M+ context - NO LM head required!)
    parser.add_argument("--lambda_delta", type=float, default=1.0,
                       help="Weight for state delta prediction loss (state_delta mode)")
    parser.add_argument("--lambda_entropy_state", type=float, default=0.1,
                       help="Weight for entropy change loss (state_delta mode)")
    parser.add_argument("--lambda_constraint", type=float, default=0.1,
                       help="Weight for constraint satisfaction loss (state_delta mode)")
    parser.add_argument("--target_entropy_rate", type=float, default=0.5,
                       help="Target rate of entropy change for state-centric training")

    # Chunked LM Head (for ultra-long contexts)
    parser.add_argument("--lm_head_chunk_size", type=int, default=0,
                       help="Chunk size for LM head processing. 0=disabled. "
                            "Recommended: 8192 for 1M context, 4096 for 5M context. "
                            "Enables training on sequences up to 5M+ tokens.")

    # Seed
    parser.add_argument("--seed", type=int, default=42,
                       help="Random seed")

    args = parser.parse_args()

    # Create config from args
    config = TrainingConfig(**vars(args))

    return config


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    config = parse_args()

    # Get estimated parameter count
    preset = MODEL_PRESETS.get(config.model_size, {})
    embed = preset.get("embed_dim", 512)
    layers = preset.get("num_layers", 8)
    ff = preset.get("ff_dim", 2048)
    est_params = (embed * config.vocab_size +  # Embeddings
                  layers * (4 * embed * embed + 2 * embed * ff) +  # Attention + FFN
                  embed * config.vocab_size)  # Output projection
    est_params_str = f"{est_params/1e9:.1f}B" if est_params > 1e9 else f"{est_params/1e6:.0f}M"

    print("\n" + "=" * 70)
    print("  SYMBOLU LLM TRAINING")
    print("  Phase Attention Transformer with O(n) Complexity")
    print("=" * 70)
    print(f"\n  Model: {config.model_size} (~{est_params_str} params)")
    print(f"  Dataset: {config.dataset}")
    print(f"  Max steps: {config.max_steps:,}")
    print(f"  Batch size: {config.batch_size} x {config.gradient_accumulation} accumulation")
    print(f"  Effective batch: {config.batch_size * config.gradient_accumulation * config.max_seq_len:,} tokens")
    print(f"  Learning rate: {config.learning_rate}")
    print(f"  Mixed precision: {config.mixed_precision}")
    print(f"  Loss type: {config.loss_type}", end="")
    if config.loss_type in ("contrastive", "infonce"):
        print(f" (num_neg={config.num_negatives})")
    elif config.loss_type == "state_delta":
        print(f" (NO LM HEAD - 65x memory savings!)")
        print(f"  State-centric training: λ_delta={config.lambda_delta}, λ_entropy={config.lambda_entropy_state}, λ_constraint={config.lambda_constraint}")
    else:
        print(" (fused)")
    if config.gradient_checkpointing:
        print(f"  Gradient checkpointing: ENABLED (saves memory)")
    if preset.get("use_gqa"):
        print(f"  Grouped Query Attention: {preset['num_heads']} heads, {preset.get('num_kv_heads', 8)} KV heads")
    print()

    try:
        train(config)
    except KeyboardInterrupt:
        print("\nTraining interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nTraining failed: {e}")
        raise
