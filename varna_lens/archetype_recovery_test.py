#!/usr/bin/env python3
"""ARCHETYPE RECOVERY (forced-choice "absolute match") falsification.

Stricter than archetype_test.py: instead of a soft 1-5 fit rating (which lets a reader project a fit
onto any evocative chain), the judge must PICK which archetype a chain belongs to, from a lineup of K
(the correct one + K-1 decoys). There is a definite right/wrong answer, so projection cannot help.

If the real sound->propensity map is an "absolute match", the real chain should identify its own
archetype ABOVE CHANCE and ABOVE both a scrambled lexicon and a random-symbolic lexicon.

Pre-registered in PREREG_ARCHETYPE_RECOVERY.md.

Judges:  --judge random   (NULL; must land at chance = 1/K)
         --judge wordnet  (deterministic semantic; reproducible)
         --judge llm      (confirmatory; blind sub-agents via emit_items/score_items)
"""
from __future__ import annotations

import argparse
import json
import random as _rnd

import varna_lens as V
import wordlist_archetype
import archetype_test as AT

K = 6                      # options per forced-choice item; chance = 1/K
S_CONTROL = 20            # seeded control lexicons (scrambled + random), averaged per word
N_BOOT = 10000
BASE_SEED = AT.BASE_SEED


# ----- forced-choice lineups (deterministic, fixed before judging) --------------------------------
def build_lineups(rows, k=K):
    arch = [(r["from_state"], r["to_state"]) for r in rows]
    lineups = []
    for i, r in enumerate(rows):
        rng = _rnd.Random(BASE_SEED + 17 * i)
        correct = arch[i]
        pool = [a for j, a in enumerate(arch) if j != i]
        rng.shuffle(pool)
        opts = pool[:k - 1] + [correct]
        rng.shuffle(opts)
        lineups.append({"options": opts, "correct": opts.index(correct)})
    return lineups


def _fmt(opt):
    return f"{opt[0]} → {opt[1]}"


# ----- deterministic judges -----------------------------------------------------------------------
def judge_random(chain, options, seed):
    return _rnd.Random(seed).randrange(len(options))


def judge_wordnet(chain, options, seed):
    wn = AT._wordnet()
    cw = AT._toks(chain)
    csyn = [s for w in cw for s in wn.synsets(w)]
    best, bi = -1.0, 0
    for i, opt in enumerate(options):
        ow = AT._toks(_fmt(opt))
        sims = []
        for w in ow:
            syn = wn.synsets(w)
            if not syn or not csyn:
                continue
            sims.append(max((a.wup_similarity(b) or 0.0) for a in syn for b in csyn))
        score = sum(sims) / len(sims) if sims else 0.0
        if score > best:
            best, bi = score, i
    return bi


JUDGES = {"random": judge_random, "wordnet": judge_wordnet}


# ----- bootstrap ----------------------------------------------------------------------------------
def _boot_ci(vals, n=N_BOOT, seed=BASE_SEED):
    r = _rnd.Random(seed); m = len(vals); out = []
    for _ in range(n):
        out.append(sum(vals[r.randrange(m)] for _ in range(m)) / m)
    out.sort()
    return out[int(0.025 * n)], out[int(0.975 * n)]


def _verdict(acc_real_vec, delta_scr, delta_rnd, chance):
    ar = sum(acc_real_vec) / len(acc_real_vec); ar_lo, ar_hi = _boot_ci(acc_real_vec)
    ds = sum(delta_scr) / len(delta_scr); ds_lo, ds_hi = _boot_ci(delta_scr)
    dr = sum(delta_rnd) / len(delta_rnd); dr_lo, dr_hi = _boot_ci(delta_rnd)
    detected = ar_lo > chance and ds_lo > 0 and dr_lo > 0
    verdict = "ARCHETYPE_RECOVERY_SIGNAL" if detected else "NO_ARCHETYPE_RECOVERY_SIGNAL"
    return {"acc_real": ar, "acc_real_ci95": [ar_lo, ar_hi], "chance": chance,
            "delta_scr": ds, "delta_scr_ci95": [ds_lo, ds_hi],
            "delta_rnd": dr, "delta_rnd_ci95": [dr_lo, dr_hi], "verdict": verdict}


# ----- deterministic run --------------------------------------------------------------------------
def run(judge_name, rows=None, n_control=S_CONTROL):
    rows = rows or wordlist_archetype.load()
    lineups = build_lineups(rows)
    judge = JUDGES[judge_name]
    cons, vow = AT.real_maps()
    chance = 1.0 / K

    real, scr, rnd = [], [], []
    for i, r in enumerate(rows):
        opts, ci = lineups[i]["options"], lineups[i]["correct"]
        real.append(1.0 if judge(AT.arc_for(r, cons, vow), opts, BASE_SEED * 2 + i) == ci else 0.0)
        sa, ra = [], []
        for s in range(n_control):
            cm, vm = AT.scrambled_maps(BASE_SEED + 101 * s)
            sa.append(1.0 if judge(AT.arc_for(r, cm, vm), opts, BASE_SEED * 5 + i * 97 + s) == ci else 0.0)
            rcm, rvm = AT.random_maps(BASE_SEED + 211 * s)
            ra.append(1.0 if judge(AT.arc_for(r, rcm, rvm), opts, BASE_SEED * 9 + i * 89 + s) == ci else 0.0)
        scr.append(sum(sa) / len(sa)); rnd.append(sum(ra) / len(ra))

    d_scr = [real[i] - scr[i] for i in range(len(rows))]
    d_rnd = [real[i] - rnd[i] for i in range(len(rows))]
    v = _verdict(real, d_scr, d_rnd, chance)
    return {"judge": judge_name, "n": len(rows), "K": K, "controls": n_control,
            "acc_scrambled": sum(scr) / len(scr), "acc_random": sum(rnd) / len(rnd), **v}


# ----- LLM arm: emit blind forced-choice items, score from picks -----------------------------------
def emit_items(lexicon, rows=None, control_seed=0):
    """Blind forced-choice items for one lexicon. lexicon in {real,scrambled,random}.
    Judge sees only chain + options; picks an index. Returns (items, key=correct index per id)."""
    rows = rows or wordlist_archetype.load()
    lineups = build_lineups(rows)
    if lexicon == "real":
        cons, vow = AT.real_maps()
    elif lexicon == "scrambled":
        cons, vow = AT.scrambled_maps(BASE_SEED + 101 * control_seed)
    else:
        cons, vow = AT.random_maps(BASE_SEED + 211 * control_seed)
    items, key = [], {}
    for i, r in enumerate(rows):
        items.append({"id": str(i), "chain": AT.arc_for(r, cons, vow),
                      "options": {str(j): _fmt(o) for j, o in enumerate(lineups[i]["options"])}})
        key[str(i)] = lineups[i]["correct"]
    return items, key


def score_items(picks_by_arm, key):
    """picks_by_arm: {arm: [ {id: chosen_index_int}, ... per judge ]}. Per-word accuracy averaged
    over that arm's judges; then real-vs-control deltas + verdict."""
    rows = wordlist_archetype.load()
    chance = 1.0 / K
    def acc_vec(judge_list):
        vec = []
        for iid, ci in key.items():
            hits = [1.0 if (iid in js and int(js[iid]) == ci) else 0.0 for js in judge_list]
            vec.append(sum(hits) / len(hits) if hits else 0.0)
        return vec
    real = acc_vec(picks_by_arm["real"]); scr = acc_vec(picks_by_arm["scrambled"]); rnd = acc_vec(picks_by_arm["random"])
    d_scr = [real[i] - scr[i] for i in range(len(real))]
    d_rnd = [real[i] - rnd[i] for i in range(len(real))]
    v = _verdict(real, d_scr, d_rnd, chance)
    return {"judge": "llm", "n": len(real), "K": K,
            "n_judges_per_arm": {a: len(p) for a, p in picks_by_arm.items()},
            "acc_scrambled": sum(scr) / len(scr), "acc_random": sum(rnd) / len(rnd), **v}


def to_markdown(res):
    return "\n".join([
        f"# Results — archetype RECOVERY (forced-choice) test (judge = {res['judge']})", "",
        f"- N = {res['n']}  ·  K = {res['K']} options  ·  chance = {res['chance']:.3f}",
        f"- **accuracy(real)      = {res['acc_real']:.3f}**  (95% CI {res['acc_real_ci95'][0]:.3f}–{res['acc_real_ci95'][1]:.3f})",
        f"- accuracy(scrambled) = {res['acc_scrambled']:.3f}",
        f"- accuracy(random)    = {res['acc_random']:.3f}",
        f"- **Δ_scr = real − scrambled = {res['delta_scr']:+.3f}**  (95% CI {res['delta_scr_ci95'][0]:+.3f} … {res['delta_scr_ci95'][1]:+.3f})",
        f"- **Δ_rnd = real − random   = {res['delta_rnd']:+.3f}**  (95% CI {res['delta_rnd_ci95'][0]:+.3f} … {res['delta_rnd_ci95'][1]:+.3f})",
        "", f"## VERDICT: **{res['verdict']}**", "",
        "_Pre-registered (PREREG_ARCHETYPE_RECOVERY.md). Verdict computed by rule. NOT a meaning claim; not part of C×R×S._"])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", choices=list(JUDGES), default="wordnet")
    ap.add_argument("--controls", type=int, default=S_CONTROL)
    ap.add_argument("--emit", choices=["real", "scrambled", "random"], help="emit blind LLM items for one lexicon")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    if args.emit:
        items, key = emit_items(args.emit)
        print(json.dumps({"items": items, "key": key}, ensure_ascii=False, indent=2))
        return 0
    res = run(args.judge, n_control=args.controls)
    md = to_markdown(res)
    print(md)
    print("\nJSON:", json.dumps(res, ensure_ascii=False))
    if args.out:
        open(args.out, "w", encoding="utf-8").write(md + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
