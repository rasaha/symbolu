"""Evaluation harness (§12).

Honesty rule: this harness does **not** fabricate benchmark numbers. Metrics that
require a *labeled evaluation corpus* (true-positive / false-escalation / miss
rates, lead time, detection-rate populations) have no corpus in-repo and are
reported as ``NOT RUN`` with the reason. Metrics that are genuinely measurable
from the built-in *illustrative* scenarios (determinism, explanation
completeness, dedup, bounded-state memory, mean-events-before-escalation on the
one demo sequence) are reported as ``measured (illustrative only)`` and are
explicitly not a benchmark.

Runtime-per-event is ``NOT RUN``: replay-mode determinism forbids wall-clock in
the authoritative path, and a meaningful figure needs a controlled corpus + host.
"""

from __future__ import annotations

from composite_threat_detector import BY_CASE, DIGITAL_ONTOLOGY, SequenceRiskAnalyzer, signals
from demos import scenarios

NOT_RUN = "NOT RUN"
_NO_CORPUS = "NOT RUN — no labeled evaluation corpus present in-repo"


def _determinism() -> str:
    a, _ = scenarios.run(DIGITAL_ONTOLOGY, scenarios.exfiltration_events)
    b, _ = scenarios.run(DIGITAL_ONTOLOGY, scenarios.exfiltration_events)
    ids_a = [f["finding_id"] for f in a]
    ids_b = [f["finding_id"] for f in b]
    return "PASS" if ids_a == ids_b and ids_a else "FAIL"


def _mean_events_before_escalation() -> object:
    az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY, specs=(BY_CASE,))
    n = 0
    for ev in scenarios.exfiltration_events:
        n += 1
        fs = az.observe(ev)
        if any(f.signal == signals.ESCALATE for f in fs):
            return n
    return NOT_RUN


def _explanation_completeness() -> object:
    fs, _ = scenarios.run(DIGITAL_ONTOLOGY, scenarios.exfiltration_events)
    if not fs:
        return NOT_RUN
    have = sum(1 for f in fs if f.get("explanation"))
    return round(have / len(fs), 4)


def _dedup_sensitivity() -> int:
    e = scenarios.exfiltration_events
    az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY, specs=(BY_CASE,))
    for ev in [e[0], e[0], e[1], e[1], e[2], e[3]]:
        az.observe(ev)
    return az.report.duplicates_suppressed


def _state_memory() -> dict:
    az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY, specs=(BY_CASE,))
    for ev in scenarios.exfiltration_events:
        az.observe(ev)
    tenants = az.ledger.tenant_count()
    assemblies = sum(az.ledger.assembly_count(t) for t in az.ledger._by_tenant)
    return {"tenants": tenants, "assemblies": assemblies}


def evaluate() -> dict:
    """Return the metric report. Values are numbers, PASS/FAIL, or NOT RUN."""
    return {
        "note": ("Illustrative scenarios only — NOT a benchmark. Population rates "
                 "require a labeled corpus and are marked NOT RUN."),
        "metrics": {
            "determinism_repeated_runs": _determinism(),
            "true_positive_rate": _NO_CORPUS,
            "false_escalation_rate": _NO_CORPUS,
            "miss_rate": _NO_CORPUS,
            "mean_events_before_escalation_illustrative": _mean_events_before_escalation(),
            "escalation_lead_time_before_completion": _NO_CORPUS,
            "cross_session_detection_rate": _NO_CORPUS,
            "multi_actor_detection_rate": _NO_CORPUS,
            "duplicate_sensitivity_illustrative": _dedup_sensitivity(),
            "state_memory_after_illustrative_run": _state_memory(),
            "runtime_per_event": (
                "NOT RUN — needs controlled corpus + host; excluded from "
                "replay-deterministic path"),
            "explanation_completeness_illustrative": _explanation_completeness(),
        },
    }
