"""
Paired metrics for the ablations (STATISTICS in the preregistration).

All metrics are deterministic. The bootstrap uses a fixed seed so two runs match
byte-for-byte (REPRODUCIBILITY_REPORT.md).

Decision level ("retained"): a claim is retained iff its recommended_action is
retain or narrow. V0 (no validation) retains everything.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Mapping, Tuple

from relationship_claim_validation.model import (
    EvidenceRecord, GoldLabel, RETAINED_ACTIONS,
)

BOOTSTRAP_SEED = 20260720
BOOTSTRAP_N = 2000


def _retained(rec: EvidenceRecord) -> bool:
    return rec.recommended_action in RETAINED_ACTIONS


@dataclass(frozen=True)
class ConfusionCounts:
    tp: int   # gold-retained  & pred-retained   (supported preserved)
    fp: int   # gold-not-retn  & pred-retained   (false acceptance)
    tn: int   # gold-not-retn  & pred-not-retn   (unsupported removed)
    fn: int   # gold-retained  & pred-not-retn   (false removal)

    @property
    def precision(self) -> float:
        d = self.tp + self.fp
        return round(self.tp / d, 4) if d else 1.0

    @property
    def recall(self) -> float:
        d = self.tp + self.fn
        return round(self.tp / d, 4) if d else 1.0


def confusion(records: Mapping[str, EvidenceRecord],
              gold: Mapping[str, GoldLabel]) -> ConfusionCounts:
    tp = fp = tn = fn = 0
    for rid, g in gold.items():
        pred = _retained(records[rid])
        if g.gold_retained and pred:
            tp += 1
        elif not g.gold_retained and pred:
            fp += 1
        elif not g.gold_retained and not pred:
            tn += 1
        else:
            fn += 1
    return ConfusionCounts(tp, fp, tn, fn)


def paired_vs_baseline(records: Mapping[str, EvidenceRecord],
                       baseline: Mapping[str, EvidenceRecord],
                       gold: Mapping[str, GoldLabel]) -> Dict[str, object]:
    """Fixes/breaks of `records` vs `baseline` at the retained-decision level."""
    fixes: List[str] = []
    breaks: List[str] = []
    for rid, g in gold.items():
        base_ret = _retained(baseline[rid])
        new_ret = _retained(records[rid])
        if base_ret == new_ret:
            continue
        # a decision changed relative to baseline
        base_correct = (base_ret == g.gold_retained)
        new_correct = (new_ret == g.gold_retained)
        if new_correct and not base_correct:
            fixes.append(rid)
        elif base_correct and not new_correct:
            breaks.append(rid)
    n = len(gold)
    net = len(fixes) - len(breaks)
    return {
        "fixes": sorted(fixes),
        "breaks": sorted(breaks),
        "n_fixes": len(fixes),
        "n_breaks": len(breaks),
        "net": net,
        "net_fix_rate": round(net / n, 4) if n else 0.0,
    }


def status_accuracy(records: Mapping[str, EvidenceRecord],
                    gold: Mapping[str, GoldLabel]) -> float:
    correct = sum(1 for rid, g in gold.items()
                  if records[rid].validation_status == g.gold_status)
    return round(correct / len(gold), 4) if gold else 1.0


def bootstrap_ci_net_fix_rate(records: Mapping[str, EvidenceRecord],
                              baseline: Mapping[str, EvidenceRecord],
                              gold: Mapping[str, GoldLabel]) -> Tuple[float, float]:
    ids = sorted(gold.keys())
    per_id_net: Dict[str, int] = {}
    for rid in ids:
        g = gold[rid]
        base_ret = _retained(baseline[rid])
        new_ret = _retained(records[rid])
        base_correct = (base_ret == g.gold_retained)
        new_correct = (new_ret == g.gold_retained)
        if new_ret != base_ret and new_correct and not base_correct:
            per_id_net[rid] = 1
        elif new_ret != base_ret and base_correct and not new_correct:
            per_id_net[rid] = -1
        else:
            per_id_net[rid] = 0
    rng = random.Random(BOOTSTRAP_SEED)
    n = len(ids)
    samples: List[float] = []
    for _ in range(BOOTSTRAP_N):
        s = sum(per_id_net[ids[rng.randrange(n)]] for _ in range(n))
        samples.append(s / n)
    samples.sort()
    lo = samples[int(0.025 * BOOTSTRAP_N)]
    hi = samples[int(0.975 * BOOTSTRAP_N)]
    return round(lo, 4), round(hi, 4)


def judge_agreement(records: Mapping[str, EvidenceRecord]) -> Dict[str, object]:
    """A/B agreement proxy: fraction of claims that did NOT require adjudication
    (Judge C) among those where both judges ran. Also counts adjudications."""
    adjudicated = [rid for rid, r in records.items() if r.adjudicated]
    return {
        "n_adjudicated": len(adjudicated),
        "adjudicated_ids": sorted(adjudicated),
    }
