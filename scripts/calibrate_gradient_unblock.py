#!/usr/bin/env python3
"""
Gradient-Unblock Calibration Script
====================================

Verifies that removing .detach() on _cg_sov_state in the Phase 3 CG
integration path actually allows CG losses to train the state projector.

Tests:
  1. Gradient flow: does backward() produce nonzero grad on state projector?
  2. A/B comparison: detach ON (old) vs OFF (fix) — grad norms side by side
  3. State evolution: over N optimization steps, do Bhava/Vritti/Guna slices
     move away from initialization?
  4. Structural check: do softmax slices become non-uniform, sigmoid slices
     move away from midpoint?

Runs on CPU, no model download needed. Uses only CG modules directly.
"""

import sys
import os
import json
import math
from datetime import datetime
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from symbolu_training.jepa.state_projector import SovereignStateProjector
from symbolu_training.training.conscious_generation.governance.kosha_router import KoshaDomainRouter
from symbolu_training.training.conscious_generation.governance.bliss_gate import BlissTokenGate
from symbolu_training.training.conscious_generation.integration.token_scorer import IntegratedTokenScorer
from symbolu_training.training.conscious_generation.losses.kosha_routing import KoshaRoutingLoss
from symbolu_training.training.conscious_generation.losses.bliss_coherence import BlissCoherenceLoss


# ── Constants ────────────────────────────────────────────────────────────
EMBED_DIM = 256       # Simulated hidden dim (small for CPU speed)
STATE_DIM = 32        # 32D sovereign state
BATCH_SIZE = 4
SEQ_LEN = 16
K = 32                # Shortlist size
NUM_STEPS = 200       # Optimization steps for evolution test
LR = 1e-3
SEED = 42

# Slice layout
BHAVA = slice(0, 12)
KOSHA = slice(12, 17)
VRITTI = slice(17, 22)
GUNA = slice(22, 28)
RESERVED = slice(28, 32)


def entropy(probs: torch.Tensor, dim: int = -1) -> torch.Tensor:
    """Shannon entropy in nats."""
    return -(probs * (probs + 1e-8).log()).sum(dim=dim)


def distance_from_uniform(probs: torch.Tensor, dim: int = -1) -> float:
    """L2 distance from uniform distribution."""
    n = probs.shape[dim]
    uniform = torch.full_like(probs, 1.0 / n)
    return (probs - uniform).norm(dim=dim).mean().item()


def distance_from_midpoint(vals: torch.Tensor) -> float:
    """Mean |val - 0.5| for sigmoid outputs."""
    return (vals - 0.5).abs().mean().item()


def build_modules():
    """Create the CG module pipeline matching train.py's Phase 3 path."""
    state_proj = SovereignStateProjector(
        hidden_dim=EMBED_DIM,
        state_dim=STATE_DIM,
    )

    kosha_router = KoshaDomainRouter(
        embed_dim=EMBED_DIM,
        state_dim=STATE_DIM,
    )

    bliss_gate = BlissTokenGate()

    scorer = IntegratedTokenScorer(
        kosha_router=kosha_router,
        bliss_gate=bliss_gate,
    )

    kosha_loss_fn = KoshaRoutingLoss()
    bliss_loss_fn = BlissCoherenceLoss()

    return state_proj, scorer, kosha_loss_fn, bliss_loss_fn


def make_batch():
    """Create a synthetic batch matching the training loop's tensor shapes."""
    hidden = torch.randn(BATCH_SIZE, SEQ_LEN, EMBED_DIM)
    # Mock T tensor: (B, T, K, 6) — random primitive scores
    T = torch.randn(BATCH_SIZE, SEQ_LEN, K, 6).softmax(dim=-1)
    # Mock candidate ids and target ids
    candidate_ids = torch.randint(0, 32000, (BATCH_SIZE, SEQ_LEN, K))
    target_ids = candidate_ids[:, :, 0]  # First candidate as target
    return hidden, T, candidate_ids, target_ids


def compute_sp_grad_norm(state_proj: nn.Module) -> float:
    """Compute L2 gradient norm over state projector parameters."""
    return (sum(
        p.grad.norm().item() ** 2
        for p in state_proj.parameters()
        if p.grad is not None
    )) ** 0.5


def state_slice_stats(sov_state: torch.Tensor) -> dict:
    """Compute per-slice statistics for the 32D state."""
    with torch.no_grad():
        bhava = sov_state[..., BHAVA]
        vritti = sov_state[..., VRITTI]
        guna = sov_state[..., GUNA]

        return {
            # Bhava (softmax → uniform = 1/12 ≈ 0.083 each)
            "bhava_entropy": entropy(bhava).mean().item(),
            "bhava_max_entropy": math.log(12),
            "bhava_dist_from_uniform": distance_from_uniform(bhava),
            "bhava_max": bhava.max(dim=-1).values.mean().item(),
            "bhava_min": bhava.min(dim=-1).values.mean().item(),
            "bhava_spread": (bhava.max(dim=-1).values - bhava.min(dim=-1).values).mean().item(),

            # Vritti (softmax → uniform = 1/5 = 0.2 each)
            "vritti_entropy": entropy(vritti).mean().item(),
            "vritti_max_entropy": math.log(5),
            "vritti_dist_from_uniform": distance_from_uniform(vritti),
            "vritti_max": vritti.max(dim=-1).values.mean().item(),
            "vritti_min": vritti.min(dim=-1).values.mean().item(),
            "vritti_spread": (vritti.max(dim=-1).values - vritti.min(dim=-1).values).mean().item(),

            # Guna (sigmoid → midpoint = 0.5 each)
            "guna_dist_from_midpoint": distance_from_midpoint(guna),
            "guna_mean": guna.mean().item(),
            "guna_std": guna.std().item(),
            "guna_max": guna.max(dim=-1).values.mean().item(),
            "guna_min": guna.min(dim=-1).values.mean().item(),
        }


# ═══════════════════════════════════════════════════════════════════════
# TEST 1: Gradient flow comparison — detach ON vs OFF
# ═══════════════════════════════════════════════════════════════════════

def test_gradient_flow():
    """Compare gradient norms: old (detached) vs fix (live)."""
    print("=" * 70)
    print("TEST 1: Gradient Flow Comparison")
    print("=" * 70)

    results = {}

    for mode_name, detach_state in [("OLD_detached", True), ("FIX_live", False)]:
        torch.manual_seed(SEED)
        state_proj, scorer, kosha_loss_fn, bliss_loss_fn = build_modules()
        hidden, T, candidate_ids, target_ids = make_batch()

        # Forward: hidden → state projector → sov_state
        pooled = hidden.mean(dim=1)  # [B, EMBED_DIM]
        sov_state = state_proj(pooled)  # [B, 32]

        # Expand to sequence length for scorer
        sov_state_seq = sov_state.unsqueeze(1).expand(-1, SEQ_LEN, -1)
        hidden_for_scorer = hidden.detach()  # Always detach hidden (Phase 3 design)

        # Apply detach on sov_state — this is the variable under test
        if detach_state:
            o_ctx = sov_state_seq.detach()
        else:
            o_ctx = sov_state_seq

        # IntegratedScorer: (T, hidden, o_ctx) → alpha, B, D
        integ_result = scorer(
            T=T,
            hidden=hidden_for_scorer,
            o_ctx=o_ctx,
        )
        alpha = integ_result["alpha"]
        B = integ_result["B"]
        D = integ_result["D"]

        # Compute losses (matching train.py)
        router_result = integ_result.get("router_result", {
            "alpha": alpha,
            "policy_logits": torch.zeros_like(alpha),
        })
        kr_result = kosha_loss_fn(
            router_result=router_result,
            T=T,
            target_ids=target_ids,
            candidate_ids=candidate_ids,
        )
        bl_result = bliss_loss_fn(B=B, D=D, target_ids=target_ids, candidate_ids=candidate_ids)

        total_loss = 0.01 * kr_result["loss"] + 0.01 * bl_result["loss"]

        # Backward
        total_loss.backward()

        # Measure
        sp_grad_norm = compute_sp_grad_norm(state_proj)
        router_grad_norm = (sum(
            p.grad.norm().item() ** 2
            for p in scorer.kosha_router.parameters()
            if p.grad is not None
        )) ** 0.5

        results[mode_name] = {
            "sp_grad_norm": sp_grad_norm,
            "router_grad_norm": router_grad_norm,
            "total_loss": total_loss.item(),
            "kosha_routing_loss": kr_result["loss"].item(),
            "bliss_loss": bl_result["loss"].item(),
        }

        print(f"\n  [{mode_name}]")
        print(f"    State projector grad norm:  {sp_grad_norm:.6f}")
        print(f"    Router grad norm:           {router_grad_norm:.6f}")
        print(f"    Total CG loss:              {total_loss.item():.6f}")
        print(f"    Kosha routing loss:         {kr_result['loss'].item():.6f}")
        print(f"    Bliss loss:                 {bl_result['loss'].item():.6f}")

    # Verdict
    old_grad = results["OLD_detached"]["sp_grad_norm"]
    fix_grad = results["FIX_live"]["sp_grad_norm"]
    print(f"\n  VERDICT:")
    print(f"    Old (detached) sp_grad_norm = {old_grad:.6f}")
    print(f"    Fix (live)     sp_grad_norm = {fix_grad:.6f}")

    if old_grad == 0.0 and fix_grad > 0.0:
        print(f"    --> PASS: Gradient flow unblocked. Fix works as intended.")
    elif old_grad > 0.0:
        print(f"    --> UNEXPECTED: Old path has nonzero grad (check TET path).")
    elif fix_grad == 0.0:
        print(f"    --> FAIL: Fix did not unblock gradient flow.")
    else:
        print(f"    --> PARTIAL: Both have nonzero grad, fix increased it.")

    return results


# ═══════════════════════════════════════════════════════════════════════
# TEST 2: State Evolution Over Training Steps
# ═══════════════════════════════════════════════════════════════════════

def test_state_evolution():
    """Run N optimization steps and track state slice movement."""
    print("\n" + "=" * 70)
    print(f"TEST 2: State Evolution Over {NUM_STEPS} Steps")
    print("=" * 70)

    torch.manual_seed(SEED)
    state_proj, scorer, kosha_loss_fn, bliss_loss_fn = build_modules()

    # Only optimize state projector + router (matching Phase 3)
    optimizer = optim.Adam(
        list(state_proj.parameters()) + list(scorer.parameters()),
        lr=LR,
    )

    # Track evolution
    history = []
    log_steps = [0, 1, 5, 10, 25, 50, 100, 150, NUM_STEPS - 1]

    for step in range(NUM_STEPS):
        optimizer.zero_grad()

        # Fresh batch each step (simulates different training samples)
        hidden, T, candidate_ids, target_ids = make_batch()

        # Forward
        pooled = hidden.mean(dim=1)
        sov_state = state_proj(pooled)
        sov_state_seq = sov_state.unsqueeze(1).expand(-1, SEQ_LEN, -1)

        # Phase 3 path WITH fix applied (no detach on sov_state)
        integ_result = scorer(
            T=T,
            hidden=hidden.detach(),
            o_ctx=sov_state_seq,  # LIVE — the fix
        )

        router_result = integ_result.get("router_result", {
            "alpha": integ_result["alpha"],
            "policy_logits": torch.zeros_like(integ_result["alpha"]),
        })
        kr_result = kosha_loss_fn(
            router_result=router_result,
            T=T,
            target_ids=target_ids,
            candidate_ids=candidate_ids,
        )
        bl_result = bliss_loss_fn(
            B=integ_result["B"],
            D=integ_result["D"],
            target_ids=target_ids,
            candidate_ids=candidate_ids,
        )

        total_loss = 0.01 * kr_result["loss"] + 0.01 * bl_result["loss"]
        total_loss.backward()

        sp_grad = compute_sp_grad_norm(state_proj)
        optimizer.step()

        # Log at selected steps
        if step in log_steps:
            stats = state_slice_stats(sov_state)
            stats["step"] = step
            stats["sp_grad_norm"] = sp_grad
            stats["total_loss"] = total_loss.item()
            history.append(stats)

            print(f"\n  Step {step:>3d} | loss={total_loss.item():.4f} | sp_grad={sp_grad:.4f}")
            print(f"    Bhava:  entropy={stats['bhava_entropy']:.3f}/{stats['bhava_max_entropy']:.3f}"
                  f"  spread={stats['bhava_spread']:.4f}"
                  f"  dist_from_uniform={stats['bhava_dist_from_uniform']:.4f}")
            print(f"    Vritti: entropy={stats['vritti_entropy']:.3f}/{stats['vritti_max_entropy']:.3f}"
                  f"  spread={stats['vritti_spread']:.4f}"
                  f"  dist_from_uniform={stats['vritti_dist_from_uniform']:.4f}")
            print(f"    Guna:   dist_from_midpoint={stats['guna_dist_from_midpoint']:.4f}"
                  f"  mean={stats['guna_mean']:.4f}  std={stats['guna_std']:.4f}")

    # Compare first vs last
    first = history[0]
    last = history[-1]
    print(f"\n  EVOLUTION SUMMARY (step 0 → step {NUM_STEPS - 1}):")
    print(f"    Bhava  dist_from_uniform:  {first['bhava_dist_from_uniform']:.4f} → {last['bhava_dist_from_uniform']:.4f}")
    print(f"    Vritti dist_from_uniform:  {first['vritti_dist_from_uniform']:.4f} → {last['vritti_dist_from_uniform']:.4f}")
    print(f"    Guna   dist_from_midpoint: {first['guna_dist_from_midpoint']:.4f} → {last['guna_dist_from_midpoint']:.4f}")
    print(f"    Bhava  entropy:            {first['bhava_entropy']:.4f} → {last['bhava_entropy']:.4f}")
    print(f"    Vritti entropy:            {first['vritti_entropy']:.4f} → {last['vritti_entropy']:.4f}")
    print(f"    Loss:                      {first['total_loss']:.4f} → {last['total_loss']:.4f}")
    print(f"    sp_grad_norm:              {first['sp_grad_norm']:.4f} → {last['sp_grad_norm']:.4f}")

    # Verdict
    bhava_moved = last["bhava_dist_from_uniform"] > first["bhava_dist_from_uniform"] * 1.1
    vritti_moved = last["vritti_dist_from_uniform"] > first["vritti_dist_from_uniform"] * 1.1
    guna_moved = last["guna_dist_from_midpoint"] > first["guna_dist_from_midpoint"] * 1.1
    grad_alive = last["sp_grad_norm"] > 1e-6

    print(f"\n  MOVEMENT VERDICTS:")
    print(f"    Bhava  moved away from uniform:   {'YES' if bhava_moved else 'NO'}")
    print(f"    Vritti moved away from uniform:   {'YES' if vritti_moved else 'NO'}")
    print(f"    Guna   moved away from midpoint:  {'YES' if guna_moved else 'NO'}")
    print(f"    Gradients alive at final step:    {'YES' if grad_alive else 'NO'}")

    return history


# ═══════════════════════════════════════════════════════════════════════
# TEST 3: Gradient Stability Check
# ═══════════════════════════════════════════════════════════════════════

def test_gradient_stability(history: list):
    """Check if gradients are stable (not vanishing or exploding)."""
    print("\n" + "=" * 70)
    print("TEST 3: Gradient Stability")
    print("=" * 70)

    grads = [h["sp_grad_norm"] for h in history]
    grad_mean = sum(grads) / len(grads)
    grad_max = max(grads)
    grad_min = min(grads)

    print(f"  sp_grad_norm over {len(history)} checkpoints:")
    print(f"    min:  {grad_min:.6f}")
    print(f"    max:  {grad_max:.6f}")
    print(f"    mean: {grad_mean:.6f}")

    vanishing = grad_mean < 1e-6
    exploding = grad_max > 100.0
    stable = not vanishing and not exploding

    print(f"\n  Vanishing: {'YES' if vanishing else 'NO'}")
    print(f"  Exploding: {'YES' if exploding else 'NO'}")
    print(f"  Stable:    {'YES' if stable else 'NO'}")

    return {
        "grad_min": grad_min,
        "grad_max": grad_max,
        "grad_mean": grad_mean,
        "vanishing": vanishing,
        "exploding": exploding,
        "stable": stable,
    }


# ═══════════════════════════════════════════════════════════════════════
# FINAL REPORT
# ═══════════════════════════════════════════════════════════════════════

def final_report(grad_results, history, stability):
    """Print the final go/no-go verdict."""
    print("\n" + "=" * 70)
    print("FINAL VERDICT")
    print("=" * 70)

    old_grad = grad_results["OLD_detached"]["sp_grad_norm"]
    fix_grad = grad_results["FIX_live"]["sp_grad_norm"]

    checks = {
        "gradient_unblocked": old_grad == 0.0 and fix_grad > 0.0,
        "gradients_stable": stability["stable"],
        "bhava_moving": history[-1]["bhava_dist_from_uniform"] > history[0]["bhava_dist_from_uniform"] * 1.1,
        "vritti_moving": history[-1]["vritti_dist_from_uniform"] > history[0]["vritti_dist_from_uniform"] * 1.1,
        "guna_moving": history[-1]["guna_dist_from_midpoint"] > history[0]["guna_dist_from_midpoint"] * 1.1,
    }

    for check, passed in checks.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {check}")

    all_pass = all(checks.values())
    core_pass = checks["gradient_unblocked"] and checks["gradients_stable"]

    print()
    if all_pass:
        print("  OVERALL: FIXED. State projector is now learning.")
        print("  -> Future real-checkpoint gate evaluations ARE worth doing.")
        verdict = "FIXED"
    elif core_pass:
        partial_moves = sum(1 for k in ["bhava_moving", "vritti_moving", "guna_moving"] if checks[k])
        print(f"  OVERALL: PARTIALLY FIXED. Gradients flow, {partial_moves}/3 slices moving.")
        print("  -> Gradient path is correct; slice movement may need more steps or real data.")
        print("  -> Future real-checkpoint gate evaluations ARE worth doing.")
        verdict = "PARTIALLY_FIXED"
    else:
        print("  OVERALL: STILL BLOCKED. Gradient path not working as expected.")
        print("  -> Another training-side fix is needed before checkpoint evaluation.")
        verdict = "STILL_BLOCKED"

    # Build summary dict
    summary = {
        "timestamp": datetime.now().isoformat(),
        "verdict": verdict,
        "checks": checks,
        "gradient_comparison": {
            "old_detached_sp_grad": old_grad,
            "fix_live_sp_grad": fix_grad,
        },
        "stability": {
            "grad_min": stability["grad_min"],
            "grad_max": stability["grad_max"],
            "grad_mean": stability["grad_mean"],
        },
        "evolution_step_0": {k: v for k, v in history[0].items()},
        "evolution_step_final": {k: v for k, v in history[-1].items()},
        "config": {
            "embed_dim": EMBED_DIM,
            "state_dim": STATE_DIM,
            "batch_size": BATCH_SIZE,
            "seq_len": SEQ_LEN,
            "num_steps": NUM_STEPS,
            "lr": LR,
        },
    }

    return summary


def main():
    print("Gradient-Unblock Calibration")
    print(f"Date: {datetime.now().isoformat()}")
    print(f"Config: embed_dim={EMBED_DIM}, state_dim={STATE_DIM}, "
          f"batch={BATCH_SIZE}, seq_len={SEQ_LEN}, steps={NUM_STEPS}, lr={LR}")

    # Test 1: Gradient flow comparison
    grad_results = test_gradient_flow()

    # Test 2: State evolution
    history = test_state_evolution()

    # Test 3: Gradient stability
    stability = test_gradient_stability(history)

    # Final report
    summary = final_report(grad_results, history, stability)

    # Save results
    out_dir = Path("eval_results/gradient_unblock_calibration")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "calibration_summary.json"
    with open(out_file, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n  Results saved to: {out_file}")


if __name__ == "__main__":
    main()
