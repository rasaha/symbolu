#!/usr/bin/env python3
"""Non-lexical UTILITY falsification: real lexicon vs scrambled lexicon, same word/rule/template, blind judge.

Pre-registered in PREREG_UTILITY_SIGNAL.md. Tests whether the REAL sound→propensity attachment yields more
useful contemplative / creative / naming / affective artifacts than a SCRAMBLED one. The scramble permutes
the (worldly, spiritual-counter) PAIRS as units among consonants (and vowel essences among vowels), so it
preserves antonym pairing, +/− structure, the gloss multiset, and output length — real can only win on the
specific attachment, not on formatting or the lexicon's general richness.

Judges:  --judge surface  (deterministic CPU; PARITY/null check — expected Δ≈0)
         --judge random   (null; no systematic preference)
         --judge llm      (confirmatory; blind sub-agents / API — emit pairs, score externally)
"""
from __future__ import annotations

import argparse
import json
import random as _rnd
import re

import varna_lens as V
import wordlist_utility

S_SCRAMBLE = 20
N_BOOT = 10000
BASE_SEED = 20240624
MIN_EFFECT = 0.30          # practical threshold on the 1–5 utility scale
DIMS = ["coherence", "depth", "usefulness", "specificity", "non_generic", "fit"]


# ----- segmentation (with fallback) --------------------------------------------------------------
_KEYS = {}
def resolve_keys(row):
    """Phoneme (type,key) per sound. Cached — independent of the lexicon map (real vs scrambled)."""
    ck = (row["word"], row["pronunciation"])
    if ck in _KEYS:
        return _KEYS[ck]
    pron = row["pronunciation"]
    if pron == "roman":
        ph, _ = V.phonemes_roman(row["word"])
    elif pron == "g2p":
        ph, _ = V.phonemes_cmudict(row["word"])
        if not ph:
            ph, _ = V.phonemes_roman(row["word"])      # fallback: read literally
    else:
        ph, _ = V.phonemes_explicit(pron)
    _KEYS[ck] = [(t, k) for (t, k, _s) in ph]
    return _KEYS[ck]


# ----- lexicon maps (real + pair-preserving scramble) --------------------------------------------
def _gloss(v):
    """Readable English gloss: the parenthetical if present, else the term itself."""
    m = re.search(r"\(([^)]*)\)", v)
    return (m.group(1) if m else v).strip()


def real_maps():
    cons = {k: (_gloss(d["leading_vritti"]), _gloss(d["counter_vritti"])) for k, d in V.CONS.items()}
    vow = {k: _gloss(d["liberating_state"]) for k, d in V.VOW.items()}
    return cons, vow


def scrambled_maps(seed):
    """Permute (worldly,counter) PAIRS among consonant keys, and vowel essences among vowel keys."""
    cons, vow = real_maps()
    r = _rnd.Random(seed)
    ck, cv = list(cons), list(cons.values()); r.shuffle(cv)
    vk, vv = list(vow), list(vow.values()); r.shuffle(vv)
    return dict(zip(ck, cv)), dict(zip(vk, vv))


# ----- reading (same polarity rule as varna_lens.read_op) ----------------------------------------
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


# ----- artifact rendering (identical templates for real & scrambled) -----------------------------
def _parts(elems, summary):
    worldlies = [e["worldly"] for e in elems] or ["stillness"]
    arcs = [(e["worldly"], e["counter"]) for e in elems if e["kind"] == "C" and e["sign"] == "−" and e["counter"]]
    affirmed = [e["worldly"] for e in elems if e["sign"] == "+"]
    summ = summary["worldly"] if summary and summary.get("worldly") else worldlies[-1]
    return worldlies, arcs, affirmed, summ


def render(word, use_case, elems, summary):
    w, arcs, aff, summ = _parts(elems, summary)
    mid = w[len(w) // 2]
    if use_case == "journaling":
        third = (f"If {arcs[-1][0]} is ready to ease toward {arcs[-1][1]}, what is one small step?"
                 if arcs else f"What would it mean to hold {w[-1]} more lightly?")
        return (f"A symbolic reading of \"{word}\" — as a reflection prompt, not a claim about the word.\n"
                f"Images, in order: {', '.join(w)}"
                f"{(' (with ' + ', '.join(f'{a} easing toward {b}' for a, b in arcs) + ')') if arcs else ''}.\n"
                f"This reading invites three reflections:\n"
                f"1) Where does {w[0]} show up for you lately?\n"
                f"2) Notice where {mid} feels active — is it serving you?\n"
                f"3) {third}\n"
                f"Journaling prompt: write for five minutes on the movement from {w[0]} to {summ}.")
    if use_case == "naming":
        return (f"A symbolic mood-palette for the name \"{word}\" — themes it evokes, not a hidden meaning.\n"
                f"Themes: {', '.join(dict.fromkeys(w))}.\n"
                f"Strengths: a palette that can lean toward {', '.join(dict.fromkeys(b for _, b in arcs)) or summ}.\n"
                f"Cautions: watch that {', '.join(dict.fromkeys(a for a, _ in arcs)) or w[0]} doesn't read as off-tone.\n"
                f"Brand positioning: as a symbolic prompt, this name tends toward a movement from {w[0]} to {summ}.")
    if use_case == "creative":
        return (f"A creative seed from \"{word}\" — imagery to riff on, not a meaning.\n"
                f"Imagery: {', '.join(w)}.\n"
                f"Tension: {(aff[0] if aff else w[0])} pulling against {(arcs[0][0] if arcs else w[-1])}.\n"
                f"Transformation arc: from {w[0]} toward {(arcs[-1][1] if arcs else summ)}.")
    # affective
    return (f"An affective reading of \"{word}\" — a possible felt sense, not a claim.\n"
            f"Emotional tone: {', '.join(w[:3])}.\n"
            f"Possible felt sense: a movement from {w[0]}{(' easing toward ' + arcs[0][1]) if arcs else ''}.\n"
            f"Balancing question: when {w[0]} is loud, what helps you return to {(arcs[-1][1] if arcs else summ)}?")


def artifact(row, cons_map, vow_map):
    elems, summary = reading(resolve_keys(row), cons_map, vow_map)
    return render(row["word"], row["use_case"], elems, summary)


# ----- judges --------------------------------------------------------------------------------------
def judge_surface(text, use_case, seed):
    """Deterministic surface-feature proxy (parity/null check) — depends only on measurable text stats,
    so real and scrambled (identical template, permuted glosses) score ≈ equally. Returns 1–5."""
    toks = re.findall(r"[a-zA-Z]+", text.lower())
    if not toks:
        return 1.0
    ttr = len(set(toks)) / len(toks)                       # lexical variety
    rare = sum(1 for t in toks if len(t) > 6) / len(toks)  # specificity proxy
    return 1.0 + 4.0 * (0.5 * ttr + 0.5 * rare)


def judge_random(text, use_case, seed):
    # NULL judge: ignores content, depends only on the (deterministic) per-item seed — so `--judge random`
    # is reproducible as the pre-registration states (Python's hash() is per-process randomized; avoid it).
    return 1.0 + 4.0 * _rnd.Random(seed).random()


JUDGES = {"surface": judge_surface, "random": judge_random}


# ----- run + metrics -------------------------------------------------------------------------------
def _boot_ci(vals, n=N_BOOT, seed=BASE_SEED):
    r = _rnd.Random(seed); m = len(vals); out = []
    for _ in range(n):
        out.append(sum(vals[r.randrange(m)] for _ in range(m)) / m)
    out.sort()
    return out[int(0.025 * n)], out[int(0.975 * n)]


def run(judge_name, rows=None, n_scramble=S_SCRAMBLE):
    rows = rows or wordlist_utility.load()
    judge = JUDGES[judge_name]
    cons, vow = real_maps()

    real_score, scr_score, pref = [], [], []
    for i, r in enumerate(rows):
        a_real = artifact(r, cons, vow)
        sr = judge(a_real, r["use_case"], BASE_SEED * 2 + i)
        ss = []
        for s in range(n_scramble):
            cm, vm = scrambled_maps(BASE_SEED + 101 * s)
            ss.append(judge(artifact(r, cm, vm), r["use_case"], BASE_SEED * 5 + i * 97 + s))
        real_score.append(sr)
        scr_score.append(sum(ss) / len(ss))
        pref.append(1.0 if sr > sum(ss) / len(ss) else (0.5 if sr == sum(ss) / len(ss) else 0.0))

    delta = [real_score[i] - scr_score[i] for i in range(len(rows))]
    d = sum(delta) / len(delta)
    d_lo, d_hi = _boot_ci(delta)
    p = sum(pref) / len(pref)
    p_lo, p_hi = _boot_ci(pref)

    if d_lo > 0 and d >= MIN_EFFECT:
        verdict = "UTILITY_SIGNAL_DETECTED"
    elif d_lo <= 0 <= d_hi:
        verdict = "NO_UTILITY_SIGNAL"
    else:
        verdict = "INCONCLUSIVE"

    def by(key):
        groups = {}
        for i, r in enumerate(rows):
            groups.setdefault(r[key], []).append(i)
        return {g: {"n": len(ix), "delta": sum(delta[j] for j in ix) / len(ix)} for g, ix in groups.items()}

    return {"judge": judge_name, "n": len(rows), "scrambles": n_scramble, "min_effect": MIN_EFFECT,
            "acc_real": sum(real_score) / len(real_score), "acc_scrambled": sum(scr_score) / len(scr_score),
            "delta": d, "delta_ci95": [d_lo, d_hi], "pref_real": p, "pref_ci95": [p_lo, p_hi],
            "verdict": verdict, "by_use_case": by("use_case"), "by_category": by("category")}


# ----- LLM-judge support: emit blind pairs, score from external picks ------------------------------
def emit_pairs(rows=None, scramble_seeds=(0,)):
    """Blind A/B pairs for sub-agent / API scoring. real is randomly assigned to A or B per item; the
    'real_is' key is the held-out answer (NOT shown to the judge)."""
    rows = rows or wordlist_utility.load()
    cons, vow = real_maps()
    items, key = [], {}
    rr = _rnd.Random(BASE_SEED)
    for s in scramble_seeds:
        cm, vm = scrambled_maps(BASE_SEED + 101 * s)
        for i, r in enumerate(rows):
            a_real = artifact(r, cons, vow)
            a_scr = artifact(r, cm, vm)
            iid = f"s{s}:{i}"
            if rr.random() < 0.5:
                A, B, real_is = a_real, a_scr, "A"
            else:
                A, B, real_is = a_scr, a_real, "B"
            items.append({"id": iid, "use_case": r["use_case"], "A": A, "B": B})
            key[iid] = real_is
    return items, key


def score_pairs(picks, key):
    """picks: {id: {"A": util1to5, "B": util1to5, "prefer": "A"|"B"|"tie"}}. Returns metrics."""
    delta, pref = [], []
    for iid, ri in key.items():
        if iid not in picks:
            continue
        pk = picks[iid]
        rs = pk[ri]; ss = pk["A" if ri == "B" else "B"]
        delta.append(rs - ss)
        pr = pk.get("prefer", "tie")
        pref.append(1.0 if pr == ri else (0.5 if pr == "tie" else 0.0))
    if not delta:
        return {"verdict": "INCONCLUSIVE", "n": 0}
    d = sum(delta) / len(delta); d_lo, d_hi = _boot_ci(delta)
    p = sum(pref) / len(pref); p_lo, p_hi = _boot_ci(pref)
    verdict = ("UTILITY_SIGNAL_DETECTED" if (d_lo > 0 and d >= MIN_EFFECT)
               else "NO_UTILITY_SIGNAL" if d_lo <= 0 <= d_hi else "INCONCLUSIVE")
    return {"judge": "llm", "n": len(delta), "delta": d, "delta_ci95": [d_lo, d_hi],
            "pref_real": p, "pref_ci95": [p_lo, p_hi], "verdict": verdict}


def to_markdown(res):
    L = [f"# Results — non-lexical utility test (judge = {res['judge']})", "",
         f"- N = {res['n']}  ·  scrambles = {res.get('scrambles','-')}  ·  MIN_EFFECT = {res['min_effect']} (1–5 scale)",
         f"- utility(real)      = {res['acc_real']:.3f}",
         f"- utility(scrambled) = {res['acc_scrambled']:.3f}   (avg over {res.get('scrambles','-')} scrambles)",
         f"- **Δ = real − scrambled = {res['delta']:+.3f}**  (95% CI {res['delta_ci95'][0]:+.3f} … {res['delta_ci95'][1]:+.3f})",
         f"- real-preferred rate = {res['pref_real']:.3f}  (95% CI {res['pref_ci95'][0]:.3f}–{res['pref_ci95'][1]:.3f})",
         "", f"## VERDICT: **{res['verdict']}**", "",
         "| use_case | n | Δ |", "|---|---|---|"]
    for g, d in sorted(res.get("by_use_case", {}).items()):
        L.append(f"| {g} | {d['n']} | {d['delta']:+.3f} |")
    L += ["", "| category | n | Δ |", "|---|---|---|"]
    for g, d in sorted(res.get("by_category", {}).items()):
        L.append(f"| {g} | {d['n']} | {d['delta']:+.3f} |")
    L += ["", "_Pre-registered (PREREG_UTILITY_SIGNAL.md). Verdict computed by rule. NOT a meaning claim; "
          "not part of C×R×S._"]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", choices=list(JUDGES), default="surface")
    ap.add_argument("--scrambles", type=int, default=S_SCRAMBLE)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    res = run(args.judge, n_scramble=args.scrambles)
    md = to_markdown(res)
    print(md)
    print("\nJSON:", json.dumps({k: v for k, v in res.items() if k not in ("by_use_case", "by_category")}))
    if args.out:
        open(args.out, "w", encoding="utf-8").write(md + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
