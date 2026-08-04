#!/usr/bin/env python3
"""Single-source verifier for the LLM Steering Controller.

Fails (nonzero exit) if the canonical routing-controller implementation reappears outside
the ONE canonical package. The routing/steering *research* engines
(``model_selection_pilot``, ``model_selection_experiment``, ``model_selection_reconciliation``)
are DIFFERENT, self-declared research algorithms (dict-based ``route`` with distinct I/O)
and are explicitly exempt — they carry no copy of the canonical controller's symbols.

Run from anywhere; the repository root is located relative to this file.
"""

from __future__ import annotations

import json
import pathlib
import sys

# Sentinels UNIQUE to the canonical LLM Steering Controller. The research route engines
# use dict-based `route(...)` with different names, so these class names exist only in the
# canonical package.
ALGORITHM_SENTINELS = (
    "class LLMSteeringController",
    "class CandidateRegistry",
    "class RoutingRecommendation",
)

CANONICAL_REL = "packages/capabilities/llm-steering-controller/src/ugence_llm_steering_controller"

# Research/experiment/pilot trees that legitimately implement a DIFFERENT routing
# algorithm and are exempt from the single-source check (they carry none of the sentinels
# above; this is defense-in-depth documentation of intent).
EXEMPT_PREFIXES = (
    "model_selection_pilot",
    "model_selection_experiment",
    "model_selection_reconciliation",
    "execution_gate",
)


def _repo_root() -> pathlib.Path:
    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "packages" / "capabilities" / "llm-steering-controller").is_dir() and \
           (parent / ".git").exists():
            return parent
    return here.parents[4]


def audit(root: pathlib.Path) -> dict:
    canonical = (root / CANONICAL_REL).resolve()
    violations = []
    sentinel_files = []

    for path in root.rglob("*.py"):
        rp = path.resolve()
        parts = set(rp.parts)
        if "__pycache__" in parts or ".git" in parts:
            continue
        if any(seg in parts for seg in ("build", "dist", ".venv", "site-packages")):
            continue
        # Only implementation source is subject to single-source; non-shipped trees
        # (this audit script, tests, docs, examples, fixtures, evidence) legitimately
        # mention the sentinel names as strings.
        if any(seg in parts for seg in ("scripts", "tests", "docs", "examples",
                                        "fixtures", "artifacts")):
            continue
        try:
            rp.relative_to(canonical)
            in_canonical = True
        except ValueError:
            in_canonical = False

        try:
            text = rp.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for sentinel in ALGORITHM_SENTINELS:
            if sentinel in text:
                rel = str(rp.relative_to(root))
                sentinel_files.append({"file": rel, "sentinel": sentinel, "canonical": in_canonical})
                if not in_canonical:
                    violations.append(f"{rel}: '{sentinel}' outside the canonical package")

    return {
        "canonical_package": CANONICAL_REL,
        "sentinels": list(ALGORITHM_SENTINELS),
        "exempt_prefixes": list(EXEMPT_PREFIXES),
        "sentinel_files": sentinel_files,
        "violations": violations,
        "single_source": not violations,
    }


def main() -> int:
    root = _repo_root()
    report = audit(root)
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["violations"]:
        print("\nSINGLE-SOURCE AUDIT FAILED: canonical routing controller duplicated.",
              file=sys.stderr)
        return 1
    print("\nLLM STEERING CONTROLLER SINGLE SOURCE OK", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
