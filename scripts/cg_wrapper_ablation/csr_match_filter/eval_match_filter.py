#!/usr/bin/env python3
"""eval_match_filter.py — held-out evaluation harness for the C×R×S MATCH-filter wrapper.

Measures whether the match-filter improves framing/rejection, whether derived domain templates are
reliable, and whether it generalizes to unknown terms without a curated per-word dictionary.

IMPORTANT — semantic-backend labeling. Every report states which backend produced S:
  real_embed_fn        -> production-valid
  offline_hashing_embed-> ARCHITECTURE-SMOKE only (weak deterministic stand-in)
  lexical_fallback     -> ARCHITECTURE-SMOKE only (exact-token overlap)
  demo_curated_fixture -> NOT production (demo/test fixtures)
Only real_embed_fn results are production evidence. If no real embed_fn is configured, the offline
eval still runs but is marked architecture-smoke.

Usage:
  python scripts/cg_wrapper_ablation/csr_match_filter/eval_match_filter.py            # hashing (smoke)
  ... --semantic-backend lexical | demo | real        ... --compare        ... --json out.json
Real backend: set CSR_EMBED_MODEL (sentence-transformers) — falls back to smoke if unavailable.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from csr_match_filter import (  # noqa: E402
    DOMAIN_TEMPLATES,
    CSRThresholds,
    SemanticCoherenceAdapter,
    build_trace,
    compute_12d_profile,
    derive_ontology_rule,
    dominant_terms,
    hashing_embed,
    make_demo_adapter,
)
from csr_match_filter.registry import DEMO_TERM_GLOSSES  # noqa: E402

_HERE = Path(__file__).resolve().parent
_EVAL = _HERE / "eval_data" / "domain_match_eval.jsonl"
_KB = _HERE / "eval_data" / "term_definitions.json"

BACKEND_LABEL = {
    "hashing": ("offline_hashing_embed", False, "ARCHITECTURE-SMOKE"),
    "lexical": ("lexical_fallback", False, "ARCHITECTURE-SMOKE"),
    "demo": ("demo_curated_fixture", False, "NOT-PRODUCTION (demo fixtures)"),
    "real": ("real_embed_fn", True, "production-valid"),
}


# --- data + definition source ---------------------------------------------------------------------

def load_eval(path=_EVAL):
    rows = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def load_kb(path=_KB):
    raw = json.loads(Path(path).read_text())
    return {k: v for k, v in raw.items() if not k.startswith("_")}


class ContextualDefinitionProvider:
    """External definition-source stand-in (EVAL FIXTURE). Picks a sense by the current context."""

    def __init__(self, kb):
        self.kb = kb
        self.context = None

    def __call__(self, term):
        e = self.kb.get(term.lower())
        if e is None:
            return None                      # -> raw-term fallback in the adapter
        if isinstance(e, str):
            return e
        if self.context and self.context in e:
            return e[self.context]
        return e.get("default") or next(iter(e.values()))


def load_real_embed_fn():
    """Build a real sentence embedder; return (fn, label) or (None, reason).

    Imports/loads the embedder with THIS script's injected sys.path entries removed — running
    eval_match_filter.py puts the csr_match_filter package dir on sys.path[0], which breaks
    sentence-transformers' dynamic module loading (an 'attempted relative import' error). Stripping
    those entries recreates the clean import environment, then we restore sys.path. Tries
    sentence-transformers, then a transformers mean-pooling fallback. CSR_EMBED_MODEL = hub id or path.
    """
    import os
    name = os.environ.get("CSR_EMBED_MODEL", "all-MiniLM-L6-v2")
    here = str(Path(__file__).resolve().parent)            # csr_match_filter/  (auto sys.path[0])
    parent = str(Path(__file__).resolve().parents[1])      # scripts/cg_wrapper_ablation (injected)
    saved = list(sys.path)
    sys.path[:] = [p for p in sys.path if p not in ("", here, parent)]
    errs = []
    try:
        # 1) sentence-transformers
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(name)
            return (lambda text: model.encode(text)), f"sentence_transformers:{name}"
        except Exception as exc:
            errs.append(f"sentence_transformers({name}): {type(exc).__name__}: {exc}")

        # 2) transformers AutoModel + mean pooling (try the name, then the sentence-transformers/ org)
        for cand in ([name] if "/" in name else [name, f"sentence-transformers/{name}"]):
            try:
                import torch
                from transformers import AutoModel, AutoTokenizer
                tok = AutoTokenizer.from_pretrained(cand)
                mdl = AutoModel.from_pretrained(cand); mdl.eval()

                def embed(text, _tok=tok, _mdl=mdl):
                    import torch as _t
                    with _t.no_grad():
                        enc = _tok(text, return_tensors="pt", truncation=True, max_length=128)
                        out = _mdl(**enc).last_hidden_state[0]            # [T, H]
                        mask = enc["attention_mask"][0].unsqueeze(-1).float()
                        return ((out * mask).sum(0) / mask.sum().clamp(min=1.0)).cpu().numpy()

                return embed, f"transformers:{cand}"
            except Exception as exc:
                errs.append(f"transformers({cand}): {type(exc).__name__}: {exc}")
        return None, "; ".join(errs)
    finally:
        sys.path[:] = saved


def make_adapter(backend, provider, audit):
    if backend == "hashing":
        return SemanticCoherenceAdapter(definition_provider=provider, offline_backend="hashing",
                                        audit=audit)
    if backend == "lexical":
        return SemanticCoherenceAdapter(definition_provider=provider, offline_backend="lexical",
                                        audit=audit)
    if backend == "demo":
        a = make_demo_adapter()
        a.audit = audit
        return a
    if backend == "real":
        fn, info = load_real_embed_fn()
        if fn is None:
            return None, info
        return SemanticCoherenceAdapter(definition_provider=provider, embed_fn=fn, audit=audit), info
    raise ValueError(backend)


# --- metric helpers -------------------------------------------------------------------------------

def _safe(num, den):
    return (num / den) if den else None


def _fmt(x):
    return "n/a" if x is None else f"{x:.3f}"


def _primary_correct(P, Sec, R, EP, ESec, ER):
    P, ER_, EP_, ESec_ = set(P), set(ER), set(EP), set(ESec)
    if not EP_:
        return None
    return EP_ <= P and not (P & ER_) and P <= (EP_ | ESec_)


def run_eval(rows, adapter, provider, thr=None):
    per = []
    rej_tp = rej_fp = rej_fn = 0
    sem_tot = sem_ok = ont_tot = ont_ok = ovr_tot = ovr_ok = 0
    trace_complete = 0
    ep_inst = ep_primary = ep_framed = ep_misrejected = 0   # where expected-primary domains land
    ep_ranks = []; ep_scores = []                            # rank/score distribution of EP domains
    ep_band = {"primary": 0, "secondary": 0, "weak": 0, "rejected": 0}
    ep_secondary_due_to_threshold = 0                        # MATCH in [0.30,0.60) -> secondary
    match_by_role = {"primary": [], "secondary": [], "rejected": [], "other": []}  # for calibration
    for ex in rows:
        provider.context = ex.get("context")
        cand = ex["candidate_domains"]
        trace = build_trace(ex["query"], ex["dominant_terms"], cand, adapter=adapter,
                            thr=thr or CSRThresholds())
        dec = {s.domain: s.decision for s in trace.scores}
        P, Sec, R = set(trace.primary_domains), set(trace.secondary_domains), set(trace.rejected_domains)
        EP, ESec, ER = ex["expected_primary"], ex["expected_secondary"], ex["expected_rejected"]

        pc = _primary_correct(P, Sec, R, EP, ESec, ER)
        ranked = sorted(trace.scores, key=lambda s: -s.match)
        order = {s.domain: i + 1 for i, s in enumerate(ranked)}
        mscore = {s.domain: s.match for s in trace.scores}
        for d in EP:                                  # pooled landing of each expected-primary domain
            ep_inst += 1
            ep_primary += int(d in P)
            ep_framed += int(d in P or d in Sec)
            ep_misrejected += int(d in R)
            ep_ranks.append(order.get(d)); ep_scores.append(mscore.get(d, 0.0))
            band = ("primary" if d in P else "secondary" if d in Sec
                    else "rejected" if d in R else "weak")
            ep_band[band] += 1
            if band == "secondary" and 0.30 <= mscore.get(d, 0.0) < 0.60:
                ep_secondary_due_to_threshold += 1
        for d in cand:                                # MATCH by expected role (for calibration)
            role = ("primary" if d in EP else "secondary" if d in ESec
                    else "rejected" if d in ER else "other")
            match_by_role[role].append(mscore.get(d, 0.0))
        srec = _safe(len(Sec & set(ESec)), len(ESec))
        rej_tp += len(R & set(ER)); rej_fp += len(R - set(ER)); rej_fn += len(set(ER) - R)
        for d in ex.get("semantic_invalid_domains", []):
            sem_tot += 1; sem_ok += int(dec.get(d) == "reject_semantic")
        for d in ex.get("ontological_invalid_domains", []):
            ont_tot += 1; ont_ok += int(dec.get(d) == "reject_ontological")
        for d in ex.get("phoneme_overreach_domains", []):
            ovr_tot += 1; ovr_ok += int(str(dec.get(d, "")).startswith("reject"))
        # trace completeness: a decision for every candidate domain, all fields present, JSON ok
        ok = all(d in dec for d in cand) and all(
            None not in (s.C, s.R, s.S, s.match) and s.decision for s in trace.scores)
        try:
            json.loads(trace.to_json()); ok = ok and True
        except Exception:
            ok = False
        trace_complete += int(ok)
        per.append({"id": ex["id"], "category": ex.get("category"), "primary_correct": pc,
                    "secondary_recall": srec, "produced": {"primary": sorted(P),
                    "secondary": sorted(Sec), "rejected": sorted(R)}, "decisions": dec,
                    "scores": {s.domain: (round(s.C, 3), round(s.R, 3), round(s.S, 3),
                                          round(s.match, 3)) for s in trace.scores}})

    def acc(key, subset=None):
        vals = [r[key] for r in per if r[key] is not None and (subset is None or subset(r))]
        return _safe(sum(bool(v) for v in vals), len(vals))

    unknown_ids = {ex["id"] for ex in rows
                   if ex["dominant_terms"] and all(t in ex.get("unknown_terms", [])
                                                   for t in ex["dominant_terms"])}
    ctx_ids = {ex["id"] for ex in rows if ex.get("category") == "context"}
    metrics = {
        "primary_frame_accuracy": acc("primary_correct"),
        "secondary_frame_recall": _safe(
            sum(r["secondary_recall"] for r in per if r["secondary_recall"] is not None),
            sum(1 for r in per if r["secondary_recall"] is not None)),
        "rejected_precision": _safe(rej_tp, rej_tp + rej_fp),
        "rejected_recall": _safe(rej_tp, rej_tp + rej_fn),
        "semantic_veto_accuracy": _safe(sem_ok, sem_tot),
        "ontological_veto_accuracy": _safe(ont_ok, ont_tot),
        "phoneme_overreach_prevention": _safe(ovr_ok, ovr_tot),
        "unknown_term_generalization": acc("primary_correct", lambda r: r["id"] in unknown_ids),
        "context_disambiguation": acc("primary_correct", lambda r: r["id"] in ctx_ids),
        "trace_completeness": _safe(trace_complete, len(rows)),
        # ranking-vs-threshold diagnostics (where expected-primary domains actually land)
        "expected_primary_as_primary": _safe(ep_primary, ep_inst),
        "expected_primary_framed": _safe(ep_framed, ep_inst),
        "expected_primary_misrejected": _safe(ep_misrejected, ep_inst),
    }
    import numpy as np
    ranks = [r for r in ep_ranks if r is not None]
    sc = np.asarray(ep_scores, float) if ep_scores else np.zeros(0)
    metrics["expected_primary_detail"] = {
        "n": ep_inst,
        "rank_distribution": {"rank1": ranks.count(1), "rank2": ranks.count(2),
                              "rank3plus": sum(1 for r in ranks if r >= 3)},
        "rank1_rate": _safe(ranks.count(1), len(ranks)),
        "match_score": {"mean": float(sc.mean()) if sc.size else None,
                        "median": float(np.median(sc)) if sc.size else None,
                        "min": float(sc.min()) if sc.size else None,
                        "max": float(sc.max()) if sc.size else None,
                        "lt_0.60": int((sc < 0.60).sum()), "lt_0.30": int((sc < 0.30).sum())},
        "landing": dict(ep_band),
        "secondary_due_to_threshold": ep_secondary_due_to_threshold,
    }
    metrics["match_by_role"] = match_by_role
    counts = {"n": len(rows), "n_unknown": len(unknown_ids), "n_context": len(ctx_ids),
              "n_semantic_veto": sem_tot, "n_ontological_veto": ont_tot, "n_overreach": ovr_tot}
    return metrics, counts, per


# --- audits ---------------------------------------------------------------------------------------

def backend_usage(audit, backend):
    total_def = sum(audit.get(k, 0) for k in
                    ("definition_external", "definition_demo_gloss", "definition_raw_term"))
    total_sim = sum(audit.get(k, 0) for k in
                    ("s_embed", "s_hashing", "s_lexical", "s_demo_curated"))
    return {
        "semantic_backend": BACKEND_LABEL[backend][0],
        "production_valid": BACKEND_LABEL[backend][1],
        "status": BACKEND_LABEL[backend][2],
        "embed_fn_used": audit.get("s_embed", 0) > 0,
        "offline_hashing_used": audit.get("s_hashing", 0) > 0,
        "lexical_used": audit.get("s_lexical", 0) > 0,
        "demo_fixture_used": audit.get("s_demo_curated", 0) > 0,
        "definition_provider_used": audit.get("definition_external", 0) > 0,
        "pct_external_definition": _safe(audit.get("definition_external", 0), total_def),
        "pct_raw_term_fallback": _safe(audit.get("definition_raw_term", 0), total_def),
        "pct_demo_gloss": _safe(audit.get("definition_demo_gloss", 0), total_def),
        "pct_scalable_S": _safe(audit.get("s_embed", 0) + audit.get("s_hashing", 0), total_sim),
        "pct_lexical_S": _safe(audit.get("s_lexical", 0), total_sim),
        "pct_demo_curated_S": _safe(audit.get("s_demo_curated", 0), total_sim),
        "raw_counts": dict(audit),
    }


def template_audit(domains):
    import numpy as np
    from csr_match_filter import domain_group_weights, realization_flat, realization_grouped
    tmpls = {d: np.asarray(DOMAIN_TEMPLATES[d].vector, float) for d in domains if d in DOMAIN_TEMPLATES}
    rows = []
    for d, v in tmpls.items():
        rule = derive_ontology_rule(d)
        # nearest neighbours under BOTH flat cosine and group-aware R (template d as a 'term')
        flat = sorted(((realization_flat(v, e), e) for e in tmpls if e != d), reverse=True)
        grp = sorted(((realization_grouped(v, e)[0], e) for e in tmpls if e != d), reverse=True)
        w = domain_group_weights(d)
        rows.append({
            "domain": d,
            "required_high": rule.required_high,
            "blocked_high": rule.blocked_high,
            "group_weights": {g: round(x, 2) for g, x in w.items() if x > 0.01},
            "too_strict_blocked": len(rule.blocked_high) >= 5,
            "too_flat": float(v.std()) < 0.12,
            "too_generic": float(v.mean()) > 0.72 and len(rule.required_high) >= 6,
            "nearest_flat": [(e, round(s, 3)) for s, e in flat[:2]],
            "nearest_grouped": [(e, round(s, 3)) for s, e in grp[:2]],
            "confusable_flat": [e for s, e in flat if s > 0.97],
            "confusable_grouped": [e for s, e in grp if s > 0.90],
        })
    return rows


def calibrate_thresholds(match_by_role):
    """Suggest F1-optimal primary/secondary cutoffs for THIS MATCH distribution. Reporting only —
    does NOT change the live 0.60/0.30 defaults. primary: expected-primary vs the rest;
    secondary(framed): expected-primary+secondary vs expected-rejected."""
    import numpy as np
    mbr = match_by_role

    def best_t(pos, neg):
        if not pos:
            return None, None
        grid = sorted({round(x, 3) for x in (pos + neg)} | {0.0})
        best_f1, best_t_ = -1.0, 0.0
        for t in grid:
            tp = sum(1 for x in pos if x >= t); fp = sum(1 for x in neg if x >= t)
            fn = sum(1 for x in pos if x < t)
            f1 = tp / (tp + 0.5 * (fp + fn)) if (tp + fp + fn) else 0.0
            if f1 > best_f1:
                best_f1, best_t_ = f1, t
        return round(best_t_, 3), round(best_f1, 3)

    pos_p, neg_p = mbr["primary"], mbr["secondary"] + mbr["rejected"] + mbr["other"]
    # secondary: keep 'other' as negatives too, so the cutoff doesn't sweep unlabeled domains in
    pos_s, neg_s = mbr["primary"] + mbr["secondary"], mbr["rejected"] + mbr["other"]
    pt, pf1 = best_t(pos_p, neg_p)
    st, sf1 = best_t(pos_s, neg_s)

    def _f1_at(t, pos, neg):
        tp = sum(1 for x in pos if x >= t); fp = sum(1 for x in neg if x >= t)
        fn = sum(1 for x in pos if x < t)
        return round(tp / (tp + 0.5 * (fp + fn)), 3) if (tp + fp + fn) else None

    # held-out check: fit the primary cutoff on even-indexed scores, score odd-indexed (and swap)
    def holdout(pos, neg):
        pe, po = pos[::2], pos[1::2]; ne, no = neg[::2], neg[1::2]
        ta, _ = best_t(pe, ne); tb, _ = best_t(po, no)
        return {"fit_A_test_B": {"t": ta, "f1": _f1_at(ta, po, no) if ta is not None else None},
                "fit_B_test_A": {"t": tb, "f1": _f1_at(tb, pe, ne) if tb is not None else None}}

    def stats(xs):
        a = np.asarray(xs, float)
        return {"n": len(xs), "mean": round(float(a.mean()), 3) if a.size else None,
                "median": round(float(np.median(a)), 3) if a.size else None,
                "p90": round(float(np.percentile(a, 90)), 3) if a.size else None}
    return {"by_role_match": {k: stats(v) for k, v in mbr.items()},
            "suggested_primary_threshold": pt, "primary_f1_at_suggested": pf1,
            "suggested_secondary_threshold": st, "secondary_f1_at_suggested": sf1,
            "primary_holdout": holdout(pos_p, neg_p),
            "current_defaults": {"primary": 0.60, "secondary": 0.30}}


def print_calibration(res):
    c = calibrate_thresholds(res["metrics"]["match_by_role"])
    print("=" * 72)
    print(f"THRESHOLD CALIBRATION ({res['usage']['semantic_backend']}) — reporting only, defaults UNCHANGED")
    for role in ("primary", "secondary", "rejected", "other"):
        s = c["by_role_match"][role]
        print(f"  expected-{role:<10} MATCH: n={s['n']:>3} mean={s['mean']} median={s['median']} "
              f"p90={s['p90']}")
    print(f"  suggested primary threshold   = {c['suggested_primary_threshold']} "
          f"(F1={c['primary_f1_at_suggested']})   [current default 0.60]")
    print(f"  suggested secondary threshold = {c['suggested_secondary_threshold']} "
          f"(F1={c['secondary_f1_at_suggested']})   [current default 0.30]")
    ho = c["primary_holdout"]
    print(f"  held-out primary cutoff: fit-A/test-B t={ho['fit_A_test_B']['t']} "
          f"F1={ho['fit_A_test_B']['f1']}   fit-B/test-A t={ho['fit_B_test_A']['t']} "
          f"F1={ho['fit_B_test_A']['f1']}  (stable => generalises)")
    print("  NOTE: suggestions only — adopt via CSRThresholds; verify with --primary-threshold/"
          "--secondary-threshold before changing defaults.")


def explain_failures(rows, per):
    """List the cases that miss expectation, with C/R/S, to localise veto/framing errors."""
    byid = {ex["id"]: ex for ex in rows}
    out = {"ontological_not_rejected": [], "semantic_not_rejected": [],
           "expected_primary_misframed": [], "context_wrong": []}
    for p in per:
        ex = byid[p["id"]]; dec = p["decisions"]; sc = p["scores"]
        P = set(p["produced"]["primary"])
        for d in ex.get("ontological_invalid_domains", []):
            if dec.get(d) != "reject_ontological":
                out["ontological_not_rejected"].append((p["id"], d, dec.get(d), sc.get(d)))
        for d in ex.get("semantic_invalid_domains", []):
            if dec.get(d) != "reject_semantic":
                out["semantic_not_rejected"].append((p["id"], d, dec.get(d), sc.get(d)))
        for d in ex["expected_primary"]:
            if d not in P:
                out["expected_primary_misframed"].append((p["id"], d, dec.get(d), sc.get(d)))
        if ex.get("category") == "context" and not (set(ex["expected_primary"]) <= P):
            out["context_wrong"].append((p["id"], ex.get("context"), ex["expected_primary"],
                                         p["produced"]["primary"]))
    return out


def print_failures(res):
    f = explain_failures(load_eval(), res["per"])
    print("=" * 72)
    print(f"FAILURE EXPLAINER ({res['usage']['semantic_backend']})  [domain: (C, R, S, MATCH)]")
    for k in ("ontological_not_rejected", "semantic_not_rejected", "expected_primary_misframed"):
        rows = f[k]
        print(f"  {k} (n={len(rows)}):")
        for r in rows:
            print(f"    {r[0]:7} {r[1]:<11} decision={r[2]:<18} CRS={r[3]}")
    print(f"  context_wrong (n={len(f['context_wrong'])}):")
    for r in f["context_wrong"]:
        print(f"    {r[0]:7} ctx={r[1]} expected={r[2]} got_primary={r[3]}")


def resonance_confusability(domains):
    """Off-diagonal R between domain templates under flat vs group-aware R (lower = more separable)."""
    import numpy as np
    from csr_match_filter import realization_flat, realization_grouped
    doms = [d for d in domains if d in DOMAIN_TEMPLATES]
    flat, grp = [], []
    for a in doms:
        va = DOMAIN_TEMPLATES[a].vector
        for b in doms:
            if a != b:
                flat.append(realization_flat(va, b)); grp.append(realization_grouped(va, b)[0])
    f, g = np.asarray(flat), np.asarray(grp)
    return {"flat": {"mean": float(f.mean()), "max": float(f.max()), "std": float(f.std())},
            "grouped": {"mean": float(g.mean()), "max": float(g.max()), "std": float(g.std())}}


def mean_primary_S(rows, adapter, provider):
    """Average S on (dominant term, expected-primary domain) pairs — for backend comparison."""
    vals = []
    for ex in rows:
        provider.context = ex.get("context")
        for t in ex["dominant_terms"]:
            for d in ex["expected_primary"]:
                if d in DOMAIN_TEMPLATES:
                    vals.append(adapter.similarity(t, d))
    return sum(vals) / len(vals) if vals else None


# --- reporting ------------------------------------------------------------------------------------

def run_one(backend, rows, kb, thr=None):
    provider = ContextualDefinitionProvider(kb)
    audit = {}
    made = make_adapter(backend, provider, audit)
    if isinstance(made, tuple):
        adapter, info = made
        if adapter is None:
            return None, info
    else:
        adapter, info = made, None
    metrics, counts, per = run_eval(rows, adapter, provider, thr)
    usage = backend_usage(audit, backend)
    return {"backend": backend, "info": info, "metrics": metrics, "counts": counts,
            "usage": usage, "per": per, "mean_primary_S": mean_primary_S(rows, adapter, provider)}, info


def print_report(res):
    u, m, c = res["usage"], res["metrics"], res["counts"]
    print("=" * 72)
    print(f"SEMANTIC BACKEND: {u['semantic_backend']}   [{u['status']}]"
          f"   production_valid={u['production_valid']}")
    if res.get("info"):
        print(f"  backend info: {res['info']}")
    print(f"  n={c['n']}  unknown-term cases={c['n_unknown']}  context cases={c['n_context']}")
    print("-" * 72)
    print("METRICS")
    for k in ("primary_frame_accuracy", "secondary_frame_recall", "rejected_precision",
              "rejected_recall", "semantic_veto_accuracy", "ontological_veto_accuracy",
              "phoneme_overreach_prevention", "unknown_term_generalization",
              "context_disambiguation", "trace_completeness"):
        print(f"  {k:<32} {_fmt(m[k])}")
    print("  -- ranking vs threshold (where expected-primary domains land) --")
    for k in ("expected_primary_as_primary", "expected_primary_framed", "expected_primary_misrejected"):
        print(f"  {k:<32} {_fmt(m[k])}")
    epd = m["expected_primary_detail"]
    print(f"  rank distribution (n={epd['n']}): rank1={epd['rank_distribution']['rank1']} "
          f"rank2={epd['rank_distribution']['rank2']} rank3+={epd['rank_distribution']['rank3plus']} "
          f"(rank1_rate={_fmt(epd['rank1_rate'])})")
    ms = epd["match_score"]
    print(f"  MATCH score: mean={_fmt(ms['mean'])} median={_fmt(ms['median'])} "
          f"min={_fmt(ms['min'])} max={_fmt(ms['max'])}  (<0.60: {ms['lt_0.60']}  <0.30: {ms['lt_0.30']})")
    print(f"  landing: {epd['landing']}   secondary-because-MATCH<0.60 = "
          f"{epd['secondary_due_to_threshold']}")
    print("-" * 72)
    print("SEMANTIC-BACKEND AUDIT")
    print(f"  embed_fn_used={u['embed_fn_used']}  offline_hashing_used={u['offline_hashing_used']}  "
          f"lexical_used={u['lexical_used']}  demo_fixture_used={u['demo_fixture_used']}")
    print(f"  definition_provider_used={u['definition_provider_used']}")
    print(f"  pct_external_definition={_fmt(u['pct_external_definition'])}  "
          f"pct_raw_term_fallback={_fmt(u['pct_raw_term_fallback'])}  "
          f"pct_demo_gloss={_fmt(u['pct_demo_gloss'])}")
    print(f"  pct_scalable_S={_fmt(u['pct_scalable_S'])}  pct_lexical_S={_fmt(u['pct_lexical_S'])}  "
          f"pct_demo_curated_S={_fmt(u['pct_demo_curated_S'])}")
    print(f"  mean S on expected-primary pairs = {_fmt(res['mean_primary_S'])}")
    if not u["production_valid"]:
        print("  NOTE: results are ARCHITECTURE-SMOKE, not production evidence.")


def print_template_audit(domains):
    doms = sorted(set(domains))
    print("=" * 72)
    print("TEMPLATE-QUALITY AUDIT (R: flat 12D cosine  vs  group-aware)")
    conf = resonance_confusability(doms)
    print(f"  off-diagonal R confusability (lower=more separable):")
    print(f"    flat   : mean={conf['flat']['mean']:.3f} max={conf['flat']['max']:.3f} "
          f"std={conf['flat']['std']:.3f}")
    print(f"    grouped: mean={conf['grouped']['mean']:.3f} max={conf['grouped']['max']:.3f} "
          f"std={conf['grouped']['std']:.3f}")
    for r in template_audit(doms):
        flags = [f for f, on in (("too_strict_blocked", r["too_strict_blocked"]),
                                 ("too_flat", r["too_flat"]), ("too_generic", r["too_generic"])) if on]
        print(f"  {r['domain']:<12} weights={r['group_weights']}")
        print(f"               blocked={r['blocked_high']}  nearest(flat)={r['nearest_flat']}  "
              f"nearest(grouped)={r['nearest_grouped']}  flags={flags or '-'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(_EVAL))
    ap.add_argument("--kb", default=str(_KB))
    ap.add_argument("--semantic-backend", default="hashing",
                    choices=["hashing", "lexical", "demo", "real"])
    ap.add_argument("--compare", action="store_true", help="run all available backends and compare")
    ap.add_argument("--template-audit", action="store_true")
    ap.add_argument("--calibrate", action="store_true",
                    help="report F1-optimal primary/secondary cutoffs for the MATCH distribution "
                         "(analysis only; does not change the 0.60/0.30 defaults)")
    ap.add_argument("--explain-failures", action="store_true",
                    help="list cases that miss expectation (ontological/semantic veto, primary "
                         "framing, context) with their C/R/S — for tuning the S-gate")
    ap.add_argument("--primary-threshold", type=float, default=None,
                    help="WHAT-IF: evaluate at this primary MATCH cutoff (defaults unchanged in code)")
    ap.add_argument("--secondary-threshold", type=float, default=None,
                    help="WHAT-IF: evaluate at this secondary MATCH cutoff")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    rows = load_eval(args.data)
    kb = load_kb(args.kb)
    all_domains = sorted({d for ex in rows for d in ex["candidate_domains"]})

    thr = None
    if args.primary_threshold is not None or args.secondary_threshold is not None:
        thr = CSRThresholds(primary_match=args.primary_threshold if args.primary_threshold is not None
                            else 0.60,
                            secondary_match=args.secondary_threshold if args.secondary_threshold
                            is not None else 0.30)
        print(f"[what-if] evaluating at primary={thr.primary_match} secondary={thr.secondary_match} "
              f"(code defaults unchanged)")

    backends = ["hashing", "lexical", "demo", "real"] if args.compare else [args.semantic_backend]
    results = {}
    for b in backends:
        res, info = run_one(b, rows, kb, thr)
        if res is None:
            print(f"[skip] backend '{b}' unavailable: {info}")
            continue
        results[b] = res
        print_report(res)
        if args.calibrate:
            print_calibration(res)
        if args.explain_failures:
            print_failures(res)

    if args.compare and "hashing" in results and "lexical" in results:
        sh = results["hashing"]["mean_primary_S"]; sl = results["lexical"]["mean_primary_S"]
        print("=" * 72)
        print("COMPARISON — mean S on expected-primary pairs")
        print(f"  hashing(embedding-style)={_fmt(sh)}  lexical={_fmt(sl)}  "
              f"lift={_fmt((sh - sl) if (sh is not None and sl is not None) else None)}")
        print("  primary_frame_accuracy:  " + "  ".join(
            f"{b}={_fmt(results[b]['metrics']['primary_frame_accuracy'])}" for b in results))

    if args.template_audit or args.compare:
        print_template_audit(all_domains)

    if args.json:
        Path(args.json).write_text(json.dumps(
            {b: {k: v for k, v in r.items() if k != "per"} for b, r in results.items()}, indent=2))
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
