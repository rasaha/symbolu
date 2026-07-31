"""Evaluation harness (§11, §12, §17).

Two layers of honesty:

1. Metrics requiring a *labeled enterprise* corpus (real-world accuracy, live
   enforcement) are ``NOT RUN`` / ``REQUIRES ENTERPRISE DATA``.
2. Metrics measurable on the *synthetic* corpus are computed and labeled
   ``Measured — synthetic corpus`` — explicitly NOT enterprise performance and
   NOT unknown-threat coverage.

Every reported value carries an evidence-discipline label (§17). Results are
broken down by family/split/etc; they are never collapsed into one accuracy
number.
"""

from __future__ import annotations

from composite_threat_detector import (
    BY_ACTOR, BY_CASE, DIGITAL_ONTOLOGY, FixtureProvider, ProviderRegistry,
    SequenceRiskAnalyzer, StateLimits, signals,
)
from demos import scenarios

from . import corpus as corpus_mod

NOT_RUN = "NOT RUN"
REQUIRES_ENTERPRISE = "REQUIRES ENTERPRISE DATA"
SYNTHETIC = "Measured — synthetic corpus"
UNIT = "Measured — unit/integration test"
MODELED = "Modeled — operational projection"


def _specs_for(scenario):
    if scenario["family"] == "cross_session":
        return (BY_ACTOR,)
    return (BY_CASE,)


def _run_scenario(scenario):
    providers = None
    if scenario["providers"]:
        providers = ProviderRegistry(providers=(
            FixtureProvider("corpus-fx", "1.0.0", scenario["providers"]),))
    kwargs = {"specs": _specs_for(scenario), "providers": providers}
    if scenario["family"] == "state_exhaustion":
        kwargs["limits"] = StateLimits(max_instances_per_assembly=1)
    az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY, **kwargs)
    escalated = unavailable = False
    first_escalation_event = None
    for i, ev in enumerate(scenario["events"], 1):
        for f in az.observe(ev):
            if f.signal == signals.ESCALATE:
                escalated = True
                first_escalation_event = first_escalation_event or i
            if f.signal == signals.UNAVAILABLE:
                unavailable = True
    return {"escalated": escalated, "unavailable": unavailable,
            "events": len(scenario["events"]),
            "first_escalation_event": first_escalation_event}


def evaluate_corpus() -> dict:
    """Run the synthetic corpus and compute labeled, broken-down metrics."""
    corpus = corpus_mod.build_corpus()
    rows = []
    for s in corpus:
        r = _run_scenario(s)
        rows.append({**{k: s[k] for k in ("scenario_id", "family", "label",
                                          "expected_escalation", "difficulty", "split")},
                     **r})

    harmful = [r for r in rows if r["label"] == corpus_mod.HARMFUL
               and r["expected_escalation"]]
    benign = [r for r in rows if r["label"] == corpus_mod.BENIGN]
    unknown = [r for r in rows if r["label"] == corpus_mod.UNKNOWN]

    tp = sum(1 for r in harmful if r["escalated"])
    fn = sum(1 for r in harmful if not r["escalated"])
    fp = sum(1 for r in benign if r["escalated"] and r["expected_escalation"] is False)

    def _ratio(n, d):
        return round(n / d, 4) if d else NOT_RUN

    by_family = {}
    for r in rows:
        by_family.setdefault(r["family"], {"escalated": 0, "count": 0})
        by_family[r["family"]]["count"] += 1
        by_family[r["family"]]["escalated"] += int(r["escalated"])

    wrongly_silenced = sum(1 for r in benign if r["expected_escalation"] and not r["escalated"])
    look_alikes = max(1, sum(1 for r in benign if r["expected_escalation"]))

    return {
        "evidence_label": SYNTHETIC,
        "disclaimer": ("Synthetic corpus only. NOT enterprise performance, NOT "
                       "live enforcement evidence, NOT unknown-threat coverage. "
                       "Encoded-recipe recall != unknown-threat recall."),
        "corpus_size": len(rows),
        "splits": {sp: sum(1 for r in rows if r["split"] == sp)
                   for sp in ("dev", "calibration", "final")},
        "metrics": {
            "true_positive_rate_encoded": {"value": _ratio(tp, len(harmful)),
                                           "label": SYNTHETIC, "n": len(harmful)},
            "false_escalation_rate": {"value": _ratio(fp, len(benign)),
                                      "label": SYNTHETIC, "n": len(benign)},
            "miss_rate_encoded": {"value": _ratio(fn, len(harmful)),
                                  "label": SYNTHETIC, "n": len(harmful)},
            "precision": {"value": _ratio(tp, tp + fp), "label": SYNTHETIC},
            "recall_encoded": {"value": _ratio(tp, tp + fn), "label": SYNTHETIC},
            "unknown_threat_detection": {
                "value": _ratio(sum(1 for r in unknown if r["escalated"]), len(unknown)),
                "label": SYNTHETIC, "n": len(unknown),
                "note": "expected ~0: unknown threats are not encoded"},
            "mean_events_before_escalation": {
                "value": _mean([r["first_escalation_event"] for r in harmful]),
                "label": SYNTHETIC},
            "alerts_per_1000_events": {"value": _alerts_per_1000(rows), "label": SYNTHETIC},
            "incorrect_benign_neutralization_rate": {
                "value": round(wrongly_silenced / look_alikes, 4), "label": SYNTHETIC,
                "note": "benign look-alikes lacking valid auth wrongly silenced"},
            "escalation_lead_time_before_completion": {
                "value": REQUIRES_ENTERPRISE,
                "note": "needs labeled completion index"},
            "entity_linkage_error_rate": {"value": NOT_RUN,
                                          "note": "needs labeled linkage ground truth"},
            "alerts_per_tenant_day": {"value": REQUIRES_ENTERPRISE},
            "peak_state_per_tenant": {"value": REQUIRES_ENTERPRISE},
            "runtime_per_event": {"value": NOT_RUN,
                                  "note": "excluded from replay-deterministic path"},
            "determinism_across_replay": {"value": _determinism(), "label": UNIT},
        },
        "breakdown_by_family": by_family,
        "breakdown_by_split": _by_split(rows),
    }


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 3) if xs else NOT_RUN


def _alerts_per_1000(rows):
    total = sum(r["events"] for r in rows)
    alerts = sum(1 for r in rows if r["escalated"])
    return round(alerts * 1000 / total, 2) if total else NOT_RUN


def _by_split(rows):
    out = {}
    for sp in ("dev", "calibration", "final"):
        srows = [r for r in rows if r["split"] == sp]
        out[sp] = {"count": len(srows),
                   "escalated": sum(1 for r in srows if r["escalated"])}
    return out


def _determinism() -> str:
    h1 = corpus_mod.manifest()["corpus_hash"]
    h2 = corpus_mod.manifest()["corpus_hash"]
    d1 = [f["finding_id"] for f in scenarios.run(
        DIGITAL_ONTOLOGY, scenarios.exfiltration_events)[0]]
    d2 = [f["finding_id"] for f in scenarios.run(
        DIGITAL_ONTOLOGY, scenarios.exfiltration_events)[0]]
    return "PASS" if h1 == h2 and d1 == d2 and d1 else "FAIL"


def evaluate() -> dict:
    """Entry point (CLI ``eval``): runs the synthetic-corpus evaluation."""
    return evaluate_corpus()
