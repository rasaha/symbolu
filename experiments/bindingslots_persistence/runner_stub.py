#!/usr/bin/env python3
"""Persistence-phase runner STUB.

Training for the six-arm persistence matrix (A+/R0/O1/O1R/H1/H2 x seeds 23-27) requires a SEPARATE
explicit authorization. This preregistration phase deliberately ships NO runnable training path.
Invoking this module refuses to run.
"""
from __future__ import annotations

import sys

MSG = ("TRAINING NOT AUTHORIZED: the BindingSlots persistence matrix is preregistered only. "
       "Training requires separate explicit authorization (see "
       "docs/audits/bindingslots_persistence_preregistration/TRAINING_AUTHORIZATION_GATE.md). "
       "This phase produces the preregistration, integrity report, and non-interference proof only.")


def main() -> int:
    print(MSG, file=sys.stderr)
    return 3  # non-zero: nothing was run


if __name__ == "__main__":
    raise SystemExit(main())
