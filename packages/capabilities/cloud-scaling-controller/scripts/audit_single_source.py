#!/usr/bin/env python3
"""Duplicate-source verifier for the Cloud Scaling Controller.

Fails (nonzero exit) if any scaling-algorithm module reappears outside the ONE
canonical package. Legacy namespaces (``cloud_controller``, ``symbolu.cloud_controller``)
may exist only as thin, logic-free compatibility shims.

Run from anywhere; the repository root is located relative to this file.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

# Sentinels UNIQUE to the Cloud Scaling Controller. The generic component names
# (PlasticityGate, AdaptiveGain, Damping, IdentityEMA, ReplayBuffer, Controller) are
# NOT used here: they also name the unrelated CG lineage this controller was ported
# from (symbolu_training/.../minimal_controller.py, agentic/safety/...), so matching
# them would produce false positives. These three names exist only in the canonical
# cloud package.
ALGORITHM_SENTINELS = (
    "class InfraControllerConfig",
    "class CloudScalingController",
    "class CoherenceModel",
)

CANONICAL_REL = "packages/capabilities/cloud-scaling-controller/src/ugence_cloud_scaling_controller"


def _repo_root() -> pathlib.Path:
    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "packages" / "capabilities" / "cloud-scaling-controller").is_dir() and \
           (parent / ".git").exists():
            return parent
    # Fallback: three levels up from scripts/ -> package -> capabilities -> packages -> root
    return here.parents[4]


def audit(root: pathlib.Path) -> dict:
    canonical = (root / CANONICAL_REL).resolve()
    violations = []
    algorithm_files = []

    for path in root.rglob("*.py"):
        rp = path.resolve()
        # Skip anything under the canonical package, build/venv/cache dirs.
        parts = set(rp.parts)
        if "__pycache__" in parts or ".git" in parts:
            continue
        if any(seg in parts for seg in ("build", "dist", ".venv", "site-packages")):
            continue
        try:
            rp.relative_to(canonical)
            in_canonical = True
        except ValueError:
            in_canonical = False

        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        hits = [s for s in ALGORITHM_SENTINELS if re.search(r"^\s*" + re.escape(s) + r"\b", text, re.M)]
        if not hits:
            continue
        rel = str(rp.relative_to(root))
        algorithm_files.append({"path": rel, "sentinels": hits, "canonical": in_canonical})
        if not in_canonical:
            violations.append({"path": rel, "sentinels": hits})

    # Extra structural assertions.
    nested = root / "cloud_controller" / "cloud_controller"
    if nested.exists():
        violations.append({"path": "cloud_controller/cloud_controller", "reason": "stale nested duplicate present"})
    symbolu_copy = root / "symbolu" / "cloud_controller"
    if symbolu_copy.exists() and any(symbolu_copy.rglob("*.py")):
        violations.append({"path": "symbolu/cloud_controller", "reason": "dead physical copy present"})

    # The top-level legacy shim, if present, must be logic-free (no algorithm, no numpy).
    shim = root / "cloud_controller" / "__init__.py"
    if shim.exists():
        stext = shim.read_text(encoding="utf-8", errors="ignore")
        if "import numpy" in stext or "np.random" in stext:
            violations.append({"path": "cloud_controller/__init__.py",
                               "reason": "legacy shim contains algorithm/numpy code"})
        shim_pkg_files = [p for p in (root / "cloud_controller").rglob("*.py")
                          if p.name != "__init__.py"]
        if shim_pkg_files:
            violations.append({"path": "cloud_controller/",
                               "reason": f"legacy shim dir has non-__init__ modules: "
                                         f"{[str(p.relative_to(root)) for p in shim_pkg_files]}"})

    return {
        "canonical_package": CANONICAL_REL,
        "algorithm_files": algorithm_files,
        "violations": violations,
        "single_source": not violations,
    }


def main(argv=None) -> int:
    root = _repo_root()
    result = audit(root)
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["single_source"]:
        print("DUPLICATE SOURCE DETECTED", file=sys.stderr)
        return 1
    print("SINGLE SOURCE VERIFIED", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
