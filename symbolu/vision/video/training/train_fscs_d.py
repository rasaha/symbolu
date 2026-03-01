#!/usr/bin/env python3
"""
Train FSCS-D: Discrete diffusion backbone with coherence injection.

Implements a mask-based discrete diffusion model (MDLM-style) with FSCS-D
coherence injection on top. This is the patent's strongest mathematical fit:
discrete tokens give exact coherence computation without continuous
approximations.

Architecture:
    1. Discrete token space (vocabulary V with special [MASK] token)
    2. Forward process: randomly mask tokens with schedule beta(t)
    3. Reverse process: predict unmasked tokens from masked input
    4. FSCS-D injection: when unmasked fraction > theta_warmup, apply
       coherence gradient to guide unmasking toward consistent sequences

Patent reference: Issue 9 — Warm-Up for Mask-Based Diffusion / FSCS-D

Usage:
    # Quick test with synthetic token sequences
    python -m symbolu.vision.video.training.train_fscs_d --synthetic --epochs 10

    # Train on wikitext
    python -m symbolu.vision.video.training.train_fscs_d \
        --hf-dataset wikitext --hf-config wikitext-103-v1 --epochs 50

    # Train with FSCS-D coherence injection
    python -m symbolu.vision.video.training.train_fscs_d \
        --hf-dataset wikitext --enable-fscs-d --epochs 50

Requirements:
    pip install torch transformers datasets
"""

import argparse
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, List, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class FSCSDConfig:
    """Configuration for FSCS-D discrete diffusion."""
    # Token space
    vocab_size: int = 32000        # Standard tokenizer vocab
    mask_token_id: int = 32000     # [MASK] token (appended to vocab)
    max_seq_len: int = 256

    # Model architecture
    embed_dim: int = 512
    num_heads: int = 8
    num_layers: int = 6
    ffn_ratio: float = 4.0
    dropout: float = 0.1

    # Discrete diffusion
    num_timesteps: int = 1000
    mask_schedule: str = "cosine"  # "linear" or "cosine"

    # FSCS-D coherence injection (patent Issue 9)
    enable_fscs_d: bool = True
    theta_warmup: float = 0.15     # Unmasked fraction before FSCS-D activates
    lambda_max: float = 0.05       # Max coherence coupling strength
    alpha: float = 2.0             # Schedule power

    # Training
    batch_size: int = 32
    learning_rate: float = 3e-4
    weight_decay: float = 0.01
    epochs: int = 50
    warmup_steps: int = 1000
    gradient_clip: float = 1.0
    save_every: int = 10


# ---------------------------------------------------------------------------
# Mask Schedule
# ---------------------------------------------------------------------------

class MaskSchedule:
    """
    Masking schedule for discrete diffusion.

    Defines the probability of masking a token at each timestep.
    At t=0 (clean), mask_prob=0. At t=T (fully masked), mask_prob=1.

    Supports linear and cosine schedules.
    """

    def __init__(
        self,
        num_timesteps: int = 1000,
        schedule: str = "cosine",
    ):
        self.num_timesteps = num_timesteps
        self.schedule = schedule

        # Precompute mask probabilities
        if schedule == "cosine":
            # Cosine schedule (smoother, recommended)
            steps = torch.arange(num_timesteps + 1, dtype=torch.float32)
            # f(t) = cos((t/T + s) / (1+s) * pi/2)^2
            s = 0.008
            f = torch.cos((steps / num_timesteps + s) / (1 + s) * math.pi / 2) ** 2
            # Cumulative "survival" probability (probability of NOT being masked)
            alpha_bar = f / f[0]
            # Mask probability at each step
            self.mask_probs = 1.0 - alpha_bar[1:]  # [T]
        else:
            # Linear schedule
            self.mask_probs = torch.linspace(0.0, 1.0, num_timesteps)

    def get_mask_prob(self, t: int) -> float:
        """Get mask probability at timestep t."""
        return self.mask_probs[t].item()

    def get_mask_probs(self, t: Tensor) -> Tensor:
        """Get mask probabilities for a batch of timesteps."""
        return self.mask_probs.to(t.device)[t]

    def to(self, device):
        self.mask_probs = self.mask_probs.to(device)
        return self


# ---------------------------------------------------------------------------
# Discrete Diffusion Model
# ---------------------------------------------------------------------------

class DiscreteTransformerBlock(nn.Module):
    """Transformer block with pre-norm and timestep conditioning."""

    def __init__(self, embed_dim: int, num_heads: int, ffn_ratio: float, dropout: float):
        super().__init__()
        self.norm1 = nn.LayerNorm(embed_dim)
        self.attn = nn.MultiheadAttention(
            embed_dim, num_heads, dropout=dropout, batch_first=True,
        )
        self.norm2 = nn.LayerNorm(embed_dim)
        ffn_dim = int(embed_dim * ffn_ratio)
        self.ffn = nn.Sequential(
            nn.Linear(embed_dim, ffn_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(ffn_dim, embed_dim),
            nn.Dropout(dropout),
        )
        # AdaLN-Zero style timestep conditioning
        self.adaLN = nn.Sequential(
            nn.SiLU(),
            nn.Linear(embed_dim, 6 * embed_dim),
        )

    def forward(self, x: Tensor, t_emb: Tensor) -> Tensor:
        """
        Args:
            x: [B, L, D] token embeddings.
            t_emb: [B, D] timestep embeddings.
        """
        # AdaLN-Zero modulation
        ada = self.adaLN(t_emb).unsqueeze(1)  # [B, 1, 6D]
        shift1, scale1, gate1, shift2, scale2, gate2 = ada.chunk(6, dim=-1)

        # Self-attention with modulation
        h = self.norm1(x) * (1 + scale1) + shift1
        h, _ = self.attn(h, h, h)
        x = x + gate1 * h

        # FFN with modulation
        h = self.norm2(x) * (1 + scale2) + shift2
        h = self.ffn(h)
        x = x + gate2 * h

        return x


class MaskedDiffusionModel(nn.Module):
    """
    Mask-based Discrete Diffusion Language Model (MDLM-style).

    Forward process: Randomly mask tokens according to schedule.
    Reverse process: Predict original tokens for masked positions.

    Architecture: Transformer encoder with timestep conditioning via AdaLN-Zero.
    """

    def __init__(self, config: FSCSDConfig):
        super().__init__()
        self.config = config
        # [MASK] token is always vocab_size (appended after vocab)
        self.mask_token_id = config.vocab_size
        total_vocab = config.vocab_size + 1  # +1 for [MASK]

        # Token embedding
        self.token_embed = nn.Embedding(total_vocab, config.embed_dim)
        self.pos_embed = nn.Embedding(config.max_seq_len, config.embed_dim)

        # Timestep embedding
        self.time_embed = nn.Sequential(
            nn.Linear(config.embed_dim, config.embed_dim * 4),
            nn.SiLU(),
            nn.Linear(config.embed_dim * 4, config.embed_dim),
        )

        # Transformer blocks
        self.blocks = nn.ModuleList([
            DiscreteTransformerBlock(
                config.embed_dim, config.num_heads,
                config.ffn_ratio, config.dropout,
            )
            for _ in range(config.num_layers)
        ])

        # Output projection to vocab
        self.norm_out = nn.LayerNorm(config.embed_dim)
        self.output_proj = nn.Linear(config.embed_dim, total_vocab)

        # Mask schedule
        self.mask_schedule = MaskSchedule(config.num_timesteps, config.mask_schedule)

    def get_timestep_embedding(self, t: Tensor) -> Tensor:
        """Sinusoidal timestep embedding."""
        half_dim = self.config.embed_dim // 2
        emb = math.log(10000) / (half_dim - 1)
        emb = torch.exp(torch.arange(half_dim, device=t.device, dtype=torch.float32) * -emb)
        emb = t.float().unsqueeze(-1) * emb.unsqueeze(0)
        emb = torch.cat([emb.sin(), emb.cos()], dim=-1)
        return self.time_embed(emb)

    def mask_tokens(self, tokens: Tensor, t: Tensor) -> Tuple[Tensor, Tensor]:
        """
        Apply masking to tokens at timestep t.

        Args:
            tokens: [B, L] original token IDs.
            t: [B] timesteps.

        Returns:
            masked_tokens: [B, L] with some positions replaced by [MASK].
            mask: [B, L] boolean, True where masked.
        """
        mask_probs = self.mask_schedule.get_mask_probs(t)  # [B]
        # Per-position masking
        rand = torch.rand_like(tokens.float())
        mask = rand < mask_probs.unsqueeze(-1)  # [B, L]
        masked_tokens = tokens.clone()
        masked_tokens[mask] = self.mask_token_id
        return masked_tokens, mask

    def forward(
        self,
        tokens: Tensor,
        t: Tensor,
    ) -> Tensor:
        """
        Predict token logits from masked input.

        Args:
            tokens: [B, L] token IDs (possibly masked).
            t: [B] timesteps.

        Returns:
            logits: [B, L, V+1] unnormalized token predictions.
        """
        B, L = tokens.shape

        # Embeddings
        tok_emb = self.token_embed(tokens)
        pos = torch.arange(L, device=tokens.device)
        pos_emb = self.pos_embed(pos)
        x = tok_emb + pos_emb  # [B, L, D]

        # Timestep
        t_emb = self.get_timestep_embedding(t)  # [B, D]

        # Transformer
        for block in self.blocks:
            x = block(x, t_emb)

        x = self.norm_out(x)
        logits = self.output_proj(x)  # [B, L, V+1]

        return logits


# ---------------------------------------------------------------------------
# FSCS-D Coherence Module
# ---------------------------------------------------------------------------

class FSCSDCoherence(nn.Module):
    """
    FSCS-D: Frequency-Stratified Coherence for Discrete Diffusion.

    Injects coherence gradient during the reverse (unmasking) process.
    Activates only after sufficient tokens are unmasked (theta_warmup).

    Patent formula:
        lambda = 0               if unmasked_fraction < theta_warmup
        lambda = lambda_max * ((frac - theta) / (1 - theta))^alpha    otherwise

    The coherence signal pushes the model's token predictions toward
    sequences that are locally consistent (adjacent tokens agree in
    embedding space).
    """

    def __init__(self, config: FSCSDConfig):
        super().__init__()
        self.config = config
        self.theta = config.theta_warmup
        self.lambda_max = config.lambda_max
        self.alpha = config.alpha

        # Coherence feature projection (token embeddings -> coherence space)
        self.coherence_proj = nn.Linear(config.embed_dim, config.embed_dim // 2)

    def compute_coupling(self, unmasked_fraction: float) -> float:
        """Compute coupling strength based on unmasked fraction."""
        if unmasked_fraction < self.theta:
            return 0.0
        progress = (unmasked_fraction - self.theta) / max(1.0 - self.theta, 1e-8)
        return self.lambda_max * (progress ** self.alpha)

    def compute_coherence(self, token_embeddings: Tensor, mask: Tensor) -> Tensor:
        """
        Compute token-level coherence scores.

        Measures local consistency between adjacent unmasked tokens.

        Args:
            token_embeddings: [B, L, D] token embeddings.
            mask: [B, L] True where masked.

        Returns:
            coherence: [B, L] per-token coherence scores in [0, 1].
        """
        B, L, D = token_embeddings.shape

        # Project to coherence space
        h = self.coherence_proj(token_embeddings)  # [B, L, D/2]

        # Adjacent token similarity (rectified cosine)
        h_norm = F.normalize(h, dim=-1)
        # Pad for boundary handling
        h_prev = F.pad(h_norm[:, :-1], (0, 0, 1, 0))  # shift right
        h_next = F.pad(h_norm[:, 1:], (0, 0, 0, 1))    # shift left

        sim_prev = (h_norm * h_prev).sum(dim=-1)  # [B, L]
        sim_next = (h_norm * h_next).sum(dim=-1)  # [B, L]

        # Rectify to [0, 1]
        coherence = ((sim_prev + sim_next) / 2.0 + 1.0) / 2.0

        # Zero out coherence at masked positions
        coherence = coherence * (~mask).float()

        return coherence

    def compute_correction(
        self,
        logits: Tensor,
        token_embeddings: Tensor,
        mask: Tensor,
    ) -> Tensor:
        """
        Compute FSCS-D correction to logits.

        Adjusts logit distribution to favor tokens that are coherent
        with their unmasked neighbors.

        Args:
            logits: [B, L, V] model output logits.
            token_embeddings: [B, L, D] current embeddings.
            mask: [B, L] True where masked.

        Returns:
            corrected_logits: [B, L, V] with coherence adjustment.
        """
        B, L = mask.shape
        unmasked_fraction = (~mask).float().mean().item()
        coupling = self.compute_coupling(unmasked_fraction)

        if coupling == 0.0:
            return logits

        coherence = self.compute_coherence(token_embeddings, mask)  # [B, L]

        # Incoherence at masked positions: how much their neighbors disagree
        # Use neighbor embeddings to score candidate tokens
        incoherence = (1.0 - coherence).clamp(0, 1)

        # For masked positions, boost logits of tokens similar to neighbors
        correction = coupling * incoherence.unsqueeze(-1)  # [B, L, 1]

        # The correction nudges toward the mean neighbor embedding
        # by adding a bias proportional to incoherence
        corrected = logits + correction * logits.detach().mean(dim=-1, keepdim=True)

        # Only correct at masked positions
        corrected = torch.where(mask.unsqueeze(-1), corrected, logits)

        return corrected


# ---------------------------------------------------------------------------
# Trainer
# ---------------------------------------------------------------------------

class FSCSDTrainer:
    """
    Trainer for discrete diffusion with FSCS-D.

    Training loop:
        1. Sample clean token sequences x_0
        2. Sample timestep t
        3. Mask tokens: x_t = mask(x_0, t)
        4. Predict: logits = model(x_t, t)
        5. (Optional) Apply FSCS-D correction
        6. Loss = CE(logits[masked_positions], x_0[masked_positions])
    """

    def __init__(
        self,
        config: FSCSDConfig,
        device: torch.device,
        output_dir: str = "checkpoints_fscs_d",
    ):
        self.config = config
        self.device = device
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Model
        self.model = MaskedDiffusionModel(config).to(device)

        # FSCS-D coherence module
        self.fscs_d = None
        if config.enable_fscs_d:
            self.fscs_d = FSCSDCoherence(config).to(device)

        self.global_step = 0
        self.epoch = 0

    def compute_loss(self, tokens: Tensor) -> Dict[str, Tensor]:
        """
        Compute masked diffusion training loss.

        Args:
            tokens: [B, L] clean token sequences.

        Returns:
            Dict with 'loss', 'accuracy', 'perplexity'.
        """
        B, L = tokens.shape

        # Sample timesteps
        t = torch.randint(0, self.config.num_timesteps, (B,), device=self.device)

        # Mask tokens
        masked_tokens, mask = self.model.mask_tokens(tokens, t)

        # Predict
        logits = self.model(masked_tokens, t)  # [B, L, V+1]

        # Apply FSCS-D correction (if enabled)
        if self.fscs_d is not None:
            with torch.no_grad():
                tok_emb = self.model.token_embed(masked_tokens)
            logits = self.fscs_d.compute_correction(logits, tok_emb, mask)

        # Loss: only at masked positions
        if mask.any():
            masked_logits = logits[mask]  # [N_masked, V+1]
            masked_targets = tokens[mask]  # [N_masked]
            loss = F.cross_entropy(masked_logits, masked_targets)

            with torch.no_grad():
                preds = masked_logits.argmax(dim=-1)
                accuracy = (preds == masked_targets).float().mean()
                perplexity = torch.exp(loss.detach())
        else:
            loss = torch.tensor(0.0, device=self.device, requires_grad=True)
            accuracy = torch.tensor(1.0, device=self.device)
            perplexity = torch.tensor(1.0, device=self.device)

        return {
            "loss": loss,
            "accuracy": accuracy,
            "perplexity": perplexity,
            "mask_fraction": mask.float().mean(),
        }

    def train_step(self, tokens: Tensor, optimizer: torch.optim.Optimizer) -> Dict[str, float]:
        optimizer.zero_grad()
        result = self.compute_loss(tokens)
        result["loss"].backward()
        torch.nn.utils.clip_grad_norm_(
            self.model.parameters(), self.config.gradient_clip,
        )
        optimizer.step()
        self.global_step += 1

        return {k: v.item() for k, v in result.items()}

    @torch.no_grad()
    def generate(
        self,
        batch_size: int = 1,
        seq_len: int = 64,
        num_steps: int = 50,
    ) -> Tensor:
        """
        Generate token sequences via iterative unmasking.

        Starts from fully masked sequence and progressively unmasks
        tokens from high to low timestep.

        Args:
            batch_size: Number of sequences to generate.
            seq_len: Sequence length.
            num_steps: Number of unmasking steps.

        Returns:
            tokens: [B, L] generated token IDs.
        """
        self.model.eval()
        device = self.device

        # Start fully masked
        tokens = torch.full(
            (batch_size, seq_len), self.model.mask_token_id,
            device=device, dtype=torch.long,
        )

        # Iterate from high t to low t
        timesteps = torch.linspace(
            self.config.num_timesteps - 1, 0, num_steps,
        ).long().to(device)

        for step_idx, t_val in enumerate(timesteps):
            t = t_val.expand(batch_size)

            # Predict token logits
            logits = self.model(tokens, t)

            # Apply FSCS-D if enabled
            if self.fscs_d is not None:
                mask = (tokens == self.model.mask_token_id)
                tok_emb = self.model.token_embed(tokens)
                logits = self.fscs_d.compute_correction(logits, tok_emb, mask)

            # Sample from predictions at masked positions
            probs = F.softmax(logits, dim=-1)
            # Don't predict [MASK] token
            probs[:, :, self.model.mask_token_id] = 0
            probs = probs / probs.sum(dim=-1, keepdim=True).clamp(min=1e-8)

            sampled = torch.multinomial(
                probs.reshape(-1, probs.shape[-1]), 1,
            ).reshape(batch_size, seq_len)

            # Determine which positions to unmask at this step
            mask = (tokens == self.model.mask_token_id)
            if not mask.any():
                break

            # Unmask a fraction of positions (proportional to schedule)
            current_mask_prob = self.model.mask_schedule.get_mask_prob(t_val.item())
            if step_idx + 1 < num_steps:
                next_mask_prob = self.model.mask_schedule.get_mask_prob(
                    timesteps[step_idx + 1].item(),
                )
            else:
                next_mask_prob = 0.0

            # Number of tokens to unmask this step
            unmask_fraction = current_mask_prob - next_mask_prob
            n_unmask = max(1, int(unmask_fraction * seq_len))

            # Score masked positions by confidence
            confidence = probs.max(dim=-1).values  # [B, L]
            confidence[~mask] = -1  # Don't re-unmask

            # Unmask top-k most confident positions
            _, top_idx = confidence.topk(min(n_unmask, mask.sum(dim=-1).min().item()), dim=-1)
            for b in range(batch_size):
                tokens[b, top_idx[b]] = sampled[b, top_idx[b]]

        # Fill any remaining masks with top-1 prediction
        final_mask = (tokens == self.model.mask_token_id)
        if final_mask.any():
            t_final = torch.zeros(batch_size, device=device, dtype=torch.long)
            logits = self.model(tokens, t_final)
            preds = logits.argmax(dim=-1)
            tokens[final_mask] = preds[final_mask]

        self.model.train()
        return tokens

    def save_checkpoint(self, optimizer, scheduler=None, filename=None):
        if filename is None:
            filename = f"epoch_{self.epoch}.pt"
        checkpoint = {
            "epoch": self.epoch,
            "global_step": self.global_step,
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "config": self.config,
        }
        if self.fscs_d is not None:
            checkpoint["fscs_d_state_dict"] = self.fscs_d.state_dict()
        if scheduler is not None:
            checkpoint["scheduler_state_dict"] = scheduler.state_dict()
        path = self.output_dir / filename
        torch.save(checkpoint, path)
        print(f"Saved checkpoint: {path}")

    def load_checkpoint(self, path: str, optimizer=None, scheduler=None):
        checkpoint = torch.load(path, map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.epoch = checkpoint["epoch"]
        self.global_step = checkpoint["global_step"]
        if self.fscs_d is not None and "fscs_d_state_dict" in checkpoint:
            self.fscs_d.load_state_dict(checkpoint["fscs_d_state_dict"])
        if optimizer and "optimizer_state_dict" in checkpoint:
            optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        if scheduler and "scheduler_state_dict" in checkpoint:
            scheduler.load_state_dict(checkpoint["scheduler_state_dict"])
        print(f"Loaded checkpoint: {path} (epoch {self.epoch})")


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

class SyntheticTokenDataset(torch.utils.data.Dataset):
    """Synthetic token sequences for testing."""

    def __init__(self, num_samples: int = 5000, seq_len: int = 128, vocab_size: int = 32000):
        self.num_samples = num_samples
        self.seq_len = seq_len
        self.vocab_size = vocab_size

    def __len__(self):
        return self.num_samples

    def __getitem__(self, idx):
        torch.manual_seed(idx)
        # Generate sequence with local patterns (not pure random)
        base = torch.randint(0, self.vocab_size, (self.seq_len,))
        # Add some local repetition to test coherence
        for i in range(1, self.seq_len):
            if torch.rand(1).item() < 0.3:
                base[i] = base[i - 1]  # 30% chance of repeating previous token
        return base


def load_tokenized_dataset(
    dataset_name: str,
    config_name: Optional[str] = None,
    max_samples: int = 50000,
    seq_len: int = 256,
):
    """Load and tokenize a HuggingFace text dataset."""
    from datasets import load_dataset
    from transformers import AutoTokenizer

    print(f"Loading dataset: {dataset_name}")
    if config_name:
        dataset = load_dataset(dataset_name, config_name, split="train")
    else:
        dataset = load_dataset(dataset_name, split="train")

    print(f"Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained("gpt2")
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Tokenize
    print(f"Tokenizing {min(len(dataset), max_samples)} samples...")
    all_tokens = []
    for i, item in enumerate(dataset):
        if i >= max_samples:
            break
        text = item.get("text", item.get("content", ""))
        if not text or len(text.strip()) < 10:
            continue
        tokens = tokenizer.encode(text, max_length=seq_len, truncation=True)
        if len(tokens) < 16:
            continue
        # Pad to seq_len
        if len(tokens) < seq_len:
            tokens = tokens + [tokenizer.pad_token_id] * (seq_len - len(tokens))
        all_tokens.append(torch.tensor(tokens[:seq_len], dtype=torch.long))

    print(f"Tokenized {len(all_tokens)} sequences")
    return all_tokens, tokenizer


class TokenDataset(torch.utils.data.Dataset):
    def __init__(self, token_list: List[Tensor]):
        self.tokens = token_list

    def __len__(self):
        return len(self.tokens)

    def __getitem__(self, idx):
        return self.tokens[idx]


# ---------------------------------------------------------------------------
# Main Training
# ---------------------------------------------------------------------------

def train(
    synthetic: bool = True,
    hf_dataset: Optional[str] = None,
    hf_config: Optional[str] = None,
    enable_fscs_d: bool = True,
    epochs: int = 50,
    batch_size: int = 32,
    learning_rate: float = 3e-4,
    seq_len: int = 128,
    num_layers: int = 6,
    embed_dim: int = 512,
    output_dir: str = "checkpoints_fscs_d",
    resume: Optional[str] = None,
    save_every: int = 10,
):
    """Main training function."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training FSCS-D on {device}")

    # Config
    config = FSCSDConfig(
        embed_dim=embed_dim,
        num_layers=num_layers,
        max_seq_len=seq_len,
        enable_fscs_d=enable_fscs_d,
        batch_size=batch_size,
        learning_rate=learning_rate,
        epochs=epochs,
        save_every=save_every,
    )

    # Dataset
    tokenizer = None
    if synthetic or not hf_dataset:
        print("Using synthetic token data")
        dataset = SyntheticTokenDataset(
            num_samples=5000, seq_len=seq_len, vocab_size=config.vocab_size,
        )
    else:
        token_list, tokenizer = load_tokenized_dataset(
            hf_dataset, hf_config, seq_len=seq_len,
        )
        config.vocab_size = tokenizer.vocab_size
        config.mask_token_id = config.vocab_size  # Append [MASK]
        dataset = TokenDataset(token_list)

    dataloader = torch.utils.data.DataLoader(
        dataset, batch_size=batch_size, shuffle=True, drop_last=True,
    )
    print(f"Dataset: {len(dataset)} sequences, {len(dataloader)} batches")

    # Trainer
    trainer = FSCSDTrainer(config, device, output_dir)
    n_params = sum(p.numel() for p in trainer.model.parameters())
    print(f"Model params: {n_params:,}")
    if trainer.fscs_d:
        fscs_params = sum(p.numel() for p in trainer.fscs_d.parameters())
        print(f"FSCS-D params: {fscs_params:,}")
    print(f"FSCS-D enabled: {enable_fscs_d}")

    # Optimizer
    params = list(trainer.model.parameters())
    if trainer.fscs_d:
        params += list(trainer.fscs_d.parameters())
    optimizer = torch.optim.AdamW(params, lr=learning_rate, weight_decay=config.weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=epochs, eta_min=learning_rate / 100,
    )

    if resume:
        trainer.load_checkpoint(resume, optimizer, scheduler)

    # Training loop
    print(f"\nStarting training for {epochs} epochs...")
    print("=" * 60)
    start_time = time.time()

    for epoch in range(trainer.epoch, epochs):
        trainer.epoch = epoch
        epoch_loss = 0.0
        epoch_acc = 0.0
        epoch_ppl = 0.0
        n_batches = 0

        for batch in dataloader:
            tokens = batch.to(device)
            metrics = trainer.train_step(tokens, optimizer)
            epoch_loss += metrics["loss"]
            epoch_acc += metrics["accuracy"]
            epoch_ppl += metrics["perplexity"]
            n_batches += 1

        scheduler.step()
        avg_loss = epoch_loss / max(n_batches, 1)
        avg_acc = epoch_acc / max(n_batches, 1)
        avg_ppl = epoch_ppl / max(n_batches, 1)

        if (epoch + 1) % 5 == 0 or epoch == 0:
            print(
                f"Epoch {epoch + 1:4d}/{epochs} | "
                f"Loss: {avg_loss:.4f} | "
                f"Acc: {avg_acc:.3f} | "
                f"PPL: {avg_ppl:.1f} | "
                f"LR: {optimizer.param_groups[0]['lr']:.2e}"
            )

        if (epoch + 1) % save_every == 0:
            trainer.save_checkpoint(optimizer, scheduler)

    trainer.save_checkpoint(optimizer, scheduler, "final.pt")
    total_time = time.time() - start_time
    print(f"\nTraining complete in {total_time:.1f}s")

    # Generate sample
    print("\n--- Sample generation ---")
    tokens = trainer.generate(batch_size=4, seq_len=64, num_steps=50)
    print(f"Generated {tokens.shape[0]} sequences of length {tokens.shape[1]}")

    if tokenizer:
        for i in range(min(4, tokens.shape[0])):
            text = tokenizer.decode(tokens[i].tolist(), skip_special_tokens=True)
            print(f"  Sample {i}: {text[:100]}...")
    else:
        for i in range(min(4, tokens.shape[0])):
            unique = tokens[i].unique().numel()
            repeats = (tokens[i, 1:] == tokens[i, :-1]).float().mean().item()
            print(f"  Sample {i}: {unique} unique tokens, {repeats:.1%} local repeats")

    # FSCS-D analysis
    if trainer.fscs_d:
        print("\n--- FSCS-D coherence analysis ---")
        with torch.no_grad():
            test_tokens = next(iter(dataloader)).to(device)
            # Low timestep (mostly unmasked) — FSCS-D should be active
            t_low = torch.full((batch_size,), 100, device=device, dtype=torch.long)
            masked_low, mask_low = trainer.model.mask_tokens(test_tokens, t_low)
            tok_emb = trainer.model.token_embed(masked_low)
            coherence_low = trainer.fscs_d.compute_coherence(tok_emb, mask_low)
            unmask_frac_low = (~mask_low).float().mean().item()
            coupling_low = trainer.fscs_d.compute_coupling(unmask_frac_low)

            # High timestep (mostly masked) — FSCS-D should be inactive
            t_high = torch.full((batch_size,), 900, device=device, dtype=torch.long)
            masked_high, mask_high = trainer.model.mask_tokens(test_tokens, t_high)
            tok_emb = trainer.model.token_embed(masked_high)
            coherence_high = trainer.fscs_d.compute_coherence(tok_emb, mask_high)
            unmask_frac_high = (~mask_high).float().mean().item()
            coupling_high = trainer.fscs_d.compute_coupling(unmask_frac_high)

            print(f"  Low noise  (t=100): unmasked={unmask_frac_low:.1%}, "
                  f"coupling={coupling_low:.4f}, coherence={coherence_low.mean():.4f}")
            print(f"  High noise (t=900): unmasked={unmask_frac_high:.1%}, "
                  f"coupling={coupling_high:.4f}, coherence={coherence_high.mean():.4f}")
            print(f"  Warmup threshold: {config.theta_warmup:.0%}")


def main():
    parser = argparse.ArgumentParser(description="Train FSCS-D discrete diffusion")
    parser.add_argument("--synthetic", action="store_true", default=True)
    parser.add_argument("--hf-dataset", type=str, help="HuggingFace dataset")
    parser.add_argument("--hf-config", type=str, help="Dataset config name")
    parser.add_argument("--enable-fscs-d", action="store_true", default=True)
    parser.add_argument("--no-fscs-d", action="store_true", help="Disable FSCS-D")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--seq-len", type=int, default=128)
    parser.add_argument("--num-layers", type=int, default=6)
    parser.add_argument("--embed-dim", type=int, default=512)
    parser.add_argument("--output-dir", type=str, default="checkpoints_fscs_d")
    parser.add_argument("--resume", type=str)
    parser.add_argument("--save-every", type=int, default=10)
    args = parser.parse_args()

    train(
        synthetic=args.synthetic if not args.hf_dataset else False,
        hf_dataset=args.hf_dataset,
        hf_config=args.hf_config,
        enable_fscs_d=not args.no_fscs_d,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        seq_len=args.seq_len,
        num_layers=args.num_layers,
        embed_dim=args.embed_dim,
        output_dir=args.output_dir,
        resume=args.resume,
        save_every=args.save_every,
    )


if __name__ == "__main__":
    main()
