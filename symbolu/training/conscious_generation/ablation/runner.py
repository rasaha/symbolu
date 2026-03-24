"""
Unified Ablation Runner for Stage 9 — runs the 8-config ablation matrix.

Reference: CONSCIOUS_GENERATION_DESIGN.md, F.14.3

Usage:
    python -m symbolu.training.conscious_generation.ablation.runner \
        --checkpoint checkpoints_mistral_cg/best.pt \
        --dataset wikitext103 \
        --prompts prompts.txt
"""

from __future__ import annotations

import json
import os
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn as nn

from .config import AttentionAblationConfig
from .metrics import (
    AblationMetrics,
    compute_ablation_metrics,
    compute_attention_entropy,
    compute_token_change_rate,
    compute_hidden_state_perturbation,
    collect_gradient_norms,
)


# ── The 8-configuration ablation matrix per F.14.3 ──────────────────────

ABLATION_MATRIX: List[Tuple[str, AttentionAblationConfig]] = [
    ("Baseline",
     AttentionAblationConfig(use_phase_sync=True, use_vritti_modulation=True,
                             use_guna_bias=True, use_dual_channel_intent=False)),
    ("Phase OFF",
     AttentionAblationConfig(use_phase_sync=False, use_vritti_modulation=True,
                             use_guna_bias=True, use_dual_channel_intent=False)),
    ("Vritti OFF",
     AttentionAblationConfig(use_phase_sync=True, use_vritti_modulation=False,
                             use_guna_bias=True, use_dual_channel_intent=False)),
    ("Guna OFF",
     AttentionAblationConfig(use_phase_sync=True, use_vritti_modulation=True,
                             use_guna_bias=False, use_dual_channel_intent=False)),
    ("Phase+Vritti only",
     AttentionAblationConfig(use_phase_sync=True, use_vritti_modulation=True,
                             use_guna_bias=False, use_dual_channel_intent=False)),
    ("Phase+Guna only",
     AttentionAblationConfig(use_phase_sync=True, use_vritti_modulation=False,
                             use_guna_bias=True, use_dual_channel_intent=False)),
    ("Vritti+Guna only",
     AttentionAblationConfig(use_phase_sync=False, use_vritti_modulation=True,
                             use_guna_bias=True, use_dual_channel_intent=False)),
    ("All OFF",
     AttentionAblationConfig(use_phase_sync=False, use_vritti_modulation=False,
                             use_guna_bias=False, use_dual_channel_intent=False)),
]


@dataclass
class AblationResult:
    """Aggregated result from an ablation run."""
    config_name: str
    config: AttentionAblationConfig
    metrics: AblationMetrics
    cg_diagnostics: Optional[Dict[str, float]] = None

    def __post_init__(self):
        # Internal: hidden states for cross-config comparison (not serialized)
        self._hidden_states: Optional[torch.Tensor] = None


class AblationRunner:
    """
    Runs the Stage 9 ablation matrix on a trained model.

    Usage::

        runner = AblationRunner(model, eval_fn, generate_fn)
        results = runner.run_matrix(eval_dataloader)
        runner.print_report(results)
        runner.save_report(results, "ablation_results.json")
    """

    def __init__(
        self,
        model: nn.Module,
        eval_fn,
        generate_fn=None,
        device: torch.device = torch.device("cpu"),
    ):
        """
        Args:
            model: The trained model (must accept ablation_config).
            eval_fn: Callable(model, dataloader, device) -> (val_loss, attention_weights_list)
                     where attention_weights_list is optional (may be None).
            generate_fn: Optional callable(model, prompts, device, seed)
                         -> (token_ids [B, T], hidden_states [B, T, D]).
                         If None, token change rate and hidden perturbation are skipped.
            device: Torch device.
        """
        self.model = model
        self.eval_fn = eval_fn
        self.generate_fn = generate_fn
        self.device = device

    def _apply_config(self, config: AttentionAblationConfig) -> None:
        """Push ablation config to all modules that understand it."""
        if hasattr(self.model, "set_ablation_config"):
            self.model.set_ablation_config(config)
        else:
            # Walk sub-modules
            for module in self.model.modules():
                if hasattr(module, "ablation_config"):
                    module.ablation_config = config

    @torch.no_grad()
    def run_single(
        self,
        name: str,
        config: AttentionAblationConfig,
        dataloader,
        baseline_ppl: Optional[float] = None,
        baseline_tokens: Optional[torch.Tensor] = None,
        baseline_hidden: Optional[torch.Tensor] = None,
        prompts: Optional[List[str]] = None,
        seed: int = 42,
    ) -> AblationResult:
        """Run evaluation with a single ablation configuration."""
        self._apply_config(config)
        self.model.eval()

        # Evaluate validation loss
        eval_result = self.eval_fn(self.model, dataloader, self.device)
        if isinstance(eval_result, tuple):
            val_loss, eval_extra = eval_result
        else:
            val_loss, eval_extra = eval_result, None

        # Extract hidden states and CG diagnostics from eval_extra
        attn_weights = None
        ablated_hidden = None
        cg_diagnostics = None
        if isinstance(eval_extra, dict):
            # New format: eval_fn returns CG diagnostics dict
            cg_diagnostics = {k: v for k, v in eval_extra.items() if k != "hidden_states"}
            if "hidden_states" in eval_extra:
                ablated_hidden = eval_extra["hidden_states"]
        elif eval_extra is not None:
            # Legacy format: eval_fn returns attention weights tensor
            attn_weights = eval_extra

        # Generate tokens for change-rate comparison
        ablated_tokens = None
        if self.generate_fn is not None and prompts is not None:
            gen_result = self.generate_fn(self.model, prompts, self.device, seed)
            if isinstance(gen_result, tuple) and len(gen_result) == 2:
                ablated_tokens, gen_hidden = gen_result
                if ablated_hidden is None:
                    ablated_hidden = gen_hidden
            else:
                ablated_tokens = gen_result

        metrics = compute_ablation_metrics(
            val_loss=val_loss,
            baseline_ppl=baseline_ppl,
            attention_weights=attn_weights,
            tokens_baseline=baseline_tokens,
            tokens_ablated=ablated_tokens,
            h_baseline=baseline_hidden,
            h_ablated=ablated_hidden,
            config_label=name,
        )

        result = AblationResult(
            config_name=name, config=config, metrics=metrics,
            cg_diagnostics=cg_diagnostics,
        )
        result._hidden_states = ablated_hidden
        return result

    def run_matrix(
        self,
        dataloader,
        prompts: Optional[List[str]] = None,
        seed: int = 42,
        configs: Optional[List[Tuple[str, AttentionAblationConfig]]] = None,
    ) -> List[AblationResult]:
        """
        Run the full ablation matrix (or a custom subset).

        Returns list of AblationResult, one per configuration.
        """
        if configs is None:
            configs = ABLATION_MATRIX

        results: List[AblationResult] = []

        # Run baseline first to get reference values
        baseline_name, baseline_cfg = configs[0]
        print(f"\n{'='*60}")
        print(f"  Stage 9 Ablation Audit — {len(configs)} configurations")
        print(f"{'='*60}")

        # Baseline run
        print(f"\n  [1/{len(configs)}] {baseline_name} ...")
        baseline_result = self.run_single(
            baseline_name, baseline_cfg, dataloader,
            prompts=prompts, seed=seed,
        )
        results.append(baseline_result)
        baseline_ppl = baseline_result.metrics.ppl
        # Show CG diagnostics for baseline
        if baseline_result.cg_diagnostics:
            diag = baseline_result.cg_diagnostics
            print(f"    PPL = {baseline_ppl:.4f}  |  gate={diag.get('adapter_gate', 0):.4f}  "
                  f"adapter_norm={diag.get('adapter_output_norm', 0):.4f}  "
                  f"state_norm={diag.get('state_norm', 0):.4f}")
        else:
            print(f"    PPL = {baseline_ppl:.4f}")

        # Extract baseline hidden states from eval (for HiddenΔ comparison)
        baseline_tokens = None
        baseline_hidden = baseline_result._hidden_states

        # Also try generation-based comparison if available
        if self.generate_fn is not None and prompts is not None:
            self._apply_config(baseline_cfg)
            gen = self.generate_fn(self.model, prompts, self.device, seed)
            if isinstance(gen, tuple) and len(gen) == 2:
                baseline_tokens, baseline_hidden = gen
            else:
                baseline_tokens = gen

        # Run remaining configs
        for i, (name, cfg) in enumerate(configs[1:], start=2):
            print(f"\n  [{i}/{len(configs)}] {name} ...")
            result = self.run_single(
                name, cfg, dataloader,
                baseline_ppl=baseline_ppl,
                baseline_tokens=baseline_tokens,
                baseline_hidden=baseline_hidden,
                prompts=prompts, seed=seed,
            )
            results.append(result)
            diag_str = ""
            if result.cg_diagnostics:
                d = result.cg_diagnostics
                diag_str = (f"  |  gate={d.get('adapter_gate', 0):.4f}  "
                            f"adapter_norm={d.get('adapter_output_norm', 0):.4f}")
            print(f"    PPL = {result.metrics.ppl:.4f}  "
                  f"(ΔPPL: {result.metrics.delta_ppl_pct:+.2f}%)  "
                  f"HiddenΔ: {result.metrics.hidden_state_perturbation:.4f}{diag_str}")
            # Free hidden states to save memory (metrics already computed)
            result._hidden_states = None

        # Free baseline hidden states and restore config
        baseline_hidden = None
        results[0]._hidden_states = None
        self._apply_config(baseline_cfg)
        return results

    @staticmethod
    def print_report(results: List[AblationResult]) -> None:
        """Pretty-print the ablation report with decision recommendations."""
        print(f"\n{'='*70}")
        print("  STAGE 9 ABLATION REPORT")
        print(f"{'='*70}")

        baseline_ppl = results[0].metrics.ppl if results else 0

        # ── CG Health Check ──────────────────────────────────────────
        baseline_diag = results[0].cg_diagnostics if results and results[0].cg_diagnostics else {}
        if baseline_diag:
            print(f"\n  CG Health Check (Baseline):")
            gate = baseline_diag.get("adapter_gate", 0)
            adapter_norm = baseline_diag.get("adapter_output_norm", 0)
            state_norm = baseline_diag.get("state_norm", 0)
            delta_s = baseline_diag.get("delta_S_norm", 0)

            print(f"    Adapter gate:        {gate:.6f}"
                  f"{'  !! DEAD (gate ~ 0)' if gate < 0.01 else ''}"
                  f"{'  !! SATURATED (gate ~ 1)' if gate > 0.99 else ''}")
            print(f"    Adapter output norm: {adapter_norm:.4f}"
                  f"{'  !! DEAD (no adapter signal)' if adapter_norm < 1e-4 else ''}")
            print(f"    State norm:          {state_norm:.4f}"
                  f"{'  !! DEAD (state projector not producing signal)' if state_norm < 1e-4 else ''}")
            print(f"    Delta_S norm:        {delta_s:.6f}"
                  f"{'  !! DEAD (no state dynamics)' if delta_s < 1e-6 else ''}")

            # Overall CG verdict
            issues = []
            if gate < 0.01:
                issues.append("gate=0 (adapter fully suppressed)")
            if adapter_norm < 1e-4:
                issues.append("adapter output is zero")
            if state_norm < 1e-4:
                issues.append("state projector dead")
            if delta_s < 1e-6:
                issues.append("no state dynamics")

            if issues:
                print(f"\n    !! CG IS NOT MEANINGFULLY ACTIVE: {', '.join(issues)}")
                print(f"    This typically means the CG adapter hasn't been trained yet,")
                print(f"    or the state_projector was re-initialized (check checkpoint step).")
            else:
                all_off_result = next((r for r in results if r.config_name == "All OFF"), None)
                if all_off_result:
                    delta = all_off_result.metrics.delta_ppl_pct
                    if delta < -1.0:
                        print(f"\n    !! CG IS HURTING: All-OFF PPL is {abs(delta):.1f}% BETTER than baseline")
                        print(f"    The CG adapter is adding noise, not signal. Needs more training.")
                    elif abs(delta) < 0.5:
                        print(f"\n    CG MARGINAL: All-OFF within 0.5% of baseline — CG not yet contributing")
                    else:
                        print(f"\n    CG ACTIVE: All-OFF degrades PPL by {delta:+.1f}% — CG is contributing")

        # Table header
        print(f"\n  {'Configuration':<22} {'PPL':>8} {'ΔPPL%':>8} "
              f"{'HiddenΔ':>8} {'Gate':>8} {'AdptNorm':>8}")
        print(f"  {'-'*22} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")

        for r in results:
            m = r.metrics
            d = r.cg_diagnostics or {}
            gate_str = f"{d.get('adapter_gate', 0):>8.4f}" if d else f"{'n/a':>8}"
            norm_str = f"{d.get('adapter_output_norm', 0):>8.4f}" if d else f"{'n/a':>8}"
            print(f"  {r.config_name:<22} {m.ppl:>8.2f} {m.delta_ppl_pct:>+7.2f}% "
                  f"{m.hidden_state_perturbation:>8.4f} {gate_str} {norm_str}")

        # Decision recommendations (F.14.8)
        print(f"\n  {'─'*70}")
        print("  Decision Recommendations (per F.14.8):")
        print(f"  {'─'*70}")

        for r in results[1:]:
            m = r.metrics
            name = r.config_name

            if "Phase OFF" == name:
                verdict = "KEEP (core innovation)" if abs(m.delta_ppl_pct) >= 1.0 else "KEEP (core, regardless)"
            elif "Vritti OFF" == name:
                if m.token_change_rate >= 0.03 or abs(m.delta_ppl_pct) >= 1.0:
                    verdict = "KEEP"
                elif m.token_change_rate < 0.01:
                    verdict = "CONSIDER REMOVE (token change < 1%)"
                else:
                    verdict = "MARGINAL — check long-context"
            elif "Guna OFF" == name:
                if abs(m.delta_ppl_pct) >= 1.0:
                    verdict = "KEEP"
                elif abs(m.delta_ppl_pct) < 0.5:
                    verdict = "CONSIDER REMOVE (ΔPPL < 0.5%)"
                else:
                    verdict = "MARGINAL — check coherence"
            elif "All OFF" == name:
                verdict = f"Transformer baseline (Δ={m.delta_ppl_pct:+.2f}%)"
            else:
                verdict = "See pairwise analysis"

            print(f"  {name:<22} → {verdict}")

        # Redundancy check (F.14.8 interaction rule)
        ppl_map = {r.config_name: r.metrics.ppl for r in results}
        pv_only = ppl_map.get("Phase+Vritti only", 0)
        baseline = ppl_map.get("Baseline", 0)
        if pv_only > 0 and baseline > 0:
            ratio = abs(pv_only - baseline) / baseline * 100
            if ratio < 0.5:
                print(f"\n  ⚠  Guna may be REDUNDANT with Phase+Vritti "
                      f"(PPL diff = {ratio:.2f}%)")

    @staticmethod
    def save_report(results: List[AblationResult], path: str) -> None:
        """Save ablation results to JSON."""
        data = []
        for r in results:
            entry = {
                "config_name": r.config_name,
                "config": asdict(r.config),
                "metrics": asdict(r.metrics),
                "cg_diagnostics": r.cg_diagnostics,
            }
            data.append(entry)

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"\n  Ablation report saved to: {path}")
