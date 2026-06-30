"""Guarded entrypoint for the synonym-selection pilot.

SCAFFOLDING ONLY. The pre-registration (varna_lens/PREREG_SYNONYM_SELECTION.md) is
NOT frozen and NOT approved to run. This entrypoint therefore refuses to compute any
fit on real synonym data: it emits NOT_RUN unless a frozen, pre-registered dataset is
present (which it is not). No semantic claim is made.

    python3 experiments/synonym_selection/run_synonym_selection.py
"""
from __future__ import annotations

import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lexicon import load_readings, vocab_index   # noqa: E402

FROZEN_DATA = os.environ.get("SYNSEL_FROZEN_DATA")   # set only after pre-reg freeze+approval


def main() -> int:
    cons, vow, vocab = load_readings()
    print(f"[scaffold] loaded word_formation_reading: {len(cons)} consonants, "
          f"{len(vow)} vowels, {len(vocab)} distinct consonant reading labels.")
    print(f"[scaffold] confirmatory space = consonant-only, equal-weight (dim {len(vocab)}).")

    if not FROZEN_DATA or not pathlib.Path(FROZEN_DATA).exists():
        print("DECISION: NOT_RUN")
        print("  reason: pre-registration not frozen/approved; no frozen synonym dataset present.")
        print("  (set SYNSEL_FROZEN_DATA to a sha256-frozen, pre-registered dataset to enable a run.)")
        print("  no fit computed on real data; Stage A untouched.")
        return 0

    # Intentionally NOT implemented: real fit must wait for pre-reg freeze + explicit approval.
    print("DECISION: NOT_RUN  (frozen-data path present but real-fit execution is gated; "
          "implement only after pre-registration freeze and approval).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
