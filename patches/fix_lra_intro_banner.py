#!/usr/bin/env python3
"""
Patch: Add introduction banner to LRA training script
======================================================

Adds a proper introduction banner to train_lra.py matching
the style of train_unified_llm.py.

Usage:
    python patches/fix_lra_intro_banner.py
"""

from pathlib import Path

PATCH_FILE = Path(__file__).parent.parent / "train_lra.py"

OLD_CODE = '''def train_lra(config: LRAConfig):
    """Main training loop for LRA."""

    torch.manual_seed(config.seed)'''

NEW_CODE = '''def train_lra(config: LRAConfig):
    """Main training loop for LRA."""

    # Early banner
    print(f"\\n{'='*70}")
    print("   LRA BENCHMARK TRAINING")
    print("   Long Range Arena for Efficient Attention")
    print(f"{'='*70}")

    torch.manual_seed(config.seed)'''


def apply_patch():
    print("=" * 60)
    print("  PATCH: Add LRA Introduction Banner")
    print("=" * 60)
    print()

    if not PATCH_FILE.exists():
        print(f"ERROR: File not found: {PATCH_FILE}")
        return False

    content = PATCH_FILE.read_text()

    # Check if already patched
    if "LRA BENCHMARK TRAINING" in content:
        print("SKIP: Patch already applied (banner exists)")
        return True

    # Check if old code exists
    if OLD_CODE not in content:
        print("ERROR: Could not find target code to patch")
        print("       The file may have been modified")
        return False

    # Apply patch
    new_content = content.replace(OLD_CODE, NEW_CODE)

    PATCH_FILE.write_text(new_content)

    print(f"SUCCESS: Patched {PATCH_FILE}")
    print()
    print("Changes:")
    print("  - Added introduction banner with title")
    print("  - Matches train_unified_llm.py style")

    return True


if __name__ == "__main__":
    import sys
    success = apply_patch()
    sys.exit(0 if success else 1)
