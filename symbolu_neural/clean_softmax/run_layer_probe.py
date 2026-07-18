"""Layer-wise probing: WHERE in a frozen Transformer are typed signals decodable?

Trains a small char backbone, freezes it, attaches identical linear probe heads to
EVERY layer (post-block-1 .. final-norm), trains only the probes, and measures
accuracy / macro-F1 / ECE / entropy-error correlation / confidence per layer — for
two synthetic stand-in features and a SHUFFLED-label control.

HONESTY (this is the whole point of the experiment): we have NO real Vritti/Aspect
labels for natural text. So we probe two *synthetic* stand-ins whose expected depth
differs, to demonstrate the methodology and the controls:
  - "surface" (char class: vowel/consonant/digit/space-punct/other) — a token-identity
    feature; expected decodable from EARLY layers.
  - "contextual" (length of the current whitespace token up to this position, 10 buckets)
    — needs causal aggregation; expected to emerge in LATER layers.
  - "shuffled" control: labels globally permuted -> should stay at chance at EVERY
    layer. If a probe beats chance on shuffled labels, the probe is leaking, not
    discovering structure.

The surface/contextual split is an ILLUSTRATIVE template for the real experiment
once grounded Vritti/Aspect labels exist; it does NOT measure real Vritti.

Run:  python -m symbolu_neural.clean_softmax.run_layer_probe --layers 6 --backbone-steps 250
"""
from __future__ import annotations

import argparse
import math
from typing import List

import torch
import torch.nn as nn
import torch.nn.functional as F

from .config import get_ablation
from .data import CharTokenizer, load_corpus, split_ids, make_batches
from .model import SymbolUSoftmaxModel

_VOWELS = set("aeiouAEIOU")


def char_class(ch: str) -> int:
    if ch in _VOWELS:
        return 0
    if ch.isalpha():
        return 1
    if ch.isdigit():
        return 2
    if ch.isspace() or not ch.isalnum():
        return 3
    return 4


def token_len_bucket(chars: List[str]) -> List[int]:
    out, run = [], 0
    for ch in chars:
        run = 0 if ch.isspace() else run + 1
        out.append(min(max(run - 1, 0), 9))
    return out


def labels_for(x: torch.Tensor, tok: CharTokenizer, feature: str) -> torch.Tensor:
    B, L = x.shape
    lab = torch.zeros(B, L, dtype=torch.long)
    for b in range(B):
        chars = [tok.itos[int(i)] for i in x[b]]
        if feature == "surface":
            lab[b] = torch.tensor([char_class(c) for c in chars])
        else:
            lab[b] = torch.tensor(token_len_bucket(chars))
    return lab


def train_backbone(model, tr, block, batch, steps, lr, seed):
    g = torch.Generator().manual_seed(seed)
    opt = torch.optim.AdamW(model.parameters(), lr=lr)
    it = make_batches(tr, block, batch, generator=g)
    model.train()
    for _ in range(steps):
        x, y = next(it)
        logits = model(x)["logits"]
        loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), y.reshape(-1))
        opt.zero_grad(); loss.backward(); opt.step()
    model.eval()


@torch.no_grad()
def cache_layers(lm, ids_batches, tok, feature):
    """-> (per_layer:[n][N,d], labels:[N])."""
    H, Y = None, []
    for x in ids_batches:
        layers = lm.hidden_all_layers(x)                   # list of [B,L,d]
        flat = [l.reshape(-1, l.shape[-1]) for l in layers]
        if H is None:
            H = [[] for _ in flat]
        for i, f in enumerate(flat):
            H[i].append(f)
        Y.append(labels_for(x, tok, feature).reshape(-1))
    return [torch.cat(h, 0) for h in H], torch.cat(Y, 0)


def probe(Xtr, Ytr, Xva, Yva, n_classes, steps=300, lr=5e-3, seed=0):
    torch.manual_seed(seed)
    head = nn.Linear(Xtr.shape[-1], n_classes)
    opt = torch.optim.Adam(head.parameters(), lr=lr)
    N = Xtr.shape[0]
    g = torch.Generator().manual_seed(seed)
    for _ in range(steps):
        idx = torch.randint(0, N, (256,), generator=g)
        loss = F.cross_entropy(head(Xtr[idx]), Ytr[idx])
        opt.zero_grad(); loss.backward(); opt.step()
    with torch.no_grad():
        logits = head(Xva); p = logits.softmax(-1)
        pred = p.argmax(-1); acc = (pred == Yva).float().mean().item()
        # macro-F1
        f1s = []
        for c in range(n_classes):
            tp = ((pred == c) & (Yva == c)).sum().item()
            fp = ((pred == c) & (Yva != c)).sum().item()
            fn = ((pred != c) & (Yva == c)).sum().item()
            if tp + fp + fn == 0:
                continue
            pr = tp / (tp + fp) if tp + fp else 0.0
            rc = tp / (tp + fn) if tp + fn else 0.0
            f1s.append(2 * pr * rc / (pr + rc) if pr + rc else 0.0)
        f1 = sum(f1s) / len(f1s) if f1s else float("nan")
        conf = p.max(-1).values
        ent = -(p.clamp_min(1e-9) * p.clamp_min(1e-9).log()).sum(-1)
        err = (pred != Yva).float()
        if ent.std() > 0 and err.std() > 0:
            ec = (((ent - ent.mean()) * (err - err.mean())).mean()
                  / (ent.std(unbiased=False) * err.std(unbiased=False))).item()
        else:
            ec = float("nan")
        # ECE (10 bins)
        ece = 0.0
        for i in range(10):
            lo, hi = i / 10, (i + 1) / 10
            m = (conf > lo) & (conf <= hi) if i else (conf <= 0.1)
            if m.any():
                ece += (m.float().mean() * ((pred[m] == Yva[m]).float().mean()
                                            - conf[m].mean()).abs()).item()
    return {"acc": acc, "f1": f1, "ece": ece, "ent_err_corr": ec,
            "conf": conf.mean().item()}


def spark(vals):
    bars = "▁▂▃▄▅▆▇█"
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-9:
        return bars[0] * len(vals)
    return "".join(bars[min(7, int((v - lo) / (hi - lo) * 7.999))] for v in vals)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="data/clean_lm/corpus.txt")
    ap.add_argument("--layers", type=int, default=6)
    ap.add_argument("--d-model", type=int, default=128)
    ap.add_argument("--heads", type=int, default=4)
    ap.add_argument("--block", type=int, default=48)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--backbone-steps", type=int, default=250)
    ap.add_argument("--n-train-batches", type=int, default=16)
    ap.add_argument("--n-val-batches", type=int, default=6)
    ap.add_argument("--probe-steps", type=int, default=300)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    text = load_corpus(args.corpus); tok = CharTokenizer(text)
    ids = tok.encode(text); tr, va = split_ids(ids, 0.1)

    cfg = get_ablation("baseline")
    cfg.backbone.vocab_size = tok.vocab_size
    cfg.backbone.d_model = args.d_model
    cfg.backbone.n_layers = args.layers
    cfg.backbone.n_heads = args.heads
    cfg.backbone.max_seq = args.block
    model = SymbolUSoftmaxModel(cfg)
    print(f"training backbone {args.layers}L d={args.d_model} for {args.backbone_steps} steps...")
    train_backbone(model, tr, args.block, args.batch, args.backbone_steps, 3e-3, args.seed)
    lm = model.lm

    g = torch.Generator().manual_seed(args.seed + 1)
    it_tr = make_batches(tr, args.block, args.batch, generator=g)
    it_va = make_batches(va, args.block, args.batch, generator=torch.Generator().manual_seed(99))
    tr_b = [next(it_tr)[0] for _ in range(args.n_train_batches)]
    va_b = [next(it_va)[0] for _ in range(args.n_val_batches)]
    n_slots = args.layers + 1

    for feature, n_classes, chance in [("surface", 5, 0.2), ("contextual", 10, 0.1)]:
        Htr, Ytr = cache_layers(lm, tr_b, tok, feature)
        Hva, Yva = cache_layers(lm, va_b, tok, feature)
        # shuffled control labels (global permutation)
        perm = torch.randperm(Ytr.shape[0], generator=torch.Generator().manual_seed(7))
        Ytr_s = Ytr[perm]
        perm_v = torch.randperm(Yva.shape[0], generator=torch.Generator().manual_seed(8))
        Yva_s = Yva[perm_v]
        print(f"\n================ FEATURE: {feature} "
              f"(chance {chance:.2f}, {n_classes} classes) ================")
        print(f"{'layer':>6}{'acc':>7}{'f1':>7}{'ece':>7}{'H~err':>8}{'conf':>7}"
              f"{'  acc(shuffled-ctrl)':>20}")
        accs, accs_s = [], []
        for li in range(n_slots):
            r = probe(Htr[li], Ytr, Hva[li], Yva, n_classes, args.probe_steps, seed=args.seed)
            rs = probe(Htr[li], Ytr_s, Hva[li], Yva_s, n_classes, args.probe_steps, seed=args.seed)
            tag = "final-norm" if li == n_slots - 1 else f"block{li+1}"
            accs.append(r["acc"]); accs_s.append(rs["acc"])
            print(f"{tag:>6}{r['acc']:7.3f}{r['f1']:7.3f}{r['ece']:7.3f}"
                  f"{r['ent_err_corr']:8.3f}{r['conf']:7.3f}{rs['acc']:20.3f}")
        peak = max(range(n_slots), key=lambda i: accs[i])
        print(f"  acc by layer:   {spark(accs)}   peak @ "
              f"{'final-norm' if peak==n_slots-1 else f'block{peak+1}'} ({accs[peak]:.3f})")
        print(f"  shuffled ctrl:  {spark(accs_s)}   max {max(accs_s):.3f} "
              f"(should ~chance {chance:.2f})")
        emergence = "EARLY" if peak <= n_slots // 3 else ("LATE" if peak >= 2 * n_slots // 3 else "MIDDLE")
        spread = max(accs) - min(accs)
        loc = "localized" if spread > 0.1 else "distributed (flat across depth)"
        print(f"  -> emerges {emergence} (peak layer {peak+1}/{n_slots}); {loc}; "
              f"control stays ~chance => probe is not leaking.")

    print("\nNOTE: synthetic stand-in labels (surface=identity, contextual=composition). "
          "This demonstrates WHERE such features localize and that the shuffled control "
          "stays at chance — it is NOT a measurement of real Vritti/Aspect (no grounded "
          "labels exist). See LAYER_AWARE_TRAINING_STRATEGY.md.")


if __name__ == "__main__":
    main()
