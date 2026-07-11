#!/usr/bin/env python3
"""B1.10 — Gate G0 word-set distinctness audit (deterministic; representational; NO judges, NO network*).

Executes the frozen mechanical selection rule in `B1_10_WORD_SPECIFICITY_PREREG.md` (Rev 3, commit 658a6475).
Purely representational: derives each candidate's varṇa sequence + Tier-3 facet sets from the FROZEN active
mapping (`varna_bridge_active`) and the FROZEN facet map (`build_b1_10_control_ext.VARNA_PLAIN`), computes the
pre-registered overlap metrics, and applies the pre-registered rule EXACTLY. It never inspects whether a packet
is semantically correct for its word.

*No network/model call. Semantic similarity is SUPPLEMENTARY (not in the frozen selection/tie-break rule);
it is left pending and labelled, per the prereg — it is not required for selection, so its absence does not
block G0 (no `G0_BLOCKED_MISSING_SEMANTIC_SIM_SPEC`).

Frozen rule: k=6; max pairwise facet-set Jaccard ≤ 0.34; mean pairwise facet-set Jaccard ≤ 0.20; ≥1 unique
discriminating facet per word (target ≥2 where achievable — soft, reported not selected-on); valid binding AND
liberating packets; no target-word leakage; no semantic-correctness judgement; no post-hoc relaxation.
Selection = minimize max pairwise facet-Jaccard; tie-break (a) min mean facet-Jaccard, (b) min mean lexical-
Jaccard, (c) alphabetical.

Note (bijection): within a pole each varṇa maps to a distinct facet clause, so a word's facet SET is in
bijection with its (deduped) varṇa SET. Hence facet-set Jaccard(binding) == facet-set Jaccard(liberating) ==
varṇa-set Jaccard for every pair; the audit asserts this and uses it as the pre-registered facet-set Jaccard.

Guardrails: resonance / phonetic-fidelity refinement only. No GENUTILITY_*; no ONTOLOGICAL_SIGNAL; no
semantic-truth / ontology / Sanskrit-privilege / generation-utility claim; no individual-varṇa attribution.
B1.4b' NULL_RETURN_BOTTOM; original B1.4b blocked; Track B blocked. Structure, not validated meaning.
"""
import hashlib
import itertools
import json
import pathlib
import re

import varna_bridge_active as AB
import build_b1_10_control_ext as BLD
from b1_10_packet_aware_echo_audit import STOPWORDS  # fixed stopword list (frozen, offline)

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "b1_10_g0_audit"

# ---- frozen candidate pool (prereg §8 G0.1; assembled for phonetic breadth, sorted for order-independence) ----
CANDIDATE_POOL = sorted({
    "pride", "freedom", "patience", "courage", "control", "doubt", "anger", "greed", "envy", "fear", "hope",
    "joy", "grief", "love", "calm", "trust", "shame", "desire", "peace", "faith", "humility", "gratitude",
    "contentment", "compassion", "discipline", "focus", "clarity", "confusion", "attachment", "detachment",
    "ambition", "restlessness", "craving", "aversion", "equanimity", "boredom", "wonder",
})

# ---- frozen selection rule constants ----
K = 6
MAX_FACET_JACCARD_CAP = 0.34
MEAN_FACET_JACCARD_CAP = 0.20
POLES = ("binding", "liberating")
COVERED = {v for (v, _p) in BLD.VARNA_PLAIN}   # 11 varṇas with a facet render


def dedup(seq):
    seen, out = set(), []
    for v in seq:
        if v not in seen:
            seen.add(v); out.append(v)
    return out


def _tok(text):
    toks = re.sub(r"[^a-z]+", " ", text.lower()).split()
    return {t for t in toks if t not in STOPWORDS and len(t) > 2}


def jaccard(a, b):
    a, b = set(a), set(b)
    return (len(a & b) / len(a | b)) if (a | b) else 0.0


def candidate_record(w):
    seq = dedup(AB.word_to_varnas(w))
    missing = [v for v in seq if v not in COVERED]
    valid = (len(seq) > 0) and (not missing)
    facets = {p: ([BLD.VARNA_PLAIN[(v, p)] for v in seq] if valid else None) for p in POLES}
    # packet word/char length per pole (concatenated render)
    lengths = {}
    for p in POLES:
        if facets[p] is not None:
            render = " ".join(facets[p])
            lengths[p] = {"n_facets": len(facets[p]), "n_words": len(render.split()), "n_chars": len(render)}
        else:
            lengths[p] = None
    # target-word leakage (MECHANICAL only: literal word token, word-boundary, both poles) — never semantic
    leak = False
    if valid:
        wl = w.lower()
        for p in POLES:
            for clause in facets[p]:
                if re.search(r"(?<![\w-])" + re.escape(wl) + r"(?![\w-])", clause.lower()):
                    leak = True
    return {"word": w, "varna_sequence": seq, "facet_count": len(seq),
            "missing_varnas": missing, "valid_both_poles": valid, "leakage": leak,
            "packet_lengths": lengths,
            "binding_facets": facets["binding"], "liberating_facets": facets["liberating"]}


def pair_metrics(ra, rb):
    """Pairwise metrics for two valid candidate records; per pole + combined facet-set Jaccard."""
    va, vb = set(ra["varna_sequence"]), set(rb["varna_sequence"])
    out = {"shared_varnas": sorted(va & vb), "shared_varna_count": len(va & vb),
           "unique_varna_count": len(va ^ vb)}
    facet_jac = {}
    lex_jac = {}
    for p in POLES:
        fa, fb = set(ra[f"{p}_facets"]), set(rb[f"{p}_facets"])
        facet_jac[p] = jaccard(fa, fb)
        out[f"{p}_shared_facet_count"] = len(fa & fb)
        out[f"{p}_unique_facet_count"] = len(fa ^ fb)
        lex_jac[p] = jaccard(_tok(" ".join(ra[f"{p}_facets"])), _tok(" ".join(rb[f"{p}_facets"])))
    # bijection check: facet-set Jaccard equals varṇa-set Jaccard and is pole-invariant
    vj = jaccard(va, vb)
    assert abs(facet_jac["binding"] - vj) < 1e-12 and abs(facet_jac["liberating"] - vj) < 1e-12, \
        f"bijection broken for {ra['word']}/{rb['word']}"
    out["facet_jaccard_binding"] = round(facet_jac["binding"], 6)
    out["facet_jaccard_liberating"] = round(facet_jac["liberating"], 6)
    out["facet_jaccard"] = round(vj, 6)                       # pre-registered facet-set Jaccard (pole-invariant)
    out["lexical_jaccard_binding"] = round(lex_jac["binding"], 6)
    out["lexical_jaccard_liberating"] = round(lex_jac["liberating"], 6)
    out["lexical_jaccard_mean"] = round((lex_jac["binding"] + lex_jac["liberating"]) / 2, 6)
    out["combined_overlap_score"] = out["facet_jaccard"]     # prereg: facet-set Jaccard IS the overlap for caps/selection
    return out


def unique_facet_counts(subset_words, recs):
    """Per-word count of varṇas unique WITHIN the subset (a facet no other subset member has)."""
    sets = {w: set(recs[w]["varna_sequence"]) for w in subset_words}
    counts = {}
    for w in subset_words:
        others = set().union(*[sets[o] for o in subset_words if o != w])
        counts[w] = len(sets[w] - others)
    return counts


def evaluate_subset(subset, recs, pair_j, pair_lex):
    ws = sorted(subset)
    pairs = list(itertools.combinations(ws, 2))
    fj = [pair_j[(a, b)] for a, b in pairs]
    lx = [pair_lex[(a, b)] for a, b in pairs]
    uf = unique_facet_counts(ws, recs)
    max_fj = max(fj); mean_fj = sum(fj) / len(fj)
    eligible = (max_fj <= MAX_FACET_JACCARD_CAP) and (mean_fj <= MEAN_FACET_JACCARD_CAP) \
        and all(uf[w] >= 1 for w in ws)
    return {"words": ws, "max_facet_jaccard": round(max_fj, 6), "mean_facet_jaccard": round(mean_fj, 6),
            "mean_lexical_jaccard": round(sum(lx) / len(lx), 6), "unique_facet_counts": uf,
            "n_words_with_ge2_unique": sum(1 for w in ws if uf[w] >= 2), "eligible": eligible}


def run_audit():
    OUT.mkdir(parents=True, exist_ok=True)
    recs = {w: candidate_record(w) for w in CANDIDATE_POOL}

    # eligible candidates for selection: valid both poles + no leakage
    valid_words = sorted(w for w in CANDIDATE_POOL if recs[w]["valid_both_poles"] and not recs[w]["leakage"])

    # pairwise matrices over valid words
    pairwise = {"binding": {}, "liberating": {}, "combined": {}}
    pair_j, pair_lex = {}, {}
    for a, b in itertools.combinations(valid_words, 2):
        m = pair_metrics(recs[a], recs[b])
        key = f"{a}|{b}"
        pairwise["binding"][key] = {k: m[k] for k in ("shared_varnas", "binding_shared_facet_count",
                                                      "binding_unique_facet_count", "facet_jaccard_binding",
                                                      "lexical_jaccard_binding")}
        pairwise["liberating"][key] = {k: m[k] for k in ("shared_varnas", "liberating_shared_facet_count",
                                                         "liberating_unique_facet_count", "facet_jaccard_liberating",
                                                         "lexical_jaccard_liberating")}
        pairwise["combined"][key] = {k: m[k] for k in ("shared_varna_count", "unique_varna_count",
                                                       "facet_jaccard", "lexical_jaccard_mean",
                                                       "combined_overlap_score")}
        pair_j[(a, b)] = m["facet_jaccard"]; pair_lex[(a, b)] = m["lexical_jaccard_mean"]

    # enumerate all size-k subsets deterministically; filter to eligible
    evals = [evaluate_subset(s, recs, pair_j, pair_lex) for s in itertools.combinations(valid_words, K)] \
        if len(valid_words) >= K else []
    eligible = [e for e in evals if e["eligible"]]

    status = None; selected = None; trace = []
    if len(valid_words) < K:
        status = "G0_NOT_TESTABLE_WITH_CURRENT_PROSE_PACKETS"
        trace.append(f"only {len(valid_words)} valid candidates (< k={K}); cannot form a size-{K} set")
    elif not eligible:
        status = "G0_NOT_TESTABLE_WITH_CURRENT_PROSE_PACKETS"
        trace.append(f"{len(evals)} size-{K} subsets of {len(valid_words)} valid words; "
                     f"0 satisfy caps (max facet-Jaccard ≤ {MAX_FACET_JACCARD_CAP}, mean ≤ {MEAN_FACET_JACCARD_CAP}) "
                     f"+ per-word ≥1 unique facet. No relaxation permitted.")
    else:
        # frozen tie-break chain: (max_fj) -> (mean_fj) -> (mean_lex) -> alphabetical(words tuple)
        eligible.sort(key=lambda e: (e["max_facet_jaccard"], e["mean_facet_jaccard"],
                                     e["mean_lexical_jaccard"], tuple(e["words"])))
        best = eligible[0]
        # deterministic tie-break completeness: the alphabetical final key is total -> never ambiguous
        selected = best["words"]
        status = "G0_PASS_WORD_SET_SELECTED"
        trace.append(f"{len(eligible)} eligible size-{K} subsets; selected by min max facet-Jaccard "
                     f"({best['max_facet_jaccard']}), then min mean facet-Jaccard ({best['mean_facet_jaccard']}), "
                     f"then min mean lexical-Jaccard ({best['mean_lexical_jaccard']}), then alphabetical.")

    # ---- write machine-readable artifacts ----
    cand_table = {w: {k: recs[w][k] for k in ("word", "varna_sequence", "facet_count", "missing_varnas",
                                              "valid_both_poles", "leakage", "packet_lengths")}
                  for w in CANDIDATE_POOL}
    (OUT / "candidate_table.json").write_text(json.dumps(cand_table, ensure_ascii=False, indent=2, sort_keys=True))
    (OUT / "pairwise_binding.json").write_text(json.dumps(pairwise["binding"], ensure_ascii=False, indent=2, sort_keys=True))
    (OUT / "pairwise_liberating.json").write_text(json.dumps(pairwise["liberating"], ensure_ascii=False, indent=2, sort_keys=True))
    (OUT / "combined_distinctness.json").write_text(json.dumps(pairwise["combined"], ensure_ascii=False, indent=2, sort_keys=True))

    old_six = ["pride", "freedom", "patience", "courage", "control", "doubt"]
    old_eval = evaluate_subset(old_six, recs, pair_j, pair_lex) if all(w in valid_words for w in old_six) else None

    selection = {
        "artifact": "b1_10_g0_word_set_audit",
        "prereg": "B1_10_WORD_SPECIFICITY_PREREG.md Rev 3 (commit 658a6475)",
        "rule": {"k": K, "max_facet_jaccard_cap": MAX_FACET_JACCARD_CAP,
                 "mean_facet_jaccard_cap": MEAN_FACET_JACCARD_CAP,
                 "min_unique_facet_per_word": 1, "target_unique_facet": 2,
                 "tie_break": ["min max_facet_jaccard", "min mean_facet_jaccard", "min mean_lexical_jaccard",
                               "alphabetical"]},
        "n_candidates": len(CANDIDATE_POOL),
        "n_valid_candidates": len(valid_words),
        "valid_candidates": valid_words,
        "invalid_candidates": {w: recs[w]["missing_varnas"] for w in CANDIDATE_POOL
                               if not recs[w]["valid_both_poles"]},
        "leakage_excluded": [w for w in CANDIDATE_POOL if recs[w]["valid_both_poles"] and recs[w]["leakage"]],
        "n_size_k_subsets_examined": len(evals),
        "n_eligible_subsets": len(eligible),
        "selected_word_set": selected,
        "selected_metrics": (eligible[0] if status == "G0_PASS_WORD_SET_SELECTED" else None),
        "old_six_for_context_only": old_eval,
        "semantic_similarity_status": ("PENDING_SUPPLEMENTARY — not in the frozen selection/tie-break rule; "
                                       "no embedding model/revision is pinned; not required for selection, so "
                                       "not computed here (no network/model call)."),
        "semantic_correctness_inspected": False,
        "trace": trace,
        "status": status,
    }
    (OUT / "selection.json").write_text(json.dumps(selection, ensure_ascii=False, indent=2, sort_keys=True))
    return selection


if __name__ == "__main__":
    s = run_audit()
    print(json.dumps({"status": s["status"], "n_valid": s["n_valid_candidates"],
                      "valid": s["valid_candidates"], "n_eligible_subsets": s["n_eligible_subsets"],
                      "selected": s["selected_word_set"],
                      "selected_metrics": s["selected_metrics"]}, ensure_ascii=False, indent=2))
