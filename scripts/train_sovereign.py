#!/usr/bin/env python3
"""
Train Sovereign Model on Wikitext-2 Dataset.

Usage:
    python scripts/train_sovereign.py --epochs 3 --batch_size 8

This script:
1. Downloads Wikitext-2 dataset via HuggingFace
2. Preprocesses with SovereignTokenizer (generates C/S/R/G signals)
3. Trains using multi-objective loss with PID Governor
"""

import argparse
import math
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from symbolu.sovereign.embedding import (
    SovereignEmbedding,
    SovereignEmbeddingConfig,
    SovereignOutputHead,
)
from symbolu.sovereign.metrics import SovereignMetrics
from symbolu.sovereign.tagger import SovereignTokenizer
from symbolu.sovereign.train_loss import MultiObjectiveLoss, TrainingLossConfig, VrittiLoss, VrittiLossConfig
from symbolu.sovereign.stitched_objective import (
    VrittiGovernor,
    format_governor_log,
    StitchedScorer,
    ScorerConfig,
    VrittiAspectCoupling,
    EntropyConfidence,
)
from symbolu.sovereign.heartbeat import SovereignHeartbeat, format_governor_telemetry
from symbolu.sovereign.insight_gate import InsightGate, InsightGateConfig, format_gate_log

# Default quality sample prompts
DEFAULT_SAMPLE_PROMPTS = [
    "The history of the Roman Empire began when",
    "In computer science, algorithms are",
    "The weather today is expected to be",
]


def compute_guna_coherence_loss(g_states):
    """
    Compute Guna coherence loss - encourages smooth Guna state transitions.

    Guna states (Sattva/Rajas/Tamas) represent attention quality at each position.
    High coherence = consistent focus across sequence (low variance in transitions).
    Low coherence = scattered/erratic attention shifts.

    Args:
        g_states: [B, Seq, 3] - raw Guna scores (Sattva, Rajas, Tamas)

    Returns:
        coherence_loss: scalar tensor (lower = more coherent/smoother)
    """
    # Normalize to probabilities
    guna_probs = torch.softmax(g_states, dim=-1)  # [B, Seq, 3]

    # Compute difference between adjacent positions
    # Penalizes rapid Guna state changes
    diffs = guna_probs[:, 1:, :] - guna_probs[:, :-1, :]  # [B, Seq-1, 3]

    # L2 norm of differences (smooth transitions = low loss)
    coherence_loss = (diffs ** 2).mean()

    return coherence_loss


@torch.no_grad()
def compute_sovereign_metrics(r_logits, s_logits, target_r, target_s, g_states):
    """
    Compute Sovereign-specific metrics beyond PPL.

    Returns:
        dict with:
        - r_acc: R-Signal (Intent/Ontology) accuracy
        - s_acc: S-Signal (Reality-Lock) accuracy
        - guna_entropy: Entropy of Guna state distribution
        - guna_dist: [Sattva, Rajas, Tamas] distribution
    """
    # R-Accuracy: How well does model predict Intent layer?
    r_preds = r_logits.argmax(dim=-1)  # [B, Seq]
    r_correct = (r_preds == target_r).float()
    r_acc = r_correct.mean().item() * 100

    # S-Accuracy: How well does model predict Reality category?
    s_preds = s_logits.argmax(dim=-1)  # [B, Seq]
    s_correct = (s_preds == target_s).float()
    s_acc = s_correct.mean().item() * 100

    # Guna Distribution: Track S/R/T balance across sequence
    # g_states is [B, Seq, 3] - average across batch and sequence
    guna_mean = g_states.mean(dim=(0, 1))  # [3]
    sattva, rajas, tamas = guna_mean[0].item(), guna_mean[1].item(), guna_mean[2].item()

    # Guna Entropy: Higher entropy = more balanced/exploring, Lower = focused
    guna_probs = torch.softmax(guna_mean, dim=0)
    guna_entropy = -(guna_probs * torch.log(guna_probs + 1e-8)).sum().item()

    return {
        "r_acc": r_acc,
        "s_acc": s_acc,
        "guna_entropy": guna_entropy,
        "sattva": sattva,
        "rajas": rajas,
        "tamas": tamas,
    }


def generate_sample(
    model: nn.Module,
    tokenizer: SovereignTokenizer,
    prompt: str,
    device: torch.device,
    max_new_tokens: int = 50,
    temperature: float = 0.8,
    top_p: float = 0.9,
) -> str:
    """
    Generate text from a prompt using the Sovereign model.

    Uses nucleus (top-p) sampling with temperature for diverse outputs.
    The SovereignTokenizer generates C/S/R/G signals for each token.
    """
    model.eval()

    with torch.no_grad():
        # Get initial encoding with signals
        batch = tokenizer.process_batch([prompt], max_length=512)

        input_ids = batch["input_ids"].to(device)
        c_signals = batch["c_signals"].to(device)
        s_signals = batch["s_signals"].to(device)
        r_signals = batch["r_signals"].to(device)
        g_states = batch["g_states"].to(device)

        # Generate tokens one by one
        for _ in range(max_new_tokens):
            # Forward pass
            token_logits, _, _, _ = model(
                input_ids, c_signals, s_signals, r_signals, g_states
            )

            # Get next token logits (last position)
            next_logits = token_logits[:, -1, :] / temperature

            # Top-p (nucleus) sampling
            sorted_logits, sorted_indices = torch.sort(next_logits, descending=True)
            cumsum = torch.cumsum(torch.softmax(sorted_logits, dim=-1), dim=-1)

            # Remove tokens with cumulative probability above threshold
            sorted_indices_to_remove = cumsum > top_p
            sorted_indices_to_remove[:, 1:] = sorted_indices_to_remove[:, :-1].clone()
            sorted_indices_to_remove[:, 0] = False

            # Set removed tokens to -inf
            indices_to_remove = sorted_indices_to_remove.scatter(
                1, sorted_indices, sorted_indices_to_remove
            )
            next_logits[indices_to_remove] = float("-inf")

            # Sample next token
            probs = torch.softmax(next_logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)

            # Decode the new token to get its signals
            new_token_str = tokenizer.tokenizer.decode(next_token[0])
            new_batch = tokenizer.process_batch([new_token_str], max_length=16)

            # Append new token and its signals
            input_ids = torch.cat([input_ids, next_token], dim=1)
            c_signals = torch.cat([c_signals, new_batch["c_signals"][:, :1].to(device)], dim=1)
            s_signals = torch.cat([s_signals, new_batch["s_signals"][:, :1].to(device)], dim=1)
            r_signals = torch.cat([r_signals, new_batch["r_signals"][:, :1].to(device)], dim=1)
            g_states = torch.cat([g_states, new_batch["g_states"][:, :1].to(device)], dim=1)

            # Stop at EOS
            if next_token.item() == tokenizer.tokenizer.eos_token_id:
                break

    # Decode full sequence (skip prompt tokens)
    prompt_len = batch["input_ids"].shape[1]
    generated_ids = input_ids[0, prompt_len:]
    generated_text = tokenizer.tokenizer.decode(generated_ids, skip_special_tokens=True)

    model.train()
    return generated_text


def generate_with_governor(
    model: nn.Module,
    tokenizer: SovereignTokenizer,
    prompt: str,
    device: torch.device,
    max_new_tokens: int = 50,
    temperature: float = 0.8,
    top_p: float = 0.9,
    verbose: bool = False,
) -> Tuple[str, List[Dict]]:
    """
    Generate text using the Vritti Governor with Stitched Objective.

    This function applies the patent formulas [001]-[007] for penalized
    token selection, preventing hallucination, repetition, and domain drift.

    Args:
        model: SovereignTransformer model
        tokenizer: SovereignTokenizer
        prompt: Input prompt
        device: Torch device
        max_new_tokens: Maximum tokens to generate
        temperature: Sampling temperature
        top_p: Nucleus sampling threshold
        verbose: Print detailed Governor logs

    Returns:
        generated_text: The generated text
        governor_log: List of step-by-step Governor actions
    """
    model.eval()
    governor = VrittiGovernor(d_model=model.embedding.config.d_model)
    governor.to(device)
    governor.reset(1, device)

    governor_log = []
    vritti_names = ["PRAMANA", "VIPARYAYA", "VIKALPA", "SMRTI", "NIDRA"]

    with torch.no_grad():
        # Get initial encoding with signals
        batch = tokenizer.process_batch([prompt], max_length=512)

        input_ids = batch["input_ids"].to(device)
        c_signals = batch["c_signals"].to(device)
        s_signals = batch["s_signals"].to(device)
        r_signals = batch["r_signals"].to(device)
        g_states = batch["g_states"].to(device)
        v_signals = batch.get("v_signals", torch.zeros_like(s_signals)).to(device)

        if verbose:
            print("\n" + "=" * 80)
            print("  VRITTI GOVERNOR GENERATION")
            print("=" * 80)
            print(f"  {'Step':>4} {'Token':<15} {'Vritti':<10} {'Kp':>5} {'Ki':>5} {'Kd':>5} | "
                  f"{'Red':>5} {'Dom':>5} {'Coup':>5} | Action")
            print("-" * 80)

        # Generate tokens one by one
        for step in range(max_new_tokens):
            # Forward pass - get hidden states and logits
            token_logits, r_logits, s_logits, c_pred = model(
                input_ids, c_signals, s_signals, r_signals, g_states
            )

            # Get hidden states from the model's transformer
            # For now, use a simple approximation based on the embedding
            hidden_states = model.embedding(
                input_ids, c_signals, s_signals, r_signals, g_states
            )

            # Get next token logits (last position)
            next_logits = token_logits[:, -1, :] / temperature

            # Predict Vritti for current position
            curr_vritti = v_signals[:, -1] if v_signals.size(1) > 0 else torch.tensor([4], device=device)

            # Apply Governor
            adjusted_logits, penalties = governor(
                next_logits,
                hidden_states,
                curr_vritti,
                c_signals[:, -1, :] if c_signals.dim() == 3 else None,
            )

            # Top-p (nucleus) sampling on adjusted logits
            sorted_logits, sorted_indices = torch.sort(adjusted_logits, descending=True)
            cumsum = torch.cumsum(torch.softmax(sorted_logits, dim=-1), dim=-1)

            sorted_indices_to_remove = cumsum > top_p
            sorted_indices_to_remove[:, 1:] = sorted_indices_to_remove[:, :-1].clone()
            sorted_indices_to_remove[:, 0] = False

            indices_to_remove = sorted_indices_to_remove.scatter(
                1, sorted_indices, sorted_indices_to_remove
            )
            adjusted_logits[indices_to_remove] = float("-inf")

            # Sample next token
            probs = torch.softmax(adjusted_logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)

            # Decode the new token
            new_token_str = tokenizer.tokenizer.decode(next_token[0])
            new_batch = tokenizer.process_batch([new_token_str], max_length=16)

            # Log step
            token_display = new_token_str.replace("\n", "\\n").strip()[:15]
            vritti_id = curr_vritti.item()
            pid = penalties["pid_gains"]

            log_entry = {
                "step": step,
                "token": new_token_str,
                "vritti": vritti_names[vritti_id],
                "kp": pid[0, 0].item(),
                "ki": pid[0, 1].item(),
                "kd": pid[0, 2].item(),
                "redundancy": penalties["redundancy"].item(),
                "domain_jump": penalties["domain_jump"].item(),
                "coupling": penalties["coupling"].item(),
                "reset_triggered": penalties["should_reset"].item(),
            }
            governor_log.append(log_entry)

            if verbose:
                action = "RESET" if log_entry["reset_triggered"] else "OK"
                print(f"  {step:>4} {token_display:<15} {log_entry['vritti']:<10} "
                      f"{log_entry['kp']:>5.2f} {log_entry['ki']:>5.2f} {log_entry['kd']:>5.2f} | "
                      f"{log_entry['redundancy']:>5.3f} {log_entry['domain_jump']:>5.3f} "
                      f"{log_entry['coupling']:>5.3f} | {action}")

            # Append new token and its signals
            input_ids = torch.cat([input_ids, next_token], dim=1)
            c_signals = torch.cat([c_signals, new_batch["c_signals"][:, :1].to(device)], dim=1)
            s_signals = torch.cat([s_signals, new_batch["s_signals"][:, :1].to(device)], dim=1)
            r_signals = torch.cat([r_signals, new_batch["r_signals"][:, :1].to(device)], dim=1)
            g_states = torch.cat([g_states, new_batch["g_states"][:, :1].to(device)], dim=1)
            new_v = new_batch.get("v_signals", torch.zeros(1, 1, dtype=torch.long))
            v_signals = torch.cat([v_signals, new_v[:, :1].to(device)], dim=1)

            # Stop at EOS
            if next_token.item() == tokenizer.tokenizer.eos_token_id:
                break

        if verbose:
            print("=" * 80 + "\n")

    # Decode full sequence (skip prompt tokens)
    prompt_len = batch["input_ids"].shape[1]
    generated_ids = input_ids[0, prompt_len:]
    generated_text = tokenizer.tokenizer.decode(generated_ids, skip_special_tokens=True)

    model.train()
    return generated_text, governor_log


def generate_with_stitched_scorer(
    model: nn.Module,
    tokenizer: SovereignTokenizer,
    prompt: str,
    device: torch.device,
    max_new_tokens: int = 50,
    verbose: bool = False,
) -> Tuple[str, List[Dict]]:
    """
    Generate text using the StitchedScorer with full patent formulas.

    This uses the complete multi-factor relevance (Formula [214]),
    redundancy penalty (Formula [220]), domain-jump penalty (Formula [223]),
    and stitched objective (Formula [226]) for token selection.

    Args:
        model: SovereignTransformer model
        tokenizer: SovereignTokenizer
        prompt: Input prompt
        device: Torch device
        max_new_tokens: Maximum tokens to generate
        verbose: Print detailed scoring logs

    Returns:
        generated_text: The generated text
        scorer_log: List of step-by-step scoring details
    """
    model.eval()

    # Initialize StitchedScorer with patent formulas
    scorer_config = ScorerConfig(
        theta1=0.3,   # Aspect weight exponent
        theta2=0.25,  # Vritti-Aspect coupling exponent
        theta3=0.2,   # Domain fit exponent
        theta4=0.15,  # Template fit exponent
        theta5=0.1,   # Confidence coefficient exponent
        lambda1=0.3,  # Redundancy weight
        lambda2=0.5,  # Domain-jump weight
    )
    scorer = StitchedScorer(
        d_model=model.embedding.config.d_model,
        n_aspects=12,
        config=scorer_config,
    ).to(device)

    scorer_log = []
    vritti_names = ["PRAMANA", "VIPARYAYA", "VIKALPA", "SMRTI", "NIDRA"]

    with torch.no_grad():
        # Get initial encoding with signals
        batch = tokenizer.process_batch([prompt], max_length=512)

        input_ids = batch["input_ids"].to(device)
        c_signals = batch["c_signals"].to(device)
        s_signals = batch["s_signals"].to(device)
        r_signals = batch["r_signals"].to(device)
        g_states = batch["g_states"].to(device)
        v_signals = batch.get("v_signals", torch.zeros_like(s_signals)).to(device)

        if verbose:
            print("\n" + "=" * 90)
            print("  STITCHED SCORER GENERATION (Patent Formulas [214]-[226])")
            print("=" * 90)
            print(f"  {'Step':>4} {'Token':<15} {'Vritti':<10} | "
                  f"{'Relevance':>8} {'Redundancy':>10} {'DomainJump':>10} | {'Score':>8}")
            print("-" * 90)

        # Generate tokens one by one
        for step in range(max_new_tokens):
            # Forward pass
            token_logits, r_logits, s_logits, c_pred = model(
                input_ids, c_signals, s_signals, r_signals, g_states
            )

            # Get hidden states
            hidden_states = model.embedding(
                input_ids, c_signals, s_signals, r_signals, g_states
            )

            # Get current position signals
            current_hidden = hidden_states[:, -1, :]  # [B, d_model]
            current_vritti = v_signals[:, -1]  # [B]
            current_guna = g_states[:, -1, :] if g_states.dim() == 3 else g_states[:, -1].unsqueeze(-1).expand(-1, 3)

            # Create Vritti logits (use R-logits as proxy)
            vritti_logits = torch.zeros(1, 5, device=device)
            vritti_logits[0, :min(5, r_logits.size(2))] = r_logits[0, -1, :min(5, r_logits.size(2))]

            # Use StitchedScorer for token selection (Formula [226])
            selected_token, info = scorer.select_next_token(
                logits=token_logits[:, -1, :],
                hidden_state=current_hidden,
                vritti_logits=vritti_logits,
                guna_states=current_guna,
            )

            # Decode the new token
            new_token_str = tokenizer.tokenizer.decode(selected_token)
            new_batch = tokenizer.process_batch([new_token_str], max_length=16)

            # Log step
            token_display = new_token_str.replace("\n", "\\n").strip()[:15]
            vritti_id = current_vritti.item() if current_vritti.dim() == 0 else current_vritti[0].item()

            log_entry = {
                "step": step,
                "token": new_token_str,
                "vritti": vritti_names[vritti_id] if 0 <= vritti_id <= 4 else "UNKNOWN",
                "relevance": info["relevance"].item(),
                "redundancy": info["redundancy"].item(),
                "domain_jump": info["domain_jump"].item(),
                "entropy_conf": info["entropy_conf"].item(),
                "vritti_coupling": info["vritti_coupling"].item(),
                "selected_score": info["selected_score"].item(),
            }
            scorer_log.append(log_entry)

            if verbose:
                print(f"  {step:>4} {token_display:<15} {log_entry['vritti']:<10} | "
                      f"{log_entry['relevance']:>8.4f} {log_entry['redundancy']:>10.4f} "
                      f"{log_entry['domain_jump']:>10.4f} | {log_entry['selected_score']:>8.4f}")

            # Append new token and its signals
            input_ids = torch.cat([input_ids, selected_token.unsqueeze(0)], dim=1)
            c_signals = torch.cat([c_signals, new_batch["c_signals"][:, :1].to(device)], dim=1)
            s_signals = torch.cat([s_signals, new_batch["s_signals"][:, :1].to(device)], dim=1)
            r_signals = torch.cat([r_signals, new_batch["r_signals"][:, :1].to(device)], dim=1)
            g_states = torch.cat([g_states, new_batch["g_states"][:, :1].to(device)], dim=1)
            new_v = new_batch.get("v_signals", torch.zeros(1, 1, dtype=torch.long))
            v_signals = torch.cat([v_signals, new_v[:, :1].to(device)], dim=1)

            # Stop at EOS
            if selected_token.item() == tokenizer.tokenizer.eos_token_id:
                break

        if verbose:
            print("=" * 90)
            # Summary statistics
            avg_relevance = sum(e["relevance"] for e in scorer_log) / len(scorer_log)
            avg_redundancy = sum(e["redundancy"] for e in scorer_log) / len(scorer_log)
            avg_domain_jump = sum(e["domain_jump"] for e in scorer_log) / len(scorer_log)
            print(f"  Summary: Avg Relevance={avg_relevance:.4f} | "
                  f"Avg Redundancy={avg_redundancy:.4f} | Avg DomainJump={avg_domain_jump:.4f}")
            print("=" * 90 + "\n")

    # Decode full sequence (skip prompt tokens)
    prompt_len = batch["input_ids"].shape[1]
    generated_ids = input_ids[0, prompt_len:]
    generated_text = tokenizer.tokenizer.decode(generated_ids, skip_special_tokens=True)

    model.train()
    return generated_text, scorer_log


def run_quality_samples(
    model: nn.Module,
    tokenizer: SovereignTokenizer,
    prompts: list,
    device: torch.device,
    step: int,
):
    """
    Generate sample outputs to monitor training quality.

    This provides a qualitative check that the model is learning
    meaningful language patterns, not just minimizing perplexity.
    """
    print("")
    print("=" * 60)
    print(f"  📝 QUALITY SAMPLES (Step {step})")
    print("=" * 60)

    for prompt in prompts:
        try:
            generated = generate_sample(
                model, tokenizer, prompt, device,
                max_new_tokens=50,
                temperature=0.8,
                top_p=0.9,
            )
            # Clean up and truncate for display
            generated = generated.strip().replace("\n", " ")[:200]
            print(f'  Prompt: "{prompt}"')
            print(f'  Output: "{generated}"')
            print("")
        except Exception as e:
            print(f"  Sampling failed for prompt '{prompt[:30]}...': {e}")

    print("=" * 60)
    print("")


def sovereign_collate_fn(batch):
    """Custom collate function that pads tensors to the same length."""
    # Find max sequence length in this batch
    max_len = max(item["input_ids"].shape[0] for item in batch)

    # Pad each tensor to max_len
    padded_batch = {
        "input_ids": [],
        "c_signals": [],
        "s_signals": [],
        "r_signals": [],
        "g_states": [],
        "attention_mask": [],
    }

    for item in batch:
        seq_len = item["input_ids"].shape[0]
        pad_len = max_len - seq_len

        # Pad input_ids with 0 (typically pad token)
        padded_batch["input_ids"].append(
            torch.nn.functional.pad(item["input_ids"], (0, pad_len), value=0)
        )
        # Pad c_signals [seq, 32] -> pad on seq dimension
        padded_batch["c_signals"].append(
            torch.nn.functional.pad(item["c_signals"], (0, 0, 0, pad_len), value=0)
        )
        # Pad s_signals [seq]
        padded_batch["s_signals"].append(
            torch.nn.functional.pad(item["s_signals"], (0, pad_len), value=0)
        )
        # Pad r_signals [seq]
        padded_batch["r_signals"].append(
            torch.nn.functional.pad(item["r_signals"], (0, pad_len), value=0)
        )
        # Pad g_states [seq, 3] -> pad on seq dimension
        padded_batch["g_states"].append(
            torch.nn.functional.pad(item["g_states"], (0, 0, 0, pad_len), value=0)
        )
        # Pad attention_mask [seq]
        padded_batch["attention_mask"].append(
            torch.nn.functional.pad(item["attention_mask"], (0, pad_len), value=0)
        )

    # Stack into batch tensors
    return {
        "input_ids": torch.stack(padded_batch["input_ids"]),
        "c_signals": torch.stack(padded_batch["c_signals"]),
        "s_signals": torch.stack(padded_batch["s_signals"]),
        "r_signals": torch.stack(padded_batch["r_signals"]),
        "g_states": torch.stack(padded_batch["g_states"]),
        "attention_mask": torch.stack(padded_batch["attention_mask"]),
    }


class SovereignTransformer(nn.Module):
    """Sovereign Transformer for training."""

    def __init__(self, config, n_heads=16, n_layers=6):
        super().__init__()
        self.embedding = SovereignEmbedding(config)
        self.transformer = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(
                d_model=config.d_model,
                nhead=n_heads,
                dim_feedforward=config.d_model * 4,
                batch_first=True,
                dropout=0.1,
            ),
            num_layers=n_layers,
        )
        self.output_head = SovereignOutputHead(config)

    def forward(self, input_ids, c_signals, s_signals, r_signals, g_states, attention_mask=None):
        x = self.embedding(input_ids, c_signals, s_signals, r_signals, g_states)

        # Create causal mask
        seq_len = x.size(1)
        causal_mask = torch.triu(
            torch.ones(seq_len, seq_len, device=x.device), diagonal=1
        ).bool()

        x = self.transformer(x, mask=causal_mask)
        return self.output_head(x)


class WikitextSovereignDataset(Dataset):
    """Dataset that preprocesses Wikitext with Sovereign signals."""

    def __init__(self, texts, tokenizer, max_length=128):
        self.texts = texts
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        text = self.texts[idx]

        # Process with SovereignTokenizer
        # Note: padding and truncation are handled internally by process_batch
        batch = self.tokenizer.process_batch(
            [text],
            max_length=self.max_length,
        )

        # Remove batch dimension
        return {
            "input_ids": batch["input_ids"][0],
            "c_signals": batch["c_signals"][0],
            "s_signals": batch["s_signals"][0],
            "r_signals": batch["r_signals"][0],
            "g_states": batch["g_states"][0],
            "attention_mask": batch["attention_mask"][0],
        }


def load_dataset_texts(dataset_name, split="train", max_samples=None):
    """
    Load dataset texts from HuggingFace.

    Supported datasets:
    - wikitext-2: Wikitext-2-raw-v1
    - wikitext-103: Wikitext-103-raw-v1
    - openwebtext: OpenWebText
    - c4: C4 (en subset)
    - bookcorpus: BookCorpus
    - pile: The Pile (subset)
    """
    try:
        from datasets import load_dataset
    except ImportError:
        print("Installing datasets...")
        os.system("pip install datasets")
        from datasets import load_dataset

    dataset_name = dataset_name.lower()

    # Dataset configurations
    DATASET_CONFIGS = {
        "wikitext-2": ("wikitext", "wikitext-2-raw-v1", "text"),
        "wikitext-103": ("wikitext", "wikitext-103-raw-v1", "text"),
        "openwebtext": ("openwebtext", None, "text"),
        "c4": ("allenai/c4", "en", "text"),
        "bookcorpus": ("bookcorpus", None, "text"),
        "pile": ("monology/pile-uncopyrighted", None, "text"),
        "tinystories": ("roneneldan/TinyStories", None, "text"),
    }

    if dataset_name not in DATASET_CONFIGS:
        available = ", ".join(DATASET_CONFIGS.keys())
        raise ValueError(f"Unknown dataset: {dataset_name}. Available: {available}")

    repo, config, text_field = DATASET_CONFIGS[dataset_name]

    print(f"Loading {dataset_name} ({split})...")

    # Handle streaming for large datasets
    if dataset_name in ["c4", "pile", "openwebtext"]:
        print("  (Using streaming for large dataset)")
        if config:
            dataset = load_dataset(repo, config, split=split, streaming=True)
        else:
            dataset = load_dataset(repo, split=split, streaming=True)

        texts = []
        for i, item in enumerate(dataset):
            text = item[text_field]
            if len(text.strip()) > 50:
                texts.append(text)
            if max_samples and len(texts) >= max_samples:
                break
    else:
        # Non-streaming for smaller datasets
        if config:
            dataset = load_dataset(repo, config, split=split)
        else:
            dataset = load_dataset(repo, split=split)

        # Filter empty lines and short texts
        texts = [t for t in dataset[text_field] if len(t.strip()) > 50]

        if max_samples:
            texts = texts[:max_samples]

    print(f"Loaded {len(texts)} samples from {dataset_name}")
    return texts


def train_epoch(
    model, dataloader, optimizer, loss_fn, device, epoch,
    tokenizer=None, sample_every=0, sample_prompts=None, global_step=0
):
    """Train for one epoch with optional quality sampling."""
    model.train()
    total_loss = 0
    total_r_acc = 0
    total_s_acc = 0
    total_guna_entropy = 0
    num_batches = 0
    step = global_step

    pbar = tqdm(dataloader, desc=f"Epoch {epoch+1}")
    for batch in pbar:
        step += 1

        # Move to device
        input_ids = batch["input_ids"].to(device)
        c_signals = batch["c_signals"].to(device)
        s_signals = batch["s_signals"].to(device)
        r_signals = batch["r_signals"].to(device)
        g_states = batch["g_states"].to(device)

        # Shift for next-token prediction
        target_tokens = input_ids[:, 1:].contiguous()
        target_r = r_signals[:, 1:].contiguous()
        target_s = s_signals[:, 1:].contiguous()
        target_c = c_signals[:, 1:].contiguous()

        input_ids = input_ids[:, :-1]
        c_signals = c_signals[:, :-1]
        s_signals = s_signals[:, :-1]
        r_signals = r_signals[:, :-1]
        g_states = g_states[:, :-1]

        # Forward pass
        optimizer.zero_grad()
        token_logits, r_logits, s_logits, c_pred = model(
            input_ids, c_signals, s_signals, r_signals, g_states
        )

        # Compute loss
        loss_output = loss_fn(
            token_logits=token_logits,
            r_logits=r_logits,
            s_logits=s_logits,
            c_pred=c_pred,
            target_tokens=target_tokens,
            target_r=target_r,
            target_s=target_s,
            target_c=target_c,
        )

        # Backward pass
        loss_output.total.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

        # Compute Sovereign metrics (R-Acc, S-Acc, Guna)
        sov_metrics = compute_sovereign_metrics(
            r_logits, s_logits, target_r, target_s, g_states
        )

        total_loss += loss_output.total.item()
        total_r_acc += sov_metrics["r_acc"]
        total_s_acc += sov_metrics["s_acc"]
        total_guna_entropy += sov_metrics["guna_entropy"]
        num_batches += 1

        # Update progress bar with PPL and Sovereign metrics
        token_ppl = math.exp(loss_output.token) if loss_output.token < 20 else float('inf')
        pbar.set_postfix({
            "PPL": f"{token_ppl:.1f}",
            "R%": f"{sov_metrics['r_acc']:.1f}",
            "S%": f"{sov_metrics['s_acc']:.1f}",
            "G": f"S{sov_metrics['sattva']:.2f}/R{sov_metrics['rajas']:.2f}/T{sov_metrics['tamas']:.2f}",
        })

        # Quality sampling
        if sample_every > 0 and step % sample_every == 0 and tokenizer is not None:
            run_quality_samples(model, tokenizer, sample_prompts or DEFAULT_SAMPLE_PROMPTS, device, step)

    avg_loss = total_loss / num_batches
    avg_r_acc = total_r_acc / num_batches
    avg_s_acc = total_s_acc / num_batches
    avg_guna_entropy = total_guna_entropy / num_batches
    ppl = math.exp(avg_loss) if avg_loss < 20 else float('inf')

    return {
        "loss": avg_loss,
        "ppl": ppl,
        "r_acc": avg_r_acc,
        "s_acc": avg_s_acc,
        "guna_entropy": avg_guna_entropy,
        "step": step,
    }


@torch.no_grad()
def validate(model, dataloader, loss_fn, device):
    """Run validation and compute perplexity + Sovereign metrics."""
    model.eval()
    total_loss = 0
    total_tokens = 0
    total_r_acc = 0
    total_s_acc = 0
    total_guna_entropy = 0
    num_batches = 0

    for batch in tqdm(dataloader, desc="Validating", leave=False):
        input_ids = batch["input_ids"].to(device)
        c_signals = batch["c_signals"].to(device)
        s_signals = batch["s_signals"].to(device)
        r_signals = batch["r_signals"].to(device)
        g_states = batch["g_states"].to(device)

        # Shift for next-token prediction
        target_tokens = input_ids[:, 1:].contiguous()
        target_r = r_signals[:, 1:].contiguous()
        target_s = s_signals[:, 1:].contiguous()
        target_c = c_signals[:, 1:].contiguous()

        input_ids = input_ids[:, :-1]
        c_signals = c_signals[:, :-1]
        s_signals = s_signals[:, :-1]
        r_signals = r_signals[:, :-1]
        g_states = g_states[:, :-1]

        # Forward pass
        token_logits, r_logits, s_logits, c_pred = model(
            input_ids, c_signals, s_signals, r_signals, g_states
        )

        # Compute loss
        loss_output = loss_fn(
            token_logits=token_logits,
            r_logits=r_logits,
            s_logits=s_logits,
            c_pred=c_pred,
            target_tokens=target_tokens,
            target_r=target_r,
            target_s=target_s,
            target_c=target_c,
        )

        # Compute Sovereign metrics
        sov_metrics = compute_sovereign_metrics(
            r_logits, s_logits, target_r, target_s, g_states
        )

        # Accumulate
        batch_size, seq_len = target_tokens.shape
        total_loss += loss_output.token * batch_size * seq_len
        total_tokens += batch_size * seq_len
        total_r_acc += sov_metrics["r_acc"]
        total_s_acc += sov_metrics["s_acc"]
        total_guna_entropy += sov_metrics["guna_entropy"]
        num_batches += 1

    model.train()

    avg_loss = total_loss / total_tokens if total_tokens > 0 else float('inf')
    ppl = math.exp(avg_loss) if avg_loss < 20 else float('inf')
    avg_r_acc = total_r_acc / num_batches if num_batches > 0 else 0
    avg_s_acc = total_s_acc / num_batches if num_batches > 0 else 0
    avg_guna_entropy = total_guna_entropy / num_batches if num_batches > 0 else 0

    return {
        "loss": avg_loss,
        "ppl": ppl,
        "r_acc": avg_r_acc,
        "s_acc": avg_s_acc,
        "guna_entropy": avg_guna_entropy,
    }


# Model size configurations
MODEL_SIZES = {
    "small": {"d_model": 512, "n_layers": 4, "n_heads": 8},
    "medium": {"d_model": 1024, "n_layers": 6, "n_heads": 16},
    "large": {"d_model": 1536, "n_layers": 12, "n_heads": 16},
    "xl": {"d_model": 2048, "n_layers": 24, "n_heads": 16},
}


def main():
    parser = argparse.ArgumentParser(
        description="Train Sovereign Model",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Model sizes:
  small   ~25M params  (d=512, layers=4)
  medium  ~85M params  (d=1024, layers=6)
  large   ~300M params (d=1536, layers=12)
  xl      ~800M params (d=2048, layers=24)

Supported datasets:
  wikitext-2, wikitext-103, openwebtext, c4, tinystories, bookcorpus, pile

Examples:
  python train_sovereign.py --model_size medium --dataset wikitext-103 --max_seq_len 1024
  python train_sovereign.py --model_size small --dataset tinystories --max_steps 10000
  python train_sovereign.py --model_size large --dataset c4 --gradient_checkpointing --gradient_accumulation 4
  python train_sovereign.py --model_size medium --use_guna_coherence --lambda_guna 0.15
"""
    )
    # Model
    parser.add_argument("--model_size", type=str, default="medium",
                        choices=["small", "medium", "large", "xl"],
                        help="Model size preset (default: medium)")
    parser.add_argument("--n_layers", type=int, default=None,
                        help="Override number of layers")

    # Dataset
    parser.add_argument("--dataset", type=str, default="wikitext-2",
                        help="Dataset to train on (default: wikitext-2)")
    parser.add_argument("--max_seq_len", type=int, default=512,
                        help="Max sequence length (default: 512)")
    parser.add_argument("--max_samples", type=int, default=None,
                        help="Max training samples (None=all)")

    # Training
    parser.add_argument("--epochs", type=int, default=None,
                        help="Number of epochs (use --max_steps instead for step-based)")
    parser.add_argument("--max_steps", type=int, default=None,
                        help="Max training steps (overrides --epochs)")
    parser.add_argument("--batch_size", type=int, default=8, help="Batch size")
    parser.add_argument("--gradient_accumulation", type=int, default=1,
                        help="Gradient accumulation steps")
    parser.add_argument("--lr", type=float, default=3e-4, help="Learning rate")

    # Optimizations
    parser.add_argument("--gradient_checkpointing", action="store_true",
                        help="Enable gradient checkpointing to save memory")
    parser.add_argument("--use_guna_coherence", action="store_true",
                        help="Add Guna coherence loss (smooth Sattva/Rajas/Tamas transitions)")
    parser.add_argument("--lambda_guna", type=float, default=0.1,
                        help="Weight for Guna coherence loss (default: 0.1)")

    # SGP (Stochastic Gradient Persistence)
    parser.add_argument("--sgp_rate", type=int, default=20,
                        help="SGP base rate (steps to persist gradients). Higher = more cement (default: 20)")
    parser.add_argument("--sgp_boost", type=float, default=2.0,
                        help="SGP rate multiplier during mode collapse (default: 2.0)")
    parser.add_argument("--use_sgp", action="store_true",
                        help="Enable SGP synchronized with Sattvic Controller")

    # Vritti PID Governor
    parser.add_argument("--use_vritti", action="store_true",
                        help="Enable Vritti-driven PID Governor with stiffness multiplier")
    parser.add_argument("--show_heartbeat", action="store_true",
                        help="Show Sovereign Heartbeat visualization during training")
    parser.add_argument("--heartbeat_every", type=int, default=50,
                        help="Show heartbeat every N steps (default: 50)")

    # Output
    parser.add_argument("--save_dir", type=str, default="checkpoints/sovereign",
                        help="Save directory")
    parser.add_argument("--sample_every", type=int, default=500,
                        help="Generate quality samples every N steps (0=disabled)")
    parser.add_argument("--health_check_every", type=int, default=100,
                        help="Print Sovereign health dashboard every N steps (0=disabled)")
    parser.add_argument("--save_every", type=int, default=1000,
                        help="Save checkpoint every N steps")
    parser.add_argument("--log_every", type=int, default=10,
                        help="Log metrics every N steps")

    args = parser.parse_args()

    # Set default epochs if neither epochs nor max_steps specified
    if args.epochs is None and args.max_steps is None:
        args.epochs = 3

    # Device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # Get model config from size preset
    size_config = MODEL_SIZES[args.model_size]
    d_model = size_config["d_model"]
    n_layers = args.n_layers if args.n_layers else size_config["n_layers"]
    n_heads = size_config["n_heads"]

    # Create model
    print(f"\n1. Creating {args.model_size} model...")
    print(f"   d_model={d_model}, n_layers={n_layers}, n_heads={n_heads}")

    # Calculate body_dim based on d_model
    # Header is always 128 dims: r_dim(48) + c_dim(32) + s_dim(32) + g_dim(16)
    header_dim = 48 + 32 + 32 + 16  # 128
    body_dim = d_model - header_dim
    if body_dim < 64:
        raise ValueError(f"d_model={d_model} too small. Need at least {header_dim + 64}=192 for header+body")

    embed_config = SovereignEmbeddingConfig(
        vocab_size=50257,
        d_model=d_model,
        body_dim=body_dim,
    )
    model = SovereignTransformer(embed_config, n_heads=n_heads, n_layers=n_layers)

    # Enable gradient checkpointing if requested
    if args.gradient_checkpointing:
        print("   Gradient checkpointing enabled")
        if hasattr(model.transformer, 'gradient_checkpointing_enable'):
            model.transformer.gradient_checkpointing_enable()
        else:
            # Manual checkpointing for nn.TransformerEncoder
            from torch.utils.checkpoint import checkpoint_sequential
            model._use_gradient_checkpointing = True

    model.to(device)
    print(f"   Parameters: {sum(p.numel() for p in model.parameters()):,}")

    # Create tokenizer
    print("\n2. Creating SovereignTokenizer...")
    tokenizer = SovereignTokenizer()

    # Load datasets
    print(f"\n3. Loading {args.dataset} dataset...")
    train_texts = load_dataset_texts(args.dataset, split="train", max_samples=args.max_samples)

    # Try to load validation split, fall back to using portion of train
    val_max = args.max_samples // 10 if args.max_samples else 500
    try:
        val_texts = load_dataset_texts(args.dataset, split="validation", max_samples=val_max)
    except Exception:
        # Some datasets don't have validation split, use last portion of train
        print("  No validation split, using 10% of train data")
        split_idx = int(len(train_texts) * 0.9)
        val_texts = train_texts[split_idx:]
        train_texts = train_texts[:split_idx]

    # Create dataset and dataloader
    print("\n4. Creating dataloaders...")
    train_dataset = WikitextSovereignDataset(train_texts, tokenizer, max_length=args.max_seq_len)
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0,  # NLTK not fork-safe
        drop_last=True,
        collate_fn=sovereign_collate_fn,
    )
    val_dataset = WikitextSovereignDataset(val_texts, tokenizer, max_length=args.max_seq_len)
    val_loader = DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,
        drop_last=False,
        collate_fn=sovereign_collate_fn,
    )
    print(f"   Train batches: {len(train_loader)}, Val batches: {len(val_loader)}")
    print(f"   Effective batch size: {args.batch_size * args.gradient_accumulation}")

    # Calculate total steps
    steps_per_epoch = len(train_loader) // args.gradient_accumulation
    if args.max_steps:
        total_steps = args.max_steps
        num_epochs = (total_steps // steps_per_epoch) + 1
    else:
        num_epochs = args.epochs
        total_steps = num_epochs * steps_per_epoch

    # Create loss and optimizer
    print("\n5. Setting up training...")
    loss_config = TrainingLossConfig(
        lambda_token=1.0,
        lambda_r=0.1,
        lambda_s=0.1,
        lambda_c=0.05,
    )
    loss_fn = MultiObjectiveLoss(loss_config)

    # Vritti-driven loss (optional)
    vritti_loss_fn = None
    governor = None
    heartbeat = None
    if args.use_vritti:
        vritti_loss_config = VrittiLossConfig(
            lambda_token=1.0,
            lambda_vritti=0.2,
            transition_weight=0.5,
        )
        vritti_loss_fn = VrittiLoss(vritti_loss_config).to(device)
        governor = VrittiGovernor(d_model=d_model).to(device)
        print("  Vritti PID Governor: ENABLED")
        if args.show_heartbeat:
            heartbeat = SovereignHeartbeat()
            print(f"  Sovereign Heartbeat: ENABLED (every {args.heartbeat_every} steps)")

    # Initialize Insight Gate for epistemic stability control
    insight_gate = None
    if args.use_vritti:
        gate_config = InsightGateConfig(
            stability_threshold=0.78,
            risk_threshold=0.25,
            r_acc_min=0.92,
            s_acc_min=0.85,
        )
        insight_gate = InsightGate(gate_config).to(device)
        print("  Insight Gate: ENABLED (STAB>=0.78, RISK<=0.25)")

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=total_steps)

    # Training loop
    print("\n" + "=" * 70)
    print("TRAINING")
    print("=" * 70)
    print(f"  Model: {args.model_size} | Dataset: {args.dataset}")
    print(f"  Max seq len: {args.max_seq_len} | Batch: {args.batch_size} x {args.gradient_accumulation}")
    print(f"  Total steps: {total_steps} | LR: {args.lr}")
    if args.sample_every > 0:
        print(f"  Quality samples every {args.sample_every} steps")
    if args.health_check_every > 0:
        print(f"  Health dashboard every {args.health_check_every} steps")
    if args.use_guna_coherence:
        print(f"  Guna coherence loss: ENABLED (lambda={args.lambda_guna})")
    if args.use_vritti:
        print(f"  Vritti PID Governor: ENABLED")
    print("=" * 70)

    os.makedirs(args.save_dir, exist_ok=True)
    best_val_ppl = float("inf")
    global_step = 0
    accum_loss = 0
    accum_metrics = {"r_acc": 0, "s_acc": 0, "guna_entropy": 0}

    for epoch in range(num_epochs):
        model.train()
        pbar = tqdm(train_loader, desc=f"Epoch {epoch+1}/{num_epochs}")

        for batch_idx, batch in enumerate(pbar):
            # Check max_steps
            if args.max_steps and global_step >= args.max_steps:
                break

            # Move to device
            input_ids = batch["input_ids"].to(device)
            c_signals = batch["c_signals"].to(device)
            s_signals = batch["s_signals"].to(device)
            r_signals = batch["r_signals"].to(device)
            g_states = batch["g_states"].to(device)

            # Shift for next-token prediction
            target_tokens = input_ids[:, 1:].contiguous()
            target_r = r_signals[:, 1:].contiguous()
            target_s = s_signals[:, 1:].contiguous()
            target_c = c_signals[:, 1:].contiguous()

            input_ids = input_ids[:, :-1]
            c_signals = c_signals[:, :-1]
            s_signals = s_signals[:, :-1]
            r_signals = r_signals[:, :-1]
            g_states = g_states[:, :-1]

            # Forward pass
            token_logits, r_logits, s_logits, c_pred = model(
                input_ids, c_signals, s_signals, r_signals, g_states
            )

            # Compute loss
            loss_output = loss_fn(
                token_logits=token_logits,
                r_logits=r_logits,
                s_logits=s_logits,
                c_pred=c_pred,
                target_tokens=target_tokens,
                target_r=target_r,
                target_s=target_s,
                target_c=target_c,
            )

            # Add Guna coherence loss if enabled
            total_loss = loss_output.total
            if args.use_guna_coherence:
                guna_coh_loss = compute_guna_coherence_loss(g_states)
                total_loss = total_loss + args.lambda_guna * guna_coh_loss

            # Add Vritti-driven loss if enabled
            vritti_info = None
            if args.use_vritti and vritti_loss_fn is not None:
                # Get Vritti signals from ORIGINAL batch (before r_signals was sliced above)
                # Use target_r as vritti target since it's already shifted to [:, 1:]
                if "v_signals" in batch:
                    v_signals_full = batch["v_signals"].to(device)
                    target_vritti = v_signals_full[:, 1:].contiguous()  # [B, N-1]
                else:
                    # Use target_r (already shifted r_signals[:, 1:]) as Vritti proxy
                    target_vritti = target_r.clamp(0, 4).contiguous()  # [B, N-1]

                # prev_vritti: for each position, what was the previous vritti state
                # Shift target_vritti right by 1, pad with Nidrā (4) at start
                prev_vritti = torch.cat([
                    torch.full((target_vritti.size(0), 1), 4, device=device, dtype=target_vritti.dtype),
                    target_vritti[:, :-1]
                ], dim=1)  # [B, N-1]

                # Compute Vritti prediction logits (use R-logits as proxy if no dedicated head)
                # r_logits is already [B, N-1, r_classes] matching target shape
                vritti_logits = torch.zeros(r_logits.size(0), r_logits.size(1), 5, device=device)
                vritti_logits[:, :, :min(5, r_logits.size(2))] = r_logits[:, :, :min(5, r_logits.size(2))]

                # token_logits is already [B, N-1, V] matching target_tokens shape
                # No slicing needed!

                # Compute VrittiLoss with stiffness multiplier
                vritti_output = vritti_loss_fn(
                    token_logits=token_logits,
                    vritti_logits=vritti_logits,
                    target_tokens=target_tokens,
                    target_vritti=target_vritti,
                    prev_vritti=prev_vritti,
                )
                total_loss = total_loss + vritti_output.total * 0.5  # Weight Vritti loss

                # Compute metrics early (needed for InsightGate)
                sov_metrics = compute_sovereign_metrics(r_logits, s_logits, target_r, target_s, g_states)

                # Apply Governor for telemetry (sample last position)
                if governor is not None:
                    hidden_states = model.embedding(
                        input_ids, c_signals, s_signals, r_signals, g_states
                    )
                    # Use predicted Vritti from logits for Governor
                    vritti_pred = vritti_logits.argmax(dim=-1)[:, -1]  # [B]
                    _, vritti_info = governor(
                        token_logits[:, -1, :],
                        hidden_states,
                        vritti_pred,
                        c_signals[:, -1, :] if c_signals.dim() == 3 else None,
                        g_states[:, -1, :] if g_states.dim() == 3 else None,
                        step=global_step,
                        record_telemetry=True,
                    )

                    # Apply Insight Gate for epistemic stability control
                    if insight_gate is not None:
                        # Extract 128-D biological header from hidden states
                        # Header is at positions body_dim: (G|S|R|C in last 128 dims)
                        biological_header = hidden_states[:, -1, body_dim:]  # [B, 128]

                        # Gather metrics for gate
                        gate_metrics = {
                            "r_acc": sov_metrics["r_acc"] / 100.0,  # Convert to 0-1
                            "s_acc": sov_metrics["s_acc"] / 100.0,
                            "gc": 1.0 - sov_metrics["guna_entropy"],  # Coherence = 1 - entropy
                            "drift": vritti_info["s_drift"].mean(),
                            "vritti": vritti_pred,
                            "authority": 1.0 - vritti_info.get("tamas_ratio", torch.tensor(0.33)).mean(),
                        }

                        # Run gate check
                        gate_output = insight_gate(biological_header, gate_metrics)

                        # Compute token entropy for surfacing penalty
                        token_probs = torch.softmax(token_logits[:, -1, :], dim=-1)
                        token_entropy = -(token_probs * torch.log(token_probs + 1e-8)).sum(dim=-1)

                        # Apply surfacing penalty if trying to be creative without stability
                        surfacing_penalty = insight_gate.get_surfacing_penalty(
                            gate_output, token_entropy, lambda_insight=0.3
                        )
                        total_loss = total_loss + surfacing_penalty.mean()

                        # Store gate info for logging
                        vritti_info["gate_stab"] = gate_output["stab_score"]
                        vritti_info["gate_risk"] = gate_output["risk_score"]
                        vritti_info["gate_released"] = gate_output["can_release"]

            # Scale loss for gradient accumulation
            loss = total_loss / args.gradient_accumulation
            loss.backward()

            # Use previously computed metrics (sov_metrics already computed above if use_vritti)
            if not args.use_vritti:
                sov_metrics = compute_sovereign_metrics(r_logits, s_logits, target_r, target_s, g_states)
            accum_loss += loss_output.total.item()
            accum_metrics["r_acc"] += sov_metrics["r_acc"]
            accum_metrics["s_acc"] += sov_metrics["s_acc"]
            accum_metrics["guna_entropy"] += sov_metrics["guna_entropy"]
            if args.use_guna_coherence:
                accum_metrics["guna_coh"] = accum_metrics.get("guna_coh", 0) + guna_coh_loss.item()
            if args.use_vritti and vritti_info is not None:
                accum_metrics["s_drift"] = accum_metrics.get("s_drift", 0) + vritti_info["s_drift"].mean().item()
                accum_metrics["stiffness"] = accum_metrics.get("stiffness", 0) + vritti_info["pid_gains"][:, 0].mean().item()
                # Track InsightGate metrics
                if "gate_stab" in vritti_info:
                    accum_metrics["gate_stab"] = accum_metrics.get("gate_stab", 0) + vritti_info["gate_stab"].mean().item()
                    accum_metrics["gate_risk"] = accum_metrics.get("gate_risk", 0) + vritti_info["gate_risk"].mean().item()
                    accum_metrics["gate_released"] = accum_metrics.get("gate_released", 0) + vritti_info["gate_released"].any().float().item()

            # Gradient accumulation step
            if (batch_idx + 1) % args.gradient_accumulation == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()
                global_step += 1

                # Average accumulated metrics
                avg_loss = accum_loss / args.gradient_accumulation
                avg_r_acc = accum_metrics["r_acc"] / args.gradient_accumulation
                avg_s_acc = accum_metrics["s_acc"] / args.gradient_accumulation
                token_ppl = math.exp(avg_loss) if avg_loss < 20 else float('inf')

                # Update progress bar
                postfix = {
                    "step": global_step,
                    "PPL": f"{token_ppl:.1f}",
                    "R%": f"{avg_r_acc:.1f}",
                    "S%": f"{avg_s_acc:.1f}",
                }
                if args.use_guna_coherence:
                    avg_guna_coh = accum_metrics.get("guna_coh", 0) / args.gradient_accumulation
                    postfix["GC"] = f"{avg_guna_coh:.4f}"
                if args.use_vritti:
                    avg_drift = accum_metrics.get("s_drift", 0) / args.gradient_accumulation
                    avg_stiff = accum_metrics.get("stiffness", 0) / args.gradient_accumulation
                    postfix["Drift"] = f"{avg_drift:.3f}"
                    postfix["Kp"] = f"{avg_stiff:.2f}"
                    # Add InsightGate metrics
                    if "gate_stab" in accum_metrics:
                        avg_stab = accum_metrics.get("gate_stab", 0) / args.gradient_accumulation
                        avg_risk = accum_metrics.get("gate_risk", 0) / args.gradient_accumulation
                        postfix["STAB"] = f"{avg_stab:.2f}"
                        postfix["RISK"] = f"{avg_risk:.2f}"
                pbar.set_postfix(postfix)

                # Reset accumulators
                accum_loss = 0
                accum_metrics = {"r_acc": 0, "s_acc": 0, "guna_entropy": 0}

                # Sovereign Heartbeat visualization
                if args.show_heartbeat and heartbeat is not None and governor is not None:
                    if global_step % args.heartbeat_every == 0 and len(governor.telemetry_history) > 0:
                        heartbeat.update(governor.telemetry_history[-1])
                        print("\n" + heartbeat.render())

                # Quality sampling
                if args.sample_every > 0 and global_step % args.sample_every == 0:
                    run_quality_samples(model, tokenizer, DEFAULT_SAMPLE_PROMPTS, device, global_step)

                # Sovereign Health Check dashboard
                if args.health_check_every > 0 and global_step % args.health_check_every == 0:
                    health_stats = SovereignMetrics.get_health_stats(
                        token_logits, r_logits, s_logits,
                        target_tokens, target_r, target_s
                    )
                    guna_coherence = SovereignMetrics.get_guna_coherence(g_states)
                    guna_state = SovereignMetrics.get_guna_state(g_states)
                    dashboard = SovereignMetrics.format_health_check(
                        global_step, health_stats, guna_state, guna_coherence, ppl=token_ppl
                    )
                    print(dashboard)

                # Periodic checkpoint
                if args.save_every > 0 and global_step % args.save_every == 0:
                    ckpt_path = os.path.join(args.save_dir, f"step_{global_step}.pt")
                    torch.save({"step": global_step, "model_state_dict": model.state_dict()}, ckpt_path)
                    print(f"  💾 Checkpoint saved: {ckpt_path}")

        # Check max_steps at epoch end
        if args.max_steps and global_step >= args.max_steps:
            break

        # Validate
        val_metrics = validate(model, val_loader, loss_fn, device)

        # Print Sovereign metrics
        print(f"\n{'='*70}")
        print(f"  EPOCH {epoch+1}/{num_epochs} | Step {global_step}/{total_steps}")
        print(f"{'='*70}")
        print(f"  Val PPL:        {val_metrics['ppl']:>10.2f}")
        print(f"  Val R-Acc:      {val_metrics['r_acc']:>9.1f}%")
        print(f"  Val S-Acc:      {val_metrics['s_acc']:>9.1f}%")
        print(f"  Guna Entropy:   {val_metrics['guna_entropy']:>10.3f}")
        print(f"{'='*70}")

        # Save checkpoint based on val PPL
        val_ppl = val_metrics["ppl"]
        if val_ppl < best_val_ppl:
            best_val_ppl = val_ppl
            checkpoint_path = os.path.join(args.save_dir, "best_model.pt")
            torch.save({
                "step": global_step,
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_metrics": val_metrics,
                "args": vars(args),
            }, checkpoint_path)
            print(f"  📦 New best! Val PPL: {val_ppl:.2f} | R-Acc: {val_metrics['r_acc']:.1f}% | S-Acc: {val_metrics['s_acc']:.1f}%")
            print(f"     Saved to {checkpoint_path}")

    # Final summary
    print("\n" + "=" * 70)
    print("TRAINING COMPLETE")
    print(f"  Total steps: {global_step}")
    print(f"  Best Val PPL: {best_val_ppl:.2f}")
    print("=" * 70)


if __name__ == "__main__":
    main()
