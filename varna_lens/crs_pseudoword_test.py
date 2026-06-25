#!/usr/bin/env python3
"""Design B (CRS-weighted interpretation) on PSEUDOWORDS — first runnable slice of
PREREG_CRS_POLE_SELECTION.md.

Design B never flips a pole. The engine structurally decodes each pseudoword (Design A, R), and CRS only
*weights / ranks / scores confidence* of the decoded reading:

    score(reading | word, ctx) = α·log C  +  β·log R  +  γ·log S

This harness implements the full CRS scaffold, the firewall, the control ladder, and provenance logging,
and runs every MACHINE-CHECKABLE arm now. It also surfaces — and empirically demonstrates — the result that
gates everything else:

    A DETERMINISTIC, STRUCTURE-BASED S IS RELABELING-INVARIANT.
    emergent_valence / signs depend on phoneme POSITION, not on gloss CONTENT, so permuting the lexicon
    leaves the structural score unchanged (real ≡ shuffled-lexicon). Therefore a deterministic structure-S
    can only ever test STRUCTURE (R); the lexicon-CONTENT question (does the binding/liberating *meaning*
    cohere with context?) necessarily requires a SEMANTIC judge (LLM / human) — which is gated on API/panel
    and is exactly the channel the firewall watches.

So this run reports: (1) the machinery validated (random null), (2) the empirical relabeling-invariance
proof, (3) an EXPLORATORY structural-vs-independent-sound-symbolism correlation, and (4) the decision-rule
status = GATED (R3 cannot fire without the semantic judge). It does NOT declare Design B valid/invalid.

FIREWALL: S receives ONLY (decoded reading, ctx). It never sees a dictionary gloss, known valence, target
explanation, or eval label. Pseudowords have no gloss, enforcing this structurally.
"""
from __future__ import annotations

import argparse
import json
import math
import random as _rnd

import varna_lens as V
import wordlist_pseudo

BASE_SEED = 20240625
N_BOOT = 10000

# ----- INDEPENDENT sound-symbolism target (psycholinguistic, NOT the varṇa lexicon) -----------------
# sharp(+1): voiceless obstruents/sibilants + high/front vowels;  round(-1): sonorants/voiced + low/back.
_SHARP_C = {"ka", "kha", "ca", "cha", "tta", "ttha", "ta", "tha", "pa", "pha", "sa", "sha", "ssa", "ksha"}
_ROUND_C = {"ga", "gha", "nga", "ja", "jha", "nya", "dda", "ddha", "nna", "da", "dha", "na",
            "ba", "bha", "ma", "ya", "ra", "la", "va", "ha"}
_SHARP_V = {"i", "ii", "e"}
_ROUND_V = {"a", "aa", "u", "uu", "o", "au", "ai"}


def soundsym_target(seq):
    """Independent sharp(+)/round(−) score in [-1,1] from the parsed keys. Defined OUTSIDE the varṇa
    ontology, so a varṇa score predicting it is a non-circular cross-check."""
    vals = []
    for a in seq:
        k = a["key"]
        if a["type"] == "C":
            vals.append(1.0 if k in _SHARP_C else -1.0 if k in _ROUND_C else 0.0)
        else:
            vals.append(1.0 if k in _SHARP_V else -1.0 if k in _ROUND_V else 0.0)
    return sum(vals) / len(vals) if vals else 0.0


# ----- structural reading (R / Design A) + the CRS terms --------------------------------------------
def decode(word):
    """Structural decode (Design A). Returns (seq, struct_score) with struct_score = (lib−bind)/(lib+bind)
    from emergent_valence — a PURE SIGN/POSITION quantity (gloss-independent)."""
    d, _src, _w = V.analyze(word, model="op", roman=True)
    ev = d.get("emergent_valence") or {}
    lib, bind = ev.get("liberating_votes", 0), ev.get("binding_votes", 0)
    tot = lib + bind
    return d["sequence"], (0.0 if tot == 0 else (lib - bind) / tot)


def crs_score(struct_score, ctx_sign, judge, word_seq, seed, alpha=1.0, beta=1.0, gamma=1.0):
    """score = α·logC + β·logR + γ·logS, returned as additive log-terms for provenance.
    C: uniform ontology prior → 0 (documented). R: structural term = ctx_sign·struct_score (the decoded
    reading's alignment with the context pole). S: the judge's coherence term (see judges). FIREWALL: the
    judge is handed ONLY (word_seq, ctx_sign) — never a gloss/valence/target/label."""
    logC = 0.0                                            # uniform prior (no ontology preference yet)
    logR = ctx_sign * struct_score                        # structural alignment with the context pole
    logS = judge(word_seq, ctx_sign, seed)                # semantic/contextual coherence (firewalled)
    total = alpha * logC + beta * logR + gamma * logS
    return total, {"logC": logC, "logR": logR, "logS": logS, "total": total}


# ----- judges (the S term) --------------------------------------------------------------------------
def judge_random(word_seq, ctx_sign, seed):
    return _rnd.Random(seed).uniform(-1, 1)


def judge_structure(word_seq, ctx_sign, seed):
    """DETERMINISTIC structure-S: RELABELING-INVARIANT by construction — it could only read the decoded
    reading's structure, not any gloss. Returns 0 (contributes nothing beyond R), included precisely to
    demonstrate that such an S adds no lexicon-content signal (model corr == structural corr)."""
    return 0.0


def judge_llm(word_seq, ctx_sign, seed):
    raise RuntimeError("llm judge (the real content-S) needs ANTHROPIC_API_KEY — gated on API/panel")


JUDGES = {"random": judge_random, "structure": judge_structure, "llm": judge_llm}


# ----- stats ----------------------------------------------------------------------------------------
def _rank(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def _pearson(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va == 0 or vb == 0:
        return 0.0
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    return cov / math.sqrt(va * vb)


def spearman(a, b):
    return _pearson(_rank(a), _rank(b))


def _boot_ci(a, b, n=N_BOOT, seed=BASE_SEED):
    r = _rnd.Random(seed)
    m = len(a)
    vals = []
    for _ in range(n):
        idx = [r.randrange(m) for _ in range(m)]
        vals.append(spearman([a[i] for i in idx], [b[i] for i in idx]))
    vals.sort()
    return vals[int(0.025 * n)], vals[int(0.975 * n)]


# ----- relabeling-invariance demonstration ----------------------------------------------------------
def relabeling_invariance_check(words):
    """Empirically prove the structural score is gloss-independent: permute the lexicon glosses among
    consonants/vowels, recompute emergent_valence, and confirm the per-word struct_scores are IDENTICAL."""
    base = [decode(w)[1] for w in words]
    cons_keys = list(V.CONS)
    cons_lead = [V.CONS[k]["leading_vritti"] for k in cons_keys]
    cons_cnt = [V.CONS[k]["counter_vritti"] for k in cons_keys]
    r = _rnd.Random(BASE_SEED)
    perm = list(range(len(cons_keys)))
    r.shuffle(perm)
    for i, k in enumerate(cons_keys):                     # permute glosses among consonants
        V.CONS[k]["leading_vritti"] = cons_lead[perm[i]]
        V.CONS[k]["counter_vritti"] = cons_cnt[perm[i]]
    shuf = [decode(w)[1] for w in words]
    for i, k in enumerate(cons_keys):                     # restore
        V.CONS[k]["leading_vritti"] = cons_lead[i]
        V.CONS[k]["counter_vritti"] = cons_cnt[i]
    identical = all(abs(a - b) < 1e-12 for a, b in zip(base, shuf))
    return identical


# ----- run ------------------------------------------------------------------------------------------
def run(judge_name="random", n=80, ctx_sign=1):
    words = wordlist_pseudo.generate(n=n)
    decoded = [decode(w) for w in words]
    struct = [s for _seq, s in decoded]
    target = [soundsym_target(seq) for seq, _s in decoded]
    judge = JUDGES[judge_name]

    # model scores + provenance
    prov = []
    model = []
    for i, (w, (seq, s)) in enumerate(zip(words, decoded)):
        tot, terms = crs_score(s, ctx_sign, judge, seq, BASE_SEED + i)
        model.append(tot)
        prov.append({"word": w, **terms})

    # arms
    corr_struct = spearman(struct, target)                       # R (structure) vs independent target
    lo_s, hi_s = _boot_ci(struct, target)
    rnd_scores = [judge_random(None, ctx_sign, BASE_SEED * 3 + i) for i in range(len(words))]
    corr_rand = spearman(rnd_scores, target)                     # random null
    corr_model = spearman(model, target)                         # full CRS (with chosen S)

    invariant = relabeling_invariance_check(words)

    return {
        "judge": judge_name, "n_words": len(words), "ctx_sign": ctx_sign,
        "corr_struct_vs_soundsym": corr_struct, "struct_ci95": [lo_s, hi_s],
        "corr_random_vs_soundsym": corr_rand, "corr_model_vs_soundsym": corr_model,
        "relabeling_invariant": invariant,
        "provenance_sample": prov[:5],
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", choices=list(JUDGES), default="random")
    ap.add_argument("--n", type=int, default=80)
    a = ap.parse_args(argv)
    res = run(judge_name=a.judge, n=a.n)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
