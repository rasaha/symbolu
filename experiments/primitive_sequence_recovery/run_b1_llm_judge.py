#!/usr/bin/env python3
"""B1 LLM judge harness (D1 Llama panel) — BUILD ONLY until RUN_LLM_JUDGE is approved.

Reads the blinded b1_judge_view.jsonl and runs the three declared Llama judges sequentially, greedy,
structured-JSON only. Enforces the pre-run declaration (addendum b13ac74):
  * judges MUST be one of the declared Llama checkpoints; Mistral/Qwen and any undeclared model refused
  * the judge sees ONLY blinded fields (task + two neutrally-labelled outputs) — never arm/model/seed/
    conditioning/truth/internal packet_id/display_id
  * choices: output_1_better | output_2_better | tie_no_preference | both_bad  (scoring uses ONLY choice)
  * planted attention checks + frozen exclusion rule (fail >1 OR >25%, whichever stricter)
  * resume; per-judge output files; provenance/hash block

Does NOT score, map choices to A-win, or compute a verdict. Track B stays BLOCKED. A MockJudgeAdapter
exercises the whole path with NO model call (used by the tests).

    # after RUN_LLM_JUDGE approval, on the pod:
    python3 experiments/primitive_sequence_recovery/run_b1_llm_judge.py --judge all
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import random
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent

JUDGE_VIEW = HERE / "b1_judge_view.jsonl"          # the ONLY packet input the judge is fed
OUT_DIR = HERE                                      # per-judge outputs written here

# --- declared panel (addendum b13ac74). Do not add models here without a new pre-run addendum. ---
DECLARED_JUDGES = (
    "meta-llama/Llama-3.1-8B-Instruct",
    "meta-llama/Meta-Llama-3-8B-Instruct",
    "meta-llama/Llama-3.2-3B-Instruct",
)
BANNED_JUDGE_SUBSTR = ("mistral", "qwen")          # generation families — never judges

CHOICES = ("output_1_better", "output_2_better", "tie_no_preference", "both_bad")
CONFIDENCE = ("low", "medium", "high")
CORRECTNESS = ("none", "output_1_problem", "output_2_problem", "both_problem")
FLAGGED_CHOICES = ("tie_no_preference", "both_bad")  # -> 0.5 later; both_bad also separately flagged

N_ATTENTION = 24                                     # planted checks per judge
ATTENTION_SEED = 90311                               # fixed (not a frozen scoring seed)

JUDGE_PROMPT = (
    "You are comparing two responses to the same task. Read the task and both responses, then decide "
    "which response better accomplishes the task. Judge quality and correctness only; ignore length "
    "and surface style. Do NOT explain your thinking. Respond with ONLY a JSON object of this exact "
    "shape and nothing else:\n"
    '{{"choice": "output_1_better|output_2_better|tie_no_preference|both_bad", '
    '"confidence": "low|medium|high", '
    '"correctness_flag": "none|output_1_problem|output_2_problem|both_problem", '
    '"short_reason": "one short sentence"}}\n\n'
    "Task: {task_text}\n\nOutput 1: {text1}\n\nOutput 2: {text2}\n\nJSON:"
)

_HIDDEN_TOKENS = ('"arm"', "A_vs_", "control_arm", "truth", "packet_id", "model_id",
                  "mistral", "qwen", "1101", "2027", "conditioning")


# ---------------------------------------------------------------- judge validation ----------------
def validate_judge(judge_id):
    low = judge_id.lower()
    if any(b in low for b in BANNED_JUDGE_SUBSTR):
        raise ValueError(f"REFUSED: {judge_id!r} is a banned judge family (generation model).")
    if judge_id not in DECLARED_JUDGES:
        raise ValueError(f"REFUSED: {judge_id!r} is not a declared judge. A new pre-run addendum is "
                         f"required. Declared: {list(DECLARED_JUDGES)}")
    return judge_id


def judge_slug(judge_id):
    return judge_id.split("/")[-1].replace(".", "-")


# ---------------------------------------------------------------- prompt (blinded) ----------------
def build_judge_prompt(view):
    """Prompt from a blinded judge_view ONLY. Contains task + the two outputs; nothing else."""
    o = view["outputs"]
    prompt = JUDGE_PROMPT.format(task_text=view["task_text"],
                                 text1=o[0]["text"], text2=o[1]["text"])
    return prompt


# ---------------------------------------------------------------- response parsing -----------------
def parse_judge_response(text):
    """Extract + validate the JSON object. Returns (record_fields, ok). On any violation returns a
    tie_no_preference fallback with ok=False (flagged)."""
    fallback = {"choice": "tie_no_preference", "confidence": "low",
                "correctness_flag": "none", "short_reason": "unparseable-or-invalid"}
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not m:
        return fallback, False
    try:
        d = json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return fallback, False
    if d.get("choice") not in CHOICES:
        return fallback, False
    rec = {
        "choice": d["choice"],
        "confidence": d.get("confidence") if d.get("confidence") in CONFIDENCE else "low",
        "correctness_flag": d.get("correctness_flag") if d.get("correctness_flag") in CORRECTNESS else "none",
        "short_reason": str(d.get("short_reason", ""))[:200],
    }
    return rec, True


# ---------------------------------------------------------------- scoring helper (NOT the scorer) --
def choice_to_a_win_placeholder(choice):
    """Helper used ONLY by tests/reporting to show the tie/both_bad -> 0.5 convention. The REAL scorer
    (separate, gated) maps choice -> A-win via the packet truth map; this harness never sees truth."""
    if choice in FLAGGED_CHOICES:
        return 0.5
    return None  # output_1/2_better require the truth map to become an A-win score


# ---------------------------------------------------------------- adapters -------------------------
class MockJudgeAdapter:
    """Deterministic judge with NO model call. Picks the longer output as better (so it passes the
    planted attention checks, where the coherent output is longer than the broken one)."""
    is_real = False

    def __init__(self, judge_id):
        self.judge_id = validate_judge(judge_id)
        self.calls = 0

    def judge_raw(self, prompt, view):
        self.calls += 1
        t1 = len(view["outputs"][0]["text"].strip())
        t2 = len(view["outputs"][1]["text"].strip())
        if abs(t1 - t2) <= 3:
            choice = "tie_no_preference"
        else:
            choice = "output_1_better" if t1 > t2 else "output_2_better"
        return json.dumps({"choice": choice, "confidence": "medium",
                           "correctness_flag": "none", "short_reason": "mock deterministic"})


class LlamaJudgeAdapter:
    """Real Llama judge (greedy). Imports transformers lazily so the harness/tests load without it."""
    is_real = True

    def __init__(self, judge_id):
        self.judge_id = validate_judge(judge_id)
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.tok = AutoTokenizer.from_pretrained(judge_id)
        self.model = AutoModelForCausalLM.from_pretrained(judge_id, torch_dtype=torch.float16,
                                                          device_map="auto")
        self.model.eval()

    def judge_raw(self, prompt, view):
        import torch
        msgs = [{"role": "user", "content": prompt}]
        enc = self.tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt",
                                           return_dict=True).to(self.model.device)
        with torch.no_grad():
            out = self.model.generate(**enc, do_sample=False, temperature=None, top_p=None,
                                      max_new_tokens=96, pad_token_id=self.tok.eos_token_id)
        return self.tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)


# ---------------------------------------------------------------- attention checks -----------------
def build_attention_checks(n=N_ATTENTION, seed=ATTENTION_SEED):
    """Planted packets: one clearly on-task coherent output vs one clearly broken output. Returns
    blinded views (same shape as judge_view) plus a hidden _attn_correct = which choice picks the good
    output. The judge is fed ONLY the blinded view; _attn_correct is used solely for pass/fail here."""
    rng = random.Random(seed)
    topics = ["patience", "a river", "friendship", "courage", "silence", "autumn", "honesty", "grief"]
    checks = []
    for i in range(n):
        topic = topics[i % len(topics)]
        good = (f"{topic.capitalize()} is something people experience in everyday life; this short "
                f"paragraph reflects on {topic} clearly, stays on the requested task, and reads as "
                f"coherent, grammatical English about {topic}.")
        bad = rng.choice([
            "asdf qwerty zxcv lorem ipsum blah blah 12345 !!! ??? ncjk wpq",
            "the the the the and and and of of of a a a ... (no content)",
            "",
            "BUY NOW cheap pixels click here unrelated spam advertisement unrelated to any task",
        ]) or "..."
        good_side = rng.choice((0, 1))
        outs = [{"id": "Output 1", "text": good if good_side == 0 else bad},
                {"id": "Output 2", "text": good if good_side == 1 else bad}]
        correct = "output_1_better" if good_side == 0 else "output_2_better"
        checks.append({"display_id": f"ATTN{i:05d}", "key_word": topic, "task_text":
                       f"Write a short reflective paragraph about {topic}.", "outputs": outs,
                       "_attn_correct": correct})
    return checks


def attention_excluded(fails, n):
    """Frozen rule: exclude if fails >1 OR fails >25% (whichever stricter => either triggers)."""
    return fails > 1 or fails > 0.25 * n


# ---------------------------------------------------------------- I/O ------------------------------
def load_views():
    if not JUDGE_VIEW.exists():
        raise SystemExit(f"ABORT: {JUDGE_VIEW} not found (run the packet builder first).")
    return [json.loads(x) for x in JUDGE_VIEW.read_text(encoding="utf-8").splitlines() if x.strip()]


def out_path_for(judge_id):
    return OUT_DIR / f"b1_judge_responses_{judge_slug(judge_id)}.jsonl"


def _done_ids(path):
    done = set()
    if path.exists():
        for ln in path.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(ln)["display_id"])
            except Exception:  # noqa: BLE001
                pass
    return done


def run_one_judge(judge_id, adapter, views, attn, resume=True, verbose=True):
    """Judge all real views + attention checks with one judge. Writes per-judge JSONL. Returns a
    summary (attention fails, flagged count). Does NOT score or map to A-win."""
    path = out_path_for(judge_id)
    done = _done_ids(path) if resume else set()
    attn_fail = 0
    flagged = 0
    all_items = [("real", v) for v in views] + [("attn", a) for a in attn]
    n_items = len(all_items)
    done_n = len(done)
    if verbose:
        print(f"[judge {judge_slug(judge_id)}] starting: {n_items} items "
              f"({done_n} already done, resuming)", flush=True)
    with path.open("a", encoding="utf-8") as fh:
        for i, (kind, item) in enumerate(all_items, 1):
            did = item["display_id"]
            if did in done:
                continue
            view = {k: item[k] for k in ("display_id", "key_word", "task_text", "outputs")}
            prompt = build_judge_prompt(view)
            raw = adapter.judge_raw(prompt, view)
            rec_fields, ok = parse_judge_response(raw)
            if not ok or rec_fields["choice"] in FLAGGED_CHOICES:
                flagged += 1
            if kind == "attn":
                if rec_fields["choice"] != item["_attn_correct"]:
                    attn_fail += 1
            rec = {"display_id": did, "judge_id": judge_id, "kind": kind,
                   "choice": rec_fields["choice"], "confidence": rec_fields["confidence"],
                   "correctness_flag": rec_fields["correctness_flag"],
                   "short_reason": rec_fields["short_reason"], "parse_ok": ok}
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()                                    # progress is durable + visible via wc -l
            if verbose and (i % 100 == 0 or i == n_items):
                print(f"[judge {judge_slug(judge_id)}] {i}/{n_items} "
                      f"(attn_fail {attn_fail}, flagged {flagged})", flush=True)
    excluded = attention_excluded(attn_fail, len(attn))
    if verbose:
        print(f"[judge {judge_slug(judge_id)}] attention fails {attn_fail}/{len(attn)} "
              f"-> {'EXCLUDED' if excluded else 'kept'} | flagged(tie/both_bad) {flagged}")
    return {"judge_id": judge_id, "attn_fail": attn_fail, "n_attn": len(attn),
            "excluded": excluded, "flagged": flagged, "out_path": str(path)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", default="all",
                    help="'all' or a specific declared judge id")
    ap.add_argument("--mock", action="store_true", help="use MockJudgeAdapter (no model call)")
    ap.add_argument("--no-resume", action="store_true")
    args = ap.parse_args(argv)

    judges = DECLARED_JUDGES if args.judge == "all" else (validate_judge(args.judge),)
    views = load_views()
    attn = build_attention_checks()
    print(f"[ok] {len(views)} blinded views + {len(attn)} attention checks | judges: "
          f"{[judge_slug(j) for j in judges]} | mock={args.mock}")

    summaries = []
    for jid in judges:                                   # SEQUENTIAL (one model resident at a time)
        adapter = MockJudgeAdapter(jid) if args.mock else LlamaJudgeAdapter(jid)
        summaries.append(run_one_judge(jid, adapter, views, attn, resume=not args.no_resume))

    prov = {"B1_JUDGE_RUN_PROVENANCE": {
        "judges": [judge_slug(j) for j in judges],
        "per_judge": [{"judge": judge_slug(s["judge_id"]), "attn_fail": s["attn_fail"],
                       "n_attn": s["n_attn"], "excluded": s["excluded"], "flagged": s["flagged"],
                       "out_sha256": hashlib.sha256(pathlib.Path(s["out_path"]).read_bytes()).hexdigest()
                       if pathlib.Path(s["out_path"]).exists() else None}
                      for s in summaries],
        "scored": False, "verdict": None, "track_b": "BLOCKED",
        "note": "Judge choices recorded. NOT scored, NOT mapped to A-win, NO verdict. Structure, "
                "not validated meaning."}}
    print("\n===== PASTE THIS BACK (judge-run provenance) =====")
    print(json.dumps(prov, indent=2))
    print("===== END =====")
    print("NOT scored. Track B BLOCKED. Next gate: RUN_B1_SCORING (separately approved).")


if __name__ == "__main__":
    main()
