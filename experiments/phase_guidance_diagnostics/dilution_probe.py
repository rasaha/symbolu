"""
dilution_probe.py — Question C: does cumulative normalization dilute the rare
topic evidence as filler/distractor tokens accumulate?

The frozen readout is  o_t = Re(q_t ⊙ S_t) / stopgrad(a_q ⊙ A_t), with
S_t = Σ_{j≤t} a_{k,j} e^{-iφ_{k,j}} V_j  and  A_t = Σ_{j≤t} a_{k,j}  (no decay).

We attribute, at the answer position, the (unnormalized) numerator contribution
Re(q_t ⊙ kv_j) of:
  * the topic-declaration token,
  * the topic-fact value token(s)  (write label 1),
  * distractor value tokens        (write label 0),
  * everything else (filler),
and the denominator Z_t and its topic share. Swept over distractor counts
(context growth). If the topic-share of the numerator/denominator collapses toward
0 as distractors grow AND that collapse tracks the accuracy drop, dilution is
implicated.
"""
from __future__ import annotations
import torch
from experiments.phase_guidance_diagnostics import _common as C

DISTRACTORS = [0, 8, 16, 32, 64, 128]


@torch.no_grad()
def measure(model, tok, ncand, seed=11, n=120):
    exs = C.generate_pressure(tok, "test", seed, n, ncand, C.TARGET_LEN)
    ids = C.collate_ids(exs, tok.pad_id)
    h, g = C.encode_features(model, ids)
    intern = C.phase_internals(model.phase, h)
    a_q = intern["a_q"]; phi_q = intern["phi_q"]; kv = intern["kv"]
    A = intern["A"]; a_k = intern["a_k"]
    B = ids.shape[0]
    ar = torch.arange(B)
    apos = torch.tensor([e.answer_pos for e in exs])
    q_phasor = torch.polar(a_q[ar, apos], phi_q[ar, apos])   # [B,H,Dh]

    # per-token numerator contribution to n_t at the answer position
    # contrib_j = Re(q ⊙ kv_j) summed over H,Dh
    contrib = (q_phasor.unsqueeze(1) * kv).real.sum(dim=(-1, -2))   # [B,N]
    denom_incr = a_k.sum(dim=(-1, -2))                              # [B,N] per-token
    Z = (a_q[ar, apos] * A[ar, apos]).clamp(min=0.1).sum(dim=(-1, -2))  # [B]

    topic_num = torch.zeros(B); relfact_num = torch.zeros(B)
    distr_num = torch.zeros(B); filler_num = torch.zeros(B)
    topic_den = torch.zeros(B); distr_den = torch.zeros(B); filler_den = torch.zeros(B)
    for i, e in enumerate(exs):
        wl = e.write_labels
        N = len(e.tokens)
        topic_set = {2}  # topic declaration token
        val1 = {j for j, l in enumerate(wl) if l == 1}
        val0 = {j for j, l in enumerate(wl) if l == 0}
        for j in range(min(N, contrib.shape[1])):
            cj = contrib[i, j].item(); dj = denom_incr[i, j].item()
            if j in topic_set:
                topic_num[i] += cj; topic_den[i] += dj
            elif j in val1:
                relfact_num[i] += cj; topic_den[i] += dj
            elif j in val0:
                distr_num[i] += cj; distr_den[i] += dj
            else:
                filler_num[i] += cj; filler_den[i] += dj
    total_num_abs = (topic_num.abs() + relfact_num.abs() + distr_num.abs() + filler_num.abs() + 1e-9)
    return {
        "n_candidates": ncand,
        "topic_num_abs": topic_num.abs().mean().item(),
        "relfact_num_abs": relfact_num.abs().mean().item(),
        "distractor_num_abs": distr_num.abs().mean().item(),
        "filler_num_abs": filler_num.abs().mean().item(),
        "topic_num_share": (topic_num.abs() / total_num_abs).mean().item(),
        "relfact_num_share": (relfact_num.abs() / total_num_abs).mean().item(),
        "distractor_num_share": (distr_num.abs() / total_num_abs).mean().item(),
        "filler_num_share": (filler_num.abs() / total_num_abs).mean().item(),
        "Z_mean": Z.mean().item(),
        "topic_denom_share": (topic_den / (topic_den + distr_den + filler_den + 1e-9)).mean().item(),
        "relevant_to_distractor_num": (
            (topic_num.abs() + relfact_num.abs()) / (distr_num.abs() + 1e-6)).mean().item(),
        "seq_len_mean": float(sum(len(e.tokens) for e in exs) / len(exs)),
    }


def run(arm="D", pressure="3x"):
    model, cfg, tok, meta = C.train_or_load(arm, pressure, seed=0)
    model.eval()
    rows = []
    for nd in DISTRACTORS:
        r = measure(model, tok, ncand=nd + 1)   # +1 topic fact
        rows.append(r)
        print(f"  distractors~{nd:4d} len={r['seq_len_mean']:.0f} "
              f"topic_share={r['topic_num_share']:.4f} "
              f"relfact_share={r['relfact_num_share']:.4f} "
              f"filler_share={r['filler_num_share']:.4f} "
              f"rel/distr={r['relevant_to_distractor_num']:.3f} Z={r['Z_mean']:.1f}")
    res = {"arm": arm, "pressure": pressure, "sweep": rows}
    C.save_json(f"dilution_probe_{arm}_p{pressure}.json", res)
    return res


if __name__ == "__main__":
    run("D", "3x")
