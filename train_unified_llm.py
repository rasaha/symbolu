#!/usr/bin/env python3
"""
Unified LLM Training Script V9.8.0
===================================

Thin backward-compatible wrapper around symbolu.training.unified.train.

All training logic (train/evaluate/main) now lives in the modular package:
    symbolu/training/unified/train.py

This file preserves backward compatibility so that:
    python train_unified_llm.py --model_type ontological_hybrid ...
    from train_unified_llm import train, evaluate, main
still work exactly as before.

See symbolu/training/unified/train.py for the full implementation.
"""

# Re-export everything from the unified train module so that
#   from train_unified_llm import SomeClass
# continues to work for all previously importable names.

from symbolu.training.unified.train import *  # noqa: F401,F403

# Explicit re-exports for clarity and static analysis
from symbolu.training.unified.train import train, evaluate, main  # noqa: F401

if __name__ == "__main__":
    main()
