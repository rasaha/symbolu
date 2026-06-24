#!/usr/bin/env python3
"""ARCHETYPE-alignment falsification: does the REAL varṇa chain depict a role-word's transformation
archetype better than a SCRAMBLED lexicon AND a RANDOM-SYMBOLIC lexicon? (PREREG_ARCHETYPE_SIGNAL.md)

Not meaning-recovery. Each role word has a pre-registered transformation (doctor: suffering -> healing).
For each word, the lens reading is rendered as a lexicon-agnostic transformation ARC; a blind judge rates
how well that arc depicts the archetype (1-5). Real must beat BOTH controls (CI lower > 0) to count.

Three lexicons:
  real             - the Sanskrit varṇa map (lexicon_authoritative.json)
  scrambled        - (worldly,counter) PAIRS permuted among consonants; vowel essences permuted among
                     vowels. Preserves vocabulary/pairing/length; randomizes only sound->propensity.
                     *Decisive control for the acoustic claim.*
  random-symbolic  - same arc structure built from a NEUTRAL, non-psychological vocabulary pool.
                     Controls for "any symbolic arc reads as a transformation."

Judges:  --judge random   (NULL; ignores content -> Δ≈0, sanity check)
         --judge overlap  (deterministic literal token overlap; low power, reported)
         --judge wordnet  (deterministic semantic similarity; reproducible confirmatory-ish arm)
         --judge llm      (confirmatory; blind sub-agents/API via emit_items/score_items)
"""
from __future__ import annotations

import argparse
import json
import random as _rnd
import re

import varna_lens as V
import wordlist_archetype

S_CONTROL = 20            # seeded control lexicons (scrambled + random), averaged per word
N_BOOT = 10000
BASE_SEED = 20240624
MIN_EFFECT = 0.30         # product-meaningful threshold on the 1–5 fit scale

# Neutral, non-psychological vocabulary for the random-symbolic lexicon (concrete / elemental nouns —
# carry no inherent transformation valence, so a real win over this is not "uses emotion words").
NEUTRAL_POOL = [
    "stone", "river", "copper", "north", "lattice", "ember", "signal", "hollow", "vapor", "thread",
    "prism", "gravel", "harbor", "cinder", "drift", "beacon", "marrow", "quartz", "tide", "husk",
    "granite", "willow", "socket", "bracket", "conduit", "spindle", "pixel", "turbine", "magnet",
    "rubber", "concrete", "ledger", "canister", "gasket", "nozzle", "pavement", "monitor", "girder",
    "filament", "alloy", "basalt", "current", "antenna", "valve", "trellis", "cobble", "shale",
    "tundra", "delta", "meridian", "pylon", "rivet", "louver", "gantry", "ballast", "flange",
    "dune", "reef", "glacier", "canyon", "plateau", "estuary", "isthmus", "fjord", "mesa", "ridge",
]


# ----- phoneme keys (lexicon-independent) ---------------------------------------------------------
_KEYS = {}
def resolve_keys(row):
    ck = (row["word"], row["pron"])
    if ck in _KEYS:
        return _KEYS[ck]
    pron = row["pron"]
    if pron == "roman":
        ph, _ = V.phonemes_roman(row["word"])
    elif pron == "g2p":
        ph, _ = V.phonemes_cmudict(row["word"])
        if not ph:
            ph, _ = V.phonemes_roman(row["word"])
    else:
        ph, _ = V.phonemes_explicit(pron)
    _KEYS[ck] = [(t, k) for (t, k, _s) in ph]
    return _KEYS[ck]


# ----- lexicon maps -------------------------------------------------------------------------------
def _gloss(v):
    m = re.search(r"\(([^)]*)\)", v)
    g = (m.group(1) if m else v).strip()
    return g.split("/")[0].strip()            # trim long vowel glosses to their first clause


def real_maps():
    cons = {k: (_gloss(d["leading_vritti"]), _gloss(d["counter_vritti"])) for k, d in V.CONS.items()}
    vow = {k: _gloss(d["positive"]) for k, d in V.VOW.items()}
    return cons, vow


def scrambled_maps(seed):
    """Permute (worldly,counter) PAIRS among consonants; vowel essences among vowels (same vocabulary)."""
    cons, vow = real_maps()
    r = _rnd.Random(seed)
    ck, cv = list(cons), list(cons.values()); r.shuffle(cv)
    vk, vv = list(vow), list(vow.values()); r.shuffle(vv)
    return dict(zip(ck, cv)), dict(zip(vk, vv))


def random_maps(seed):
    """Same arc structure from a NEUTRAL non-psychological pool — different vocabulary entirely."""
    r = _rnd.Random(seed)
    cons = {k: tuple(r.sample(NEUTRAL_POOL, 2)) for k in V.CONS}
    vow = {k: r.choice(NEUTRAL_POOL) for k in V.VOW}
    return cons, vow


# ----- reading (same vowel-attachment polarity rule as the lens) ----------------------------------
def reading(keys, cons_map, vow_map):
    seq = list(keys)
    summary = None
    if seq and seq[0] != seq[-1] and seq[-1][0] == "V":
        t, k = seq.pop()
        prev = seq[-1] if seq else None
        spos = bool(prev and prev[0] == "C")
        summary = {"worldly": vow_map.get(k), "sign": "+" if spos else "−"}
    elems, n = [], len(seq)
    for i, (t, k) in enumerate(seq):
        if t == "C":
            if k not in cons_map:
                continue
            nxt = seq[i + 1] if i + 1 < n else None
            pos = bool(nxt and nxt[0] == "V") and i != 0
            w, c = cons_map[k]
            elems.append({"kind": "C", "sign": "+" if pos else "−", "worldly": w,
                          "counter": None if pos else c})
        else:
            if k not in vow_map:
                continue
            prev = seq[i - 1] if i > 0 else None
            pos = bool(prev and prev[0] == "C")
            elems.append({"kind": "V", "sign": "+" if pos else "−", "worldly": vow_map[k], "counter": None})
    return elems, summary


def render_arc(elems, summary):
    """Lexicon-agnostic transformation arc. IDENTICAL template for all three lexicons; only glosses differ."""
    w = [e["worldly"] for e in elems] or ["(none)"]
    arcs = [f"{e['worldly']} into {e['counter']}"
            for e in elems if e["kind"] == "C" and e["sign"] == "−" and e["counter"]]
    summ = summary["worldly"] if summary and summary.get("worldly") else w[-1]
    parts = [f"ordered states: {' → '.join(w)}"]
    if arcs:
        parts.append("easing: " + "; ".join(arcs))
    parts.append(f"overall note: {summ}")
    return " | ".join(parts)


def arc_for(row, cons_map, vow_map, shuffle_order=False, oseed=0):
    keys = resolve_keys(row)
    if shuffle_order:
        keys = list(keys); _rnd.Random(oseed).shuffle(keys)
    elems, summary = reading(keys, cons_map, vow_map)
    return render_arc(elems, summary)


# ----- deterministic judges -----------------------------------------------------------------------
_STOP = {"of", "the", "a", "an", "to", "into", "and", "or", "without", "self", "raw"}
def _toks(text):
    return [w for w in re.findall(r"[a-zA-Z]+", text.lower()) if w not in _STOP and len(w) > 2]


def judge_random(arc, frm, to, seed):
    return 1.0 + 4.0 * _rnd.Random(seed).random()


def judge_overlap(arc, frm, to, seed):
    a, t = set(_toks(arc)), set(_toks(frm + " " + to))
    if not t:
        return 1.0
    return 1.0 + 4.0 * (len(a & t) / len(a | t) if (a | t) else 0.0)


_WN = None
def _wordnet():
    global _WN
    if _WN is None:
        from nltk.corpus import wordnet as wn
        try:
            wn.synsets("test")
        except LookupError:
            import nltk; nltk.download("wordnet", quiet=True); nltk.download("omw-1.4", quiet=True)
        _WN = wn
    return _WN


def judge_wordnet(arc, frm, to, seed):
    """Mean best WordNet (Wu-Palmer) similarity of arc content words to the {from,to} archetype words."""
    wn = _wordnet()
    tgt = [s for w in _toks(frm + " " + to) for s in wn.synsets(w)]
    aw = _toks(arc)
    if not tgt or not aw:
        return 1.0
    sims = []
    for w in aw:
        syn = wn.synsets(w)
        if not syn:
            continue
        sims.append(max((a.wup_similarity(b) or 0.0) for a in syn for b in tgt))
    s = sum(sims) / len(sims) if sims else 0.0
    return 1.0 + 4.0 * max(0.0, min(1.0, s))


JUDGES = {"random": judge_random, "overlap": judge_overlap, "wordnet": judge_wordnet}


# ----- bootstrap + verdict ------------------------------------------------------------------------
def _boot_ci(vals, n=N_BOOT, seed=BASE_SEED):
    r = _rnd.Random(seed); m = len(vals); out = []
    for _ in range(n):
        out.append(sum(vals[r.randrange(m)] for _ in range(m)) / m)
    out.sort()
    return out[int(0.025 * n)], out[int(0.975 * n)]


def verdict_from(delta_scr, delta_rnd):
    d_s = sum(delta_scr) / len(delta_scr); ds_lo, ds_hi = _boot_ci(delta_scr)
    d_r = sum(delta_rnd) / len(delta_rnd); dr_lo, dr_hi = _boot_ci(delta_rnd)
    beats_both = ds_lo > 0 and dr_lo > 0
    if beats_both and min(d_s, d_r) >= MIN_EFFECT:
        verdict = "ARCHETYPE_SIGNAL_DETECTED"
    elif beats_both:
        verdict = "ARCHETYPE_SIGNAL_WEAK"
    else:
        verdict = "NO_ARCHETYPE_SIGNAL"
    return {"delta_scr": d_s, "delta_scr_ci95": [ds_lo, ds_hi],
            "delta_rnd": d_r, "delta_rnd_ci95": [dr_lo, dr_hi],
            "min_delta": min(d_s, d_r), "min_effect": MIN_EFFECT, "verdict": verdict}


# ----- deterministic run --------------------------------------------------------------------------
def run(judge_name, rows=None, n_control=S_CONTROL):
    rows = rows or wordlist_archetype.load()
    judge = JUDGES[judge_name]
    cons, vow = real_maps()

    fit_real, fit_scr, fit_rnd, fit_shuf = [], [], [], []
    for i, r in enumerate(rows):
        frm, to = r["from_state"], r["to_state"]
        fit_real.append(judge(arc_for(r, cons, vow), frm, to, BASE_SEED * 2 + i))
        fit_shuf.append(judge(arc_for(r, cons, vow, shuffle_order=True, oseed=BASE_SEED * 7 + i),
                              frm, to, BASE_SEED * 2 + i))
        ss, rr = [], []
        for s in range(n_control):
            cm, vm = scrambled_maps(BASE_SEED + 101 * s)
            ss.append(judge(arc_for(r, cm, vm), frm, to, BASE_SEED * 5 + i * 97 + s))
            rcm, rvm = random_maps(BASE_SEED + 211 * s)
            rr.append(judge(arc_for(r, rcm, rvm), frm, to, BASE_SEED * 9 + i * 89 + s))
        fit_scr.append(sum(ss) / len(ss))
        fit_rnd.append(sum(rr) / len(rr))

    delta_scr = [fit_real[i] - fit_scr[i] for i in range(len(rows))]
    delta_rnd = [fit_real[i] - fit_rnd[i] for i in range(len(rows))]
    v = verdict_from(delta_scr, delta_rnd)

    doms = {}
    for i, r in enumerate(rows):
        doms.setdefault(r["domain"], []).append(i)
    by_domain = {d: {"n": len(ix), "d_scr": sum(delta_scr[j] for j in ix) / len(ix),
                     "d_rnd": sum(delta_rnd[j] for j in ix) / len(ix)} for d, ix in doms.items()}

    return {"judge": judge_name, "n": len(rows), "controls": n_control, "min_effect": MIN_EFFECT,
            "fit_real": sum(fit_real) / len(fit_real), "fit_scrambled": sum(fit_scr) / len(fit_scr),
            "fit_random": sum(fit_rnd) / len(fit_rnd), "fit_order_shuffled": sum(fit_shuf) / len(fit_shuf),
            **v, "by_domain": by_domain}


# ----- LLM arm: emit blind trios, score from external picks ---------------------------------------
def emit_items(rows=None, control_seed=0):
    """One blind item per word: archetype + 3 chains (real/scrambled/random) in randomized, hidden order.
    Returns (items, key). key[id] maps slot -> arm. The judge must not see key."""
    rows = rows or wordlist_archetype.load()
    cons, vow = real_maps()
    cm, vm = scrambled_maps(BASE_SEED + 101 * control_seed)
    rcm, rvm = random_maps(BASE_SEED + 211 * control_seed)
    items, key = [], {}
    rr = _rnd.Random(BASE_SEED + control_seed)
    for i, r in enumerate(rows):
        arms = [("real", arc_for(r, cons, vow)),
                ("scrambled", arc_for(r, cm, vm)),
                ("random", arc_for(r, rcm, rvm))]
        rr.shuffle(arms)
        iid = f"{i}"
        items.append({"id": iid, "from": r["from_state"], "to": r["to_state"],
                      "chains": {str(s + 1): a for s, (_arm, a) in enumerate(arms)}})
        key[iid] = {str(s + 1): arm for s, (arm, _a) in enumerate(arms)}
    return items, key


def score_items(judge_scores, key, rows=None):
    """judge_scores: list of {id: {"1":1-5,"2":1-5,"3":1-5}} (one dict per blind judge).
    Averages per-word over judges, maps slots back to arms, computes deltas + verdict."""
    rows = rows or wordlist_archetype.load()
    real, scr, rnd = [], [], []
    for iid, slotmap in key.items():
        per = {"real": [], "scrambled": [], "random": []}
        for js in judge_scores:
            if iid not in js:
                continue
            for slot, arm in slotmap.items():
                if slot in js[iid]:
                    per[arm].append(float(js[iid][slot]))
        if not per["real"] or not per["scrambled"] or not per["random"]:
            continue
        real.append(sum(per["real"]) / len(per["real"]))
        scr.append(sum(per["scrambled"]) / len(per["scrambled"]))
        rnd.append(sum(per["random"]) / len(per["random"]))
    if not real:
        return {"judge": "llm", "n": 0, "verdict": "NO_ARCHETYPE_SIGNAL"}
    delta_scr = [real[i] - scr[i] for i in range(len(real))]
    delta_rnd = [real[i] - rnd[i] for i in range(len(real))]
    v = verdict_from(delta_scr, delta_rnd)
    return {"judge": "llm", "n": len(real), "controls": 1, "n_judges": len(judge_scores),
            "fit_real": sum(real) / len(real), "fit_scrambled": sum(scr) / len(scr),
            "fit_random": sum(rnd) / len(rnd), **v}


def to_markdown(res):
    L = [f"# Results — archetype-alignment test (judge = {res['judge']})", "",
         f"- N = {res['n']}  ·  controls = real / scrambled / random-symbolic  ·  MIN_EFFECT = {res['min_effect']} (1–5)",
         f"- fit(real)            = {res['fit_real']:.3f}",
         f"- fit(scrambled)       = {res['fit_scrambled']:.3f}",
         f"- fit(random-symbolic) = {res['fit_random']:.3f}"]
    if "fit_order_shuffled" in res:
        L.append(f"- fit(real, order-shuffled) = {res['fit_order_shuffled']:.3f}")
    L += [f"- **Δ_scr = real − scrambled = {res['delta_scr']:+.3f}**  (95% CI {res['delta_scr_ci95'][0]:+.3f} … {res['delta_scr_ci95'][1]:+.3f})",
          f"- **Δ_rnd = real − random   = {res['delta_rnd']:+.3f}**  (95% CI {res['delta_rnd_ci95'][0]:+.3f} … {res['delta_rnd_ci95'][1]:+.3f})",
          "", f"## VERDICT: **{res['verdict']}**", ""]
    if "by_domain" in res:
        L += ["| domain | n | Δ_scr | Δ_rnd |", "|---|---|---|---|"]
        for d, x in sorted(res["by_domain"].items()):
            L.append(f"| {d} | {x['n']} | {x['d_scr']:+.3f} | {x['d_rnd']:+.3f} |")
        L.append("")
    L += ["_Pre-registered (PREREG_ARCHETYPE_SIGNAL.md). Verdict computed by rule, not by hand. "
          "NOT a meaning claim; not part of C×R×S._"]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", choices=list(JUDGES), default="wordnet")
    ap.add_argument("--controls", type=int, default=S_CONTROL)
    ap.add_argument("--emit", action="store_true", help="emit blind LLM items+key as JSON (for sub-agent judges)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    if args.emit:
        items, key = emit_items()
        print(json.dumps({"items": items, "key": key}, ensure_ascii=False, indent=2))
        return 0
    res = run(args.judge, n_control=args.controls)
    md = to_markdown(res)
    print(md)
    print("\nJSON:", json.dumps({k: v for k, v in res.items() if k != "by_domain"}, ensure_ascii=False))
    if args.out:
        open(args.out, "w", encoding="utf-8").write(md + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
