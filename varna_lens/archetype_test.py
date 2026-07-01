#!/usr/bin/env python3
"""Blind ARCHETYPE-alignment test: does the real varṇa chain fit a word's transformation
archetype (FROM→TO) better than a SCRAMBLED chain or a RANDOM-SYMBOLIC chain?

Pre-registered in PREREG_ARCHETYPE_SIGNAL.md. This is a DIFFERENT hypothesis than the two prior
falsified tests. Prior test 1 asked "can the chain recover the exact dictionary word?" (NO_SIGNAL).
Prior test 2 asked "is a real artifact more useful than a scrambled one?" (NO_UTILITY_SIGNAL). This
asks the lower-resolution question ChatGPT raised: for role/function words whose *archetypal
transformation* is clear (doctor: suffering→healing), does the REAL sound→propensity chain embody
that transformation better than controls?

Three lexicons per word (all rendered as a comma-separated propensity chain, mechanically, no signs):
  real       — the frozen Sanskrit worldly-gloss lexicon (varna_lens.CONS/VOW)
  scrambled  — the same rich propensity vocabulary, permuted among keys (the LOAD-BEARING control:
               if real ≈ scrambled, "any rich vocabulary fits archetypes via reader projection")
  random     — content-free symbol tokens (a FLOOR: nonsense cannot embody a transformation)

Metric: a BLIND judge (never told which chain is which) RANKS the three chains 1(best)–3(worst) by
how well the propensity sequence embodies the word's FROM→TO transformation. Positions randomized
per word. Multiple independent blind judges; ranks averaged.

Pre-registered verdict (ChatGPT's rule):
  ARCHETYPE_SIGNAL_DETECTED   iff mean_rank(real) < mean_rank(scrambled) AND < mean_rank(random),
                              with bootstrap CI lower bound of BOTH rank-advantages > 0.
  NO_ARCHETYPE_SIGNAL         iff real-vs-scrambled advantage CI contains 0 (real indistinguishable
                              from the permuted control — restates NO_SIGNAL at the archetypal level).
  INCONCLUSIVE                otherwise.

Usage:
  python archetype_test.py emit  --out packet.json     # writes blind judging packet (+ hidden key)
  python archetype_test.py score --packet packet.json --judges j1.json j2.json j3.json --out RESULTS.md
"""
from __future__ import annotations

import argparse
import json
import random as _rnd

import varna_lens as V
from signal_test import phoneme_keys, real_maps, scrambled_maps, essence, _boot_ci

BASE_SEED = 20240624
LEXES = ["real", "scrambled", "random"]

# ----- role words with FROZEN archetypes (committed before any chain is generated) ---------------
# Each: (word, FROM, TO). FROM→TO is the archetypal transformation the role effects.
ARCHETYPES = [
    ("doctor",   "suffering",        "healing / restored vitality"),
    ("teacher",  "ignorance",        "understanding"),
    ("judge",    "dispute",          "resolution / just order"),
    ("warrior",  "threat",           "protection"),
    ("mother",   "vulnerability",    "nourishment / safety"),
    ("monk",     "attachment",       "detachment / stillness"),
    ("king",     "disorder",         "authority / order"),
    ("artist",   "inner image",      "outer form"),
    ("farmer",   "seed",             "nourishment / harvest"),
    ("priest",   "ordinary",         "sacred / consecrated"),
    ("healer",   "wound",            "wholeness"),
    ("guardian", "danger",           "safety"),
    ("leader",   "confusion",        "direction"),
    ("thief",    "security",         "loss / dispossession"),
    ("tyrant",   "freedom",          "oppression / domination"),
    ("nurse",    "sickness",         "care / recovery"),
    ("builder",  "emptiness",        "structure"),
    ("hunter",   "prey",             "sustenance"),
    ("sage",     "question",         "wisdom"),
    ("servant",  "need",             "service"),
]


def _rows():
    return [{"word": w, "pron": "g2p", "from": f, "to": t} for (w, f, t) in ARCHETYPES]


# ----- random-symbolic lexicon (content-free tokens) ---------------------------------------------
_SYL_C = "kgtdpbmnrlsvzhcj"
_SYL_V = "aeiou"
def random_maps(seed):
    """Assign each varṇa key a content-free pronounceable nonsense token (no semantic content)."""
    r = _rnd.Random(seed)
    def tok():
        return r.choice(_SYL_C) + r.choice(_SYL_V) + r.choice(_SYL_C) + r.choice(_SYL_V)
    cons = {k: tok() for k in V.CONS}
    vow = {k: tok() for k in V.VOW}
    return cons, vow


def chain_for(keys, lex):
    if lex == "real":
        cm, vm = real_maps()
    elif lex == "scrambled":
        cm, vm = scrambled_maps(BASE_SEED + 5)          # one fixed scramble seed for the packet
    else:
        cm, vm = random_maps(BASE_SEED + 9)
    return essence(keys, cm, vm)


# ----- emit blind judging packet ------------------------------------------------------------------
def emit(out_path):
    rows = _rows()
    keys_all = [phoneme_keys(r) for r in rows]
    blind, key = [], []
    for i, (row, keys) in enumerate(zip(rows, keys_all)):
        chains = {lex: chain_for(keys, lex) for lex in LEXES}
        labels = ["A", "B", "C"]
        order = list(LEXES)
        _rnd.Random(BASE_SEED + 31 * i).shuffle(order)   # randomize which lexicon is A/B/C
        lab2lex = dict(zip(labels, order))
        blind.append({
            "id": i, "word": row["word"], "from": row["from"], "to": row["to"],
            "choices": {lab: chains[lab2lex[lab]] for lab in labels},
        })
        key.append({"id": i, "word": row["word"], "label2lex": lab2lex})
    packet = {"base_seed": BASE_SEED, "n": len(rows), "blind": blind, "key": key}
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(packet, fh, ensure_ascii=False, indent=2)
    # also print the judge-facing (blind) view
    print(f"# Archetype judging packet — {len(rows)} words, 3 chains each (A/B/C, order randomized)\n")
    print("For each word, RANK the three chains 1(best)–3(worst) by how well the propensity sequence")
    print("embodies the transformation FROM → TO. Output JSON: {\"<id>\": {\"A\":rank,\"B\":rank,\"C\":rank}}.\n")
    for b in blind:
        print(f"[{b['id']}] {b['word']}:  {b['from']}  →  {b['to']}")
        for lab in ("A", "B", "C"):
            print(f"    {lab}. {b['choices'][lab]}")
        print()
    return packet


# ----- score against blind judges' rankings -------------------------------------------------------
def score(packet_path, judge_paths, out_path=None):
    with open(packet_path, encoding="utf-8") as fh:
        packet = json.load(fh)
    key = {k["id"]: k["label2lex"] for k in packet["key"]}
    judges = []
    for p in judge_paths:
        with open(p, encoding="utf-8") as fh:
            judges.append({int(k): v for k, v in json.load(fh).items()})

    n = packet["n"]
    # per-word mean rank per lexicon (averaged over judges); rank 1=best
    rank = {lex: [] for lex in LEXES}
    for i in range(n):
        lab2lex = key[i]
        for lex in LEXES:
            lab = next(l for l, lx in lab2lex.items() if lx == lex)
            rs = [j[i][lab] for j in judges if i in j and lab in j[i]]
            rank[lex].append(sum(rs) / len(rs) if rs else 2.0)

    mean_rank = {lex: sum(rank[lex]) / n for lex in LEXES}
    # real ranked #1 rate (chance = 1/3): count words where real's mean rank is strictly the lowest
    real_first = sum(1 for i in range(n)
                     if rank["real"][i] < rank["scrambled"][i] and rank["real"][i] < rank["random"][i]) / n

    # advantages (control_rank − real_rank): positive = real is better (lower rank)
    adv_scr = [rank["scrambled"][i] - rank["real"][i] for i in range(n)]
    adv_rnd = [rank["random"][i] - rank["real"][i] for i in range(n)]
    scr_lo, scr_hi = _boot_ci(adv_scr)
    rnd_lo, rnd_hi = _boot_ci(adv_rnd)

    beats_scr = mean_rank["real"] < mean_rank["scrambled"] and scr_lo > 0
    beats_rnd = mean_rank["real"] < mean_rank["random"] and rnd_lo > 0
    if beats_scr and beats_rnd:
        verdict = "ARCHETYPE_SIGNAL_DETECTED"
    elif scr_lo <= 0 <= scr_hi:
        verdict = "NO_ARCHETYPE_SIGNAL"
    else:
        verdict = "INCONCLUSIVE"

    res = {
        "n_words": n, "n_judges": len(judges), "chance_first": 1 / 3,
        "mean_rank": mean_rank, "real_first_rate": real_first,
        "adv_real_vs_scrambled": sum(adv_scr) / n, "adv_scr_ci95": [scr_lo, scr_hi],
        "adv_real_vs_random": sum(adv_rnd) / n, "adv_rnd_ci95": [rnd_lo, rnd_hi],
        "verdict": verdict,
        "per_word": [{"word": packet["blind"][i]["word"],
                      "real": rank["real"][i], "scrambled": rank["scrambled"][i],
                      "random": rank["random"][i]} for i in range(n)],
    }
    md = to_markdown(res)
    print(md)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(md + "\n")
    print("\nJSON:", json.dumps({k: v for k, v in res.items() if k != "per_word"}, ensure_ascii=False))
    return res


def to_markdown(res):
    mr = res["mean_rank"]
    L = [f"# Results — archetype-alignment test", "",
         f"- role words N = {res['n_words']}  ·  blind judges = {res['n_judges']}  ·  "
         f"metric = mean rank 1(best)–3(worst)  ·  real-first chance = {res['chance_first']:.3f}",
         f"- **mean rank(real) = {mr['real']:.3f}**  ·  mean rank(scrambled) = {mr['scrambled']:.3f}  ·  "
         f"mean rank(random) = {mr['random']:.3f}",
         f"- real ranked #1 rate = {res['real_first_rate']:.3f}  (chance {res['chance_first']:.3f})",
         f"- **real vs scrambled advantage = {res['adv_real_vs_scrambled']:+.3f}**  "
         f"(95% CI {res['adv_scr_ci95'][0]:+.3f} … {res['adv_scr_ci95'][1]:+.3f})  ← LOAD-BEARING",
         f"- real vs random advantage = {res['adv_real_vs_random']:+.3f}  "
         f"(95% CI {res['adv_rnd_ci95'][0]:+.3f} … {res['adv_rnd_ci95'][1]:+.3f})  (floor)",
         "", f"## VERDICT: **{res['verdict']}**", "",
         "| word | rank(real) | rank(scrambled) | rank(random) |", "|---|---|---|---|"]
    for w in res["per_word"]:
        L.append(f"| {w['word']} | {w['real']:.2f} | {w['scrambled']:.2f} | {w['random']:.2f} |")
    L += ["", "_Pre-registered (PREREG_ARCHETYPE_SIGNAL.md). Verdict computed by rule, not by hand. "
          "Load-bearing comparison is real vs scrambled; random is a floor. "
          "Interpretive lens — not part of C×R×S._"]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("emit"); e.add_argument("--out", default="archetype_packet.json")
    s = sub.add_parser("score")
    s.add_argument("--packet", default="archetype_packet.json")
    s.add_argument("--judges", nargs="+", required=True)
    s.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    if args.cmd == "emit":
        emit(args.out)
    else:
        score(args.packet, args.judges, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
