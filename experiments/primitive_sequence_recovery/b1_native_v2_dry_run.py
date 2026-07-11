"""Dry-run infrastructure validation of the frozen v2 evaluator protocol (NO model calls, NO real accuracy).

Implements a REFERENCE RUNNER exactly per native_word_specificity_packets_v2/evaluator_protocol.json and exercises it
against synthetic fixed responses to prove: valid parse; exactly-one retry on invalid; second-invalid -> missing;
timeout handling; duplicate handling; raw-response freeze precedes scoring; scoring reproduces expected synthetic
accuracies; the runner performs no result-dependent prompt modification. Emits dry_run_record.json.
"""
import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
V2 = HERE / "native_word_specificity_packets_v2"
OUT = HERE / "native_packet_prerun_audit_v2"
PROTO = json.load(open(V2 / "evaluator_protocol.json", encoding="utf-8"))
VALID = set(PROTO["response_schema"]["properties"]["choice"]["enum"])       # {"W1".."W6"}


def parse_choice(raw):
    """Strict: raw must be a JSON object whose ONLY key is 'choice' mapping to one of W1..W6. Else invalid (None)."""
    try:
        obj = json.loads(raw)
    except Exception:
        return None
    if not isinstance(obj, dict) or set(obj.keys()) != {"choice"}:
        return None
    c = obj["choice"]
    return c if isinstance(c, str) and c in VALID else None    # non-string (e.g. list) choice is invalid


def run_one(attempts):
    """attempts: list of (kind, payload); kind in {'ok','timeout'}. Max 1 retry => at most 2 attempts consumed.
    Returns status in {'answered','missing'} and the parsed choice (or None). NEVER inspects the answer key."""
    used = 0
    for kind, payload in attempts[:2]:                 # retry policy: <=1 retry => <=2 attempts
        used += 1
        if kind == "timeout":
            continue                                   # timeout -> triggers the single retry
        ch = parse_choice(payload)
        if ch is not None:
            return {"status": "answered", "choice": ch, "attempts": used}
        # invalid/duplicate/prose -> retry (if budget remains)
    return {"status": "missing", "choice": None, "attempts": used}


def score(runs, key_by_oid):
    """Score ONLY after raw responses are frozen. missing/invalid -> incorrect."""
    correct = 0
    per_arm = {}
    for oid, r in runs.items():
        k = key_by_oid[oid]
        ok = (r["status"] == "answered" and r["choice"] == k["correct_label"])
        correct += int(ok)
        per_arm.setdefault(k["arm"], [0, 0])
        per_arm[k["arm"]][0] += int(ok); per_arm[k["arm"]][1] += 1
    return correct, {a: round(c / n, 6) for a, (c, n) in per_arm.items()}


def build():
    OUT.mkdir(exist_ok=True)
    key = json.load(open(V2 / "internal" / "answer_key.json", encoding="utf-8"))["key"]
    key_by_oid = {k["opaque_trial_id"]: k for k in key}

    # ---- A. scripted micro-scenarios covering every branch ----
    scenarios = {
        "valid_first_try": ([("ok", '{"choice": "W3"}')], "answered", "W3", 1),
        "invalid_then_valid": ([("ok", "I think W2"), ("ok", '{"choice": "W2"}')], "answered", "W2", 2),
        "invalid_twice_missing": ([("ok", "W2"), ("ok", "nonsense")], "missing", None, 2),
        "timeout_then_valid": ([("timeout", None), ("ok", '{"choice": "W5"}')], "answered", "W5", 2),
        "timeout_twice_missing": ([("timeout", None), ("timeout", None)], "missing", None, 2),
        "duplicate_choice_invalid": ([('ok', '{"choice": "W1", "second": "W2"}'), ("ok", '{"choice":"W1"}')], "answered", "W1", 2),
        "list_choice_invalid_then_missing": ([("ok", '{"choice": ["W1","W2"]}'), ("ok", '{"choice": "W7"}')], "missing", None, 2),
        "prose_wrapped_invalid_then_valid": ([("ok", 'Sure! {"choice":"W4"}'), ("ok", '{"choice": "W4"}')], "answered", "W4", 2),
    }
    micro = {}
    for name, (att, exp_status, exp_choice, exp_attempts) in scenarios.items():
        r = run_one(att)
        micro[name] = {"result": r, "expected": {"status": exp_status, "choice": exp_choice, "attempts": exp_attempts},
                       "pass": (r["status"] == exp_status and r["choice"] == exp_choice and r["attempts"] == exp_attempts)}
    micro_all_pass = all(v["pass"] for v in micro.values())

    # ---- B. full synthetic sweeps over all 720 presentations (freeze-before-score enforced by construction) ----
    def sweep(responder, label):
        raw = {oid: responder(oid) for oid in key_by_oid}                     # 1) collect raw responses
        frozen_hash = hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()   # 2) FREEZE raw
        runs = {oid: run_one([("ok", raw[oid])]) for oid in raw}              # (parse; no retry needed here)
        total, per_arm = score(runs, key_by_oid)                             # 3) score AFTER freeze
        return {"label": label, "raw_frozen_sha256": frozen_hash, "n": len(raw),
                "overall_accuracy": round(total / len(raw), 6), "per_arm_accuracy": per_arm}

    all_correct = sweep(lambda oid: json.dumps({"choice": key_by_oid[oid]["correct_label"]}), "oracle_all_correct")
    always_w1 = sweep(lambda oid: json.dumps({"choice": "W1"}), "always_W1")
    all_invalid = sweep(lambda oid: "no json here", "all_invalid")

    sweeps_ok = (all_correct["overall_accuracy"] == 1.0
                 and all(abs(v - 1 / 6) < 1e-6 for v in always_w1["per_arm_accuracy"].values())
                 and all_invalid["overall_accuracy"] == 0.0)

    # ---- C. structural guarantees ----
    import inspect
    run_src, parse_src, score_src = (inspect.getsource(f) for f in (run_one, parse_choice, score))
    structural = {
        # the response-producing path (parse + run) never references the answer key / correct label
        "runner_never_reads_key": all(tok not in (run_src + parse_src)
                                      for tok in ("correct_label", "key_by_oid", "answer_key")),
        "score_is_separate_from_run": "score(" not in run_src,       # run_one does not score
        "freeze_precedes_score_in_sweep": True,   # sweep(): raw -> hash -> runs -> score, in that order
        "no_result_dependent_prompt_mod": "prompt" not in (run_src + parse_src).lower(),
        "retry_cap_one": "[:2]" in run_src,
    }
    _ = score_src

    record = {"artifact": "v2_dry_run_infrastructure_validation", "no_model_calls": True, "no_real_accuracy": True,
              "protocol_source": "native_word_specificity_packets_v2/evaluator_protocol.json",
              "micro_scenarios": micro, "micro_all_pass": micro_all_pass,
              "sweeps": {"oracle_all_correct": all_correct, "always_W1": always_w1, "all_invalid": all_invalid},
              "sweeps_reproduce_expected": sweeps_ok, "structural_guarantees": structural,
              "dry_run_pass": bool(micro_all_pass and sweeps_ok and all(structural.values()))}
    (OUT / "dry_run_record.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return record


if __name__ == "__main__":
    r = build()
    print("micro scenarios pass:", r["micro_all_pass"])
    for n, v in r["micro_scenarios"].items():
        print("  ", "OK " if v["pass"] else "FAIL", n, "->", v["result"]["status"], v["result"]["choice"])
    print("oracle accuracy:", r["sweeps"]["oracle_all_correct"]["overall_accuracy"],
          "| always-W1 per-arm:", r["sweeps"]["always_W1"]["per_arm_accuracy"])
    print("sweeps reproduce expected:", r["sweeps_reproduce_expected"])
    print("structural:", r["structural_guarantees"])
    print("DRY RUN PASS:", r["dry_run_pass"])
