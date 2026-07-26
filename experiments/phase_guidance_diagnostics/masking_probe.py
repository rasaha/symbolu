"""
masking_probe.py — Question M: is the frozen Phase recurrence overloaded by
irrelevant (filler) tokens? (state dilution vs invalid recurrence)

We feed the SAME examples through the trained D encoder but zero the local
representation h at filler positions before the Phase pass, comparing topic
decodability from the Phase readout g under:
  * all tokens processed            (baseline; matches the experiment)
  * filler zeroed                   (keep header + fact-value tokens only)
  * only topic + fact tokens        (zero everything except the topic decl + facts)

If masking filler dramatically RESTORES topic decoding, the recurrence preserves
useful information when write density is reduced — i.e. the failure is STATE
DILUTION under broad writes, NOT an invalid recurrence. This is the decisive test
separating "fix the write density / task" from "Phase v2".

NOTE: this is a READ-ONLY diagnostic intervention on the INPUT to the frozen Phase
pass (we do not modify the frozen layer). We reuse the arm's own local encoder for
h, then re-run the frozen Phase forward on a masked copy of h.
"""
from __future__ import annotations
import torch
from experiments.phase_guidance_diagnostics import _common as C
from experiments.lightweight_phase_natural_language.datasets import BASE_NAMES


@torch.no_grad()
def _phase_g_on_masked_h(model, h, keep_mask):
    """Run frozen Phase on h with non-kept positions zeroed; return g = phase(h')-h'."""
    hm = h * keep_mask.unsqueeze(-1).to(h.dtype)
    return model.phase(hm) - hm


def run(arm="D", pressure="3x", n=500, seed=41):
    model, cfg, tok, meta = C.train_or_load(arm, pressure, seed=0)
    model.eval()
    lab = {b: i for i, b in enumerate(BASE_NAMES)}
    exs = C.generate_pressure(tok, "train", seed, n, 24, C.TARGET_LEN)
    ids = C.collate_ids(exs, tok.pad_id)
    h, g_all = C.encode_features(model, ids)
    ar = torch.arange(len(exs)); apos = torch.tensor([e.answer_pos for e in exs])
    y = torch.tensor([lab[tok.itos[e.tokens[2]]] for e in exs])

    N = ids.shape[1]
    keep_all = torch.ones(len(exs), N)
    keep_nofiller = torch.zeros(len(exs), N)
    keep_topicfact = torch.zeros(len(exs), N)
    for i, e in enumerate(exs):
        wl = e.write_labels
        # header (topic decl span 0..3), the query span, and fact-value tokens
        keep_nofiller[i, :4] = 1.0                 # header incl. topic token
        keep_nofiller[i, e.answer_pos - 4:e.answer_pos + 1] = 1.0  # query span
        keep_topicfact[i, 2] = 1.0                 # topic declaration token
        for j, l in enumerate(wl):
            if l in (0, 1):
                keep_nofiller[i, j] = 1.0
                keep_topicfact[i, j] = 1.0
        keep_topicfact[i, 2] = 1.0

    ntr = int(0.7 * len(y)); perm = torch.randperm(len(y)); tri, tei = perm[:ntr], perm[ntr:]

    def probe_g(g):
        gA = g[ar, apos]
        return C.fit_linear_probe(gA[tri], y[tri], len(BASE_NAMES), gA[tei], y[tei])["top1"]

    res = {"arm": arm, "pressure": pressure, "chance": 1.0 / len(BASE_NAMES),
           "keep_density": {
               "all": keep_all.mean().item(),
               "no_filler": keep_nofiller.mean().item(),
               "topic_fact_only": keep_topicfact.mean().item()},
           "phase_topic_top1": {
               "all_tokens": probe_g(g_all),
               "filler_zeroed": probe_g(_phase_g_on_masked_h(model, h, keep_nofiller)),
               "topic_fact_only": probe_g(_phase_g_on_masked_h(model, h, keep_topicfact))}}
    C.save_json(f"masking_probe_{arm}_p{pressure}.json", res)
    print(f"[masking_probe {arm} p{pressure}] chance={res['chance']:.3f}")
    for k, v in res["phase_topic_top1"].items():
        print(f"  {k:18s} phase_topic_top1={v:.3f} "
              f"(keep_density={res['keep_density'].get(k.replace('_tokens','').replace('all','all').replace('filler_zeroed','no_filler').replace('topic_fact_only','topic_fact_only'), '')})")
    return res


if __name__ == "__main__":
    run("D", "3x")
