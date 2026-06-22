"""CPU tests for P-B (csr_policy_eval.py) on SYNTHETIC rows — no embeddings, no traces file.

Verifies the metric math, the non-overlap partition, grid-fit + grouped-CV, the per-class/critical/
false-rewrite accounting, and every decision label (BEATS / REPACKAGING_ONLY / NO_INCREMENTAL_VALUE /
INSUFFICIENT_LABEL_POWER). No runtime/Phase 1-3 change.
"""

import sys
from pathlib import Path

import pytest

_ABL = Path(__file__).resolve().parent.parent / "scripts" / "cg_wrapper_ablation"
if str(_ABL) not in sys.path:
    sys.path.insert(0, str(_ABL))

pytest.importorskip("numpy")

from csr_match_filter import csr_policy_eval as PB             # noqa: E402


def _mk(group, arm, traj, sev, guna=0.0, baseline=None):
    should = (traj > 0) or (sev > 0)
    truth = {"frame_violation": traj > 0, "rejected_leak": False, "factuality": sev > 0,
             "secondary": False, "should_rewrite": should, "critical": sev > 0}
    return {"id": group, "arm": arm, "group": group,
            "baseline_rewrite": (sev > 0) if baseline is None else baseline,   # narrow: criticals only
            "truth": truth,
            "feat": {"inv_match": 0.0, "traj_drift": float(traj), "guna": float(guna),
                     "severity": float(sev)},
            "finding_types": []}


# ---- units ---------------------------------------------------------------------------------------

def test_overlap_partition_disjoint():
    assert PB.overlap_ok() is True
    s = [set(PB.FRAME_MOVE), set(PB.SEVERITY), set(PB.GUNA_FIND)]
    for i in range(3):
        for j in range(i + 1, 3):
            assert s[i].isdisjoint(s[j])


def test_rubric_truth_mapping():
    t = PB.rubric_truth({"primary_frame_correct": 0.0, "rejected_domain_avoidance": 1.0,
                         "factuality_preserved": 1.0, "secondary_promoted": True})
    assert t["frame_violation"] and not t["rejected_leak"] and t["secondary"] and t["should_rewrite"]
    t2 = PB.rubric_truth({"primary_frame_correct": 1.0, "rejected_domain_avoidance": 1.0,
                          "factuality_preserved": 1.0, "secondary_promoted": False})
    assert not t2["should_rewrite"] and not t2["critical"]


def test_features_from_findings_uses_disjoint_buckets():
    f = PB.features_from_findings(["rejected_domain_promoted", "factuality_suspected",
                                   "answer_too_generic"], inv_match=0.3)
    assert f["traj_drift"] == 1.0 and f["severity"] == 1.0 and f["guna"] == 1.0 and f["inv_match"] == 0.3


def test_metrics_basic():
    m = PB._metrics([1, 1, 0, 0], [1, 0, 0, 0])
    assert m["tp"] == 1 and m["fn"] == 1 and m["precision"] == 1.0 and m["recall"] == 0.5


# ---- end-to-end decision labels ------------------------------------------------------------------

def test_policy_beats_when_baseline_misses_a_class():
    # narrow baseline rewrites only criticals (severity); trajectory-only failures are missed.
    rows = []
    for t in range(30):
        g = f"wd{chr(97 + t)}"
        pat = t % 3
        traj, sev = (1, 0) if pat == 0 else (0, 1) if pat == 1 else (0, 0)
        for arm in ("base", "framed"):
            rows.append(_mk(g, arm, traj, sev))
    rep = PB.run(rows, n_splits=5, seed=0)
    assert rep["decision"] == "PB_POLICY_BEATS_AUDIT_GATE"
    assert rep["csr_policy"]["f1"] > rep["baseline_needs_rewrite"]["f1"]
    assert rep["net_f1_improvement"]["excludes_zero"]
    # the policy recovered the frame_violation class the narrow gate missed
    assert (rep["per_class_recall"]["policy"]["frame_violation"] or 0) > \
        (rep["per_class_recall"]["baseline"]["frame_violation"] or 0)
    assert rep["missed_critical_rate"]["policy"] <= rep["missed_critical_rate"]["baseline"]


def test_repackaging_when_baseline_already_optimal():
    # baseline already == should_rewrite truth (perfect) -> policy can only match it
    rows = []
    for t in range(30):
        g = f"wd{chr(97 + t)}"
        sev = 1 if t % 2 == 0 else 0
        for arm in ("base", "framed"):
            r = _mk(g, arm, 0, sev)
            r["baseline_rewrite"] = r["truth"]["should_rewrite"]      # perfect baseline
            rows.append(r)
    rep = PB.run(rows, n_splits=5, seed=0)
    assert rep["decision"] == "PB_AUDIT_REPACKAGING_ONLY"
    assert rep["decision_agreement"] >= 0.97


def test_no_incremental_when_features_uninformative():
    # truth driven by an unobserved cause; features are all zero -> policy cannot help, disagrees w/ base
    rows = []
    for t in range(30):
        g = f"wd{chr(97 + t)}"
        should = t % 2 == 0
        for arm in ("base", "framed"):
            rows.append({"id": g, "arm": arm, "group": g, "baseline_rewrite": should,
                         "truth": {"frame_violation": False, "rejected_leak": False,
                                   "factuality": should, "secondary": False,
                                   "should_rewrite": should, "critical": should},
                         "feat": {"inv_match": 0.0, "traj_drift": 0.0, "guna": 0.0, "severity": 0.0},
                         "finding_types": []})
    rep = PB.run(rows, n_splits=5, seed=0)
    assert rep["decision"] in ("PB_POLICY_NO_INCREMENTAL_VALUE", "PB_AUDIT_REPACKAGING_ONLY")
    assert rep["csr_policy"]["f1"] <= rep["baseline_needs_rewrite"]["f1"]


def test_insufficient_label_power():
    rows = [_mk(f"t{t}", "base", 1 if t == 0 else 0, 0) for t in range(12)]   # 1 positive
    rep = PB.run(rows, n_splits=3, seed=0)
    assert rep["decision"] == "PB_INSUFFICIENT_LABEL_POWER"


def test_decision_label_set_and_markdown():
    assert set(PB.DECISIONS) == {"PB_POLICY_BEATS_AUDIT_GATE", "PB_POLICY_NO_INCREMENTAL_VALUE",
                                 "PB_AUDIT_REPACKAGING_ONLY", "PB_TERM_OVERLAP_INVALID",
                                 "PB_INSUFFICIENT_LABEL_POWER"}
    rows = [_mk(f"t{t}", "base", t % 2, (t + 1) % 2) for t in range(24)]
    md = PB.to_markdown(PB.run(rows, n_splits=4, seed=0))
    assert "CSR_policy vs Phase 3 needs_rewrite" in md and "DECISION:" in md
