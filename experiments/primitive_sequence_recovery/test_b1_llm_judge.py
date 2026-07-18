"""Tests for the B1 LLM judge harness — NO MODEL, NO SCORING, NO VERDICT.

Exercises the whole judging path with MockJudgeAdapter (no model call): blinding of the judge prompt,
judge-family/declaration enforcement, JSON schema validation, tie/both_bad -> 0.5 helper, flagged-rate
recording, attention-check exclusion, resume, and the guarantee that no scoring/verdict is produced.

    python3 experiments/primitive_sequence_recovery/test_b1_llm_judge.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_b1_llm_judge as J   # noqa: E402


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


def _sample_views(n=6):
    views = []
    for i in range(n):
        views.append({"display_id": f"P{i:05d}", "key_word": "grief",
                      "task_text": "Write a short reflective paragraph about grief.",
                      "outputs": [{"id": "Output 1", "text": "A longer coherent reflection on grief."},
                                  {"id": "Output 2", "text": "short."}]})
    return views


# ---------------------------------------------------------------- blinding ------------------------
def test_prompt_contains_only_blinded_fields():
    v = {"display_id": "P00001", "key_word": "grief",
         "task_text": "Write a short reflective paragraph about grief.",
         "outputs": [{"id": "Output 1", "text": "coherent one"}, {"id": "Output 2", "text": "other"}]}
    prompt = J.build_judge_prompt(v)
    _check("prompt has task_text", "reflective paragraph about grief" in prompt)
    _check("prompt has both outputs", "coherent one" in prompt and "other" in prompt)
    # hidden fields / identifiers must not appear
    for bad in ("P00001", "display_id", "arm", "A_vs_", "model_id", "seed", "conditioning",
                "mistral", "qwen", "truth", "packet_id"):
        _check(f"prompt hides {bad!r}", bad.lower() not in prompt.lower())


# ---------------------------------------------------------------- judge enforcement ---------------
def test_banned_and_undeclared_judges_rejected():
    for banned in ("mistralai/Mistral-7B-Instruct-v0.3", "Qwen/Qwen2.5-7B-Instruct"):
        try:
            J.validate_judge(banned); _check(f"reject banned {banned}", False)
        except ValueError:
            _check(f"reject banned {banned}", True)
    for undeclared in ("meta-llama/Llama-3.2-3B-Instruct", "meta-llama/Llama-3.1-70B-Instruct"):
        try:
            J.validate_judge(undeclared); _check(f"reject undeclared {undeclared}", False)
        except ValueError:
            _check(f"reject undeclared {undeclared}", True)
    for good in J.DECLARED_JUDGES:
        _check(f"accept declared {good}", J.validate_judge(good) == good)


# ---------------------------------------------------------------- schema validation ---------------
def test_json_schema_validation_and_invalid_choice():
    good = '{"choice": "output_1_better", "confidence": "high", "correctness_flag": "none", "short_reason": "clearer"}'
    rec, ok = J.parse_judge_response(good)
    _check("valid json parses ok", ok and rec["choice"] == "output_1_better")
    # invalid choice -> fallback tie, flagged (ok False)
    bad_choice = '{"choice": "output_3_better", "confidence": "high"}'
    rec, ok = J.parse_judge_response(bad_choice)
    _check("invalid choice rejected -> tie fallback", (not ok) and rec["choice"] == "tie_no_preference")
    # unparseable -> fallback
    rec, ok = J.parse_judge_response("I think Output 1 is better, definitely.")
    _check("prose (no json) -> tie fallback", (not ok) and rec["choice"] == "tie_no_preference")
    # invalid confidence/correctness coerced to safe defaults but choice kept
    rec, ok = J.parse_judge_response('{"choice":"both_bad","confidence":"weird","correctness_flag":"nope"}')
    _check("bad enum fields coerced, choice kept", ok and rec["choice"] == "both_bad"
           and rec["confidence"] == "low" and rec["correctness_flag"] == "none")


_FULL = ('{"choice": "%s", "confidence": "high", "correctness_flag": "none", '
         '"short_reason": "a clear reason"}')


def test_strict_and_fenced_and_prose_parse_without_repair():
    # strict JSON
    rec, ok = J.parse_judge_response(_FULL % "output_1_better")
    _check("strict JSON parses", ok and rec["choice"] == "output_1_better" and rec["parse_repair"] is None)
    # markdown-fenced
    rec, ok = J.parse_judge_response("```json\n" + (_FULL % "output_2_better") + "\n```")
    _check("fenced JSON parses (no repair)", ok and rec["choice"] == "output_2_better"
           and rec["parse_repair"] is None)
    # prose-wrapped
    rec, ok = J.parse_judge_response("Sure, here: " + (_FULL % "both_bad") + " done.")
    _check("prose-wrapped JSON parses (no repair)", ok and rec["choice"] == "both_bad"
           and rec["parse_repair"] is None)


def test_missing_final_brace_is_safely_repaired():
    # the exact judge-2 failure mode: complete body, all fields, only the closing brace missing
    body = ('{\n"choice": "output_1_better",\n"confidence": "high",\n"correctness_flag": "none",\n'
            '"short_reason": "More effective use of metaphor and vivid imagery."')
    rec, ok = J.parse_judge_response(body)
    _check("missing-final-brace repaired -> ok", ok and rec["choice"] == "output_1_better")
    _check("repair is flagged missing_final_brace", rec["parse_repair"] == "missing_final_brace")


def test_repair_refused_when_field_missing_or_invalid_or_duplicated():
    # missing a required field -> NOT repaired
    miss = '{"choice": "output_1_better", "confidence": "high", "correctness_flag": "none"'
    rec, ok = J.parse_judge_response(miss)
    _check("missing required field not repaired", (not ok) and rec["choice"] == "tie_no_preference")
    # invalid choice -> NOT repaired
    badc = '{"choice": "output_3_better", "confidence": "high", "correctness_flag": "none", "short_reason": "x"'
    rec, ok = J.parse_judge_response(badc)
    _check("invalid choice not repaired", (not ok) and rec["choice"] == "tie_no_preference")
    # invalid confidence -> NOT repaired (repair path requires valid confidence)
    badconf = '{"choice": "output_1_better", "confidence": "sky", "correctness_flag": "none", "short_reason": "x"'
    rec, ok = J.parse_judge_response(badconf)
    _check("invalid confidence not repaired", not ok)
    # duplicated key -> NOT repaired
    dup = ('{"choice": "output_1_better", "choice": "output_2_better", "confidence": "high", '
           '"correctness_flag": "none", "short_reason": "x"')
    rec, ok = J.parse_judge_response(dup)
    _check("duplicated key not repaired", not ok)
    # genuinely non-JSON prose -> fallback
    rec, ok = J.parse_judge_response("I think Output 1 is better, honestly.")
    _check("prose (no json) -> tie fallback", (not ok) and rec["choice"] == "tie_no_preference")


def test_tie_and_both_bad_map_to_half():
    _check("tie -> 0.5", J.choice_to_a_win_placeholder("tie_no_preference") == 0.5)
    _check("both_bad -> 0.5", J.choice_to_a_win_placeholder("both_bad") == 0.5)
    _check("output_1_better needs truth (None here)", J.choice_to_a_win_placeholder("output_1_better") is None)
    _check("output_2_better needs truth (None here)", J.choice_to_a_win_placeholder("output_2_better") is None)


# ---------------------------------------------------------------- attention rule ------------------
def test_attention_exclusion_rule():
    # frozen: exclude if fails >1 OR >25% (whichever stricter => either triggers)
    _check("0 fails kept", J.attention_excluded(0, 24) is False)
    _check("1 fail kept", J.attention_excluded(1, 24) is False)
    _check("2 fails excluded (>1)", J.attention_excluded(2, 24) is True)
    _check("7/24 excluded (>25%)", J.attention_excluded(7, 24) is True)
    checks = J.build_attention_checks(n=24)
    _check("24 attention checks built", len(checks) == 24)
    _check("each has a known correct side", all(c["_attn_correct"] in
           ("output_1_better", "output_2_better") for c in checks))


# ---------------------------------------------------------------- run + resume + no scoring -------
def test_mock_run_resume_flagged_and_no_scoring():
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        views = _sample_views(6)
        (td / "b1_judge_view.jsonl").write_text(
            "\n".join(json.dumps(v) for v in views) + "\n", encoding="utf-8")
        J.JUDGE_VIEW = td / "b1_judge_view.jsonl"
        J.OUT_DIR = td
        jid = J.DECLARED_JUDGES[0]
        attn = J.build_attention_checks(n=24)

        a1 = J.MockJudgeAdapter(jid)
        s1 = J.run_one_judge(jid, a1, views, attn, resume=True, verbose=False)
        _check("mock adapter is not real", a1.is_real is False)
        _check("mock judged all items (6 views + 24 attn)", a1.calls == 30)
        _check("mock passes attention (good output longer) -> not excluded", s1["excluded"] is False)
        _check("flagged rate recorded", isinstance(s1["flagged"], int))

        # resume: second run over same file skips everything -> 0 new calls
        a2 = J.MockJudgeAdapter(jid)
        J.run_one_judge(jid, a2, views, attn, resume=True, verbose=False)
        _check("resume skips completed (0 new calls)", a2.calls == 0)

        # per-judge output exists; NO scoring/verdict files were produced
        outp = J.out_path_for(jid)
        _check("per-judge output written", outp.exists())
        names = {p.name for p in td.iterdir()}
        _check("no scoring/verdict file produced",
               not any(("scor" in n or "verdict" in n) for n in names))
        # every record is choice-only judgment, no A-win / no truth
        for ln in outp.read_text(encoding="utf-8").splitlines():
            r = json.loads(ln)
            _check("record has choice, no a_win/truth",
                   r["choice"] in J.CHOICES and "a_win" not in r and "truth" not in r)


def test_raw_preserved_and_repair_flagged_end_to_end():
    class BraceDropAdapter:
        is_real = False

        def __init__(self, jid):
            self.judge_id = J.validate_judge(jid)

        def judge_raw(self, prompt, view):
            # complete body, all fields, NO closing brace (the exact judge-2 failure)
            return ('{"choice": "output_1_better", "confidence": "high", '
                    '"correctness_flag": "none", "short_reason": "good"')

    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        views = _sample_views(2)
        (td / "b1_judge_view.jsonl").write_text("\n".join(json.dumps(v) for v in views) + "\n",
                                                encoding="utf-8")
        J.JUDGE_VIEW = td / "b1_judge_view.jsonl"
        J.OUT_DIR = td
        jid = J.DECLARED_JUDGES[0]
        s = J.run_one_judge(jid, BraceDropAdapter(jid), views, J.build_attention_checks(n=4),
                            resume=True, verbose=False)
        rows = [json.loads(x) for x in J.out_path_for(jid).read_text(encoding="utf-8").splitlines()]
        real = [r for r in rows if r["kind"] == "real"]
        _check("repaired records are parse_ok", all(r["parse_ok"] for r in real))
        _check("repaired records flagged missing_final_brace",
               all(r["parse_repair"] == "missing_final_brace" for r in real))
        _check("raw text preserved UNCHANGED (no appended brace in raw)",
               all(not r["raw"].rstrip().endswith("}") for r in real))
        _check("repaired choice is valid", all(r["choice"] == "output_1_better" for r in real))
        _check("summary counts repaired", s.get("repaired", 0) >= len(real))


def test_only_judge_view_is_read():
    # harness input path is the blinded view; it must not reference the full/truth packet file
    src = pathlib.Path(J.__file__).read_text(encoding="utf-8")
    _check("reads b1_judge_view.jsonl", "b1_judge_view.jsonl" in src)
    _check("does NOT read b1_judge_packets_full.jsonl", "b1_judge_packets_full.jsonl" not in src)


def main():
    print("test_b1_llm_judge — LLM judge harness tests (no model, no scoring, no verdict)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll LLM judge harness tests passed (no model call, no scoring, no verdict).")


if __name__ == "__main__":
    main()
