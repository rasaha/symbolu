"""E1-S torch runtime tests (fixtures only). SKIPS (exit 0) when torch/numpy are unavailable."""
from __future__ import annotations

import pathlib
import shutil

FIXT = 886003
TMP = pathlib.Path("/tmp/claude-0/-home-user-symbolu/2ec1335e-f6de-58ee-b0b2-cf1663a48120/scratchpad/e1s_rt")


def _ok():
    try:
        import numpy, torch  # noqa: F401
        return True
    except ImportError:
        return False


def test_models_built_from_unchanged_e1_with_new_vocab():
    from .. import config as C, keyspace as KS, run as R
    from ..e1_import import E1_DIR
    import inspect
    e1, b0 = R.build_models(512, FIXT)
    assert pathlib.Path(inspect.getsourcefile(type(e1))).resolve().parent == E1_DIR
    assert e1.embed.num_embeddings == KS.VOCAB and b0.slot_keys.shape[0] == 512
    assert sum(p.numel() for p in e1.parameters()) == C.EXPECTED_E1_PARAMS == 22_848

def test_density_run_dump_rescore_and_determinism():
    from .. import run as R
    shutil.rmtree(TMP, ignore_errors=True)
    a = R.run_density(FIXT, 32, steps=30, n_eval=10, train_episodes=40, out_dir=TMP)
    b = R.run_density(FIXT, 32, steps=30, n_eval=10, train_episodes=40)
    assert a["e1_param_hash"] == b["e1_param_hash"] and a["metrics"] == b["metrics"]          # deterministic
    rs = R.rescore_predictions_file(TMP / f"predictions_fixture_{FIXT}_K32.jsonl")
    for split in ("G1_unseen_identity", "G6_no_match"):
        for k in ("addressing_top1", "e2e_retrieval_accuracy", "false_accept_rate"):
            if k in rs[split]:
                assert abs(rs[split][k] - a["e1"][split][k]) < 1e-6, (split, k)   # float32 vs python float
    assert set(a["gates"]["generalization"]) >= {"G1_unseen_identity", "G8_unseen_composition"}
    assert a["leakage"]["all_pass"] and a["anchor"] is True
    shutil.rmtree(TMP, ignore_errors=True)

def test_frozen_recipe_overrides_refused_on_reserved_roles_before_torch():
    from .. import run as R
    from ..execution import ExecutionNotAuthorized
    for s in (6100, 6140):
        try:
            R.run_density(s, 32, steps=5); assert False
        except ExecutionNotAuthorized:
            pass

def test_ladder_and_aggregate_on_fixture():
    from .. import run as R
    out = R.run_seed(FIXT, densities=(32, 128), steps=5, n_eval=4, train_episodes=8)
    assert set(out["densities"]) == {32, 128} and "anchor" in out
    agg = R.aggregate([out]); assert agg["primary_verdict"] in ("SHORTCUT_OR_LEAKAGE_DETECTED", "EXPLICIT_KEY_PROTOCOL_VIOLATED",
                                                                "EXPLICIT_KEY_SCALEUP_NOT_VALIDATED")
    assert agg["preserved"][:3] == ["ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED", "E1_TEMPORAL_TRANSFER_PARTIAL", "KDA_VALIDATION_BLOCKED"]


def main() -> int:
    if not _ok():
        print("SKIP: torch/numpy not installed (runtime checks not run)")
        return 0
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    p = f = 0
    for t in tests:
        try:
            t(); p += 1; print(f"PASS {t.__name__}")
        except Exception as exc:  # noqa: BLE001
            f += 1; print(f"FAIL {t.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{p} passed, {f} failed, {len(tests)} total")
    return 1 if f else 0


if __name__ == "__main__":
    raise SystemExit(main())
