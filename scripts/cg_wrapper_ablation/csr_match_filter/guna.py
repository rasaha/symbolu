#!/usr/bin/env python3
"""guna.py — GunaQuality diagnostics (P-A, diagnostics-only).

Relabels EXISTING Phase 3 audit findings into expression-quality flags. Pure function; NO runtime
behavior change, NO Phase 1-3 threshold change, NO new detectors. Only signals that are direct relabels
of validated audit fields are [D]; `parroting` relies on `is_meta_parrot` which over-fires and is [N]
(diagnostic only). Clarity/specificity/overconfidence/hedging detectors are [N] FUTURE work and are NOT
implemented here. This is NOT canonical Guna (`p_g`); it is an audit-derived quality overlay.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from csr_match_filter.eval_real_output_audit import is_meta_parrot   # noqa: E402

# This layer is `GunaQualityDiagnostic` — an audit-derived symbolic quality overlay. It is NOT canonical
# Guna `p_g` (the softmax-3D Sattva/Rajas/Tamas distribution), which is reserved for a separate future
# estimator track (see docs/CSR_GUNA_VRITTI_POLICY_SPEC.md §5.1).
LAYER_NAME = "GunaQualityDiagnostic"

# flag -> (source audit finding / signal, status, bucket). EXPRESSION QUALITY ONLY (not frame movement).
GUNA_FLAGS = {
    "generic_low_signal": ("answer_too_generic", "[D]", "expression_quality"),
    "parroting": ("is_meta_parrot", "[N]", "expression_quality"),
}

# [N] future detectors — documented, NOT implemented, NOT runtime-active.
GUNA_FUTURE_DETECTORS_N = ("clear_stable", "specific_grounded", "overconfident", "hedged_uncertain",
                          "noisy_unstable")


def derive_guna(finding_types, answer=None) -> dict:
    """Multi-label GunaQuality flags from existing audit findings (+ optional answer for [N] parroting)."""
    fts = set(finding_types or [])
    flags = []
    for flag, (src, _status, _bucket) in GUNA_FLAGS.items():
        if src == "is_meta_parrot":
            if answer is not None and is_meta_parrot(answer):
                flags.append(flag)
        elif src in fts:
            flags.append(flag)
    return {"flags": sorted(flags), "multi_label": True,
            "future_detectors_not_built": list(GUNA_FUTURE_DETECTORS_N)}
