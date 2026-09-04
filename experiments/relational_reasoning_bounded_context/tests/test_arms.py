"""Sibling-arm registry, per-arm guard, digest extension, companion JSON and record (torch-free; fixtures only)."""
from __future__ import annotations

import json
import pathlib

from .. import config as C
from .. import generator as gen
from .. import manifest as MAN
from ..execution import ExecutionNotAuthorized, guard_seed, load_signed_record, record_path_for

FIXT = 883000
BENCH = pathlib.Path(__file__).resolve().parents[3] / "docs/research/hybrid_llm/benchmarks"


def test_registry_consistency():
    assert set(C.ARMS) == {"ABS", "ROPE"}
    assert C.ARMS["ABS"]["positional_mechanism"] == "learned_absolute" and C.ARMS["ABS"]["ratified"] is True
    assert {spec["status"] for spec in C.ARMS.values()} == {"CLOSED"}
    assert C.ARMS["ROPE"]["positional_mechanism"] == "rope" and C.ARMS["ROPE"]["ratified"] is False
    assert C.ARMS["ABS"]["max_updates"] == C.MAX_UPDATES == 2000
    assert C.arm_param_count("ABS") == (394_752, 131_392)
    assert C.arm_param_count("ROPE") == (144_896, 131_392)
    assert C.arm_param_count("ROPE")[0] == 394_752 - 3904 * 64

def test_both_arms_closed_and_fail_closed_even_with_a_signed_record():
    import hashlib, json, os
    from ..execution import _evaluate_authorization, guard_seed
    assert C.ARMS["ABS"]["status"] == "CLOSED" and C.ARMS["ROPE"]["status"] == "CLOSED"
    # the two-key evaluation still works in isolation (audit of historical signatures) ...
    tok = "closure-test-token"
    rec = {"roles": {"smoke": {"authorized": True, "scope_seeds": [8100], "expires_at": None,
                               "token_sha256": hashlib.sha256(tok.encode()).hexdigest(),
                               "protocol_lock_digest": MAN.config_digest("ABS")}}}
    assert _evaluate_authorization("smoke", 8100, tok, rec, "ABS").authorized
    # ... but the guard refuses every reserved seed of a CLOSED arm before consulting any record or token
    for s in (8100, 8101, 81600, 8200, 8201, 81700):
        try:
            guard_seed(s, tok); assert False, s
        except ExecutionNotAuthorized as exc:
            assert "CLOSED" in str(exc), exc
    assert guard_seed(FIXT).authorized


def test_seed_blocks_disjoint_and_classified():
    abs_seeds = {s for seeds in C.ARMS["ABS"]["seeds"].values() for s in seeds}
    rope_seeds = {s for seeds in C.ARMS["ROPE"]["seeds"].values() for s in seeds}
    assert abs_seeds == {8100, 8101, 8102, 8103, 81600, 81601, 81602, 81603, 81604}
    assert rope_seeds == {8200, 8201, 8202, 8203, 81700, 81701, 81702, 81703, 81704}
    assert not (abs_seeds & rope_seeds) and not ((abs_seeds | rope_seeds) & C.UNIT_FIXTURE_SEEDS)
    assert C.arm_of_seed(8200) == ("ROPE", "smoke") and C.arm_of_seed(81704) == ("ROPE", "final")
    assert C.arm_of_seed(8100) == ("ABS", "smoke") and C.arm_of_seed(FIXT) is None
    # ABS legacy map unchanged
    assert dict(C.RESERVED_SEED_ROLES) == {s: r for s, (a, r) in C.RESERVED_SEED_ARM_ROLES.items() if a == "ABS"}

def test_rope_seeds_fail_closed_everywhere():
    for s in (8200, 8201, 8203, 81700, 81704):
        try:
            guard_seed(s); assert False, s
        except ExecutionNotAuthorized:
            pass
        try:
            gen.generate_episode("R1", s, 0); assert False, s
        except ExecutionNotAuthorized:
            pass
    assert guard_seed(FIXT).authorized

def test_rope_record_unsigned_and_scoped():
    p = record_path_for("ROPE")
    assert p.name == "BTRR_ROPE_EXECUTION_AUTHORIZATION_RECORD.json" and p.exists()
    rec = load_signed_record(p)
    assert rec["arm"] == "ROPE"
    for role, entry in rec["roles"].items():
        assert sorted(entry["scope_seeds"]) == sorted(C.ARMS["ROPE"]["seeds"][role])
        if role in ("development", "final"):      # evidence tiers stay closed until the arm is ratified
            assert entry["authorized"] is False and entry["token_sha256"] is None, role
        elif entry["authorized"]:                 # smoke may be owner-signed (calibration); hash only
            assert entry["token_sha256"] and len(entry["token_sha256"]) == 64
            assert entry["protocol_lock_digest"] == MAN.config_digest("ROPE")
    assert record_path_for("ABS").name == "BTRR_EXECUTION_AUTHORIZATION_RECORD.json"

def test_config_digest_binds_arm_and_train_recipe():
    pa, pr = MAN.config_payload("ABS"), MAN.config_payload("ROPE")
    assert MAN.config_digest("ABS") != MAN.config_digest("ROPE")
    assert MAN.config_digest() == MAN.config_digest("ABS")
    for payload in (pa, pr):
        assert set(payload["train_recipe"]) == {"batch_size", "max_updates", "learning_rate", "beta1", "beta2",
                                                "weight_decay", "gradient_clip", "n_train_per_split"}
    assert pa["train_recipe"]["max_updates"] == 2000 and pa["train_recipe"]["n_train_per_split"] is None
    assert pr["train_recipe"]["max_updates"] == 15000 and pr["train_recipe"]["n_train_per_split"] == 400
    assert pa["positional_mechanism"] == "learned_absolute" and pr["positional_mechanism"] == "rope"
    # a recipe change moves the digest (the gap that let a budget change leave the lock untouched)
    import copy, hashlib, json as _json
    alt = copy.deepcopy(pa); alt["train_recipe"]["max_updates"] = 15000
    assert MAN._sha(_json.dumps(alt, sort_keys=True)) != MAN.config_digest("ABS")

def test_companion_json_matches_config():
    doc = json.loads((BENCH / "BTRR_ROPE_SIBLING_ARM_PREREGISTRATION.json").read_text())
    spec = C.ARMS["ROPE"]
    assert doc["ratified"] is False and doc["arm"] == "ROPE"
    assert doc["parameters"]["expected_total_params"] == spec["expected_total_params"] == 144_896
    assert doc["single_difference"]["rope_theta"] == spec["rope_theta"]
    assert doc["train_recipe"] == MAN.config_payload("ROPE")["train_recipe"]
    assert doc["reserved_seeds"] == {r: sorted(s) for r, s in spec["seeds"].items()}
    assert doc["config_digest_at_draft"] == MAN.config_digest("ROPE")

def test_frozen_run_params_admissibility():
    assert C.frozen_run_params("ROPE", FIXT, None, None) == (400, 15000)
    assert C.frozen_run_params("ROPE", 8200, 50, 300) == (50, 300)          # smoke may calibrate
    assert C.frozen_run_params("ABS", 8101, 50, None) == (50, 2000)          # ABS dataset size unfrozen
    for args in (("ROPE", 8201, 50, None), ("ROPE", 81700, None, 2000), ("ABS", 81600, None, 15000),
                 ("ROPE", 8100, None, None), ("ABS", 8200, None, None), ("NOPE", FIXT, None, None)):
        try:
            C.frozen_run_params(*args); assert False, args
        except ValueError:
            pass

def test_report_carries_arm():
    from .. import dataset as DS, run as R
    r_coh = DS.eval_cohorts_r(FIXT, 1, "unit"); p0_coh = DS.eval_cohorts_p0(FIXT, 1, "unit")
    rep = R.assemble_report(seed=FIXT, role="fixture", checkpoint_digest="0" * 64, arm="ROPE",
                            p0_predictions=DS.gold_predictions(p0_coh), r_predictions=DS.gold_predictions(r_coh))
    assert rep["arm"] == "ROPE" and rep["arm_ratified"] is False and rep["config_digest"] == MAN.config_digest("ROPE")
    assert R._role_for(8202) == "development" and R._role_for(FIXT) == "fixture"


def main() -> int:
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
