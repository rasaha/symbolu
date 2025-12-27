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
    local_layers: int = 4  # Number of early layers with local attention only
    window_size: int = 256  # Local attention window size
    local_backend: str = "auto"  # LocalAttention backend: auto, flash, sdpa, unfold
    alpha_local: float = 0.8  # Weight for local attention in hybrid layers
    alpha_phase: float = 0.2  # Weight for phase attention in hybrid layers

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

    # Resume
    resume: Optional[str] = None

    # Coherence Loss (S3, S1-S2, S8-S9)
    use_coherence_loss: bool = True  # Enable coherence-enhanced training
    lambda_entropy: float = 0.01     # S5: Semantic entropy weight
    lambda_coherence: float = 0.01   # S1-S2: Layer coherence weight
    lambda_stability: float = 0.001  # S8-S9: Stability constraint weight

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

    # Create dataloaders
    train_loader = DataLoader(
        train_dataset,
        batch_size=config.batch_size,
        shuffle=True,
        num_workers=config.num_workers,
        pin_memory=config.pin_memory,
        drop_last=True,
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=config.num_workers,
        pin_memory=config.pin_memory,
        drop_last=True,
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
    Compute semantic entropy (Formula S5).

    H_sem = -Σ pₖ log pₖ

    Lower entropy = more confident/focused predictions.

    For long sequences, samples positions to avoid OOM on full softmax.
    At 16K context, full logits = 3.3GB - sampling 1024 positions = 0.2GB.
    """
    B, N, V = logits.shape

    # Sample positions if sequence is too long (memory optimization)
    if N > max_positions:
        # Sample evenly spaced positions for representative entropy
        indices = torch.linspace(0, N - 1, max_positions, dtype=torch.long, device=logits.device)
        logits = logits[:, indices, :]  # (B, max_positions, V)

    # Compute entropy efficiently using log_softmax (avoids separate probs tensor)
    log_probs = F.log_softmax(logits, dim=-1)
    probs = log_probs.exp()  # More memory efficient than separate softmax
    entropy = -(probs * log_probs).sum(dim=-1)
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


# Global state for entropy stability tracking (S8-S9)
_prev_entropy = None


def compute_loss(
    model: PhaseTransformer,
    batch: Tuple[torch.Tensor, torch.Tensor],
    device: torch.device,
    use_coherence_loss: bool = True,
    lambda_entropy: float = 0.01,
    lambda_coherence: float = 0.01,
    lambda_stability: float = 0.001,
) -> Tuple[torch.Tensor, Dict[str, float]]:
    """
    Compute enhanced loss with coherence formulas (S3, S1-S2, S8-S9).

    L_coherence = L_task + λ_e·L_entropy + λ_c·L_coherence + λ_s·L_stability

    Where:
    - L_task: Standard cross-entropy (next-token prediction)
    - L_entropy: Semantic entropy regularization (S5) - encourages confident predictions
    - L_coherence: Layer coherence (S1-S2) - encourages aligned representations
    - L_stability: Entropy stability (S8) - penalizes entropy spikes
    """
    global _prev_entropy

    x, y = batch
    x = x.to(device)
    y = y.to(device)

    # Forward pass with hidden states for layer coherence
    output = model(x, return_hidden=True)
    logits = output['logits']
    hidden_states = output.get('hidden_states', [])

    # Compute task loss (standard cross-entropy)
    B, N, V = logits.shape
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
        # S5: Semantic Entropy - target moderate entropy (not too high, not too low)
        entropy = compute_semantic_entropy(logits)
        target_entropy = 4.0  # ~moderate confidence
        L_entropy = (entropy - target_entropy).pow(2)
        metrics["entropy"] = entropy.item()

        # =================================================================
        # UPDATE GATE: Detect likely state changes/updates
        # High entropy or entropy spike → reduce coherence penalty
        # This allows the model to "update" information without being
        # penalized for breaking coherence with earlier context
        # =================================================================

        # Normalize entropy to [0, 1] range (max entropy ~ log(vocab) ≈ 10.8)
        max_entropy = 10.8  # log(50257)
        normalized_entropy = torch.clamp(entropy / max_entropy, 0.0, 1.0)

        # Update gate: high when entropy is high (uncertain/changing context)
        # Using sigmoid to smooth the gate
        # When entropy > 6.0 (moderately uncertain), gate starts activating
        entropy_threshold = 6.0
        update_gate = torch.sigmoid((entropy - entropy_threshold) * 2.0)

        # Also consider entropy change (sudden spike = likely update)
        if _prev_entropy is not None:
            entropy_change = entropy - _prev_entropy
            # Positive change (entropy increase) activates gate more
            change_gate = torch.sigmoid(entropy_change * 5.0)
            # Combine both signals
            update_gate = torch.max(update_gate, change_gate * 0.5)

        metrics["update_gate"] = update_gate.item()

        # =================================================================
        # CONDITIONAL COHERENCE: λ * (1 - g_update) * L_coh
        # When update_gate is high, reduce coherence penalty
        # =================================================================
        coherence_scale = 1.0 - update_gate  # Reduce coherence loss during updates

        # S1-S2: Layer Coherence - maximize cross-layer alignment
        if hidden_states:
            coherence = compute_layer_coherence(hidden_states)
            L_coherence_term = 1.0 - coherence  # Penalize low coherence
            metrics["coherence"] = coherence.item()
        else:
            L_coherence_term = torch.tensor(0.0, device=device)
            metrics["coherence"] = 0.0

        # S8-S9: Stability Constraint - penalize entropy spikes
        if _prev_entropy is not None:
            entropy_change = entropy - _prev_entropy
            # Penalize increases (dH/dt > 0 violates S8)
            L_stability = F.relu(entropy_change)
            metrics["entropy_change"] = entropy_change.item()
        else:
            L_stability = torch.tensor(0.0, device=device)
            metrics["entropy_change"] = 0.0

        _prev_entropy = entropy.detach()

        # Combined Coherence Loss (S3) with conditional gating
        # Coherence and stability losses are scaled by (1 - update_gate)
        loss = (L_task +
                lambda_entropy * L_entropy +
                lambda_coherence * coherence_scale * L_coherence_term +
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
        loss, metrics = compute_loss(
            model, batch, device,
            use_coherence_loss=config.use_coherence_loss,
            lambda_entropy=config.lambda_entropy,
            lambda_coherence=config.lambda_coherence,
            lambda_stability=config.lambda_stability,
        )
        loss = loss / config.gradient_accumulation

    # Backward pass
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

                step_start_time = time.time()

            # Evaluation
            if state.step % config.eval_every == 0:
                logger.info("Evaluating...")
                val_metrics = evaluate(model, val_loader, config, device)

                logger.info(
                    f"  Val Loss: {val_metrics['val_loss']:.4f} | "
                    f"Val PPL: {val_metrics['val_perplexity']:.2f}"
                )

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

    # Hybrid parameters
    parser.add_argument("--local_layers", type=int, default=4,
                       help="Number of early layers with local attention only (hybrid mode)")
    parser.add_argument("--window_size", type=int, default=256,
                       help="Local attention window size (hybrid mode)")
    parser.add_argument("--local_backend", type=str, default="auto",
                       choices=["auto", "flash", "sdpa", "unfold"],
                       help="LocalAttention backend: flash (fastest), sdpa, unfold (fallback)")
    parser.add_argument("--alpha_local", type=float, default=0.8,
                       help="Weight for local attention in hybrid layers")
    parser.add_argument("--alpha_phase", type=float, default=0.2,
                       help="Weight for phase attention in hybrid layers")

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
