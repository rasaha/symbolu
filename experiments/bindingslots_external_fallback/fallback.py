#!/usr/bin/env python3
"""Fallback trigger + hybrid arms (M0 / T0 / F1 / V0) over the frozen needle eval, backed by the
external ephemeral table. The model is used for inference ONLY (no training, no optimizer step, no
weight change). The trigger decides BEFORE any table read; F1 consults the table only when it fires.
"""
from __future__ import annotations

import math
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
VPD = REPO / "experiments" / "bindingslots_value_path_diagnosis"
for p in (str(HERE), str(VPD)):
    if p not in sys.path:
        sys.path.insert(0, p)

EVAL_SEED, EVAL_N, EVAL_DIST = 123, 120, 96


# ------------------------------------------------------------------ frozen trigger
class Trigger:
    """Deterministic fallback trigger from runtime-visible model routing signals ONLY.
    fallback = low_top1_prob OR low_top1_margin OR high_entropy. (key-verification is not available
    for this task without oracle info, so it is not used — recorded in the preregistration.)"""
    def __init__(self, prob_min, margin_min, entropy_max):
        self.prob_min = prob_min
        self.margin_min = margin_min
        self.entropy_max = entropy_max

    def fires(self, sig):
        return bool(sig["top1_prob"] < self.prob_min
                    or sig["margin"] < self.margin_min
                    or sig["entropy"] > self.entropy_max)

    def as_dict(self):
        return {"prob_min": self.prob_min, "margin_min": self.margin_min, "entropy_max": self.entropy_max,
                "formula": "low_top1_prob OR low_top1_margin OR high_entropy"}


# ------------------------------------------------------------------ per-example signals + facts
def eval_examples(vocab, T):
    import diagnosis_lib as DL
    X, fp, qp, tgt = DL.needle_examples(vocab, T, EVAL_SEED, EVAL_N, EVAL_DIST)
    return X, fp, qp, tgt


def extract(model, vocab, T, bs=60):
    """Per-example: entity_id (lookup key, from the query), target value token, model prediction, and
    the read-distribution signals (top1 prob / margin / entropy) aggregated over slot layers."""
    import torch
    import diagnosis_lib as DL
    X, fp, qp, tgt = eval_examples(vocab, T)
    out = []
    for i in range(0, len(X), bs):
        xb, fb, qb, tb = X[i:i + bs], fp[i:i + bs], qp[i:i + bs], tgt[i:i + bs]
        with DL.instrumented_model(model, mode=None, capture=True, fact_pos=fb, query_pos=qb) as slots:
            with torch.no_grad():
                lo = model(xb)
            j = torch.arange(len(xb))
            pred = lo[j, qb].argmax(-1)
            L = len(slots)
            r_top1 = torch.zeros(len(xb)); r_marg = torch.zeros(len(xb)); r_ent = torch.zeros(len(xb))
            for sm in slots:
                rq = sm._cap["raddr_query"]
                top2 = rq.topk(2, dim=-1).values
                r_top1 += top2[:, 0]
                r_marg += (top2[:, 0] - top2[:, 1])
                r_ent += -(rq * (rq + 1e-9).log()).sum(-1)
            r_top1 /= L; r_marg /= L; r_ent /= L
        for k in range(len(xb)):
            entity_id = int(xb[k, fb[k] - 2])     # ENT token in [the,code,for,ENT,is,VAL,.]
            out.append({"idx": i + k, "entity_id": str(entity_id), "target": int(tb[k]),
                        "model_pred": int(pred[k]), "model_correct": int(pred[k]) == int(tb[k]),
                        "signals": {"top1_prob": float(r_top1[k]), "margin": float(r_marg[k]),
                                    "entropy": float(r_ent[k])}})
    return out


# ------------------------------------------------------------------ populate table at write time
def _episode_session(session_id, idx):
    """Each needle example is an INDEPENDENT retrieval episode -> its own session, so an entity that
    recurs across examples is never conflated (entity_id -> value is unique within an episode)."""
    return f"{session_id}_ex{idx}"


def populate_table(table, examples, session_id, tenant_id="t0", ttl_s=3600, scope="eval"):
    """Write the EXPLICIT observed facts (entity_id -> value) — the same info written to slots — into
    each episode's own session."""
    for e in examples:
        table.write_fact(session_id=_episode_session(session_id, e["idx"]), tenant_id=tenant_id,
                         memory_key=e["entity_id"], fact_or_entity_id=e["entity_id"], typed_value=str(e["target"]),
                         value_type="value_token_id", source_event_id=f"write_{e['idx']}",
                         evidence_reference=f"needle_fact_{e['idx']}", authorization_scope=scope, ttl_s=ttl_s)


# ------------------------------------------------------------------ arms
def run_arms(model, vocab, T, table, trigger, session_id, tenant_id="t0", scope="eval",
             table_available=True):
    examples = extract(model, vocab, T)
    populate_table(table, examples, session_id, tenant_id=tenant_id, scope=scope)
    table.set_available(table_available)
    m0 = {"correct": 0, "n": len(examples)}
    t0 = {"correct": 0, "n": len(examples)}
    f1 = {"correct": 0, "n": len(examples), "fallback_invoked": 0, "rescued": 0, "unnecessary": 0,
          "false_negative": 0, "provenance_complete": 0, "table_unavailable": 0, "abstain": 0,
          "incorrect_fallback": 0}
    v0 = {"agree": 0, "disagree": 0, "n": len(examples)}
    conf = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}   # trigger fires (positive) vs model_incorrect (actual)
    read_lat, write_lat = [], []
    for e in examples:
        m0_ok = e["model_correct"]
        m0["correct"] += m0_ok
        # T0: table read every time
        from ephemeral_table import TableUnavailable
        try:
            r = table.lookup(session_id=_episode_session(session_id, e["idx"]), tenant_id=tenant_id, memory_key=e["entity_id"], authorization_scope=scope)
            t0_ok = r.found and r.typed_value == str(e["target"])
        except TableUnavailable:
            t0_ok = False
        t0["correct"] += int(t0_ok)
        # F1: trigger then maybe table
        fired = trigger.fires(e["signals"])
        # confusion vs actual model failure
        actual_fail = (not m0_ok)
        if fired and actual_fail: conf["tp"] += 1
        elif fired and not actual_fail: conf["fp"] += 1
        elif (not fired) and actual_fail: conf["fn"] += 1
        else: conf["tn"] += 1
        if not fired:
            f1_ok = m0_ok
        else:
            f1["fallback_invoked"] += 1
            t = time.perf_counter()
            try:
                r = table.lookup(session_id=_episode_session(session_id, e["idx"]), tenant_id=tenant_id, memory_key=e["entity_id"], authorization_scope=scope)
                read_lat.append(time.perf_counter() - t)
                if r.found:
                    f1_ok = (r.typed_value == str(e["target"]))
                    if r.provenance:
                        f1["provenance_complete"] += 1
                    if actual_fail and f1_ok:
                        f1["rescued"] += 1
                    if not actual_fail:
                        f1["unnecessary"] += 1
                else:
                    f1_ok = m0_ok
                    f1["abstain"] += 1
                if not f1_ok:
                    f1["incorrect_fallback"] += 1
            except TableUnavailable:
                f1["table_unavailable"] += 1
                f1_ok = m0_ok      # structured: keep model signal, do NOT fabricate; recorded as unavailable
                f1["abstain"] += 1
        f1["correct"] += int(f1_ok)
        # V0 always-verify
        try:
            rv = table.lookup(session_id=_episode_session(session_id, e["idx"]), tenant_id=tenant_id, memory_key=e["entity_id"], authorization_scope=scope)
            tv = rv.typed_value if rv.found else None
        except TableUnavailable:
            tv = None
        agree = (str(e["model_pred"]) == (tv if tv is not None else str(e["model_pred"]))) if not fired else None
        if tv is not None:
            if str(e["target"]) == tv and e["model_correct"]:
                v0["agree"] += 1
            else:
                v0["disagree"] += 1
    f1["false_negative"] = conf["fn"]
    return {"session_id": session_id, "n": len(examples), "M0": m0, "T0": t0, "F1": f1, "V0": v0,
            "confusion": conf, "trigger": trigger.as_dict(),
            "table_ops": dict(table.ops), "peak_table_bytes": table.peak_size_bytes(),
            "read_latency_samples": read_lat}
