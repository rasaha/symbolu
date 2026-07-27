"""
run_generalization.py — held-out compositional generalization for the pointer-query arm.

ONLY run after grounded-D1 passes ≥0.85 (sequencing rule). Trains the grounded-D1 arm
(oracle route + structured pointer query) on a RESTRICTED composition set and evaluates on the
DISJOINT held-out set, plus an eval-only identity-renaming probe.

  unseen_entity_pair      : train on train-pairs only, test on test-only entity adjacencies.
  unseen_relation_compose : train on train-relation-compositions, test on test-only (r1,r2).
  identity_renaming       : train normally, eval on a scrambled identity relabeling.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import torch

from .multihop_dataset import build_vocab, generate
from .config import TrainCfg
from .hybrid_model import IterativeHybrid
from .train import train_hybrid
from .evaluate import evaluate
from .heldout_splits import (entity_pair_split, relation_compose_split,
                             generate_entity_pair, generate_relation_compose, rename_identities)

HERE = Path(__file__).resolve().parent
ARM = dict(hops=2, routing_mode="oracle", pointer_query=True, W=32, K=8)


def _train(vocab, nid, gen, steps):
    torch.manual_seed(0)
    m = IterativeHybrid(vocab.size, nid, **ARM)
    train_hybrid(m, gen, vocab, TrainCfg(seed=0, steps=steps))
    return m


def run(N=32, steps=3000):
    vocab = build_vocab(); nid = vocab.n_id; t0 = time.time(); res = {}

    # in-distribution reference (renaming applies to this model)
    g_all = lambda bs, s: generate(vocab, N, 2, bs, s)
    m_all = _train(vocab, nid, g_all, steps)
    te = generate(vocab, N, 2, 300, 77000)
    res["in_distribution"] = evaluate(m_all, te, vocab)["accuracy"]
    res["identity_renaming"] = evaluate(m_all, rename_identities(te, vocab, seed=7), vocab)["accuracy"]
    print(f"in_dist={res['in_distribution']:.3f} renamed={res['identity_renaming']:.3f} "
          f"({time.time()-t0:.0f}s)", flush=True)

    # unseen entity pairs
    tr_p, te_p = entity_pair_split(vocab, holdout_frac=0.3, seed=0)
    g_ep = lambda bs, s: generate_entity_pair(vocab, N, 2, bs, s, tr_p)
    m_ep = _train(vocab, nid, g_ep, steps)
    te_ep = generate_entity_pair(vocab, N, 2, 300, 78000, te_p)
    res["unseen_entity_pair"] = evaluate(m_ep, te_ep, vocab)["accuracy"]
    print(f"unseen_entity_pair={res['unseen_entity_pair']:.3f} ({time.time()-t0:.0f}s)", flush=True)

    # unseen relation compositions
    tr_c, te_c = relation_compose_split(vocab, holdout_frac=0.3, seed=1)
    g_rc = lambda bs, s: generate_relation_compose(vocab, N, 2, bs, s, tr_c)
    m_rc = _train(vocab, nid, g_rc, steps)
    te_rc = generate_relation_compose(vocab, N, 2, 300, 79000, te_c)
    res["unseen_relation_compose"] = evaluate(m_rc, te_rc, vocab)["accuracy"]
    print(f"unseen_relation_compose={res['unseen_relation_compose']:.3f} ({time.time()-t0:.0f}s)",
          flush=True)

    res["interpretation"] = {
        "generalizes": (res["unseen_entity_pair"] >= 0.85 and res["unseen_relation_compose"] >= 0.85
                        and res["identity_renaming"] >= 0.85),
        "memorization_risk": res["identity_renaming"] < 0.5 * max(1e-9, res["in_distribution"]),
    }
    (HERE / "results" / "generalization.json").write_text(json.dumps(res, indent=2, default=float))
    print("GENERALIZATION:", json.dumps(res, indent=1, default=float), flush=True)
    print("GENERALIZATION DONE", flush=True)
    return res


if __name__ == "__main__":
    run()
