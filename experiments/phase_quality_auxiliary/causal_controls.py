"""
causal_controls.py — Phase causal-dependence checks for A3 (and DHA serialization).

Phase adds real long-range value only if corrupting the RELEVANT distant evidence / the Phase
state degrades the relevant quality prediction, while removing IRRELEVANT evidence does not.
Controls: Phase zeroed / shuffled-across-examples / shuffled-across-time / sequence reversed;
plus data-level ablations that remove the relevant distant segment vs an irrelevant segment.
"""
from __future__ import annotations

import copy
import torch

from .dataset import Schema, deterministic_packet, NOTE
from .evaluate import evaluate, predict, auroc, metrics_for
from .train import collate


def _ablate(data, schema, which):
    """Return a copy of data with a segment neutralized to NOTE/background records.
    which='relevant' removes the distant relevant focus evidence; 'irrelevant' removes an equal
    number of non-relevant, out-of-packet positions."""
    out = []
    for ex in data:
        ex2 = copy.deepcopy(ex)
        pk = set(deterministic_packet(ex, schema))
        rel = [p for p in ex["relevant_positions"] if p not in pk and p != ex["query_pos"]]
        if which == "relevant":
            targets = rel
        else:
            cand = [i for i in range(ex["N"]) if i not in pk and i not in ex["relevant_positions"]
                    and i != ex["query_pos"]]
            targets = cand[:len(rel)]
        for p in targets:
            e = ex2["events"][p]
            e["subject_id"] = (ex["focus"] + 7) % schema.n_subjects    # different subject
            e["status"] = NOTE; e["object_id"] = 0; e["version"] = 1; e["tag"] = "ablated"
        out.append(ex2)
    return out


def phase_causal_controls(model, data, schema, device="cpu"):
    """Return macro-AUROC (and long-range-target AUROC) under each Phase/data corruption."""
    res = {}
    base = evaluate(model, data, schema, device, phase_mode="normal")
    res["normal"] = {"macro_auroc": base["macro_auroc"],
                     "persistence": base["persistence"]["auroc"],
                     "unresolved_recurrence": base["unresolved_recurrence"]["auroc"]}
    for mode in ("zero", "shuffle_batch", "shuffle_time", "reverse"):
        m = evaluate(model, data, schema, device, phase_mode=mode)
        res[f"phase_{mode}"] = {"macro_auroc": m["macro_auroc"],
                                "persistence": m["persistence"]["auroc"],
                                "unresolved_recurrence": m["unresolved_recurrence"]["auroc"]}
    rel = evaluate(model, _ablate(data, schema, "relevant"), schema, device)
    irr = evaluate(model, _ablate(data, schema, "irrelevant"), schema, device)
    res["remove_relevant_distant"] = {"macro_auroc": rel["macro_auroc"],
                                       "persistence": rel["persistence"]["auroc"],
                                       "unresolved_recurrence": rel["unresolved_recurrence"]["auroc"]}
    res["remove_irrelevant"] = {"macro_auroc": irr["macro_auroc"],
                                "persistence": irr["persistence"]["auroc"],
                                "unresolved_recurrence": irr["unresolved_recurrence"]["auroc"]}
    # causal dependence: relevant removal hurts the long-range targets more than irrelevant removal
    def lr(x): return (x["persistence"] + x["unresolved_recurrence"]) / 2
    res["causal_dependence_verified"] = bool(
        lr(res["remove_relevant_distant"]) < lr(res["normal"]) - 0.03 and
        lr(res["remove_irrelevant"]) > lr(res["remove_relevant_distant"]) and
        res["phase_zero"]["macro_auroc"] < res["normal"]["macro_auroc"] - 0.01)
    return res


def serialize_dha(model, ex, schema, device="cpu"):
    """DHA-compatible structured output. Phase scores auxiliary/non-authoritative; supporting
    evidence IDs come ONLY from deterministic/quadratic processing (never latent Phase state)."""
    cats, num, det, qp, pk, vl, _ = collate([ex], schema, device)
    with torch.no_grad():
        logits, extra = model(cats, num, det, qp, pk, vl)
    sc = {t: float(torch.sigmoid(logits[t])[0]) for t in logits}
    status = "healthy"
    if sc["sequence_anomaly"] >= 0.5 or sc["context_shift"] >= 0.5:
        status = "attention_required"
    if sc["unresolved_recurrence"] >= 0.5 or sc["persistence"] >= 0.5:
        status = "unresolved_active"
    sel = extra.get("selected_evidence_ids", [])
    if sel and isinstance(sel[0], list):
        sel = sel[0]
    conf = extra.get("phase_signal_confidence", None)
    return {"persistence_score": sc["persistence"],
            "unresolved_recurrence_score": sc["unresolved_recurrence"],
            "context_shift_score": sc["context_shift"],
            "sequence_anomaly_score": sc["sequence_anomaly"],
            "supporting_evidence_ids": sorted(set(int(i) for i in sel)),
            "quality_status": status,
            "phase_auxiliary_used": bool(extra.get("phase_auxiliary_used", False)),
            "phase_signal_confidence": (float(conf[0]) if conf is not None else None),
            "phase_authoritative": False}
