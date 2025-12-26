#!/usr/bin/env python3
"""
Symbol-U Image Generation Test Script
======================================

Tests the image generation module with FLUX integration.

Usage:
    # Quick test (no GPU needed - tests coherence engines only)
    python test_image_generation.py --mode mock

    # Full test with FLUX (requires GPU + ~24GB VRAM)
    python test_image_generation.py --mode full

    # Test with FLUX schnell (faster, less VRAM)
    python test_image_generation.py --mode schnell

    # Test with FLUX on CPU (very slow, ~10+ minutes, no GPU required)
    python test_image_generation.py --mode cpu
"""

import argparse
import sys
import numpy as np
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_coherence_engines():
    """Test coherence engines without GPU/FLUX."""
    print("\n" + "="*60)
    print("Testing Coherence Engines (No GPU Required)")
    print("="*60)

    # Create mock layer states
    np.random.seed(42)
    layer_states = {
        i: np.random.randn(1, 64, 32, 32).astype(np.float32)
        for i in range(1, 13)
    }
    latents = np.random.randn(1, 4, 128, 128).astype(np.float32)

    # Test BCVF
    print("\n[1/4] Testing BCVF Engine...")
    from symbolu.image_gen import BCVFImageEngine

    bcvf = BCVFImageEngine()
    score = bcvf.score(
        latents=latents,
        prompt="A beautiful mountain landscape",
    )
    print(f"  Forward score (sf): {score.forward_score:.3f}")
    print(f"  Backward score (sb): {score.backward_score:.3f}")
    print(f"  Lagrangian (L): {score.lagrangian:.3f}")
    print(f"  Consistency weight (w): {score.consistency_weight:.3f}")
    print(f"  Quality: {score.quality_category}")
    print("  ✓ BCVF Engine OK")

    # Test USE
    print("\n[2/4] Testing USE Engine...")
    from symbolu.image_gen import USEImageEngine

    use = USEImageEngine()
    phases = use.extract_phases(layer_states)
    coherence = use.compute_total_coherence(phases=phases)
    sync_result = use.synchronize(phases=phases, num_steps=3)

    print(f"  Phase coherence: {coherence:.3f}")
    print(f"  After sync: {sync_result.final_coherence:.3f}")
    print(f"  Improvement: {sync_result.improvement:.3f}")
    print("  ✓ USE Engine OK")

    # Test SCC
    print("\n[3/4] Testing SCC Engine...")
    from symbolu.image_gen import SCCImageEngine

    scc = SCCImageEngine()
    global_result = scc.compute_global_coherence(layer_states)

    print(f"  Global coherence: {global_result.global_coherence:.3f}")
    print(f"  Mean layer coherence: {global_result.mean_coherence:.3f}")
    print(f"  Weakest layers: {global_result.weakest_layers}")
    print(f"  Quality: {global_result.quality}")
    print("  ✓ SCC Engine OK")

    # Test Extended SCC (S6-S9)
    print("\n[4/4] Testing Extended SCC Engine (S6-S9)...")
    from symbolu.image_gen import ExtendedSCCImageEngine

    ext_scc = ExtendedSCCImageEngine()

    # S6: Integrated Information
    ii_result = ext_scc.compute_integrated_information(layer_states)
    print(f"  S6 - Integrated Info (Φ): {ii_result.phi:.3f}")

    # S7: Bidirectional Consistency
    bidir = ext_scc.compute_bidirectional_consistency(layer_states, layer_idx=6)
    print(f"  S7 - Bidir Consistency (L6): R={bidir.R:.3f}, C_up={bidir.C_up:.3f}, C_down={bidir.C_down:.3f}")

    # S8-S9: Constraints (need multiple recordings)
    ext_scc.constraint_checker.record_state(layer_states)
    # Simulate second state
    layer_states_2 = {i: s * 1.01 for i, s in layer_states.items()}
    constraints = ext_scc.check_constraints(layer_states_2)
    print(f"  S8 - Stability: {constraints.stability.is_stable}")
    print(f"  S9 - Drift: {constraints.drift.within_bounds}")
    print("  ✓ Extended SCC Engine OK")

    # Full analysis
    print("\n[Bonus] Full Analysis...")
    analysis = ext_scc.full_analysis(layer_states)
    print(f"  Global coherence: {analysis['global_coherence']:.3f}")
    print(f"  Integrated info: {analysis['integrated_information']['phi']:.3f}")
    print(f"  Constraints satisfied: {analysis['constraints']['all_satisfied']}")

    print("\n" + "="*60)
    print("All Coherence Engine Tests PASSED ✓")
    print("="*60)


def test_coherence_monitor():
    """Test the coherence monitor."""
    print("\n" + "="*60)
    print("Testing Coherence Monitor")
    print("="*60)

    from symbolu.image_gen import CoherenceMonitor, GenerationMode

    # Create monitor
    monitor = CoherenceMonitor(mode=GenerationMode.BALANCED)
    monitor.set_prompt("A majestic eagle soaring over mountains")

    # Simulate generation timesteps
    np.random.seed(42)
    print("\nSimulating 5 generation timesteps...")

    for t in range(5):
        layer_states = {
            i: np.random.randn(1, 64, 32, 32).astype(np.float32) * (1 - t*0.1)
            for i in range(1, 13)
        }
        latents = np.random.randn(1, 4, 128, 128).astype(np.float32)

        metrics = monitor.record_timestep(
            timestep=t,
            latents=latents,
            layer_states=layer_states,
        )

        print(f"  t={t}: combined_weight={metrics.combined_weight:.3f}, "
              f"issues={len(metrics.issues)}")

    # Get final decision
    decision = monitor.get_generation_result()
    print(f"\nFinal Decision:")
    print(f"  Should accept: {decision.should_accept}")
    print(f"  Confidence: {decision.confidence:.3f}")
    print(f"  Category: {decision.category}")
    print(f"  Completion weight: {decision.completion_weight:.3f}")

    if decision.recommendations:
        print(f"  Recommendations: {decision.recommendations[:2]}")

    print("\n✓ Coherence Monitor OK")


def test_with_flux(model_variant="dev"):
    """Test with actual FLUX model (requires GPU)."""
    print("\n" + "="*60)
    print(f"Testing with FLUX.1-{model_variant} (Requires GPU)")
    print("="*60)

    try:
        import torch
        if not torch.cuda.is_available():
            print("ERROR: CUDA not available. Use --mode mock for CPU testing.")
            return False

        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    except ImportError:
        print("ERROR: PyTorch not installed. Run: pip install torch")
        return False

    try:
        from symbolu.image_gen import (
            SymbolUFluxPipeline,
            ImageGenConfig,
            GenerationMode,
        )

        # Configure based on variant
        if model_variant == "schnell":
            model_id = "black-forest-labs/FLUX.1-schnell"
            steps = 4
        else:
            model_id = "black-forest-labs/FLUX.1-dev"
            steps = 20

        print(f"\nLoading {model_id}...")
        print("(This may take a few minutes on first run)")

        # Create pipeline
        config = ImageGenConfig(
            mode=GenerationMode.BALANCED,
            num_inference_steps=steps,
            width=512,  # Smaller for testing
            height=512,
        )
        config.flux.model_id = model_id
        config.flux.enable_model_cpu_offload = True  # Save VRAM

        pipeline = SymbolUFluxPipeline.from_pretrained(config=config)

        # Generate
        prompt = "A majestic eagle soaring over snow-capped mountains at sunset, photorealistic"
        print(f"\nGenerating: '{prompt}'")

        result = pipeline.generate(
            prompt=prompt,
            seed=42,
        )

        if result.success:
            print(f"\n✓ Generation Successful!")
            print(f"  Confidence: {result.confidence}")
            print(f"  Global coherence: {result.metrics.global_coherence:.3f}")
            print(f"  Prompt alignment: {result.metrics.prompt_alignment:.3f}")
            print(f"  Quality score: {result.metrics.quality_score:.3f}")
            print(f"  Completion weight: {result.metrics.completion_weight:.3f}")
            print(f"  Generation time: {result.generation_time_ms:.0f}ms")

            # Save image
            output_path = Path(__file__).parent / "test_output.png"
            result.image.save(output_path)
            print(f"\n  Image saved to: {output_path}")

            # Show layer coherences
            print("\n  Layer Coherences:")
            for layer, coh in list(result.layer_coherences.items())[:6]:
                print(f"    {layer}: {coh:.3f}")

            return True
        else:
            print(f"\n✗ Generation Failed: {result.error_message}")
            return False

    except ImportError as e:
        print(f"ERROR: Missing dependency: {e}")
        print("Run: pip install diffusers transformers accelerate")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False


def test_with_flux_cpu():
    """Test with FLUX model on CPU (very slow but works without GPU)."""
    print("\n" + "="*60)
    print("Testing with FLUX.1-schnell on CPU")
    print("="*60)
    print("\nWARNING: CPU mode is VERY SLOW (~10-30 minutes per image)")
    print("This is only for testing when no GPU is available.\n")

    try:
        import torch
        print(f"PyTorch version: {torch.__version__}")
        print(f"Using device: CPU")
        print(f"RAM will be used instead of VRAM\n")

    except ImportError:
        print("ERROR: PyTorch not installed. Run: pip install torch")
        return False

    try:
        from symbolu.image_gen import (
            SymbolUFluxPipeline,
            ImageGenConfig,
            GenerationMode,
        )

        # Use schnell variant (faster) with minimal settings for CPU
        model_id = "black-forest-labs/FLUX.1-schnell"
        steps = 2  # Minimal steps for CPU testing

        print(f"Loading {model_id}...")
        print("(This may take several minutes - downloading ~23GB model)")
        print("(The model will be cached for future runs)\n")

        # Create pipeline with CPU-optimized settings
        config = ImageGenConfig(
            mode=GenerationMode.SPEED,  # Fastest mode
            num_inference_steps=steps,
            width=256,   # Small size for CPU
            height=256,
        )
        config.flux.model_id = model_id
        config.flux.device = "cpu"
        config.flux.torch_dtype = "float32"  # CPU requires float32
        config.flux.enable_model_cpu_offload = False  # Already on CPU

        pipeline = SymbolUFluxPipeline.from_pretrained(config=config)

        # Generate with a simple prompt
        prompt = "A simple red apple on a white background"
        print(f"Generating: '{prompt}'")
        print("Please wait... this will take 10-30 minutes on CPU...")

        import time
        start_time = time.time()

        result = pipeline.generate(
            prompt=prompt,
            seed=42,
        )

        elapsed = time.time() - start_time

        if result.success:
            print(f"\n✓ Generation Successful!")
            print(f"  Time elapsed: {elapsed/60:.1f} minutes")
            print(f"  Confidence: {result.confidence}")
            print(f"  Global coherence: {result.metrics.global_coherence:.3f}")
            print(f"  Prompt alignment: {result.metrics.prompt_alignment:.3f}")
            print(f"  Quality score: {result.metrics.quality_score:.3f}")

            # Save image
            output_path = Path(__file__).parent / "test_output_cpu.png"
            result.image.save(output_path)
            print(f"\n  Image saved to: {output_path}")

            return True
        else:
            print(f"\n✗ Generation Failed: {result.error_message}")
            return False

    except ImportError as e:
        print(f"ERROR: Missing dependency: {e}")
        print("Run: pip install diffusers transformers accelerate")
        return False
    except Exception as e:
        import traceback
        print(f"ERROR: {e}")
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="Test Symbol-U Image Generation")
    parser.add_argument(
        "--mode",
        choices=["mock", "schnell", "full", "cpu"],
        default="mock",
        help="Test mode: mock (no GPU), schnell (fast FLUX), full (FLUX dev), cpu (FLUX on CPU)"
    )
    args = parser.parse_args()

    print("="*60)
    print("Symbol-U Image Generation Test Suite")
    print("="*60)

    # Always test coherence engines
    test_coherence_engines()
    test_coherence_monitor()

    # Test with FLUX if requested
    if args.mode in ["schnell", "full"]:
        variant = "schnell" if args.mode == "schnell" else "dev"
        success = test_with_flux(variant)
        if not success:
            sys.exit(1)
    elif args.mode == "cpu":
        success = test_with_flux_cpu()
        if not success:
            sys.exit(1)

    print("\n" + "="*60)
    print("ALL TESTS COMPLETED ✓")
    print("="*60)


if __name__ == "__main__":
    main()
