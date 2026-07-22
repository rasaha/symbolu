"""
TAP-E5 evaluation harness.

For each case: compile the four frozen upstream records (E1 IntentRecord via the frozen E1
layer; E2/E3/E4 records via their public schemas), run each of the six baselines (A-F), and
score with the TAP-E5 packet metrics. Configuration selection uses the DEV split only (the
simplest baseline that satisfies every preregistered gate); the locked eval split is scored
once, for the verdict. Deterministic; no randomness.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Dict, List, Mapping, Sequence, Tuple

from truth_assurance_pipeline.tap_e5_evidence_assembly import (
    assembler, dependency_graph, metrics, packet_validator, schema,
)
from truth_assurance_pipeline.tap_e5_evidence_assembly.assembler import (
    BASELINES, AssemblyConfig, EvidenceAssemblyLayer,
)
from truth_assurance_pipeline.tap_e5_evidence_assembly.corpus import cases as corpus
from truth_assurance_pipeline.tap_e5_evidence_assembly.corpus.cases import Case


def _packet(cfg: AssemblyConfig, case: Case):
    return EvidenceAssemblyLayer(cfg).assemble(*corpus.build_records(case))


def run_config(cfg: AssemblyConfig, cs: Sequence[Case]) -> List[metrics.CaseScore]:
    return [metrics.score_case(case, _packet(cfg, case), cfg.validate_freeze) for case in cs]


def _deterministic(cfg: AssemblyConfig, cs: Sequence[Case]) -> float:
    for case in cs:
        if _packet(cfg, case).to_json() != _packet(cfg, case).to_json():
            return 0.0
    return 1.0


def _metrics_by_config(cs: Sequence[Case]) -> Dict[str, Dict]:
    out = {cfg.name: metrics.aggregate(run_config(cfg, cs)) for cfg in BASELINES}
    ref = out[BASELINES[0].name]["mean_object_count"] or 1.0
    for cfg in BASELINES:
        m = out[cfg.name]
        m["packet_size_reduction"] = round(max(0.0, 1.0 - m["mean_object_count"] / ref), 6)
        m["determinism"] = _deterministic(cfg, cs)
    return out


# --------------------------------------------------------------------------- #
# preregistered gates                                                         #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Gate:
    key: str
    op: str
    threshold: float


GATES: Tuple[Gate, ...] = (
    Gate("packet_completeness", ">=", 1.00),
    Gate("packet_minimality", ">=", 1.00),
    Gate("dependency_preservation", ">=", 1.00),
    Gate("provenance_preservation", ">=", 1.00),
    Gate("reference_integrity", ">=", 1.00),
    Gate("conflict_preservation", ">=", 1.00),
    Gate("gap_preservation", ">=", 1.00),
    Gate("duplicate_elimination", ">=", 1.00),
    Gate("unsupported_reference_rate", "<=", 0.00),
    Gate("orphan_rate", "<=", 0.00),
    Gate("validation_success", ">=", 1.00),
    Gate("packet_size_reduction", ">=", 0.05),
    Gate("determinism", ">=", 1.00),
    Gate("severe_critical_failure_count", "==", 0.0),
)


def _passes(g: Gate, v: float) -> bool:
    return (v >= g.threshold if g.op == ">=" else
            v <= g.threshold if g.op == "<=" else v == g.threshold)


def evaluate_gates(m: Mapping[str, object]) -> Dict[str, object]:
    res, ok_all = [], True
    for g in GATES:
        v = float(m[g.key])
        ok = _passes(g, v)
        ok_all = ok_all and ok
        res.append({"gate": g.key, "op": g.op, "threshold": g.threshold,
                    "value": round(v, 4), "pass": ok})
    return {"all_pass": ok_all, "gates": res}


def select_config(dev: Mapping[str, Mapping[str, object]]) -> str:
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
                "baseline. The claim is limited to mechanism/construction validation: TAP-E5 "
                "deterministically assembles a minimal, complete, provenance- and dependency-"
                "preserving EvidencePacket from frozen upstream TAP records on this study's "
                "synthetic corpus. It introduces no new reasoning, evidence, governance "
                "decision, or factual assertion; it validates no claim and resolves nothing.")
    if not selected_passes_dev:
        return ("INCONCLUSIVE",
                "No baseline satisfied all preregistered gates on the development split.")
    if not severe["pass"] or n_fail >= 3:
        return ("FAIL", f"{n_fail} preregistered gate(s) failed on the locked eval split.")
    return ("INCONCLUSIVE", f"{n_fail} preregistered gate(s) failed; evidence is mixed.")


def frozen_components_hash() -> str:
    from truth_assurance_pipeline.tap_e2_trusted_retrieval.evidence_unit import stable_hash
    src = {
        "assembler": inspect.getsource(assembler),
        "dependency_graph": inspect.getsource(dependency_graph),
        "packet_validator": inspect.getsource(packet_validator),
        "metrics": inspect.getsource(metrics),
        "schema": inspect.getsource(schema),
        "gates": [(g.key, g.op, g.threshold) for g in GATES],
        "baselines": [(c.name, c.dedup, c.prune, c.full_closure, c.preserve_provenance,
                       c.minimize, c.validate_freeze) for c in BASELINES],
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

    return {
        "schema_version": schema.SCHEMA_VERSION,
        "corpus_manifest": corpus.manifest(),
        "frozen_components_hash": frozen_components_hash(),
        "baselines": [{"name": c.name, "description": c.description} for c in BASELINES],
        "metrics": {"dev": dev_m, "eval_locked": eval_m},
        "selection": {
            "selected_config": selected, "selected_passes_dev": selected_passes_dev,
            "rule": "simplest baseline (A..F) satisfying ALL preregistered gates on DEV; "
                    "locked eval never used for selection",
            "dev_gate_pass": {c.name: evaluate_gates(dev_m[c.name])["all_pass"]
                              for c in BASELINES},
        },
        "gates": gate_result, "verdict": v, "verdict_reason": v_reason,
    }


if __name__ == "__main__":  # pragma: no cover
    import json
    r = run_all()
    print(json.dumps({k: v for k, v in r.items() if k != "metrics"}, indent=2, default=str))
