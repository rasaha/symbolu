"""Grounding experiment: can Vritti/Aspect heads be grounded on REAL (weak-labeled)
words, and do they GENERALIZE to unseen words?

Trains a char backbone, freezes it, labels corpus words via the distant-supervision
lexicon, pools per-word hidden states at every layer, and trains linear Vritti/Aspect
probes. Reports, per layer, accuracy on:
  - in-vocab test  (random split; words may also appear in train)  -> can it fit?
  - UNSEEN-word test (disjoint words)                              -> does it GENERALIZE?
  - shuffled-label control                                          -> is it leaking?

The decisive number is the unseen-word accuracy vs the shuffled control: fitting
seen words is mostly spelling memorization; generalizing to unseen words by category
is evidence the backbone encodes the *meaning*. Honest expectation for a char-level
LM backbone: good in-vocab fit, weak unseen-word generalization (it encodes spelling,
not semantics) — which tells you grounding needs a semantically-capable backbone.

Run:  python -m symbolu_neural.clean_softmax.run_grounding --layers 4 --backbone-steps 300
"""
from __future__ import annotations

import argparse
import re

import torch
import torch.nn as nn
import torch.nn.functional as F

from .config import get_ablation
from .data import CharTokenizer, load_corpus, split_ids, make_batches
from .model import SymbolUSoftmaxModel
from . import lexicon

WORD_RE = re.compile(r"[A-Za-z]+")


def train_backbone(model, tr, block, batch, steps, seed):
    g = torch.Generator().manual_seed(seed)
    opt = torch.optim.AdamW(model.parameters(), lr=3e-3)
    it = make_batches(tr, block, batch, generator=g)
    model.train()
    for _ in range(steps):
        x, y = next(it)
        loss = F.cross_entropy(model(x)["logits"].reshape(-1, model.cfg.backbone.vocab_size),
                               y.reshape(-1))
        opt.zero_grad(); loss.backward(); opt.step()
    model.eval()


@torch.no_grad()
def collect(lm, tok, ids, block, n_blocks, seed):
    """-> per-layer reps [n_slots][N,d], v_labels[N], a_labels[N], words[N]."""
    g = torch.Generator().manual_seed(seed)
    it = make_batches(ids, block, 1, generator=g)
    reps, vlab, alab, words = None, [], [], []
    for _ in range(n_blocks):
        x, _ = next(it)
        layers = lm.hidden_all_layers(x)                   # list [1,L,d]
        s = "".join(tok.itos[int(i)] for i in x[0])
        for m in WORD_RE.finditer(s):
            a, b = m.start(), m.end()
            w = m.group()
            vl, al = lexicon.vritti_label(w), lexicon.aspect_label(w)
            if vl is None and al is None:
                continue
            pooled = [l[0, a:b].mean(0) for l in layers]    # per-layer mean over span
            if reps is None:
                reps = [[] for _ in pooled]
            for i, p in enumerate(pooled):
                reps[i].append(p)
            vlab.append(vl if vl is not None else -100)
            alab.append(al if al is not None else -100)
            words.append(lexicon.normalize(w))
    reps = [torch.stack(r) for r in reps]
    return reps, torch.tensor(vlab), torch.tensor(alab), words


def probe(Xtr, Ytr, Xte, Yte, C, steps=400, seed=0):
    keep_tr = Ytr != -100
    keep_te = Yte != -100
    Xtr, Ytr, Xte, Yte = Xtr[keep_tr], Ytr[keep_tr], Xte[keep_te], Yte[keep_te]
    if len(Ytr) < 10 or len(Yte) < 5:
        return float("nan"), float("nan")
    torch.manual_seed(seed)
    head = nn.Linear(Xtr.shape[-1], C)
    opt = torch.optim.Adam(head.parameters(), lr=5e-3)
    g = torch.Generator().manual_seed(seed)
    for _ in range(steps):
        idx = torch.randint(0, len(Ytr), (min(256, len(Ytr)),), generator=g)
        loss = F.cross_entropy(head(Xtr[idx]), Ytr[idx])
        opt.zero_grad(); loss.backward(); opt.step()
    with torch.no_grad():
        pred = head(Xte).argmax(-1)
        acc = (pred == Yte).float().mean().item()
        # majority baseline on test
        maj = torch.bincount(Yte).max().item() / len(Yte)
    return acc, maj


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="data/clean_lm/corpus.txt")
    ap.add_argument("--layers", type=int, default=4)
    ap.add_argument("--d-model", type=int, default=128)
    ap.add_argument("--block", type=int, default=128)
    ap.add_argument("--backbone-steps", type=int, default=300)
    ap.add_argument("--n-blocks", type=int, default=400)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    text = load_corpus(args.corpus); tok = CharTokenizer(text)
    ids = tok.encode(text); tr, _ = split_ids(ids, 0.1)
    print("lexicon coverage:", lexicon.coverage())

    cfg = get_ablation("baseline")
    cfg.backbone.vocab_size = tok.vocab_size; cfg.backbone.d_model = args.d_model
    cfg.backbone.n_layers = args.layers; cfg.backbone.n_heads = 4
    cfg.backbone.max_seq = args.block
    model = SymbolUSoftmaxModel(cfg)
    print(f"training {args.layers}L backbone {args.backbone_steps} steps...")
    train_backbone(model, tr, args.block, 16, args.backbone_steps, args.seed)

    reps, vlab, alab, words = collect(model.lm, tok, tr, args.block, args.n_blocks, args.seed + 1)
    N = len(words)
    print(f"collected {N} labeled words "
          f"(vritti {int((vlab!=-100).sum())}, aspect {int((alab!=-100).sum())})")

    rng = torch.Generator().manual_seed(7)
    # random (in-vocab) split
    perm = torch.randperm(N, generator=rng)
    cut = int(N * 0.85)
    tr_idx, te_idx = perm[:cut], perm[cut:]
    # unseen-word split: hold out ~20% of UNIQUE words
    uniq = sorted(set(words))
    wperm = torch.randperm(len(uniq), generator=torch.Generator().manual_seed(8))
    held = {uniq[i] for i in wperm[: max(1, len(uniq) // 5)].tolist()}
    seen_mask = torch.tensor([w not in held for w in words])
    # shuffled-label control
    vs = vlab[torch.randperm(N, generator=torch.Generator().manual_seed(9))]
    as_ = alab[torch.randperm(N, generator=torch.Generator().manual_seed(10))]

    for headname, lab, C, labshuf in [("Vritti", vlab, 5, vs), ("Aspect", alab, 10, as_)]:
        print(f"\n=========== {headname} ({C} classes) ===========")
        print(f"{'layer':>11}{'in-vocab':>10}{'unseen-wd':>11}{'shuffled':>10}{'maj':>7}")
        for li in range(args.layers + 1):
            X = reps[li]
            iv, _ = probe(X[tr_idx], lab[tr_idx], X[te_idx], lab[te_idx], C, seed=args.seed)
            uw, maj = probe(X[seen_mask], lab[seen_mask], X[~seen_mask], lab[~seen_mask], C, seed=args.seed)
            sh, _ = probe(X[tr_idx], labshuf[tr_idx], X[te_idx], labshuf[te_idx], C, seed=args.seed)
            tag = "final-norm" if li == args.layers else f"block{li+1}"
            print(f"{tag:>11}{iv:10.3f}{uw:11.3f}{sh:10.3f}{maj:7.3f}")

    print("\nINTERPRETATION: in-vocab >> shuffled means the head fits seen words "
          "(largely spelling). The decisive test is UNSEEN-WORD acc vs majority/shuffled: "
          "if unseen-wd ~ majority, grounding is word-memorization, NOT semantic — a "
          "char-LM backbone does not encode Vritti/Aspect *meaning*, so real grounding "
          "needs a semantically-capable backbone + human labels. WEAK/distant labels; "
          "not ground truth (see lexicon.py).")


if __name__ == "__main__":
    main()
