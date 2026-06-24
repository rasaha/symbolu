#!/usr/bin/env python3
"""H1 — Interpretive-convergence test for the Varṇa Profile Method (VARNA_PROFILE_METHOD.md).

Claim under test (H1): given a word's varṇa profile, independent readers produce CONVERGENT readings —
i.e. the profile reliably *channels* interpretation. This is a property of the system as a generative
instrument; it does NOT claim veridical decoding (H3, falsified).

Design: blind readers each author a short character sketch for many items. Items are chains under three
lexicons plus a no-seed floor:
  real       — the varṇa chain (real lexicon)
  scrambled  — same propensity vocabulary, permuted mapping (honesty control)
  random     — neutral-noun chain (vocabulary control)
  free       — NO seed (floor: how much do readers agree with no profile at all?)
Readers never see the word or the condition. Convergence = mean pairwise content-word cosine of the R
readers' sketches for an item. Higher = the seed channels readers to a shared reading.

Honest reading of results:
- convergence(real) >> convergence(free)  ⇒  the profile is a real generative constraint (H1 support).
- convergence(real) ≈ convergence(scrambled)  ⇒  the channeling is structural, not from the specific
  sound→gloss mapping (consistent with the six prior nulls — reported, not hidden).
"""
from __future__ import annotations
import argparse, json, math, re, random as _rnd
from collections import Counter
import archetype_test as AT

BASE = AT.BASE_SEED
WORDS = ["doctor", "mother", "river", "warrior", "ocean", "silence", "machine", "garden"]
N_FREE = 3

_STOP = {"the", "and", "with", "that", "this", "from", "into", "their", "they", "them", "than", "then",
         "your", "you", "for", "are", "was", "who", "her", "his", "its", "but", "not", "has", "have",
         "one", "out", "off", "all", "any", "can", "she", "him", "had", "a", "an", "of", "to", "in",
         "is", "it", "as", "at", "on", "or", "by", "be"}


# ----- items -------------------------------------------------------------------------------------
def build_items():
    cons, vow = AT.real_maps()
    cm, vm = AT.scrambled_maps(BASE + 101)
    rcm, rvm = AT.random_maps(BASE + 211)
    items, key = [], {}
    for i, w in enumerate(WORDS):
        row = {"word": w, "pron": "g2p"}
        for cond, (c, v) in [("real", (cons, vow)), ("scrambled", (cm, vm)), ("random", (rcm, rvm))]:
            iid = f"{i}:{cond}"
            items.append({"id": iid, "chain": AT.arc_for(row, c, v)})
            key[iid] = {"word": w, "cond": cond}
    for k in range(N_FREE):
        iid = f"free:{k}"
        items.append({"id": iid, "chain": None})
        key[iid] = {"word": None, "cond": "free"}
    _rnd.Random(BASE).shuffle(items)
    return items, key


# ----- convergence metric ------------------------------------------------------------------------
def _vec(text):
    toks = [t for t in re.findall(r"[a-z]+", (text or "").lower()) if t not in _STOP and len(t) > 3]
    return Counter(toks)


def _cos(a, b):
    common = set(a) & set(b)
    num = sum(a[t] * b[t] for t in common)
    da = math.sqrt(sum(v * v for v in a.values())); db = math.sqrt(sum(v * v for v in b.values()))
    return num / (da * db) if da and db else 0.0


def convergence(texts):
    vs = [_vec(t) for t in texts if t]
    pairs = [_cos(vs[i], vs[j]) for i in range(len(vs)) for j in range(i + 1, len(vs))]
    return sum(pairs) / len(pairs) if pairs else 0.0


def _boot_ci(vals, n=10000, seed=BASE):
    if not vals:
        return (0.0, 0.0)
    r = _rnd.Random(seed); m = len(vals); out = []
    for _ in range(n):
        out.append(sum(vals[r.randrange(m)] for _ in range(m)) / m)
    out.sort()
    return out[int(0.025 * n)], out[int(0.975 * n)]


# ----- scoring -----------------------------------------------------------------------------------
def score(readers, key):
    """readers: list of {id: sketch_text} (one dict per blind reader)."""
    by_cond = {"real": [], "scrambled": [], "random": [], "free": []}
    per_word = {}            # word -> {cond: convergence}
    for iid, meta in key.items():
        texts = [r[iid] for r in readers if iid in r and r[iid]]
        if len(texts) < 2:
            continue
        c = convergence(texts)
        by_cond[meta["cond"]].append(c)
        if meta["word"]:
            per_word.setdefault(meta["word"], {})[meta["cond"]] = c
    # per-word paired deltas (real vs scrambled, real vs random)
    d_scr, d_rnd = [], []
    for w, cc in per_word.items():
        if "real" in cc and "scrambled" in cc:
            d_scr.append(cc["real"] - cc["scrambled"])
        if "real" in cc and "random" in cc:
            d_rnd.append(cc["real"] - cc["random"])
    mean = lambda xs: sum(xs) / len(xs) if xs else 0.0
    out = {
        "n_readers": len(readers), "n_words": len(per_word),
        "conv_real": mean(by_cond["real"]), "conv_scrambled": mean(by_cond["scrambled"]),
        "conv_random": mean(by_cond["random"]), "conv_free": mean(by_cond["free"]),
        "conv_real_ci": _boot_ci(by_cond["real"]), "conv_free_ci": _boot_ci(by_cond["free"]),
        "delta_real_vs_free": mean(by_cond["real"]) - mean(by_cond["free"]),
        "delta_real_vs_scrambled": mean(d_scr), "d_scr_ci": _boot_ci(d_scr),
        "delta_real_vs_random": mean(d_rnd), "d_rnd_ci": _boot_ci(d_rnd),
        "per_word": per_word,
    }
    # H1 verdict: profile channels interpretation iff real convergence clearly above the no-seed floor.
    out["H1_channels"] = out["conv_real_ci"][0] > out["conv_free"]
    out["mapping_adds"] = out["d_scr_ci"][0] > 0   # does the specific mapping add convergence?
    return out


def to_markdown(res):
    L = [f"# H1 results — interpretive convergence ({res['n_readers']} blind readers, {res['n_words']} words)", "",
         f"- convergence(real)      = {res['conv_real']:.3f}  (95% CI {res['conv_real_ci'][0]:.3f}–{res['conv_real_ci'][1]:.3f})",
         f"- convergence(scrambled) = {res['conv_scrambled']:.3f}",
         f"- convergence(random)    = {res['conv_random']:.3f}",
         f"- convergence(free/no-seed floor) = {res['conv_free']:.3f}  (95% CI {res['conv_free_ci'][0]:.3f}–{res['conv_free_ci'][1]:.3f})",
         "",
         f"- **Δ real − free  = {res['delta_real_vs_free']:+.3f}**  → H1 (profile channels interpretation): "
         f"**{'SUPPORTED' if res['H1_channels'] else 'not supported'}**",
         f"- Δ real − scrambled = {res['delta_real_vs_scrambled']:+.3f}  (95% CI {res['d_scr_ci'][0]:+.3f}…{res['d_scr_ci'][1]:+.3f})  "
         f"→ specific mapping adds convergence: **{'yes' if res['mapping_adds'] else 'no (structural, as expected)'}**",
         f"- Δ real − random = {res['delta_real_vs_random']:+.3f}  (95% CI {res['d_rnd_ci'][0]:+.3f}…{res['d_rnd_ci'][1]:+.3f})",
         "",
         "_H1 = the profile reliably channels independent readers to a shared reading (a property of the_",
         "_system as a generative instrument). It does NOT claim veridical decoding (H3, falsified). A real≈_",
         "_scrambled result means the channeling is structural, not from the specific sound→gloss mapping._"]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit", action="store_true", help="emit blind reader items + key as JSON")
    ap.add_argument("--score", help="path to readers JSON (list of {id:text}) to score")
    ap.add_argument("--keyfile", help="path to key JSON (from --emit)")
    a = ap.parse_args(argv)
    if a.emit:
        items, key = build_items()
        print(json.dumps({"items": items, "key": key}, ensure_ascii=False, indent=1))
        return 0
    if a.score:
        readers = json.load(open(a.score))
        key = json.load(open(a.keyfile))["key"] if a.keyfile else build_items()[1]
        res = score(readers, key)
        print(to_markdown(res))
        print("\nJSON:", json.dumps({k: v for k, v in res.items() if k != "per_word"}, ensure_ascii=False))
        return 0
    ap.error("use --emit or --score")


if __name__ == "__main__":
    raise SystemExit(main())
