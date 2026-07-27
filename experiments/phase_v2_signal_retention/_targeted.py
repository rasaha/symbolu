"""Targeted V2-S/gate_sup vs V1 distance/dilution/ablation (acceptance-gate numbers)."""
import json
import time

from experiments.phase_guided_slots_v2.task_schema import build_vocab
from experiments.phase_v2_signal_retention.focus_data import generate_focus
from experiments.phase_v2_signal_retention.train import TrainCfg, train_focus
from experiments.phase_v2_signal_retention.distance_eval import run_distance
from experiments.phase_v2_signal_retention.dilution_eval import run_dilution
from experiments.phase_v2_signal_retention.ablations import run_ablations


def main():
    v = build_vocab()
    out = {}
    for name, mode in [("V1", "e2e"), ("V2-S", "gate_sup")]:
        t0 = time.time()

        def gen():
            return generate_focus(v, "train", 0, 300, 24, 256)

        m, _ = train_focus(name, gen, v.pad_id,
                           TrainCfg(steps=250, mode=mode, rho=0.1, seed=0), v.size)
        d = run_distance(m, v, seed=201, n=160)
        dil = run_dilution(m, v, seed=301, n=160)
        ab = run_ablations(m, v, seed=401, n=200) if name != "V1" else {}
        out[f"{name}/{mode}"] = {"distance": d, "dilution": dil, "ablations": ab}
        print(f"=== {name}/{mode} ({round(time.time()-t0)}s) ===", flush=True)
        print("  distance(state):", {k: round(d[k]["phase_top1"], 3) for k in d}, flush=True)
        print("  dilution(g):", {k: round(dil[k]["phase_top1"], 3) for k in dil}, flush=True)
        if ab:
            print("  ablations(g):", {k: (round(x, 3) if isinstance(x, float) else x)
                                      for k, x in ab.items()}, flush=True)
    json.dump(out, open("experiments/phase_v2_signal_retention/results/targeted.json", "w"),
              indent=2, default=float)
    print("TARGETED DONE", flush=True)


if __name__ == "__main__":
    main()
