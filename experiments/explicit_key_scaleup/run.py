"""E1-S harness: density-ladder train/eval, predictions dump, offline rescorer, anchor check, report.

Training loops replicate experiments/bindingslots_e1/engine.py::train_e1 / train_b0 line for line (same
optimizer, loss, sampling RNG scheme); they are re-implemented ONLY because E1's versions construct
`E1()` / `B0()` with E1's task defaults (vocab 250, 32 slots), whereas this package must pass its own
vocabulary and density. Evaluation (`eval_e1`, `eval_b0`), `collate`, `param_hash` and
`set_determinism` are E1's functions, imported unchanged. Fail-closed: every entry point guards the seed
before torch is imported.
"""
from __future__ import annotations

import json
import pathlib
import random

from . import config as C
from . import gates as G
from . import keyspace as KS
from . import leakage as L
from . import manifest as MAN
from . import shortcuts as SC
from .execution import assert_generation_allowed


def _role_for(seed: int) -> str:
    return C.RESERVED_SEED_ROLES.get(int(seed), "fixture")


def _pool_for(seed: int) -> list:
    role = _role_for(seed)
    return KS.identity_pools()[{"development": "dev", "final": "final"}.get(role, "dev")]


# ---------------------------------------------------------------- torch path (lazy)
def build_models(K: int, seed: int):
    """E1 and B0 for density K with this package's vocabulary; E1 classes imported unchanged."""
    from .e1_import import e1_engine, e1_models
    eng, mod = e1_engine(), e1_models()
    eng.set_determinism(int(seed))
    e1 = mod.E1(d=C.D, vocab=KS.VOCAB)
    b0 = mod.B0(d=C.D, vocab=KS.VOCAB, n_slots=K, n_values=KS.N_VALUES)
    n_e1 = sum(p.numel() for p in e1.parameters()); n_b0 = sum(p.numel() for p in b0.parameters())
    assert n_e1 == C.EXPECTED_E1_PARAMS == C.e1_param_count(), (n_e1, C.EXPECTED_E1_PARAMS)
    assert n_b0 == C.b0_param_count(K), (n_b0, C.b0_param_count(K))
    return e1, b0


def train_e1(train_eps, seed, *, steps=C.STEPS, batch=C.BATCH, lr=C.LR, tau=C.TAU, loss_log=None):
    import torch
    import torch.nn.functional as F
    from .e1_import import e1_engine, e1_models
    eng, mod = e1_engine(), e1_models()
    eng.set_determinism(int(seed))
    m = mod.E1(d=C.D, vocab=KS.VOCAB)
    opt = torch.optim.Adam(m.parameters(), lr=lr)
    rng = random.Random(int(seed) ^ 0x51ED)
    m.train()
    for step in range(steps):
        idx = [rng.randrange(len(train_eps)) for _ in range(batch)]
        kt, kv, qt, ti, tv = eng.collate([train_eps[i] for i in idx])
        logits = m(kt, qt, tau)
        K = kt.size(1)
        target = torch.where(ti >= 0, ti, torch.full_like(ti, K))
        loss = F.cross_entropy(logits, target)
        opt.zero_grad(); loss.backward(); opt.step()
        if loss_log is not None and (step % 100 == 99 or step == steps - 1):
            loss_log.append((step + 1, float(loss.detach())))
    m.eval()
    return m


def train_b0(train_eps, seed, K, *, steps=C.STEPS, batch=C.BATCH, lr=C.LR):
    import torch
    import torch.nn.functional as F
    from .e1_import import e1_engine, e1_models
    eng, mod = e1_engine(), e1_models()
    eng.set_determinism(int(seed))
    m = mod.B0(d=C.D, vocab=KS.VOCAB, n_slots=K, n_values=KS.N_VALUES)
    opt = torch.optim.Adam(m.parameters(), lr=lr)
    rng = random.Random(int(seed) ^ 0x0B0)
    valid = [e for e in train_eps if e["target_index"] >= 0]
    m.train()
    for _ in range(steps):
        idx = [rng.randrange(len(valid)) for _ in range(batch)]
        kt, kv, qt, ti, tv = eng.collate([valid[i] for i in idx])
        loss = F.cross_entropy(m(kt, qt), tv)
        opt.zero_grad(); loss.backward(); opt.step()
    m.eval()
    return m


def predict_rows(e1, eps, split, K, tau=C.TAU) -> list:
    """Per-example prediction rows for the dump: everything the rescorer needs, nothing more."""
    import torch
    from .e1_import import e1_engine
    eng = e1_engine()
    rows = []
    with torch.no_grad():
        kt, kv, qt, ti, tv = eng.collate(eps)
        logits = e1(kt, qt, tau)
        pred_all = logits.argmax(-1); pred_key = logits[:, :K].argmax(-1)
        top2 = logits.topk(2, dim=1).values; margin = (top2[:, 0] - top2[:, 1])
        for i, e in enumerate(eps):
            pa = int(pred_all[i]); pk = int(pred_key[i])
            rows.append({"split": split, "K": K, "target_index": int(ti[i]), "target_value": int(tv[i]),
                         "pred_all": pa, "pred_key": pk, "abstained": pa == K,
                         "chosen_value": (int(kv[i, pa]) if pa < K else None), "margin": round(float(margin[i]), 5)})
    return rows


def run_density(seed: int, K: int, *, authorization_token=None, steps=None, n_eval=None, train_episodes=None,
                out_dir=None) -> dict:
    """Train E1 and B0 at density K, evaluate G1-G8 on the seed's pool, score gates, dump predictions."""
    assert_generation_allowed(seed, authorization_token)
    role = _role_for(seed)
    if role in ("development", "final") and (steps is not None or n_eval is not None or train_episodes is not None):
        raise ValueError(f"{role} seed {seed}: overriding the frozen recipe is inadmissible")
    steps = C.STEPS if steps is None else steps
    n_eval = C.EVAL_N_PER_SPLIT if n_eval is None else n_eval
    train_episodes = C.TRAIN_EPISODES if train_episodes is None else train_episodes
    from .e1_import import e1_engine
    eng = e1_engine()
    train_eps = KS.build_train_split(train_episodes, C.TRAIN_SEED_FOR_EPISODES, K, C.TRAIN_NO_MATCH_FRAC)
    evals = KS.build_eval_splits(_pool_for(seed), n_eval, int(seed), K)
    leak = L.run_all(evals, train_eps)
    loss_log: list = []
    e1 = train_e1(train_eps, seed, steps=steps, loss_log=loss_log)
    b0 = train_b0(train_eps, seed, K, steps=steps)
    h_e1, h_b0 = eng.param_hash(e1), eng.param_hash(b0)
    e1_res = {name: eng.eval_e1(e1, eps, C.TAU) for name, eps in evals.items()}
    b0_res = {name: eng.eval_b0(b0, eps) for name, eps in evals.items()}
    assert eng.param_hash(e1) == h_e1 and eng.param_hash(b0) == h_b0, "model mutated during evaluation"
    metrics = G.seed_density_metrics(e1_res, b0_res["G1_unseen_identity"]["e2e_retrieval_accuracy"])
    gates = G.eval_gates(metrics)
    suite = SC.run_suite(evals["G1_unseen_identity"], metrics["G1_e2e"], C.GATES["structure_blind_margin"])
    rows = [r for name, eps in evals.items() for r in predict_rows(e1, eps, name, K)]
    rep = {"schema": "e1s/density_report/v1", "arm": C.ARM_NAME, "seed": seed, "role": role, "K": K,
           "config_digest": MAN.config_digest(), "e1_param_hash": h_e1, "b0_param_hash": h_b0,
           "recipe": {"steps": steps, "n_eval_per_split": n_eval, "train_episodes": train_episodes},
           "loss_curve": [(s, round(l, 4)) for s, l in loss_log],
           "e1": e1_res, "b0": b0_res, "metrics": metrics, "gates": gates, "leakage": leak,
           "structure_blind": suite, "anchor": (K == C.ANCHOR_DENSITY)}
    if out_dir:
        d = pathlib.Path(out_dir); d.mkdir(parents=True, exist_ok=True)
        (d / f"report_{role}_{seed}_K{K}.json").write_text(json.dumps(rep, indent=2, default=str))
        with (d / f"predictions_{role}_{seed}_K{K}.jsonl").open("w") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        rep["report_path"] = str(d / f"report_{role}_{seed}_K{K}.json")
    return rep


def anchor_check(rep: dict) -> dict:
    """K=32 replication anchor (draft §2): every primary gate must pass; otherwise PROTOCOL_VIOLATED."""
    assert rep["K"] == C.ANCHOR_DENSITY
    return {"anchor_ok": bool(rep["gates"]["all_primary_pass"]), "K": rep["K"],
            "failed": [k for grp in ("generalization", "nomatch", "e2e", "stable")
                       for k, v in rep["gates"][grp].items() if not v]}


def run_seed(seed: int, *, authorization_token=None, out_dir=None, densities=C.DENSITIES, **overrides) -> dict:
    """Full ladder for one seed: anchor first (K=32), then the rest. Returns per-density reports + anchor."""
    assert_generation_allowed(seed, authorization_token)
    out = {"seed": seed, "role": _role_for(seed), "densities": {}}
    for K in densities:
        out["densities"][K] = run_density(seed, K, authorization_token=authorization_token, out_dir=out_dir, **overrides)
    if C.ANCHOR_DENSITY in out["densities"]:
        out["anchor"] = anchor_check(out["densities"][C.ANCHOR_DENSITY])
    return out


def aggregate(seed_runs: list, *, determinism_ok: bool = True) -> dict:
    """Mechanical verdict over completed seed runs (draft §7)."""
    per_seed = [{"densities": {K: {"metrics": r["metrics"], "gates": r["gates"]} for K, r in s["densities"].items()}}
                for s in seed_runs]
    leakage_ok = all(r["leakage"]["all_pass"] for s in seed_runs for r in s["densities"].values())
    shortcut = any(r["structure_blind"]["shortcut_detected"] for s in seed_runs for r in s["densities"].values())
    anchor_ok = all(s.get("anchor", {}).get("anchor_ok", False) for s in seed_runs)
    primary, preserved = G.verdict(per_seed, leakage_ok=leakage_ok, determinism_ok=determinism_ok,
                                   shortcut_detected=shortcut, anchor_ok=anchor_ok)
    G.assert_verdict_admissible(primary, preserved)
    return {"primary_verdict": primary, "preserved": preserved, "n_seeds": len(seed_runs),
            "leakage_ok": leakage_ok, "shortcut_detected": shortcut, "anchor_ok": anchor_ok,
            "config_digest": MAN.config_digest()}


# ---------------------------------------------------------------- offline rescorer (torch-free)
def rescore_predictions_file(path) -> dict:
    """Recompute addressing / e2e / false-accept / false-reject per split from a predictions dump."""
    by: dict = {}
    for line in pathlib.Path(path).read_text().splitlines():
        if line.strip():
            r = json.loads(line); by.setdefault(r["split"], []).append(r)
    out = {}
    for split, rows in by.items():
        valid = [r for r in rows if r["target_index"] >= 0]; nm = [r for r in rows if r["target_index"] < 0]
        o = {"n": len(rows), "K": rows[0]["K"]}
        if valid:
            o["addressing_top1"] = sum(r["pred_key"] == r["target_index"] for r in valid) / len(valid)
            o["e2e_retrieval_accuracy"] = sum((not r["abstained"]) and r["chosen_value"] == r["target_value"] for r in valid) / len(valid)
            o["false_reject_rate"] = sum(r["abstained"] for r in valid) / len(valid)
        if nm:
            o["false_accept_rate"] = sum(not r["abstained"] for r in nm) / len(nm)
        out[split] = o
    return out
