#!/usr/bin/env python3
"""Torch-free integrity verifier for the BindingSlots value-path / gradient diagnosis.

Checks (whether or not training evidence is present):
  * frozen source hashes match the live files (nothing frozen was edited);
  * cohort is well-formed, frozen-before-inspection, and a subset of the persistence reserved seeds;
  * preregistration decision constants match the classifier;
  * the read-path binding forbids fusion-gate reporting and none is reported;
  * no artifact emits READY_FOR_KDA_VALIDATION; KDA stays BLOCKED.
When results exist it additionally checks the reproduction gate, param-group completeness, unchanged
diagnostic state hashes, and that the verdict is one of the allowed strings.

Prints BINDINGSLOTS_VALUE_PATH_DIAGNOSIS_VERIFIED with <checks>/<failures>, else a failure verdict.
"""
from __future__ import annotations

import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]

ALLOWED_VERDICTS = {
    "BINDINGSLOTS_BOTH_FAILURE_FAMILIES_LOCALIZED", "BINDINGSLOTS_VALUE_PATH_FAILURE_LOCALIZED",
    "BINDINGSLOTS_QUALITY_INTERFERENCE_LOCALIZED", "BINDINGSLOTS_DIAGNOSTIC_RESULTS_INCONCLUSIVE",
    "BINDINGSLOTS_INSTRUMENTED_REPRODUCTION_FAILED", "BINDINGSLOTS_DIAGNOSTIC_PROTOCOL_VIOLATED",
    "BINDINGSLOTS_DIAGNOSTIC_INTEGRITY_FAILED", "BINDINGSLOTS_DIAGNOSTIC_RESOURCE_BLOCKED",
}
PERSISTENCE_SEEDS = {23, 24, 25, 26, 27}
ARMS = {"A+", "R0", "O1R", "H2"}


def main() -> int:
    checks = []

    def ok(cond, name):
        checks.append((name, bool(cond)))

    proto = json.loads((HERE / "reproduction_protocol.json").read_text())
    for rel, want in proto["frozen_source_hashes_sha256"].items():
        got = hashlib.sha256((REPO / rel).read_bytes()).hexdigest()
        ok(got == want, f"frozen_hash:{pathlib.Path(rel).name}")

    cohort = json.loads((HERE / "cohort.json").read_text())
    ok(cohort.get("frozen_before_tensor_inspection") is True, "cohort_frozen_before_inspection")
    ok(len(cohort["members"]) == 12, "cohort_size_12")
    ok(all(m["arm"] in ARMS for m in cohort["members"]), "cohort_arms_valid")
    ok(all(m["seed"] in PERSISTENCE_SEEDS for m in cohort["members"]), "cohort_seeds_subset_of_persistence")
    ok(len({(m["arm"], m["seed"]) for m in cohort["members"]}) == 12, "cohort_unique")

    # preregistration constants == classifier constants
    import sys
    sys.path.insert(0, str(HERE))
    import diagnosis_classify as DC  # noqa: E402
    prereg = json.loads((HERE / "preregistration.json").read_text())
    pc = prereg["frozen_decision_constants"]
    for k in ("DECODABLE_MIN", "MATERIAL_DROP", "RETRIEVAL_PRESENT_MIN", "RETRIEVAL_FAILS_MAX",
              "RECOVER_MIN", "CONFLICT_COS", "CONTROL_GAP"):
        ok(getattr(DC, k) == pc[k], f"prereg_constant:{k}")
    ok(prereg["implements_fix"] is False, "no_fix")
    ok(prereg["always_emit"] == "KDA_VALIDATION_BLOCKED", "kda_blocked_declared")

    # No fusion-gate metric is REPORTED and no readiness is EMITTED. These are value-level checks over
    # the produced results artifacts (prose prohibitions in the prereg legitimately name both tokens,
    # so grepping text would false-positive; we inspect parsed JSON keys/values instead).
    def _walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield ("key", str(k))
                yield from _walk(v)
        elif isinstance(o, list):
            for v in o:
                yield from _walk(v)
        else:
            yield ("val", o)

    leak = []
    for f in sorted((HERE / "results").glob("*.json")) if (HERE / "results").exists() else []:
        try:
            obj = json.loads(f.read_text())
        except Exception:
            continue
        for kind, item in _walk(obj):
            if kind == "key" and "fusion_gate" in item.lower():
                leak.append(f"fusion-gate metric key in {f.name}: {item}")
            if isinstance(item, str) and item == "READY_FOR_KDA_VALIDATION":
                leak.append(f"READY_FOR_KDA emitted as a value in {f.name}")
    ok(len(leak) == 0, "no_ready_for_kda_no_fusion_gate_metric")

    # frozen abc.json unchanged
    abc = REPO / "experiments" / "phase_lc" / "results" / "abc.json"
    ok(hashlib.sha256(abc.read_bytes()).hexdigest()
       == "b31989a3135b150ef4cf693e42f173aadb51bba876b6e956da73f022d539b482", "abc_unchanged")

    # ---- results-dependent checks (only if evidence has been produced) ----
    res = HERE / "results"
    agg_p = res / "aggregate_conclusion.json"
    if agg_p.exists():
        agg = json.loads(agg_p.read_text())
        ok(agg["primary_verdict"] in ALLOWED_VERDICTS, "verdict_allowed")
        ok(agg["kda_readiness"] == "KDA_VALIDATION_BLOCKED", "kda_blocked_result")
        ok(agg["ready_for_kda_validation"] is False, "not_ready_for_kda")
        repro = json.loads((res / "reproduction_results.json").read_text())
        ok(all(r["passed"] for r in repro["runs"]) or
           agg["primary_verdict"] == "BINDINGSLOTS_INSTRUMENTED_REPRODUCTION_FAILED",
           "reproduction_gate_consistent")
        ok(all(r["no_extra_optimizer_steps"] for r in repro["runs"]), "no_extra_optimizer_steps")
        integ = json.loads((res / "integrity_report.json").read_text())
        ok(integ["checks"]["all_pass"], "integrity_all_pass")

    n = len(checks)
    fails = [name for name, good in checks if not good]
    if fails:
        print(f"BINDINGSLOTS_DIAGNOSTIC_INTEGRITY_FAILED: {len(fails)}/{n} failed -> {fails}")
        return 1
    print(f"value-path diagnosis integrity: {n} checks, 0 failures "
          f"-> BINDINGSLOTS_VALUE_PATH_DIAGNOSIS_VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
