#!/usr/bin/env python3
"""inspect_bhava_csr_sample.py — per-example trace viewer for the Bhava + CSR probe.

Interpretability/debugging only (no training, no generation injection, no governance). Reads an
existing probe run dir (features.npz, labels.json, results.json, config.json) and, for selected
examples, prints a human-readable trace of every C/S/R component + per-component probe scores +
agreement diagnostics, so you can see whether CSR is a coherence field or just diluting Resonance.

Per-example probe scores are recomputed here (out-of-fold) from features.npz with the same
per-group PCA the report uses — nothing in the trainer changes.

Usage:
  python scripts/cg_wrapper_ablation/inspect_bhava_csr_sample.py --run-dir runs/bhava_probe/<ts> --id <id>
  ... --top-correct --limit 5     ... --top-incorrect --limit 5     ... --surprising --limit 10
Optionally --data <probe.jsonl> for prompt/expected/model-output (else printed as unavailable).
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cg_ablation import probe_features as PF      # noqa: E402
from cg_ablation import probe_train as PT          # noqa: E402

BHAVA_NAMES = ['POT', 'IDN', 'EXE', 'STR', 'COG', 'AGY', 'RSN', 'PRP', 'WIT', 'UNI', 'INT', 'ABS']

# probe sets we score per example (only those whose keys are present are used)
TRACE_SETS = ["hidden_only", "state_bhava_only", "resonance_combined", "context_r_ctx_only",
              "semantic_only", "csr_static", "state_bhava_plus_resonance",
              "phoneme_bhava_only", "vritti_consonant_only"]


def _vowel_vritti_labels():
    try:
        import varna_mapping as VM
        vowels = sorted({v["varna"] for v in VM.VOWEL_STATES.values()})
        vrittis = sorted({e.get("english", str(e)) for e in VM.VRITTI_LABELS.values()})
        return vowels, vrittis
    except Exception:
        return None, None


def load_run(run_dir: Path, label_type: str):
    import numpy as np
    npz = np.load(run_dir / "features.npz")
    arrays = {k: npz[k] for k in npz.files}
    labels = json.loads((run_dir / "labels.json").read_text())
    cfg = json.loads((run_dir / "config.json").read_text()) if (run_dir / "config.json").exists() else {}
    idx = [i for i, l in enumerate(labels) if l["label_type"] == label_type]
    if not idx:
        raise SystemExit(f"no examples with label_type={label_type} in {run_dir}")
    idx = np.asarray(idx)
    y = np.asarray([labels[i]["label"] for i in idx], dtype=int)
    ids = [labels[i]["id"] for i in idx]
    # per-example OOF probability per available set (same per-group PCA as the report)
    scores = {}
    avail = PF.available_sets_arrays(arrays)
    for s in TRACE_SETS:
        if s in avail:
            groups = PF.group_arrays_for_set(arrays, s, idx)
            oof, _ = PT._oof_from_groups(groups, y, PF.HIDDEN_KEYS, 24, "logreg", 5, 1.0, 0)
            scores[s] = oof
    return arrays, idx, y, ids, scores, cfg, avail


def _agree(a, b):
    """same-side-of-0.5 agreement between two probabilities."""
    return (a >= 0.5) == (b >= 0.5)


def trace_one(i, pos, arrays, idx, y, ids, scores, data_by_id):
    """Build the human-readable trace string for example position `pos` (within the subset)."""
    import numpy as np
    ex_id = ids[pos]
    gi = idx[pos]
    label = int(y[pos])
    L = []
    L.append("=" * 60)
    L.append(f"ID: {ex_id}   label_type: correctness   gold: {'correct' if label else 'incorrect'}")
    d = data_by_id.get(ex_id)
    if d:
        L.append(f"\nPrompt:\n  {d.get('prompt','')[:300]}")
        L.append(f"Expected: {d.get('expected','')}")
        gen = (d.get("metadata") or {}).get("generation")
        L.append(f"Model output: {gen[:160] if gen else 'model_output_unavailable: true'}")
    else:
        L.append("  prompt/model_output_unavailable: true (pass --data to join)")

    def sc(name):
        return float(scores[name][pos]) if name in scores else None
    L.append("\nPrediction scores (OOF P(correct), same folds/PCA as report):")
    for s in TRACE_SETS:
        v = sc(s)
        if v is not None:
            mark = "✓" if _agree(v, label) else "✗"
            L.append(f"  {s:<28} {v:.3f}  ({'pred-correct' if v>=0.5 else 'pred-incorrect'}) {mark}vs-gold")

    # state-Bhava
    if "state_bhava" in arrays:
        sb = arrays["state_bhava"][gi]
        dom = int(np.argmax(sb))
        ent = float(arrays.get("state_bhava_entropy", np.zeros((len(idx) and 1, 1)))[gi][0]) \
            if "state_bhava_entropy" in arrays else float("nan")
        L.append("\nState-Bhava (learned hidden summary):")
        L.append(f"  dominant: {BHAVA_NAMES[dom] if dom < len(BHAVA_NAMES) else dom}  "
                 f"(idx {dom})   entropy: {ent:.3f}")
        L.append(f"  vector: {np.round(sb, 3).tolist()}")

    vowels, vrittis = _vowel_vritti_labels()
    if "phoneme_bhava" in arrays:
        pb = arrays["phoneme_bhava"][gi]
        dom = int(np.argmax(pb)) if pb.sum() else -1
        lab = (vowels[dom] if (vowels and 0 <= dom < len(vowels)) else dom)
        L.append("\nPhoneme-Bhava (vowel -> cognitive mode):")
        L.append(f"  dominant vowel-mode: {lab}   vector: {np.round(pb, 3).tolist()}")
    if "vritti_consonant" in arrays:
        vc = arrays["vritti_consonant"][gi]
        dom = int(np.argmax(vc)) if vc.sum() else -1
        lab = (vrittis[dom] if (vrittis and 0 <= dom < len(vrittis)) else dom)
        L.append("Vritti (consonant -> motion tendency):")
        L.append(f"  dominant motion: {lab}   vector: {np.round(vc, 3).tolist()}")
    if "resonance_combined" in arrays:
        rc = arrays["resonance_combined"][gi]
        top = np.argsort(-np.abs(rc))[:3].tolist()
        L.append(f"\nResonance (12D varna affinity): norm={float(np.linalg.norm(rc)):.3f} "
                 f"top-dims={top}")
    if "context_r_ctx" in arrays:
        rx = arrays["context_r_ctx"][gi]
        L.append(f"Context r_ctx (16D): norm={float(np.linalg.norm(rx)):.3f} "
                 f"top-dims={np.argsort(-np.abs(rx))[:3].tolist()}")
    if "semantic" in arrays:
        se = arrays["semantic"][gi]
        L.append(f"Semantic (input-emb pooled, {se.shape[0]}D): norm={float(np.linalg.norm(se)):.3f}")

    # CSR coherence diagnostics
    hid, res, csr = sc("hidden_only"), sc("resonance_combined"), sc("csr_static")
    sb_s, ctx_s, sem_s = sc("state_bhava_only"), sc("context_r_ctx_only"), sc("semantic_only")
    L.append("\nAgreement (same-side-of-0.5):")
    def ag(a, b, na, nb):
        if a is None or b is None:
            return f"  {na} vs {nb}: n/a"
        return f"  {na} vs {nb}: {'AGREE' if _agree(a,b) else 'DISAGREE'} ({a:.2f} / {b:.2f})"
    L.append(ag(sb_s, res, "state_bhava", "resonance"))
    L.append(ag(sb_s, sem_s, "state_bhava", "semantic"))
    L.append(ag(res, sem_s, "resonance", "semantic"))
    L.append(ag(csr, hid, "csr_static", "hidden"))
    # is CSR diluting resonance? (only flag meaningful dilution, not trivial rounding)
    if csr is not None and res is not None:
        if abs(res - label) < abs(csr - label) - 0.05:
            L.append(f"  ⚠ CSR appears to DILUTE resonance (resonance {res:.2f} closer to gold "
                     f"{label} than csr_static {csr:.2f}).")
        elif _agree(csr, label) and not _agree(res, label):
            L.append(f"  CSR rescued a wrong resonance ({res:.2f}->{csr:.2f}).")
    if csr is not None and sem_s is not None and sb_s is not None:
        if _agree(csr, sem_s) and not _agree(csr, sb_s):
            L.append("  note: csr_static agrees with semantic but not state_bhava.")
    return "\n".join(L)


def select(mode, y, scores, limit):
    """Return positions to display for a selection mode."""
    import numpy as np
    n = len(y)
    res = scores.get("resonance_combined")
    sb = scores.get("state_bhava_only")
    hid = scores.get("hidden_only")
    csr = scores.get("csr_static")
    bhava_csr = res if res is not None else sb  # 'Bhava/CSR' confidence proxy

    if mode == "top_correct" and bhava_csr is not None:
        order = [i for i in np.argsort(-bhava_csr) if y[i] == 1]
    elif mode == "top_incorrect" and bhava_csr is not None:
        # high-confidence-correct prediction but actually incorrect (confident-wrong)
        order = [i for i in np.argsort(-bhava_csr) if y[i] == 0]
    elif mode == "surprising" and hid is not None and bhava_csr is not None:
        dis = [i for i in range(n) if (hid[i] >= 0.5) != (bhava_csr[i] >= 0.5)]
        order = sorted(dis, key=lambda i: -abs(hid[i] - bhava_csr[i]))
    elif mode == "csr_dilutes" and csr is not None and res is not None:
        order = sorted(range(n), key=lambda i: -(abs(csr[i] - y[i]) - abs(res[i] - y[i])))
    else:
        order = list(range(n))
    return order[:limit]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--data", default=str(Path(__file__).resolve().parent / "probe_data" / "probe_balanced.jsonl"))
    ap.add_argument("--label-type", default="correctness")
    ap.add_argument("--id", default=None)
    ap.add_argument("--top-correct", action="store_true")
    ap.add_argument("--top-incorrect", action="store_true")
    ap.add_argument("--surprising", action="store_true")
    ap.add_argument("--csr-dilutes", action="store_true")
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    arrays, idx, y, ids, scores, cfg, avail = load_run(run_dir, args.label_type)

    data_by_id = {}
    dp = Path(args.data)
    if dp.exists():
        for line in dp.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    r = json.loads(line); data_by_id[r["id"]] = r
                except Exception:
                    pass

    print(f"run={run_dir}  label_type={args.label_type}  n={len(y)}  "
          f"sets_scored={sorted(scores)}")
    if args.id:
        if args.id not in ids:
            print(f"id {args.id} not found (have {len(ids)} ids)"); return 2
        positions = [ids.index(args.id)]
    else:
        mode = ("top_correct" if args.top_correct else "top_incorrect" if args.top_incorrect
                else "surprising" if args.surprising else "csr_dilutes" if args.csr_dilutes else "all")
        positions = select(mode, y, scores, args.limit)
        print(f"mode={mode}  showing {len(positions)} of {len(y)}")
    for pos in positions:
        print(trace_one(None, pos, arrays, idx, y, ids, scores, data_by_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
