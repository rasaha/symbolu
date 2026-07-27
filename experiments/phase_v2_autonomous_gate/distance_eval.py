"""
distance_eval.py — focus decode + relevance across distance for the autonomous-gate study.

Probes the recurrent Phase state and the EXISTING Phase readout (no new selective readout,
per constraint), with shuffled/random state controls. Reuses the v3 probe fitters.
"""
from __future__ import annotations

import torch

from experiments.phase_v3_selective_ssm import dataset as D
from experiments.phase_v3_selective_ssm.config import DataCfg
from experiments.phase_v3_selective_ssm.focus_probe import _fit_linear, _fit_binary


@torch.no_grad()
def _extract(model, data, vocab, device="cpu"):
    Xs, ys, xevt, yrel, gates_cat = {}, [], [], [], {"cue": [], "relevant": [], "distractor": [], "filler": []}
    for i in range(0, len(data), 32):
        b = data[i:i + 32]
        ids, wt, pp, fo = D.collate(b, vocab.PAD, device)
        gate = model.gate(ids)                       # [B,N,H]
        f = model.features(ids, gate=gate)
        ar = torch.arange(ids.shape[0], device=device)
        row = {"local": model.embed(ids)[ar, pp], "state": f["state"][ar, pp], "readout": f["readout"][ar, pp]}
        for k, v in row.items():
            Xs.setdefault(k, []).append(v)
        ys.append(fo)
        gm = gate.mean(-1)                           # [B,N]
        for j, e in enumerate(b):
            gates_cat["cue"].append(gm[j, 0].item())
            if e["event_pos"]:
                ep = torch.tensor(e["event_pos"], device=device)
                xevt.append(f["readout"][j, ep]); yrel.append(torch.tensor([1.0 if r else 0.0 for r in e["event_relevant"]], device=device))
                for k, pos in enumerate(e["event_pos"]):
                    gates_cat["relevant" if e["event_relevant"][k] else "distractor"].append(gm[j, pos].item())
            nonpad = (ids[j] != vocab.PAD)
            fill = nonpad.clone(); fill[0] = False; fill[e["probe_pos"]] = False
            for pos in e["event_pos"]:
                fill[pos] = False
            gates_cat["filler"].append(gm[j][fill].mean().item() if fill.any() else 0.0)
    X = {k: torch.cat(v, 0) for k, v in Xs.items()}
    y = torch.cat(ys, 0)
    Xe = torch.cat(xevt, 0) if xevt else torch.zeros(0, model.embed_dim)
    ye = torch.cat(yrel, 0) if yrel else torch.zeros(0)
    cat = {k: (sum(v) / len(v) if v else 0.0) for k, v in gates_cat.items()}
    return X, y, Xe, ye, cat


def probe_at(model, vocab, dcfg, distance, seed=0, n_train=600, n_eval=400, device="cpu"):
    tr = D.generate(vocab, dcfg, distance, n_train, 5000 + seed)
    te = D.generate(vocab, dcfg, distance, n_eval, 9000 + seed)
    Xtr, ytr, Etr, rtr, catr = _extract(model, tr, vocab, device)
    Xte, yte, Ete, rte, cate = _extract(model, te, vocab, device)
    E = dcfg.num_entities
    r = {}
    for name in ("local", "state", "readout"):
        r[name] = _fit_linear(Xtr[name], ytr, Xte[name], yte, E, seed=seed)
    g = torch.Generator().manual_seed(seed)
    perm = torch.randperm(Xtr["state"].shape[0], generator=g)
    r["shuffled_state"] = _fit_linear(Xtr["state"][perm], ytr, Xte["state"], yte, E, seed=seed)
    r["random_state"] = _fit_linear(torch.randn_like(Xtr["state"]), ytr, torch.randn_like(Xte["state"]), yte, E, seed=seed)
    r["relevance"] = _fit_binary(Etr, rtr, Ete, rte, seed=seed)
    r["write_by_category"] = cate
    r["gate_margin_rel_minus_distr"] = cate["relevant"] - cate["distractor"]
    r["chance"] = 1.0 / E
    return r


def eval_distances(model, vocab, dcfg, distances, seed=0):
    out = {}
    for d in distances:
        r = probe_at(model, vocab, dcfg, d, seed=seed)
        out[str(d)] = {
            "state_top1": r["state"]["top1"], "state_topk": r["state"]["topk"],
            "readout_top1": r["readout"]["top1"],
            "shuffled_top1": r["shuffled_state"]["top1"], "random_top1": r["random_state"]["top1"],
            "relevance_f1": r["relevance"]["f1"], "relevance_auroc": r["relevance"]["auroc"],
            "write_by_category": r["write_by_category"],
            "gate_margin": r["gate_margin_rel_minus_distr"],
        }
    return out
