#!/usr/bin/env python3
"""Run the 4-arm Layer-2 ablation over a frozen corpus and emit deterministic metrics (JSON + report
tables). No model, no scoring vocabulary. See ablation.py for arm definitions."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_VL = _HERE.parent.parent
_REPO = _VL.parent
sys.path.insert(0, str(_HERE))
import ablation as AB  # noqa: E402

# Balanced corpus: the frozen Layer-2/3/4 inputs + multi-varṇa + mixed-pole + ś + ṣ + conjunct kṣ.
# Chosen for coverage of the required cases, NOT to favor any arm.
CORPUS = [
    ("love", "frozen L2/3/4 input"),
    ("mercy", "frozen L2/3/4 input"),
    ("anger", "frozen L2/3/4 input"),
    ("peace", "frozen L2/3/4 input"),
    ("compassion", "multi-varṇa (English)"),
    ("courage", "multi-varṇa (English)"),
    ("śānti", "contains ś (śa → artha)"),
    ("ṣaṭ", "contains ṣ (ṣa → kāma)"),
    ("kṣamā", "conjunct-normalized kṣ → k + ṣ"),
    ("dama", "Sanskrit, mixed poles"),
    ("kāla", "Sanskrit, mixed poles"),
    ("yoga", "Sanskrit, mixed poles"),
]

TEMPLATE_STOP = {"moves", "toward", "and", "is", "the", "resolving", "principle"}
FORBIDDEN = ["means", "proves", "reveals", "reveal", "decodes", "represents", "signifies", "hidden meaning"]
_TOK = re.compile(r"[a-zāīūṛṝḷṅñṭḍṇśṣ/]+", re.IGNORECASE)


def _content_tokens(text):
    return [t for t in _TOK.findall(text.lower()) if t not in TEMPLATE_STOP and t != "[unresolved]"
            and t != "unresolved"]


def _pole_source_concat(rendered):
    # concatenation of the raw B1.12 pole source texts (verbatim) — the fidelity reference.
    return " ".join(AB._t_direct(p["state"]) for p in rendered["poles"])


def coverage(rendered, arm):
    r = rendered["arms"][arm]
    poles = rendered["poles"]
    n = len(poles)
    if arm == "D_none":
        return {"poles_total": n, "poles_represented": 0, "unresolved": 0, "missing_key": 0,
                "coverage_pct": 0.0}
    texts = r["pole_texts"]
    unresolved = sum(1 for t in texts if t == AB.UNRESOLVED)
    represented = sum(1 for t in texts if t and t != AB.UNRESOLVED)
    return {"poles_total": n, "poles_represented": represented, "unresolved": unresolved,
            "missing_key": 0, "coverage_pct": round(100.0 * represented / n, 1) if n else 0.0}


def fidelity(rendered, arm):
    r = rendered["arms"][arm]
    if arm == "D_none" or not rendered["poles"]:
        return {"source_concepts_retained_pct": 0.0, "unsupported_introduced": 0,
                "binding_liberating_distinct": False, "order_preserved": True}
    src = set(_content_tokens(_pole_source_concat(rendered)))
    pay = _content_tokens(r["payload"])
    pay_set = set(pay)
    unsupported = sorted(pay_set - src)                       # tokens not in the B1.12 source
    # leading-concept retention: does each pole's payload text keep its source's first content token?
    retained = 0
    for p, ptext in zip(rendered["poles"], r["pole_texts"]):
        src_toks = _content_tokens(AB._t_direct(p["state"]))
        if src_toks and ptext != AB.UNRESOLVED and src_toks[0] in _content_tokens(ptext):
            retained += 1
    distinct = (len(r["pole_texts"]) >= 2 and r["pole_texts"][0] != r["pole_texts"][1]
                and r["pole_texts"][0] != AB.UNRESOLVED)
    return {"source_concepts_retained_pct": round(100.0 * retained / len(rendered["poles"]), 1),
            "unsupported_introduced": len(unsupported), "unsupported_terms": unsupported,
            "binding_liberating_distinct": bool(distinct), "order_preserved": True}


def honesty(rendered, arm):
    r = rendered["arms"][arm]
    text = r["payload"].lower()
    forbidden_hits = {w: text.count(w) for w in FORBIDDEN if w in text}
    # semantic additions = unsupported tokens (already computed in fidelity); recomputed here standalone
    add = fidelity(rendered, arm).get("unsupported_introduced", 0) if arm != "D_none" else 0
    return {"forbidden_decode_tokens": sum(forbidden_hits.values()), "forbidden_detail": forbidden_hits,
            "semantic_additions": add}


def tokens(rendered, arm):
    p = rendered["arms"][arm]["payload"]
    return {"chars": len(p), "est_tokens": (len(p) + 3) // 4}   # ~4 chars/token heuristic


def run():
    rows = [AB.render_all(w) for w, _ in CORPUS]
    per = {a: [] for a in AB.ARMS}
    payloads = {a: [] for a in AB.ARMS}
    for r in rows:
        for a in AB.ARMS:
            per[a].append({"word": r["word"], "coverage": coverage(r, a), "fidelity": fidelity(r, a),
                           "honesty": honesty(r, a), "tokens": tokens(r, a),
                           "payload": r["arms"][a]["payload"]})
            payloads[a].append(r["arms"][a]["payload"])

    def agg(a):
        c = [x["coverage"] for x in per[a]]
        f = [x["fidelity"] for x in per[a]]
        h = [x["honesty"] for x in per[a]]
        t = [x["tokens"] for x in per[a]]
        n = len(per[a])
        distinct = len(set(payloads[a]))
        return {
            "coverage_pct_mean": round(sum(x["coverage_pct"] for x in c) / n, 1),
            "unresolved_total": sum(x["unresolved"] for x in c),
            "fidelity_retained_pct_mean": round(sum(x["source_concepts_retained_pct"] for x in f) / n, 1),
            "unsupported_introduced_total": sum(x["unsupported_introduced"] for x in f),
            "binding_liberating_distinct_words": sum(1 for x in f if x["binding_liberating_distinct"]),
            "honesty_forbidden_tokens_total": sum(x["forbidden_decode_tokens"] for x in h),
            "semantic_additions_total": sum(x["semantic_additions"] for x in h),
            "distinct_payloads": distinct, "corpus_size": n,
            "differentiation_pct": round(100.0 * distinct / n, 1),
            "chars_mean": round(sum(x["chars"] for x in t) / n, 1),
            "est_tokens_mean": round(sum(x["est_tokens"] for x in t) / n, 1),
        }

    summary = {a: agg(a) for a in AB.ARMS}
    return {"corpus": [{"word": w, "note": note} for w, note in CORPUS], "per_arm": per,
            "summary": summary}


def markdown(result):
    S = result["summary"]
    L = ["# Layer-2 Bridge Ablation — Metrics (GENERATED, deterministic, no model)\n"]
    L.append(f"Corpus: {result['summary']['A_direct']['corpus_size']} words "
             "(frozen L2/3/4 inputs + multi-varṇa + ś + ṣ + conjunct kṣ + Sanskrit mixed poles).\n")
    cols = ["A_direct", "B_legacy", "C_compress", "D_none"]
    def row(label, key, fmt="{}"):
        return "| " + label + " | " + " | ".join(fmt.format(S[a][key]) for a in cols) + " |"
    L.append("| Metric | Arm A Direct | Arm B Legacy | Arm C Compression | Arm D None |")
    L.append("|---|---|---|---|---|")
    L.append(row("Coverage % (mean poles represented)", "coverage_pct_mean"))
    L.append(row("Unresolved poles (total)", "unresolved_total"))
    L.append(row("Fidelity: leading-concept retained % (mean)", "fidelity_retained_pct_mean"))
    L.append(row("Unsupported concepts introduced (total)", "unsupported_introduced_total"))
    L.append(row("Binding/liberating distinct (words)", "binding_liberating_distinct_words"))
    L.append(row("Honesty: decode-claim tokens (total)", "honesty_forbidden_tokens_total"))
    L.append(row("Semantic additions (total)", "semantic_additions_total"))
    L.append(row("Differentiation % (distinct payloads)", "differentiation_pct"))
    L.append(row("Payload chars (mean)", "chars_mean"))
    L.append(row("Est. tokens (mean)", "est_tokens_mean"))
    L.append("\n## Per-word payloads (illustrative)\n")
    for i, w in enumerate(result["corpus"]):
        L.append(f"**{w['word']}** — {w['note']}")
        for a in cols:
            p = result["per_arm"][a][i]["payload"] or "(no payload)"
            L.append(f"- `{a}`: {p}")
        L.append("")
    return "\n".join(L)


def main():
    result = run()
    (_HERE / "ablation_metrics.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (_HERE / "ABLATION_METRICS.md").write_text(markdown(result), encoding="utf-8")
    S = result["summary"]
    print("Layer-2 ablation metrics (mean over corpus):")
    for a in AB.ARMS:
        s = S[a]
        print(f"  {a:11} coverage={s['coverage_pct_mean']:5}%  fidelity={s['fidelity_retained_pct_mean']:5}%  "
              f"differentiation={s['differentiation_pct']:5}%  unsupported={s['unsupported_introduced_total']}  "
              f"tokens≈{s['est_tokens_mean']}")
    print(f"wrote {(_HERE / 'ablation_metrics.json').relative_to(_REPO)}")
    print(f"wrote {(_HERE / 'ABLATION_METRICS.md').relative_to(_REPO)}")


if __name__ == "__main__":
    main()
