#!/usr/bin/env python3
"""
Spanda-Softmax Hybrid v0.4 Benchmark

Runs the full experiment plan:
    1. PhaseTransformer baseline
    2. PhaseTransformer + Spanda
    3. StandardTransformer baseline
    4. StandardTransformer + Spanda
    5. Gamma ablation: PhaseTransformer + Spanda, gamma=0.99
    6. Gamma ablation: PhaseTransformer + Spanda, gamma=0.995
    7. Gamma ablation: PhaseTransformer + Spanda, gamma=0.999

Logs all specified metrics. Generates plots and comparative table.

Usage:
    python Spanda/run_benchmark.py --dataset wikitext2 --max_steps 5000
    python Spanda/run_benchmark.py --dataset wikitext2 --max_steps 5000 --model_size tiny
    python Spanda/run_benchmark.py --dataset wikitext2 --max_steps 5000 --configs phase_spanda
"""

import os
import sys
import math
import time
import json
import argparse
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR

# Ensure project root on path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "Spanda"))

from symbolu.phase_transformer import PhaseTransformer, StandardTransformer, TransformerConfig
from spanda.state import SpandaState
from spanda.emission import AnchorEmission
from spanda.regularizers import SpandaRegularizers
from spanda.wrapper import SpandaHybridWrapper
from spanda.metrics import SpandaMetrics
from spanda.plotting import (
    generate_all_plots,
    plot_anchor_cosine_histogram,
    plot_psi_trajectory,
    generate_results_table,
)

# Optional imports
try:
    from datasets import load_dataset as hf_load_dataset
    from transformers import AutoTokenizer
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

try:
    import numpy as np
    NP_AVAILABLE = True
except ImportError:
    NP_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("spanda_benchmark")


# =============================================================================
# CONFIGURATION
# =============================================================================

MODEL_PRESETS = {
    "tiny": {"embed_dim": 256, "num_layers": 4, "num_heads": 4, "ff_dim": 1024},
    "small": {"embed_dim": 512, "num_layers": 8, "num_heads": 8, "ff_dim": 2048},
    "medium": {"embed_dim": 768, "num_layers": 12, "num_heads": 12, "ff_dim": 3072},
}


@dataclass
class BenchmarkConfig:
    """Configuration for Spanda benchmark experiments."""

    # Model
    model_size: str = "tiny"
    vocab_size: int = 50257
    max_seq_len: int = 256

    # Spanda
    psi_dim: int = 256
    decay_gamma: float = 0.99
    reg_alpha: float = 1e-4
    reg_beta: float = 1e-4

    # Training
    batch_size: int = 16
    learning_rate: float = 3e-4
    weight_decay: float = 0.01
    max_steps: int = 5000
    warmup_steps: int = 500
    eval_interval: int = 250
    log_interval: int = 50
    gradient_clip: float = 1.0

    # Dataset
    dataset: str = "wikitext2"
    tokenizer: str = "tiktoken"

    # Output
    output_dir: str = "Spanda/results"
    seed: int = 42

    # Anchor diagnostics interval (every N eval steps)
    anchor_diag_interval: int = 2


# =============================================================================
# DATASET
# =============================================================================

class TextDataset(Dataset):
    """Simple text dataset for language modeling."""

    def __init__(self, tokens: torch.Tensor, seq_len: int):
        self.tokens = tokens
        self.seq_len = seq_len
        self.num_samples = max(1, len(tokens) // seq_len - 1)

    def __len__(self):
        return self.num_samples

    def __getitem__(self, idx):
        start = idx * self.seq_len
        end = start + self.seq_len + 1
        chunk = self.tokens[start:end]
        return chunk[:-1], chunk[1:]


def load_tokenizer(config: BenchmarkConfig):
    """Load tokenizer."""
    if config.tokenizer == "tiktoken" and TIKTOKEN_AVAILABLE:
        return tiktoken.get_encoding("gpt2")
    elif HF_AVAILABLE:
        tokenizer = AutoTokenizer.from_pretrained("gpt2")
        tokenizer.model_max_length = int(1e12)
        return tokenizer
    else:
        raise ImportError("No tokenizer available. Install tiktoken or transformers.")


def tokenize_text(text: str, tokenizer) -> torch.Tensor:
    """Tokenize text."""
    if hasattr(tokenizer, "encode_ordinary"):
        tokens = tokenizer.encode(text, allowed_special={"<|endoftext|>"})
    else:
        tokens = tokenizer.encode(text)
    return torch.tensor(tokens, dtype=torch.long)


def load_data(config: BenchmarkConfig, split: str = "train") -> torch.Tensor:
    """Load and tokenize dataset."""
    if not HF_AVAILABLE:
        raise ImportError("datasets library required: pip install datasets transformers")

    logger.info(f"Loading {config.dataset} ({split})...")
    tokenizer = load_tokenizer(config)

    if config.dataset == "wikitext2":
        dataset = hf_load_dataset("wikitext", "wikitext-2-v1", split=split)
        text = "\n".join(dataset["text"])
    elif config.dataset == "wikitext103":
        dataset = hf_load_dataset("wikitext", "wikitext-103-v1", split=split)
        text = "\n".join(dataset["text"])
    else:
        raise ValueError(f"Unknown dataset: {config.dataset}")

    tokens = tokenize_text(text, tokenizer)
    logger.info(f"  {split}: {len(tokens):,} tokens")
    return tokens


def create_dataloaders(config: BenchmarkConfig) -> Tuple[DataLoader, DataLoader]:
    """Create train and validation dataloaders."""
    train_tokens = load_data(config, "train")
    val_tokens = load_data(config, "validation")

    train_ds = TextDataset(train_tokens, config.max_seq_len)
    val_ds = TextDataset(val_tokens, config.max_seq_len)

    train_loader = DataLoader(
        train_ds, batch_size=config.batch_size, shuffle=True, drop_last=True
    )
    val_loader = DataLoader(
        val_ds, batch_size=config.batch_size, shuffle=False, drop_last=True
    )

    return train_loader, val_loader


# =============================================================================
# MODEL CREATION
# =============================================================================

def create_model(
    backbone_type: str,
    config: BenchmarkConfig,
    use_spanda: bool = False,
    decay_gamma: float = 0.99,
    device: torch.device = torch.device("cpu"),
) -> nn.Module:
    """
    Create a model (baseline or Spanda hybrid).

    Args:
        backbone_type: "phase" or "standard".
        config: Benchmark configuration.
        use_spanda: Whether to wrap with SpandaHybridWrapper.
        decay_gamma: Gamma for Spanda (only used if use_spanda=True).
        device: Device to place model on.

    Returns:
        Model instance.
    """
    preset = MODEL_PRESETS[config.model_size]

    model_kwargs = dict(
        vocab_size=config.vocab_size,
        embed_dim=preset["embed_dim"],
        num_layers=preset["num_layers"],
        num_heads=preset["num_heads"],
        ff_dim=preset["ff_dim"],
        max_seq_len=config.max_seq_len,
        dropout=0.1,
        tie_embeddings=not use_spanda,  # Disable tying when using Spanda (Option B projection)
    )

    if backbone_type == "phase":
        backbone = PhaseTransformer(**model_kwargs)
    elif backbone_type == "standard":
        backbone = StandardTransformer(**model_kwargs)
    else:
        raise ValueError(f"Unknown backbone: {backbone_type}")

    if use_spanda:
        model = SpandaHybridWrapper(
            backbone=backbone,
            psi_dim=config.psi_dim,
            decay_gamma=decay_gamma,
            alpha=config.reg_alpha,
            beta=config.reg_beta,
        )
    else:
        model = backbone

    model = model.to(device)
    param_count = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info(f"  Model: {backbone_type} {'+ Spanda' if use_spanda else 'baseline'}")
    logger.info(f"  Parameters: {param_count:,}")
    if use_spanda:
        logger.info(f"  Psi dim: {config.psi_dim}, gamma: {decay_gamma}")

    return model


# =============================================================================
# TRAINING LOOP
# =============================================================================

def train_step(
    model: nn.Module,
    batch: Tuple[torch.Tensor, torch.Tensor],
    optimizer: torch.optim.Optimizer,
    device: torch.device,
    grad_clip: float = 1.0,
    is_spanda: bool = False,
) -> Dict[str, float]:
    """Single training step."""
    input_ids, targets = batch
    input_ids = input_ids.to(device)
    targets = targets.to(device)

    model.train()
    optimizer.zero_grad()

    if is_spanda:
        result = model(input_ids, return_spanda_state=True)
        logits = result["logits"]
        reg_losses = result["reg_losses"]
    else:
        result = model(input_ids)
        logits = result["logits"]
        reg_losses = None

    # Cross-entropy loss
    loss = F.cross_entropy(
        logits.reshape(-1, logits.size(-1)), targets.reshape(-1)
    )

    # Add regularization if Spanda
    total_loss = loss
    if reg_losses is not None:
        total_loss = total_loss + reg_losses["total_reg"]

    total_loss.backward()

    # Gradient clipping
    if grad_clip > 0:
        torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)

    optimizer.step()

    metrics = {
        "loss": loss.item(),
        "perplexity": math.exp(min(loss.item(), 20)),
    }

    if reg_losses is not None:
        metrics["l_step"] = reg_losses["l_step"].item()
        metrics["l_smooth"] = reg_losses["l_smooth"].item()

    return metrics


@torch.no_grad()
def evaluate(
    model: nn.Module,
    val_loader: DataLoader,
    device: torch.device,
    is_spanda: bool = False,
    spanda_metrics: Optional[SpandaMetrics] = None,
    compute_anchor_diag: bool = False,
) -> Dict[str, float]:
    """Evaluate model on validation set."""
    model.eval()
    total_loss = 0.0
    total_tokens = 0
    all_spanda_stats = []

    for batch_idx, (input_ids, targets) in enumerate(val_loader):
        input_ids = input_ids.to(device)
        targets = targets.to(device)

        if is_spanda:
            result = model(input_ids, return_spanda_state=True)
            logits = result["logits"]

            # Compute Spanda metrics
            if spanda_metrics is not None:
                anchors = None
                if compute_anchor_diag:
                    anchors = model.get_anchors_normalized().detach()

                stats = spanda_metrics.compute(
                    psi=result["psi"],
                    delta=result["delta"],
                    h=result["last_hidden_state"],
                    logits=logits,
                    tau=model.temperature,
                    anchors=anchors,
                    norm_clamp_c=model.spanda_state.norm_clamp_c,
                )
                all_spanda_stats.append(stats)
        else:
            result = model(input_ids)
            logits = result["logits"]

        loss = F.cross_entropy(
            logits.reshape(-1, logits.size(-1)), targets.reshape(-1), reduction="sum"
        )
        total_loss += loss.item()
        total_tokens += targets.numel()

        # Limit eval batches for speed
        if batch_idx >= 50:
            break

    avg_loss = total_loss / max(total_tokens, 1)
    ppl = math.exp(min(avg_loss, 20))

    eval_metrics = {
        "val_loss": avg_loss,
        "val_perplexity": ppl,
    }

    # Aggregate Spanda metrics
    if all_spanda_stats:
        agg = {}
        for key in all_spanda_stats[0]:
            values = [s[key] for s in all_spanda_stats if key in s]
            if values:
                agg[key] = sum(values) / len(values)
        eval_metrics.update(agg)

        # Run diagnostics
        if spanda_metrics is not None:
            warnings = spanda_metrics.check_diagnostics(agg)
            if warnings:
                for w in warnings:
                    logger.warning(w)

    # Compute active anchor coverage on last batch (if Spanda)
    if is_spanda and spanda_metrics is not None and compute_anchor_diag:
        try:
            result = model(input_ids, return_spanda_state=True)
            anchors = model.get_anchors_normalized().detach()
            coverage = spanda_metrics.compute_active_coverage(
                result["psi"], anchors, model.config.vocab_size
            )
            eval_metrics["active_anchor_coverage"] = coverage
        except Exception:
            pass

    return eval_metrics


def run_experiment(
    name: str,
    backbone_type: str,
    config: BenchmarkConfig,
    use_spanda: bool,
    decay_gamma: float,
    device: torch.device,
    train_loader: DataLoader,
    val_loader: DataLoader,
) -> Tuple[List[Dict], Dict[str, float]]:
    """
    Run a single experiment configuration.

    Returns:
        logs: List of per-step metric dicts.
        final_results: Final eval metrics.
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"EXPERIMENT: {name}")
    logger.info(f"{'='*60}")

    # Set seed
    torch.manual_seed(config.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(config.seed)

    # Create model
    model = create_model(
        backbone_type=backbone_type,
        config=config,
        use_spanda=use_spanda,
        decay_gamma=decay_gamma,
        device=device,
    )

    # Optimizer
    optimizer = AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
        betas=(0.9, 0.95),
    )

    # Scheduler (cosine with warmup)
    def lr_lambda(step):
        if step < config.warmup_steps:
            return step / max(1, config.warmup_steps)
        progress = (step - config.warmup_steps) / max(
            1, config.max_steps - config.warmup_steps
        )
        return 0.5 * (1 + math.cos(math.pi * progress))

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)

    # Metrics tracker
    spanda_metrics = SpandaMetrics() if use_spanda else None

    # Training loop
    logs = []
    step = 0
    eval_count = 0
    train_iter = iter(train_loader)

    while step < config.max_steps:
        try:
            batch = next(train_iter)
        except StopIteration:
            train_iter = iter(train_loader)
            batch = next(train_iter)

        step_metrics = train_step(
            model, batch, optimizer, device,
            grad_clip=config.gradient_clip,
            is_spanda=use_spanda,
        )
        scheduler.step()
        step += 1

        step_metrics["step"] = step
        step_metrics["lr"] = scheduler.get_last_lr()[0]

        # Log
        if step % config.log_interval == 0:
            log_msg = (
                f"  [{name}] step {step}/{config.max_steps} | "
                f"loss={step_metrics['loss']:.4f} | "
                f"ppl={step_metrics['perplexity']:.1f} | "
                f"lr={step_metrics['lr']:.2e}"
            )
            if use_spanda:
                log_msg += (
                    f" | l_step={step_metrics.get('l_step', 0):.2e}"
                    f" | l_smooth={step_metrics.get('l_smooth', 0):.2e}"
                )
            logger.info(log_msg)
            logs.append(step_metrics)

        # Evaluate
        if step % config.eval_interval == 0:
            eval_count += 1
            compute_anchor = use_spanda and (eval_count % config.anchor_diag_interval == 0)

            eval_metrics = evaluate(
                model, val_loader, device,
                is_spanda=use_spanda,
                spanda_metrics=spanda_metrics,
                compute_anchor_diag=compute_anchor,
            )
            eval_metrics["step"] = step

            eval_msg = (
                f"  [{name}] EVAL step {step} | "
                f"val_loss={eval_metrics['val_loss']:.4f} | "
                f"val_ppl={eval_metrics['val_perplexity']:.1f}"
            )
            if use_spanda:
                tau = eval_metrics.get("tau", "N/A")
                psi_norm = eval_metrics.get("mean_psi_norm", "N/A")
                psi_cont = eval_metrics.get("psi_continuity", "N/A")
                eval_msg += (
                    f" | tau={tau:.3f}" if isinstance(tau, float) else f" | tau={tau}"
                )
                eval_msg += (
                    f" | ||Psi||={psi_norm:.3f}" if isinstance(psi_norm, float) else ""
                )
                eval_msg += (
                    f" | cos(Psi)={psi_cont:.4f}" if isinstance(psi_cont, float) else ""
                )
            logger.info(eval_msg)

            # Merge eval metrics into logs
            logs.append(eval_metrics)

    # Final evaluation
    logger.info(f"  [{name}] Final evaluation...")
    final_eval = evaluate(
        model, val_loader, device,
        is_spanda=use_spanda,
        spanda_metrics=spanda_metrics,
        compute_anchor_diag=use_spanda,
    )
    final_eval["step"] = step
    logs.append(final_eval)

    # Generate Psi trajectory plot if Spanda
    if use_spanda:
        try:
            # Get one batch for trajectory visualization
            batch = next(iter(val_loader))
            input_ids = batch[0].to(device)
            with torch.no_grad():
                result = model(input_ids, return_spanda_state=True)
                psi = result["psi"]
                psi_norms = psi[0].norm(dim=-1).cpu().numpy()

                plot_dir = os.path.join(config.output_dir, "plots")
                plot_psi_trajectory(
                    psi_norms,
                    plot_dir,
                    config_name=name.replace(" ", "_"),
                    norm_clamp_c=model.spanda_state.norm_clamp_c,
                )

                # Anchor cosine histogram
                anchors = model.get_anchors_normalized().detach()
                V = anchors.size(0)
                num_pairs = min(1000, V * (V - 1) // 2)
                idx_i = torch.randint(0, V, (num_pairs,))
                idx_j = torch.randint(0, V, (num_pairs,))
                mask = idx_i != idx_j
                cos_vals = F.cosine_similarity(
                    anchors[idx_i[mask]], anchors[idx_j[mask]], dim=-1
                ).cpu().numpy()
                plot_anchor_cosine_histogram(
                    cos_vals, plot_dir, config_name=name.replace(" ", "_")
                )
        except Exception as e:
            logger.warning(f"Failed to generate plots: {e}")

    final_results = {
        "val_perplexity": final_eval["val_perplexity"],
        "val_loss": final_eval["val_loss"],
    }
    if use_spanda:
        for k in ["tau", "mean_psi_norm", "max_psi_norm", "psi_continuity",
                   "backbone_continuity", "mean_delta_norm",
                   "anchor_pairwise_cosine_mean", "active_anchor_coverage"]:
            if k in final_eval:
                final_results[k] = final_eval[k]

    # Cleanup
    del model, optimizer
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return logs, final_results


# =============================================================================
# EXPERIMENT CONFIGURATIONS
# =============================================================================

EXPERIMENTS = {
    "phase_baseline": {
        "backbone": "phase",
        "use_spanda": False,
        "gamma": 0.99,
        "description": "PhaseTransformer baseline (no Spanda)",
    },
    "phase_spanda": {
        "backbone": "phase",
        "use_spanda": True,
        "gamma": 0.99,
        "description": "PhaseTransformer + Spanda (gamma=0.99)",
    },
    "standard_baseline": {
        "backbone": "standard",
        "use_spanda": False,
        "gamma": 0.99,
        "description": "StandardTransformer baseline (no Spanda)",
    },
    "standard_spanda": {
        "backbone": "standard",
        "use_spanda": True,
        "gamma": 0.99,
        "description": "StandardTransformer + Spanda (gamma=0.99)",
    },
    "gamma_099": {
        "backbone": "phase",
        "use_spanda": True,
        "gamma": 0.99,
        "description": "PhaseTransformer + Spanda, gamma=0.99 (half-life ~69 tokens)",
    },
    "gamma_0995": {
        "backbone": "phase",
        "use_spanda": True,
        "gamma": 0.995,
        "description": "PhaseTransformer + Spanda, gamma=0.995 (half-life ~138 tokens)",
    },
    "gamma_0999": {
        "backbone": "phase",
        "use_spanda": True,
        "gamma": 0.999,
        "description": "PhaseTransformer + Spanda, gamma=0.999 (half-life ~693 tokens)",
    },
}


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Spanda v0.4 Benchmark")
    parser.add_argument("--model_size", default="tiny", choices=["tiny", "small", "medium"])
    parser.add_argument("--dataset", default="wikitext2", choices=["wikitext2", "wikitext103"])
    parser.add_argument("--max_steps", type=int, default=5000)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--max_seq_len", type=int, default=256)
    parser.add_argument("--psi_dim", type=int, default=256)
    parser.add_argument("--learning_rate", type=float, default=3e-4)
    parser.add_argument("--eval_interval", type=int, default=250)
    parser.add_argument("--log_interval", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output_dir", default="Spanda/results")
    parser.add_argument(
        "--configs",
        nargs="*",
        default=None,
        help="Specific experiment configs to run (default: all). "
             "Options: " + ", ".join(EXPERIMENTS.keys()),
    )
    parser.add_argument("--device", default=None, help="Device (auto-detect if not set)")

    args = parser.parse_args()

    # Device
    if args.device:
        device = torch.device(args.device)
    elif torch.cuda.is_available():
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")
    logger.info(f"Device: {device}")

    # Config
    config = BenchmarkConfig(
        model_size=args.model_size,
        max_steps=args.max_steps,
        batch_size=args.batch_size,
        max_seq_len=args.max_seq_len,
        psi_dim=args.psi_dim,
        learning_rate=args.learning_rate,
        eval_interval=args.eval_interval,
        log_interval=args.log_interval,
        seed=args.seed,
        output_dir=args.output_dir,
        dataset=args.dataset,
    )

    # Select experiments
    if args.configs:
        experiment_names = args.configs
        for name in experiment_names:
            if name not in EXPERIMENTS:
                logger.error(f"Unknown config: {name}. Available: {list(EXPERIMENTS.keys())}")
                sys.exit(1)
    else:
        experiment_names = list(EXPERIMENTS.keys())

    logger.info(f"Running {len(experiment_names)} experiments: {experiment_names}")
    logger.info(f"Config: {asdict(config)}")

    # Load data once
    logger.info("Loading data...")
    train_loader, val_loader = create_dataloaders(config)

    # Run experiments
    all_logs = {}
    all_results = {}

    for exp_name in experiment_names:
        exp = EXPERIMENTS[exp_name]
        logger.info(f"\n{exp['description']}")

        logs, results = run_experiment(
            name=exp_name,
            backbone_type=exp["backbone"],
            config=config,
            use_spanda=exp["use_spanda"],
            decay_gamma=exp["gamma"],
            device=device,
            train_loader=train_loader,
            val_loader=val_loader,
        )

        all_logs[exp_name] = logs
        all_results[exp_name] = results

        # Save intermediate results
        os.makedirs(config.output_dir, exist_ok=True)
        with open(os.path.join(config.output_dir, f"{exp_name}_logs.json"), "w") as f:
            json.dump(logs, f, indent=2, default=str)

    # Generate plots and table
    logger.info("\nGenerating plots and results table...")
    os.makedirs(config.output_dir, exist_ok=True)
    plot_dir = os.path.join(config.output_dir, "plots")

    try:
        paths, table = generate_all_plots(all_logs, all_results, plot_dir)
        logger.info(f"Plots saved to {plot_dir}")
    except Exception as e:
        logger.warning(f"Plot generation failed: {e}")
        table = generate_results_table(all_results, config.output_dir)

    # Print results table
    logger.info("\n" + "=" * 60)
    logger.info("RESULTS")
    logger.info("=" * 60)
    logger.info("\n" + table)

    # Save all results
    with open(os.path.join(config.output_dir, "all_results.json"), "w") as f:
        json.dump(all_results, f, indent=2, default=str)

    # Generate conclusion
    conclusion = generate_conclusion(all_results)
    logger.info("\n" + conclusion)

    with open(os.path.join(config.output_dir, "conclusion.md"), "w") as f:
        f.write(conclusion)

    logger.info(f"\nAll results saved to {config.output_dir}")


def generate_conclusion(results: Dict[str, Dict[str, float]]) -> str:
    """Generate written conclusion from results."""
    lines = [
        "# Spanda v0.4 Experiment Conclusion",
        "",
    ]

    # 1. Does Spanda improve coherence?
    lines.append("## 1. Does Spanda improve coherence?")
    phase_base_ppl = results.get("phase_baseline", {}).get("val_perplexity", None)
    phase_spanda_ppl = results.get("phase_spanda", {}).get("val_perplexity", None)
    std_base_ppl = results.get("standard_baseline", {}).get("val_perplexity", None)
    std_spanda_ppl = results.get("standard_spanda", {}).get("val_perplexity", None)

    if phase_base_ppl and phase_spanda_ppl:
        diff = phase_spanda_ppl - phase_base_ppl
        direction = "lower (better)" if diff < 0 else "higher (worse)" if diff > 0 else "equal"
        lines.append(
            f"- PhaseTransformer: baseline PPL={phase_base_ppl:.1f}, "
            f"Spanda PPL={phase_spanda_ppl:.1f} ({direction}, delta={diff:+.1f})"
        )
    if std_base_ppl and std_spanda_ppl:
        diff = std_spanda_ppl - std_base_ppl
        direction = "lower (better)" if diff < 0 else "higher (worse)" if diff > 0 else "equal"
        lines.append(
            f"- StandardTransformer: baseline PPL={std_base_ppl:.1f}, "
            f"Spanda PPL={std_spanda_ppl:.1f} ({direction}, delta={diff:+.1f})"
        )

    psi_cont = results.get("phase_spanda", {}).get("psi_continuity", None)
    h_cont = results.get("phase_spanda", {}).get("backbone_continuity", None)
    if psi_cont and h_cont:
        lines.append(
            f"- Emission continuity (Phase+Spanda): cos(Psi)={psi_cont:.4f}, "
            f"cos(h)={h_cont:.4f}. "
            f"{'Spanda adds smoothness.' if psi_cont > h_cont else 'Backbone already smoother.'}"
        )
    lines.append("")

    # 2. Does gamma influence long-range stability?
    lines.append("## 2. Does gamma influence long-range stability?")
    gamma_results = {}
    for key in ["gamma_099", "gamma_0995", "gamma_0999"]:
        if key in results:
            gamma_results[key] = results[key]

    if gamma_results:
        for key, res in sorted(gamma_results.items()):
            gamma_val = {"gamma_099": 0.99, "gamma_0995": 0.995, "gamma_0999": 0.999}[key]
            lines.append(
                f"- gamma={gamma_val}: PPL={res.get('val_perplexity', 'N/A')}, "
                f"||Psi||={res.get('mean_psi_norm', 'N/A')}, "
                f"cos(Psi)={res.get('psi_continuity', 'N/A')}"
            )
    else:
        lines.append("- Gamma ablations not run.")
    lines.append("")

    # 3. Does Spanda help more on linear vs quadratic?
    lines.append("## 3. Does Spanda help more on linear (O(L)) vs quadratic (O(L^2))?")
    if phase_base_ppl and phase_spanda_ppl and std_base_ppl and std_spanda_ppl:
        phase_delta = phase_spanda_ppl - phase_base_ppl
        std_delta = std_spanda_ppl - std_base_ppl
        lines.append(
            f"- Phase (O(L)): Spanda delta PPL = {phase_delta:+.1f}"
        )
        lines.append(
            f"- Standard (O(L^2)): Spanda delta PPL = {std_delta:+.1f}"
        )
        if abs(phase_delta) > abs(std_delta):
            lines.append("- Spanda has larger effect on linear attention backbone.")
        elif abs(std_delta) > abs(phase_delta):
            lines.append("- Spanda has larger effect on quadratic attention backbone.")
        else:
            lines.append("- Similar effect on both backbones.")
    else:
        lines.append("- Not enough data to compare.")
    lines.append("")

    # 4. Training instability?
    lines.append("## 4. Any training instability?")
    for name, res in results.items():
        tau = res.get("tau", None)
        if tau is not None and (tau < 0.1 or tau > 100):
            lines.append(f"- {name}: Temperature diverged (tau={tau:.3f})")

        cos_mean = res.get("anchor_pairwise_cosine_mean", None)
        if cos_mean is not None and cos_mean > 0.9:
            lines.append(f"- {name}: Anchor collapse risk (mean cosine={cos_mean:.4f})")

    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
