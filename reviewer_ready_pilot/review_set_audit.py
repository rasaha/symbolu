"""Phase 9 - Final review set audit.

Independently audits the frozen final review set (data/final_review_v1/final_review.json) for the
properties a reviewer-ready set must have BEFORE any real reviewer is engaged:

  A1 size          - >= MIN_FINAL eligible artifacts
  A2 blinding      - no item exposes the system result (gold_obligation / explanation / invariants)
  A3 disjoint      - no artifact_id or natural source_path shared with the training set
  A4 prior-excl    - no natural artifact reuses a prior corpus/dev/held-out/review source_path
  A5 provenance    - every natural item carries source_path + source_kind + surface metadata
  A6 risk-coverage - each risk tier (low/medium/high/critical/unknown) is represented
  A7 trap-coverage - all 8 safety-trap families present, each >= TRAP_VARIANTS
  A8 no-mock       - no is_mock / fake-reviewer artifact leaked into the set

Returns a structured verdict. If any check fails, the overall status is REVIEW_SET_NEEDS_IMPROVEMENT
(decision option 3) with the specific failures listed - the audit never silently passes a deficient set.

Read-only over the frozen policy and the dataset. Deterministic, stdlib-only.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List

from reviewer_ready_pilot import dataset
from reviewer_ready_pilot.qualification import short_level

_PKG = os.path.dirname(os.path.abspath(__file__))

_GOLD_KEYS = ("gold_obligation", "gold_explanation", "invariants_triggered", "rationale", "final_obligation")
_RISK_TIERS = {"low", "medium", "high", "critical", "unknown"}
_TRAP_FAMILIES = {t[0] for t in dataset._TRAPS}


@dataclass
class Check:
    key: str
    label: str
    passed: bool
    detail: str = ""


@dataclass
class AuditReport:
    status: str
    checks: List[Check] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {"status": self.status,
                "checks": [{"key": c.key, "label": c.label, "passed": c.passed, "detail": c.detail}
                           for c in self.checks],
                "stats": self.stats}


def audit() -> AuditReport:
    final = dataset.load_final()
    training = dataset.load_training()
    tr_ids = {i["artifact_id"] for i in training}
    tr_paths = {i["source_path"] for i in training if not i.get("synthetic")}
    prior = dataset._prior_paths()

    natural = [i for i in final if not i.get("synthetic")]
    traps = [i for i in final if i.get("source_kind") == "trap"]
    edges = [i for i in final if i.get("source_kind") == "edge_case"]
    checks: List[Check] = []

    # A1 size
    checks.append(Check("A1", "final set has >= MIN_FINAL natural eligible artifacts",
                        len(natural) >= dataset.MIN_FINAL,
                        f"{len(natural)} natural (min {dataset.MIN_FINAL}); {len(traps)} traps; "
                        f"{len(edges)} edge cases; {len(final)} total"))

    # A2 blinding
    leaked = [i["artifact_id"] for i in final if any(k in i for k in _GOLD_KEYS)]
    checks.append(Check("A2", "no item exposes the system result (blinded)",
                        not leaked, f"{len(leaked)} leaked" if leaked else "fully blinded"))

    # A3 disjoint from training
    id_overlap = tr_ids & {i["artifact_id"] for i in final}
    path_overlap = tr_paths & {i["source_path"] for i in natural}
    checks.append(Check("A3", "disjoint from training (ids + natural source paths)",
                        not id_overlap and not path_overlap,
                        f"{len(id_overlap)} id / {len(path_overlap)} path overlaps"))

    # A4 prior exclusion
    reused = [i["source_path"] for i in natural if i["source_path"] in prior]
    checks.append(Check("A4", "no natural artifact reuses a prior source path",
                        not reused, f"{len(reused)} reused (of {len(prior)} prior paths guarded)"))

    # A5 provenance / metadata present
    missing = [i["artifact_id"] for i in natural
               if not (i.get("source_path") and i.get("source_kind") and i.get("risk_tier"))]
    checks.append(Check("A5", "every natural item carries provenance + surface metadata",
                        not missing, f"{len(missing)} missing fields"))

    # A6 risk coverage
    risk_counts = Counter(i.get("risk_tier", "unknown") for i in final)
    covered = {t for t in _RISK_TIERS if risk_counts.get(t, 0) > 0}
    checks.append(Check("A6", "all risk tiers represented",
                        covered == _RISK_TIERS,
                        f"present: {sorted(covered)}; missing: {sorted(_RISK_TIERS - covered)}"))

    # A7 trap coverage
    trap_counts = Counter(i["trap_type"] for i in traps)
    edge_counts = Counter(i["edge_type"] for i in edges)
    thin = {fam: trap_counts.get(fam, 0) for fam in _TRAP_FAMILIES if trap_counts.get(fam, 0) < dataset.TRAP_VARIANTS}
    checks.append(Check("A7", f"all 8 trap families present, each >= {dataset.TRAP_VARIANTS}",
                        not thin, f"thin/missing families: {thin}" if thin else "all families sufficient"))

    # A8 no mock/fake reviewer leakage
    mock = [i["artifact_id"] for i in final if i.get("is_mock") or i.get("source_kind") == "mock_reviewer"]
    checks.append(Check("A8", "no mock / fake-reviewer artifact in the set",
                        not mock, f"{len(mock)} mock artifacts" if mock else "none"))

    status = "REVIEW_SET_OK" if all(c.passed for c in checks) else "REVIEW_SET_NEEDS_IMPROVEMENT"
    stats = {
        "total": len(final), "natural": len(natural), "traps": len(traps), "edge_cases": len(edges),
        "risk_distribution": dict(sorted(risk_counts.items())),
        "trap_distribution": dict(sorted(trap_counts.items())),
        "edge_distribution": dict(sorted(edge_counts.items())),
        "claim_family_distribution": dict(sorted(Counter(
            i.get("claim_family", "unknown") for i in natural).items())),
        "source_kind_distribution": dict(sorted(Counter(
            i.get("source_kind", "unknown") for i in natural).items())),
        "policy_obligation_preview_absent": all(short_level(i.get("gold_obligation")) is None for i in final),
    }
    return AuditReport(status=status, checks=checks, stats=stats)


if __name__ == "__main__":
    rep = audit()
    print(f"final review set audit: {rep.status}")
    for c in rep.checks:
        print(f"  [{'PASS' if c.passed else 'FAIL'}] {c.key} {c.label} - {c.detail}")
    print("stats:", json.dumps(rep.stats, indent=2, sort_keys=True))
