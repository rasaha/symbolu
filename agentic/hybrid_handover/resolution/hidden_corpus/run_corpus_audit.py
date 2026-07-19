#!/usr/bin/env python3
"""
Hidden-corpus audit — integrity + leakage + statistics. Does NOT run any resolver
and reports NO resolver performance.

    python -m agentic.hybrid_handover.resolution.hidden_corpus.run_corpus_audit
"""

from __future__ import annotations

import json
import os

from .leakage import verify
from .stats import statistics
from .validate import validate

OUT_DIR = os.path.dirname(__file__)


def run():
    return {
        "corpus": "SEEB hidden relationship corpus (audit-only)",
        "synthetic": True,
        "integrity_issues": validate(),
        "leakage_findings": verify(),
        "statistics": statistics(),
    }


def main():
    out = run()
    with open(os.path.join(OUT_DIR, "CORPUS_AUDIT.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)
    s = out["statistics"]
    print("=" * 78)
    print("HIDDEN RELATIONSHIP CORPUS — AUDIT (no resolver run)")
    print("=" * 78)
    print(f"cases: {s['n_cases']}")
    print(f"integrity issues: {out['integrity_issues'] or 'none'}")
    print(f"leakage findings: {out['leakage_findings'] or 'none'}")
    print(f"\ndifficulty: {s['coverage_by_difficulty']}")
    print(f"abstention: {s['coverage_by_abstention']}   ambiguity: {s['coverage_by_ambiguity']}")
    print(f"governance types: {s['coverage_by_governance_type']}")
    print(f"relationship types: {s['coverage_by_relationship_type']}")
    print(f"negative controls: {s['negative_controls']}")
    print("\nblind spots:")
    for k, v in s["blind_spots"].items():
        print(f"  {k}: {v}")
    print(f"\nWrote {os.path.join(OUT_DIR, 'CORPUS_AUDIT.json')}")


if __name__ == "__main__":
    main()
