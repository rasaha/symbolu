"""Report assembly + origin banner.

Collates the machinery sections into a deterministic, machine-readable report and
stamps the claim lock. On non-real data the report carries the TEST-DATA banner and
every verdict field holds a *_PATH_VERIFIED / *_NO_SCIENTIFIC_VERDICT outcome.
"""

from __future__ import annotations

from typing import Any, Dict, List

from cyber_security.behavioral_biometrics.study import origin
from cyber_security.behavioral_biometrics.study.effects import StudyEffects
from cyber_security.behavioral_biometrics.version import STUDY_VERSION

_SECTION_ORDER = ["dataset_eligibility", "quality_summary", "marginal_identity",
                  "multimodal_fusion", "coupling_use", "bcvf", "confidence_calibration",
                  "temporal_diagnostics", "confound_artifact_gates", "mechanical_verdicts",
                  "limitations", "origin_banner"]


def assemble(records: List[Dict[str, Any]], sections: Dict[str, Any],
             cfg: StudyEffects) -> Dict[str, Any]:
    lock = sections["claim_lock"]
    origin_label = lock["origin"]
    banner = origin.BANNER if lock["locked"] else None

    def verdict_of(key):
        s = sections.get(key, {})
        return s.get("verdict") if isinstance(s, dict) else s

    report = {
        "study_version": STUDY_VERSION,
        "origin_banner": banner,
        "data_origin": origin_label,
        "claim_lock": lock,
        "dataset_eligibility": sections.get("eligibility"),
        "leakage_check": sections.get("leakage_check"),
        "quality_summary": {"n_records": len(records),
                            "note": "quality gate applies at session level upstream"},
        "marginal_identity": {a: v for a, v in sections.get("identity_ablation", {}).items()
                              if a in ("K", "P", "T", "M", "MM")},
        "multimodal_fusion": {"ablation": {a: v for a, v in sections.get("identity_ablation", {}).items()
                                           if a.startswith("MM")},
                              "verdict": verdict_of("fusion"),
                              "analysis": sections.get("fusion", {}).get("analysis")},
        "coupling_use": {"verdict": verdict_of("use"),
                         "analysis": sections.get("use", {}).get("analysis")},
        "bcvf": {"verdict": verdict_of("bcvf"), "analysis": sections.get("bcvf", {}).get("analysis")},
        "confidence_calibration": {"verdict": verdict_of("confidence"),
                                   "analysis": sections.get("confidence", {}).get("analysis")},
        "temporal_diagnostics": sections.get("temporal", {"note": "no stream provided"}),
        "confound_artifact_gates": sections.get("confounds"),
        "estimators": sections.get("estimators"),
        "mechanical_verdicts": {
            "coupling_use": verdict_of("use"),
            "bcvf": verdict_of("bcvf"),
            "fusion": verdict_of("fusion"),
            "confidence": verdict_of("confidence"),
        },
        "limitations": _limitations(origin_label),
        "prereg": sections.get("prereg"),
    }
    return report


def _limitations(origin_label: str) -> List[str]:
    base = [
        "Estimator uncertainties in the end-to-end runner are documented proxies; the "
        "dedicated BCVF fixtures carry explicit σ.",
        "Coupling is credited only if it beats a fair all-modalities marginal baseline AND "
        "its shuffled/context-matched controls — never for more modalities or capacity.",
        "Temporal machinery is diagnostic-only and makes no security claim.",
    ]
    if origin_label != "REAL_PARTICIPANT":
        base.insert(0, f"Data origin is {origin_label}: NO scientific/biometric verdict is "
                       "emitted — outcomes are algorithm-path checks only.")
    return base


def summary_lines(report: Dict[str, Any]) -> List[str]:
    L = []
    if report.get("origin_banner"):
        L.append("=== " + report["origin_banner"] + " ===")
    L.append(f"origin: {report['data_origin']}  study: {report['study_version']}")
    elig = report.get("dataset_eligibility", {})
    L.append(f"eligibility met: {elig.get('met')}")
    mv = report["mechanical_verdicts"]
    for k, v in mv.items():
        L.append(f"{k}: {v}")
    return L
