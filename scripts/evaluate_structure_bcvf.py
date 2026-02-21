#!/usr/bin/env python3
"""
Evaluate Structure BCVF — Constraint Energy on Code Candidates
================================================================

Tests whether structure-level BCVF produces discriminative signal
that is non-redundant with logprob during code generation reranking.

The core question:

    Can cheap structural checks (AST, unbound vars, runtime smoke)
    reclaim oracle headroom that token-level BCVF cannot?

Diagnostic criteria (from the BCVF evolution framework):

    1. Discriminative: utility varies across candidates (not constant)
    2. Non-redundant: not rank-correlated with base logprob (ρ < 0.95)
    3. Aligned: positively correlated with correctness
    4. Actionable: changes rankings without destroying fluency

This script works with synthetic "code candidates" (no HumanEval download
needed) to validate the constraint energy pipeline end-to-end.

Usage::

    # Default — synthetic code candidates, all features
    python scripts/evaluate_structure_bcvf.py

    # With runtime smoke tests enabled
    python scripts/evaluate_structure_bcvf.py --use-runtime

    # Alpha sweep
    python scripts/evaluate_structure_bcvf.py --alphas 0.0 0.5 1.0 2.0

    # JSON output
    python scripts/evaluate_structure_bcvf.py --output structure_report.json

    # Verbose per-candidate diagnostics
    python scripts/evaluate_structure_bcvf.py --verbose
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Project root
# ---------------------------------------------------------------------------
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from symbolu.ontological.structure_bcvf import (
    ConstraintDiagnostics,
    MultiChannelBCVF,
    MultiChannelConfig,
    StructureBCVF,
    StructureConfig,
)

# =========================================================================
# Synthetic Test Problems
# =========================================================================

# Each problem has: prompt, K candidates (some correct, some broken),
# simulated logprobs, and ground-truth pass/fail labels.


@dataclass
class SyntheticProblem:
    """A synthetic code problem with candidates."""
    task_id: str
    prompt: str
    candidates: List[str]
    logprobs: List[float]
    labels: List[bool]       # True = correct, False = incorrect
    description: str = ""


def _synthetic_problems() -> List[SyntheticProblem]:
    """Generate synthetic code problems for testing."""
    problems = []

    # Problem 1: is_palindrome
    problems.append(SyntheticProblem(
        task_id="synth/0",
        prompt='def is_palindrome(s: str) -> bool:\n    """Check if s is a palindrome."""\n',
        candidates=[
            # Correct — clean
            '    return s == s[::-1]\n',
            # Correct — verbose
            '    cleaned = s.lower()\n    return cleaned == cleaned[::-1]\n',
            # Wrong — off-by-one, but syntactically valid
            '    return s == s[:-1]\n',
            # Wrong — unbound variable
            '    return text == text[::-1]\n',
            # Wrong — placeholder
            '    pass\n',
            # Wrong — syntax error (unclosed bracket)
            '    return s == s[::(-1\n',
        ],
        logprobs=[-5.2, -6.1, -5.5, -5.8, -3.0, -7.0],
        labels=[True, True, False, False, False, False],
        description="palindrome check",
    ))

    # Problem 2: factorial
    problems.append(SyntheticProblem(
        task_id="synth/1",
        prompt='def factorial(n: int) -> int:\n    """Return n factorial."""\n',
        candidates=[
            # Correct — recursive
            '    if n <= 1:\n        return 1\n    return n * factorial(n - 1)\n',
            # Correct — iterative
            '    result = 1\n    for i in range(2, n + 1):\n        result *= i\n    return result\n',
            # Wrong — missing return
            '    result = 1\n    for i in range(2, n + 1):\n        result *= i\n',
            # Wrong — uses undefined variable
            '    return math_factorial(n)\n',
            # Wrong — not implemented
            '    raise NotImplementedError\n',
        ],
        logprobs=[-4.5, -5.0, -4.8, -6.2, -2.5],
        labels=[True, True, False, False, False],
        description="factorial",
    ))

    # Problem 3: two_sum
    problems.append(SyntheticProblem(
        task_id="synth/2",
        prompt='def two_sum(nums: list, target: int) -> list:\n    """Return indices of two numbers that add up to target."""\n',
        candidates=[
            # Correct — hash map
            '    seen = {}\n    for i, n in enumerate(nums):\n        comp = target - n\n        if comp in seen:\n            return [seen[comp], i]\n        seen[n] = i\n    return []\n',
            # Correct — brute force
            '    for i in range(len(nums)):\n        for j in range(i + 1, len(nums)):\n            if nums[i] + nums[j] == target:\n                return [i, j]\n    return []\n',
            # Wrong — returns values not indices
            '    for i in range(len(nums)):\n        for j in range(i + 1, len(nums)):\n            if nums[i] + nums[j] == target:\n                return [nums[i], nums[j]]\n    return []\n',
            # Wrong — unbound variable + no return
            '    for pair in combinations(nums, 2):\n        if sum(pair) == target:\n            print(pair)\n',
            # Wrong — empty body
            '    ...\n',
        ],
        logprobs=[-8.5, -7.0, -7.2, -9.0, -2.0],
        labels=[True, True, False, False, False],
        description="two sum",
    ))

    # Problem 4: max_subarray (Kadane's)
    problems.append(SyntheticProblem(
        task_id="synth/3",
        prompt='def max_subarray(nums: list) -> int:\n    """Return the maximum sum of a contiguous subarray."""\n',
        candidates=[
            # Correct — Kadane's
            '    max_sum = current = nums[0]\n    for n in nums[1:]:\n        current = max(n, current + n)\n        max_sum = max(max_sum, current)\n    return max_sum\n',
            # Wrong — returns sum of all positives (not contiguous)
            '    return sum(n for n in nums if n > 0) or max(nums)\n',
            # Wrong — off by one, but parses
            '    max_sum = current = 0\n    for n in nums:\n        current += n\n        max_sum = max(max_sum, current)\n    return max_sum\n',
            # Wrong — uses undefined numpy
            '    return np.max(np.cumsum(nums) - np.minimum.accumulate(np.concatenate(([0], np.cumsum(nums)))))\n',
        ],
        logprobs=[-9.0, -6.5, -7.5, -8.0],
        labels=[True, False, False, False],
        description="max subarray",
    ))

    # Problem 5: flatten_list
    problems.append(SyntheticProblem(
        task_id="synth/4",
        prompt='def flatten(lst: list) -> list:\n    """Flatten a nested list into a single list."""\n',
        candidates=[
            # Correct — recursive
            '    result = []\n    for item in lst:\n        if isinstance(item, list):\n            result.extend(flatten(item))\n        else:\n            result.append(item)\n    return result\n',
            # Correct — itertools
            '    import itertools\n    flat = []\n    for item in lst:\n        if isinstance(item, list):\n            flat.extend(item)\n        else:\n            flat.append(item)\n    return flat\n',
            # Wrong — ignores all params
            '    return [1, 2, 3]\n',
        ],
        logprobs=[-7.0, -7.5, -3.0],
        labels=[True, True, False],
        description="flatten list",
    ))

    # Problem 6: binary search
    problems.append(SyntheticProblem(
        task_id="synth/5",
        prompt='def binary_search(arr: list, target: int) -> int:\n    """Return index of target in sorted arr, or -1 if not found."""\n',
        candidates=[
            # Correct
            '    lo, hi = 0, len(arr) - 1\n    while lo <= hi:\n        mid = (lo + hi) // 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            lo = mid + 1\n        else:\n            hi = mid - 1\n    return -1\n',
            # Wrong — infinite loop (missing update)
            '    lo, hi = 0, len(arr) - 1\n    while lo <= hi:\n        mid = (lo + hi) // 2\n        if arr[mid] == target:\n            return mid\n    return -1\n',
            # Wrong — uses undefined bisect_left
            '    idx = bisect_left(arr, target)\n    return idx if idx < len(arr) and arr[idx] == target else -1\n',
            # Wrong — linear search disguised
            '    for i, v in enumerate(arr):\n        if v == target:\n            return i\n    return -1\n',
        ],
        logprobs=[-8.0, -7.0, -6.0, -5.5],
        labels=[True, False, False, False],
        description="binary search",
    ))

    return problems


# =========================================================================
# Result Dataclasses
# =========================================================================


@dataclass
class AlphaResult:
    """Results for one alpha value."""
    alpha: float
    # Reranking
    rerank_rate: float = 0.0
    pass_at_1_base: float = 0.0
    pass_at_1_struct: float = 0.0
    delta_pass_at_1: float = 0.0
    oracle_pass_at_k: float = 0.0
    headroom_captured: float = 0.0   # (struct - base) / (oracle - base)
    # Signal quality
    utility_spread_mean: float = 0.0
    rank_correlation_mean: float = 0.0   # logprob vs structure rank
    # Win/loss
    wins: int = 0
    losses: int = 0
    ties: int = 0


@dataclass
class StructureReport:
    """Complete evaluation report."""
    n_problems: int = 0
    features_enabled: List[str] = field(default_factory=list)
    alpha_results: List[AlphaResult] = field(default_factory=list)
    per_problem_diagnostics: List[Dict[str, Any]] = field(default_factory=list)
    verdict: str = ""
    failure_modes: List[str] = field(default_factory=list)


# =========================================================================
# Evaluation
# =========================================================================


def evaluate_alpha(
    problems: List[SyntheticProblem],
    bcvf: StructureBCVF,
    alpha: float,
    verbose: bool = False,
) -> Tuple[AlphaResult, List[Dict[str, Any]]]:
    """Evaluate one alpha value across all problems."""
    bcvf.config.alpha = alpha

    base_correct = 0
    struct_correct = 0
    oracle_correct = 0
    reranks = 0
    wins = 0
    losses = 0
    ties = 0
    utility_spreads = []
    rank_correlations = []
    problem_diags = []

    for prob in problems:
        K = len(prob.candidates)

        # Base: pick by logprob
        base_idx = int(np.argmax(prob.logprobs))
        base_pass = prob.labels[base_idx]

        # Structure BCVF: rerank
        best_idx, scores, diagnostics = bcvf.rerank(
            prob.prompt, prob.candidates, prob.logprobs,
        )
        struct_pass = prob.labels[best_idx]

        # Oracle: any correct?
        oracle = any(prob.labels)

        if base_pass:
            base_correct += 1
        if struct_pass:
            struct_correct += 1
        if oracle:
            oracle_correct += 1

        changed = best_idx != base_idx
        if changed:
            reranks += 1

        if struct_pass and not base_pass:
            wins += 1
        elif not struct_pass and base_pass:
            losses += 1
        else:
            ties += 1

        # Utility spread
        utilities = [d.utility for d in diagnostics]
        spread = max(utilities) - min(utilities)
        utility_spreads.append(spread)

        # Rank correlation (logprob rank vs structure rank)
        if K > 2:
            lp_ranks = np.argsort(np.argsort(prob.logprobs)).astype(float)
            sc_ranks = np.argsort(np.argsort(scores)).astype(float)
            d = lp_ranks - sc_ranks
            rho = 1.0 - 6.0 * float(np.sum(d ** 2)) / (K * (K ** 2 - 1))
        elif K == 2:
            rho = 1.0 if np.argmax(prob.logprobs) == np.argmax(scores) else -1.0
        else:
            rho = 1.0
        rank_correlations.append(rho)

        # Diagnostics per problem
        diag_summary = bcvf.summary(diagnostics)
        diag_summary["task_id"] = prob.task_id
        diag_summary["description"] = prob.description
        diag_summary["base_idx"] = base_idx
        diag_summary["struct_idx"] = best_idx
        diag_summary["changed"] = changed
        diag_summary["base_pass"] = base_pass
        diag_summary["struct_pass"] = struct_pass
        diag_summary["oracle"] = oracle
        diag_summary["rank_correlation"] = rho
        problem_diags.append(diag_summary)

        if verbose:
            print(f"\n  [{prob.task_id}] {prob.description}")
            print(f"    Base: candidate {base_idx} ({'PASS' if base_pass else 'FAIL'})")
            print(f"    BCVF: candidate {best_idx} ({'PASS' if struct_pass else 'FAIL'})  "
                  f"{'CHANGED' if changed else 'same'}")
            print(f"    Utilities: {[f'{u:.2f}' for u in utilities]}")
            print(f"    Labels:    {prob.labels}")
            print(f"    Logprobs:  {[f'{lp:.1f}' for lp in prob.logprobs]}")
            print(f"    Scores:    {[f'{s:.2f}' for s in scores]}")
            if any(d.n_unbound > 0 for d in diagnostics):
                for i, d in enumerate(diagnostics):
                    if d.n_unbound > 0:
                        print(f"    Candidate {i}: unbound={d.unbound_vars}")

    n = len(problems)
    p1_base = base_correct / n
    p1_struct = struct_correct / n
    p1_oracle = oracle_correct / n

    headroom = (
        (p1_struct - p1_base) / (p1_oracle - p1_base)
        if p1_oracle > p1_base else 0.0
    )

    result = AlphaResult(
        alpha=alpha,
        rerank_rate=reranks / n,
        pass_at_1_base=p1_base,
        pass_at_1_struct=p1_struct,
        delta_pass_at_1=p1_struct - p1_base,
        oracle_pass_at_k=p1_oracle,
        headroom_captured=headroom,
        utility_spread_mean=float(np.mean(utility_spreads)),
        rank_correlation_mean=float(np.mean(rank_correlations)),
        wins=wins,
        losses=losses,
        ties=ties,
    )

    return result, problem_diags


# =========================================================================
# Verdict
# =========================================================================


def determine_verdict(results: List[AlphaResult]) -> Tuple[str, List[str]]:
    """Determine overall verdict."""
    failures = []

    # Find best positive alpha
    best = None
    for r in results:
        if r.alpha > 0:
            if best is None or r.delta_pass_at_1 > best.delta_pass_at_1:
                best = r

    if best is None:
        return "INCOMPLETE", ["no positive alpha tested"]

    # 1. Discriminative
    if best.utility_spread_mean < 0.05:
        failures.append(f"NOT DISCRIMINATIVE: utility spread = {best.utility_spread_mean:.3f}")

    # 2. Non-redundant
    if best.rank_correlation_mean > 0.95:
        failures.append(f"REDUNDANT: rank corr = {best.rank_correlation_mean:.3f} (too close to logprob)")

    # 3. Aligned
    if best.delta_pass_at_1 < 0:
        failures.append(f"ANTI-ALIGNED: Δpass@1 = {best.delta_pass_at_1:.3f}")

    # 4. Actionable
    if best.rerank_rate < 0.1:
        failures.append(f"NOT ACTIONABLE: rerank rate = {best.rerank_rate:.1%}")

    # Win/loss
    if best.losses > best.wins:
        failures.append(f"NET NEGATIVE: {best.losses} losses > {best.wins} wins")

    if not failures:
        verdict = (
            f"FUNCTIONAL — structure BCVF captures "
            f"{best.headroom_captured:.0%} of oracle headroom "
            f"(Δp@1 = {best.delta_pass_at_1:+.3f})"
        )
    elif any("ANTI-ALIGNED" in f or "NET NEGATIVE" in f for f in failures):
        verdict = "HARMFUL — structure BCVF reduces correctness"
    elif any("NOT DISCRIMINATIVE" in f for f in failures):
        verdict = "DECORATIVE — energies are uniform, no discrimination"
    else:
        verdict = f"MIXED — {len(failures)} issue(s)"

    return verdict, failures


# =========================================================================
# Report Formatting
# =========================================================================


def format_report(report: StructureReport) -> str:
    """Format human-readable report."""
    lines = []
    w = 90
    lines.append("=" * w)
    lines.append("Structure BCVF Evaluation — Constraint Energy on Code Candidates")
    lines.append("=" * w)
    lines.append(f"Problems:  {report.n_problems}")
    lines.append(f"Features:  {', '.join(report.features_enabled)}")
    lines.append("")

    lines.append("--- Alpha Sweep ---")
    cols = ["alpha", "rerank%", "p@1_base", "p@1_struct", "Δp@1",
            "oracle", "headroom", "spread", "rho", "W/L/T"]
    header = "  " + "  ".join(f"{c:>10}" for c in cols)
    lines.append(header)
    lines.append("  " + "-" * (len(header) - 2))

    for r in report.alpha_results:
        row = [
            f"{r.alpha:10.2f}",
            f"{r.rerank_rate:9.0%}",
            f"{r.pass_at_1_base:10.3f}",
            f"{r.pass_at_1_struct:10.3f}",
            f"{r.delta_pass_at_1:+10.3f}",
            f"{r.oracle_pass_at_k:10.3f}",
            f"{r.headroom_captured:9.0%}",
            f"{r.utility_spread_mean:10.3f}",
            f"{r.rank_correlation_mean:+10.3f}",
            f"{r.wins:>3}/{r.losses}/{r.ties}",
        ]
        lines.append("  " + "  ".join(row))
    lines.append("")

    # Per-problem diagnostics
    if report.per_problem_diagnostics:
        lines.append("--- Per-Problem Diagnostics (best alpha) ---")
        for diag in report.per_problem_diagnostics:
            tag = "WIN" if (diag["struct_pass"] and not diag["base_pass"]) else \
                  "LOSS" if (not diag["struct_pass"] and diag["base_pass"]) else \
                  "OK" if diag["struct_pass"] else "FAIL"
            lines.append(
                f"  [{diag['task_id']}] {diag['description']:<20} "
                f"base={diag['base_idx']} struct={diag['struct_idx']}  "
                f"{'CHANGED' if diag['changed'] else 'same':>7}  "
                f"{tag:>4}  "
                f"AST={diag['ast_pass_rate']:.0%}  "
                f"unbound={diag['mean_unbound']:.1f}  "
                f"spread={diag['utility_spread']:.2f}  "
                f"ρ={diag['rank_correlation']:+.2f}"
            )
        lines.append("")

    # Verdict
    lines.append("=" * w)
    lines.append(f"VERDICT: {report.verdict}")
    if report.failure_modes:
        lines.append("")
        for f in report.failure_modes:
            lines.append(f"  ! {f}")
    lines.append("=" * w)

    return "\n".join(lines)


# =========================================================================
# CLI
# =========================================================================


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Evaluate structure BCVF constraint energies on code candidates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/evaluate_structure_bcvf.py
  python scripts/evaluate_structure_bcvf.py --use-runtime --verbose
  python scripts/evaluate_structure_bcvf.py --alphas 0.0 0.5 1.0 2.0
  python scripts/evaluate_structure_bcvf.py --output structure_report.json
""",
    )

    p.add_argument("--alphas", type=float, nargs="+",
                   default=[0.0, 0.5, 1.0, 2.0, 5.0])
    p.add_argument("--use-runtime", action="store_true",
                   help="Enable runtime smoke tests (slow, uses exec)")
    p.add_argument("--output", type=str, default=None)
    p.add_argument("--verbose", action="store_true")

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    problems = _synthetic_problems()
    print(f"Loaded {len(problems)} synthetic problems")

    features = ["ast", "unbound", "return_check", "param_usage", "placeholder_check"]
    if args.use_runtime:
        features.append("runtime")

    config = StructureConfig(
        use_ast=True,
        use_unbound=True,
        use_runtime=args.use_runtime,
        use_return_check=True,
        use_param_usage=True,
        use_placeholder_check=True,
    )
    bcvf = StructureBCVF(config)

    print(f"Features: {', '.join(features)}")
    print(f"Alphas: {args.alphas}")
    print()

    alpha_results = []
    best_diags = None
    best_delta = -999

    for alpha in args.alphas:
        print(f"--- alpha = {alpha} ---")
        result, diags = evaluate_alpha(problems, bcvf, alpha, verbose=args.verbose)
        alpha_results.append(result)

        if result.delta_pass_at_1 > best_delta:
            best_delta = result.delta_pass_at_1
            best_diags = diags

        print(f"  rerank={result.rerank_rate:.0%}  "
              f"p@1: {result.pass_at_1_base:.3f} → {result.pass_at_1_struct:.3f}  "
              f"Δ={result.delta_pass_at_1:+.3f}  "
              f"headroom={result.headroom_captured:.0%}  "
              f"W/L={result.wins}/{result.losses}")

    verdict, failures = determine_verdict(alpha_results)

    report = StructureReport(
        n_problems=len(problems),
        features_enabled=features,
        alpha_results=alpha_results,
        per_problem_diagnostics=best_diags or [],
        verdict=verdict,
        failure_modes=failures,
    )

    print("\n")
    print(format_report(report))

    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w") as f:
            json.dump(asdict(report), f, indent=2, default=str)
        print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
