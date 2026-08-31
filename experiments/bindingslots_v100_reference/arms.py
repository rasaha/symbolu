#!/usr/bin/env python3
"""Arms M0 / T0 / F0 / V100 over the frozen needle-eval cohort, backed by the SQLite reference table.

The model is used for INFERENCE ONLY (no optimizer step, no weight change). Per-example neural
predictions + routing signals come from the merged fallback phase's deterministic ``extract``. Each arm
gets its own freshly populated table so read counts are cleanly attributable:

  * M0    — frozen BindingSlots only; zero table reads.
  * T0    — one table read per query; abstain when no valid record.
  * F0    — the EXACT frozen PR #1346 confidence trigger (no recalibration); reads only when it fires.
  * V100  — always verify: exactly one table read per query; agree -> verified_agreement,
            disagree -> verified_correction (return the table value), else fail-closed abstain.
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
FALLBACK = REPO / "experiments" / "bindingslots_external_fallback"
VPD = REPO / "experiments" / "bindingslots_value_path_diagnosis"
for p in (str(HERE), str(FALLBACK), str(VPD)):
    if p not in sys.path:
        sys.path.insert(0, p)

import v100 as V100                                   # noqa: E402
from v100_table import V100Table, TableUnavailable    # noqa: E402

FROZEN_CALIB_HASH_PREFIX = "7421fbfb"


def load_frozen_trigger():
    """Load the EXACT frozen trigger + thresholds from the merged PR #1346 evidence. No recalibration."""
    import fallback as FB
    d = json.loads((FALLBACK / "results" / "trigger_thresholds.json").read_text())
    assert d["calibration_hash"].startswith(FROZEN_CALIB_HASH_PREFIX), "F0 must reuse frozen #1346 calibration"
    thr = d["thresholds"]
    return FB.Trigger(thr["prob_min"], thr["margin_min"], thr["entropy_max"]), d


def _episode(session_prefix, idx):
    import fallback as FB
    return FB._episode_session(session_prefix, idx)


def _build_table(examples, session_prefix, tenant_id, scope, ttl_s):
    import fallback as FB
    t = V100Table()
    FB.populate_table(t, examples, session_prefix, tenant_id=tenant_id, ttl_s=ttl_s, scope=scope)
    return t


def run_seed(model, vocab, T, seed, tenant_id="t0", scope="eval", ttl_s=3600):
    """Run all four arms for one reproduced seed. Returns a fully mechanical per-seed record."""
    import fallback as FB
    examples = FB.extract(model, vocab, T)
    n = len(examples)
    trigger, _ = load_frozen_trigger()

    # ---- M0: frozen neural only ----------------------------------------------------------
    m0_correct = sum(int(e["model_correct"]) for e in examples)

    # ---- T0: table-only ceiling ----------------------------------------------------------
    tbl_t0 = _build_table(examples, f"eval{seed}_t0", tenant_id, scope, ttl_s)
    r0 = tbl_t0.ops["reads"]
    t0_correct = 0
    t0_abstain = 0
    for e in examples:
        rd = tbl_t0.read_for_verification(session_id=_episode(f"eval{seed}_t0", e["idx"]),
                                          tenant_id=tenant_id, memory_key=e["entity_id"],
                                          authorization_scope=scope)
        if rd["status"] == "ok" and str(rd["typed_value"]) == str(e["target"]):
            t0_correct += 1
        else:
            t0_abstain += 1
    t0_reads = tbl_t0.ops["reads"] - r0

    # ---- F0: frozen confidence trigger (comparator only) ---------------------------------
    tbl_f0 = _build_table(examples, f"eval{seed}_f0", tenant_id, scope, ttl_s)
    rf = tbl_f0.ops["reads"]
    f0 = {"correct": 0, "fallback_invoked": 0, "rescued": 0, "unnecessary": 0,
          "incorrect_fallback": 0, "abstain": 0, "provenance_complete": 0}
    conf = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    for e in examples:
        m0_ok = bool(e["model_correct"])
        actual_fail = not m0_ok
        fired = trigger.fires(e["signals"])
        if fired and actual_fail:
            conf["tp"] += 1
        elif fired and not actual_fail:
            conf["fp"] += 1
        elif (not fired) and actual_fail:
            conf["fn"] += 1
        else:
            conf["tn"] += 1
        if not fired:
            f0_ok = m0_ok
        else:
            f0["fallback_invoked"] += 1
            rd = tbl_f0.read_for_verification(session_id=_episode(f"eval{seed}_f0", e["idx"]),
                                              tenant_id=tenant_id, memory_key=e["entity_id"],
                                              authorization_scope=scope)
            if rd["status"] == "ok":
                f0_ok = (str(rd["typed_value"]) == str(e["target"]))
                if V100.provenance_complete(rd["provenance"]):
                    f0["provenance_complete"] += 1
                if actual_fail and f0_ok:
                    f0["rescued"] += 1
                if not actual_fail:
                    f0["unnecessary"] += 1
            else:
                f0_ok = m0_ok           # fail-closed: no fabricated answer
                f0["abstain"] += 1
            if not f0_ok:
                f0["incorrect_fallback"] += 1
        f0["correct"] += int(f0_ok)
    f0_reads = tbl_f0.ops["reads"] - rf

    # ---- V100: always verify -------------------------------------------------------------
    tbl_v = _build_table(examples, f"eval{seed}_v100", tenant_id, scope, ttl_s)
    rv = tbl_v.ops["reads"]
    cats = {c: 0 for c in V100.CATEGORIES}
    v = {"returned": 0, "returned_correct": 0, "verified_correct": 0, "incorrect_verified": 0,
         "disagreements": 0, "corrections": 0, "incorrect_corrections": 0, "abstain": 0,
         "provenance_complete": 0}
    for e in examples:
        try:
            rd = tbl_v.read_for_verification(session_id=_episode(f"eval{seed}_v100", e["idx"]),
                                             tenant_id=tenant_id, memory_key=e["entity_id"],
                                             authorization_scope=scope)
        except TableUnavailable:
            rd = None
        if rd is None:
            dec = V100._abstain("abstained_table_unavailable", e["model_pred"], reason="table_unavailable")
        else:
            dec = V100.classify(neural_pred=e["model_pred"], target=e["target"], read=rd)
        cats[dec["category"]] += 1
        if dec["verified"]:
            v["returned"] += 1
            if str(dec["answer"]) == str(e["target"]):
                v["returned_correct"] += 1
                v["verified_correct"] += 1
            else:
                v["incorrect_verified"] += 1
            if V100.provenance_complete(dec["provenance"]):
                v["provenance_complete"] += 1
            if dec["disagreement"]:
                v["disagreements"] += 1
                v["corrections"] += 1
                if str(dec["answer"]) != str(e["target"]):
                    v["incorrect_corrections"] += 1
        else:
            v["abstain"] += 1
    v_reads = tbl_v.ops["reads"] - rv

    rec = {
        "seed": seed, "n": n,
        "M0": {"correct": m0_correct, "accuracy": m0_correct / n, "reads": 0},
        "T0": {"correct": t0_correct, "accuracy": t0_correct / n, "abstain": t0_abstain, "reads": t0_reads},
        "F0": {**f0, "accuracy": f0["correct"] / n, "confusion": conf, "reads": f0_reads,
               "frozen_thresholds": trigger.as_dict()},
        "V100": {**v, "categories": cats,
                 "accuracy": v["returned_correct"] / n,
                 "answer_availability": v["returned"] / n,
                 "abstention_rate": v["abstain"] / n,
                 "reads": v_reads,
                 "reads_equal_n": (v_reads == n)},
        "table_ops": {"t0": dict(tbl_t0.ops), "f0": dict(tbl_f0.ops), "v100": dict(tbl_v.ops)},
        "peak_table_bytes_v100": tbl_v.peak_size_bytes(),
    }
    for t in (tbl_t0, tbl_f0, tbl_v):
        t.close()
    return rec
