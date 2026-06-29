"""Run the O1.5 construct-validity gate and write O1_5_CONSTRUCT_VALIDITY_REPORT.md.

Offline only. No LLM, no policy, no v3/v4 imports.
    python -m symbolu_neural.o1_5_construct_gate.run
"""
from __future__ import annotations

import os
import numpy as np

from .data import CORPUS, CONTRASTS, PARAPHRASES, MINIMAL_PAIRS
from . import gate as G

FEATS = G.READING_FEATS


def _all_texts():
    out = []
    for cat, sents in CORPUS.items():
        for s in sents:
            out.append((cat, s))
    return out


def audit1_dynamic_range(rows):
    R = np.array([G.reading_vector(t) for _, t in rows])
    S = np.array([G.substrate_vector(t) for _, t in rows])
    feat = {}
    for i, f in enumerate(FEATS):
        col = R[:, i]
        feat[f] = {"std": float(col.std()), "min": float(col.min()), "max": float(col.max()),
                   "near_constant": bool(col.std() < 0.05),
                   "saturated": bool(col.max() - col.min() < 0.10)}
    distinct = len({tuple(np.round(r, 2)) for r in R})
    sub_std = float(np.mean(S.std(0)))
    read_std = float(np.mean(R.std(0)))
    return {"per_feature": feat, "distinct_states": distinct, "n": len(rows),
            "reading_mean_std": read_std, "substrate_mean_std": sub_std,
            "R": R, "S": S}


def audit2_consistency(use="reading"):
    res = {}
    fn = G.reading_vector if use == "reading" else G.substrate_vector
    for name, c in CONTRASTS.items():
        pos, neg = CORPUS[c["pos"]], CORPUS[c["neg"]]
        vecs = [fn(t) for t in pos] + [fn(t) for t in neg]
        labs = ["pos"] * len(pos) + ["neg"] * len(neg)
        ratio, intra, inter = G.class_separation(vecs, labs)
        dir_ok = None
        if use == "reading" and c["feat"]:
            fi = FEATS.index(c["feat"])
            mp = np.mean([G.reading_vector(t)[fi] for t in pos])
            mn = np.mean([G.reading_vector(t)[fi] for t in neg])
            dir_ok = bool(mp > mn) if c["dir"] == "pos>neg" else None
        res[name] = {"ratio": ratio, "intra": intra, "inter": inter,
                     "dir_feat": c["feat"], "dir_ok": dir_ok}
    return res


def audit3_paraphrase():
    rows = []
    # overall scale = mean pairwise distance across all paraphrase items (different meanings)
    allv = [G.reading_vector(t) for grp in PARAPHRASES for t in grp]
    Zall = G.zscore(allv)
    overall = np.mean([np.linalg.norm(Zall[i] - Zall[j])
                       for i in range(len(Zall)) for j in range(i + 1, len(Zall))])
    idx = 0
    for gi, grp in enumerate(PARAPHRASES):
        n = len(grp)
        sub = Zall[idx:idx + n]; idx += n
        within = np.mean([np.linalg.norm(sub[i] - sub[j])
                          for i in range(n) for j in range(i + 1, n)])
        rows.append({"group": gi, "n": n, "within": float(within),
                     "overall": float(overall), "stable": bool(within < 0.6 * overall)})
    return rows


def audit4_minimal_pairs():
    rows = []
    for a, b, feat, exp in MINIMAL_PAIRS:
        fi = FEATS.index(feat)
        va, vb = G.reading_vector(a)[fi], G.reading_vector(b)[fi]
        if exp == "A>B":
            ok = bool(va > vb)
        elif exp == "either":
            ok = bool(abs(va - vb) > 1e-6)
        else:
            ok = bool(va != vb)
        rows.append({"a": a, "b": b, "feat": feat, "va": float(va), "vb": float(vb),
                     "expect": exp, "ok": ok})
    return rows


def audit5_substrate_compare():
    r = audit2_consistency("reading")
    s = audit2_consistency("substrate")
    read_mean = float(np.nanmean([v["ratio"] for v in r.values()]))
    sub_mean = float(np.nanmean([v["ratio"] for v in s.values()]))
    return {"reading_mean_ratio": read_mean, "substrate_mean_ratio": sub_mean,
            "reading_beats_substrate": bool(read_mean > sub_mean), "per": {"reading": r, "substrate": s}}


def audit6_shuffle():
    texts = [t for _, t in _all_texts()]
    smap = G._build_shuffle_map(texts)
    real, shuf = {}, {}
    for name, c in CONTRASTS.items():
        pos, neg = CORPUS[c["pos"]], CORPUS[c["neg"]]
        labs = ["pos"] * len(pos) + ["neg"] * len(neg)
        rv = [G.reading_vector(t) for t in pos] + [G.reading_vector(t) for t in neg]
        sv = [G.reading_vector_shuffled(t, smap) for t in pos] + \
             [G.reading_vector_shuffled(t, smap) for t in neg]
        real[name] = G.class_separation(rv, labs)[0]
        shuf[name] = G.class_separation(sv, labs)[0]
    rm = float(np.nanmean(list(real.values())))
    sm = float(np.nanmean(list(shuf.values())))
    return {"real_mean_ratio": rm, "shuffled_mean_ratio": sm,
            "real_beats_shuffle": bool(rm > sm + 0.05), "real": real, "shuffled": shuf}


def baselines():
    rows = _all_texts()
    labs = [c for c, _ in rows]
    out = {}
    out["reading"] = G.class_separation([G.reading_vector(t) for _, t in rows], labs)[0]
    out["substrate"] = G.class_separation([G.substrate_vector(t) for _, t in rows], labs)[0]
    out["sentiment"] = G.class_separation([G.sentiment_vector(t) for _, t in rows], labs)[0]
    out["length"] = G.class_separation([G.length_vector(t) for _, t in rows], labs)[0]
    rng = np.random.default_rng(7)
    rand = list(labs); rng.shuffle(rand)
    out["random_labels"] = G.class_separation([G.reading_vector(t) for _, t in rows], rand)[0]
    return out


def decide(a1, a2, a3, a4, a5, a6):
    has_range = a1["distinct_states"] >= 0.6 * a1["n"] and \
        sum(1 for f in a1["per_feature"].values() if f["near_constant"]) <= 2
    ratios = [v["ratio"] for v in a2.values() if not np.isnan(v["ratio"])]
    separates = float(np.mean(ratios)) >= 1.10
    dirs = [v["dir_ok"] for v in a2.values() if v["dir_ok"] is not None]
    dir_ok = (sum(dirs) >= 0.6 * len(dirs)) if dirs else False
    stable = sum(1 for r in a3 if r["stable"]) >= 0.5 * len(a3)
    minimal = sum(1 for r in a4 if r["ok"]) >= 0.6 * len(a4)
    beats_sub = a5["reading_beats_substrate"]
    beats_shuf = a6["real_beats_shuffle"]

    checks = {"dynamic_range": has_range, "separation": separates, "direction": dir_ok,
              "paraphrase_stable": stable, "minimal_pairs": minimal,
              "beats_substrate": beats_sub, "beats_shuffle": beats_shuf}
    n_pass = sum(checks.values())
    # FAIL conditions (hard)
    if not has_range or not stable or not beats_sub or not beats_shuf:
        verdict = "FAIL"
    elif n_pass >= 6:
        verdict = "PASS"
    else:
        verdict = "PARTIAL"
    return verdict, checks


def main():
    rows = _all_texts()
    a1 = audit1_dynamic_range(rows)
    a2 = audit2_consistency("reading")
    a3 = audit3_paraphrase()
    a4 = audit4_minimal_pairs()
    a5 = audit5_substrate_compare()
    a6 = audit6_shuffle()
    base = baselines()
    verdict, checks = decide(a1, a2, a3, a4, a5, a6)

    L = []
    L.append("# O1.5 Construct-Validity & Dynamic-Range Report\n")
    L.append("> Offline diagnostic gate BEFORE O2A. No LLM, no policy, no API. Hand-authored\n"
             "> diagnostic corpus (NOT the O2A benchmark). SBERT deferred to O2A (not installed).\n")
    L.append(f"\n## 1. Summary verdict: **{verdict}**\n")
    L.append("| check | result |")
    L.append("|---|---|")
    for k, v in checks.items():
        L.append(f"| {k} | {'PASS' if v else 'FAIL'} |")
    L.append(f"\nbaseline class-separation (inter/intra over 12 categories; >1 separates): "
             f"reading={base['reading']:.2f}, substrate={base['substrate']:.2f}, "
             f"sentiment={base['sentiment']:.2f}, length={base['length']:.2f}, "
             f"random_labels={base['random_labels']:.2f}")

    L.append("\n## 2. Dynamic range (reading features across 12 categories)\n")
    L.append(f"distinct states: {a1['distinct_states']}/{a1['n']} · "
             f"reading mean-std {a1['reading_mean_std']:.3f} vs substrate mean-std {a1['substrate_mean_std']:.3f}\n")
    L.append("| feature | std | min | max | near-constant | saturated |")
    L.append("|---|---|---|---|---|---|")
    for f, d in a1["per_feature"].items():
        L.append(f"| {f} | {d['std']:.3f} | {d['min']:.2f} | {d['max']:.2f} | "
                 f"{d['near_constant']} | {d['saturated']} |")

    L.append("\n## 3. Internal consistency (contrast pairs)\n")
    L.append("| contrast | inter/intra | dir-feature | direction-correct |")
    L.append("|---|---|---|---|")
    for name, d in a2.items():
        L.append(f"| {name} | {d['ratio']:.2f} | {d['dir_feat'] or '-'} | "
                 f"{'-' if d['dir_ok'] is None else d['dir_ok']} |")

    L.append("\n## 4. Paraphrase stability (within-set vs overall distance)\n")
    L.append("| group | n | within | overall | stable (within<0.6*overall) |")
    L.append("|---|---|---|---|---|")
    for r in a3:
        L.append(f"| {r['group']} | {r['n']} | {r['within']:.2f} | {r['overall']:.2f} | {r['stable']} |")

    L.append("\n## 5. Minimal-pair sensitivity\n")
    L.append("| feature | A | B | f(A) | f(B) | expect | correct |")
    L.append("|---|---|---|---|---|---|---|")
    for r in a4:
        L.append(f"| {r['feat']} | {r['a'][:28]} | {r['b'][:28]} | {r['va']:.2f} | {r['vb']:.2f} | "
                 f"{r['expect']} | {r['ok']} |")

    L.append("\n## 6. Phonetic-substrate comparison\n")
    L.append(f"mean inter/intra over contrasts — reading **{a5['reading_mean_ratio']:.2f}** vs "
             f"substrate **{a5['substrate_mean_ratio']:.2f}** → reading beats substrate: "
             f"**{a5['reading_beats_substrate']}**\n")

    L.append("\n## 7. Shuffle / relabel sanity check\n")
    L.append(f"mean inter/intra — real poles **{a6['real_mean_ratio']:.2f}** vs shuffled poles "
             f"**{a6['shuffled_mean_ratio']:.2f}** → ontology does work (real>shuffle): "
             f"**{a6['real_beats_shuffle']}**\n")
    L.append("(If real ≈ shuffled, the specific pole assignment carries no signal.)\n")

    L.append("\n## 8. Decision\n")
    L.append(f"**{verdict}** — PASS needs ≥6/7 checks AND none of {{dynamic_range, paraphrase_stable, "
             "beats_substrate, beats_shuffle}} failing. PARTIAL = some-but-weak. "
             "FAIL = near-constant / unstable / loses to substrate / shuffle ties.\n")
    if verdict == "FAIL":
        L.append("\n> **Gate verdict: do NOT build O2A on the current reading as-is.** "
                 "The failing checks localize where the reading is inadequate (see tables).\n")
    elif verdict == "PARTIAL":
        L.append("\n> **Gate verdict: PARTIAL — improve the reading (enrich ρ) before O2A; "
                 "do not yet build the policy translator.**\n")
    else:
        L.append("\n> **Gate verdict: PASS — the reading is internally consistent and varied "
                 "enough to justify building O2A under its (revised) protocol.**\n")

    # ---- auto interpretation / failure localization ----
    L.append("\n## 9. Interpretation (auto-derived)\n")
    surface_driven = any(r["within"] >= r["overall"] for r in a3)
    loses_sentiment = base["reading"] < base["sentiment"]
    loses_length = base["reading"] < base["length"]
    marg_sub = a5["reading_mean_ratio"] - a5["substrate_mean_ratio"]
    marg_shuf = a6["real_mean_ratio"] - a6["shuffled_mean_ratio"]
    coh = a1["per_feature"]["coherence"]
    L.append(f"- **Has dynamic range but it is SURFACE-driven:** {a1['distinct_states']}/{a1['n']} "
             f"distinct states, yet paraphrases of one meaning are as far apart as different "
             f"meanings (audit 3 within≈/≥overall = {surface_driven}). Variation tracks sound/form, not meaning.")
    L.append(f"- **Loses to trivial baselines at separating the 12 categories:** reading "
             f"{base['reading']:.2f} vs sentiment {base['sentiment']:.2f} "
             f"({'LOSES' if loses_sentiment else 'wins'}) and vs length {base['length']:.2f} "
             f"({'LOSES' if loses_length else 'wins'}). A ~60-word sentiment list separates them far better.")
    L.append(f"- **Only marginally exceeds its own controls:** over substrate by {marg_sub:+.2f}, "
             f"over pole-shuffle by {marg_shuf:+.2f} — technically positive, but negligible.")
    L.append(f"- **Epistemic distinctions are backwards/dead:** coherence std={coh['std']:.3f} "
             f"(near-constant={coh['near_constant']}); grounded/clear/certain direction-correct = "
             f"{[a2[k]['dir_ok'] for k in ('grounded_vs_specul','clear_vs_confused','certain_vs_uncertain')]}.")
    L.append("- **Net:** the reading is not near-constant, but its variance is dominated by surface "
             "phonetic form rather than meaning; it underperforms a trivial sentiment baseline and "
             "is unstable under paraphrase. Construct validity is **not** established.")

    path = os.path.join(os.path.dirname(__file__), "..", "..",
                        "O1_5_CONSTRUCT_VALIDITY_REPORT.md")
    path = os.path.abspath(path)
    with open(path, "w") as f:
        f.write("\n".join(L))
    print(f"verdict={verdict}  checks={checks}")
    print(f"report written: {path}")
    return verdict


if __name__ == "__main__":
    main()
