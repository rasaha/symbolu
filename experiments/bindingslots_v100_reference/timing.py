#!/usr/bin/env python3
"""End-to-end + component timing harness (characterization only; values are non-deterministic).

Timing boundaries are FROZEN in the preregistration and enforced here:

  * Query-path (V100): start immediately before frozen neural inference; stop only after neural
    inference, table lookup, comparison, classification, correction/abstention decision, provenance
    construction, and final response-object serialization.
  * Table-only (T0):   start before the table lookup; stop after lookup, validation, provenance
    construction, and response serialization.
  * Component timings:  neural inference, table lookup, comparison, provenance construction,
    serialization, and total M0 / T0 / V100 paths — measured separately.
  * Write-path:         write-event receipt, validation, serialization, commit, provenance attach —
    measured separately from query latency.
  * Lifecycle:          expiration handling, deletion, cleanup, explicit teardown.

The isolated ~0.006 ms table-read figure from PR #1346 must NOT substitute for these end-to-end
numbers — every path here includes serialization and (for V100) neural inference.
"""
from __future__ import annotations

import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
FALLBACK = REPO / "experiments" / "bindingslots_external_fallback"
VPD = REPO / "experiments" / "bindingslots_value_path_diagnosis"
for p in (str(HERE), str(FALLBACK), str(VPD)):
    if p not in sys.path:
        sys.path.insert(0, p)

import v100 as V100                         # noqa: E402
from v100_table import V100Table            # noqa: E402


def _dist(samples):
    if not samples:
        return {"p50": None, "p95": None, "p99": None, "mean": None, "max": None, "n": 0}
    xs = sorted(samples)
    q = lambda p: xs[min(len(xs) - 1, int(p * (len(xs) - 1)))]
    return {"p50": q(0.50), "p95": q(0.95), "p99": q(0.99),
            "mean": sum(xs) / len(xs), "max": xs[-1], "n": len(xs)}


def measure_seed(model, vocab, T, seed, tenant_id="t0", scope="eval"):
    """Measure query-path / component / table-only / write-path / lifecycle latencies for one seed.
    Returns wall-clock seconds distributions. Deterministic in structure, not in numeric value."""
    import torch
    import fallback as FB
    import diagnosis_lib as DL
    X, fp, qp, tgt = FB.eval_examples(vocab, T)
    n = len(X)

    # ---- write-path timing (fresh table) -------------------------------------------------
    tbl = V100Table()
    write_lat = []
    examples = FB.extract(model, vocab, T)   # deterministic predictions/entities
    for e in examples:
        sess = FB._episode_session(f"time{seed}", e["idx"])
        t0 = time.perf_counter()
        tbl.write_fact(session_id=sess, tenant_id=tenant_id, memory_key=e["entity_id"],
                       fact_or_entity_id=e["entity_id"], typed_value=str(e["target"]),
                       value_type="value_token_id", source_event_id=f"w_{e['idx']}",
                       evidence_reference=f"needle_{e['idx']}", authorization_scope=scope, ttl_s=3600)
        write_lat.append(time.perf_counter() - t0)

    # ---- query-path (V100 end-to-end) + components + M0 + T0 -----------------------------
    v100_path, t0_path, m0_path = [], [], []
    c_neural, c_lookup, c_compare, c_prov, c_serialize = [], [], [], [], []
    for k in range(n):
        xb = X[k:k + 1]
        sess = FB._episode_session(f"time{seed}", examples[k]["idx"])
        # --- V100 end-to-end: neural -> lookup -> compare -> classify -> serialize ---
        s = time.perf_counter()
        with torch.no_grad():
            lo = model(xb)
        pred = int(lo[0, int(qp[k])].argmax(-1))
        t_neural = time.perf_counter() - s
        s2 = time.perf_counter()
        rd = tbl.read_for_verification(session_id=sess, tenant_id=tenant_id,
                                       memory_key=examples[k]["entity_id"], authorization_scope=scope)
        t_lookup = time.perf_counter() - s2
        s3 = time.perf_counter()
        disagree = (str(pred) != str(rd.get("typed_value")))   # comparison
        t_compare = time.perf_counter() - s3
        s4 = time.perf_counter()
        dec = V100.classify(neural_pred=pred, target=examples[k]["target"], read=rd)  # provenance decision
        t_prov = time.perf_counter() - s4
        s5 = time.perf_counter()
        _ = V100.serialize(dec)
        t_serialize = time.perf_counter() - s5
        v100_path.append(t_neural + t_lookup + t_compare + t_prov + t_serialize)
        c_neural.append(t_neural); c_lookup.append(t_lookup); c_compare.append(t_compare)
        c_prov.append(t_prov); c_serialize.append(t_serialize)
        m0_path.append(t_neural + t_serialize)
        # --- T0 end-to-end: lookup -> validate -> provenance -> serialize (no neural) ---
        s6 = time.perf_counter()
        rd2 = tbl.read_for_verification(session_id=sess, tenant_id=tenant_id,
                                        memory_key=examples[k]["entity_id"], authorization_scope=scope)
        dec2 = V100.classify(neural_pred=rd2.get("typed_value"), target=examples[k]["target"], read=rd2)
        _ = V100.serialize(dec2)
        t0_path.append(time.perf_counter() - s6)

    # ---- lifecycle timings ---------------------------------------------------------------
    lc = {}
    s = time.perf_counter()
    tbl.delete(session_id=FB._episode_session(f"time{seed}", examples[0]["idx"]),
               tenant_id=tenant_id, memory_key=examples[0]["entity_id"])
    lc["deletion_s"] = time.perf_counter() - s
    s = time.perf_counter()
    ct = tbl.cleanup_session(FB._episode_session(f"time{seed}", examples[0]["idx"]))
    lc["cleanup_session_s"] = ct
    s = time.perf_counter()
    tbl.close()
    lc["teardown_s"] = time.perf_counter() - s

    return {
        "seed": seed, "n": n,
        "query_path_v100_s": _dist(v100_path),
        "table_only_t0_s": _dist(t0_path),
        "m0_path_s": _dist(m0_path),
        "component_s": {"neural_inference": _dist(c_neural), "table_lookup": _dist(c_lookup),
                        "comparison": _dist(c_compare), "provenance_construction": _dist(c_prov),
                        "serialization": _dist(c_serialize)},
        "write_path_s": _dist(write_lat),
        "lifecycle_s": lc,
    }
