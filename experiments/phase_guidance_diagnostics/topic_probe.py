"""
topic_probe.py — Question A/F: is the global TOPIC linearly decodable from the
frozen-Phase readout g, from the local rep h, or only from both?

Layer 1 (Tokens→Phase state) and Layer 2 (Phase state→guidance readout) test.
We fit a lightweight multinomial-logistic probe ŷ_topic = W x on features taken
at the ANSWER position (maximal distance from the topic header) and report:

  Local-only (h) / Phase-only (g) / Local+Phase (h⊕g) top-1 & top-3 topic accuracy,
  plus two controls:
    Random-state control      — x replaced by matched-variance Gaussian noise.
    Shuffled-Phase control    — g rows permuted across examples (destroys alignment).

Interpretation:
  Phase-only topic accuracy ≫ chance  ⇒ the global topic signal EXISTS in Phase
  (failure is downstream). Phase-only ≈ chance ⇒ Phase does not preserve topic.
"""
from __future__ import annotations
import torch
from experiments.phase_guidance_diagnostics import _common as C
from experiments.lightweight_phase_natural_language.datasets import BASE_NAMES


def build_feature_bank(model, tok, split="train", ncand=24, seed=7, n=600):
    """Extract (h, g) at the answer position for n examples; label = topic base name."""
    exs = C.generate_pressure(tok, split, seed, n, ncand, C.TARGET_LEN)
    lab_map = {b: i for i, b in enumerate(BASE_NAMES)}
    ids = C.collate_ids(exs, tok.pad_id)
    h, g = C.encode_features(model, ids)
    ar = torch.arange(len(exs))
    apos = torch.tensor([e.answer_pos for e in exs])
    # topic base name string via token id -> itos
    ylist, hlist, glist = [], [], []
    for i, e in enumerate(exs):
        topic_tok = e.tokens[2]  # header pos 2 = topic entity token
        name = tok.itos[topic_tok]
        if name not in lab_map:
            continue
        ylist.append(lab_map[name]); hlist.append(i)
    idx = torch.tensor(hlist)
    y = torch.tensor(ylist)
    hA = h[idx, apos[idx]]
    gA = g[idx, apos[idx]]
    return hA, gA, y


def run(arm="D", pressure="3x"):
    model, cfg, tok, meta = C.train_or_load(arm, pressure, seed=0)
    model.eval()
    hA, gA, y = build_feature_bank(model, tok)
    # keep only classes with >= 4 samples for a stable split
    ntr = int(0.7 * len(y))
    perm = torch.randperm(len(y))
    tri, tei = perm[:ntr], perm[ntr:]
    ncls = len(BASE_NAMES)

    def probe(X):
        return C.fit_linear_probe(X[tri], y[tri], ncls, X[tei], y[tei])

    hg = torch.cat([hA, gA], dim=-1)
    res = {
        "arm": arm, "pressure": pressure, "n": int(len(y)),
        "chance": 1.0 / ncls,
        "answer_acc_of_model": meta.get("metrics", {}).get("answer_acc"),
        "local_only": probe(hA),
        "phase_only": probe(gA),
        "local_plus_phase": probe(hg),
        "random_state_control": probe(torch.randn_like(gA)),
        "shuffled_phase_control": probe(gA[torch.randperm(len(y))]),
    }
    C.save_json(f"topic_probe_{arm}_p{pressure}.json", res)
    print(f"[topic_probe {arm} p{pressure}] chance={res['chance']:.3f}")
    for k in ("local_only", "phase_only", "local_plus_phase",
              "random_state_control", "shuffled_phase_control"):
        print(f"  {k:24s} top1={res[k]['top1']:.3f} top3={res[k]['topk']:.3f}")
    return res


if __name__ == "__main__":
    for arm in ("D", "C"):
        run(arm, "3x")
