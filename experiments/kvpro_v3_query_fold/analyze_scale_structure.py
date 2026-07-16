#!/usr/bin/env python3
"""Phase C — scale decomposition audit.

Tests whether the production per-block per-channel K SCALE factors as α_d·β_b
(rank-1 multiplicative / log-additive) or a pre-registered linear rank-R SVD (R∈{2,4}).
Thin CLI over structure.py. Emits variance-explained, relative-Frobenius error,
median/worst layer+head, per-channel bias, and metadata retained per block.

  python analyze_scale_structure.py --manifest capture.pt --out-json scale_structure.json
  python analyze_scale_structure.py --synthetic factorable      # CPU self-check
"""
import sys

try:
    from . import structure
except ImportError:  # pragma: no cover
    import structure  # type: ignore

if __name__ == "__main__":
    sys.exit(structure.main(kind="scale"))
