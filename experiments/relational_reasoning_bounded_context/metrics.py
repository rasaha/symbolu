"""Frozen BTRR metrics + R9 decomposition + input-length instrumentation. Torch-free.

Operates on (context, gold, predicted_text) triples. Predictions are raw model output strings; a
non-conforming prediction is invalid structured output (counts against the validity metric and never as a
correct answer).
"""
from __future__ import annotations

from .output import parse_output
from .schema_ext import ReasoningContext, ReasoningOutput
from .serializer import input_token_count


def _visible_entity_ids(ctx): return {e.entity_id for e in ctx.entities}
def _visible_event_ids(ctx): return {e.event_id for e in ctx.events}
def _visible_evidence_ids(ctx): return {e.evidence_ref for e in ctx.evidence}
def _visible_relation_types(ctx): return {r.relation_type for r in ctx.relations}


def _nodes(prefix, path): return [p[len(prefix):] for p in path if p.startswith(prefix)]


def _safe_parse(text):
    try:
        return parse_output(text)
    except Exception:
        return None


def compute(cohort: list[tuple[ReasoningContext, str]]) -> dict:
    """cohort = list of (context, predicted_text). Gold is context.authoritative_output."""
    n = len(cohort)
    if n == 0:
        return {"n": 0}
    valid = ans = ent = path = latest = policy = 0
    ev_tp = ev_fp = ev_fn = 0
    abst_correct = abst_total = false_abst = answerable = 0
    hall_e = hall_r = hall_v = 0
    input_lengths = []
    r9 = {"n": 0, "wrong_entity": 0, "wrong_relation": 0, "wrong_temporal": 0,
          "wrong_policy": 0, "wrong_outcome": 0, "fabricated": 0, "invalid": 0, "abstain_wrong": 0}
    r9_full_chain = 0
    for ctx, text in cohort:
        g: ReasoningOutput = ctx.authoritative_output
        input_lengths.append(input_token_count(ctx))
        p = _safe_parse(text)
        is_answerable = g.status != "INSUFFICIENT_EVIDENCE"
        answerable += int(is_answerable)
        if not is_answerable:
            abst_total += 1
        if p is None:
            if ctx.split == "R9":
                r9["n"] += 1; r9["invalid"] += 1
            continue
        valid += 1
        # answer
        if p.answer == g.answer:
            ans += 1
        # abstention
        if not is_answerable and p.status == "INSUFFICIENT_EVIDENCE":
            abst_correct += 1
        if is_answerable and p.status == "INSUFFICIENT_EVIDENCE":
            false_abst += 1
        # entity selection (first entity node)
        ge, pe = _nodes("Entity:", g.reasoning_path), _nodes("Entity:", p.reasoning_path)
        if ge and pe and ge[0] == pe[0]:
            ent += 1
        # exact ordered path
        if tuple(p.reasoning_path) == tuple(g.reasoning_path):
            path += 1
        # latest event node
        gv, pv = _nodes("Event:", g.reasoning_path), _nodes("Event:", p.reasoning_path)
        if gv and pv and gv[-1] == pv[-1]:
            latest += 1
        # policy correctness (status + policy node)
        gp, pp = _nodes("Policy:", g.reasoning_path), _nodes("Policy:", p.reasoning_path)
        if p.status == g.status and gp == pp:
            policy += 1
        # evidence precision/recall
        gset, pset = set(g.evidence_ids), set(p.evidence_ids)
        ev_tp += len(gset & pset); ev_fp += len(pset - gset); ev_fn += len(gset - pset)
        # hallucination
        vids, veids, vevd = _visible_entity_ids(ctx), _visible_event_ids(ctx), _visible_evidence_ids(ctx)
        vrt = _visible_relation_types(ctx)
        if any(x not in vids for x in _nodes("Entity:", p.reasoning_path)):
            hall_e += 1
        if any(x not in vrt for x in _nodes("Relation:", p.reasoning_path)):
            hall_r += 1
        if any(x not in vevd for x in p.evidence_ids):
            hall_v += 1
        # R9 full-chain correctness = conjunction of the frozen components (no compensation):
        #   final answer AND exact ordered relation path AND correct latest event AND correct policy.
        if ctx.split == "R9":
            r9["n"] += 1
            answer_ok = p.answer == g.answer
            path_ok = _nodes("Relation:", p.reasoning_path) == _nodes("Relation:", g.reasoning_path) \
                and _nodes("Entity:", p.reasoning_path) == _nodes("Entity:", g.reasoning_path)
            temporal_ok = (not gv) or (pv and pv[-1] == gv[-1])
            policy_ok = p.status == g.status and pp == gp
            full_chain = bool(answer_ok and path_ok and temporal_ok and policy_ok
                              and tuple(p.reasoning_path) == tuple(g.reasoning_path))
            r9_full_chain += int(full_chain)
            correct = full_chain
            if not correct:
                if pe and ge and pe[0] != ge[0]:
                    r9["wrong_entity"] += 1
                elif _nodes("Relation:", p.reasoning_path) != _nodes("Relation:", g.reasoning_path):
                    r9["wrong_relation"] += 1
                elif pv and gv and pv[-1] != gv[-1]:
                    r9["wrong_temporal"] += 1
                elif pp != gp:
                    r9["wrong_policy"] += 1
                elif p.answer != g.answer:
                    r9["wrong_outcome"] += 1
                elif any(x not in vids for x in _nodes("Entity:", p.reasoning_path)):
                    r9["fabricated"] += 1
                elif p.status == "INSUFFICIENT_EVIDENCE":
                    r9["abstain_wrong"] += 1

    def rate(x): return x / n
    prec = ev_tp / (ev_tp + ev_fp) if (ev_tp + ev_fp) else 1.0
    rec = ev_tp / (ev_tp + ev_fn) if (ev_tp + ev_fn) else 1.0
    return {
        "n": n,
        "structured_output_validity": rate(valid),
        "final_answer_accuracy": rate(ans),
        "entity_selection": rate(ent),
        "relation_path_exact_ordered": rate(path),
        "latest_event": rate(latest),
        "policy_condition": rate(policy),
        "evidence_precision": prec,
        "evidence_recall": rec,
        "abstention_accuracy": (abst_correct / abst_total) if abst_total else 1.0,
        "false_abstention_on_answerable": (false_abst / answerable) if answerable else 0.0,
        "hallucinated_entity": rate(hall_e),
        "hallucinated_relation": rate(hall_r),
        "hallucinated_evidence": rate(hall_v),
        "r9_decomposition": r9,
        "r9_full_chain_correct": (r9_full_chain / r9["n"]) if r9["n"] else None,
        "input_length_min": min(input_lengths),
        "input_length_max": max(input_lengths),
        "input_length_mean": sum(input_lengths) / n,
    }
