"""
Mixture of Experts FFN Benchmarks (V10.6)

Tests Mixtral-style MoE FFN for compute efficiency:
    1. Throughput comparison (dense vs MoE tokens/sec)
    2. Expert utilization (load balance across experts)
    3. Router behavior (entropy, stability)
    4. Ablation (Dense vs MoE-4E vs MoE-8E vs MoE-16E)

CLI Usage::

    # Run MoE benchmarks
    python train_hard_probes.py --test-moe-ffn

    # Custom expert count
    python train_hard_probes.py --test-moe-ffn --moe-num-experts 16 --moe-top-k 2

    # With ablation
    python train_hard_probes.py --test-moe-ffn --moe-ablation

Expected Results:
    - Speedup: 1.5-2x over dense FFN
    - Load Balance: <5%% utilization imbalance
    - Router Entropy: >70%% of maximum
    - Decision: READY if speedup >= 1.5x
"""

import time
import torch
import torch.nn as nn
from typing import Dict, Optional

from ..imports import MOE_FFN_AVAILABLE
if MOE_FFN_AVAILABLE:
    from symbolu.moe_ffn import MoEFFN, MoEConfig, MoEFFNBenchmark, create_moe_ffn

# =============================================================================
# V10.6: MOE FFN BENCHMARKS
# =============================================================================
# Tests Mixture of Experts FFN for compute efficiency.


def run_moe_ffn_benchmarks(
    args,
    config,
    device: str,
) -> Dict[str, any]:
    """
    Run comprehensive MoE FFN benchmarks.

    Tests:
    1. Throughput comparison (dense vs MoE)
    2. Expert utilization (load balance)
    3. Quality comparison (accuracy preservation)
    4. Router behavior (entropy, stability)

    Args:
        args: CLI arguments
        config: Config object
        device: torch device

    Returns:
        Dictionary with benchmark results
    """
    print("\n" + "=" * 70)
    print("V10.6: MOE FFN BENCHMARKS")
    print("=" * 70)

    if not MOE_FFN_AVAILABLE:
        print("\n  ERROR: MoE FFN module not available.")
        print("  Ensure symbolu.moe_ffn is importable.")
        return {"error": "Module not available"}

    results = {
        "throughput": {},
        "expert_utilization": {},
        "quality": {},
        "ablation": {},
    }

    d_model = config.d_model
    d_ff = config.d_ff
    num_experts = args.moe_num_experts
    top_k = args.moe_top_k

    print(f"\n  Configuration:")
    print(f"    d_model: {d_model}")
    print(f"    d_ff: {d_ff}")
    print(f"    num_experts: {num_experts}")
    print(f"    top_k: {top_k}")
    print(f"    device: {device}")

    # -------------------------------------------------------------------------
    # TEST 1: Throughput Comparison
    # -------------------------------------------------------------------------
    print("\n--- TEST 1: Throughput Comparison ---")
    print("  Comparing dense FFN vs MoE FFN throughput.")

    # Create dense FFN
    dense_ffn = nn.Sequential(
        nn.Linear(d_model, d_ff),
        nn.GELU(),
        nn.Linear(d_ff, d_model),
    ).to(device)

    # Create MoE FFN
    moe_ffn = MoEFFN(
        d_model=d_model,
        d_ff=d_ff,
        num_experts=num_experts,
        top_k=top_k,
        load_balance_weight=args.moe_load_balance_weight,
        router_z_weight=args.moe_router_z_weight,
    ).to(device)

    # Parameter counts
    dense_params = sum(p.numel() for p in dense_ffn.parameters())
    moe_params = sum(p.numel() for p in moe_ffn.parameters())

    print(f"\n  Parameter counts:")
    print(f"    Dense FFN: {dense_params:,}")
    print(f"    MoE FFN:   {moe_params:,} ({moe_params/dense_params:.1f}x)")

    # Throughput benchmark
    import time

    B, N = 32, 256
    x = torch.randn(B, N, d_model, device=device)
    num_iters = 50
    warmup = 10

    # Dense throughput
    dense_ffn.eval()
    with torch.no_grad():
        for _ in range(warmup):
            _ = dense_ffn(x)
        if device == "cuda":
            torch.cuda.synchronize()

        start = time.perf_counter()
        for _ in range(num_iters):
            _ = dense_ffn(x)
        if device == "cuda":
            torch.cuda.synchronize()
        dense_time = time.perf_counter() - start

    dense_tokens_per_sec = (B * N * num_iters) / dense_time

    # MoE throughput
    moe_ffn.eval()
    with torch.no_grad():
        for _ in range(warmup):
            _, _ = moe_ffn(x)
        if device == "cuda":
            torch.cuda.synchronize()

        start = time.perf_counter()
        for _ in range(num_iters):
            _, _ = moe_ffn(x)
        if device == "cuda":
            torch.cuda.synchronize()
        moe_time = time.perf_counter() - start

    moe_tokens_per_sec = (B * N * num_iters) / moe_time

    speedup = moe_tokens_per_sec / dense_tokens_per_sec

    print(f"\n  Throughput results:")
    print(f"    Dense FFN: {dense_tokens_per_sec:,.0f} tokens/sec")
    print(f"    MoE FFN:   {moe_tokens_per_sec:,.0f} tokens/sec")
    print(f"    Speedup:   {speedup:.2f}x")

    results["throughput"] = {
        "dense_tokens_per_sec": dense_tokens_per_sec,
        "moe_tokens_per_sec": moe_tokens_per_sec,
        "speedup": speedup,
    }

    # Theoretical speedup
    theoretical_speedup = num_experts / top_k
    efficiency = speedup / theoretical_speedup * 100

    print(f"\n  Efficiency analysis:")
    print(f"    Theoretical max speedup: {theoretical_speedup:.1f}x")
    print(f"    Achieved efficiency: {efficiency:.1f}%")

    # -------------------------------------------------------------------------
    # TEST 2: Expert Utilization
    # -------------------------------------------------------------------------
    print("\n--- TEST 2: Expert Utilization ---")
    print("  Checking load balance across experts.")

    moe_ffn.eval()
    all_utilizations = []

    with torch.no_grad():
        for _ in range(20):
            x_batch = torch.randn(B, N, d_model, device=device)
            _, aux = moe_ffn(x_batch)
            all_utilizations.append(aux["expert_utilization"])

    stacked = torch.stack(all_utilizations, dim=0)
    mean_util = stacked.mean(dim=0)
    std_util = stacked.std(dim=0)

    print(f"\n  Per-expert utilization (target: {100/num_experts:.1f}% each):")
    for e in range(num_experts):
        bar = "█" * int(mean_util[e] * 100)
        print(f"    Expert {e}: {mean_util[e]*100:5.1f}% ± {std_util[e]*100:4.1f}% {bar}")

    utilization_imbalance = mean_util.std().item()
    load_balance_ok = utilization_imbalance < 0.05  # <5% std deviation

    print(f"\n  Utilization imbalance (std): {utilization_imbalance*100:.2f}%")
    print(f"  [{'PASS' if load_balance_ok else 'WARN'}] Load balance (target: < 5%)")

    results["expert_utilization"] = {
        "mean": mean_util.cpu().tolist(),
        "std": std_util.cpu().tolist(),
        "imbalance": utilization_imbalance,
        "balanced": load_balance_ok,
    }

    # -------------------------------------------------------------------------
    # TEST 3: Router Behavior
    # -------------------------------------------------------------------------
    print("\n--- TEST 3: Router Behavior ---")
    print("  Analyzing router entropy and stability.")

    with torch.no_grad():
        _, aux = moe_ffn(x)

    router_entropy = aux["router_entropy"].item()
    max_entropy = torch.log(torch.tensor(float(num_experts))).item()
    entropy_ratio = router_entropy / max_entropy

    print(f"\n  Router entropy: {router_entropy:.3f}")
    print(f"  Max possible:   {max_entropy:.3f}")
    print(f"  Entropy ratio:  {entropy_ratio:.1%}")

    if entropy_ratio > 0.9:
        print("  Interpretation: Nearly uniform routing (good for diversity)")
    elif entropy_ratio > 0.7:
        print("  Interpretation: Moderately specialized routing")
    else:
        print("  Interpretation: Highly specialized routing (may need more load balance)")

    results["router"] = {
        "entropy": router_entropy,
        "max_entropy": max_entropy,
        "entropy_ratio": entropy_ratio,
    }

    # -------------------------------------------------------------------------
    # TEST 4: Auxiliary Losses
    # -------------------------------------------------------------------------
    print("\n--- TEST 4: Auxiliary Losses ---")
    print("  Checking load balance and router z-loss.")

    load_balance_loss = aux["load_balance_loss"].item()
    router_z_loss = aux["router_z_loss"].item()
    total_aux_loss = aux["moe_aux_loss"].item()

    print(f"\n  Load balance loss: {load_balance_loss:.6f}")
    print(f"  Router z-loss:     {router_z_loss:.6f}")
    print(f"  Total aux loss:    {total_aux_loss:.6f}")

    results["aux_losses"] = {
        "load_balance": load_balance_loss,
        "router_z": router_z_loss,
        "total": total_aux_loss,
    }

    # -------------------------------------------------------------------------
    # TEST 5: Ablation (if requested)
    # -------------------------------------------------------------------------
    if args.moe_ablation:
        print("\n--- TEST 5: Ablation Comparison ---")
        print("  Comparing Dense vs MoE-4E vs MoE-8E vs MoE-16E")

        ablation_configs = [
            ("Dense", 1, 1),
            ("MoE-4E-Top2", 4, 2),
            ("MoE-8E-Top2", 8, 2),
            ("MoE-16E-Top2", 16, 2),
        ]

        print(f"\n  {'Config':<15} {'Params':>12} {'Tokens/sec':>12} {'Speedup':>8}")
        print(f"  {'-'*15} {'-'*12} {'-'*12} {'-'*8}")

        baseline_speed = None

        for name, n_exp, tk in ablation_configs:
            if n_exp == 1:
                # Dense
                model = nn.Sequential(
                    nn.Linear(d_model, d_ff),
                    nn.GELU(),
                    nn.Linear(d_ff, d_model),
                ).to(device)
            else:
                # MoE
                model = MoEFFN(
                    d_model=d_model,
                    d_ff=d_ff,
                    num_experts=n_exp,
                    top_k=tk,
                ).to(device)

            params = sum(p.numel() for p in model.parameters())

            model.eval()
            with torch.no_grad():
                for _ in range(warmup):
                    if n_exp == 1:
                        _ = model(x)
                    else:
                        _, _ = model(x)

                if device == "cuda":
                    torch.cuda.synchronize()

                start = time.perf_counter()
                for _ in range(num_iters):
                    if n_exp == 1:
                        _ = model(x)
                    else:
                        _, _ = model(x)

                if device == "cuda":
                    torch.cuda.synchronize()

                elapsed = time.perf_counter() - start

            tokens_per_sec = (B * N * num_iters) / elapsed

            if baseline_speed is None:
                baseline_speed = tokens_per_sec
                speedup_str = "1.00x"
            else:
                speedup_str = f"{tokens_per_sec/baseline_speed:.2f}x"

            print(f"  {name:<15} {params:>12,} {tokens_per_sec:>12,.0f} {speedup_str:>8}")

            results["ablation"][name] = {
                "params": params,
                "tokens_per_sec": tokens_per_sec,
                "speedup": tokens_per_sec / baseline_speed if baseline_speed else 1.0,
            }

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("MOE FFN BENCHMARK SUMMARY")
    print("=" * 70)

    print(f"\n  Throughput:        {speedup:.2f}x speedup over dense FFN")
    print(f"  Load Balance:      {'PASS' if load_balance_ok else 'WARN'} (imbalance: {utilization_imbalance*100:.1f}%)")
    print(f"  Router Entropy:    {entropy_ratio:.1%} of maximum")
    print(f"  Aux Loss:          {total_aux_loss:.6f}")

    # Decision recommendation
    print("\n  RECOMMENDATION FOR train_unified_llm.py:")
    if speedup >= 1.5 and load_balance_ok:
        print("    [READY] MoE FFN provides good speedup with balanced utilization.")
        print("    Suggested flags: --moe-ffn --moe-num-experts 8 --moe-top-k 2")
    elif speedup >= 1.2:
        print("    [CONSIDER] Modest speedup. Consider for large-scale training.")
    else:
        print("    [SKIP] Speedup not significant. Dense FFN may be sufficient.")

    return results


def run_moe_ffn_benchmark_integration(args, config):
    """
    Integration entry point for MoE FFN benchmarks.

    Called from main() when --test-moe-ffn is specified.
    """
    print("\n" + "=" * 70)
    print("MOE FFN BENCHMARK: Integration Mode")
    print("=" * 70)

    results = run_moe_ffn_benchmarks(args, config, config.device)

    if "error" in results:
        print(f"\nBenchmark failed: {results['error']}")
        return

    # Print CLI usage
    print("\n" + "-" * 70)
    print("CLI USAGE:")
    print("-" * 70)
    print("""
  # Run MoE FFN benchmarks
  python train_hard_probes.py --test-moe-ffn

  # Custom expert configuration
  python train_hard_probes.py --test-moe-ffn --moe-num-experts 16 --moe-top-k 2

  # With ablation comparison
  python train_hard_probes.py --test-moe-ffn --moe-ablation

  # Full benchmark suite
  python train_hard_probes.py --test-moe-ffn --moe-ablation \\
      --moe-num-experts 8 --moe-top-k 2 --moe-load-balance-weight 0.01
""")

    return results


# =============================================================================
# V10.7: HIERARCHICAL PHASE-QUAD (HP-QUAD) BENCHMARKS
# =============================================================================
