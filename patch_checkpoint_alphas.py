#!/usr/bin/env python3
"""
Patch checkpoint to update alpha_local and alpha_phase values.

Usage:
    python patch_checkpoint_alphas.py checkpoints_unified/best.pt --alpha_phase 0.6 --alpha_local 0.4
"""

import argparse
import torch
from pathlib import Path


def patch_alphas(checkpoint_path: str, alpha_local: float, alpha_phase: float, output_path: str = None):
    """Patch alpha values in a checkpoint."""

    print(f"Loading checkpoint: {checkpoint_path}")
    checkpoint = torch.load(checkpoint_path, map_location='cpu', weights_only=False)

    model_state = checkpoint['model']

    # Find and update all alpha parameters
    updated = []
    for key in model_state.keys():
        if 'alpha_local' in key:
            old_val = model_state[key].item()
            model_state[key] = torch.tensor(alpha_local)
            updated.append(f"  {key}: {old_val:.4f} -> {alpha_local:.4f}")
        elif 'alpha_phase' in key:
            old_val = model_state[key].item()
            model_state[key] = torch.tensor(alpha_phase)
            updated.append(f"  {key}: {old_val:.4f} -> {alpha_phase:.4f}")

    if not updated:
        print("WARNING: No alpha parameters found in checkpoint!")
        return

    print(f"\nUpdated {len(updated)} parameters:")
    for u in updated[:10]:  # Show first 10
        print(u)
    if len(updated) > 10:
        print(f"  ... and {len(updated) - 10} more")

    # Save
    if output_path is None:
        output_path = checkpoint_path

    print(f"\nSaving to: {output_path}")
    torch.save(checkpoint, output_path)
    print("Done!")


def main():
    parser = argparse.ArgumentParser(description="Patch checkpoint alpha values")
    parser.add_argument("checkpoint", help="Path to checkpoint file")
    parser.add_argument("--alpha_local", type=float, required=True, help="New alpha_local value")
    parser.add_argument("--alpha_phase", type=float, required=True, help="New alpha_phase value")
    parser.add_argument("--output", "-o", help="Output path (default: overwrite input)")

    args = parser.parse_args()

    patch_alphas(args.checkpoint, args.alpha_local, args.alpha_phase, args.output)


if __name__ == "__main__":
    main()
