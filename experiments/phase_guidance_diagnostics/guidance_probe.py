"""
guidance_probe.py — Question F: could a better guidance readout extract more from
Phase than the trained head does?

We freeze the encoder (h, g) of the trained D model and fit several small diagnostic
heads to predict (a) topic identity and (b) write-worthiness (topic-fact vs
distractor value token), from three inputs: local-only h, Phase-only g, concat h⊕g.
Heads: linear softmax/logistic, 2-layer MLP, and a normalized-cosine (centroid)
probe. If a richer probe on Phase-only substantially beats the trained guidance
head's realized write-F1, the readout — not the Phase state — is the bottleneck.
"""
from __future__ import annotations
import torch
import torch.nn as nn
import torch.nn.functional as F
from experiments.phase_guidance_diagnostics import _common as C
from experiments.lightweight_phase_natural_language.datasets import BASE_NAMES


def _mlp_probe(X, y, ncls, Xte, yte, steps=300, hidden=64):
    mu, sd = X.mean(0, keepdim=True), X.std(0, keepdim=True) + 1e-6
    Xn, Xten = (X - mu) / sd, (Xte - mu) / sd
    net = nn.Sequential(nn.Linear(X.shape[1], hidden), nn.GELU(), nn.Linear(hidden, ncls))
    opt = torch.optim.Adam(net.parameters(), lr=0.02, weight_decay=1e-3)
    for _ in range(steps):
        opt.zero_grad(); F.cross_entropy(net(Xn), y).backward(); opt.step()
    with torch.no_grad():
        pred = net(Xten).argmax(-1)
        return (pred == yte).float().mean().item()


def _binary_f1(X, y, Xte, yte, steps=300):
    mu, sd = X.mean(0, keepdim=True), X.std(0, keepdim=True) + 1e-6
    Xn, Xten = (X - mu) / sd, (Xte - mu) / sd
    lin = nn.Linear(X.shape[1], 1)
    opt = torch.optim.Adam(lin.parameters(), lr=0.03, weight_decay=1e-3)
    for _ in range(steps):
        opt.zero_grad()
        F.binary_cross_entropy_with_logits(lin(Xn).squeeze(-1), y.float()).backward()
        opt.step()
    with torch.no_grad():
        p = (lin(Xten).squeeze(-1) > 0)
        tp = ((p) & (yte == 1)).sum().item(); fp = ((p) & (yte == 0)).sum().item()
        fn = ((~p) & (yte == 1)).sum().item()
        prec = tp / max(1, tp + fp); rec = tp / max(1, tp + fn)
        return 2 * prec * rec / max(1e-9, prec + rec)


@torch.no_grad()
def _collect(model, tok, seed=23, n=500):
    exs = C.generate_pressure(tok, "train", seed, n, 24, C.TARGET_LEN)
    ids = C.collate_ids(exs, tok.pad_id)
    h, g = C.encode_features(model, ids)
    lab = {b: i for i, b in enumerate(BASE_NAMES)}
    # topic features at answer pos
    topic_h, topic_g, topic_y = [], [], []
    # write-worthiness features at value token positions
    wh, wg, wy = [], [], []
    for i, e in enumerate(exs):
        name = tok.itos[e.tokens[2]]
        ap = e.answer_pos
        topic_h.append(h[i, ap]); topic_g.append(g[i, ap]); topic_y.append(lab[name])
        for j, l in enumerate(e.write_labels):
            if l in (0, 1):
                wh.append(h[i, j]); wg.append(g[i, j]); wy.append(l)
    return (torch.stack(topic_h), torch.stack(topic_g), torch.tensor(topic_y),
            torch.stack(wh), torch.stack(wg), torch.tensor(wy))


def run(arm="D", pressure="3x"):
    model, cfg, tok, meta = C.train_or_load(arm, pressure, seed=0)
    model.eval()
    th, tg, ty, wh, wg, wy = _collect(model, tok)
    ncls = len(BASE_NAMES)

    def split(X, y):
        n = len(y); perm = torch.randperm(n); k = int(0.7 * n)
        return perm[:k], perm[k:]

    ti, te = split(th, ty)
    res = {"arm": arm, "pressure": pressure, "chance_topic": 1.0 / ncls,
           "realized_write_f1": meta.get("metrics", {}).get("write_f1"),
           "topic_identity": {}, "write_worthiness": {}}
    for name, X in (("local_only", th), ("phase_only", tg),
                    ("local_plus_phase", torch.cat([th, tg], -1))):
        lin = C.fit_linear_probe(X[ti], ty[ti], ncls, X[te], ty[te])["top1"]
        mlp = _mlp_probe(X[ti], ty[ti], ncls, X[te], ty[te])
        res["topic_identity"][name] = {"linear_top1": lin, "mlp_top1": mlp}

    wi, wte = split(wh, wy)
    for name, X in (("local_only", wh), ("phase_only", wg),
                    ("local_plus_phase", torch.cat([wh, wg], -1))):
        f1 = _binary_f1(X[wi], wy[wi], X[wte], wy[wte])
        res["write_worthiness"][name] = {"probe_f1": f1}

    C.save_json(f"guidance_probe_{arm}_p{pressure}.json", res)
    print(f"[guidance_probe {arm} p{pressure}] realized write_f1={res['realized_write_f1']}")
    print("  topic identity:", {k: v for k, v in res["topic_identity"].items()})
    print("  write-worthiness probe F1:", {k: round(v['probe_f1'], 3)
                                           for k, v in res["write_worthiness"].items()})
    return res


if __name__ == "__main__":
    run("D", "3x")
