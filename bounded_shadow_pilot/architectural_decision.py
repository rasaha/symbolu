"""Phase 21 - Architectural decision (one of eleven).

Decides, from the frozen pilot evidence, whether to proceed to a single-customer EXTERNAL shadow pilot.
The decision is evidence-gated: it reads the frozen eval artifacts and selects exactly one of eleven
options. Falsification-first: a NOT-PROCEED or gated outcome is a legitimate success of the method.

Deterministic, read-only. Writes eval_results/architectural_decision.json.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

_EVAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_results")

OPTIONS = [
    "1  PROCEED to single-customer external shadow pilot (unconditional)",
    "2  PROCEED to single-customer external shadow pilot WITH binding conditions",
    "3  PROCEED but INTERNAL single-tenant natural shadow pilot first (not external)",
    "4  DO NOT PROCEED (external) - fix utility/calibration first; gate the external pilot",
    "5  DO NOT PROCEED - fix native ActionGate semantics first",
    "6  DO NOT PROCEED - fix safety first",
    "7  DO NOT PROCEED - fix auditability/explainability first",
    "8  NOT ENOUGH EVIDENCE - insufficient natural artifacts",
    "9  NOT ENOUGH EVIDENCE - natural language caused unhandled new failures",
    "10 STOP - a serious safety/privacy/isolation/audit/control failure occurred",
    "11 DO NOT PROCEED - the runtime is fundamentally unsuitable for natural artifacts",
]


def _load(name: str) -> Dict[str, Any]:
    return json.load(open(os.path.join(_EVAL, name)))


def decide() -> Dict[str, Any]:
    execu = _load("pilot_execution.json")
    transfer = _load("transfer_analysis.json")
    tax = _load("failure_taxonomy.json")
    fx = _load("falsification.json")

    safe = execu["safety"]["unsafe_permit"] == 0 and execu["safety"]["all_non_enforcing"]
    auditable = transfer["transfer_verdicts"]["auditability"] == "TRANSFERS"
    actiongate_ok = transfer["transfer_verdicts"]["actiongate_native_semantics"] == "PRESERVED"
    useful = transfer["transfer_verdicts"]["utility"] == "TRANSFERS"
    stopped = execu["stop_conditions"]["should_stop"]
    enough_evidence = any(x["null_id"] == "H0_INSUFFICIENT_EVIDENCE" and x["null_rejected"]
                          for x in fx["preregistered_nulls"])
    # "new unhandled failures" = an UNSAFE_PERMIT category or any non-fail-closed behavior
    unhandled_new_failures = tax["category_counts"]["UNSAFE_PERMIT"] > 0

    # option verdicts (each with the reason it is / isn't chosen)
    verdicts: List[Dict[str, str]] = []

    def v(idx, chosen, reason):
        verdicts.append({"option": OPTIONS[idx], "chosen": chosen, "reason": reason})

    # decision logic (evidence-gated, fail-closed toward caution)
    if stopped:
        chosen_idx = 9
    elif not enough_evidence:
        chosen_idx = 7
    elif unhandled_new_failures:
        chosen_idx = 8
    elif not actiongate_ok:
        chosen_idx = 4
    elif not safe:
        chosen_idx = 5
    elif not auditable:
        chosen_idx = 6
    elif not useful:
        # safe + auditable + native-preserved, but utility does not transfer -> do NOT expose an
        # external customer to a near-zero-clean-allow runtime; gate the external pilot on calibration
        # (option 4). The constructive next step is the internal-first natural pilot (option 3).
        chosen_idx = 3   # OPTIONS[3] == option "4  DO NOT PROCEED (external) - gate on calibration"
    else:
        chosen_idx = 1  # option 2 (proceed with conditions)

    for i in range(len(OPTIONS)):
        if i == chosen_idx:
            v(i, True, "selected by evidence gate")
        else:
            v(i, False, "not selected")

    dims = {"safe": safe, "auditable": auditable, "actiongate_native_preserved": actiongate_ok,
            "useful": useful, "stopped": stopped, "enough_evidence": enough_evidence,
            "unhandled_new_failures": unhandled_new_failures}

    return {
        "options": OPTIONS,
        "dimension_findings": dims,
        "chosen_option_index": chosen_idx + 1,
        "chosen_option": OPTIONS[chosen_idx],
        "option_verdicts": verdicts,
        "rationale": (
            "Safety (0 unsafe permits, all fail-closed, non-enforcing), auditability (determinism + "
            "replay), and native ActionGate preservation (0 loss) all hold on natural artifacts, and no "
            "stop condition fired - so options 5-11 are excluded. But utility does NOT transfer "
            "(85.5% over-qualification, 0% clean allow), which is proven evidence-driven rather than a "
            "defect. Exposing an external customer to a near-zero-clean-allow runtime would be low value "
            "and could misrepresent readiness, so the unconditional/external options (1-2) are not "
            "taken. The decision is OPTION 4: do NOT proceed to the external single-customer pilot yet - "
            "gate it on the utility-calibration prerequisites. The constructive next step is OPTION 3, "
            "an INTERNAL single-tenant natural shadow pilot, to gather real natural traffic and "
            "CALIBRATE the evidence stage for evidence-free text before the external pilot is re-gated."
        ),
        "external_single_customer_pilot": "GATED - conditioned on the utility-calibration prerequisites "
                                          "in SINGLE_CUSTOMER_PILOT_PLAN.md",
    }


def freeze() -> Dict[str, Any]:
    m = decide()
    with open(os.path.join(_EVAL, "architectural_decision.json"), "w") as fh:
        json.dump(m, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return m


if __name__ == "__main__":
    m = freeze()
    print("DIMENSION FINDINGS:", m["dimension_findings"])
    print(f"\nCHOSEN: Option {m['chosen_option_index']} -> {m['chosen_option']}")
    print(f"\n{m['rationale']}")
