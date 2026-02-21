#!/usr/bin/env python3
"""
BPC Trainer
============

Training loop that integrates CE + BPC losses.
Supports all ablation conditions (A0-A7).

Run modes:
  A0: Baseline CE only
  A1: Baseline CE + scale-matched logits
  A2: CE + BPC (full)
  A3: CE + MLP head baseline (param-matched)
  A4: CE + projection-only (PCA applied, no BPC losses)
  A5: CE + BPC with random U_r
  A6: CE + BPC with lambda_cf=0
  A7: CE + BPC with lambda_rollout=0
"""

from __future__ import annotations

import json
import logging
import math
import os
import random
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader, Dataset, IterableDataset

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bpc.losses import BPCConfig, BPCLoss
from bpc.counterfactual import CFConfig, CounterfactualPerturber

logger = logging.getLogger(__name__)


# ============================================================
# Config
# ============================================================

@dataclass
class TrainConfig:
    """Full training configuration."""

    # Model
    model_type: str = "standard"
    vocab_size: int = 50257
    embed_dim: int = 768
    num_layers: int = 12
    num_heads: int = 12
    max_seq_len: int = 512
    dropout: float = 0.1
    tie_embeddings: bool = True

    # Training
    max_steps: int = 50000
    batch_size: int = 8
    learning_rate: float = 3e-4
    weight_decay: float = 0.01
    grad_clip: float = 1.0
    warmup_steps: int = 1000
    seed: int = 42

    # Data
    dataset: str = "wikitext103"
    seq_len: int = 256

    # BPC
    bpc: BPCConfig = field(default_factory=BPCConfig)
    cf: CFConfig = field(default_factory=CFConfig)

    # Ablation mode
    ablation: str = "A2"  # A0..A7

    # Subspace
    subspace_path: Optional[str] = None  # path to pre-computed U_r.pt
    compute_subspace_online: bool = True
    subspace_warmup_tokens: int = 500_000

    # MLP head baseline (A3)
    mlp_head_hidden: int = 1024

    # Scale matching (A1)
    scale_match_target_std: Optional[float] = None  # set during training

    # Logging
    log_interval: int = 100
    eval_interval: int = 1000
    save_interval: int = 5000
    output_dir: str = "runs/bpc"

    # Device
    device: str = "auto"

    def model_config(self) -> dict:
        return {
            "vocab_size": self.vocab_size,
            "embed_dim": self.embed_dim,
            "num_layers": self.num_layers,
            "num_heads": self.num_heads,
            "max_seq_len": self.max_seq_len,
            "dropout": self.dropout,
            "tie_embeddings": self.tie_embeddings,
        }


# ============================================================
# Data
# ============================================================

class SyntheticTextDataset(Dataset):
    """Synthetic dataset for smoke testing when HF datasets unavailable."""

    def __init__(self, vocab_size: int, seq_len: int, size: int = 10000):
        self.vocab_size = vocab_size
        self.seq_len = seq_len
        self.size = size
        # Generate structured data: sequences with repeating patterns
        self.data = torch.randint(1, vocab_size, (size, seq_len + 1))

    def __len__(self):
        return self.size

    def __getitem__(self, idx):
        seq = self.data[idx]
        return seq[:-1], seq[1:]


def create_dataloader(
    dataset_name: str = "wikitext103",
    batch_size: int = 8,
    seq_len: int = 256,
    split: str = "train",
    vocab_size: int = 50257,
) -> DataLoader:
    """Create a DataLoader for training or validation."""
    try:
        from datasets import load_dataset
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained("gpt2")
        tokenizer.pad_token = tokenizer.eos_token

        if dataset_name == "wikitext103":
            ds_name = "wikitext"
            ds_config = "wikitext-103-raw-v1"
        elif dataset_name == "wikitext2":
            ds_name = "wikitext"
            ds_config = "wikitext-2-raw-v1"
        else:
            ds_name = dataset_name
            ds_config = None

        split_map = {"train": "train", "validation": "validation", "test": "test"}
        ds_split = split_map.get(split, split)

        raw_dataset = load_dataset(ds_name, ds_config, split=ds_split, trust_remote_code=True)

        class TokenizedDataset(Dataset):
            def __init__(self, texts, tokenizer, seq_len):
                self.tokenizer = tokenizer
                self.seq_len = seq_len
                # Concatenate all text and tokenize
                all_text = "\n".join(
                    [t for t in texts["text"] if t.strip()]
                )
                tokens = tokenizer.encode(all_text)
                # Chunk into seq_len+1 sequences
                n_seqs = len(tokens) // (seq_len + 1)
                tokens = tokens[: n_seqs * (seq_len + 1)]
                self.data = torch.tensor(tokens, dtype=torch.long).reshape(
                    n_seqs, seq_len + 1
                )

            def __len__(self):
                return len(self.data)

            def __getitem__(self, idx):
                seq = self.data[idx]
                return seq[:-1], seq[1:]

        dataset = TokenizedDataset(raw_dataset, tokenizer, seq_len)
        return DataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=(split == "train"),
            num_workers=0,
            drop_last=True,
        )

    except (ImportError, Exception) as e:
        logger.warning(f"HF datasets unavailable ({e}), using synthetic data")
        dataset = SyntheticTextDataset(vocab_size, seq_len)
        return DataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=(split == "train"),
            num_workers=0,
            drop_last=True,
        )


# ============================================================
# MLP Head Baseline (A3)
# ============================================================

class MLPLMHead(nn.Module):
    """2-layer MLP LM head to replace linear lm_head for param-matched baseline."""

    def __init__(self, embed_dim: int, vocab_size: int, hidden_dim: int = 1024):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(embed_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, vocab_size, bias=False),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)

    @property
    def extra_params(self) -> int:
        return sum(p.numel() for p in self.parameters())


# ============================================================
# Diagnostics Logger
# ============================================================

class DiagnosticsLogger:
    """Log training metrics to JSON lines file."""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.output_dir / "metrics.jsonl"
        self.history: List[Dict] = []

    def log(self, step: int, metrics: Dict[str, Any]):
        entry = {"step": step, **metrics}
        self.history.append(entry)
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def save_summary(self):
        summary_path = self.output_dir / "summary.json"
        with open(summary_path, "w") as f:
            json.dump(
                {
                    "total_steps": len(self.history),
                    "final_metrics": self.history[-1] if self.history else {},
                },
                f,
                indent=2,
                default=str,
            )


# ============================================================
# Trainer
# ============================================================

class BPCTrainer:
    """
    BPC-augmented training loop.

    Supports all ablation conditions A0-A7.
    """

    def __init__(self, config: TrainConfig):
        self.config = config

        # Device
        if config.device == "auto":
            self.device = torch.device(
                "cuda" if torch.cuda.is_available() else "cpu"
            )
        else:
            self.device = torch.device(config.device)

        # Seed
        torch.manual_seed(config.seed)
        np.random.seed(config.seed)
        random.seed(config.seed)

        # Model
        self.model = self._create_model()
        self.model.to(self.device)

        # MLP head for A3
        self.mlp_head = None
        if config.ablation == "A3":
            self.mlp_head = MLPLMHead(
                config.embed_dim, config.vocab_size, config.mlp_head_hidden
            ).to(self.device)

        # BPC loss
        self.bpc_loss = None
        if config.ablation in ("A2", "A4", "A5", "A6", "A7"):
            self.bpc_loss = BPCLoss(
                config.bpc, config.embed_dim, config.max_steps
            ).to(self.device)

            # Override lambdas for specific ablations
            if config.ablation == "A4":
                # Projection-only: no BPC losses
                config.bpc.lambda_rollout = 0.0
                config.bpc.lambda_cf = 0.0
                config.bpc.lambda_varfloor = 0.0
            elif config.ablation == "A6":
                config.bpc.lambda_cf = 0.0
            elif config.ablation == "A7":
                config.bpc.lambda_rollout = 0.0

        # Counterfactual
        self.cf_perturber = None
        if config.ablation in ("A2", "A5", "A7"):
            self.cf_perturber = CounterfactualPerturber(
                config.cf, config.vocab_size
            )

        # Scale matching state (A1)
        self._logit_std_running = None
        self._scale_factor = 1.0

        # Optimizer
        params = list(self.model.parameters())
        if self.mlp_head is not None:
            params += list(self.mlp_head.parameters())
        if self.bpc_loss is not None:
            params += list(self.bpc_loss.parameters())

        self.optimizer = AdamW(
            params,
            lr=config.learning_rate,
            weight_decay=config.weight_decay,
        )
        self.scheduler = CosineAnnealingLR(
            self.optimizer,
            T_max=config.max_steps,
            eta_min=config.learning_rate * 0.1,
        )

        # Data
        self.train_loader = create_dataloader(
            config.dataset, config.batch_size, config.seq_len, "train", config.vocab_size
        )
        self.val_loader = create_dataloader(
            config.dataset, config.batch_size, config.seq_len, "validation", config.vocab_size
        )

        # Logging
        self.logger = DiagnosticsLogger(config.output_dir)

        # Subspace
        self._subspace_computed = False
        self._tokens_seen = 0

        # PCA online computation
        if config.compute_subspace_online and self.bpc_loss is not None:
            from tools.compute_pca_subspace import IncrementalPCA
            self._online_pca = IncrementalPCA(
                config.bpc.subspace_rank,
                device=torch.device("cpu"),
            )
        else:
            self._online_pca = None

    def _create_model(self) -> nn.Module:
        from symbolu.phase_transformer import StandardTransformer
        return StandardTransformer(**self.config.model_config())

    def _maybe_load_subspace(self):
        """Load or compute PCA subspace."""
        if self.bpc_loss is None:
            return

        if self.config.subspace_path and Path(self.config.subspace_path).exists():
            data = torch.load(
                self.config.subspace_path,
                map_location=self.device,
                weights_only=True,
            )
            if self.config.ablation == "A5":
                # Random subspace control
                self.bpc_loss.projector.load_random_basis()
                logger.info("Loaded RANDOM subspace (A5 control)")
            else:
                self.bpc_loss.projector.load_basis(
                    data["U_r"].to(self.device),
                    data.get("mean", torch.zeros(self.config.embed_dim)).to(self.device),
                )
                logger.info(
                    f"Loaded PCA subspace from {self.config.subspace_path}, "
                    f"energy_ratio={data.get('energy_ratio', '?')}"
                )
            self._subspace_computed = True

    def _update_online_pca(self, hidden: torch.Tensor):
        """Update incremental PCA with hidden states from this batch."""
        if self._online_pca is None or self._subspace_computed:
            return

        B, T, D = hidden.shape
        flat = hidden.detach().cpu().reshape(-1, D)
        self._online_pca.partial_fit(flat)
        self._tokens_seen += B * T

        if self._tokens_seen >= self.config.subspace_warmup_tokens:
            results = self._online_pca.compute()
            U_r = results["U_r"].to(self.device)
            h_mean = results["mean"].to(self.device)

            if self.config.ablation == "A5":
                self.bpc_loss.projector.load_random_basis()
                logger.info("Computed online PCA -> using RANDOM basis (A5)")
            else:
                self.bpc_loss.projector.load_basis(U_r, h_mean)
                logger.info(
                    f"Computed online PCA subspace, "
                    f"energy_ratio={results['energy_ratio']:.4f}, "
                    f"tokens={self._tokens_seen:,}"
                )

            # Save for later use
            save_dir = Path(self.config.output_dir) / "subspace"
            save_dir.mkdir(parents=True, exist_ok=True)
            torch.save(
                {
                    "U_r": results["U_r"],
                    "mean": results["mean"],
                    "eigenvalues": results["eigenvalues"],
                    "explained_variance_ratio": results["explained_variance_ratio"],
                    "energy_ratio": results["energy_ratio"],
                    "layer": self.config.bpc.target_layer,
                    "rank": self.config.bpc.subspace_rank,
                },
                save_dir / "U_r.pt",
            )

            self._subspace_computed = True
            self._online_pca = None  # Free memory

    def _compute_logit_stats(self, logits: torch.Tensor) -> Dict[str, float]:
        """Compute logit distribution statistics."""
        with torch.no_grad():
            logit_std = logits.std().item()
            logit_mean = logits.mean().item()
            probs = F.softmax(logits, dim=-1)
            entropy = -(probs * torch.log(probs + 1e-9)).sum(dim=-1).mean().item()
            max_entropy = math.log(logits.shape[-1])
            normalized_entropy = entropy / max_entropy

        return {
            "logit_std": logit_std,
            "logit_mean": logit_mean,
            "entropy": entropy,
            "normalized_entropy": normalized_entropy,
        }

    def train_step(
        self, input_ids: torch.Tensor, targets: torch.Tensor, step: int
    ) -> Dict[str, float]:
        """Single training step."""
        self.model.train()
        config = self.config

        # Forward pass with hidden state extraction
        extract_layers = (
            [config.bpc.target_layer]
            if self.bpc_loss is not None
            else None
        )
        outputs = self.model(
            input_ids,
            extract_layers=extract_layers,
        )
        logits = outputs["logits"]

        # Scale matching for A1
        if config.ablation == "A1" and config.scale_match_target_std is not None:
            with torch.no_grad():
                current_std = logits.std().item()
                if current_std > 0:
                    self._scale_factor = config.scale_match_target_std / current_std
            logits = logits * self._scale_factor

        # MLP head for A3
        if self.mlp_head is not None and "last_hidden_state" not in outputs:
            # Re-run to get last hidden state
            outputs_lh = self.model(input_ids, return_last_hidden=True)
            last_hidden = outputs_lh["last_hidden_state"]
            logits = self.mlp_head(last_hidden)

        # CE loss
        B, T, V = logits.shape
        ce_loss = F.cross_entropy(
            logits.reshape(-1, V),
            targets.reshape(-1),
            ignore_index=-100,
        )

        metrics = {"ce_loss": ce_loss.item(), "ppl": math.exp(min(ce_loss.item(), 20))}
        metrics.update(self._compute_logit_stats(logits))

        # BPC loss
        total_loss = ce_loss
        if (
            self.bpc_loss is not None
            and self._subspace_computed
            and self.bpc_loss.projector.is_loaded
        ):
            teacher_hidden = outputs["hidden_states"][0]  # [B, T, D]

            # Counterfactual
            cf_hidden = None
            cf_positions = None
            if self.cf_perturber is not None:
                cf_ids, cf_positions, cf_stats = self.cf_perturber.perturb(input_ids)
                cf_outputs = self.model(
                    cf_ids, extract_layers=[config.bpc.target_layer]
                )
                cf_hidden = cf_outputs["hidden_states"][0]
                metrics.update(cf_stats)

            total_loss, bpc_metrics = self.bpc_loss(
                self.model,
                input_ids,
                targets,
                ce_loss,
                teacher_hidden,
                cf_hidden=cf_hidden,
                cf_positions=cf_positions,
                step=step,
            )
            metrics.update(bpc_metrics)

            # z variance per dimension
            with torch.no_grad():
                z = self.bpc_loss._get_z(teacher_hidden.reshape(-1, config.embed_dim))
                z_per_dim_std = z.std(dim=0).cpu().tolist()
                metrics["z_std_per_dim"] = z_per_dim_std
                metrics["z_std_mean"] = np.mean(z_per_dim_std)
                metrics["z_std_min"] = np.min(z_per_dim_std)
        elif self.bpc_loss is not None and not self._subspace_computed:
            # Still collecting for PCA
            if extract_layers and "hidden_states" in outputs:
                self._update_online_pca(outputs["hidden_states"][0])

        metrics["total_loss"] = total_loss.item()

        # Backward
        self.optimizer.zero_grad()
        total_loss.backward()

        # Gradient clipping
        grad_norm = torch.nn.utils.clip_grad_norm_(
            self.model.parameters(), config.grad_clip
        )
        metrics["grad_norm"] = grad_norm.item() if isinstance(grad_norm, torch.Tensor) else grad_norm

        self.optimizer.step()
        self.scheduler.step()
        metrics["lr"] = self.scheduler.get_last_lr()[0]

        return metrics

    @torch.no_grad()
    def evaluate(self) -> Dict[str, float]:
        """Run validation."""
        self.model.eval()
        config = self.config

        total_loss = 0.0
        total_tokens = 0
        logit_stds = []
        entropies = []

        for batch in self.val_loader:
            input_ids, targets = batch
            input_ids = input_ids.to(self.device)
            targets = targets.to(self.device)

            outputs = self.model(input_ids)
            logits = outputs["logits"]

            if config.ablation == "A1" and self._scale_factor != 1.0:
                logits = logits * self._scale_factor

            B, T, V = logits.shape
            loss = F.cross_entropy(
                logits.reshape(-1, V),
                targets.reshape(-1),
                ignore_index=-100,
            )

            total_loss += loss.item() * B * T
            total_tokens += B * T

            stats = self._compute_logit_stats(logits)
            logit_stds.append(stats["logit_std"])
            entropies.append(stats["entropy"])

        avg_loss = total_loss / max(1, total_tokens)
        return {
            "val_loss": avg_loss,
            "val_ppl": math.exp(min(avg_loss, 20)),
            "val_logit_std": np.mean(logit_stds),
            "val_entropy": np.mean(entropies),
        }

    def train(self):
        """Main training loop."""
        config = self.config

        logger.info(f"=== BPC Training: ablation={config.ablation} ===")
        logger.info(f"  Model params: {sum(p.numel() for p in self.model.parameters()):,}")
        logger.info(f"  Device: {self.device}")
        logger.info(f"  Output: {config.output_dir}")

        # Try to load pre-computed subspace
        self._maybe_load_subspace()

        # Save config
        config_path = Path(config.output_dir) / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(asdict(config), f, indent=2, default=str)

        step = 0
        epoch = 0
        best_val_loss = float("inf")
        train_iter = iter(self.train_loader)

        while step < config.max_steps:
            try:
                batch = next(train_iter)
            except StopIteration:
                epoch += 1
                train_iter = iter(self.train_loader)
                batch = next(train_iter)

            input_ids, targets = batch
            input_ids = input_ids.to(self.device)
            targets = targets.to(self.device)

            metrics = self.train_step(input_ids, targets, step)
            metrics["epoch"] = epoch

            # Log
            if step % config.log_interval == 0:
                log_msg = (
                    f"[{config.ablation}] step={step} "
                    f"loss={metrics['total_loss']:.4f} "
                    f"ce={metrics['ce_loss']:.4f} "
                    f"ppl={metrics['ppl']:.1f} "
                    f"logit_std={metrics['logit_std']:.4f} "
                    f"entropy={metrics['entropy']:.2f}"
                )
                if "rollout_smooth" in metrics:
                    log_msg += f" roll_sm={metrics['rollout_smooth']:.4f}"
                if "cf_loss" in metrics and metrics["cf_loss"] > 0:
                    log_msg += f" cf={metrics['cf_loss']:.4f}"
                if "z_std_mean" in metrics:
                    log_msg += f" z_std={metrics['z_std_mean']:.4f}"
                logger.info(log_msg)
                self.logger.log(step, metrics)

            # Eval
            if step % config.eval_interval == 0 and step > 0:
                val_metrics = self.evaluate()
                metrics.update(val_metrics)
                self.logger.log(step, val_metrics)
                logger.info(
                    f"  [VAL] loss={val_metrics['val_loss']:.4f} "
                    f"ppl={val_metrics['val_ppl']:.1f} "
                    f"logit_std={val_metrics['val_logit_std']:.4f}"
                )

                if val_metrics["val_loss"] < best_val_loss:
                    best_val_loss = val_metrics["val_loss"]
                    self._save_checkpoint(step, "best")

            # Save
            if step % config.save_interval == 0 and step > 0:
                self._save_checkpoint(step, f"step_{step}")

            step += 1

        # Final eval and save
        val_metrics = self.evaluate()
        self.logger.log(step, val_metrics)
        self._save_checkpoint(step, "final")
        self.logger.save_summary()

        logger.info(f"Training complete. Best val loss: {best_val_loss:.4f}")
        return val_metrics

    def _save_checkpoint(self, step: int, name: str):
        save_dir = Path(self.config.output_dir) / "checkpoints"
        save_dir.mkdir(parents=True, exist_ok=True)
        path = save_dir / f"{name}.pt"
        state = {
            "step": step,
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "model_config": self.config.model_config(),
            "ablation": self.config.ablation,
        }
        if self.bpc_loss is not None:
            state["bpc_state_dict"] = self.bpc_loss.state_dict()
        if self.mlp_head is not None:
            state["mlp_head_state_dict"] = self.mlp_head.state_dict()
        torch.save(state, path)


# ============================================================
# Entry Point
# ============================================================

def run_training(config: TrainConfig) -> Dict[str, float]:
    """Run a single training experiment."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    trainer = BPCTrainer(config)
    return trainer.train()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="BPC Training")
    parser.add_argument("--ablation", type=str, default="A2", choices=[f"A{i}" for i in range(8)])
    parser.add_argument("--max_steps", type=int, default=50000)
    parser.add_argument("--batch_size", type=int, default=8)
    parser.add_argument("--seq_len", type=int, default=256)
    parser.add_argument("--embed_dim", type=int, default=768)
    parser.add_argument("--num_layers", type=int, default=12)
    parser.add_argument("--num_heads", type=int, default=12)
    parser.add_argument("--learning_rate", type=float, default=3e-4)
    parser.add_argument("--dataset", type=str, default="wikitext103")
    parser.add_argument("--target_layer", type=int, default=6)
    parser.add_argument("--subspace_rank", type=int, default=32)
    parser.add_argument("--rollout_steps", type=int, default=4)
    parser.add_argument("--lambda_rollout", type=float, default=0.1)
    parser.add_argument("--lambda_cf", type=float, default=0.05)
    parser.add_argument("--output_dir", type=str, default="runs/bpc")
    parser.add_argument("--subspace_path", type=str, default=None)
    parser.add_argument("--device", type=str, default="auto")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    bpc_config = BPCConfig(
        target_layer=args.target_layer,
        subspace_rank=args.subspace_rank,
        rollout_steps=args.rollout_steps,
        lambda_rollout=args.lambda_rollout,
        lambda_cf=args.lambda_cf,
    )

    config = TrainConfig(
        ablation=args.ablation,
        max_steps=args.max_steps,
        batch_size=args.batch_size,
        seq_len=args.seq_len,
        embed_dim=args.embed_dim,
        num_layers=args.num_layers,
        num_heads=args.num_heads,
        learning_rate=args.learning_rate,
        dataset=args.dataset,
        bpc=bpc_config,
        output_dir=f"{args.output_dir}/{args.ablation}",
        subspace_path=args.subspace_path,
        device=args.device,
        seed=args.seed,
    )

    run_training(config)


if __name__ == "__main__":
    main()
