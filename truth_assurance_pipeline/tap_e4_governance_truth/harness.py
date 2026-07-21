"""
TAP-E4 evaluation harness.

For each case: build an IntentRecord with the FROZEN TAP-E1 layer, assemble a TAP-E2
RetrievalRecord and a TAP-E3 RelationshipRecord from the case's specs (frozen upstream
structures), run each of the six baselines (A-F), and score with the TAP-E4 metrics.

Configuration selection uses the DEV split ONLY — the simplest baseline (A..F) that
satisfies every preregistered gate. The locked eval split is scored once, for the verdict,
and is never consulted during selection.

Deterministic; no randomness.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Dict, List, Mapping, Sequence, Tuple

from truth_assurance_pipeline.tap_e1_intent import IntentUnderstandingLayer, config as e1_config
from truth_assurance_pipeline.tap_e1_intent.schema import RawUserRequest
from truth_assurance_pipeline.tap_e4_governance_truth import applicability, metrics
from truth_assurance_pipeline.tap_e4_governance_truth.applicability import (
    BASELINES, GovernanceConfig, GovernanceTruthLayer,
)
from truth_assurance_pipeline.tap_e4_governance_truth.corpus import cases as corpus
from truth_assurance_pipeline.tap_e4_governance_truth.corpus.cases import Case
from truth_assurance_pipeline.tap_e4_governance_truth.validator import require_valid

_E1 = IntentUnderstandingLayer(e1_config("V4"))
_INTENT_CACHE: Dict[str, object] = {}


def _intent(case: Case):
    if case.case_id not in _INTENT_CACHE:
        _INTENT_CACHE[case.case_id] = _E1.interpret(
            RawUserRequest(case.case_id, case.request_text))
    return _INTENT_CACHE[case.case_id]


def run_config(cfg: GovernanceConfig, cs: Sequence[Case]) -> List[metrics.CaseScore]:
    layer = GovernanceTruthLayer(cfg)
    out = []
    for case in cs:
        intent = _intent(case)
        retrieval = corpus.build_retrieval_record(case)
        relationship = corpus.build_relationship_record(case)
        require_valid(intent, retrieval, relationship)
        rec = layer.resolve(intent, retrieval, relationship, case.situation)
        out.append(metrics.score_case(case, rec))
    return out


def _metrics_by_config(cs: Sequence[Case]) -> Dict[str, Dict]:
    return {cfg.name: metrics.aggregate(run_config(cfg, cs)) for cfg in BASELINES}


# --------------------------------------------------------------------------- #
# preregistered gates                                                         #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Gate:
    key: str
    op: str
    threshold: float


GATES: Tuple[Gate, ...] = (
    Gate("governing_authority_accuracy", ">=", 0.90),
    Gate("jurisdiction_accuracy", ">=", 0.90),
    Gate("scope_accuracy", ">=", 0.90),
    Gate("temporal_accuracy", ">=", 0.95),
    Gate("version_accuracy", ">=", 0.90),
    Gate("exception_accuracy", ">=", 0.90),
    Gate("precedence_accuracy", ">=", 0.90),
    Gate("governance_conflict_f1", ">=", 0.75),
    Gate("governance_gap_accuracy", ">=", 0.75),
    Gate("provenance_completeness", "==", 1.00),
    Gate("unsupported_governance_rate", "<=", 0.05),
    Gate("incorrect_override_rate", "==", 0.0),
    Gate("expired_policy_selection_rate", "==", 0.0),
    Gate("severe_critical_failure_count", "==", 0.0),
)


def _passes(g: Gate, v: float) -> bool:
    return (v >= g.threshold if g.op == ">=" else
            v <= g.threshold if g.op == "<=" else v == g.threshold)


def evaluate_gates(m: Mapping[str, object]) -> Dict[str, object]:
    res = []
    ok_all = True
    for g in GATES:
        v = float(m[g.key])
        ok = _passes(g, v)
        ok_all = ok_all and ok
        res.append({"gate": g.key, "op": g.op, "threshold": g.threshold,
                    "value": round(v, 4), "pass": ok})
    return {"all_pass": ok_all, "gates": res}


def select_config(dev: Mapping[str, Mapping[str, object]]) -> str:
    """Simplest baseline (A..F order) that satisfies ALL gates on DEV."""
    for cfg in BASELINES:
        if evaluate_gates(dev[cfg.name])["all_pass"]:
            return cfg.name
    return BASELINES[-1].name


def verdict(gate_result: Mapping[str, object], selected_passes_dev: bool) -> Tuple[str, str]:
    n_fail = sum(1 for g in gate_result["gates"] if not g["pass"])
    severe = next(g for g in gate_result["gates"]
                  if g["gate"] == "severe_critical_failure_count")
    if n_fail == 0:
        return ("PASS_WITH_LIMITED_CLAIM",
                "All preregistered gates pass on the locked eval split for the selected "
                "baseline. The claim is limited to mechanism/construction validation: a "
                "deterministic, provenance-preserving governance-resolution architecture "
                "(authority precedence, jurisdiction, scope, temporal/version, supersession, "
                "exception, conflict, gap) on the synthetic corpus used in this study. No "
                "claim of production legal/regulatory reasoning or external generalization.")
    if not selected_passes_dev:
        return ("INCONCLUSIVE",
                "No baseline satisfied all preregistered gates on the development split.")
    if not severe["pass"] or n_fail >= 3:
        return ("FAIL", f"{n_fail} preregistered gate(s) failed on the locked eval split.")
    return ("INCONCLUSIVE", f"{n_fail} preregistered gate(s) failed; evidence is mixed.")


def frozen_components_hash() -> str:
    from truth_assurance_pipeline.tap_e2_trusted_retrieval.evidence_unit import stable_hash
    from truth_assurance_pipeline.tap_e4_governance_truth import (
        authority, confidence, conflict_resolution, exceptions, jurisdiction, precedence,
        scope, temporal,
    )
    src = {
        "applicability": inspect.getsource(applicability),
        "authority": inspect.getsource(authority),
        "precedence": inspect.getsource(precedence),
        "conflict_resolution": inspect.getsource(conflict_resolution),
        "confidence": inspect.getsource(confidence),
        "jurisdiction": inspect.getsource(jurisdiction),
        "scope": inspect.getsource(scope),
        "temporal": inspect.getsource(temporal),
        "exceptions": inspect.getsource(exceptions),
        "metrics": inspect.getsource(metrics),
        "gates": [(g.key, g.op, g.threshold) for g in GATES],
        "baselines": [(c.name, c.first_match, c.highest_authority, c.jurisdiction,
                       c.temporal_version, c.exceptions_precedence, c.full) for c in BASELINES],
    }
    return stable_hash(src)


def run_all() -> Dict[str, object]:
    dev = corpus.cases_for_split("dev")
    ev = corpus.cases_for_split("eval")
    dev_m = _metrics_by_config(dev)
    eval_m = _metrics_by_config(ev)

    selected = select_config(dev_m)
    selected_passes_dev = evaluate_gates(dev_m[selected])["all_pass"]
    gate_result = evaluate_gates(eval_m[selected])
    v, v_reason = verdict(gate_result, selected_passes_dev)

    from truth_assurance_pipeline.tap_e4_governance_truth.authority import (
        AUTHORITY_MODEL_VERSION,
    )
    from truth_assurance_pipeline.tap_e4_governance_truth.precedence import (
        PRECEDENCE_RULES_VERSION,
    )
    from truth_assurance_pipeline.tap_e4_governance_truth.schema import SCHEMA_VERSION
    return {
        "schema_version": SCHEMA_VERSION,
        "authority_model_version": AUTHORITY_MODEL_VERSION,
        "precedence_rules_version": PRECEDENCE_RULES_VERSION,
        "corpus_manifest": corpus.manifest(),
        "frozen_components_hash": frozen_components_hash(),
        "baselines": [{"name": c.name, "description": c.description} for c in BASELINES],
        "metrics": {"dev": dev_m, "eval_locked": eval_m},
        "selection": {
            "selected_config": selected,
            "selected_passes_dev": selected_passes_dev,
            "rule": "simplest baseline (A..F) satisfying ALL preregistered gates on DEV; "
                    "locked eval never used for selection",
            "dev_gate_pass": {c.name: evaluate_gates(dev_m[c.name])["all_pass"]
                              for c in BASELINES},
        },
        "gates": gate_result,
        "verdict": v, "verdict_reason": v_reason,
    }


if __name__ == "__main__":  # pragma: no cover
    import json
    r = run_all()
    print(json.dumps({k: v for k, v in r.items() if k != "metrics"}, indent=2, default=str))
