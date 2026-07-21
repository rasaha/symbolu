"""
Deterministic evaluation harness: runs V0..V5 over every split, computes metrics,
applies PREREGISTERED gates to the selected config on the hidden eval split, and
issues a verdict (Sections 15, 16, 22).

Determinism: no randomness anywhere; two runs return byte-identical output. A result
manifest hashes the frozen components + corpus so a re-run can prove zero drift.

Gate discipline (Section 22): the gates and thresholds in ``GATES`` are fixed BEFORE
the hidden set is scored and are mirrored in
``experiments/preregistration.json``. They are not changed after seeing results.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Callable, Dict, List, Mapping, Sequence, Tuple

from truth_assurance_pipeline.tap_e1_intent import (
    ambiguity, clarification, conflicts, extraction, interpreter, metrics,
)
from truth_assurance_pipeline.tap_e1_intent.corpus import cases as corpus_cases
from truth_assurance_pipeline.tap_e1_intent.corpus.cases import Case
from truth_assurance_pipeline.tap_e1_intent.interpreter import (
    ABLATIONS, AblationConfig, IntentUnderstandingLayer,
)
from truth_assurance_pipeline.tap_e1_intent.metrics import CaseScore, aggregate, score_case
from truth_assurance_pipeline.tap_e1_intent.schema import RawUserRequest, stable_hash


# --------------------------------------------------------------------------- #
# Preregistered gates (fixed before hidden-set scoring)                       #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Gate:
    key: str
    op: str          # ">=" or "<=" or "=="
    threshold: float
    rationale: str

    def passes(self, value: float) -> bool:
        if self.op == ">=":
            return value >= self.threshold
        if self.op == "<=":
            return value <= self.threshold
        if self.op == "==":
            return value == self.threshold
        raise ValueError(self.op)


GATES: Tuple[Gate, ...] = (
    Gate("explicit_constraint_preservation", ">=", 0.90,
         "explicit user constraints must be preserved, not dropped"),
    Gate("unsupported_assumption_rate", "<=", 0.15,
         "the layer must rarely introduce content the user did not provide"),
    Gate("material_ambiguity_recall", ">=", 0.80,
         "materially different interpretations must be detected"),
    Gate("unnecessary_clarification_rate", "<=", 0.15,
         "the layer must not over-ask on harmless ambiguity"),
    Gate("severe_failure_count", "==", 0.0,
         "no critical (Section 17) failures on the hidden set for the chosen config"),
)


# --------------------------------------------------------------------------- #
# Running one config over a split                                             #
# --------------------------------------------------------------------------- #

def _to_request(case: Case) -> RawUserRequest:
    return RawUserRequest(case.case_id, case.text, case.conversation, case.metadata)


def run_config_on_cases(cfg: AblationConfig, cases: Sequence[Case]
                        ) -> List[CaseScore]:
    layer = IntentUnderstandingLayer(cfg)
    out: List[CaseScore] = []
    for case in cases:
        rec = layer.interpret(_to_request(case))
        out.append(score_case(case, rec))
    return out


def _metrics_by_config(cases: Sequence[Case]) -> Dict[str, Dict[str, object]]:
    return {cfg.name: aggregate(run_config_on_cases(cfg, cases))
            for cfg in ABLATIONS}


# --------------------------------------------------------------------------- #
# Config selection (on DEV only — never on the hidden set)                    #
# --------------------------------------------------------------------------- #

def _selection_score(m: Mapping[str, object]) -> float:
    """Documented selection criterion (Section 15): reward constraint preservation,
    material-ambiguity recall, and low unsupported-assumption / unnecessary-
    clarification. Simpler configs win ties (handled by caller order)."""
    crit = m["critical_failures"]
    severe = float(m["severe_failure_count"])
    return round(
        1.5 * float(m["explicit_constraint_preservation"])
        + 1.0 * float(m["material_ambiguity_recall"])
        + 1.0 * (1.0 - float(m["unsupported_assumption_rate"]))
        + 0.5 * (1.0 - float(m["unnecessary_clarification_rate"]))
        + 0.5 * float(m["negation_preservation"])
        - 0.25 * severe, 6)


def select_config(dev_metrics: Mapping[str, Mapping[str, object]]) -> str:
    best_name = ABLATIONS[0].name
    best_score = float("-inf")
    for cfg in ABLATIONS:  # ascending complexity; strict '>' keeps the simplest tie
        s = _selection_score(dev_metrics[cfg.name])
        if s > best_score:
            best_score = s
            best_name = cfg.name
    return best_name


# --------------------------------------------------------------------------- #
# Gate evaluation + verdict                                                   #
# --------------------------------------------------------------------------- #

def evaluate_gates(eval_metrics: Mapping[str, object]) -> Dict[str, object]:
    results = []
    all_pass = True
    for g in GATES:
        val = float(eval_metrics[g.key]) if g.key != "severe_failure_count" \
            else float(eval_metrics["severe_failure_count"])
        ok = g.passes(val)
        all_pass = all_pass and ok
        results.append({"gate": g.key, "op": g.op, "threshold": g.threshold,
                        "value": val, "pass": ok, "rationale": g.rationale})
    return {"all_pass": all_pass, "gates": results}


def verdict(gate_result: Mapping[str, object]) -> Tuple[str, str]:
    gates = gate_result["gates"]
    n_fail = sum(1 for g in gates if not g["pass"])
    severe_gate = next(g for g in gates if g["gate"] == "severe_failure_count")
    constraint_gate = next(g for g in gates
                           if g["gate"] == "explicit_constraint_preservation")

    if n_fail == 0:
        # Even a clean pass is capped: synthetic corpus + deterministic stand-in
        # for the model interpreter (Section 21) -> limited claim only.
        return ("PASS_WITH_LIMITED_CLAIM",
                "All preregistered gates pass on the hidden set. The claim is limited "
                "to mechanism/construction validation on a synthetic, human-authored "
                "corpus using a deterministic interpreter (not an LLM). No claim of "
                "real-world accuracy, downstream truth improvement, or production "
                "readiness is made.")
    if constraint_gate["value"] < 0.70 or n_fail >= 2:
        return ("FAIL",
                f"{n_fail} preregistered gate(s) failed on the hidden set "
                "(including or beyond the severity threshold).")
    if not severe_gate["pass"] or n_fail == 1:
        return ("INCONCLUSIVE",
                f"{n_fail} preregistered gate(s) failed; evidence is mixed and does "
                "not support even a limited pass.")
    return ("INCONCLUSIVE", "mixed gate outcome")


# --------------------------------------------------------------------------- #
# Locks / manifest                                                            #
# --------------------------------------------------------------------------- #

def frozen_components_hash() -> str:
    src = {
        "schema": inspect.getsource(
            __import__("truth_assurance_pipeline.tap_e1_intent.schema",
                       fromlist=["x"])),
        "extraction": inspect.getsource(extraction),
        "provenance": inspect.getsource(
            __import__("truth_assurance_pipeline.tap_e1_intent.provenance",
                       fromlist=["x"])),
        "ambiguity": inspect.getsource(ambiguity),
        "conflicts": inspect.getsource(conflicts),
        "clarification": inspect.getsource(clarification),
        "interpreter": inspect.getsource(interpreter),
        "metrics": inspect.getsource(metrics),
        "gates": [(g.key, g.op, g.threshold) for g in GATES],
        "ablations": [(c.name, c.structured, c.deterministic, c.provenance,
                       c.ambiguity_conflict, c.clarification) for c in ABLATIONS],
    }
    return stable_hash(src)


# --------------------------------------------------------------------------- #
# Full run                                                                    #
# --------------------------------------------------------------------------- #

def run_all() -> Dict[str, object]:
    dev = corpus_cases.cases_for_split("dev")
    ev = corpus_cases.cases_for_split("eval")
    neg = corpus_cases.cases_for_split("negative")
    adv = corpus_cases.cases_for_split("adversarial")

    dev_metrics = _metrics_by_config(dev)
    eval_metrics = _metrics_by_config(ev)
    neg_metrics = _metrics_by_config(neg)
    adv_metrics = _metrics_by_config(adv)

    selected = select_config(dev_metrics)
    gate_result = evaluate_gates(eval_metrics[selected])
    v, v_reason = verdict(gate_result)

    return {
        "schema_version": interpreter.SCHEMA_VERSION,
        "corpus_manifest": corpus_cases.corpus_manifest(),
        "frozen_components_hash": frozen_components_hash(),
        "ablations": [{"name": c.name, "description": c.description}
                      for c in ABLATIONS],
        "metrics": {
            "dev": dev_metrics,
            "eval_hidden": eval_metrics,
            "negative": neg_metrics,
            "adversarial": adv_metrics,
        },
        "selection": {
            "selected_config": selected,
            "selection_scores_dev": {c.name: _selection_score(dev_metrics[c.name])
                                     for c in ABLATIONS},
            "rule": "argmax on DEV of a documented weighted criterion; simplest "
                    "config wins ties; hidden set never used for selection",
        },
        "gates": gate_result,
        "verdict": v,
        "verdict_reason": v_reason,
    }


if __name__ == "__main__":  # pragma: no cover
    import json
    print(json.dumps(run_all(), indent=2, sort_keys=True))
