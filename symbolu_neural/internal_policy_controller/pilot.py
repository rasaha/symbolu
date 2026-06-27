"""Internal draft->policy->final controller prototype — orchestrator.

Arms (per task spec):
  1 base               — no revision (draft = final)
  2 generic_refine     — content-reading critic (proxy for LLM self-critique)
  3 sentiment          — affect/style critic
  4 random             — random critic
  5 shuffled_symbolu   — Symbol-U critic with draft<->state link broken
  6 relabeled_symbolu  — Symbol-U critic with ontology dims permuted
  7 symbolu            — real Symbol-U/PSE critic

Pipeline per draft: critic diagnoses flaw -> emits policy -> SHARED reviser applies
it -> proxy evaluation. The decisive, assumption-light metric is CRITIC DIAGNOSTIC
ACCURACY (ground-truth flaw labels, held-out). Final-answer metrics use the shared
rule-based reviser (smoke-level; no LLM/ API offline).
"""
from __future__ import annotations

import argparse
from typing import Dict, List

import numpy as np

from .drafts import make_drafts, FLAWS
from .critics import CRITICS, Critic, build_feature_matrix, FLAW_TO_POLICY
from .reviser import revise
from .evaluator import residual_flaw, improvement, meaning_preservation, directness

# map task-spec arm names -> internal critic featurizer names
ARM_TO_CRITIC = {
    "generic_refine": "generic",
    "sentiment": "sentiment",
    "random": "random",
    "shuffled_symbolu": "shuffled",
    "relabeled_symbolu": "relabeled",
    "symbolu": "symbolu",
}
ARMS = ["base"] + list(ARM_TO_CRITIC.keys())


def _split(n, frac=0.6, seed=0):
    rng = np.random.default_rng(seed)
    idx = rng.permutation(n)
    k = int(n * frac)
    return idx[:k], idx[k:]


def run(seed: int = 0) -> dict:
    triples = make_drafts(seed)
    bases = [b for b, _, _ in triples]
    drafts = [d for _, d, _ in triples]
    flaws = [f for _, _, f in triples]
    y = np.array([FLAWS.index(f) for f in flaws])
    tr, te = _split(len(drafts), seed=seed)

    results = {"arms": {}, "n_drafts": len(drafts), "n_test": len(te)}

    # base arm: final = draft (no revision)
    results["arms"]["base"] = _eval_arm(
        [drafts[i] for i in te], [drafts[i] for i in te],
        [bases[i] for i in te], [flaws[i] for i in te], diag_acc=None)

    for arm, critic_name in ARM_TO_CRITIC.items():
        feats, featurizer = build_feature_matrix(critic_name, drafts, seed)
        critic = Critic(arm, feats[tr], y[tr])
        # diagnostic accuracy on held-out drafts
        pred = critic.clf.predict(feats[te])
        diag_acc = float((pred == y[te]).mean())
        # revise held-out drafts under the emitted policy
        finals = []
        for j, i in enumerate(te):
            policy = FLAW_TO_POLICY[FLAWS[int(pred[j])]]
            finals.append(revise(drafts[i], policy))
        results["arms"][arm] = _eval_arm(
            [drafts[i] for i in te], finals,
            [bases[i] for i in te], [flaws[i] for i in te], diag_acc=diag_acc)
    return results


def _eval_arm(te_drafts, finals, te_bases, te_flaws, diag_acc):
    resid, impr, mean_pres, direct = [], [], [], []
    for draft, final, base, flaw in zip(te_drafts, finals, te_bases, te_flaws):
        resid.append(residual_flaw(final, flaw))
        impr.append(improvement(draft, final, flaw))
        mean_pres.append(meaning_preservation(final, base))
        direct.append(directness(final))
    return {
        "diag_acc": diag_acc,
        "residual_flaw": float(np.mean(resid)),
        "improvement": float(np.mean(impr)),
        "meaning_preservation": float(np.mean(mean_pres)),
        "directness": float(np.mean(direct)),
    }


def print_report(r: dict) -> None:
    print("=" * 84)
    print("INTERNAL DRAFT->POLICY->FINAL CONTROLLER  (SMOKE-ONLY: no LLM/API; proxy eval)")
    print("=" * 84)
    print(f"drafts={r['n_drafts']}  held-out={r['n_test']}  flaws={FLAWS}\n")
    h = (f"{'arm':<18}{'diag_acc':>9}{'resid_flaw':>11}{'improve':>9}"
         f"{'meaning':>9}{'direct':>8}")
    print(h); print("-" * len(h))
    for arm in ARMS:
        m = r["arms"][arm]
        da = "  n/a" if m["diag_acc"] is None else f"{m['diag_acc']:.3f}"
        print(f"{arm:<18}{da:>9}{m['residual_flaw']:>11.3f}{m['improvement']:>9.3f}"
              f"{m['meaning_preservation']:>9.3f}{m['directness']:>8.3f}")
    _verdict(r)


def _verdict(r: dict) -> None:
    A = r["arms"]
    print("\n" + "-" * 30 + " VERDICT (proxy) " + "-" * 30)
    su = A["symbolu"]
    gen = A["generic_refine"]
    sent = A["sentiment"]
    rel = A["relabeled_symbolu"]
    shuf = A["shuffled_symbolu"]
    rnd = A["random"]
    chance = 1.0 / len(FLAWS)
    print(f"Symbol-U critic diagnostic accuracy: {su['diag_acc']:.3f}  (chance {chance:.3f})")
    print(f"  vs generic self-refine ({gen['diag_acc']:.3f}): "
          f"{'BEATS' if su['diag_acc'] > gen['diag_acc'] + 0.05 else 'LOSES/ties'}")
    print(f"  vs sentiment critic   ({sent['diag_acc']:.3f}): "
          f"{'BEATS' if su['diag_acc'] > sent['diag_acc'] + 0.05 else 'LOSES/ties'}")
    print(f"  vs random ({rnd['diag_acc']:.3f}) / shuffled ({shuf['diag_acc']:.3f}): "
          f"{'BEATS both' if su['diag_acc'] > max(rnd['diag_acc'], shuf['diag_acc']) + 0.05 else 'no clear gain'}")
    print(f"  ontology matters? vs relabeled ({rel['diag_acc']:.3f}): "
          f"{'YES' if abs(su['diag_acc'] - rel['diag_acc']) > 0.05 else 'NO (basis-invariant)'}")
    print(f"\nFinal-answer improvement over draft: symbolu={su['improvement']:.3f}  "
          f"generic={gen['improvement']:.3f}  sentiment={sent['improvement']:.3f}  "
          f"base={A['base']['improvement']:.3f}")
    better = su["improvement"] > gen["improvement"] + 0.01
    print("\nDoes the Symbol-U controller beat generic self-refinement? "
          f"{'YES' if better else 'NO'} "
          f"(Symbol-U improvement {su['improvement']:.3f} vs generic {gen['improvement']:.3f}).")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    print_report(run(args.seed))


if __name__ == "__main__":
    main()
