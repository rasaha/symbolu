#!/usr/bin/env python3
"""extract_csr_probe_features.py — features for the static CSR = Context x Semantic x Resonance probe.

Per labeled example, extracts (docs/STL_CSR_REFACTOR_PLAN.md), each with per-component availability:
  state_bhava (state[0:12]+entropy)  [also saved as 'bhava' for the legacy probe]
  state32                            (32D CG state baseline)
  context_r_ctx (16D)                Context = csr_scorer.context_proj([hidden; state]) from ckpt
  semantic (pooled input embeddings) Semantic = referential embedding
  resonance_combined (12D varna)     Resonance = Sanskrit-varna affinity (CSREmbeddingProvider)
  phoneme_bhava / vritti_consonant   Resonance split (vowel->cognitive mode / consonant->motion)
  hidden_pooled / hidden_last        generic baseline
  delta_bhava (+norm)                reported for completeness (STL deferred; ~dead)

NEVER fabricates: a missing component is recorded under metadata.feature_unavailable.
GPU-only; skips cleanly (exit 0) if torch/checkpoint absent.

Env: MODEL_ID, CG_CHECKPOINT, DEVICE, DTYPE. Usage:
  CG_CHECKPOINT=/path/best_model.pt python scripts/cg_wrapper_ablation/extract_csr_probe_features.py \
     --data scripts/cg_wrapper_ablation/probe_data/probe_balanced.jsonl
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from cg_ablation.probe_schema import load_probe_jsonl  # noqa: E402


def _entropy(p):
    import numpy as np
    p = np.clip(np.asarray(p, dtype=float), 1e-12, 1.0)
    return float(-(p * np.log(p)).sum())


def _load_context_proj(ckpt_path):
    """Build the Context r_ctx MLP from csr_scorer.context_proj weights in the FULL checkpoint.

    Returns (fn(x)->r_ctx, in_dim) or (None, reason). x is [N, hidden+state].
    """
    import torch
    obj = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    sd = obj.get("model_state_dict", obj.get("model", obj.get("state_dict", obj)))
    if not isinstance(sd, dict):
        return None, "checkpoint not a state-dict"
    # find context_proj.0.{weight,bias} and context_proj.2.{weight,bias} under any csr_scorer prefix
    cand = [k for k in sd if "csr_scorer.context_proj" in k and k.endswith(".weight")]
    if not cand:
        return None, "no csr_scorer.context_proj in checkpoint (CSR token scorer untrained/absent)"
    pref = cand[0].rsplit(".context_proj.", 1)[0] + ".context_proj"
    try:
        w0, b0 = sd[f"{pref}.0.weight"].float(), sd[f"{pref}.0.bias"].float()
        w2, b2 = sd[f"{pref}.2.weight"].float(), sd[f"{pref}.2.bias"].float()
    except KeyError as e:
        return None, f"context_proj weights incomplete ({e})"
    import torch.nn.functional as F

    def fn(x):  # x: [N, in_dim] float tensor
        h = F.gelu(F.linear(x, w0, b0))
        return F.linear(h, w2, b2)
    return fn, w0.shape[1]


def _resonance_extractors(tokenizer):
    """Return (combined_fn, split_fn, meta) for Resonance, each None if unavailable.

    combined_fn(input_ids)->[12] pooled varna affinity; split_fn(text)->(phoneme_bhava, vritti_consonant).
    """
    meta = {}
    combined_fn = None
    split_fn = None
    # combined 12D varna affinity via CSREmbeddingProvider (has its own g2p + char fallback)
    try:
        from csr_phoneme_provider import CSREmbeddingProvider, CSRConfig
        prov = CSREmbeddingProvider(CSRConfig(), tokenizer)

        def combined_fn(input_ids):
            import torch
            with torch.no_grad():
                out = prov(input_ids.cpu())            # affinity table is CPU — index with CPU ids
            aff = out["csr_affinity"][0].float()   # [T,12]
            return aff.mean(0).cpu().numpy()
        meta["resonance_combined"] = "ok (CSREmbeddingProvider)"
    except Exception as exc:
        meta["resonance_combined_unavailable"] = f"CSREmbeddingProvider failed: {exc}"

    # split vowel/consonant via varna_mapping (text-derived, model-independent)
    try:
        import varna_mapping as VM
        vowel_varnas = sorted({v["varna"] for v in VM.VOWEL_STATES.values()})
        vritti_labels = sorted({e.get("english", str(e)) for e in VM.VRITTI_LABELS.values()})
        try:
            from csr_phoneme_provider import HybridG2P
            g2p = HybridG2P()
            def to_phonemes(word):
                return g2p.get_phonemes(word)
        except Exception:
            g2p = None
            def to_phonemes(word):  # crude vowel/consonant fallback on raw chars
                return list(word.upper())

        import numpy as np

        def split_fn(text):
            vb = np.zeros(len(vowel_varnas)); vc = np.zeros(len(vritti_labels))
            for w in text.split():
                for ph in to_phonemes(w):
                    ph = ph.rstrip("012")
                    vs = VM.VOWEL_STATES.get(ph)
                    if vs is not None:
                        vb[vowel_varnas.index(vs["varna"])] += 1
                        continue
                    vr = VM.VRITTI_LABELS.get(ph)
                    if vr is not None:
                        lab = vr.get("english", str(vr))
                        if lab in vritti_labels:
                            vc[vritti_labels.index(lab)] += 1
            if vb.sum() > 0: vb /= vb.sum()
            if vc.sum() > 0: vc /= vc.sum()
            return vb, vc
        meta["resonance_split"] = f"ok (varna_mapping; g2p={'yes' if g2p else 'char-fallback'})"
        meta["phoneme_bhava_dim"] = len(vowel_varnas)
        meta["vritti_consonant_dim"] = len(vritti_labels)
    except Exception as exc:
        meta["resonance_split_unavailable"] = f"varna split failed: {exc}"

    return combined_fn, split_fn, meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--max-examples", type=int, default=0)
    args = ap.parse_args()
    try:
        import numpy as np
        import torch
    except ImportError:
        print("[skip] torch/numpy unavailable — extraction is GPU-only. Nothing written.")
        return 0
    from cg_ablation.runtime import parse_env, build_wrapper

    cfg = parse_env()
    if not cfg.checkpoint or not Path(cfg.checkpoint).exists():
        print(f"[skip] CG_CHECKPOINT not set or missing ({cfg.checkpoint}). Nothing written.")
        return 0

    rows = load_probe_jsonl(args.data)
    if args.max_examples:
        rows = rows[: args.max_examples]
    wrapper, tok = build_wrapper(cfg)
    wrapper.eval()
    device = next(wrapper.parameters()).device
    avail = {}

    ctx_fn, ctx_info = _load_context_proj(cfg.checkpoint)
    if ctx_fn is None:
        avail["context_r_ctx_unavailable"] = ctx_info
    res_combined_fn, res_split_fn, res_meta = _resonance_extractors(tok)
    avail.update(res_meta)
    embed = wrapper.backbone.get_input_embeddings()

    feats = {k: [] for k in (
        "bhava", "bhava_entropy", "state_bhava", "state_bhava_entropy", "state32",
        "context_r_ctx", "semantic", "resonance_combined", "phoneme_bhava", "vritti_consonant",
        "hidden_pooled", "hidden_last", "delta_bhava", "delta_bhava_norm")}
    labels = []

    with torch.no_grad():
        for r in rows:
            enc = tok(r["prompt"], return_tensors="pt", truncation=True, max_length=1024)
            ids = enc["input_ids"].to(device)
            if ids.shape[1] < 2:
                continue
            bo = wrapper.backbone(input_ids=ids, output_hidden_states=True)
            h = bo.hidden_states[-1][0].float()                 # [T,D]
            hidden_pooled = h.mean(0).cpu().numpy()
            full = wrapper(input_ids=ids, reset_state=True, return_last_hidden=False)
            prev = wrapper(input_ids=ids[:, :-1], reset_state=True)
            state = full["state"][0].float().cpu().numpy()      # [32]
            bhava = state[0:12]
            dbhava = bhava - prev["state"][0, 0:12].float().cpu().numpy()

            feats["bhava"].append(bhava); feats["state_bhava"].append(bhava)
            ent = _entropy(bhava)
            feats["bhava_entropy"].append([ent]); feats["state_bhava_entropy"].append([ent])
            feats["state32"].append(state)
            feats["hidden_pooled"].append(hidden_pooled)
            feats["hidden_last"].append(h[-1].cpu().numpy())
            feats["delta_bhava"].append(dbhava)
            feats["delta_bhava_norm"].append([float(np.linalg.norm(dbhava))])
            feats["semantic"].append(embed(ids)[0].float().mean(0).cpu().numpy())  # input embeddings

            if ctx_fn is not None:
                try:
                    x = torch.cat([torch.tensor(hidden_pooled), torch.tensor(state)]).float().unsqueeze(0)
                    feats["context_r_ctx"].append(ctx_fn(x)[0].cpu().numpy())
                except Exception as exc:
                    avail.setdefault("context_r_ctx_unavailable", f"runtime error: {exc}")
                    ctx_fn = None
            if res_combined_fn is not None:
                try:
                    feats["resonance_combined"].append(res_combined_fn(ids))
                except Exception as exc:
                    avail.setdefault("resonance_combined_unavailable", f"runtime error: {exc}")
                    res_combined_fn = None
            if res_split_fn is not None:
                try:
                    vb, vc = res_split_fn(r["prompt"])
                    feats["phoneme_bhava"].append(vb); feats["vritti_consonant"].append(vc)
                except Exception as exc:
                    avail.setdefault("resonance_split_unavailable", f"runtime error: {exc}")
                    res_split_fn = None
            labels.append({"id": r["id"], "label": r["label"], "label_type": r["label_type"]})

    out_dir = Path(args.out) if args.out else _REPO / "runs" / "bhava_probe" / \
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_csr")
    out_dir.mkdir(parents=True, exist_ok=True)
    save = {k: np.asarray(v, dtype=np.float32) for k, v in feats.items() if len(v) == len(labels) and v}
    dropped = [k for k, v in feats.items() if k not in save]
    np.savez_compressed(out_dir / "features.npz", **save)
    (out_dir / "labels.json").write_text(json.dumps(labels, indent=2))
    (out_dir / "config.json").write_text(json.dumps({
        "model_id": cfg.model_id, "checkpoint": cfg.checkpoint, "dtype": cfg.dtype,
        "data": str(args.data), "n": len(labels),
        "feature_availability": avail, "saved_feature_keys": sorted(save),
        "dropped_unavailable_keys": dropped,
    }, indent=2))
    print(f"== wrote {len(labels)} rows to {out_dir} ==")
    print("saved features:", sorted(save))
    if dropped:
        print("UNAVAILABLE (recorded, not faked):", dropped)
    for k, v in avail.items():
        if "unavailable" in k:
            print(f"  feature_unavailable: {k} -> {v}")
    print("Next: python scripts/cg_wrapper_ablation/train_bhava_probe.py", out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
