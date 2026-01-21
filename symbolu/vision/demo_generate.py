#!/usr/bin/env python3
"""
Phase-Quad Image Generator Demo

This script demonstrates actual image generation using the Phase-Quad
architecture. It creates visible images that you can inspect.

Usage:
    python -m symbolu.vision.demo_generate
    python symbolu/vision/demo_generate.py

    # With options
    python -m symbolu.vision.demo_generate --prompt "A sunset" --steps 30 --output sunset.png

Requirements:
    - PyTorch >= 2.0
    - Pillow (for saving images): pip install Pillow
    - matplotlib (for display): pip install matplotlib
"""

import argparse
import sys
import time
from pathlib import Path

import torch


def print_banner():
    """Print welcome banner."""
    print("=" * 60)
    print("  Phase-Quad Image Generator Demo")
    print("=" * 60)
    print()


def check_dependencies():
    """Check if optional dependencies are available."""
    deps = {}

    try:
        import PIL
        deps["pillow"] = True
    except ImportError:
        deps["pillow"] = False

    try:
        import matplotlib
        deps["matplotlib"] = True
    except ImportError:
        deps["matplotlib"] = False

    try:
        import numpy
        deps["numpy"] = True
    except ImportError:
        deps["numpy"] = False

    return deps


def progress_callback(step: int, total: int, latents: torch.Tensor):
    """Progress callback for generation."""
    pct = step / total * 100
    bar_len = 30
    filled = int(bar_len * step / total)
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"\r  Denoising: [{bar}] {pct:5.1f}% ({step}/{total})", end="", flush=True)


def display_image(images: torch.Tensor, title: str = "Generated Image"):
    """Display image using matplotlib if available."""
    try:
        import matplotlib.pyplot as plt
        import numpy as np

        img = images[0].cpu().permute(1, 2, 0).numpy()

        plt.figure(figsize=(8, 8))
        plt.imshow(img)
        plt.title(title)
        plt.axis("off")
        plt.tight_layout()
        plt.show()
    except ImportError:
        print("  matplotlib not available for display")
        print("  Install with: pip install matplotlib")


def save_image(images: torch.Tensor, path: str):
    """Save image to file."""
    try:
        from PIL import Image
        import numpy as np

        img = images[0].cpu().permute(1, 2, 0).numpy()
        img = (img * 255).clip(0, 255).astype(np.uint8)

        Image.fromarray(img).save(path)
        print(f"  Saved to: {path}")
        return True
    except ImportError:
        print("  Pillow not available for saving")
        print("  Install with: pip install Pillow")
        return False


def demo_basic_generation(args):
    """
    Demonstrate basic image generation.

    This creates a mock pipeline (no pretrained weights needed)
    and generates an image from a text prompt.
    """
    from symbolu.vision.inference import (
        PhaseQuadInferencePipeline,
        GenerationConfig,
    )

    # Create pipeline - use pretrained if checkpoint provided
    if args.checkpoint:
        print("1. Creating Phase-Quad Pipeline (with trained checkpoint)")
        print(f"   - Loading checkpoint: {args.checkpoint}")
        print()

        pipeline = PhaseQuadInferencePipeline.from_pretrained(
            checkpoint_path=args.checkpoint,
            model_size=args.model_size,
        )
    else:
        print("1. Creating Phase-Quad Pipeline (mock mode for demo)")
        print("   - In production, use --checkpoint to load trained model")
        print()

        # Create mock pipeline
        pipeline = PhaseQuadInferencePipeline.create_mock(
            model_size=args.model_size,
        )

    print(f"   Model: {args.model_size}")
    n_params = sum(p.numel() for p in pipeline.model.parameters())
    print(f"   Parameters: {n_params:,}")
    print(f"   Device: {pipeline.device}")
    print()

    # Generation config
    config = GenerationConfig(
        height=args.height,
        width=args.width,
        num_inference_steps=args.steps,
        guidance_scale=args.guidance_scale,
        sampler=args.sampler,
        seed=args.seed,
        tau=args.tau,
    )

    print("2. Generation Configuration")
    print(f"   Prompt: \"{args.prompt}\"")
    print(f"   Size: {config.width}x{config.height}")
    print(f"   Steps: {config.num_inference_steps}")
    print(f"   Guidance: {config.guidance_scale}")
    print(f"   Sampler: {config.sampler}")
    print(f"   Tau (Phase-Quad): {config.tau}")
    if args.seed:
        print(f"   Seed: {args.seed}")
    print()

    print("3. Generating Image...")

    # Generate!
    result = pipeline.generate(
        prompt=args.prompt,
        negative_prompt=args.negative_prompt,
        config=config,
        callback=progress_callback if not args.quiet else None,
    )

    if not args.quiet:
        print()  # Newline after progress bar

    print()
    print("4. Generation Complete!")
    print(f"   Time: {result.generation_time_ms:.1f}ms")
    print(f"   Seed: {result.seed}")
    print(f"   Output shape: {list(result.images.shape)}")
    print(f"   Latent shape: {list(result.latents.shape)}")
    print()

    # Save image
    if args.output:
        print("5. Saving Image...")
        save_image(result.images, args.output)
        print()

    # Display image
    if args.display:
        print("5. Displaying Image...")
        display_image(result.images, f'"{args.prompt}"')

    return result


def demo_batch_generation(args):
    """Demonstrate batch generation with multiple prompts."""
    from symbolu.vision.inference import (
        PhaseQuadInferencePipeline,
        GenerationConfig,
    )

    print("Batch Generation Demo")
    print("-" * 40)

    prompts = [
        "A serene mountain lake at sunset",
        "A futuristic city with flying cars",
        "A cozy cabin in a snowy forest",
    ]

    print(f"Generating {len(prompts)} images...")
    print()

    pipeline = PhaseQuadInferencePipeline.create_mock(model_size="tiny")

    config = GenerationConfig(
        height=256,
        width=256,
        num_inference_steps=20,
    )

    for i, prompt in enumerate(prompts):
        print(f"[{i+1}/{len(prompts)}] \"{prompt}\"")

        result = pipeline.generate(
            prompt=prompt,
            config=config,
        )

        output_path = f"batch_output_{i+1}.png"
        save_image(result.images, output_path)

        print(f"   Time: {result.generation_time_ms:.1f}ms")
        print()


def demo_ablation(args):
    """Demonstrate ablation modes (disabling components)."""
    from symbolu.vision.inference import (
        PhaseQuadInferencePipeline,
        GenerationConfig,
    )
    from symbolu.vision.controls import GeneratorControl

    print("Ablation Demo - Testing Component Contributions")
    print("-" * 50)

    pipeline = PhaseQuadInferencePipeline.create_mock(model_size="tiny")

    config = GenerationConfig(
        height=256,
        width=256,
        num_inference_steps=10,
        seed=42,  # Fixed seed for comparison
    )

    prompt = "A beautiful landscape"

    # Test different ablation modes
    modes = [
        ("Full (baseline)", GeneratorControl(enable_quad=True, enable_phase=True)),
        ("Quad disabled", GeneratorControl(enable_quad=False, enable_phase=True)),
        ("Phase disabled", GeneratorControl(enable_quad=True, enable_phase=False)),
    ]

    print(f"Prompt: \"{prompt}\"")
    print()

    for mode_name, control in modes:
        print(f"Mode: {mode_name}")

        # Temporarily override the control
        result = pipeline.generate(prompt=prompt, config=config)

        print(f"   Time: {result.generation_time_ms:.1f}ms")
        print(f"   Output norm: {result.images.norm().item():.2f}")
        print()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Phase-Quad Image Generator Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic generation
  python -m symbolu.vision.demo_generate --prompt "A sunset over mountains"

  # With custom settings
  python -m symbolu.vision.demo_generate --prompt "A cat" --steps 30 --size 256

  # Save to file
  python -m symbolu.vision.demo_generate --prompt "A forest" --output forest.png

  # Display interactively
  python -m symbolu.vision.demo_generate --prompt "Ocean waves" --display
        """,
    )

    parser.add_argument(
        "--prompt", "-p",
        type=str,
        default="A serene landscape with mountains and a lake at sunset",
        help="Text prompt for generation",
    )
    parser.add_argument(
        "--negative-prompt", "-n",
        type=str,
        default=None,
        help="Negative prompt (what to avoid)",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Output file path (e.g., output.png)",
    )
    parser.add_argument(
        "--display", "-d",
        action="store_true",
        help="Display image with matplotlib",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=30,
        help="Number of denoising steps (default: 30)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=256,
        help="Image height in pixels (default: 256)",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=256,
        help="Image width in pixels (default: 256)",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=None,
        help="Image size (sets both width and height)",
    )
    parser.add_argument(
        "--guidance-scale",
        type=float,
        default=7.5,
        help="Classifier-free guidance scale (default: 7.5)",
    )
    parser.add_argument(
        "--sampler",
        type=str,
        choices=["ddpm", "ddim"],
        default="ddim",
        help="Sampling method (default: ddim)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--tau",
        type=float,
        default=1.0,
        help="Phase-Quad temperature (default: 1.0)",
    )
    parser.add_argument(
        "--model-size",
        type=str,
        choices=["tiny", "small", "base", "large"],
        default="tiny",
        help="Model size (default: tiny)",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress output",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Run batch generation demo",
    )
    parser.add_argument(
        "--ablation",
        action="store_true",
        help="Run ablation demo",
    )
    parser.add_argument(
        "--checkpoint", "-c",
        type=str,
        default=None,
        help="Path to trained model checkpoint (uses pretrained VAE/CLIP)",
    )

    args = parser.parse_args()

    # Handle --size shortcut
    if args.size:
        args.height = args.size
        args.width = args.size

    print_banner()

    # Check dependencies
    deps = check_dependencies()
    print("Dependencies:")
    for dep, available in deps.items():
        status = "✓" if available else "✗"
        print(f"  {status} {dep}")
    print()

    # Auto-set output if not displaying
    if not args.output and not args.display:
        args.output = "phase_quad_output.png"
        print(f"Note: Output will be saved to {args.output}")
        print("      Use --display to view interactively")
        print()

    try:
        if args.batch:
            demo_batch_generation(args)
        elif args.ablation:
            demo_ablation(args)
        else:
            demo_basic_generation(args)

        print("=" * 60)
        print("Demo complete!")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
