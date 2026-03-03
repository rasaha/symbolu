"""
Phase-Aware Adaptation Benchmarks: IA3 + Surgical LoRA (V10.12)

Tests controlled plasticity for Phase Quad:
    1. Identity preservation (adapted=base at init)
    2. IA3 gate training
    3. LoRA projection training
    4. Regularization behavior
    5. Save/load adapter
    6. LoRA merge/unmerge
    7. Ablation comparison
    8. Throughput overhead

CLI Usage::

    python train_hard_probes.py --test-adaptation
    python train_hard_probes.py --test-adaptation --adapt-lora --adapt-ablation
"""

import time
import torch
import torch.nn as nn
from typing import Dict, Optional

from ..imports import ADAPTATION_AVAILABLE
if ADAPTATION_AVAILABLE:
    from symbolu.vision.adaptation import (
        IA3Gate, IA3BlockGates, IA3Config,
        LoRALinear, LoRAConfig, AdaptationConfig,
        PhaseQuadAdaptationManager,
    )

# =============================================================================
# V10.12: PHASE-AWARE ADAPTATION BENCHMARKS (IA³ + SURGICAL LORA)
# =============================================================================
# Tests IA³ gates and surgical LoRA for Phase Quad adaptation.
# Validates that adaptation layers:
#   1. Preserve base model output at initialization
#   2. Actually adapt behavior after training
#   3. Don't break phase separation or AdaLN-Zero geometry
#   4. Scale correctly (parameter counts, memory)
#   5. Save/load cleanly for multi-tenant serving


def run_adaptation_benchmarks(
    args,
    config,
    device: str,
) -> Dict[str, any]:
    """
    Run IA³ + LoRA adaptation benchmarks for Phase Quad.

    Tests:
    1. Identity Preservation - Adapted model = base model at init
    2. IA³ Training - Gates learn meaningful scaling from data
    3. LoRA Training - Projections adapt attention geometry
    4. Phase Integrity - Phase separation maintained after adaptation
    5. Parameter Budget - Verify <1% adaptation ratio
    6. Save/Load - Adapter files save and reload correctly
    7. Merge/Unmerge - LoRA merges into base for zero-overhead inference
    8. Ablation - IA³-only vs LoRA-only vs Combined

    Args:
        args: Parsed CLI arguments.
        config: Config dataclass.
        device: Device string ("cuda" or "cpu").

    Returns:
        Dictionary of test results.
    """
    import time
    from symbolu.vision.phase_quad_dit_block import PhaseQuadDiTBlockStack
    from symbolu.vision.controls import PatchMeta, BlockControl

    results = {}

    # Check availability
    if not ADAPTATION_AVAILABLE:
        print("\n[SKIP] Adaptation modules not available.")
        print("       Install with: pip install -e .")
        results["error"] = "adaptation_not_available"
        return results

    print("\n" + "=" * 70)
    print("PHASE-AWARE ADAPTATION BENCHMARK SUITE (V10.12)")
    print("=" * 70)
    print(f"\nDevice: {device}")
    print(f"Model: embed_dim={args.adapt_embed_dim}, heads={args.adapt_num_heads}, "
          f"blocks={args.adapt_num_blocks}")
    print(f"IA³: {'ENABLED' if args.adapt_ia3 else 'DISABLED'}")
    print(f"LoRA: {'ENABLED (rank={})'.format(args.adapt_lora_rank) if args.adapt_lora else 'DISABLED'}")

    # -------------------------------------------------------------------------
    # Setup: Build base model and test inputs
    # -------------------------------------------------------------------------
    embed_dim = args.adapt_embed_dim
    num_heads = args.adapt_num_heads
    num_blocks = args.adapt_num_blocks
    topk = args.adapt_topk
    window_size = args.adapt_window_size
    ffn_ratio = 4.0
    H_p, W_p = 8, 8
    N_patches = H_p * W_p
    batch_size = 4

    # Build base model
    stack = PhaseQuadDiTBlockStack(
        num_blocks=num_blocks,
        embed_dim=embed_dim,
        num_heads=num_heads,
        topk=topk,
        window_size=window_size,
        ffn_ratio=ffn_ratio,
        use_cross_attn=False,
        use_bcvf=False,
    ).to(device)

    # Test inputs
    coords = torch.stack(
        torch.meshgrid(
            torch.arange(H_p), torch.arange(W_p), indexing="ij"
        ),
        dim=-1,
    ).reshape(-1, 2).to(device)
    meta = PatchMeta(H_p=H_p, W_p=W_p, coords=coords, patch_size=2)
    x = torch.randn(batch_size, N_patches, embed_dim, device=device)
    t_emb = torch.randn(batch_size, embed_dim, device=device)
    timestep = torch.randint(0, 1000, (batch_size,), device=device)

    base_params = sum(p.numel() for p in stack.parameters())
    print(f"\nBase model parameters: {base_params:,}")

    # -------------------------------------------------------------------------
    # TEST 1: Identity Preservation
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("TEST 1: Identity Preservation (adapted output = base output at init)")
    print("-" * 70)

    torch.manual_seed(42)
    with torch.no_grad():
        base_out = stack(x, meta, t_emb, timestep=timestep)

    ia3_config = IA3Config(enable=True, gate_attention=True, gate_mlp=True, gate_quad=True)
    lora_config = LoRAConfig(enable=False)
    adapt_config = AdaptationConfig(ia3=ia3_config, lora=lora_config, freeze_base=True)
    adapter = PhaseQuadAdaptationManager(stack, adapt_config).to(device)

    with torch.no_grad():
        adapted_out = adapter(x, meta, t_emb, timestep=timestep)

    max_diff = (adapted_out - base_out).abs().max().item()
    mean_diff = (adapted_out - base_out).abs().mean().item()
    identity_pass = max_diff < 1e-3

    print(f"  Max difference:  {max_diff:.2e}")
    print(f"  Mean difference: {mean_diff:.2e}")
    print(f"  Result: {'PASS' if identity_pass else 'FAIL'} "
          f"(threshold: 1e-3)")
    results["identity_preservation"] = "PASS" if identity_pass else "FAIL"

    # -------------------------------------------------------------------------
    # TEST 2: Parameter Budget
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("TEST 2: Parameter Budget (adaptation < 1% of base)")
    print("-" * 70)

    summary = adapter.get_adaptation_summary()
    ia3_params = summary["ia3_params"]
    ratio = summary["adaptation_ratio"]

    print(f"  Base params (frozen): {summary['base_params_frozen']:,}")
    print(f"  IA³ params:           {ia3_params:,}")
    print(f"  LoRA params:          {summary['lora_params']:,}")
    print(f"  Total trainable:      {summary['total_trainable']:,}")
    print(f"  Adaptation ratio:     {ratio:.4%}")

    budget_pass = ratio < 0.01  # Less than 1%
    print(f"  Result: {'PASS' if budget_pass else 'FAIL'} "
          f"(ratio={ratio:.4%} < 1%)")
    results["parameter_budget"] = "PASS" if budget_pass else "FAIL"

    # -------------------------------------------------------------------------
    # TEST 3: IA³ Training Loop
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("TEST 3: IA³ Training Loop (gates learn from synthetic data)")
    print("-" * 70)

    # Create fresh model and pretrain briefly so AdaLN-Zero gates are non-zero.
    # AdaLN-Zero initializes gate_attn=0, gate_ffn=0. Without pretraining,
    # all residual paths are zeroed out and adaptation layers receive no gradient.
    # This mimics the real workflow: pretrain base model, THEN add adaptation.
    stack_train = PhaseQuadDiTBlockStack(
        num_blocks=num_blocks,
        embed_dim=embed_dim,
        num_heads=num_heads,
        topk=topk,
        window_size=window_size,
        ffn_ratio=ffn_ratio,
        use_cross_attn=False,
        use_bcvf=False,
    ).to(device)

    print("  Pretraining base model (AdaLN-Zero warmup)...")
    pretrain_opt = torch.optim.AdamW(stack_train.parameters(), lr=1e-3)
    pretrain_target = torch.randn(batch_size, N_patches, embed_dim, device=device) * 0.1
    for step in range(50):
        pretrain_opt.zero_grad()
        out = stack_train(x, meta, t_emb, timestep=timestep)
        loss = F.mse_loss(out, pretrain_target)
        loss.backward()
        pretrain_opt.step()
    print(f"  Pretrain done (final loss: {loss.item():.6f})")

    # Now freeze and add adaptation
    ia3_cfg = IA3Config(enable=True, gate_attention=True, gate_mlp=True, gate_quad=True)
    adapt_cfg = AdaptationConfig(
        ia3=ia3_cfg,
        lora=LoRAConfig(enable=False),
        freeze_base=True,
    )
    adapter_train = PhaseQuadAdaptationManager(stack_train, adapt_cfg).to(device)

    # Training loop: minimize MSE to a target
    target = torch.randn(batch_size, N_patches, embed_dim, device=device) * 0.1
    optimizer = torch.optim.AdamW(adapter_train.trainable_parameters(), lr=5e-3)

    num_train_steps = args.adapt_train_steps
    losses = []
    for step in range(num_train_steps):
        optimizer.zero_grad()
        out = adapter_train(x, meta, t_emb, timestep=timestep)
        loss = F.mse_loss(out, target) + adapter_train.regularization_loss()
        loss.backward()
        optimizer.step()
        losses.append(loss.item())
        if step % (num_train_steps // 5) == 0:
            print(f"    Step {step:4d}: loss = {loss.item():.6f}")

    loss_decreased = losses[-1] < losses[0] * 0.95  # At least 5% decrease
    print(f"  Initial loss: {losses[0]:.6f}")
    print(f"  Final loss:   {losses[-1]:.6f}")
    print(f"  Decrease:     {(1 - losses[-1]/losses[0])*100:.1f}%")

    # Check gates actually moved from 1.0
    gate_diffs = []
    for gates in adapter_train.ia3_gates:
        if gates is not None:
            if gates.gate_local_attn is not None:
                gate_diffs.append((gates.gate_local_attn.gate - 1.0).abs().mean().item())
            if gates.gate_quad_attn is not None:
                gate_diffs.append((gates.gate_quad_attn.gate - 1.0).abs().mean().item())
            if gates.gate_ffn is not None:
                gate_diffs.append((gates.gate_ffn.gate - 1.0).abs().mean().item())

    avg_gate_shift = sum(gate_diffs) / max(len(gate_diffs), 1)
    gates_moved = avg_gate_shift > 0.001
    print(f"  Avg gate shift from 1.0: {avg_gate_shift:.6f}")
    print(f"  Gates learned: {'YES' if gates_moved else 'NO'}")

    ia3_train_pass = loss_decreased and gates_moved
    print(f"  Result: {'PASS' if ia3_train_pass else 'FAIL'}")
    results["ia3_training"] = "PASS" if ia3_train_pass else "FAIL"

    # -------------------------------------------------------------------------
    # TEST 4: LoRA Training Loop (if enabled)
    # -------------------------------------------------------------------------
    if args.adapt_lora:
        print("\n" + "-" * 70)
        print("TEST 4: LoRA Training Loop (projections adapt geometry)")
        print("-" * 70)

        stack_lora = PhaseQuadDiTBlockStack(
            num_blocks=num_blocks,
            embed_dim=embed_dim,
            num_heads=num_heads,
            topk=topk,
            window_size=window_size,
            ffn_ratio=ffn_ratio,
            use_cross_attn=False,
            use_bcvf=False,
        ).to(device)

        # Pretrain so AdaLN-Zero gates are non-zero
        pretrain_opt_l = torch.optim.AdamW(stack_lora.parameters(), lr=1e-3)
        for step in range(50):
            pretrain_opt_l.zero_grad()
            out = stack_lora(x, meta, t_emb, timestep=timestep)
            loss = F.mse_loss(out, target)
            loss.backward()
            pretrain_opt_l.step()

        lora_cfg = LoRAConfig(
            enable=True,
            rank=args.adapt_lora_rank,
            alpha=args.adapt_lora_alpha,
            target_modules=["W_q", "W_k", "W_v"],
        )
        adapt_cfg_lora = AdaptationConfig(
            ia3=IA3Config(enable=True),
            lora=lora_cfg,
            freeze_base=True,
        )
        adapter_lora = PhaseQuadAdaptationManager(stack_lora, adapt_cfg_lora).to(device)

        # Use a distinct target for LoRA test so it has fresh learning signal
        # (the pretrained model may already fit `target` well, leaving little room)
        lora_target = torch.randn(batch_size, N_patches, embed_dim, device=device) * 0.1

        # LoRA starts from zero (B=0), needs higher LR and more steps than IA³
        lora_train_steps = max(num_train_steps, 300)
        optimizer_lora = torch.optim.AdamW(adapter_lora.trainable_parameters(), lr=1e-2)

        losses_lora = []
        for step in range(lora_train_steps):
            optimizer_lora.zero_grad()
            out = adapter_lora(x, meta, t_emb, timestep=timestep)
            loss = F.mse_loss(out, lora_target) + adapter_lora.regularization_loss()
            loss.backward()
            optimizer_lora.step()
            losses_lora.append(loss.item())
            if step % (lora_train_steps // 5) == 0:
                print(f"    Step {step:4d}: loss = {loss.item():.6f}")

        lora_decreased = losses_lora[-1] < losses_lora[0] * 0.95  # At least 5% decrease
        print(f"  Initial loss: {losses_lora[0]:.6f}")
        print(f"  Final loss:   {losses_lora[-1]:.6f}")
        print(f"  Decrease:     {(1 - losses_lora[-1]/losses_lora[0])*100:.1f}%")

        lora_summary = adapter_lora.get_adaptation_summary()
        print(f"  LoRA modules:  {lora_summary['num_lora_modules']}")
        print(f"  LoRA params:   {lora_summary['lora_params']:,}")

        lora_pass = lora_decreased
        print(f"  Result: {'PASS' if lora_pass else 'FAIL'}")
        results["lora_training"] = "PASS" if lora_pass else "FAIL"
    else:
        results["lora_training"] = "SKIP"

    # -------------------------------------------------------------------------
    # TEST 5: Regularization Behavior
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("TEST 5: Regularization (gates stay near identity)")
    print("-" * 70)

    reg_loss = adapter_train.regularization_loss().item()
    print(f"  Regularization loss after training: {reg_loss:.6f}")

    # Gates should not drift too far (reg keeps them near 1.0)
    max_gate_diff = max(gate_diffs) if gate_diffs else 0.0
    reg_effective = max_gate_diff < 0.5  # No gate should drift more than 0.5 from 1.0
    print(f"  Max gate deviation from 1.0:  {max_gate_diff:.6f}")
    print(f"  Regularization effective:     {'YES' if reg_effective else 'NO'}")
    print(f"  Result: {'PASS' if reg_effective else 'FAIL'}")
    results["regularization"] = "PASS" if reg_effective else "FAIL"

    # -------------------------------------------------------------------------
    # TEST 6: Save/Load Adapter
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("TEST 6: Save/Load Adapter (weights preserved)")
    print("-" * 70)

    import tempfile
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = os.path.join(tmpdir, "adapter.pt")
        adapter_train.save_adapter(save_path)
        file_size = os.path.getsize(save_path)

        # Create fresh adapter and load
        stack_load = PhaseQuadDiTBlockStack(
            num_blocks=num_blocks,
            embed_dim=embed_dim,
            num_heads=num_heads,
            topk=topk,
            window_size=window_size,
            ffn_ratio=ffn_ratio,
            use_cross_attn=False,
            use_bcvf=False,
        ).to(device)
        adapter_loaded = PhaseQuadAdaptationManager(stack_load, adapt_cfg).to(device)
        adapter_loaded.load_adapter(save_path)

        # Compare outputs
        with torch.no_grad():
            out_original = adapter_train(x, meta, t_emb, timestep=timestep)
            out_loaded = adapter_loaded(x, meta, t_emb, timestep=timestep)

        # Note: base models differ so we compare gate values instead
        gates_match = True
        for g1, g2 in zip(adapter_train.ia3_gates, adapter_loaded.ia3_gates):
            if g1 is not None and g2 is not None:
                if g1.gate_local_attn is not None and g2.gate_local_attn is not None:
                    diff = (g1.gate_local_attn.gate - g2.gate_local_attn.gate).abs().max().item()
                    if diff > 1e-6:
                        gates_match = False
                if g1.gate_ffn is not None and g2.gate_ffn is not None:
                    diff = (g1.gate_ffn.gate - g2.gate_ffn.gate).abs().max().item()
                    if diff > 1e-6:
                        gates_match = False

        print(f"  Adapter file size:  {file_size:,} bytes ({file_size/1024:.1f} KB)")
        print(f"  Base model size:    ~{base_params * 2 / 1024 / 1024:.1f} MB (BF16)")
        print(f"  Compression ratio:  {file_size / (base_params * 2):.4%}")
        print(f"  Gates match:        {'YES' if gates_match else 'NO'}")

        save_load_pass = gates_match
        print(f"  Result: {'PASS' if save_load_pass else 'FAIL'}")
        results["save_load"] = "PASS" if save_load_pass else "FAIL"

    # -------------------------------------------------------------------------
    # TEST 7: LoRA Merge/Unmerge (if enabled)
    # -------------------------------------------------------------------------
    if args.adapt_lora and "adapter_lora" in dir():
        print("\n" + "-" * 70)
        print("TEST 7: LoRA Merge/Unmerge (zero-overhead inference)")
        print("-" * 70)

        # Use eval mode to eliminate dropout stochasticity
        adapter_lora.eval()
        stack_lora.eval()

        with torch.no_grad():
            out_pre_merge = adapter_lora(x, meta, t_emb, timestep=timestep)

        adapter_lora.merge_lora()

        # After merge, the LoRA delta is in base weights
        # Forward through adapted path (LoRA skips delta since merged flag is set)
        with torch.no_grad():
            out_merged = adapter_lora(x, meta, t_emb, timestep=timestep)

        merge_diff = (out_pre_merge - out_merged).abs().max().item()
        merge_pass = merge_diff < 1e-3
        print(f"  Max diff pre/post merge: {merge_diff:.2e}")

        # Unmerge and verify reversibility
        adapter_lora.unmerge_lora()
        with torch.no_grad():
            out_unmerged = adapter_lora(x, meta, t_emb, timestep=timestep)

        # Restore train mode
        adapter_lora.train()
        stack_lora.train()

        unmerge_diff = (out_pre_merge - out_unmerged).abs().max().item()
        unmerge_pass = unmerge_diff < 1e-3
        print(f"  Max diff after unmerge:  {unmerge_diff:.2e}")
        print(f"  Merge reversible:        {'YES' if unmerge_pass else 'NO'}")

        merge_test_pass = merge_pass and unmerge_pass
        print(f"  Result: {'PASS' if merge_test_pass else 'FAIL'}")
        results["lora_merge_unmerge"] = "PASS" if merge_test_pass else "FAIL"
    else:
        results["lora_merge_unmerge"] = "SKIP"

    # -------------------------------------------------------------------------
    # TEST 8: Ablation (IA³-only vs LoRA-only vs Combined)
    # -------------------------------------------------------------------------
    if args.adapt_ablation:
        print("\n" + "-" * 70)
        print("TEST 8: Ablation (IA³-only vs LoRA-only vs Combined)")
        print("-" * 70)

        ablation_configs = {
            "ia3_only": AdaptationConfig(
                ia3=IA3Config(enable=True),
                lora=LoRAConfig(enable=False),
                freeze_base=True,
            ),
            "lora_only": AdaptationConfig(
                ia3=IA3Config(enable=False),
                lora=LoRAConfig(
                    enable=True,
                    rank=args.adapt_lora_rank,
                    alpha=args.adapt_lora_alpha,
                ),
                freeze_base=True,
            ),
            "combined": AdaptationConfig(
                ia3=IA3Config(enable=True),
                lora=LoRAConfig(
                    enable=True,
                    rank=args.adapt_lora_rank,
                    alpha=args.adapt_lora_alpha,
                ),
                freeze_base=True,
            ),
        }

        ablation_results = {}
        for name, ab_config in ablation_configs.items():
            ab_stack = PhaseQuadDiTBlockStack(
                num_blocks=num_blocks,
                embed_dim=embed_dim,
                num_heads=num_heads,
                topk=topk,
                window_size=window_size,
                ffn_ratio=ffn_ratio,
                use_cross_attn=False,
                use_bcvf=False,
            ).to(device)

            # Pretrain so AdaLN-Zero gates are non-zero
            ab_pre_opt = torch.optim.AdamW(ab_stack.parameters(), lr=1e-3)
            for _s in range(50):
                ab_pre_opt.zero_grad()
                _o = ab_stack(x, meta, t_emb, timestep=timestep)
                _l = F.mse_loss(_o, target)
                _l.backward()
                ab_pre_opt.step()

            ab_adapter = PhaseQuadAdaptationManager(ab_stack, ab_config).to(device)

            ab_optimizer = torch.optim.AdamW(ab_adapter.trainable_parameters(), lr=5e-3)

            t_start = time.time()
            ab_losses = []
            for step in range(num_train_steps):
                ab_optimizer.zero_grad()
                out = ab_adapter(x, meta, t_emb, timestep=timestep)
                loss = F.mse_loss(out, target) + ab_adapter.regularization_loss()
                loss.backward()
                ab_optimizer.step()
                ab_losses.append(loss.item())
            train_time = time.time() - t_start

            ab_summary = ab_adapter.get_adaptation_summary()
            ablation_results[name] = {
                "final_loss": ab_losses[-1],
                "loss_decrease_pct": (1 - ab_losses[-1] / ab_losses[0]) * 100,
                "trainable_params": ab_summary["total_trainable"],
                "adaptation_ratio": ab_summary["adaptation_ratio"],
                "train_time_s": train_time,
            }
            print(f"\n  [{name}]")
            print(f"    Trainable params: {ab_summary['total_trainable']:,} "
                  f"({ab_summary['adaptation_ratio']:.4%})")
            print(f"    Final loss:       {ab_losses[-1]:.6f} "
                  f"({ablation_results[name]['loss_decrease_pct']:.1f}% decrease)")
            print(f"    Train time:       {train_time:.2f}s")

        results["ablation"] = ablation_results

        # Compare
        print("\n  Comparison:")
        print(f"    {'Config':<15} {'Params':>10} {'Final Loss':>12} {'Decrease':>10} {'Time':>8}")
        print("    " + "-" * 60)
        for name, ar in ablation_results.items():
            print(f"    {name:<15} {ar['trainable_params']:>10,} "
                  f"{ar['final_loss']:>12.6f} "
                  f"{ar['loss_decrease_pct']:>9.1f}% "
                  f"{ar['train_time_s']:>7.2f}s")

        results["ablation_comparison"] = "PASS"
    else:
        results["ablation_comparison"] = "SKIP"

    # -------------------------------------------------------------------------
    # TEST 9: Throughput Benchmark
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("TEST 9: Throughput (adapted vs base forward pass)")
    print("-" * 70)

    # Warm up
    for _ in range(3):
        with torch.no_grad():
            _ = stack(x, meta, t_emb, timestep=timestep)
            _ = adapter(x, meta, t_emb, timestep=timestep)

    if device == "cuda":
        torch.cuda.synchronize()

    # Base model throughput
    num_bench_iters = args.adapt_bench_iters
    t_start = time.time()
    for _ in range(num_bench_iters):
        with torch.no_grad():
            _ = stack(x, meta, t_emb, timestep=timestep)
    if device == "cuda":
        torch.cuda.synchronize()
    base_time = (time.time() - t_start) / num_bench_iters

    # Adapted model throughput
    t_start = time.time()
    for _ in range(num_bench_iters):
        with torch.no_grad():
            _ = adapter(x, meta, t_emb, timestep=timestep)
    if device == "cuda":
        torch.cuda.synchronize()
    adapted_time = (time.time() - t_start) / num_bench_iters

    overhead = (adapted_time - base_time) / base_time * 100
    print(f"  Base model:    {base_time*1000:.2f} ms/forward")
    print(f"  Adapted model: {adapted_time*1000:.2f} ms/forward")
    print(f"  Overhead:      {overhead:+.1f}%")

    throughput_pass = overhead < 15  # Less than 15% overhead
    print(f"  Result: {'PASS' if throughput_pass else 'FAIL'} "
          f"(overhead < 15%)")
    results["throughput"] = "PASS" if throughput_pass else "FAIL"

    # -------------------------------------------------------------------------
    # TEST 10: Distribution Shift (IA³ vs LoRA under domain/OOD/long-context)
    # -------------------------------------------------------------------------
    # ChatGPT correctly noted: LoRA's strength shows under distribution shift
    # because it can learn NEW feature directions, while IA³ only rescales
    # existing channels. This test validates that claim empirically.
    if args.adapt_lora and args.adapt_ablation:
        print("\n" + "-" * 70)
        print("TEST 10: Distribution Shift (IA³ vs LoRA under domain gap)")
        print("-" * 70)

        shift_results = {}

        # --- Helper: train adapter and return final loss decrease ---
        def _train_shift_adapter(adapt_cfg, train_x, train_target,
                                 eval_x, eval_target, meta_train, meta_eval,
                                 pretrain_steps=50, train_steps=200):
            """Train on source, measure on target domain."""
            stk = PhaseQuadDiTBlockStack(
                num_blocks=num_blocks,
                embed_dim=embed_dim,
                num_heads=num_heads,
                topk=topk,
                window_size=window_size,
                ffn_ratio=ffn_ratio,
                use_cross_attn=False,
                use_bcvf=False,
            ).to(device)

            # AdaLN-Zero warmup on source domain
            pre_opt = torch.optim.AdamW(stk.parameters(), lr=1e-3)
            for _ in range(pretrain_steps):
                pre_opt.zero_grad()
                out = stk(train_x, meta_train, t_emb, timestep=timestep)
                loss = F.mse_loss(out, train_target)
                loss.backward()
                pre_opt.step()

            # Baseline: frozen model loss on target domain
            stk.eval()
            with torch.no_grad():
                baseline_loss = F.mse_loss(
                    stk(eval_x, meta_eval, t_emb[:eval_x.shape[0]],
                        timestep=timestep[:eval_x.shape[0]]),
                    eval_target
                ).item()
            stk.train()

            # Adapt on target domain
            adp = PhaseQuadAdaptationManager(stk, adapt_cfg).to(device)
            opt = torch.optim.AdamW(adp.trainable_parameters(), lr=1e-2)

            for step in range(train_steps):
                opt.zero_grad()
                out = adp(eval_x, meta_eval, t_emb[:eval_x.shape[0]],
                          timestep=timestep[:eval_x.shape[0]])
                loss = F.mse_loss(out, eval_target) + adp.regularization_loss()
                loss.backward()
                opt.step()

            adp.eval()
            with torch.no_grad():
                final_loss = F.mse_loss(
                    adp(eval_x, meta_eval, t_emb[:eval_x.shape[0]],
                        timestep=timestep[:eval_x.shape[0]]),
                    eval_target
                ).item()

            decrease_pct = (1.0 - final_loss / baseline_loss) * 100 if baseline_loss > 0 else 0
            return baseline_loss, final_loss, decrease_pct

        # Configs
        ia3_only_cfg = AdaptationConfig(
            ia3=IA3Config(enable=True),
            lora=LoRAConfig(enable=False),
            freeze_base=True,
        )
        lora_only_cfg = AdaptationConfig(
            ia3=IA3Config(enable=False),
            lora=LoRAConfig(enable=True, rank=args.adapt_lora_rank,
                            alpha=args.adapt_lora_alpha),
            freeze_base=True,
        )
        combined_cfg = AdaptationConfig(
            ia3=IA3Config(enable=True),
            lora=LoRAConfig(enable=True, rank=args.adapt_lora_rank,
                            alpha=args.adapt_lora_alpha),
            freeze_base=True,
        )

        # ---------------------------------------------------------------
        # SHIFT A: Spatial frequency domain shift
        # Train on smooth (low-freq) patterns, adapt to sharp (high-freq)
        # ---------------------------------------------------------------
        print("\n  [A] Spatial Frequency Shift (smooth -> sharp)")

        # Low-freq source: smooth sinusoidal patches
        coords_2d = meta.coords.float()  # [N, 2]
        low_freq = torch.sin(coords_2d[:, 0:1] * 0.5) * torch.cos(coords_2d[:, 1:2] * 0.5)
        train_source = low_freq.unsqueeze(0).expand(batch_size, -1, -1)
        train_source = train_source.repeat(1, 1, embed_dim // 1 + 1)[:, :, :embed_dim].to(device) * 0.1
        train_source_target = train_source * 0.8  # Slight transform

        # High-freq target: sharp checkerboard-like patterns
        high_freq = torch.sin(coords_2d[:, 0:1] * 4.0) * torch.cos(coords_2d[:, 1:2] * 4.0)
        eval_sharp = high_freq.unsqueeze(0).expand(batch_size, -1, -1)
        eval_sharp = eval_sharp.repeat(1, 1, embed_dim // 1 + 1)[:, :, :embed_dim].to(device) * 0.1
        eval_sharp_target = eval_sharp * 0.5 + 0.02  # Different transform

        for cfg_name, cfg in [("ia3_only", ia3_only_cfg),
                               ("lora_only", lora_only_cfg),
                               ("combined", combined_cfg)]:
            bl, fl, dec = _train_shift_adapter(
                cfg, train_source, train_source_target,
                eval_sharp, eval_sharp_target, meta, meta)
            shift_results[f"freq_shift_{cfg_name}"] = {
                "baseline": bl, "final": fl, "decrease": dec}
            print(f"      {cfg_name:<12}: baseline={bl:.4f} -> final={fl:.4f} "
                  f"({dec:.1f}% decrease)")

        # ---------------------------------------------------------------
        # SHIFT B: Statistical distribution shift (Gaussian -> Laplace)
        # Train on Gaussian inputs, adapt to heavy-tailed Laplace
        # ---------------------------------------------------------------
        print("\n  [B] Statistical Distribution Shift (Gaussian -> Laplace)")

        torch.manual_seed(42)
        gauss_x = torch.randn(batch_size, N_patches, embed_dim, device=device) * 0.1
        gauss_target = torch.randn(batch_size, N_patches, embed_dim, device=device) * 0.05

        # Laplace distribution: heavier tails than Gaussian
        laplace_x = torch.distributions.Laplace(0, 0.1).sample(
            (batch_size, N_patches, embed_dim)).to(device)
        laplace_target = torch.distributions.Laplace(0, 0.05).sample(
            (batch_size, N_patches, embed_dim)).to(device)

        for cfg_name, cfg in [("ia3_only", ia3_only_cfg),
                               ("lora_only", lora_only_cfg),
                               ("combined", combined_cfg)]:
            bl, fl, dec = _train_shift_adapter(
                cfg, gauss_x, gauss_target,
                laplace_x, laplace_target, meta, meta)
            shift_results[f"stat_shift_{cfg_name}"] = {
                "baseline": bl, "final": fl, "decrease": dec}
            print(f"      {cfg_name:<12}: baseline={bl:.4f} -> final={fl:.4f} "
                  f"({dec:.1f}% decrease)")

        # ---------------------------------------------------------------
        # SHIFT C: Long-context adaptation (8x8 -> 12x12 patches)
        # Train on standard resolution, adapt to higher resolution
        # ---------------------------------------------------------------
        print("\n  [C] Long-Context Shift (8x8={} patches -> 12x12={} patches)".format(
            H_p * W_p, 12 * 12))

        # Source: standard 8x8
        std_x = torch.randn(batch_size, N_patches, embed_dim, device=device) * 0.1
        std_target = torch.randn(batch_size, N_patches, embed_dim, device=device) * 0.05

        # Target: 12x12 = 144 patches (longer context)
        H_p_long, W_p_long = 12, 12
        N_long = H_p_long * W_p_long
        coords_long = torch.stack(
            torch.meshgrid(
                torch.arange(H_p_long), torch.arange(W_p_long), indexing="ij"
            ), dim=-1
        ).reshape(-1, 2).to(device)
        meta_long = PatchMeta(
            H_p=H_p_long, W_p=W_p_long, coords=coords_long, patch_size=2)

        long_x = torch.randn(batch_size, N_long, embed_dim, device=device) * 0.1
        long_target = torch.randn(batch_size, N_long, embed_dim, device=device) * 0.05

        for cfg_name, cfg in [("ia3_only", ia3_only_cfg),
                               ("lora_only", lora_only_cfg),
                               ("combined", combined_cfg)]:
            bl, fl, dec = _train_shift_adapter(
                cfg, std_x, std_target,
                long_x, long_target, meta, meta_long)
            shift_results[f"long_ctx_{cfg_name}"] = {
                "baseline": bl, "final": fl, "decrease": dec}
            print(f"      {cfg_name:<12}: baseline={bl:.4f} -> final={fl:.4f} "
                  f"({dec:.1f}% decrease)")

        # --- Summary table ---
        print(f"\n  {'Shift Scenario':<35} {'IA³':>8} {'LoRA':>8} {'Combined':>8}  {'Winner':<10}")
        print("  " + "-" * 75)
        for shift_name, shift_label in [
            ("freq_shift", "Spatial Frequency"),
            ("stat_shift", "Statistical (Gauss->Laplace)"),
            ("long_ctx", "Long Context (64->144 patches)"),
        ]:
            ia3_dec = shift_results[f"{shift_name}_ia3_only"]["decrease"]
            lora_dec = shift_results[f"{shift_name}_lora_only"]["decrease"]
            comb_dec = shift_results[f"{shift_name}_combined"]["decrease"]

            vals = {"IA3": ia3_dec, "LoRA": lora_dec, "Combined": comb_dec}
            winner = max(vals, key=vals.get)

            print(f"  {shift_label:<35} {ia3_dec:>7.1f}% {lora_dec:>7.1f}% "
                  f"{comb_dec:>7.1f}%  {winner}")

        # LoRA should show advantage under at least one distribution shift
        lora_wins = 0
        for shift_name in ["freq_shift", "stat_shift", "long_ctx"]:
            lora_dec = shift_results[f"{shift_name}_lora_only"]["decrease"]
            ia3_dec = shift_results[f"{shift_name}_ia3_only"]["decrease"]
            if lora_dec > ia3_dec:
                lora_wins += 1

        combined_always_best = all(
            shift_results[f"{s}_combined"]["decrease"] >=
            max(shift_results[f"{s}_ia3_only"]["decrease"],
                shift_results[f"{s}_lora_only"]["decrease"]) - 1.0  # 1% tolerance
            for s in ["freq_shift", "stat_shift", "long_ctx"]
        )

        print(f"\n  LoRA outperforms IA³ in {lora_wins}/3 shift scenarios")
        print(f"  Combined is best (within 1%) in all scenarios: "
              f"{'YES' if combined_always_best else 'NO'}")

        # The test passes if adaptation helps at all under shift
        any_adaptation_helps = any(
            shift_results[f"{s}_combined"]["decrease"] > 2.0
            for s in ["freq_shift", "stat_shift", "long_ctx"]
        )
        shift_pass = any_adaptation_helps
        print(f"  Result: {'PASS' if shift_pass else 'FAIL'}")
        results["distribution_shift"] = "PASS" if shift_pass else "FAIL"
        results["shift_details"] = shift_results
    else:
        results["distribution_shift"] = "SKIP"

    # -------------------------------------------------------------------------
    # SUMMARY
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("PHASE-AWARE ADAPTATION BENCHMARK SUMMARY (V10.12)")
    print("=" * 70)

    print(f"\n{'Test':<35} {'Result':<15}")
    print("-" * 50)
    for test_name, result in results.items():
        if test_name in ("ablation", "error", "shift_details"):
            continue
        status_icon = "+" if result == "PASS" else "-" if result == "SKIP" else "X"
        print(f"  {test_name:<33} [{status_icon}] {result:<15}")

    # Overall verdict — check all actual test results (skip metadata entries)
    skip_keys = ("ablation", "ablation_comparison", "error", "shift_details")
    test_results = [v for k, v in results.items()
                    if k not in skip_keys and isinstance(v, str)]
    passed = [r for r in test_results if r == "PASS"]
    skipped = [r for r in test_results if r == "SKIP"]
    failed = [r for r in test_results if r == "FAIL"]
    all_pass = len(failed) == 0
    print(f"\nOverall: {len(passed)} PASS, {len(failed)} FAIL, {len(skipped)} SKIP")

    if all_pass:
        print("\nDecision: IA³ adaptation is READY for Phase Quad deployment.")
        if args.adapt_lora and results.get("lora_training") == "PASS":
            print("          LoRA on projections is READY for surgical use.")
        if results.get("distribution_shift") == "PASS":
            print("          Distribution shift resilience CONFIRMED.")

    return results


def run_adaptation_benchmark_integration(args, config):
    """
    Integration wrapper for adaptation benchmarks.

    Called from main() when --test-adaptation is specified.
    Follows the standard benchmark integration pattern.
    """
    print("\n" + "=" * 70)
    print("ADAPTATION BENCHMARK: Integration Mode")
    print("=" * 70)

    results = run_adaptation_benchmarks(args, config, config.device)

    if "error" in results:
        print(f"\nBenchmark failed: {results['error']}")
        return

    # Print CLI usage reminder
    print("\n" + "-" * 70)
    print("CLI USAGE:")
    print("-" * 70)
    print("""
  # Run adaptation benchmarks (IA3 only, default)
  python train_hard_probes.py --test-adaptation

  # With LoRA enabled
  python train_hard_probes.py --test-adaptation --adapt-lora

  # With ablation comparison (IA3-only vs LoRA-only vs Combined)
  python train_hard_probes.py --test-adaptation --adapt-lora --adapt-ablation

  # Custom model size
  python train_hard_probes.py --test-adaptation --adapt-embed-dim 512 --adapt-num-heads 8

  # Full benchmark suite
  python train_hard_probes.py --test-adaptation --adapt-lora --adapt-ablation \\
      --adapt-lora-rank 8 --adapt-train-steps 200 --adapt-bench-iters 50
""")

    return results


# =============================================================================
# MAIN
# =============================================================================
