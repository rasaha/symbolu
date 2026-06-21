#!/usr/bin/env python3
"""extract_bhava_probe_features.py — run a model+checkpoint over labeled examples, save features.

LEGACY / PROBE-ONLY — NOT part of the current C×R×S MATCH-filter runtime (csr_match_filter/). Computes
and saves a hidden-state Bhava slice (state[0:12]) as read-only telemetry for probe training; it does
not feed CSR scoring, frame selection, prompts, audit, or rewrite, and does not steer generation.

For each probe-JSONL example, extracts (Deliverable 2):
  A. Bhava value : bhava[12], dominant_bhava, bhava_entropy
  B. CG state    : state32, kosha/vritti/guna/reserved slices
  C. Delta       : ΔBhava (bhava(prompt) − bhava(prompt[:-1])), ‖ΔBhava‖, intent_phase
  D. Hidden base : pooled final hidden, last-token final hidden   (the REQUIRED control)

Saves runs/bhava_probe/<ts>/features.npz (arrays [N, d]) + labels.json + config.json.

Requires torch + a trained Active-CG checkpoint; exits cleanly (code 0) if either is absent so it
never blocks CPU work. GPU portion only.

Env: MODEL_ID, CG_CHECKPOINT, DEVICE, DTYPE  (same as the ablation).
Usage:
  CG_CHECKPOINT=/path/best_model.pt python scripts/cg_wrapper_ablation/extract_bhava_probe_features.py \
      --data scripts/cg_wrapper_ablation/probe_data/<file>.jsonl
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="probe JSONL (id/prompt/label/label_type)")
    ap.add_argument("--out", default=None, help="output dir (default runs/bhava_probe/<ts>)")
    ap.add_argument("--max-examples", type=int, default=0, help="cap (0=all)")
    args = ap.parse_args()

    try:
        import numpy as np
        import torch  # noqa: F401
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
    print(f"== extracting features for {len(rows)} examples ==")

    wrapper, tok = build_wrapper(cfg)
    wrapper.eval()
    device = next(wrapper.parameters()).device

    feats = {k: [] for k in (
        "bhava", "bhava_entropy", "dominant_bhava", "state32",
        "kosha", "vritti", "guna", "reserved",
        "delta_bhava", "delta_bhava_norm", "intent_phase",
        "hidden_pooled", "hidden_last")}
    labels = []

    def _state(input_ids):
        out = wrapper(input_ids=input_ids, reset_state=True, return_last_hidden=False)
        return out  # dict with 'state','delta_bhava','intent_phase'

    with torch.no_grad():
        for r in rows:
            enc = tok(r["prompt"], return_tensors="pt", truncation=True, max_length=1024)
            ids = enc["input_ids"].to(device)
            if ids.shape[1] < 2:
                continue
            # raw backbone hidden (the generic control — independent of CG correction)
            bo = wrapper.backbone(input_ids=ids, output_hidden_states=True)
            h = bo.hidden_states[-1][0].float()           # [T, D]
            hidden_pooled = h.mean(0).cpu().numpy()
            hidden_last = h[-1].cpu().numpy()
            # CG state on full prompt and on prompt[:-1] for a real ΔBhava
            full = _state(ids)
            prev = _state(ids[:, :-1])
            state = full["state"][0].float().cpu().numpy()        # [32]
            bhava = state[0:12]
            bhava_prev = prev["state"][0, 0:12].float().cpu().numpy()
            dbhava = bhava - bhava_prev
            intent = full.get("intent_phase")
            intent = intent[0].float().cpu().numpy() if intent is not None else np.zeros(1)

            feats["bhava"].append(bhava)
            feats["bhava_entropy"].append([_entropy(bhava)])
            feats["dominant_bhava"].append([int(np.argmax(bhava))])
            feats["state32"].append(state)
            feats["kosha"].append(state[12:17])
            feats["vritti"].append(state[17:22])
            feats["guna"].append(state[22:28])
            feats["reserved"].append(state[28:32])
            feats["delta_bhava"].append(dbhava)
            feats["delta_bhava_norm"].append([float(np.linalg.norm(dbhava))])
            feats["intent_phase"].append(intent)
            feats["hidden_pooled"].append(hidden_pooled)
            feats["hidden_last"].append(hidden_last)
            labels.append({"id": r["id"], "label": r["label"], "label_type": r["label_type"]})

    out_dir = Path(args.out) if args.out else _REPO / "runs" / "bhava_probe" / \
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_dir / "features.npz",
                        **{k: np.asarray(v, dtype=np.float32) for k, v in feats.items()})
    (out_dir / "labels.json").write_text(json.dumps(labels, indent=2))
    (out_dir / "config.json").write_text(json.dumps({
        "model_id": cfg.model_id, "checkpoint": cfg.checkpoint, "dtype": cfg.dtype,
        "data": str(args.data), "n": len(labels),
    }, indent=2))
    print(f"== wrote {len(labels)} feature rows to {out_dir} ==")
    print("Next: python scripts/cg_wrapper_ablation/train_bhava_probe.py", out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
