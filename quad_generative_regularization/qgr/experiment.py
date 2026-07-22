"""End-to-end orchestration: pilot, screen, hard conditions, controls, verdict.

Implements the CPU validation sequence (spec section 16), positive-signal gate
(section 17), metrics (section 18), mechanism diagnostics (section 19), conditional
follow-ups (section 21), and result interpretation (sections 24-25).
"""

from __future__ import annotations

import copy
import json
import os
import statistics
import time
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

import torch

from .quad_model import QuadConfig
from .mqar import MQARConfig, split_seed
from .metrics import evaluate, quad_mechanism
from .train import TrainConfig, train_arm


# ----------------------------- configuration ------------------------------------------

@dataclass
class FrozenConfig:
    """The single frozen, preregistered protocol. Set once in the pilot, never re-tuned."""
    # model
    vocab_size: int = 32
    hidden_size: int = 96
    num_layers: int = 2
    num_heads: int = 4
    ff_size: int = 384
    context_length: int = 64
    dropout: float = 0.0
    aux_layer: int = -1
    # base MQAR (in-distribution)
    num_kv: int = 4
    num_queries: int = 2
    num_distractors: int = 0
    n_relation_systems: int = 1
    # training (shared across arms)
    steps: int = 2500
    batch_size: int = 32
    lr: float = 4e-3
    weight_decay: float = 0.0
    warmup: int = 50
    grad_clip: float = 1.0
    eval_every: int = 250
    eval_batches: int = 8
    grad_diag_every: int = 250
    # auxiliary (frozen in pilot)
    lambda_aux: float = 1.0
    tau: float = 1.0
    objective: str = "classification"
    # protocol
    screen_seeds: List[int] = field(default_factory=lambda: [0, 1, 2])
    confirm_seeds: List[int] = field(default_factory=lambda: [3, 4])
    acc_threshold: float = 0.80   # for "steps to threshold"

    def model_cfg(self) -> QuadConfig:
        return QuadConfig(self.vocab_size, self.hidden_size, self.num_layers, self.num_heads,
                          self.ff_size, self.context_length, self.dropout, self.aux_layer)

    def base_mqar(self) -> MQARConfig:
        return MQARConfig(self.num_kv, self.num_queries, self.num_distractors,
                          self.vocab_size, self.n_relation_systems)

    def train_cfg(self, arm: str, seed: int, shuffle: bool = False) -> TrainConfig:
        lam = self.lambda_aux
        return TrainConfig(arm=arm, lambda_aux=lam, tau=self.tau, objective=self.objective,
                           steps=self.steps, batch_size=self.batch_size, lr=self.lr,
                           weight_decay=self.weight_decay, warmup=self.warmup,
                           grad_clip=self.grad_clip, eval_every=self.eval_every,
                           eval_batches=self.eval_batches, grad_diag_every=self.grad_diag_every,
                           seed=seed, shuffle_aux_labels=shuffle)


# ----------------------------- hard conditions ----------------------------------------

def hard_condition_cfgs(fc: FrozenConfig) -> Dict[str, MQARConfig]:
    """Three preregistered generalization conditions (spec 10.2)."""
    return {
        "in_distribution": fc.base_mqar(),
        "longer_context": MQARConfig(fc.num_kv, fc.num_queries, num_distractors=32,
                                     vocab_size=fc.vocab_size, n_relation_systems=1),
        "higher_distractor": MQARConfig(num_kv=8, num_queries=fc.num_queries,
                                        num_distractors=fc.num_distractors,
                                        vocab_size=fc.vocab_size, n_relation_systems=1),
        "two_systems": MQARConfig(fc.num_kv, fc.num_queries, fc.num_distractors,
                                  vocab_size=fc.vocab_size, n_relation_systems=2),
    }


PREREGISTERED_HARD = ["longer_context", "higher_distractor", "two_systems"]


def eval_model_on_conditions(model, fc: FrozenConfig, seed: int,
                             n_batches: int = 12) -> Dict[str, float]:
    """Zero-shot accuracy of a trained model on each condition (disjoint test seeds)."""
    out = {}
    for name, mq in hard_condition_cfgs(fc).items():
        ev = evaluate(model, mq, seed, "test", n_batches, fc.batch_size)
        out[name] = ev["acc"]
    return out


def eval_seqlen_curve(model, fc: FrozenConfig, seed: int) -> Dict[int, float]:
    """Accuracy vs sequence length via increasing filler distractors."""
    curve = {}
    for nd in [0, 8, 16, 24, 32]:
        mq = MQARConfig(fc.num_kv, fc.num_queries, num_distractors=nd,
                        vocab_size=fc.vocab_size, n_relation_systems=1)
        ev = evaluate(model, mq, seed, "test", 8, fc.batch_size)
        L = mq.base_seq_len()
        curve[L] = ev["acc"]
    return curve


# ----------------------------- steps-to-threshold -------------------------------------

def steps_to_threshold(history: List[Dict], thr: float) -> Optional[int]:
    for h in history:
        if h["val_acc"] >= thr:
            return h["step"]
    return None


# ----------------------------- run one seed, all arms ---------------------------------

def run_seed(fc: FrozenConfig, seed: int, arms=("A", "C", "D"),
             shuffle_d: bool = False) -> Dict[str, Dict]:
    model_cfg = fc.model_cfg()
    base_mq = fc.base_mqar()
    out: Dict[str, Dict] = {}
    for arm in arms:
        shuffle = shuffle_d and arm == "D"
        r = train_arm(model_cfg, base_mq, fc.train_cfg(arm, seed, shuffle=shuffle))
        model = r["model"]
        conds = eval_model_on_conditions(model, fc, seed)
        seqlen = eval_seqlen_curve(model, fc, seed)
        mech = quad_mechanism(model, base_mq, seed, "test", 6, fc.batch_size) \
            if arm in ("C", "D") else {}
        out[arm] = {
            "seed": seed,
            "final_acc": r["final_val"]["acc"],
            "final_seq_acc": r["final_val"]["seq_acc"],
            "final_task_loss": r["final_val"]["task_loss"],
            "steps_to_threshold": steps_to_threshold(r["history"], fc.acc_threshold),
            "conditions": conds,
            "seqlen_curve": seqlen,
            "mechanism": mech,
            "history": r["history"],
            "grad_history": r["grad_history"],
            "mean_step_time": r["mean_step_time"],
            "total_train_time": r["total_train_time"],
            "num_params": r["num_params"],
        }
    return out


# ----------------------------- A vs D0 equivalence ------------------------------------

def check_a_vs_d0(fc: FrozenConfig, seed: int = 0, steps: int = 30) -> Dict:
    mc, mq = fc.model_cfg(), fc.base_mqar()
    tcfg = fc.train_cfg("A", seed)
    tcfg.steps = steps; tcfg.eval_every = 10**9; tcfg.grad_diag_every = 0; tcfg.log_curves = False
    rA = train_arm(mc, mq, tcfg)
    tcfg0 = fc.train_cfg("D0", seed)
    tcfg0.steps = steps; tcfg0.eval_every = 10**9; tcfg0.grad_diag_every = 0; tcfg0.log_curves = False
    rD0 = train_arm(mc, mq, tcfg0)
    pA, pD0 = dict(rA["model"].named_parameters()), dict(rD0["model"].named_parameters())
    max_diff = max(float((pA[n] - pD0[n]).abs().max()) for n in pA)
    return {"identical": max_diff == 0.0, "max_param_diff": max_diff, "steps": steps}


# ----------------------------- aggregation & gate -------------------------------------

def _agg(values: List[float]):
    return {"mean": statistics.mean(values),
            "std": statistics.pstdev(values) if len(values) > 1 else 0.0,
            "values": values}


def aggregate(per_seed: Dict[int, Dict[str, Dict]], arms=("A", "C", "D")) -> Dict:
    seeds = sorted(per_seed.keys())
    agg = {}
    for arm in arms:
        agg[arm] = {
            "final_acc": _agg([per_seed[s][arm]["final_acc"] for s in seeds]),
            "final_seq_acc": _agg([per_seed[s][arm]["final_seq_acc"] for s in seeds]),
            "final_task_loss": _agg([per_seed[s][arm]["final_task_loss"] for s in seeds]),
            "total_train_time": _agg([per_seed[s][arm]["total_train_time"] for s in seeds]),
            "mean_step_time": _agg([per_seed[s][arm]["mean_step_time"] for s in seeds]),
            "conditions": {},
        }
        for cond in hard_condition_cfgs_names():
            agg[arm]["conditions"][cond] = _agg(
                [per_seed[s][arm]["conditions"][cond] for s in seeds])
    return agg


def hard_condition_cfgs_names():
    return ["in_distribution"] + PREREGISTERED_HARD


def positive_signal_gate(agg: Dict, per_seed: Dict, grad_reaches_shared: bool) -> Dict:
    """Spec section 17."""
    seeds = sorted(per_seed.keys())
    dA = [per_seed[s]["D"]["final_acc"] - per_seed[s]["A"]["final_acc"] for s in seeds]
    same_dir = sum(1 for x in dA if x > 0.0)
    mean_D = agg["D"]["final_acc"]["mean"]
    mean_A = agg["A"]["final_acc"]["mean"]
    mean_C = agg["C"]["final_acc"]["mean"]
    practically_meaningful = (mean_D - mean_A) >= 0.10
    beats_C = mean_D > mean_C + 0.02
    hard_improved = [c for c in PREREGISTERED_HARD
                     if agg["D"]["conditions"][c]["mean"] > agg["A"]["conditions"][c]["mean"] + 0.05]
    criteria = {
        "1_same_direction_2of3": same_dir >= 2,
        "2_mean_D_exceeds_A_meaningful": practically_meaningful,
        "3_D_exceeds_C": beats_C,
        "4_improves_a_hard_condition": len(hard_improved) >= 1,
        "6_aux_grad_reaches_shared": grad_reaches_shared,
    }
    passed = all(criteria.values())
    label = "PROMISING_SIGNAL" if passed else (
        "NO_SIGNAL" if (mean_D - mean_A) < 0.02 else "MIXED")
    return {"criteria": criteria, "same_direction_count": same_dir,
            "mean_A": mean_A, "mean_C": mean_C, "mean_D": mean_D,
            "hard_improved": hard_improved, "label": label, "passed": passed}


def grad_reaches_shared(per_seed: Dict) -> bool:
    """True if Arm D's auxiliary gradient norm on shared params is nonzero across seeds."""
    ok = True
    for s in per_seed:
        gh = per_seed[s]["D"]["grad_history"]
        if not gh:
            ok = False
        else:
            ok = ok and any(g["aux_grad_norm"] > 0 for g in gh)
    return ok


# ----------------------------- classification (spec 24-25) ----------------------------

def classify_mechanism(agg: Dict, per_seed: Dict, shuffle_reproduces: Optional[bool]) -> str:
    seeds = sorted(per_seed.keys())
    d_beats_a = sum(1 for s in seeds
                    if per_seed[s]["D"]["final_acc"] > per_seed[s]["A"]["final_acc"] + 0.05)
    d_beats_c = sum(1 for s in seeds
                    if per_seed[s]["D"]["final_acc"] > per_seed[s]["C"]["final_acc"] + 0.05)
    n = len(seeds)
    if shuffle_reproduces:
        return "UNSUPPORTED"
    if d_beats_a >= max(2, n - 1) and d_beats_c >= max(2, n - 1):
        return "SUPPORTED"
    if d_beats_a >= max(2, n - 1) and d_beats_c < max(2, n - 1):
        return "LIMITED"
    if d_beats_a == 0:
        return "UNSUPPORTED"
    return "INCONCLUSIVE"


def classify_generalization(agg: Dict) -> str:
    improved = [c for c in PREREGISTERED_HARD
                if agg["D"]["conditions"][c]["mean"] > agg["A"]["conditions"][c]["mean"] + 0.05]
    if len(improved) >= 2:
        return "SUPPORTED"
    if len(improved) == 1:
        return "LIMITED"
    return "ABSENT"


def classify_economics(equal_wallclock_ran: bool) -> str:
    # The screen is an equal-TOKEN comparison (capability/convergence). Cost savings
    # require an equal-wall-clock comparison (spec 23.2), a conditional follow-up.
    return "NOT_MEASURED" if not equal_wallclock_ran else "NEUTRAL"


def three_seed_verdict(gate: Dict, equivalence_ok: bool, leakage_ok: bool) -> str:
    if not (equivalence_ok and leakage_ok):
        return "INVALID"
    return gate["label"]


def five_seed_verdict(mechanism: str, generalization: str, shuffle_reproduces: Optional[bool],
                      equivalence_ok: bool, leakage_ok: bool, agg: Dict) -> str:
    if not (equivalence_ok and leakage_ok):
        return "INVALID_DUE_TO_EXPERIMENTAL_FAILURE"
    if shuffle_reproduces:
        return "NOT_SUPPORTED"
    d_gt_a = agg["D"]["final_acc"]["mean"] > agg["A"]["final_acc"]["mean"] + 0.10
    if not d_gt_a:
        return "NOT_SUPPORTED"
    hard_ok = generalization in ("SUPPORTED",)  # at least two preregistered conditions
    if mechanism == "SUPPORTED" and hard_ok:
        return "SUPPORTED"
    if mechanism in ("SUPPORTED", "LIMITED") and not hard_ok and generalization != "ABSENT":
        return "SUPPORTED_WITH_LIMITED_CLAIM" if mechanism == "LIMITED" else "SUPPORTED_WITH_LIMITED_CLAIM"
    if mechanism == "LIMITED":
        return "SUPPORTED_WITH_LIMITED_CLAIM"
    return "INCONCLUSIVE"
