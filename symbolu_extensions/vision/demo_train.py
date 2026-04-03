#!/usr/bin/env python3
"""
Quick-start training demo for Phase-Quad Image Generator.

This script demonstrates training with pretrained VAE and CLIP.

Usage:
    # Quick test with synthetic data (no downloads needed)
    python -m symbolu.vision.demo_train --quick

    # Train on Pokemon dataset (small, easy to download)
    python -m symbolu.vision.demo_train --pokemon

    # Full training setup
    python -m symbolu.vision.demo_train --full

Requirements:
    pip install torch diffusers transformers datasets accelerate pillow
"""

import argparse
import sys


def print_banner():
    print("=" * 60)
    print("  Phase-Quad Image Generator - Training Demo")
    print("=" * 60)
    print()


def check_dependencies():
    """Check required dependencies."""
    deps = {}

    try:
        import torch
        deps["torch"] = torch.__version__
    except ImportError:
        deps["torch"] = None

    try:
        import diffusers
        deps["diffusers"] = diffusers.__version__
    except ImportError:
        deps["diffusers"] = None

    try:
        import transformers
        deps["transformers"] = transformers.__version__
    except ImportError:
        deps["transformers"] = None

    try:
        import datasets
        deps["datasets"] = datasets.__version__
    except ImportError:
        deps["datasets"] = None

    try:
        from PIL import Image
        deps["pillow"] = True
    except ImportError:
        deps["pillow"] = None

    return deps


def print_dependencies(deps):
    """Print dependency status."""
    print("Dependencies:")
    all_ok = True
    for name, version in deps.items():
        if version is None:
            print(f"  ✗ {name} - NOT INSTALLED")
            all_ok = False
        elif version is True:
            print(f"  ✓ {name}")
        else:
            print(f"  ✓ {name} ({version})")
    print()
    return all_ok


def quick_test():
    """
    Quick test with mock components.

    No pretrained models needed - just validates training loop.
    """
    print("Running quick test with mock components...")
    print("(No pretrained models will be downloaded)")
    print()

    from symbolu_extensions.vision.training.train import train

    train(
        model_size="tiny",
        synthetic=True,
        batch_size=2,
        epochs=2,
        save_every=1,
        output_dir="checkpoints_quick",
        use_pretrained=False,
        image_size=64,  # Small for fast testing
        num_workers=0,
    )


def train_pokemon():
    """
    Train on Pokemon BLIP captions dataset.

    Small dataset (~800 images) that's easy to download.
    Uses pretrained VAE and CLIP.
    """
    print("Training on Pokemon BLIP Captions dataset...")
    print("This will download:")
    print("  - SDXL VAE (~335MB)")
    print("  - CLIP text encoder (~600MB)")
    print("  - Pokemon dataset (~50MB)")
    print()

    input("Press Enter to continue or Ctrl+C to cancel...")

    from symbolu_extensions.vision.training.train import train

    train(
        model_size="small",
        hf_dataset="lambdalabs/pokemon-blip-captions",
        batch_size=2,
        learning_rate=1e-4,
        epochs=50,
        save_every=10,
        output_dir="checkpoints_pokemon",
        use_pretrained=True,
        image_size=256,  # Smaller for faster training
        num_workers=2,
    )


def train_full():
    """
    Full training setup with base model.
    """
    print("Full training setup...")
    print("This requires a dataset. Options:")
    print("  1. Local directory with images/ and captions/")
    print("  2. HuggingFace dataset name")
    print()
    print("Example commands:")
    print("  python -m symbolu.vision.training.train --data-dir /path/to/data")
    print("  python -m symbolu.vision.training.train --hf-dataset laion/laion2B-en")
    print()

    from symbolu_extensions.vision.training.train import train

    # Default to synthetic for demo
    train(
        model_size="base",
        synthetic=True,
        batch_size=4,
        learning_rate=1e-4,
        epochs=10,
        save_every=5,
        output_dir="checkpoints_full",
        use_pretrained=True,
        image_size=512,
        num_workers=4,
    )


def demo_inference_with_pretrained():
    """
    Demo inference with pretrained VAE and CLIP (but untrained model).

    Shows that the pipeline works, but images will be random noise
    since the model isn't trained.
    """
    print("Demo: Inference with pretrained VAE/CLIP...")
    print("(Model is untrained, so output will be random)")
    print()

    from symbolu_extensions.vision.inference import PhaseQuadInferencePipeline, GenerationConfig

    print("Creating pipeline with pretrained components...")
    pipeline = PhaseQuadInferencePipeline.from_pretrained(
        model_size="tiny",
    )

    print(f"Device: {pipeline.device}")
    print()

    config = GenerationConfig(
        height=256,
        width=256,
        num_inference_steps=20,
    )

    print("Generating image...")
    result = pipeline.generate(
        prompt="A cute pokemon character",
        config=config,
    )

    print(f"Generated in {result.generation_time_ms:.1f}ms")
    print(f"Output shape: {list(result.images.shape)}")

    # Save
    output_path = "pretrained_demo.png"
    result.save(output_path)
    print(f"Saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Phase-Quad Training Demo"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick test with mock components (no downloads)",
    )
    parser.add_argument(
        "--pokemon",
        action="store_true",
        help="Train on Pokemon dataset with pretrained VAE/CLIP",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full training setup",
    )
    parser.add_argument(
        "--inference",
        action="store_true",
        help="Demo inference with pretrained components",
    )

    args = parser.parse_args()

    print_banner()

    # Check dependencies
    deps = check_dependencies()
    all_ok = print_dependencies(deps)

    if not all_ok:
        print("Please install missing dependencies:")
        print("  pip install torch diffusers transformers datasets pillow")
        sys.exit(1)

    try:
        if args.quick:
            quick_test()
        elif args.pokemon:
            train_pokemon()
        elif args.full:
            train_full()
        elif args.inference:
            demo_inference_with_pretrained()
        else:
            # Default: show help
            print("Choose a training mode:")
            print()
            print("  --quick      Quick test with mock components (no downloads)")
            print("  --pokemon    Train on Pokemon dataset (recommended for demo)")
            print("  --full       Full training setup")
            print("  --inference  Demo inference with pretrained VAE/CLIP")
            print()
            print("Example:")
            print("  python -m symbolu.vision.demo_train --quick")

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
