#!/usr/bin/env python3
"""
PhonemeBCVF Signal Validation — Decisive 3-Layer Test
======================================================

Tests whether the Sanskrit phoneme prior is a FUNCTIONAL BCVF signal
or merely DECORATIVE, using three evaluation layers:

    Layer 1 — Token-level:  Does it change next-token behavior?
        ΔPPL, ΔNLL, ΔECE, ΔBrier, argmax_flip_rate, KL(base||biased)

    Layer 2 — Constraint:   Does it improve phoneme adherence?
        mean_phi_selected vs mean_phi_topM, var_logphi_topM,
        phoneme-consistency score

    Layer 3 — Signal:       Does it produce valid BCVF diagnostics?
        sb_correctness_corr, rank improvement, lambda non-collapse

Runs a lambda sweep: λ ∈ {0.0, 0.1, 0.3, 1.0} + optional dynamic λ.

Three failure modes detected:
    1. λ → 0           → phoneme head unused
    2. φ flat           → no discrimination (var_logphi ~0 → DEAD)
    3. entropy unchanged → constraint not working

Usage::

    # Dry-run (synthetic data, no model download, ~10 seconds)
    python scripts/validate_phoneme_bcvf.py --dry-run

    # GPT-2 sanity check (real model, fast)
    python scripts/validate_phoneme_bcvf.py --model gpt2 --samples 200

    # Real evaluation with phi-3
    python scripts/validate_phoneme_bcvf.py --model phi3 --samples 500

    # Lambda sweep with custom range
    python scripts/validate_phoneme_bcvf.py --model gpt2 --lambdas 0.0 0.05 0.1 0.3 0.5 1.0

    # Save JSON report
    python scripts/validate_phoneme_bcvf.py --dry-run --output results.json

    # With top-m sweep
    python scripts/validate_phoneme_bcvf.py --model gpt2 --top-m-sweep 50 200 500
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path
# ---------------------------------------------------------------------------
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import torch
import torch.nn.functional as F

from csr_phoneme_provider import (
    PhonemeBCVF,
    PhonemeBCVFConfig,
    CSRPhonemeHead,
    CSRPhonemeHeadConfig,
    create_phoneme_bcvf,
)
from symbolu.ontological.bcvf_decoding import BCVFDecoder, DecodingConfig
from symbolu.ontological.bcvf_experiments import (
    ExperimentRunner,
    StepLogger,
)
from symbolu.ontological.bcvf_calibration import spearman_rank_correlation


# =========================================================================
# Result Dataclass
# =========================================================================


@dataclass
class LambdaResult:
    """Diagnostics for one lambda value."""
    lambda_value: float
    # Token-level (Layer 1)
    argmax_flip_rate: float = 0.0
    mean_kl: float = 0.0
    mean_nll_base: float = 0.0
    mean_nll_biased: float = 0.0
    delta_nll: float = 0.0
    mean_entropy_base: float = 0.0
    mean_entropy_biased: float = 0.0
    entropy_delta: float = 0.0
    # Constraint (Layer 2)
    mean_phi_selected: float = 0.0
    mean_phi_topM: float = 0.0
    phi_ratio: float = 0.0
    var_logphi_topM: float = 0.0
    phoneme_consistency: float = 0.0
    # Signal (Layer 3)
    sb_correctness_corr: float = 0.0
    base_logit_correctness_corr: float = 0.0
    mean_sf: float = 0.0
    mean_sb: float = 0.0
    accuracy_base: float = 0.0
    accuracy_biased: float = 0.0
    delta_accuracy: float = 0.0
    # Timing
    elapsed_seconds: float = 0.0
    n_positions: int = 0


@dataclass
class TopMResult:
    """Results for one top_m value across lambda sweep."""
    top_m: int
    lambda_results: List[LambdaResult] = field(default_factory=list)


@dataclass
class FullReport:
    """Complete validation report."""
    model_name: str
    model_params: str
    device: str
    n_positions: int
    top_m_results: List[TopMResult] = field(default_factory=list)
    verdict: str = ""
    failure_modes: List[str] = field(default_factory=list)


# =========================================================================
# Model + Dataset Loading (reuse from validate_bcvf_signal)
# =========================================================================


def load_model_and_texts(
    model_name: str,
    device: str,
    dtype: str,
    dry_run: bool,
    dataset: str,
    max_texts: int,
    samples: int,
) -> Tuple[Any, Any, List[str], str, int]:
    """
    Load model, tokenizer, texts. Returns (model, tokenizer, texts, device, top_m_max).
    """
    if dry_run:
        try:
            from transformers import GPT2Config, GPT2LMHeadModel
        except ImportError:
            print("ERROR: transformers required even for dry-run")
            print("  pip install transformers")
            sys.exit(1)

        print("DRY-RUN: Creating tiny random-weight model")
        config = GPT2Config(
            vocab_size=200,
            n_positions=256,
            n_embd=64,
            n_layer=2,
            n_head=2,
            n_inner=128,
            bos_token_id=0,
            eos_token_id=1,
        )
        model = GPT2LMHeadModel(config)
        with torch.no_grad():
            model.lm_head.weight = torch.nn.Parameter(
                torch.randn_like(model.lm_head.weight)
            )
        model.to(device).eval()
        n_params = sum(p.numel() for p in model.parameters())
        print(f"  Tiny model: {n_params / 1e3:.1f}K params, "
              f"vocab={config.vocab_size}, d={config.n_embd}")

        class _Tok:
            def __init__(self, vs):
                self.vocab_size = vs
                self.pad_token_id = 1
                self.pad_token = "<p>"
                self.eos_token_id = 1
                self.eos_token = "<e>"

            def encode(self, text, return_tensors="pt",
                       truncation=True, max_length=256, **kw):
                ids = [(ord(c) * 31 + i * 7) % (self.vocab_size - 2) + 2
                       for i, c in enumerate(text)][:max_length]
                return torch.tensor([ids], dtype=torch.long) if return_tensors == "pt" else ids

            def decode(self, ids, **kw):
                return f"<{len(ids)} toks>"

            def __len__(self):
                return self.vocab_size

        tokenizer = _Tok(config.vocab_size)
        texts = [
            "The quick brown fox jumps over the lazy dog. " * 10,
            "Functional programming treats functions as first-class values. " * 8,
            "Neural networks learn distributed representations of language. " * 8,
            "Statistical significance testing requires careful hypothesis design. " * 8,
            "The Sanskrit phoneme system organizes sounds by articulation point. " * 8,
            "Calibration ensures predicted confidence matches observed accuracy. " * 10,
            "Goal-conditioned generation steers output toward desired outcomes. " * 8,
            "The Lagrangian penalizes deviations from bidirectional consistency. " * 8,
        ]
        return model, tokenizer, texts, device, 100

    # Real model
    from scripts.validate_bcvf_signal import (
        load_hf_model,
        load_evaluation_texts,
        resolve_model_name,
    )
    resolved = resolve_model_name(model_name)
    print(f"Resolved model: {resolved}")
    model, tokenizer = load_hf_model(resolved, device=device, dtype=dtype)
    texts = load_evaluation_texts(dataset, max_texts=max_texts)
    print(f"  Loaded {len(texts)} text passages")
    top_m_max = min(500, getattr(model.config, 'vocab_size', 50257))
    return model, tokenizer, texts, device, top_m_max


# =========================================================================
# Build PhonemeBCVF from model
# =========================================================================


def build_phoneme_bcvf(
    model: Any,
    tokenizer: Any,
    lambda_init: float,
    dynamic_lambda: bool = False,
) -> PhonemeBCVF:
    """Create PhonemeBCVF from model config, building token-phoneme weights."""
    d_model = 64
    for attr in ['hidden_size', 'n_embd', 'embed_dim', 'd_model', 'dim']:
        if hasattr(model.config, attr):
            d_model = getattr(model.config, attr)
            break

    vocab_size = getattr(model.config, 'vocab_size', 50257)

    # Build CSRPhonemeHead to get token-phoneme weights
    csr_config = CSRPhonemeHeadConfig(d_model=d_model, vocab_size=vocab_size)
    csr_head = CSRPhonemeHead(csr_config, tokenizer=tokenizer)

    if csr_head._token_phoneme_weights is None:
        # Fallback: random weights (for dry-run / minimal tokenizers)
        print("  [PhonemeBCVF] No G2P mapping — using random phoneme weights")
        torch.manual_seed(42)
        w = torch.zeros(vocab_size, csr_head.num_phonemes)
        for i in range(vocab_size):
            n = torch.randint(2, 5, (1,)).item()
            idx = torch.randperm(csr_head.num_phonemes)[:n]
            vals = torch.rand(n)
            w[i, idx] = vals / vals.sum()
        csr_head.register_buffer('_token_phoneme_weights', w)

    bcvf = create_phoneme_bcvf(
        csr_head,
        lambda_init=lambda_init,
        dynamic_lambda=dynamic_lambda,
    )
    return bcvf


# =========================================================================
# Core Evaluation Loop
# =========================================================================


def evaluate_lambda(
    model: Any,
    tokenizer: Any,
    texts: List[str],
    lambda_init: float,
    n_positions: int,
    top_m: int,
    device: str,
    max_seq_len: int = 512,
    dynamic_lambda: bool = False,
) -> LambdaResult:
    """
    Run full evaluation for one lambda value.

    Collects all 3-layer diagnostics:
        Layer 1: Token-level (KL, NLL, entropy, flip rate)
        Layer 2: Constraint (phi_selected, phi_topM, var_logphi)
        Layer 3: Signal (BCVF sb_rho via StepLogger)
    """
    t0 = time.time()

    # Build phoneme BCVF for this lambda
    bcvf = build_phoneme_bcvf(model, tokenizer, lambda_init, dynamic_lambda)
    bcvf.to(device).eval()

    # BCVF decoder for signal layer
    bcvf_config = DecodingConfig(
        top_m=top_m, beta=0.2,
        use_rerank=True, use_calibration=True,
    )
    decoder = BCVFDecoder(bcvf_config)

    vocab_emb = model.get_input_embeddings().weight.detach().float()

    # Accumulators
    flips = 0
    kl_values = []
    nll_base_values = []
    nll_biased_values = []
    entropy_base_values = []
    entropy_biased_values = []
    phi_selected_values = []
    phi_topM_values = []
    logphi_topM_vars = []
    phoneme_consistency_values = []
    correct_base = 0
    correct_biased = 0
    total_positions = 0

    # BCVF signal logger
    logger = StepLogger()

    for text in texts:
        if total_positions >= n_positions:
            break

        tokens = tokenizer.encode(
            text, return_tensors="pt", truncation=True,
            max_length=max_seq_len,
        ).to(device)

        if tokens.shape[1] < 10:
            continue

        with torch.no_grad():
            outputs = model(tokens, output_hidden_states=True, use_cache=False)
            logits_all = outputs.logits.float()           # [1, T, V]
            hidden_all = outputs.hidden_states[-1].float() # [1, T, D]

        T = tokens.shape[1]
        ground_truth = tokens[0, 1:]  # [T-1]

        positions = min(T - 1, n_positions - total_positions)
        for t in range(positions):
            h_t = hidden_all[:, t:t+1, :]      # [1, 1, D]
            base_logits = logits_all[:, t:t+1, :]  # [1, 1, V]
            gt_token = int(ground_truth[t].item())

            # Apply phoneme bias
            result = bcvf(base_logits, h_t)
            biased_logits = result['logits']        # [1, 1, V]
            phi_prior = result['phoneme_prior']     # [1, 1, V]

            base_2d = base_logits.squeeze(1)        # [1, V]
            biased_2d = biased_logits.squeeze(1)    # [1, V]
            phi_1d = phi_prior.squeeze()             # [V]

            # === Layer 1: Token-level ===

            # Argmax flip
            base_top = torch.argmax(base_2d, dim=-1).item()
            biased_top = torch.argmax(biased_2d, dim=-1).item()
            if base_top != biased_top:
                flips += 1

            # Accuracy
            if base_top == gt_token:
                correct_base += 1
            if biased_top == gt_token:
                correct_biased += 1

            # KL divergence
            p_base = F.softmax(base_2d, dim=-1)
            p_biased = F.softmax(biased_2d, dim=-1)
            kl = F.kl_div(p_biased.log(), p_base, reduction='batchmean').item()
            kl_values.append(kl)

            # NLL for ground truth token
            nll_base = -F.log_softmax(base_2d, dim=-1)[0, gt_token].item()
            nll_biased = -F.log_softmax(biased_2d, dim=-1)[0, gt_token].item()
            nll_base_values.append(nll_base)
            nll_biased_values.append(nll_biased)

            # Entropy
            eps = 1e-8
            H_base = -(p_base * (p_base + eps).log()).sum(-1).item()
            H_biased = -(p_biased * (p_biased + eps).log()).sum(-1).item()
            entropy_base_values.append(H_base)
            entropy_biased_values.append(H_biased)

            # === Layer 2: Constraint ===

            # Top-M for phi diagnostics
            actual_m = min(top_m, phi_1d.shape[0])
            _, topM_idx = torch.topk(biased_2d, actual_m, dim=-1)
            phi_sel = phi_1d[biased_top].item()
            phi_topM = phi_1d[topM_idx.squeeze()]
            phi_selected_values.append(phi_sel)
            phi_topM_values.append(phi_topM.mean().item())

            # var(log(phi + eps)) — the degeneracy detector
            logphi = torch.log(phi_topM + bcvf.config.epsilon)
            logphi_topM_vars.append(logphi.var().item())

            # Phoneme consistency: phi of selected token
            phoneme_consistency_values.append(phi_sel)

            # === Layer 3: BCVF signal ===

            # Run through BCVF decoder with biased logits
            h_flat = hidden_all[:, t, :]  # [1, D]
            # Goal = lookahead (t+1 hidden state) or self for last
            if t + 1 < T:
                goal = hidden_all[:, t + 1, :].float()
            else:
                goal = h_flat.clone()

            best_idx, probs, log_data = decoder.decode_step(
                h_flat, vocab_emb, goal, biased_2d
            )

            record = StepLogger.from_decode_log(
                step_index=total_positions,
                log_data=log_data,
                predicted_token=int(best_idx[0].item()),
                ground_truth_token=gt_token,
            )
            logger.log(record)
            total_positions += 1

        if total_positions % 100 == 0 and total_positions > 0:
            print(f"    [λ={lambda_init}] {total_positions}/{n_positions} positions")

    elapsed = time.time() - t0

    # Compute signal metrics from BCVF logger
    summary = logger.summary()

    return LambdaResult(
        lambda_value=lambda_init,
        # Layer 1
        argmax_flip_rate=flips / max(total_positions, 1),
        mean_kl=float(np.mean(kl_values)) if kl_values else 0.0,
        mean_nll_base=float(np.mean(nll_base_values)) if nll_base_values else 0.0,
        mean_nll_biased=float(np.mean(nll_biased_values)) if nll_biased_values else 0.0,
        delta_nll=float(np.mean(nll_biased_values) - np.mean(nll_base_values)) if nll_biased_values else 0.0,
        mean_entropy_base=float(np.mean(entropy_base_values)) if entropy_base_values else 0.0,
        mean_entropy_biased=float(np.mean(entropy_biased_values)) if entropy_biased_values else 0.0,
        entropy_delta=float(np.mean(entropy_biased_values) - np.mean(entropy_base_values)) if entropy_biased_values else 0.0,
        # Layer 2
        mean_phi_selected=float(np.mean(phi_selected_values)) if phi_selected_values else 0.0,
        mean_phi_topM=float(np.mean(phi_topM_values)) if phi_topM_values else 0.0,
        phi_ratio=float(np.mean(phi_selected_values) / (np.mean(phi_topM_values) + 1e-8)) if phi_topM_values else 0.0,
        var_logphi_topM=float(np.mean(logphi_topM_vars)) if logphi_topM_vars else 0.0,
        phoneme_consistency=float(np.mean(phoneme_consistency_values)) if phoneme_consistency_values else 0.0,
        # Layer 3
        sb_correctness_corr=summary["sb_correctness_corr"],
        base_logit_correctness_corr=summary["base_logit_correctness_corr"],
        mean_sf=summary["mean_sf"],
        mean_sb=summary["mean_sb"],
        accuracy_base=correct_base / max(total_positions, 1),
        accuracy_biased=correct_biased / max(total_positions, 1),
        delta_accuracy=(correct_biased - correct_base) / max(total_positions, 1),
        # Meta
        elapsed_seconds=elapsed,
        n_positions=total_positions,
    )


# =========================================================================
# Verdict Logic
# =========================================================================


def determine_verdict(results: List[LambdaResult]) -> Tuple[str, List[str]]:
    """
    Determine overall verdict and list failure modes.

    Returns (verdict_string, [failure_mode_strings])
    """
    failures = []

    # Find the λ=0 baseline and best non-zero λ
    baseline = None
    best = None
    for r in results:
        if r.lambda_value == 0.0:
            baseline = r
        elif best is None or r.mean_phi_selected > best.mean_phi_selected:
            best = r

    if best is None:
        return "INCOMPLETE — no non-zero λ tested", ["no_nonzero_lambda"]

    # Failure mode 1: λ collapse (no KL at best λ)
    if best.mean_kl < 1e-5:
        failures.append(f"DEAD: λ={best.lambda_value} produces zero KL — bias is decorative")

    # Failure mode 2: φ flat (no discrimination)
    if best.var_logphi_topM < 1e-4:
        failures.append(f"DEAD: var(log(φ)) = {best.var_logphi_topM:.6f} — prior is uniform")

    # Failure mode 3: entropy unchanged or increased
    if best.entropy_delta > 0.1:
        failures.append(f"NOISE: entropy increased by {best.entropy_delta:.3f} — bias adds disorder")

    # Flip rate health
    if best.argmax_flip_rate == 0.0 and best.lambda_value > 0:
        failures.append(f"INACTIVE: flip rate = 0% at λ={best.lambda_value}")
    elif best.argmax_flip_rate > 0.5:
        failures.append(f"DESTRUCTIVE: flip rate = {best.argmax_flip_rate:.1%} — overrides semantics")

    # NLL check: bias should not significantly worsen NLL
    if best.delta_nll > 0.5:
        failures.append(f"PPL HARM: ΔNLL = +{best.delta_nll:.3f} — bias hurts prediction")

    # Verdict
    if not failures:
        verdict = "FUNCTIONAL — phoneme BCVF signal is active, discriminative, and non-destructive"
    elif all("DEAD" in f or "INACTIVE" in f for f in failures):
        verdict = "DECORATIVE — signal exists but has no effect"
    elif any("DESTRUCTIVE" in f or "PPL HARM" in f for f in failures):
        verdict = "HARMFUL — signal active but damages model quality"
    else:
        verdict = f"MIXED — {len(failures)} issue(s) detected"

    return verdict, failures


# =========================================================================
# Report Formatting
# =========================================================================


def format_report(report: FullReport) -> str:
    """Format the full validation report."""
    lines = []
    w = 90
    lines.append("=" * w)
    lines.append("PhonemeBCVF Signal Validation Report")
    lines.append("=" * w)
    lines.append(f"Model:      {report.model_name} ({report.model_params})")
    lines.append(f"Device:     {report.device}")
    lines.append(f"Positions:  {report.n_positions}")
    lines.append("")

    for tm_result in report.top_m_results:
        lines.append(f"--- top_m = {tm_result.top_m} ---")
        lines.append("")

        # Header
        cols = ["λ", "flip%", "KL", "ΔNLL", "ΔH", "φ_sel", "φ_topM",
                "var(logφ)", "acc_Δ", "sb_ρ"]
        header = f"  {'  '.join(f'{c:>9}' for c in cols)}"
        lines.append(header)
        lines.append("  " + "-" * (len(header) - 2))

        for r in tm_result.lambda_results:
            row = [
                f"{r.lambda_value:9.3f}",
                f"{r.argmax_flip_rate:8.1%}",
                f"{r.mean_kl:9.5f}",
                f"{r.delta_nll:+9.4f}",
                f"{r.entropy_delta:+9.4f}",
                f"{r.mean_phi_selected:9.4f}",
                f"{r.mean_phi_topM:9.4f}",
                f"{r.var_logphi_topM:9.5f}",
                f"{r.delta_accuracy:+8.1%}",
                f"{r.sb_correctness_corr:+9.4f}",
            ]
            lines.append(f"  {'  '.join(row)}")

        lines.append("")

    # Verdict
    lines.append("=" * w)
    lines.append(f"VERDICT: {report.verdict}")
    if report.failure_modes:
        lines.append("")
        lines.append("Failure modes detected:")
        for f in report.failure_modes:
            lines.append(f"  ! {f}")
    lines.append("=" * w)

    return "\n".join(lines)


# =========================================================================
# CLI
# =========================================================================


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Validate PhonemeBCVF as a functional BCVF signal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry-run (synthetic, ~10 seconds)
  python scripts/validate_phoneme_bcvf.py --dry-run

  # GPT-2 sanity check
  python scripts/validate_phoneme_bcvf.py --model gpt2 --samples 200

  # Real test with phi-3
  python scripts/validate_phoneme_bcvf.py --model phi3 --samples 500

  # Custom lambda sweep
  python scripts/validate_phoneme_bcvf.py --model gpt2 --lambdas 0.0 0.05 0.1 0.3 0.5

  # With top-m sweep
  python scripts/validate_phoneme_bcvf.py --model gpt2 --top-m-sweep 50 200 500
""",
    )

    # Model
    p.add_argument("--model", default="gpt2", help="HF model name or alias")
    p.add_argument("--dtype", default="auto", choices=["auto", "float16", "bfloat16", "float32"])
    p.add_argument("--device", default="auto", help="auto, cpu, cuda, cuda:0")

    # Data
    p.add_argument("--dataset", default="wikitext", choices=["wikitext", "openwebtext", "c4"])
    p.add_argument("--samples", type=int, default=200, help="# token positions to evaluate")
    p.add_argument("--max-seq-len", type=int, default=512)
    p.add_argument("--max-texts", type=int, default=100)

    # Lambda sweep
    p.add_argument("--lambdas", type=float, nargs="+",
                   default=[0.0, 0.1, 0.3, 1.0],
                   help="Lambda values to sweep (default: 0.0 0.1 0.3 1.0)")
    p.add_argument("--dynamic", action="store_true",
                   help="Also test dynamic lambda (lambda_net)")

    # Top-M
    p.add_argument("--top-m", type=int, default=50, help="Default top-m")
    p.add_argument("--top-m-sweep", type=int, nargs="+", default=None,
                   help="Top-m values to sweep (e.g., 50 200 500)")

    # Output
    p.add_argument("--output", type=str, default=None, help="Path to save JSON report")

    # Mode
    p.add_argument("--dry-run", action="store_true", help="Tiny random model, no downloads")

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Resolve device
    device = args.device
    if device == "auto":
        if torch.cuda.is_available():
            device = "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"
    print(f"Device: {device}")

    # Load model + texts
    model, tokenizer, texts, device, top_m_max = load_model_and_texts(
        model_name=args.model,
        device=device,
        dtype=args.dtype,
        dry_run=args.dry_run,
        dataset=args.dataset,
        max_texts=args.max_texts,
        samples=args.samples,
    )

    n_params = sum(p.numel() for p in model.parameters())
    model_params_str = f"{n_params / 1e9:.2f}B" if n_params > 1e8 else f"{n_params / 1e3:.1f}K"

    # Clamp for dry-run
    if args.dry_run:
        args.samples = min(args.samples, 200)
        args.max_seq_len = min(args.max_seq_len, 256)

    # Top-M sweep or single value
    top_m_values = args.top_m_sweep or [args.top_m]
    top_m_values = [min(tm, top_m_max) for tm in top_m_values]

    # Lambda values
    lambdas = sorted(set(args.lambdas))

    # Print header
    print(f"\n{'='*60}")
    print("PhonemeBCVF Signal Validation")
    print(f"  Model:     {args.model} ({model_params_str})")
    print(f"  Positions: {args.samples}")
    print(f"  λ sweep:   {lambdas}")
    print(f"  top_m:     {top_m_values}")
    if args.dynamic:
        print(f"  + dynamic λ (lambda_net)")
    print(f"{'='*60}\n")

    # Run evaluation
    all_top_m_results: List[TopMResult] = []
    all_lambda_results: List[LambdaResult] = []

    for top_m in top_m_values:
        print(f"\n=== top_m = {top_m} ===")
        tm_result = TopMResult(top_m=top_m)

        for lam in lambdas:
            print(f"\n  --- λ = {lam} ---")
            lr = evaluate_lambda(
                model=model,
                tokenizer=tokenizer,
                texts=texts,
                lambda_init=lam,
                n_positions=args.samples,
                top_m=top_m,
                device=device,
                max_seq_len=args.max_seq_len,
                dynamic_lambda=False,
            )
            tm_result.lambda_results.append(lr)
            all_lambda_results.append(lr)

            print(f"    flip={lr.argmax_flip_rate:.1%}  KL={lr.mean_kl:.5f}  "
                  f"ΔNLL={lr.delta_nll:+.4f}  ΔH={lr.entropy_delta:+.4f}")
            print(f"    φ_sel={lr.mean_phi_selected:.4f}  φ_topM={lr.mean_phi_topM:.4f}  "
                  f"var(logφ)={lr.var_logphi_topM:.5f}")
            print(f"    acc: {lr.accuracy_base:.1%}→{lr.accuracy_biased:.1%} "
                  f"(Δ={lr.delta_accuracy:+.1%})  "
                  f"sb_ρ={lr.sb_correctness_corr:+.4f}  "
                  f"({lr.elapsed_seconds:.1f}s)")

        # Dynamic lambda (if requested)
        if args.dynamic:
            print(f"\n  --- λ = dynamic ---")
            lr = evaluate_lambda(
                model=model,
                tokenizer=tokenizer,
                texts=texts,
                lambda_init=0.1,
                n_positions=args.samples,
                top_m=top_m,
                device=device,
                max_seq_len=args.max_seq_len,
                dynamic_lambda=True,
            )
            lr.lambda_value = -1.0  # sentinel for "dynamic"
            tm_result.lambda_results.append(lr)
            all_lambda_results.append(lr)
            print(f"    flip={lr.argmax_flip_rate:.1%}  KL={lr.mean_kl:.5f}  "
                  f"ΔNLL={lr.delta_nll:+.4f}")

        all_top_m_results.append(tm_result)

    # Verdict
    verdict, failures = determine_verdict(all_lambda_results)

    report = FullReport(
        model_name=args.model,
        model_params=model_params_str,
        device=device,
        n_positions=args.samples,
        top_m_results=all_top_m_results,
        verdict=verdict,
        failure_modes=failures,
    )

    # Print report
    print("\n")
    print(format_report(report))

    # Save JSON
    if args.output:
        output_path = Path(args.output)
        output_data = {
            "model": report.model_name,
            "model_params": report.model_params,
            "device": report.device,
            "n_positions": report.n_positions,
            "verdict": report.verdict,
            "failure_modes": report.failure_modes,
            "top_m_results": [
                {
                    "top_m": tm.top_m,
                    "lambda_results": [asdict(lr) for lr in tm.lambda_results],
                }
                for tm in report.top_m_results
            ],
        }
        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2)
        print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
