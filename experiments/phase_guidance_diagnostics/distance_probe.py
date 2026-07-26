"""
distance_probe.py — Question B: does the Phase topic signal decay with distance?

Two measurements:
  (1) Natural examples: decode topic from g at each fact/answer position, bucketed
      by distance (pos - topic_decl_pos).
  (2) Controlled long-filler streaming: "TOPIC vendor X <sep>" + K filler tokens,
      decode topic from g at the final position for K in
      [64,128,256,512,1K,2K,4K,8K,16K,32K]. Also track, relative to the state right
      after the topic declaration:
        * Phase-state norm            ||S_t||
        * cosine(S_t, S_decl)         signal persistence
        * SNR proxy = |topic numerator contribution| / ||S_t||
"""
from __future__ import annotations
import torch
from experiments.phase_guidance_diagnostics import _common as C
from experiments.lightweight_phase_natural_language.datasets import BASE_NAMES, FILLER

DISTANCES = [64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768]


def _long_examples(tok, topics, K):
    """Build id sequences: header + K filler tokens. Returns ids [B, 4+K], labels."""
    rng = torch.Generator().manual_seed(1234 + K)
    seqs = []
    fillwords = " ".join(FILLER).split()
    fill_ids = tok.encode(fillwords)
    for name in topics:
        head = tok.encode(["TOPIC", "vendor", name, "<sep>"])
        # sample K filler ids
        pick = torch.randint(0, len(fill_ids), (K,), generator=rng).tolist()
        body = [fill_ids[i] for i in pick]
        seqs.append(head + body)
    ids = torch.tensor(seqs)
    return ids


@torch.no_grad()
def long_distance(model, tok, n_topics=24, reps=8):
    lab_map = {b: i for i, b in enumerate(BASE_NAMES)}
    topics = [b for b in BASE_NAMES]
    # replicate topics reps times for train/test samples
    topic_list = (topics * reps)
    y = torch.tensor([lab_map[t] for t in topic_list])
    out = {}
    for K in DISTANCES:
        ids = _long_examples(tok, topic_list, K)
        B = ids.shape[0]
        # process in small batches to bound memory at long K
        bs = max(1, min(B, 4096 // max(1, K // 64)))
        gfin, norms, coss, snrs = [], [], [], []
        for i in range(0, B, bs):
            chunk = ids[i:i + bs]
            h, g = C.encode_features(model, chunk)
            intern = C.phase_internals(model.phase, h)
            S = intern["S"]  # [b,N,H,Dh]
            gfin.append(g[:, -1])
            # state norm at final vs at declaration (pos 3, the <sep> after topic)
            Sfin = S[:, -1]; Sdecl = S[:, 3]
            norms.append(Sfin.abs().pow(2).sum(dim=(-1, -2)).sqrt())
            cs = torch.nn.functional.cosine_similarity(
                Sfin.reshape(chunk.shape[0], -1).abs(),
                Sdecl.reshape(chunk.shape[0], -1).abs(), dim=-1)
            coss.append(cs)
            # topic numerator contribution at final query vs total state norm
            qpos = torch.full((chunk.shape[0],), chunk.shape[1] - 1)
            spos = torch.full((chunk.shape[0],), 2)  # topic token position
            rc = C.readout_contrib_from_token(intern, qpos, spos)
            snrs.append(rc["num_contrib"].abs() / (norms[-1] + 1e-6))
        gfin = torch.cat(gfin); norms = torch.cat(norms)
        coss = torch.cat(coss); snrs = torch.cat(snrs)
        ntr = int(0.6 * B); perm = torch.randperm(B)
        tri, tei = perm[:ntr], perm[ntr:]
        pr = C.fit_linear_probe(gfin[tri], y[tri], len(BASE_NAMES), gfin[tei], y[tei])
        out[str(K)] = {"phase_top1": pr["top1"], "phase_top3": pr["topk"],
                       "state_norm_mean": norms.mean().item(),
                       "cos_to_decl_mean": coss.mean().item(),
                       "topic_snr_mean": snrs.mean().item()}
        print(f"  K={K:6d} phase_top1={pr['top1']:.3f} "
              f"norm={norms.mean():.2f} cos_decl={coss.mean():.3f} snr={snrs.mean():.4f}")
    return out


@torch.no_grad()
def natural_by_distance(model, tok, ncand=24, seed=7, n=400):
    lab_map = {b: i for i, b in enumerate(BASE_NAMES)}
    exs = C.generate_pressure(tok, "train", seed, n, ncand, C.TARGET_LEN)
    ids = C.collate_ids(exs, tok.pad_id)
    h, g = C.encode_features(model, ids)
    feats, labs, dists = [], [], []
    for i, e in enumerate(exs):
        name = tok.itos[e.tokens[2]]
        if name not in lab_map:
            continue
        pos = e.answer_pos
        feats.append(g[i, pos]); labs.append(lab_map[name])
        dists.append(pos - 2)
    G = torch.stack(feats); y = torch.tensor(labs); d = torch.tensor(dists)
    ntr = int(0.7 * len(y)); perm = torch.randperm(len(y))
    tri, tei = perm[:ntr], perm[ntr:]
    pr = C.fit_linear_probe(G[tri], y[tri], len(BASE_NAMES), G[tei], y[tei])
    return {"answer_pos_phase_top1": pr["top1"],
            "median_distance": int(d.float().median().item()),
            "distance_range": [int(d.min()), int(d.max())]}


def run(arm="D", pressure="3x"):
    model, cfg, tok, meta = C.train_or_load(arm, pressure, seed=0)
    model.eval()
    print(f"[distance_probe {arm} p{pressure}] long-filler streaming:")
    long_res = long_distance(model, tok)
    nat = natural_by_distance(model, tok)
    res = {"arm": arm, "pressure": pressure, "chance": 1.0 / len(BASE_NAMES),
           "long_filler": long_res, "natural": nat}
    C.save_json(f"distance_probe_{arm}_p{pressure}.json", res)
    return res


if __name__ == "__main__":
    run("D", "3x")
