#!/usr/bin/env python3
"""(2) Blind bīja↔vṛtti SOUND-matching test — real table vs scramble, at the sound level.

The only live, relabeling-immune claim: "the acoustic root of the āśā-vṛtti is Ka" etc. — i.e. the
bīja sound and the vṛtti (felt propensity) are co-aspects, so a person feeling the *sound* should match
it to its vṛtti above chance, and the REAL pairing-table should fit human sound-feeling better than a
scrambled one. The dependent variable is a MEASURED human (here: LLM-proxy) sound→feeling match, not a
gloss computation — so this escapes the relabeling-invariance wall that sinks the word-level tests.

Judges see a bare sound syllable + K candidate feeling-words; they pick the one the SOUND resonates with,
instructed to ignore any Sanskrit/mantra knowledge. Accuracy is scored against the real table; chance =
1/K. A scrambled table scores at chance by construction, so acc(real) > chance IS acc(real) > scrambled.

PRIMARY THREAT = leakage: an LLM may recall the traditional bīja→vṛtti table and match from memory, not
from sound. Run bija_vrtti_test.py with the leakage probe first; interpret near-ceiling accuracy as
leakage, a modest-above-chance effect as possible genuine iconicity. A clean answer needs naive human
listeners with AUDIO and nonce-sound controls — this LLM run is a cheap first screen only.
"""
from __future__ import annotations
import argparse, json, random as _rnd
import varna_lens as V
import archetype_test as AT

K = 5
BASE = AT.BASE_SEED


def _gloss(k):
    return AT._gloss(V.CONS[k]["leading_vritti"])


def build_items():
    keys = [k for k in V.CONS if V.CONS[k].get("leading_vritti")]
    pool = [(k, _gloss(k)) for k in keys]
    all_gloss = list(dict.fromkeys(g for _, g in pool))
    items, key = [], {}
    for i, (k, g) in enumerate(pool):
        rng = _rnd.Random(BASE + 13 * i)
        distract = [x for x in all_gloss if x != g]
        rng.shuffle(distract)
        opts = distract[:K - 1] + [g]
        rng.shuffle(opts)
        sound = V.CONS[k]["iast"].split()[0].lower()      # bare syllable, e.g. "ka", "ḍa"
        items.append({"id": k, "sound": sound, "options": {str(j): o for j, o in enumerate(opts)}})
        key[k] = opts.index(g)
    return items, key


def _boot_ci(vals, n=10000, seed=BASE):
    if not vals:
        return (0.0, 0.0)
    r = _rnd.Random(seed); m = len(vals); out = []
    for _ in range(n):
        out.append(sum(vals[r.randrange(m)] for _ in range(m)) / m)
    out.sort()
    return out[int(0.025 * n)], out[int(0.975 * n)]


def score(judges, key):
    chance = 1.0 / K
    per_item = []      # mean accuracy across judges, per item
    agree = []         # inter-judge agreement (top pick share), per item
    consensus_hits = 0
    consensus_items = 0
    for iid, ci in key.items():
        picks = [int(j[iid]) for j in judges if iid in j]
        if not picks:
            continue
        per_item.append(sum(1 for p in picks if p == ci) / len(picks))
        from collections import Counter
        c = Counter(picks); top, n_top = c.most_common(1)[0]
        agree.append(n_top / len(picks))
        if n_top >= 2:                                     # judges formed a consensus on this sound
            consensus_items += 1
            if top == ci:
                consensus_hits += 1
    acc = sum(per_item) / len(per_item) if per_item else 0.0
    lo, hi = _boot_ci(per_item)
    verdict = "SOUND_VRTTI_MATCH" if lo > chance else "NO_SOUND_VRTTI_MATCH"
    if verdict == "SOUND_VRTTI_MATCH" and acc > 0.80:
        verdict += " (WARNING: near-ceiling — likely memorized-table leakage, not sound-feeling)"
    return {"n_items": len(per_item), "n_judges": len(judges), "K": K, "chance": chance,
            "acc_real": acc, "acc_ci95": [lo, hi], "verdict": verdict,
            "mean_interjudge_agreement": sum(agree) / len(agree) if agree else 0.0,
            "consensus_matches_real": (consensus_hits / consensus_items) if consensus_items else None,
            "consensus_items": consensus_items}


def to_markdown(res):
    return "\n".join([
        f"# (2) bīja↔vṛtti SOUND-matching — real table vs scramble", "",
        f"- N = {res['n_items']} bīja sounds · {res['n_judges']} blind judges · K = {res['K']} · chance = {res['chance']:.3f}",
        f"- **accuracy(real table) = {res['acc_real']:.3f}**  (95% CI {res['acc_ci95'][0]:.3f}–{res['acc_ci95'][1]:.3f})",
        f"- inter-judge agreement = {res['mean_interjudge_agreement']:.3f}  (do judges feel the same sound the same way?)",
        f"- where judges formed a consensus ({res['consensus_items']} sounds), it matched the real table "
        f"{res['consensus_matches_real']:.3f} of the time" if res['consensus_matches_real'] is not None else "",
        "", f"## VERDICT: **{res['verdict']}**", "",
        "_Escapes relabeling (target = measured sound-feeling, not a gloss). PRIMARY THREAT = leakage:_",
        "_an LLM may recall the traditional table. Near-ceiling accuracy = leakage; a clean answer needs_",
        "_naive human listeners with AUDIO + nonce controls. Not a meaning claim; not part of C×R×S._"])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit", action="store_true")
    ap.add_argument("--score"); ap.add_argument("--keyfile")
    a = ap.parse_args(argv)
    if a.emit:
        items, key = build_items()
        print(json.dumps({"items": items, "key": key}, ensure_ascii=False, indent=1)); return 0
    if a.score:
        judges = json.load(open(a.score))
        key = json.load(open(a.keyfile))["key"] if a.keyfile else build_items()[1]
        res = score(judges, key)
        print(to_markdown(res)); print("\nJSON:", json.dumps(res, ensure_ascii=False)); return 0
    ap.error("use --emit or --score")


if __name__ == "__main__":
    raise SystemExit(main())
