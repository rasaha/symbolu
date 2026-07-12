"""Instrumentation-pilot workflow: quality-gate → features → splits → analyses →
mechanical verdicts, assembled into one report.

Low-quality sessions are EXCLUDED from identity analysis but RECORDED in
``excluded_sessions`` with their reason — never silently dropped. Identity/coupling
verdicts are refused on synthetic data by the verdict layer.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from cyber_security.behavioral_biometrics import (
    analysis,
    features,
    quality,
    splits,
    verdicts,
)
from cyber_security.behavioral_biometrics.config import DEFAULT, BiometricConfig
from cyber_security.behavioral_biometrics.version import ANALYSIS_VERSION


def run_pilot(sessions: List[Dict[str, Any]], cfg: BiometricConfig = DEFAULT,
              identity_min_quality: str = quality.DEGRADED) -> Dict[str, Any]:
    """Assemble the full pilot report from raw sessions."""
    quality_summaries = []
    records = []
    excluded = []
    usable_records = []

    rank = {quality.READY: 2, quality.DEGRADED: 1, quality.NOT_READY: 0}
    min_rank = rank[identity_min_quality]

    for s in sessions:
        pid = s["session_meta"]["participant_pseudonym"]
        q = quality.analyze(s)
        q["participant"] = pid
        q["session_id"] = s["session_meta"]["session_id"]
        quality_summaries.append(q)
        rec = features.extract(s)
        records.append(rec)
        if rank[q["verdict"]] >= min_rank:
            usable_records.append(rec)
        else:
            excluded.append({"participant": pid, "session_id": q["session_id"],
                             "verdict": q["verdict"], "reasons": q["reasons"]})

    report: Dict[str, Any] = {
        "analysis_version": ANALYSIS_VERSION,
        "n_sessions": len(sessions),
        "n_usable_for_identity": len(usable_records),
        "excluded_sessions": excluded,
        "data_provenance": "SYNTHETIC_TEST_ONLY" if verdicts.data_is_synthetic(records) else "REAL",
    }

    # A — instrumentation
    report["A_instrument_quality"] = analysis.instrument_quality(quality_summaries)
    report["instrumentation_verdict"] = verdicts.instrumentation_verdict(quality_summaries)

    # identity analyses need a usable, leakage-safe split
    plan = splits.session_disjoint(usable_records, seed=cfg.master_seed)
    leaks = splits.check_leakage(plan, usable_records)
    report["split"] = {"name": plan.name, "leakage_violations": leaks,
                       "n_enroll_participants": len(plan.enroll)}

    report["B_within_user_repeatability"] = analysis.within_user_repeatability(usable_records, cfg)
    C = analysis.marginal_identity(usable_records, plan, cfg)
    report["C_marginal_identity"] = C
    D = analysis.coupling_residual(usable_records, plan, cfg)
    report["D_coupling_residual"] = D
    E = analysis.device_confound(usable_records, cfg)
    report["E_device_confound"] = E
    report["F_task_context_confound"] = analysis.task_context_confound(usable_records, plan, cfg)

    # mechanical, guarded verdicts
    report["marginal_signal_verdict"] = verdicts.marginal_signal_verdict(
        usable_records, C, quality_summaries, cfg)
    report["coupling_verdict"] = verdicts.coupling_verdict(
        usable_records, D, E, quality_summaries, cfg)
    report["minimums"] = verdicts.minimums_report(usable_records, quality_summaries, cfg)
    return report


def summary_lines(report: Dict[str, Any]) -> List[str]:
    """Human-readable one-liners (no raw input; safe to print)."""
    L = []
    L.append(f"provenance: {report['data_provenance']}  sessions: {report['n_sessions']}  "
             f"usable-for-identity: {report['n_usable_for_identity']}  "
             f"excluded: {len(report['excluded_sessions'])}")
    iv = report["instrumentation_verdict"]
    L.append(f"instrumentation: {iv['verdict']} (ready {iv['ready_fraction']:.2f})")
    C = report.get("C_marginal_identity", {})
    if C.get("usable"):
        L.append(f"marginal identity AUC: {C['auc']['point']:.3f} "
                 f"[{C['auc']['lo']:.3f},{C['auc']['hi']:.3f}]")
    L.append(f"marginal verdict: {report['marginal_signal_verdict']['verdict']}")
    L.append(f"coupling verdict: {report['coupling_verdict']['verdict']}")
    return L
