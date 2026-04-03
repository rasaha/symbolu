#!/usr/bin/env python3
"""
Quick-start training demo for Phase-Quad Video Generator.

This script demonstrates video training with various configurations.

Usage:
    # Quick test with synthetic data (no downloads needed)
    python -m symbolu.vision.video.demo_train --quick

    # Train with progressive approach (from image model)
    python -m symbolu.vision.video.demo_train --progressive

    # Full training setup
    python -m symbolu.vision.video.demo_train --full

Requirements:
    pip install torch diffusers transformers datasets decord
"""

import argparse
import sys


def print_banner():
    print("=" * 60)
    print("  Phase-Quad Video Generator - Training Demo")
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

    # Optional video dependencies
    try:
        import decord
        deps["decord"] = "installed"
    except ImportError:
        deps["decord"] = None

    return deps


def print_dependencies(deps):
    """Print dependency status."""
    print("Dependencies:")
    all_ok = True
    for name, version in deps.items():
        if version is None:
            if name == "decord":
                # Optional
                print(f"  ~ {name} - not installed (optional, for video loading)")
            else:
                print(f"  ✗ {name} - NOT INSTALLED")
                all_ok = False
        elif version is True or version == "installed":
            print(f"  ✓ {name}")
        else:
            print(f"  ✓ {name} ({version})")
    print()
    return all_ok


def quick_test():
    """
    Quick test with mock components.

    No pretrained models needed - validates training loop.
    """
    print("Running quick test with mock components...")
    print("(No pretrained models will be downloaded)")
    print()

    from symbolu.vision.video.train import train

    train(
        model_size="tiny",
        synthetic=True,
        batch_size=1,
        epochs=2,
        save_every=1,
        output_dir="checkpoints_video_quick",
        use_pretrained=False,
        num_frames=8,
        image_size=128,
        num_workers=0,
        gradient_accumulation=1,
    )


def train_progressive():
    """
    Progressive training from image model.

    This demonstrates the recommended approach:
    1. Start from pretrained image model
    2. Train on short videos
    3. Gradually increase video length

    Requires a trained image model checkpoint.
    """
    print("Progressive training from image model...")
    print()
    print("This requires a trained image model checkpoint.")
    print("If you don't have one, run image training first:")
    print("  python -m symbolu.vision.demo_train --pokemon")
    print()

    from pathlib import Path

    # Check for image checkpoint
    image_checkpoints = list(Path("checkpoints_pokemon").glob("*.pt"))
    if not image_checkpoints:
        image_checkpoints = list(Path("checkpoints").glob("*.pt"))

    if image_checkpoints:
        checkpoint = sorted(image_checkpoints)[-1]  # Use latest
        print(f"Found image checkpoint: {checkpoint}")
    else:
        print("No image checkpoint found.")
        print("Running with random initialization instead...")
        checkpoint = None

    input("\nPress Enter to continue or Ctrl+C to cancel...")

    from symbolu.vision.video.train import train

    # Phase 1: Short videos (8 frames)
    print("\n" + "=" * 50)
    print("Phase 1: Training on 8-frame videos")
    print("=" * 50)

    train(
        model_size="small",
        synthetic=True,  # Using synthetic for demo
        batch_size=1,
        learning_rate=1e-5,
        epochs=10,
        save_every=5,
        output_dir="checkpoints_video_progressive",
        init_from_image=str(checkpoint) if checkpoint else None,
        use_pretrained=False,  # Mock for demo
        num_frames=8,
        image_size=128,
        num_workers=0,
        gradient_accumulation=4,
    )

    # Phase 2: Longer videos (16 frames)
    print("\n" + "=" * 50)
    print("Phase 2: Training on 16-frame videos")
    print("=" * 50)

    train(
        model_size="small",
        synthetic=True,
        batch_size=1,
        learning_rate=5e-6,  # Lower LR for fine-tuning
        epochs=10,
        save_every=5,
        output_dir="checkpoints_video_progressive",
        resume="checkpoints_video_progressive/epoch_10.pt",
        use_pretrained=False,
        num_frames=16,
        image_size=128,
        num_workers=0,
        gradient_accumulation=4,
    )


def train_full():
    """
    Full training setup.
    """
    print("Full video training setup...")
    print()
    print("Options:")
    print("  1. Local directory with videos/ and captions/")
    print("  2. HuggingFace video dataset")
    print()
    print("Example commands:")
    print("  python -m symbolu.vision.video.train --data-dir /path/to/videos")
    print("  python -m symbolu.vision.video.train --hf-dataset HuggingFaceM4/webvid")
    print()

    from symbolu.vision.video.train import train

    # Default to synthetic for demo
    train(
        model_size="small",
        synthetic=True,
        batch_size=1,
        learning_rate=1e-5,
        epochs=20,
        save_every=5,
        output_dir="checkpoints_video_full",
        use_pretrained=False,
        num_frames=16,
        image_size=256,
        num_workers=2,
        gradient_accumulation=4,
    )


def demo_inference():
    """
    Demo video inference with untrained model.
    """
    print("Demo: Video inference (untrained model)...")
    print("(Output will be random noise)")
    print()

    from symbolu.vision.video import (
        PhaseQuadVideoPipeline,
        VideoGenerationConfig,
    )

    print("Creating video pipeline...")
    pipeline = PhaseQuadVideoPipeline.create_mock(model_size="tiny")

    print(f"Device: {pipeline.device}")
    print()

    config = VideoGenerationConfig(
        num_frames=8,
        height=128,
        width=128,
        num_inference_steps=10,
    )

    print("Generating video...")
    result = pipeline.generate(
        prompt="A sunset over the ocean",
        config=config,
    )

    print(f"Generated in {result.generation_time_ms:.1f}ms")
    print(f"Output shape: {list(result.frames.shape)}")

    # Save
    output_path = "video_demo.gif"
    result.save(output_path)


def main():
    parser = argparse.ArgumentParser(
        description="Phase-Quad Video Training Demo"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick test with mock components",
    )
    parser.add_argument(
        "--progressive",
        action="store_true",
        help="Progressive training from image model",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full training setup",
    )
    parser.add_argument(
        "--inference",
        action="store_true",
        help="Demo inference",
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
        elif args.progressive:
            train_progressive()
        elif args.full:
            train_full()
        elif args.inference:
            demo_inference()
        else:
            print("Choose a training mode:")
            print()
            print("  --quick        Quick test with mock components")
            print("  --progressive  Progressive training from image model")
            print("  --full         Full training setup")
            print("  --inference    Demo inference")
            print()
            print("Example:")
            print("  python -m symbolu.vision.video.demo_train --quick")

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
