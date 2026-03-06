#!/usr/bin/env python3
"""
Conscious Generation Phase Test CLI
====================================

Smoke-tests all 5 phases of the conscious generation pipeline:
  Phase 1: Token Ontology Projection
  Phase 2: Primitive Scoring Heads
  Phase 3: Governance Integration (Kosha + Bliss)
  Phase 4: Field-Integrated Generation (Z*, Two-Stage)
  Phase 5: Curriculum Stage Manager (A→B→C→D transitions)

Runs a short training loop (default 100 steps) with synthetic data to verify
that all modules instantiate, produce gradients, and stage transitions work.

Usage:
    python scripts/test_cg_phases.py                    # all phases, 100 steps
    python scripts/test_cg_phases.py --phases 1 2 3     # specific phases only
    python scripts/test_cg_phases.py --steps 50 --tiny  # fast run with tiny model
    python scripts/test_cg_phases.py --phase5-only      # only curriculum test
"""

import argparse
import sys
import time
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def make_config(args):
    """Build a UnifiedTrainingConfig for CG phase testing."""
    from symbolu.training.unified.config import UnifiedTrainingConfig

    # Lambda targets — non-zero so all losses activate
    lambdas = {
        "lambda_ont": 0.01,
        "lambda_kosha_routing": 0.01,
        "lambda_bliss_token": 0.01,
        "lambda_jepa_token": 0.01,
        "lambda_csr_token": 0.01,
        "lambda_vritti_token": 0.01,
        "lambda_guna_token": 0.01,
    }

    # Zero out lambdas for disabled phases
    phases = set(args.phases)
    if 1 not in phases:
        lambdas["lambda_ont"] = 0.0
    if 3 not in phases:
        for k in list(lambdas):
            if k != "lambda_ont":
                lambdas[k] = 0.0

    size = "tiny" if args.tiny else "small"
    config = UnifiedTrainingConfig(
        model_type="ontological",
        model_size=size,
        vocab_size=50257,
        max_seq_len=256,
        batch_size=args.batch_size,
        max_steps=args.steps,
        learning_rate=1e-4,
        warmup_steps=10,
        warmup_until_ppl=0,  # use fixed warmup
        eval_every=args.eval_every,
        log_every=10,
        save_every=999999,  # no checkpoints
        no_save=True,
        dataset="synthetic",
        mixed_precision="none",  # CPU-friendly
        quiet=True,
        # CG master toggle
        enable_conscious_generation=True,
        # Phase 1
        token_ontology_dim=32,
        ontology_cache_refresh_interval=50,
        ontology_loss_type="contrastive",
        ontology_loss_temperature=0.1,
        ontology_scorer_use_low_rank=True,
        ontology_scorer_rank=4,
        # Phase 2
        jepa_token_dim=8,
        csr_token_dim=8,
        primitive_shortlist_k=64,
        use_low_rank_primitives=True,
        primitive_rank=4,
        # Phase 4
        use_field_integrated_softmax=(4 in phases),
        field_softmax_temperature=1.0,
        use_agreement_energy=(4 in phases),
        agreement_energy_weight=0.1,
        # Phase 5
        enable_cg_curriculum=(5 in phases),
        cg_curriculum_ramp_mode="linear",
        cg_curriculum_ppl_var_threshold=2.0,  # relaxed for synthetic data
        cg_curriculum_stability_window=3,
        cg_curriculum_stage_proportions="0.25,0.25,0.25,0.25",
        enable_cg_diagnostics=(5 in phases),
        # Apply lambdas
        **lambdas,
    )
    return config


def test_phase1(config, model, device):
    """Phase 1: Token Ontology Projection — verify projector and cache work."""
    import torch

    print("\n" + "=" * 60)
    print("  Phase 1: Token Ontology Projection")
    print("=" * 60)

    checks = []

    # Check modules exist
    assert hasattr(model, "conscious_gen"), "model.conscious_gen missing"
    assert "token_projector" in model.conscious_gen, "token_projector missing"
    assert "token_cache" in model.conscious_gen, "token_cache missing"
    assert "ontology_scorer" in model.conscious_gen, "ontology_scorer missing"
    checks.append(("Modules instantiated", True))

    # Forward pass through projector
    projector = model.conscious_gen["token_projector"]
    hidden = torch.randn(2, 16, model.conscious_gen["token_projector"].project.in_features, device=device)
    o_tok = projector(hidden)
    assert o_tok.shape[-1] == config.token_ontology_dim, f"O_tok dim mismatch: {o_tok.shape[-1]} != {config.token_ontology_dim}"
    checks.append(("Projector forward", True))

    # Ontology scorer
    scorer = model.conscious_gen["ontology_scorer"]
    score = scorer(o_tok[:, :8], o_tok[:, 8:])
    assert score.shape == (2, 8, 8), f"Scorer shape: {score.shape}"
    checks.append(("OntologyScorer forward", True))

    # Gradient check
    loss = score.sum()
    loss.backward()
    has_grad = any(p.grad is not None and p.grad.abs().sum() > 0
                   for p in projector.parameters())
    checks.append(("Gradients flow", has_grad))
    model.zero_grad()

    for name, ok in checks:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")

    return all(ok for _, ok in checks)


def test_phase2(config, model, device):
    """Phase 2: Primitive Scoring Heads — verify all 6 primitives score tokens."""
    import torch

    print("\n" + "=" * 60)
    print("  Phase 2: Primitive Scoring Heads")
    print("=" * 60)

    checks = []
    B, S, K = 2, 16, config.primitive_shortlist_k

    for name in ["base_scorer", "jepa_scorer", "csr_scorer", "vritti_scorer", "guna_scorer"]:
        assert name in model.conscious_gen, f"{name} missing"
    checks.append(("All scorers instantiated", True))

    assert "token_eval_tensor" in model.conscious_gen, "token_eval_tensor missing"
    checks.append(("TokenEvaluationTensor instantiated", True))

    # Forward through token eval tensor
    tet = model.conscious_gen["token_eval_tensor"]
    embed_dim = model.conscious_gen["token_projector"].project.in_features
    hidden = torch.randn(B, S, embed_dim, device=device)
    base_logits = torch.randn(B, S, config.vocab_size, device=device)

    # Get top-K
    topk_logits, topk_ids = base_logits.topk(K, dim=-1)

    # Ontology projection
    o_tok = model.conscious_gen["token_projector"](hidden)

    # Score through TET
    Z_star = tet(hidden_states=hidden, o_tok=o_tok, base_logits=base_logits,
                 candidate_logits=topk_logits, candidate_ids=topk_ids)
    assert Z_star.shape == (B, S, K), f"Z_star shape {Z_star.shape} != ({B}, {S}, {K})"
    checks.append(("TokenEvaluationTensor forward", True))

    # Gradient check
    loss = Z_star.sum()
    loss.backward()
    tet_has_grad = any(p.grad is not None and p.grad.abs().sum() > 0
                       for p in tet.parameters())
    checks.append(("Gradients flow through TET", tet_has_grad))
    model.zero_grad()

    for name, ok in checks:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")

    return all(ok for _, ok in checks)


def test_phase3(config, model, device):
    """Phase 3: Governance Integration — Kosha router + Bliss gate."""
    import torch

    print("\n" + "=" * 60)
    print("  Phase 3: Governance Integration")
    print("=" * 60)

    checks = []

    for name in ["kosha_router", "bliss_gate", "integrated_scorer"]:
        assert name in model.conscious_gen, f"{name} missing"
    checks.append(("Governance modules instantiated", True))

    B, S, K = 2, 16, config.primitive_shortlist_k
    embed_dim = model.conscious_gen["token_projector"].project.in_features

    # Kosha router forward
    router = model.conscious_gen["kosha_router"]
    hidden = torch.randn(B, S, embed_dim, device=device)
    o_tok = model.conscious_gen["token_projector"](hidden)

    # Router needs hidden and o_tok
    weights = router(hidden, o_tok)
    assert weights.dim() >= 2, f"Router output dim: {weights.dim()}"
    checks.append(("KoshaRouter forward", True))

    # Bliss gate
    bliss = model.conscious_gen["bliss_gate"]
    scores = torch.randn(B, S, 6, device=device)  # 6 primitives
    gated = bliss(scores, o_tok)
    checks.append(("BlissGate forward", True))

    # Check loss modules exist
    loss_modules = []
    if "kosha_routing_loss" in model.conscious_gen:
        loss_modules.append("kosha_routing_loss")
    if "bliss_coherence_loss" in model.conscious_gen:
        loss_modules.append("bliss_coherence_loss")
    if "primitive_aux_losses" in model.conscious_gen:
        loss_modules.append("primitive_aux_losses")
    checks.append((f"Loss modules: {', '.join(loss_modules) or 'NONE'}", len(loss_modules) > 0))

    for name, ok in checks:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")

    return all(ok for _, ok in checks)


def test_phase4(config, model, device):
    """Phase 4: Field-Integrated Generation — Z*, two-stage generator."""
    import torch

    print("\n" + "=" * 60)
    print("  Phase 4: Field-Integrated Generation")
    print("=" * 60)

    checks = []

    for name in ["field_softmax", "two_stage_generator"]:
        present = name in model.conscious_gen
        checks.append((f"{name} instantiated", present))

    if not all(ok for _, ok in checks):
        for name, ok in checks:
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        return False

    B, S = 2, 16
    embed_dim = model.conscious_gen["token_projector"].project.in_features

    # Full two-stage generation forward
    gen = model.conscious_gen["two_stage_generator"]
    hidden = torch.randn(B, S, embed_dim, device=device)
    base_logits = torch.randn(B, S, config.vocab_size, device=device)
    o_tok = model.conscious_gen["token_projector"](hidden)

    Z_final = gen(hidden_states=hidden, o_tok=o_tok, base_logits=base_logits)
    assert Z_final.shape == (B, S, config.vocab_size), f"Z_final shape: {Z_final.shape}"
    checks.append(("TwoStageGenerator forward", True))

    # Field softmax standalone
    fs = model.conscious_gen["field_softmax"]
    K = config.primitive_shortlist_k
    topk_logits, topk_ids = base_logits.topk(K, dim=-1)
    Z_star = torch.randn(B, S, K, device=device)
    integrated = fs(base_logits=base_logits, Z_star=Z_star,
                    candidate_ids=topk_ids, candidate_logits=topk_logits)
    checks.append(("FieldIntegratedSoftmax forward", True))

    # Gradient flow
    loss = Z_final.sum()
    loss.backward()
    has_grad = any(p.grad is not None and p.grad.abs().sum() > 0
                   for p in gen.parameters())
    checks.append(("Gradients flow through generator", has_grad))
    model.zero_grad()

    for name, ok in checks:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")

    return all(ok for _, ok in checks)


def test_phase5(config):
    """Phase 5: Curriculum Stage Manager — test A→B→C→D transitions."""

    print("\n" + "=" * 60)
    print("  Phase 5: Curriculum Stage Manager")
    print("=" * 60)

    from symbolu.training.conscious_generation.curriculum.stages import CurriculumStageManager

    checks = []
    total_steps = config.max_steps

    target_lambdas = {
        "lambda_ont": 0.01,
        "lambda_kosha_routing": 0.01,
        "lambda_bliss_token": 0.01,
        "lambda_jepa_token": 0.01,
        "lambda_csr_token": 0.01,
        "lambda_vritti_token": 0.01,
        "lambda_guna_token": 0.01,
    }

    manager = CurriculumStageManager(
        target_lambdas=target_lambdas,
        total_steps=total_steps,
        stage_proportions=(0.25, 0.25, 0.25, 0.25),
        ppl_var_threshold=999.0,  # disable PPL gating for deterministic test
        stability_window=2,
        ramp_mode="linear",
    )
    checks.append(("CurriculumStageManager instantiated", True))

    # Simulate stepping through all stages
    stages_seen = set()
    stage_transitions = []

    for step in range(total_steps):
        lambdas = manager.step(step)
        stages_seen.add(manager.current_stage)

        # Feed stable PPL to allow transitions
        if step % 10 == 0:
            manager.update(step, ppl=50.0)

        if len(stage_transitions) == 0 or stage_transitions[-1][1] != manager.current_stage:
            stage_transitions.append((step, manager.current_stage))

    checks.append((f"Stages visited: {sorted(stages_seen)}", len(stages_seen) == 4))

    # Verify lambda values at end (Stage D should have all at target)
    final_lambdas = manager.step(total_steps - 1)
    all_positive = all(v > 0 for v in final_lambdas.values())
    checks.append(("Final lambdas all positive (Stage D)", all_positive))

    # Verify field-integrated softmax flag in Stage D
    checks.append(("Field-integrated active in Stage D", manager.use_field_integrated_softmax))

    # Print transition log
    print("  Stage transitions:")
    for step, stage in stage_transitions:
        print(f"    step {step:>5d} -> {stage}")

    print(f"  Final lambdas:")
    for k, v in sorted(final_lambdas.items()):
        print(f"    {k}: {v:.6f}")

    for name, ok in checks:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")

    return all(ok for _, ok in checks)


def test_training_loop(config):
    """Run a short training loop with all CG phases active."""
    import torch
    from symbolu.training.unified.model_factory import build_model
    from symbolu.training.unified.train import train

    print("\n" + "=" * 60)
    print("  Integration: Short Training Loop")
    print("=" * 60)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"  Device: {device}")
    print(f"  Steps: {config.max_steps}")
    print(f"  Eval every: {config.eval_every}")

    t0 = time.time()
    try:
        train(config)
        elapsed = time.time() - t0
        print(f"  [PASS] Training loop completed in {elapsed:.1f}s")
        return True
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  [FAIL] Training loop failed after {elapsed:.1f}s: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Test all conscious generation phases",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--phases", type=int, nargs="*", default=[1, 2, 3, 4, 5],
                       help="Which phases to test (default: 1 2 3 4 5)")
    parser.add_argument("--phase5-only", action="store_true",
                       help="Only test Phase 5 (curriculum) — no model needed")
    parser.add_argument("--steps", type=int, default=100,
                       help="Training steps for integration test (default: 100)")
    parser.add_argument("--eval-every", type=int, default=25,
                       help="Eval interval (default: 25)")
    parser.add_argument("--batch-size", type=int, default=4,
                       help="Batch size (default: 4)")
    parser.add_argument("--tiny", action="store_true",
                       help="Use tiny model size (faster)")
    parser.add_argument("--no-loop", action="store_true",
                       help="Skip integration training loop (unit tests only)")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Verbose output")

    args = parser.parse_args()

    if args.phase5_only:
        args.phases = [5]

    print("=" * 60)
    print("  Conscious Generation Phase Test")
    print(f"  Phases: {args.phases}")
    print(f"  Steps:  {args.steps} | Eval every: {args.eval_every}")
    print(f"  Model:  {'tiny' if args.tiny else 'small'}")
    print("=" * 60)

    config = make_config(args)
    results = {}

    # Phase 5 (curriculum) doesn't need a model
    if 5 in args.phases:
        results["Phase 5: Curriculum"] = test_phase5(config)

    # Phases 1-4 need a model
    model_phases = [p for p in args.phases if p in (1, 2, 3, 4)]
    if model_phases or (not args.no_loop and args.phases != [5]):
        import torch
        from symbolu.training.unified.model_factory import build_model

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"\n  Building model on {device}...")
        model = build_model(config, device)

        if 1 in model_phases:
            results["Phase 1: Token Ontology"] = test_phase1(config, model, device)
        if 2 in model_phases:
            results["Phase 2: Primitives"] = test_phase2(config, model, device)
        if 3 in model_phases:
            results["Phase 3: Governance"] = test_phase3(config, model, device)
        if 4 in model_phases:
            results["Phase 4: Field Integrated"] = test_phase4(config, model, device)

        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # Integration training loop
    if not args.no_loop and not args.phase5_only:
        results["Integration Loop"] = test_training_loop(config)

    # Summary
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    all_pass = True
    for name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")
        if not ok:
            all_pass = False

    if all_pass:
        print(f"\n  All {len(results)} tests passed.")
    else:
        failed = sum(1 for ok in results.values() if not ok)
        print(f"\n  {failed}/{len(results)} tests FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    main()
