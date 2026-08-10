#!/usr/bin/env python3
"""
Stability and Orthogonality Verification — Appendix F Stage 6
==============================================================

Ensures control-plane signals do not destabilize generation and
verifies architectural invariants under stress.

Five verification tests:
  1. Phase/Control Plane Orthogonality (F.8.2)
  2. Logit Stability Under Modulation (F.8.3)
  3. Entropy Monitoring — Collapse Detection (F.8.4)
  4. Long-Sequence Stability (F.8.5)
  5. Auxiliary Module Kill Switch (F.8.6)

Reference: Project_documentation/repository/docs/design/CONSCIOUS_GENERATION_DESIGN.md, Appendix F §F.8

Author: Sovereign-1 Training Initiative
Date: March 2026
Phase: Appendix F Stage 6 — Stability and Orthogonality Verification
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
import math


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class StabilityConfig:
    """Configuration for stability verification tests.

    Attributes:
        phase_control_corr_threshold: Max |correlation| between phase and
            control planes (F.8.2). Default 0.3.
        modulation_ratio_max: Max modulation magnitude as fraction of
            logit std (F.8.3). Default 0.1.
        entropy_min: Minimum acceptable entropy (F.8.4). Default 1.0.
        entropy_max: Maximum acceptable entropy (F.8.4). Default 12.0.
        entropy_std_max: Maximum entropy std over sequence (F.8.4). Default 2.0.
        repetition_ngram_size: N-gram size for repetition detection (F.8.5).
            Default 4.
        repetition_rate_max: Maximum allowed repetition rate (F.8.5). Default 0.05.
        oscillation_window: Window for detecting A-B-A-B patterns (F.8.5).
            Default 8.
        coherence_min: Minimum C_total at any point (F.8.5). Default 0.3.
        norm_growth_max: Maximum hidden state norm growth factor (F.8.5).
            Default 10.0.
        bhava_slice: Slice for Bhava (phase plane) in ontological state.
        control_slice: Slice for Control plane (Kosha+Vritti+Guna).
    """
    phase_control_corr_threshold: float = 0.3
    modulation_ratio_max: float = 0.1
    entropy_min: float = 1.0
    entropy_max: float = 12.0
    entropy_std_max: float = 2.0
    repetition_ngram_size: int = 4
    repetition_rate_max: float = 0.05
    oscillation_window: int = 8
    coherence_min: float = 0.3
    norm_growth_max: float = 10.0
    bhava_slice: Tuple[int, int] = (0, 12)
    control_slice: Tuple[int, int] = (12, 28)


# =============================================================================
# TEST 1 — PHASE/CONTROL PLANE ORTHOGONALITY (F.8.2)
# =============================================================================

class PhaseControlOrthogonalityChecker:
    """Verifies that Bhava (12D phase plane) remains orthogonal to
    Control (16D Koshas/Vrittis/Gunas) in attention computation.

    The V11.0.0 contract requires these planes to be independent.
    Correlation above the threshold indicates information leakage
    between phase rotation and control signals.

    Args:
        config: StabilityConfig with threshold settings.
    """

    def __init__(self, config: StabilityConfig = None):
        self.config = config or StabilityConfig()

    def check(
        self,
        ontological_state: torch.Tensor,
    ) -> Dict[str, Any]:
        """Check phase/control orthogonality.

        Args:
            ontological_state: Ontological state tensor with shape
                (..., state_dim) where state_dim >= 28. Contains
                Bhava[0:12] and Control[12:28].

        Returns:
            Dict with 'correlation', 'passed', 'threshold'.
        """
        b_start, b_end = self.config.bhava_slice
        c_start, c_end = self.config.control_slice

        bhava = ontological_state[..., b_start:b_end].flatten().float()
        control = ontological_state[..., c_start:c_end].flatten().float()

        corr = self._pearson_correlation(bhava, control)

        return {
            "correlation": corr,
            "abs_correlation": abs(corr),
            "passed": abs(corr) < self.config.phase_control_corr_threshold,
            "threshold": self.config.phase_control_corr_threshold,
        }

    def check_batch(
        self,
        ontological_states: List[torch.Tensor],
    ) -> Dict[str, Any]:
        """Check orthogonality across a batch of inputs.

        Args:
            ontological_states: List of ontological state tensors.

        Returns:
            Dict with per-sample results and aggregate pass/fail.
        """
        results = [self.check(state) for state in ontological_states]
        all_passed = all(r["passed"] for r in results)
        max_corr = max(r["abs_correlation"] for r in results)

        return {
            "per_sample": results,
            "all_passed": all_passed,
            "max_abs_correlation": max_corr,
            "num_samples": len(results),
            "num_failed": sum(1 for r in results if not r["passed"]),
        }

    @staticmethod
    def _pearson_correlation(x: torch.Tensor, y: torch.Tensor) -> float:
        """Compute Pearson correlation between flattened tensors.

        Handles the case where vectors have different lengths by
        truncating to the shorter length.
        """
        min_len = min(len(x), len(y))
        x = x[:min_len]
        y = y[:min_len]

        x_centered = x - x.mean()
        y_centered = y - y.mean()

        num = (x_centered * y_centered).sum()
        denom = torch.sqrt((x_centered ** 2).sum() * (y_centered ** 2).sum())

        if denom < 1e-8:
            return 0.0

        return (num / denom).item()


# =============================================================================
# TEST 2 — LOGIT STABILITY UNDER MODULATION (F.8.3)
# =============================================================================

class ModulationStabilityChecker:
    """Verifies that auxiliary modulation stays within safety bounds.

    Modulation must remain bounded relative to base logits:
        max(|mod|) ≤ modulation_ratio_max × std(base_logits)

    Args:
        config: StabilityConfig with modulation bounds.
    """

    def __init__(self, config: StabilityConfig = None):
        self.config = config or StabilityConfig()

    def check(
        self,
        base_logits: torch.Tensor,
        modulated_logits: torch.Tensor,
    ) -> Dict[str, Any]:
        """Check modulation stability.

        Args:
            base_logits: Original logits (..., vocab_size).
            modulated_logits: Logits after CG modulation (..., vocab_size).

        Returns:
            Dict with 'max_ratio', 'mean_ratio', 'passed', details.
        """
        delta = (modulated_logits - base_logits).abs()
        logit_std = base_logits.std(dim=-1, keepdim=True)

        # Ratio of modulation to logit std
        ratio = delta / (logit_std + 1e-8)
        max_ratio = ratio.max().item()
        mean_ratio = ratio.mean().item()

        return {
            "max_ratio": max_ratio,
            "mean_ratio": mean_ratio,
            "max_delta": delta.max().item(),
            "logit_std_mean": logit_std.mean().item(),
            "passed": max_ratio <= self.config.modulation_ratio_max + 1e-6,
            "threshold": self.config.modulation_ratio_max,
        }

    def clamp_modulation(
        self,
        base_logits: torch.Tensor,
        modulated_logits: torch.Tensor,
    ) -> torch.Tensor:
        """Clamp modulation to stay within safety bounds.

        Enforces the invariant by clamping delta to
        ±(modulation_ratio_max × std(base_logits)).

        Args:
            base_logits: Original logits.
            modulated_logits: Logits after CG modulation.

        Returns:
            Clamped modulated logits.
        """
        delta = modulated_logits - base_logits
        logit_std = base_logits.std(dim=-1, keepdim=True)
        max_delta = self.config.modulation_ratio_max * (logit_std + 1e-8)

        clamped_delta = torch.clamp(delta, -max_delta, max_delta)
        return base_logits + clamped_delta


# =============================================================================
# TEST 3 — ENTROPY MONITORING (F.8.4)
# =============================================================================

class EntropyMonitor:
    """Monitors generation entropy for collapse/explosion detection.

    Healthy range: entropy_min < H(logits) < entropy_max
    Stability: std(H) < entropy_std_max over the sequence.

    Collapse (H → 0) indicates deterministic repetition.
    Explosion (H → max) indicates random noise.

    Args:
        config: StabilityConfig with entropy bounds.
    """

    def __init__(self, config: StabilityConfig = None):
        self.config = config or StabilityConfig()

    def compute_entropy(self, logits: torch.Tensor) -> torch.Tensor:
        """Compute entropy of logit distributions.

        Args:
            logits: Logit tensor (..., vocab_size).

        Returns:
            Entropy values (...,) in nats.
        """
        probs = F.softmax(logits, dim=-1)
        log_probs = F.log_softmax(logits, dim=-1)
        entropy = -(probs * log_probs).sum(dim=-1)
        return entropy

    def check_sequence(
        self,
        logits_sequence: torch.Tensor,
    ) -> Dict[str, Any]:
        """Check entropy stability over a sequence of logits.

        Args:
            logits_sequence: (seq_len, vocab_size) or (batch, seq_len, vocab_size).

        Returns:
            Dict with entropy stats and pass/fail status.
        """
        entropies = self.compute_entropy(logits_sequence)

        # Flatten batch dimension if present
        if entropies.dim() > 1:
            entropies = entropies.flatten()

        min_h = entropies.min().item()
        max_h = entropies.max().item()
        mean_h = entropies.mean().item()
        std_h = entropies.std().item() if len(entropies) > 1 else 0.0

        no_collapse = min_h > self.config.entropy_min
        no_explosion = max_h < self.config.entropy_max
        stable = std_h < self.config.entropy_std_max

        return {
            "min_entropy": min_h,
            "max_entropy": max_h,
            "mean_entropy": mean_h,
            "std_entropy": std_h,
            "no_collapse": no_collapse,
            "no_explosion": no_explosion,
            "stable": stable,
            "passed": no_collapse and no_explosion and stable,
            "entropies": entropies.detach(),
        }

    def check_monotonic_decrease(
        self,
        entropies: torch.Tensor,
        window: int = 50,
    ) -> Dict[str, Any]:
        """Detect monotonic entropy decrease (degeneration signal).

        Checks if entropy is monotonically decreasing over sliding windows.

        Args:
            entropies: 1D tensor of entropy values over sequence.
            window: Window size for checking monotonic decrease.

        Returns:
            Dict with 'monotonic_decrease_detected', 'longest_decrease_run'.
        """
        if len(entropies) < window:
            return {
                "monotonic_decrease_detected": False,
                "longest_decrease_run": 0,
            }

        diffs = entropies[1:] - entropies[:-1]
        # Count longest run of consecutive decreases
        current_run = 0
        longest_run = 0
        for d in diffs:
            if d < 0:
                current_run += 1
                longest_run = max(longest_run, current_run)
            else:
                current_run = 0

        return {
            "monotonic_decrease_detected": longest_run >= window,
            "longest_decrease_run": longest_run,
        }


# =============================================================================
# TEST 4 — LONG-SEQUENCE STABILITY (F.8.5)
# =============================================================================

class LongSequenceAnalyzer:
    """Analyzes long-sequence generation for stability issues.

    Checks for:
    - Repetition rate (n-gram)
    - Token oscillation (A-B-A-B patterns)
    - Coherence maintenance
    - Hidden state norm growth

    Args:
        config: StabilityConfig with thresholds.
    """

    def __init__(self, config: StabilityConfig = None):
        self.config = config or StabilityConfig()

    def check_repetition(
        self,
        token_ids: torch.Tensor,
    ) -> Dict[str, Any]:
        """Check n-gram repetition rate.

        Args:
            token_ids: 1D tensor of generated token ids.

        Returns:
            Dict with 'repetition_rate', 'passed', unique/total ngram counts.
        """
        n = self.config.repetition_ngram_size
        ids = token_ids.tolist() if isinstance(token_ids, torch.Tensor) else token_ids

        if len(ids) < n:
            return {
                "repetition_rate": 0.0,
                "passed": True,
                "total_ngrams": 0,
                "unique_ngrams": 0,
            }

        ngrams = []
        for i in range(len(ids) - n + 1):
            ngrams.append(tuple(ids[i:i + n]))

        total = len(ngrams)
        unique = len(set(ngrams))
        repetition_rate = 1.0 - (unique / total) if total > 0 else 0.0

        return {
            "repetition_rate": repetition_rate,
            "passed": repetition_rate < self.config.repetition_rate_max,
            "total_ngrams": total,
            "unique_ngrams": unique,
            "threshold": self.config.repetition_rate_max,
        }

    def check_oscillation(
        self,
        token_ids: torch.Tensor,
    ) -> Dict[str, Any]:
        """Detect A-B-A-B oscillation patterns.

        Looks for alternating pairs within a sliding window.

        Args:
            token_ids: 1D tensor of generated token ids.

        Returns:
            Dict with 'oscillation_detected', 'max_oscillation_length'.
        """
        ids = token_ids.tolist() if isinstance(token_ids, torch.Tensor) else token_ids
        window = self.config.oscillation_window

        if len(ids) < 4:
            return {
                "oscillation_detected": False,
                "max_oscillation_length": 0,
            }

        max_osc = 0
        for i in range(len(ids) - 3):
            # Check if alternating: A B A B ...
            osc_len = 2
            a, b = ids[i], ids[i + 1]
            if a == b:
                continue
            j = i + 2
            while j < len(ids):
                expected = a if (j - i) % 2 == 0 else b
                if ids[j] == expected:
                    osc_len += 1
                    j += 1
                else:
                    break
            max_osc = max(max_osc, osc_len)

        return {
            "oscillation_detected": max_osc >= window,
            "max_oscillation_length": max_osc,
            "threshold": window,
        }

    def check_norm_growth(
        self,
        hidden_states: torch.Tensor,
    ) -> Dict[str, Any]:
        """Check for unbounded hidden state norm growth.

        Args:
            hidden_states: (seq_len, hidden_dim) or (batch, seq_len, hidden_dim).

        Returns:
            Dict with 'growth_factor', 'passed', norm stats.
        """
        if hidden_states.dim() == 3:
            # Average over batch
            norms = hidden_states.norm(dim=-1).mean(dim=0)
        else:
            norms = hidden_states.norm(dim=-1)

        if len(norms) < 2:
            return {
                "growth_factor": 1.0,
                "passed": True,
                "initial_norm": norms[0].item() if len(norms) > 0 else 0.0,
                "final_norm": norms[-1].item() if len(norms) > 0 else 0.0,
            }

        initial_norm = norms[:10].mean().item()  # Average first 10
        final_norm = norms[-10:].mean().item()  # Average last 10

        if initial_norm < 1e-8:
            growth_factor = 0.0
        else:
            growth_factor = final_norm / initial_norm

        return {
            "growth_factor": growth_factor,
            "passed": growth_factor <= self.config.norm_growth_max,
            "initial_norm": initial_norm,
            "final_norm": final_norm,
            "max_norm": norms.max().item(),
            "threshold": self.config.norm_growth_max,
        }

    def check_coherence(
        self,
        coherence_scores: torch.Tensor,
    ) -> Dict[str, Any]:
        """Check coherence stays above minimum.

        Args:
            coherence_scores: 1D tensor of C_total values over sequence.

        Returns:
            Dict with 'min_coherence', 'passed', stats.
        """
        min_c = coherence_scores.min().item()
        mean_c = coherence_scores.mean().item()

        return {
            "min_coherence": min_c,
            "mean_coherence": mean_c,
            "passed": min_c > self.config.coherence_min,
            "threshold": self.config.coherence_min,
        }

    def full_analysis(
        self,
        token_ids: torch.Tensor,
        hidden_states: Optional[torch.Tensor] = None,
        coherence_scores: Optional[torch.Tensor] = None,
    ) -> Dict[str, Any]:
        """Run all long-sequence stability checks.

        Args:
            token_ids: Generated token ids.
            hidden_states: Optional hidden states for norm check.
            coherence_scores: Optional coherence scores for coherence check.

        Returns:
            Dict with all check results and overall pass/fail.
        """
        results = {}

        rep = self.check_repetition(token_ids)
        results["repetition"] = rep

        osc = self.check_oscillation(token_ids)
        results["oscillation"] = osc

        all_passed = rep["passed"] and not osc["oscillation_detected"]

        if hidden_states is not None:
            norm = self.check_norm_growth(hidden_states)
            results["norm_growth"] = norm
            all_passed = all_passed and norm["passed"]

        if coherence_scores is not None:
            coh = self.check_coherence(coherence_scores)
            results["coherence"] = coh
            all_passed = all_passed and coh["passed"]

        results["all_passed"] = all_passed
        return results


# =============================================================================
# TEST 5 — AUXILIARY MODULE KILL SWITCH (F.8.6)
# =============================================================================

class KillSwitchVerifier:
    """Verifies that disabling all auxiliary CG modules produces
    identical output to the baseline model.

    The kill switch must ensure clean deactivation — no residual
    effects from CG modules when disabled.

    Args:
        atol: Absolute tolerance for output comparison.
        rtol: Relative tolerance for output comparison.
    """

    def __init__(self, atol: float = 1e-5, rtol: float = 1e-5):
        self.atol = atol
        self.rtol = rtol

    def check(
        self,
        baseline_output: torch.Tensor,
        killswitch_output: torch.Tensor,
    ) -> Dict[str, Any]:
        """Compare baseline output with kill-switch output.

        Args:
            baseline_output: Output from model without CG (reference).
            killswitch_output: Output from model with CG disabled via switch.

        Returns:
            Dict with 'passed', 'max_diff', 'mean_diff'.
        """
        diff = (baseline_output - killswitch_output).abs()
        max_diff = diff.max().item()
        mean_diff = diff.mean().item()

        passed = torch.allclose(
            baseline_output, killswitch_output,
            atol=self.atol, rtol=self.rtol,
        )

        return {
            "passed": passed,
            "max_diff": max_diff,
            "mean_diff": mean_diff,
            "atol": self.atol,
            "rtol": self.rtol,
        }

    def check_logits(
        self,
        baseline_logits: torch.Tensor,
        killswitch_logits: torch.Tensor,
    ) -> Dict[str, Any]:
        """Compare logit distributions after kill switch.

        Additionally checks that the argmax (predicted token) matches.

        Args:
            baseline_logits: Logits from baseline model.
            killswitch_logits: Logits from model with CG disabled.

        Returns:
            Dict with numerical and argmax comparison results.
        """
        base_result = self.check(baseline_logits, killswitch_logits)

        # Check argmax agreement
        base_preds = baseline_logits.argmax(dim=-1)
        ks_preds = killswitch_logits.argmax(dim=-1)
        argmax_match = (base_preds == ks_preds).float().mean().item()

        base_result["argmax_agreement"] = argmax_match
        base_result["argmax_perfect"] = argmax_match == 1.0

        return base_result


# =============================================================================
# COMBINED STABILITY VERIFIER (F.8)
# =============================================================================

class StabilityVerifier:
    """Orchestrates all five stability verification tests.

    Provides a single entry point for running the full stability
    verification suite defined in Appendix F §F.8.

    Args:
        config: StabilityConfig for all sub-checkers.
    """

    def __init__(self, config: StabilityConfig = None):
        self.config = config or StabilityConfig()
        self.orthogonality = PhaseControlOrthogonalityChecker(self.config)
        self.modulation = ModulationStabilityChecker(self.config)
        self.entropy = EntropyMonitor(self.config)
        self.long_sequence = LongSequenceAnalyzer(self.config)
        self.kill_switch = KillSwitchVerifier()

    def run_all(
        self,
        ontological_states: Optional[List[torch.Tensor]] = None,
        base_logits: Optional[torch.Tensor] = None,
        modulated_logits: Optional[torch.Tensor] = None,
        logits_sequence: Optional[torch.Tensor] = None,
        token_ids: Optional[torch.Tensor] = None,
        hidden_states: Optional[torch.Tensor] = None,
        coherence_scores: Optional[torch.Tensor] = None,
        baseline_output: Optional[torch.Tensor] = None,
        killswitch_output: Optional[torch.Tensor] = None,
    ) -> Dict[str, Any]:
        """Run all available stability tests.

        Each test is only run if its required inputs are provided.
        Missing inputs result in the test being skipped.

        Returns:
            Dict with results per test and overall summary.
        """
        results = {}
        tests_run = 0
        tests_passed = 0

        # Test 1: Phase/Control Orthogonality
        if ontological_states is not None:
            results["orthogonality"] = self.orthogonality.check_batch(
                ontological_states
            )
            tests_run += 1
            if results["orthogonality"]["all_passed"]:
                tests_passed += 1

        # Test 2: Modulation Stability
        if base_logits is not None and modulated_logits is not None:
            results["modulation"] = self.modulation.check(
                base_logits, modulated_logits
            )
            tests_run += 1
            if results["modulation"]["passed"]:
                tests_passed += 1

        # Test 3: Entropy Monitoring
        if logits_sequence is not None:
            results["entropy"] = self.entropy.check_sequence(logits_sequence)
            tests_run += 1
            if results["entropy"]["passed"]:
                tests_passed += 1

        # Test 4: Long-Sequence Stability
        if token_ids is not None:
            results["long_sequence"] = self.long_sequence.full_analysis(
                token_ids, hidden_states, coherence_scores
            )
            tests_run += 1
            if results["long_sequence"]["all_passed"]:
                tests_passed += 1

        # Test 5: Kill Switch
        if baseline_output is not None and killswitch_output is not None:
            results["kill_switch"] = self.kill_switch.check(
                baseline_output, killswitch_output
            )
            tests_run += 1
            if results["kill_switch"]["passed"]:
                tests_passed += 1

        results["summary"] = {
            "tests_run": tests_run,
            "tests_passed": tests_passed,
            "all_passed": tests_run > 0 and tests_passed == tests_run,
        }

        return results
