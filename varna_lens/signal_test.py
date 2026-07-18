#!/usr/bin/env python3
"""Blind acoustic-root meaning-recovery test with a scrambled-lexicon control.

Pre-registered in PREREG_ACOUSTIC_SIGNAL.md. Removes the human from the loop: the lens essence is computed
MECHANICALLY, a BLIND judge (never sees the word/sounds) recovers the meaning by forced choice, and the
whole pipeline is re-run on a SCRAMBLED lexicon. If the acoustic root is a real latent signal, real ≫
scrambled. Verdict is computed by the rule in the prereg, not by hand.

Judges:  --judge random   (NULL baseline; must land at chance)
         --judge wordnet  (deterministic CPU semantic-similarity; reproducible, lower power)
         --judge llm       (confirmatory; Claude API, blind — run where API/pod is available)
"""
from __future__ import annotations

import argparse
import json
import random as _rnd
import re
from collections import Counter

import varna_lens as V
import wordlist_signal

K = 5                 # candidates per forced-choice item (chance = 1/K)
N_SCRAMBLE = 20       # seeded scrambled lexicons, averaged
N_BOOT = 10000        # bootstrap resamples
BASE_SEED = 20240624

_STOP = {"a", "an", "the", "of", "to", "in", "and", "or", "without", "self", "for", "your", "own",
         "good", "into", "out", "up", "no", "non"}


# ----- mechanical essence ------------------------------------------------------------------------
def phoneme_keys(row):
    """(type,key) per sound, by the row's native pronunciation. No human, no signs, no ⤳ overlay."""
    pron = row["pron"]
    if pron == "roman":
        ph, _ = V.phonemes_roman(row["word"])
    elif pron == "g2p":
        ph, _ = V.phonemes_cmudict(row["word"])
    else:
        ph, _ = V.phonemes_explicit(pron)
    return [(t, k) for (t, k, _s) in ph]


_KEYS_CACHE = None
def keys_for(rows):
    """Precompute phoneme keys once per word (independent of the lexicon map)."""
    global _KEYS_CACHE
    if _KEYS_CACHE is None:
        _KEYS_CACHE = [phoneme_keys(r) for r in rows]
    return _KEYS_CACHE


def real_maps():
    """key -> worldly short-gloss.  consonant = leading_vritti (binding);  vowel = liberating_state (worldly)."""
    cons = {k: V._short(d["leading_vritti"]) for k, d in V.CONS.items()}
    vow = {k: V._short(d["liberating_state"]) for k, d in V.VOW.items()}
    return cons, vow


def scrambled_maps(seed):
    """Permute the worldly glosses among keys (consonants among consonants, vowels among vowels)."""
    cons, vow = real_maps()
    r = _rnd.Random(seed)
    ck, cv = list(cons), list(cons.values()); r.shuffle(cv)
    vk, vv = list(vow), list(vow.values()); r.shuffle(vv)
    return dict(zip(ck, cv)), dict(zip(vk, vv))


def essence(keys, cons_map, vow_map):
    out = []
    for t, k in keys:
        g = cons_map.get(k) if t == "C" else vow_map.get(k)
        if g:
            out.append(g)
    return ", ".join(out)


# ----- forced-choice item construction (deterministic) -------------------------------------------
def build_items(rows):
    """For each word: (true_gloss, [K candidate glosses incl. true], correct_index). Distractors are
    valence-matched, never equal to the true gloss, seeded per word."""
    by_val = {}
    for r in rows:
        by_val.setdefault(r["valence"], []).append(r["gloss"])
    all_gloss = [r["gloss"] for r in rows]
    items = []
    for i, r in enumerate(rows):
        rng = _rnd.Random(BASE_SEED + i)
        true = r["gloss"]
        pool = [g for g in by_val.get(r["valence"], []) if g != true]
        pool = list(dict.fromkeys(pool))                       # unique, keep order
        if len(pool) < K - 1:                                  # backfill from all glosses if class small
            extra = [g for g in all_gloss if g != true and g not in pool]
            rng.shuffle(extra); pool += extra
        rng.shuffle(pool)
        cands = pool[:K - 1] + [true]
        rng.shuffle(cands)
        items.append((true, cands, cands.index(true)))
    return items


# ----- judges ------------------------------------------------------------------------------------
def _words(text):
    return [w for w in re.findall(r"[a-zA-Z]+", text.lower()) if w not in _STOP and len(w) > 2]


def judge_random(essence_str, cands, seed):
    return _rnd.Random(seed).randrange(len(cands))


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


def judge_wordnet(essence_str, cands, seed):
    """Pick the candidate whose content words are most WordNet-similar to the essence's content words."""
    wn = _wordnet()
    ew = _words(essence_str)
    e_syn = [s for w in ew for s in wn.synsets(w)]
    best, best_i = -1.0, 0
    for i, c in enumerate(cands):
        score, n = 0.0, 0
        for cwword in _words(c) or [c.lower()]:
            csyn = wn.synsets(cwword)
            if not csyn or not e_syn:
                n += 1; continue
            sim = max((a.wup_similarity(b) or 0.0) for a in csyn for b in e_syn)
            score += sim; n += 1
        score = score / n if n else 0.0
        if score > best:
            best, best_i = score, i
    return best_i


def judge_llm(essence_str, cands, seed):
    """Blind Claude judge (confirmatory). Needs ANTHROPIC_API_KEY; respects HTTPS_PROXY + proxy CA."""
    import os, ssl, urllib.request
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("llm judge needs ANTHROPIC_API_KEY (run on a pod/with API access)")
    listing = "\n".join(f"{i}. {c}" for i, c in enumerate(cands))
    prompt = ("You are given an abstract 'essence' — an ordered list of psychological propensities — and a "
              "numbered list of candidate word-meanings. Pick the single meaning the essence best fits. "
              "Answer with ONLY the number.\n\nESSENCE: " + essence_str + "\n\nCANDIDATES:\n" + listing +
              "\n\nNumber:")
    body = json.dumps({"model": "claude-haiku-4-5-20251001", "max_tokens": 8,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    ctx = ssl.create_default_context()
    ca = "/root/.ccr/ca-bundle.crt"
    if os.path.exists(ca):
        ctx.load_verify_locations(ca)
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body,
                                 headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                          "content-type": "application/json"})
    with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
        out = json.loads(resp.read())
    txt = out["content"][0]["text"]
    m = re.search(r"\d+", txt)
    idx = int(m.group()) if m else 0
    return idx if 0 <= idx < len(cands) else 0


JUDGES = {"random": judge_random, "wordnet": judge_wordnet, "llm": judge_llm}


# ----- run + metrics -------------------------------------------------------------------------------
def _acc_vector(rows, items, judge, cons_map, vow_map, shuffle_order=False, tag=""):
    """Per-word correctness (0/1) under one lexicon map."""
    correct = []
    all_keys = keys_for(rows)
    for i, (r, (true, cands, ci)) in enumerate(zip(rows, items)):
        keys = all_keys[i]
        if shuffle_order:
            keys = list(keys); _rnd.Random(BASE_SEED * 7 + i).shuffle(keys)
        ess = essence(keys, cons_map, vow_map)
        pick = judge(ess, cands, BASE_SEED * 3 + i) if ess else judge_random(ess, cands, BASE_SEED * 3 + i)
        correct.append(1 if pick == ci else 0)
    return correct


def _boot_ci(diffs, n=N_BOOT, seed=BASE_SEED):
    r = _rnd.Random(seed)
    m = len(diffs)
    means = []
    for _ in range(n):
        s = sum(diffs[r.randrange(m)] for _ in range(m)) / m
        means.append(s)
    means.sort()
    return means[int(0.025 * n)], means[int(0.975 * n)]


def run(judge_name, rows=None):
    rows = rows or wordlist_signal.load()
    items = build_items(rows)
    judge = JUDGES[judge_name]
    cons, vow = real_maps()

    real = _acc_vector(rows, items, judge, cons, vow)
    shuf = _acc_vector(rows, items, judge, cons, vow, shuffle_order=True)

    # scrambled: per-word mean correctness over N_SCRAMBLE seeded lexicons
    scr_word = [0.0] * len(rows)
    for s in range(N_SCRAMBLE):
        cm, vm = scrambled_maps(BASE_SEED + 101 * s)
        cv = _acc_vector(rows, items, judge, cm, vm)
        for j, c in enumerate(cv):
            scr_word[j] += c / N_SCRAMBLE

    acc_real = sum(real) / len(real)
    acc_scr = sum(scr_word) / len(scr_word)
    acc_shuf = sum(shuf) / len(shuf)
    chance = 1.0 / K

    delta = [real[j] - scr_word[j] for j in range(len(rows))]
    d_lo, d_hi = _boot_ci(delta)
    r_lo, r_hi = _boot_ci([float(x) for x in real])

    if d_lo > 0 and r_lo > chance:
        verdict = "SIGNAL_DETECTED"
    elif d_lo <= 0 <= d_hi:
        verdict = "NO_SIGNAL"
    else:
        verdict = "INCONCLUSIVE"

    # per-language + Sanskrit-only Δ
    langs = {}
    for j, r in enumerate(rows):
        langs.setdefault(r["lang"], []).append(j)
    per_lang = {lg: {"n": len(idx), "acc_real": sum(real[j] for j in idx) / len(idx),
                     "acc_scr": sum(scr_word[j] for j in idx) / len(idx)} for lg, idx in langs.items()}

    return {
        "judge": judge_name, "n_words": len(rows), "K": K, "chance": chance,
        "acc_real": acc_real, "acc_scrambled": acc_scr, "acc_order_shuffled": acc_shuf,
        "delta": acc_real - acc_scr, "delta_ci95": [d_lo, d_hi], "acc_real_ci95": [r_lo, r_hi],
        "verdict": verdict, "per_lang": per_lang,
    }


def to_markdown(res):
    L = [f"# Results — acoustic-signal test (judge = {res['judge']})", "",
         f"- words N = {res['n_words']}  ·  K = {res['K']}  ·  chance = {res['chance']:.3f}",
         f"- **accuracy(real)      = {res['acc_real']:.3f}**  (95% CI {res['acc_real_ci95'][0]:.3f}–{res['acc_real_ci95'][1]:.3f})",
         f"- accuracy(scrambled) = {res['acc_scrambled']:.3f}   (avg over {N_SCRAMBLE} scrambles)",
         f"- accuracy(order-shuffled) = {res['acc_order_shuffled']:.3f}",
         f"- **Δ = real − scrambled = {res['delta']:+.3f}**  (95% CI {res['delta_ci95'][0]:+.3f} … {res['delta_ci95'][1]:+.3f})",
         "", f"## VERDICT: **{res['verdict']}**", "",
         "| lang | n | acc(real) | acc(scrambled) |", "|---|---|---|---|"]
    for lg, d in sorted(res["per_lang"].items()):
        L.append(f"| {lg} | {d['n']} | {d['acc_real']:.3f} | {d['acc_scr']:.3f} |")
    L += ["", "_Pre-registered (PREREG_ACOUSTIC_SIGNAL.md). Verdict computed by rule, not by hand. "
          "Interpretive lens — not part of C×R×S._"]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", choices=list(JUDGES), default="wordnet")
    ap.add_argument("--out", default=None, help="write results markdown to this path")
    args = ap.parse_args(argv)
    res = run(args.judge)
    md = to_markdown(res)
    print(md)
    print("\nJSON:", json.dumps({k: v for k, v in res.items() if k != "per_lang"}, ensure_ascii=False))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(md + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
