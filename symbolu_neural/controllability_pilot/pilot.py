"""Controllability pilot orchestrator.

Framing (frozen): Symbol-U = deterministic open-loop feedforward conditioning code.
Question: can it steer generation along intended SEMANTIC axes (calm/active/heavy)
better than matched controls?

Arms:
  base      — unconditional generator (reference; "did output change?" baseline)
  symbolu   — conditional generator, code = Symbol-U axis centroid
  random    — conditional generator, code = fixed random per-axis vector
  shuffled  — conditional generator, Symbol-U codes mapped to wrong axes
  sentiment — conditional generator, code = known axis-keyword centroid
  relabel   — conditional generator, Symbol-U codes with dims permuted
  prompt    — BASE generator, but the axis word is prepended to the prompt (NL prompting)

Each conditional arm trains its own small LM with that arm's codes (each scheme
gets its best shot), then generates for every (target axis × prompt × seed).
Evaluation is offline + PROXY-ONLY (lexicon scorer + BoW classifier).
"""
from __future__ import annotations

import argparse
import json
from typing import Dict, List

import numpy as np

from .data import AXES, make_corpus, prompts
from .codes import build_all
from .generator import Vocab, train_model, generate, perplexity
from .evaluator import LexiconScorer, ProxyClassifier, unigram_js, repetition_rate

CONDITIONAL_ARMS = ["symbolu", "random", "shuffled", "sentiment", "relabel"]


def _split(corpus, frac=0.7, seed=0):
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(corpus))
    k = int(len(corpus) * frac)
    tr = [corpus[i] for i in idx[:k]]
    te = [corpus[i] for i in idx[k:]]
    return tr, te


def run(per_axis=60, u_backend="pse_meaning", steps=400, n_seeds=4,
        seed=0, max_len=12, temp=0.8) -> dict:
    corpus = make_corpus(per_axis=per_axis, seed=seed)
    train_c, test_c = _split(corpus, seed=seed)

    # shared vocab (axis words also added so NL-prompt tokens exist)
    vocab = Vocab([t for t, _ in corpus], extra=AXES + prompts())

    # proxy classifier trained on held-out split
    clf = ProxyClassifier([w for t, _ in corpus for w in t.split()] + AXES)
    clf.fit([t for t, _ in test_c], [a for _, a in test_c])
    lex = LexiconScorer()

    codes = build_all(train_c, u_backend=u_backend, seed=seed)

    # base (unconditional) model — also used for prompting arm + perplexity
    base_model = train_model(train_c, vocab, code_dim=0, steps=steps, seed=seed)

    gen_prompts = prompts()
    arms_text: Dict[str, Dict[str, List[str]]] = {}

    # base arm: generate ignoring axis (same model, no code) — one pool
    base_pool = []
    for p in gen_prompts:
        for s in range(n_seeds):
            base_pool.append(generate(base_model, vocab, p, None, max_len, temp, seed=s))
    arms_text["base"] = {a: base_pool for a in AXES}  # axis-agnostic reference

    # prompt arm: base model, prepend axis word to prompt
    arms_text["prompt"] = {a: [] for a in AXES}
    for a in AXES:
        for p in gen_prompts:
            for s in range(n_seeds):
                arms_text["prompt"][a].append(
                    generate(base_model, vocab, f"{a} {p}", None, max_len, temp, seed=s))

    # conditional arms
    for arm in CONDITIONAL_ARMS:
        cd = codes[arm]
        dim = len(next(iter(cd.values())))
        model = train_model(train_c, vocab, codes=cd, code_dim=dim, steps=steps, seed=seed)
        arms_text[arm] = {a: [] for a in AXES}
        for a in AXES:
            for p in gen_prompts:
                for s in range(n_seeds):
                    arms_text[arm][a].append(
                        generate(model, vocab, p, cd[a], max_len, temp, seed=s))

    return _evaluate(arms_text, base_pool, clf, lex, base_model, vocab, u_backend)


def _axis_metrics(texts: List[str], target: str, scorer) -> Dict[str, float]:
    probs = [scorer.proba(t) if hasattr(scorer, "proba") else scorer.scores(t) for t in texts]
    on = float(np.mean([p[target] for p in probs]))
    off = float(np.mean([np.mean([p[a] for a in AXES if a != target]) for p in probs]))
    acc = float(np.mean([max(p, key=p.get) == target for p in probs]))
    return {"on_target": on, "off_target": off, "selectivity": on - off, "steer_acc": acc}


def _evaluate(arms_text, base_pool, clf, lex, base_model, vocab, u_backend) -> dict:
    results = {"u_backend": u_backend, "axes": AXES, "arms": {}}
    for arm, by_axis in arms_text.items():
        per_axis_clf, per_axis_lex = [], []
        ppls, reps, jss = [], [], []
        for a in AXES:
            texts = by_axis[a]
            per_axis_clf.append(_axis_metrics(texts, a, clf))
            per_axis_lex.append(_axis_metrics(texts, a, lex))
            ppls += [perplexity(base_model, vocab, t) for t in texts]
            reps += [repetition_rate(t) for t in texts]
            jss.append(unigram_js(texts, base_pool))

        def avg(key, src):
            return float(np.mean([m[key] for m in src]))

        results["arms"][arm] = {
            "clf_steer_acc": avg("steer_acc", per_axis_clf),
            "clf_on_target": avg("on_target", per_axis_clf),
            "clf_selectivity": avg("selectivity", per_axis_clf),
            "lex_steer_acc": avg("steer_acc", per_axis_lex),
            "lex_selectivity": avg("selectivity", per_axis_lex),
            "perplexity": float(np.nanmean(ppls)),
            "repetition": float(np.mean(reps)),
            "js_vs_base": float(np.mean(jss)),
            "n_samples": sum(len(by_axis[a]) for a in AXES),
        }
    results["chance_steer_acc"] = 1.0 / len(AXES)
    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-axis", type=int, default=60)
    ap.add_argument("--u-backend", default="pse_meaning",
                    choices=["vritti_mapper", "pse_meaning", "pse_resonance", "combined"])
    ap.add_argument("--steps", type=int, default=400)
    ap.add_argument("--n-seeds", type=int, default=4)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json", default=None, help="optional path to dump raw results")
    args = ap.parse_args()

    r = run(per_axis=args.per_axis, u_backend=args.u_backend, steps=args.steps,
            n_seeds=args.n_seeds, seed=args.seed)
    if args.json:
        with open(args.json, "w") as f:
            json.dump(r, f, indent=2)
    print_report(r)


def print_report(r: dict) -> None:
    print("=" * 84)
    print("CONTROLLABILITY PILOT  (SMOKE-ONLY: tiny from-scratch LM; proxy evaluators)")
    print("=" * 84)
    print(f"U backend={r['u_backend']}  axes={r['axes']}  "
          f"chance steer_acc={r['chance_steer_acc']:.3f}\n")
    h = (f"{'arm':<11}{'clf_acc':>8}{'clf_sel':>8}{'lex_acc':>8}{'lex_sel':>8}"
         f"{'ppl':>8}{'rep':>7}{'JSvsB':>7}")
    print(h); print("-" * len(h))
    order = ["base", "symbolu", "relabel", "random", "shuffled", "sentiment", "prompt"]
    for arm in order:
        if arm not in r["arms"]:
            continue
        m = r["arms"][arm]
        print(f"{arm:<11}{m['clf_steer_acc']:>8.3f}{m['clf_selectivity']:>8.3f}"
              f"{m['lex_steer_acc']:>8.3f}{m['lex_selectivity']:>8.3f}"
              f"{m['perplexity']:>8.1f}{m['repetition']:>7.2f}{m['js_vs_base']:>7.3f}")
    _verdict(r)


def _verdict(r: dict) -> None:
    A = r["arms"]
    print("\n" + "-" * 30 + " VERDICT (proxy) " + "-" * 30)
    su = A["symbolu"]["clf_steer_acc"]
    ch = r["chance_steer_acc"]
    rnd = A["random"]["clf_steer_acc"]
    shuf = A["shuffled"]["clf_steer_acc"]
    sent = A["sentiment"]["clf_steer_acc"]
    pr = A["prompt"]["clf_steer_acc"]
    rel = A["relabel"]["clf_steer_acc"]
    print(f"Symbol-U steers above chance:        {su:.3f} vs {ch:.3f}  "
          f"-> {'YES' if su > ch + 0.05 else 'no'}")
    print(f"Symbol-U beats random code:          {su:.3f} vs {rnd:.3f}  "
          f"-> {'YES' if su > rnd + 0.05 else 'NO (vacuous: any code steers)'}")
    print(f"Symbol-U beats shuffled:             {su:.3f} vs {shuf:.3f}  "
          f"-> {'YES' if su > shuf + 0.05 else 'no'}")
    print(f"Symbol-U beats sentiment (known tax): {su:.3f} vs {sent:.3f}  "
          f"-> {'YES' if su > sent + 0.05 else 'NO'}")
    print(f"Symbol-U beats NL prompting:         {su:.3f} vs {pr:.3f}  "
          f"-> {'YES' if su > pr + 0.05 else 'NO (dominated by prompting)'}")
    print(f"Specific ontology matters (vs relabel): {su:.3f} vs {rel:.3f}  "
          f"-> {'YES' if abs(su - rel) > 0.05 else 'NO (ontology labels are a basis choice)'}")


if __name__ == "__main__":
    main()
