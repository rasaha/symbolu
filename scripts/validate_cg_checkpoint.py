#!/usr/bin/env python3
"""
Validate Conscious Generation Checkpoint — Stages 0-8
=====================================================

Post-training validation script that loads a checkpoint and verifies all
CG modules are healthy and producing meaningful signals.

Checks:
  Stage 0: State Projector norm, output distribution
  Phase 1: Token Ontology — projector weight health
  Phase 2: Primitive Scoring — cache population, scorer outputs
  Phase 3: Governance — Kosha router, Bliss gate weights
  Phase 4: Field-Integrated Generation — field softmax presence
  Stage 8: Perspective Synthesizer — gate value, conditioning norm,
           interpretive state distributions

Usage:
    python scripts/validate_cg_checkpoint.py checkpoints_mistral_cg/best.pt
    python scripts/validate_cg_checkpoint.py checkpoints_mistral_cg/final.pt --verbose
    python scripts/validate_cg_checkpoint.py checkpoints_mistral_cg/last.pt --run-forward
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Auto-detect project root and add to sys.path so 'import symbolu' works
# regardless of where the script is invoked from.
_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import torch
import torch.nn as nn


def load_state_dict_from_checkpoint(path: Path) -> Dict[str, Any]:
    """Load model state_dict from checkpoint (handles split format)."""
    stem = path.parent / path.stem
    model_path = Path(f"{stem}_model.pt")

    if model_path.exists():
        print(f"  Loading split checkpoint: {stem}_*.pt")
        state_dict = torch.load(model_path, map_location="cpu", weights_only=False)
        meta_path = Path(f"{stem}_meta.pt")
        meta = torch.load(meta_path, map_location="cpu", weights_only=False) if meta_path.exists() else {}
        return state_dict, meta
    elif path.exists():
        print(f"  Loading single-file checkpoint: {path}")
        ckpt = torch.load(path, map_location="cpu", weights_only=False)
        state_dict = ckpt.get("model", ckpt)
        meta = {k: v for k, v in ckpt.items() if k != "model"}
        return state_dict, meta
    else:
        raise FileNotFoundError(f"Checkpoint not found: {path}")


def check_parameter_health(
    name: str, tensor: torch.Tensor, verbose: bool = False
) -> Tuple[List[str], List[str]]:
    """Check a parameter tensor for NaN, Inf, zero, and distribution issues.

    Returns (failures, warnings) — only failures indicate real problems.
    """
    failures = []
    warnings = []
    if torch.isnan(tensor).any():
        failures.append(f"  FAIL: {name} contains NaN values")
    if torch.isinf(tensor).any():
        failures.append(f"  FAIL: {name} contains Inf values")
    if tensor.numel() > 0 and tensor.abs().max().item() == 0:
        # Zero bias vectors are normal (default init), only warn
        warnings.append(f"  WARN: {name} is all zeros")
    if verbose and tensor.numel() > 1:
        print(f"    {name}: shape={list(tensor.shape)}, "
              f"mean={tensor.float().mean():.6f}, std={tensor.float().std():.6f}, "
              f"min={tensor.float().min():.6f}, max={tensor.float().max():.6f}")
    return failures, warnings


def validate_stage0(state_dict: Dict, verbose: bool) -> Tuple[int, int, List[str]]:
    """Stage 0: State Projector — maps hidden to sovereign state."""
    passed = 0
    failed = 0
    issues = []

    # Look for state projector weights
    proj_keys = [k for k in state_dict if "state_projector" in k.lower()]
    if not proj_keys:
        # Mistral CG: check for state_projector directly
        proj_keys = [k for k in state_dict if "state_projector" in k]

    if proj_keys:
        print(f"  Found {len(proj_keys)} state projector parameters")
        for k in proj_keys:
            param_fails, param_warns = check_parameter_health(k, state_dict[k], verbose)
            issues.extend(param_fails + param_warns)
            if param_fails:
                failed += 1
            else:
                passed += 1
    else:
        issues.append("  SKIP: No state projector found (may be non-CG model)")
        return 0, 0, issues

    return passed, failed, issues


def validate_phase1(state_dict: Dict, verbose: bool) -> Tuple[int, int, List[str]]:
    """Phase 1: Token Ontology — ontological projection."""
    passed = 0
    failed = 0
    issues = []

    ont_keys = [k for k in state_dict if "conscious_gen.token_ontology" in k
                or "conscious_gen.ontology_loss" in k]

    if not ont_keys:
        issues.append("  SKIP: No token ontology modules found")
        return 0, 0, issues

    print(f"  Found {len(ont_keys)} token ontology parameters")
    for k in ont_keys:
        param_fails, param_warns = check_parameter_health(k, state_dict[k], verbose)
        issues.extend(param_fails + param_warns)
        if param_fails:
            failed += 1
        else:
            passed += 1

    return passed, failed, issues


def validate_phase2(state_dict: Dict, verbose: bool) -> Tuple[int, int, List[str]]:
    """Phase 2: Primitive Scoring — primitive scorers and token cache."""
    passed = 0
    failed = 0
    issues = []

    # Check for token_eval_tensor (the primitive cache)
    cache_keys = [k for k in state_dict if "token_eval_tensor" in k]
    scorer_keys = [k for k in state_dict if "conscious_gen.integrated_scorer" in k]

    if not scorer_keys and not cache_keys:
        issues.append("  SKIP: No primitive scoring modules found")
        return 0, 0, issues

    if cache_keys:
        for k in cache_keys:
            t = state_dict[k]
            nonzero_ratio = (t.abs() > 1e-8).float().mean().item()
            print(f"  Token cache: shape={list(t.shape)}, "
                  f"populated={nonzero_ratio*100:.1f}%")
            if nonzero_ratio < 0.01:
                issues.append(f"  WARN: Token cache is <1% populated ({k})")
            else:
                passed += 1

    for k in scorer_keys:
        param_fails, param_warns = check_parameter_health(k, state_dict[k], verbose)
        issues.extend(param_fails + param_warns)
        if param_fails:
            failed += 1
        else:
            passed += 1

    return passed, failed, issues


def validate_phase3(state_dict: Dict, verbose: bool) -> Tuple[int, int, List[str]]:
    """Phase 3: Governance — Kosha router, Bliss gate."""
    passed = 0
    failed = 0
    issues = []

    kosha_keys = [k for k in state_dict if "conscious_gen.kosha_router" in k]
    bliss_keys = [k for k in state_dict if "conscious_gen.bliss_gate" in k]

    if not kosha_keys and not bliss_keys:
        issues.append("  SKIP: No governance modules found")
        return 0, 0, issues

    print(f"  Kosha router: {len(kosha_keys)} params, Bliss gate: {len(bliss_keys)} params")
    for k in kosha_keys + bliss_keys:
        param_fails, param_warns = check_parameter_health(k, state_dict[k], verbose)
        issues.extend(param_fails + param_warns)
        if param_fails:
            failed += 1
        else:
            passed += 1

    return passed, failed, issues


def validate_phase4(state_dict: Dict, verbose: bool) -> Tuple[int, int, List[str]]:
    """Phase 4: Field-Integrated Generation."""
    passed = 0
    failed = 0
    issues = []

    field_keys = [k for k in state_dict if "conscious_gen.field_softmax" in k]

    if not field_keys:
        issues.append("  SKIP: No field softmax module found")
        return 0, 0, issues

    print(f"  Field softmax: {len(field_keys)} params")
    for k in field_keys:
        param_fails, param_warns = check_parameter_health(k, state_dict[k], verbose)
        issues.extend(param_fails + param_warns)
        if param_fails:
            failed += 1
        else:
            passed += 1

    return passed, failed, issues


def validate_stage8(state_dict: Dict, verbose: bool) -> Tuple[int, int, List[str]]:
    """Stage 8: Perspective Synthesizer — interpretive conditioning."""
    passed = 0
    failed = 0
    issues = []

    # Look for perspective synthesizer keys in conscious_gen or _perspective_synthesizer
    synth_keys = [k for k in state_dict
                  if "perspective_synthesizer" in k
                  or "_perspective_synthesizer" in k]

    if not synth_keys:
        issues.append("  SKIP: No Perspective Synthesizer found (Stage 8 not enabled)")
        return 0, 0, issues

    print(f"  Found {len(synth_keys)} perspective synthesizer parameters")

    # Categorize by sub-module
    builder_keys = [k for k in synth_keys if "state_builder" in k]
    conditioner_keys = [k for k in synth_keys if "conditioner" in k]

    print(f"    InterpretiveStateBuilder: {len(builder_keys)} params")
    print(f"    InterpretiveConditioner:  {len(conditioner_keys)} params")

    # Check gate parameter specifically
    gate_keys = [k for k in synth_keys if "gate" in k.lower() and "weight" not in k.lower()]
    for k in gate_keys:
        gate_val = state_dict[k]
        if gate_val.numel() == 1:
            raw = gate_val.item()
            activated = torch.sigmoid(gate_val).item()
            print(f"    Synthesis gate: raw={raw:.6f}, sigmoid={activated:.6f}")
            if activated < 0.001:
                issues.append(f"  INFO: Synthesis gate near zero ({activated:.6f}) — "
                              "conditioning is minimal (expected early in training)")
            elif activated > 0.99:
                issues.append(f"  WARN: Synthesis gate saturated ({activated:.6f}) — "
                              "may indicate training instability")
            passed += 1

    # Check all synthesis params for health
    for k in synth_keys:
        param_fails, param_warns = check_parameter_health(k, state_dict[k], verbose)
        issues.extend(param_fails + param_warns)
        if param_fails:
            failed += 1
        else:
            passed += 1

    # Check for zero-init final layer (synthesis MLP last layer should start near zero)
    final_layer_keys = [k for k in synth_keys
                        if ("synthesis_mlp" in k or "project_out" in k)
                        and "weight" in k]
    for k in final_layer_keys:
        w = state_dict[k]
        w_norm = w.float().norm().item()
        if verbose:
            print(f"    Final layer {k}: norm={w_norm:.6f}")
        if w_norm < 1e-6:
            print(f"    Final layer still at zero-init (norm={w_norm:.6f})")

    return passed, failed, issues


def validate_phase_adapter(state_dict: Dict, verbose: bool) -> Tuple[int, int, List[str]]:
    """Phase Adapter — gated residual adapter (Mistral CG)."""
    passed = 0
    failed = 0
    issues = []

    adapter_keys = [k for k in state_dict if "phase_adapter" in k]
    if not adapter_keys:
        issues.append("  SKIP: No phase adapter found (not Mistral CG)")
        return 0, 0, issues

    print(f"  Phase adapter: {len(adapter_keys)} params")

    # Check adapter gate
    gate_keys = [k for k in adapter_keys if "gate" in k.lower()]
    for k in gate_keys:
        g = state_dict[k]
        if g.numel() == 1:
            print(f"    Adapter gate: {torch.sigmoid(g).item():.6f}")

    for k in adapter_keys:
        param_fails, param_warns = check_parameter_health(k, state_dict[k], verbose)
        issues.extend(param_fails + param_warns)
        if param_fails:
            failed += 1
        else:
            passed += 1

    return passed, failed, issues


def print_section(title: str, passed: int, failed: int, issues: List[str]):
    """Print a validation section result."""
    total = passed + failed
    if total == 0 and issues:
        # Skip section
        for i in issues:
            print(i)
        return

    status = "PASS" if failed == 0 else "FAIL"
    symbol = "+" if failed == 0 else "X"
    print(f"  [{symbol}] {title}: {passed}/{total} params OK", end="")
    if failed > 0:
        print(f" ({failed} FAILED)")
    else:
        print()

    for i in issues:
        print(i)


def main():
    parser = argparse.ArgumentParser(
        description="Validate CG checkpoint health (Stages 0-8)"
    )
    parser.add_argument("checkpoint", type=str, help="Path to checkpoint file")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print per-parameter statistics")
    parser.add_argument("--run-forward", action="store_true",
                        help="Run a forward pass with synthetic data to verify outputs")
    args = parser.parse_args()

    path = Path(args.checkpoint)
    print("=" * 70)
    print("  CG Checkpoint Validation — Stages 0-8")
    print("=" * 70)

    # Load checkpoint
    try:
        state_dict, meta = load_state_dict_from_checkpoint(path)
    except (FileNotFoundError, RuntimeError) as e:
        print(f"\n  ERROR: {e}")
        sys.exit(1)

    # Print meta info
    step = meta.get("step", "?")
    best_val = meta.get("best_val_loss", "?")
    print(f"\n  Step: {step}")
    print(f"  Best val loss: {best_val}")
    print(f"  Total parameters in state_dict: {len(state_dict)}")

    # Count trainable CG params
    cg_keys = [k for k in state_dict
                if any(x in k for x in [
                    "conscious_gen", "state_projector", "phase_adapter",
                    "perspective_synthesizer", "_perspective_synthesizer"
                ])]
    cg_params = sum(state_dict[k].numel() for k in cg_keys)
    print(f"  CG-related parameters: {len(cg_keys)} tensors, {cg_params:,} values")

    # Run validations
    total_passed = 0
    total_failed = 0
    all_issues = []

    validators = [
        ("Stage 0: State Projector", validate_stage0),
        ("Phase 1: Token Ontology", validate_phase1),
        ("Phase 2: Primitive Scoring", validate_phase2),
        ("Phase 3: Governance", validate_phase3),
        ("Phase 4: Field Integration", validate_phase4),
        ("Phase Adapter (Mistral)", validate_phase_adapter),
        ("Stage 8: Perspective Synthesizer", validate_stage8),
    ]

    print("\n" + "-" * 70)
    for title, validator in validators:
        print(f"\n  {title}")
        p, f, issues = validator(state_dict, args.verbose)
        print_section(title, p, f, issues)
        total_passed += p
        total_failed += f
        all_issues.extend(issues)

    # Forward pass test
    if args.run_forward:
        print(f"\n  {'='*50}")
        print("  Running forward pass with synthetic data...")
        _run_forward_test(state_dict, meta, args.verbose)

    # Summary
    print("\n" + "=" * 70)
    warns = sum(1 for i in all_issues if "WARN" in i)
    infos = sum(1 for i in all_issues if "INFO" in i)
    fails = sum(1 for i in all_issues if "FAIL" in i)
    skips = sum(1 for i in all_issues if "SKIP" in i)

    if total_failed == 0 and fails == 0:
        print(f"  RESULT: ALL CHECKS PASSED")
    else:
        print(f"  RESULT: {fails} FAILURES DETECTED")

    print(f"  Params OK: {total_passed} | Failed: {total_failed} | "
          f"Warnings: {warns} | Info: {infos} | Skipped: {skips}")
    print("=" * 70)

    sys.exit(1 if fails > 0 else 0)


def _run_forward_test(state_dict: Dict, meta: Dict, verbose: bool):
    """Run a synthetic forward pass to verify CG modules produce output."""
    try:
        has_synth = any("perspective_synthesizer" in k for k in state_dict)

        if not has_synth:
            print("    Stage 8 not present — skipping forward test")
            return

        from symbolu.inference.perspective_synthesizer import (
            PerspectiveSynthesizer, PerspectiveSynthesizerConfig,
        )

        # Find a consistent prefix (conscious_gen.perspective_synthesizer. or
        # _perspective_synthesizer.) — use the first one found
        synth_prefix = None
        for k in state_dict:
            if "perspective_synthesizer." in k:
                synth_prefix = k[:k.index("perspective_synthesizer.") + len("perspective_synthesizer.")]
                break

        if not synth_prefix:
            print("    Could not find synthesizer prefix in state_dict")
            return

        # Extract sub-state_dict for loading
        synth_state = {
            k[len(synth_prefix):]: v
            for k, v in state_dict.items()
            if k.startswith(synth_prefix)
        }

        # Infer dimensions from checkpoint weights:
        #   conditioner.synthesis.0.weight: [d_synthesis, interp_dim]
        #   conditioner.synthesis.2.weight: [hidden_dim, d_synthesis]
        #   state_builder.csr_proj.0.weight: [intermediate, hidden_dim + onto_dim]
        #   state_builder.vritti_proj.weight: [vritti_classes, hidden_dim + onto_dim]
        #   state_builder.kosha_proj.2.weight: [kosha_primitives, intermediate]
        #   state_builder.bhava_compressor.compressor.0.weight: [intermediate, bhava_input_dim]

        synth_0_w = synth_state.get("conditioner.synthesis.0.weight")  # [d_synth, interp_dim]
        synth_2_w = synth_state.get("conditioner.synthesis.2.weight")  # [hidden_dim, d_synth]
        csr_0_w = synth_state.get("state_builder.csr_proj.0.weight")   # [inter, hidden+onto]
        vritti_w = synth_state.get("state_builder.vritti_proj.weight")  # [vritti, hidden+onto]
        kosha_2_w = synth_state.get("state_builder.kosha_proj.2.weight")  # [kosha, inter]
        bhava_0_w = synth_state.get("state_builder.bhava_compressor.compressor.0.weight")  # [inter, bhava_in]
        bhava_2_w = synth_state.get("state_builder.bhava_compressor.compressor.2.weight")  # [bhava_out, inter]

        if synth_2_w is None or synth_0_w is None:
            print("    Could not infer dimensions — missing conditioner weights")
            return

        hidden_dim = synth_2_w.shape[0]      # e.g. 4096
        d_synthesis = synth_2_w.shape[1]      # e.g. 64
        interp_dim = synth_0_w.shape[1]       # e.g. 43
        vritti_classes = vritti_w.shape[0] if vritti_w is not None else 5
        kosha_primitives = kosha_2_w.shape[0] if kosha_2_w is not None else 6
        bhava_input_dim = bhava_0_w.shape[1] if bhava_0_w is not None else 144
        bhava_output_dim = bhava_2_w.shape[0] if bhava_2_w is not None else 16

        # Infer onto_dim: csr_proj input = hidden_dim + onto_dim
        if csr_0_w is not None:
            onto_dim = csr_0_w.shape[1] - hidden_dim
            if onto_dim < 0:
                onto_dim = 12  # fallback
        else:
            onto_dim = 12

        # Compute csr_dim from interp_dim and known components
        csr_dim = interp_dim - vritti_classes - kosha_primitives - bhava_output_dim
        if csr_dim <= 0:
            csr_dim = 16

        print(f"    Inferred dimensions: hidden={hidden_dim}, d_synthesis={d_synthesis}, "
              f"interp={interp_dim}, onto={onto_dim}")
        print(f"    Components: csr={csr_dim}, vritti={vritti_classes}, "
              f"kosha={kosha_primitives}, bhava_out={bhava_output_dim}")

        config = PerspectiveSynthesizerConfig(
            enable=True,
            d_synthesis=d_synthesis,
            csr_dim=csr_dim,
            vritti_classes=vritti_classes,
            kosha_primitives=kosha_primitives,
            bhava_output_dim=bhava_output_dim,
            bhava_input_dim=bhava_input_dim,
            onto_dim=onto_dim,
        )
        synth = PerspectiveSynthesizer(config, hidden_dim=hidden_dim)
        synth.load_state_dict(synth_state, strict=True)
        synth.eval()

        # Synthetic forward pass
        B, T = 2, 8
        hidden = torch.randn(B, T, hidden_dim)
        onto_state = torch.randn(B, T, onto_dim)
        bhava_matrix = torch.randn(B, bhava_input_dim)

        with torch.no_grad():
            result = synth(hidden, onto_state, bhava_matrix)

        conditioned = result["conditioned_hidden"]
        delta_norm = (conditioned - hidden).norm(dim=-1).mean().item()
        gate = result["gate_value"]

        print(f"    Stage 8 forward pass OK")
        print(f"      Output shape: {list(conditioned.shape)}")
        print(f"      Gate value: {gate:.6f}")
        print(f"      Conditioning delta norm: {delta_norm:.6f}")

        if result.get("log_dict"):
            log = result["log_dict"]
            if "vritti_dominant" in log:
                print(f"      Vritti dominant: {log['vritti_dominant']}")
            if "kosha_primary" in log:
                print(f"      Kosha primary: {log['kosha_primary']}")

    except Exception as e:
        print(f"    Forward test failed: {type(e).__name__}: {e}")
        if verbose:
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
