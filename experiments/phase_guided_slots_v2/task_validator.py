"""
task_validator.py — Stage A gate: does the task create GENUINE capacity pressure
and is plain-slot C failing through real eviction (not leakage/matching collapse)?

Trains A (local only) and C (local + slots) at a pressure config, then checks the
validity thresholds from the redesign spec §14/§18 against C:

  capacity_saturation_rate >= 0.80
  frac_time_full           > 0.25
  evictions                > 1 per example
  early_target_eviction    > 0.20   (1 - early target survival)
  target_survival          in [0.30, 0.80]
  topk_support_recall      < 0.80
  C answer_acc             in [0.30, 0.70]  (decisive window 0.30-0.65 preferred)
  merge_of_distinct_rate   low       (distinct facts occupy distinct slots)

PASS requires the capacity/eviction conditions AND C in the failure window.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import torch

from experiments.phase_guided_slots_v2.guided_models_v2 import GCfg2, build_v2
from experiments.phase_guided_slots_v2.task_schema import build_vocab
from experiments.phase_guided_slots_v2.datasets_pressure_v2 import generate
from experiments.phase_guided_slots_v2.train_eval import TCfg, train, evaluate
from experiments.phase_guided_slots_v2.memory_trace import trace_dataset

HERE = Path(__file__).resolve().parent
CKPT = HERE / "results" / "ckpt"
CKPT.mkdir(parents=True, exist_ok=True)

torch.set_num_threads(4)


@dataclass
class PCfg:
    M: int = 8
    top_k: int = 2
    n_live: int = 32          # distinct live contracts (pressure = n_live / M)
    embed_dim: int = 96
    num_heads: int = 4
    local_window: int = 16
    max_seq_len: int = 1400
    steps: int = 400
    lambda_write: float = 1.0
    lambda_keydiv: float = 0.5      # keep distinct composite identities on distinct keys
    match_threshold: float = 0.85   # constructor arg to GuidedBoundedSlots (module unmodified)
    gate_bias_init: float = -3.0    # start writing rarely; BCE raises gate at anchors
    n_train: int = 400
    n_val: int = 60
    n_test: int = 120
    query_type: str = "latest_value"

    @property
    def pressure(self):
        return self.n_live / self.M


def make_data(vocab, pc: PCfg, seed: int):
    tr = generate(vocab, "train", seed, pc.n_train, pc.n_live, pc.M, query_type=pc.query_type)
    va = generate(vocab, "val", 500 + seed, pc.n_val, pc.n_live, pc.M, query_type=pc.query_type)
    te = generate(vocab, "test", 1000 + seed, pc.n_test, pc.n_live, pc.M, query_type=pc.query_type)
    return tr, va, te


def train_arm(arm: str, pc: PCfg, seed: int, force=False):
    vocab = build_vocab()
    cfg = GCfg2(vocab_size=vocab.size, embed_dim=pc.embed_dim, num_heads=pc.num_heads,
                local_window=pc.local_window, num_slots=pc.M, top_k=pc.top_k,
                max_seq_len=pc.max_seq_len, match_threshold=pc.match_threshold,
                gate_bias_init=pc.gate_bias_init)
    tag = f"{arm}_M{pc.M}_K{pc.top_k}_L{pc.n_live}_s{seed}"
    path = CKPT / f"{tag}.pt"
    m = build_v2(cfg, arm, seed)
    if path.exists() and not force:
        m.load_state_dict(torch.load(path, map_location="cpu"))
        meta = json.loads((CKPT / f"{tag}.json").read_text())
        return m, vocab, meta, tag
    tr, va, te = make_data(vocab, pc, seed)
    trlog = train(m, tr, vocab.pad_id, TCfg(steps=pc.steps, lambda_write=pc.lambda_write,
                                            lambda_keydiv=pc.lambda_keydiv, seed=seed), val=va)
    metrics = evaluate(m, te, vocab.pad_id)
    trace = trace_dataset(m, te, vocab.pad_id)
    torch.save(m.state_dict(), path)
    meta = {"arm": arm, "tag": tag, "pcfg": pc.__dict__, "seed": seed,
            "pressure": pc.pressure, "train": trlog, "metrics": metrics, "trace": trace}
    (CKPT / f"{tag}.json").write_text(json.dumps(meta, indent=2, default=float))
    return m, vocab, meta, tag


def gate(cmeta: dict) -> Dict:
    tr = cmeta["trace"]; me = cmeta["metrics"]
    acc = me["answer_acc"]
    early_surv = tr["by_target_position"]["early"]["target_survival_rate"]
    conds = {
        "capacity_saturation>=0.80": tr["capacity_saturation_rate"] >= 0.80,
        "frac_time_full>0.25": tr["frac_time_full"] > 0.25,
        "evictions>1": tr["evictions"] > 1.0,
        "early_target_eviction>0.20": (1.0 - early_surv) > 0.20,
        "target_survival_in_0.30_0.80": 0.30 <= tr["target_survival_rate"] <= 0.80,
        "topk_support_recall<0.80": tr["topk_support_recall"] < 0.80,
        "C_acc_in_0.30_0.70": 0.30 <= acc <= 0.70,
        "distinct_slots (merge_rate<2)": tr["merge_of_distinct_rate"] < 2.0,
    }
    return {"conditions": conds, "PASS": all(conds.values()),
            "C_answer_acc": acc, "early_target_survival": early_surv,
            "capacity_saturation": tr["capacity_saturation_rate"],
            "evictions": tr["evictions"], "target_survival": tr["target_survival_rate"],
            "topk_support_recall": tr["topk_support_recall"],
            "merge_of_distinct_rate": tr["merge_of_distinct_rate"]}
