#!/usr/bin/env python3
"""Train/probe the Guna-sigmoid + Vritti heads on Mistral hidden states. HARNESS ONLY — not a training
claim, no runtime change, Bhava NOT trained. Doc: docs/CG_TRAINING_GUNA_VRITTI_HARNESS.md.

Modes:
  --dry-run            : torch random hidden states (no model download); verify shapes/loss/grad. CPU-safe
                         (needs torch; pod CPU is fine). -> CG_GUNA_VRITTI_SHAPE_ONLY_PASS.
  head_only (default)  : load Mistral (frozen), extract hidden states, train PROJECTOR + HEADS only.
  LoRA                 : optional future hook, DISABLED by default.
Writes a predictions cache (guna_scores, vritti_probs, labels, label_source) for eval_guna_vritti_probe.py.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))
from conscious_generation_training.guna_vritti_heads import (   # noqa: E402
    SymbolicHeadConfig, GUNA_DIM, VRITTI_DIM, HIDDEN_SIZE, formula_available, FORMULA_PROVENANCE)


def _torch():
    try:
        import torch  # noqa: F401
        return True
    except Exception:                                   # noqa: BLE001
        return False


def gpu_available():
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:                                   # noqa: BLE001
        return False


def dry_run(cfg: SymbolicHeadConfig, batch=4, seq=8, seed=0) -> dict:
    """Random hidden states -> shapes/loss/grad check. Returns a report dict. Requires torch."""
    import torch
    from conscious_generation_training.guna_vritti_heads import SymbolicHeadBundle
    torch.manual_seed(seed)
    bundle = SymbolicHeadBundle(cfg)
    h = torch.randn(batch, seq, cfg.hidden_size)
    out = bundle(h)
    guna_labels = (torch.rand(batch, cfg.guna_dim) > 0.5).float()
    vritti_labels = torch.randint(0, cfg.vritti_dim, (batch,))
    total, parts = bundle.loss(out, guna_labels, vritti_labels)
    total.backward()
    grad_ok = any(p.grad is not None and torch.isfinite(p.grad).all() for p in bundle.parameters())
    checks = {
        "state_shape": list(out["state"].shape) == [batch, cfg.symbolic_dim],
        "guna_shape": list(out["guna_scores"].shape) == [batch, cfg.guna_dim],
        "guna_in_unit_interval": bool((out["guna_scores"] >= 0).all() and (out["guna_scores"] <= 1).all()),
        "vritti_shape": list(out["vritti_probs"].shape) == [batch, cfg.vritti_dim],
        "vritti_sums_to_one": bool(torch.allclose(out["vritti_probs"].sum(-1), torch.ones(batch), atol=1e-4)),
        "loss_finite": bool(torch.isfinite(total)),
        "grad_finite": bool(grad_ok),
    }
    return {"mode": "dry_run", "checks": checks, "all_pass": all(checks.values()),
            "loss_parts": parts, "config": cfg.__dict__,
            "decision": "CG_GUNA_VRITTI_SHAPE_ONLY_PASS" if all(checks.values())
                        else "CG_GUNA_VRITTI_ENV_UNAVAILABLE"}


def train_head_only(cfg, model_id, data_path, output_dir, epochs=5, lr=1e-3, seed=0) -> dict:
    """Load Mistral (frozen), extract hidden states, train projector+heads on labels. GPU path."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from conscious_generation_training.guna_vritti_heads import SymbolicHeadBundle
    torch.manual_seed(seed)
    rows = [json.loads(l) for l in Path(data_path).read_text().splitlines() if l.strip()]
    label_sources = {r.get("metadata", {}).get("source", "placeholder") for r in rows}
    label_source = "real" if label_sources <= {"audit_derived", "human", "real"} else \
        ("synthetic" if "synthetic" in label_sources or "placeholder" in label_sources else "mixed")

    tok = AutoTokenizer.from_pretrained(model_id)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(model_id, device_map="auto", torch_dtype=torch.bfloat16,
                                                 output_hidden_states=True)
    model.eval()
    for p in model.parameters():
        p.requires_grad_(False)

    def extract(text):
        inp = tok(text, return_tensors="pt", truncation=True, max_length=512).to(model.device)
        with torch.no_grad():
            hs = model(**inp).hidden_states[cfg.hidden_layer]      # [1, T, H]
        return hs.float().cpu()

    states, guna_y, vritti_y = [], [], []
    from conscious_generation_training.guna_vritti_heads import pool_hidden, VRITTI_NAMES
    vmap = {n.lower(): i for i, n in enumerate(VRITTI_NAMES)}
    for r in rows:
        text = (r.get("prompt", "") + "\n" + r.get("response", "")).strip()
        states.append(pool_hidden(extract(text), cfg.pooling))
        lab = r.get("labels", {})
        guna_y.append(lab.get("guna", [0] * cfg.guna_dim))
        vritti_y.append(vmap.get(str(lab.get("vritti", "")).lower(), 0))
    S = torch.cat(states, 0)                                       # [N, H]
    GY = torch.tensor(guna_y, dtype=torch.float32)
    VY = torch.tensor(vritti_y, dtype=torch.long)

    bundle = SymbolicHeadBundle(cfg)
    opt = torch.optim.Adam([p for p in bundle.parameters() if p.requires_grad], lr=lr)
    for _ in range(epochs):
        opt.zero_grad()
        out = bundle(S)
        total, parts = bundle.loss(out, GY, VY)
        total.backward(); opt.step()
    with torch.no_grad():
        out = bundle(S)
        preds = {"guna_scores": out["guna_scores"].tolist(), "guna_labels": GY.tolist(),
                 "vritti_probs": out["vritti_probs"].tolist(), "vritti_labels": VY.tolist(),
                 "label_source": label_source, "n": len(rows), "final_loss": parts}
    out_dir = Path(output_dir); out_dir.mkdir(parents=True, exist_ok=True)
    torch.save(bundle.state_dict(), out_dir / "guna_vritti_heads.pt")
    (out_dir / "predictions.json").write_text(json.dumps(preds, indent=2))
    return {"mode": "head_only", "label_source": label_source, "n": len(rows),
            "saved": str(out_dir / "predictions.json")}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Guna/Vritti probe trainer (harness).")
    ap.add_argument("--model", default="mistralai/Mistral-7B-Instruct-v0.3")
    ap.add_argument("--data", default=None)
    ap.add_argument("--output", default="runs/cg_training/guna_vritti_probe")
    ap.add_argument("--mode", choices=("head_only", "lora"), default="head_only")
    ap.add_argument("--hidden-layer", type=int, default=-1)
    ap.add_argument("--pooling", choices=("last_token", "mean"), default="last_token")
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args(argv)

    if not formula_available():
        print("CG_GUNA_VRITTI_FORMULA_UNAVAILABLE"); return 1   # never invent a formula
    cfg = SymbolicHeadConfig(hidden_layer=args.hidden_layer, pooling=args.pooling,
                             use_lora=(args.mode == "lora"))
    cfg.use_lora = False                                        # LoRA hook OFF by default in this harness
    cfg.assert_probe_boundaries()
    Path(args.output).mkdir(parents=True, exist_ok=True)

    if args.dry_run or not args.execute or not gpu_available():
        if not _torch():
            print("CG_GUNA_VRITTI_ENV_UNAVAILABLE: torch not importable (dry-run needs torch)"); return 1
        rep = dry_run(cfg)
        (Path(args.output) / "dry_run.json").write_text(json.dumps(rep, indent=2))
        print(f"DRY-RUN all_pass={rep['all_pass']}  DECISION: {rep['decision']}")
        print(f"provenance: {FORMULA_PROVENANCE['guna']} | {FORMULA_PROVENANCE['vritti']}")
        return 0
    if not args.data:
        print("CG_GUNA_VRITTI_ENV_UNAVAILABLE: --data required for head_only training"); return 1
    rep = train_head_only(cfg, args.model, args.data, args.output, epochs=args.epochs)
    print(f"trained head_only n={rep['n']} label_source={rep['label_source']} -> {rep['saved']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
