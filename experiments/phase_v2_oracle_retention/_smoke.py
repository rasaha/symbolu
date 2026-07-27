import time
import torch
from experiments.phase_guided_slots_v2.task_schema import build_vocab
from experiments.phase_guided_slots_v2 import datasets_pressure_v2 as D
from experiments.phase_v2_oracle_retention.retention_model import OCfg, RetentionModel
from experiments.phase_v2_oracle_retention.train_eval import TCfg, train_curriculum, evaluate

v = build_vocab()


def gen_fn(n_live):
    return D.generate(v, "train", 0, 300, n_live, 8, focus_retention=True)


if __name__ == "__main__":
    for arm in ["C-oracle", "D-v2", "D-zero", "D-random", "D-shuffled"]:
        t0 = time.time()
        torch.manual_seed(0)
        m = RetentionModel(OCfg(vocab_size=v.size, lambda_fixed=0.25), arm)
        train_curriculum(m, gen_fn, v.pad_id, [(4, 120), (8, 150), (12, 200)], TCfg(seed=0))
        te = D.generate(v, "test", 100, 150, 12, 8, focus_retention=True)
        r = evaluate(m, te, v.pad_id)
        print(f"{arm}: acc={r['answer_acc']:.3f} surv={r['target_survival_rate']:.3f} "
              f"acc|surv={r['acc_given_survived']:.3f} acc|evict={r['acc_given_evicted']:.3f} "
              f"early_surv={r['survival_by_target_position']['early']} "
              f"evict={r['evictions']:.1f} ({round(time.time()-t0)}s)", flush=True)
    print("SMOKE DONE", flush=True)
