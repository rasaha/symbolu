#!/usr/bin/env python3
"""B1 generation + scoring harness — DRY-RUN / MOCK ONLY (no real model, no real scoring, no evidence).

Plumbing for the H2 Track B B1 evaluation, exercised end-to-end WITHOUT any real model call and
WITHOUT real scoring. It proves the pipeline shape: frozen-input load → expansion → (mock)
generation → leak scan → blinded judge packets → (mock) judging → pairwise A-vs-D/R/S/C/X
aggregation → clustered bootstrap → Holm-Bonferroni → verdict label.

HARD FACTS:
  * No real model is ever called. The only generation path is MockModelAdapter (fixed placeholder).
    RealModelAdapter.generate() raises — the real path is intentionally NOT wired here.
  * No real scoring: mock judge responses are deterministic placeholders that exercise the scorer.
  * No result files are written. Everything is in-memory. Outputs are marked MOCK_DRY_RUN.
  * This does NOT freeze B0, approve B1, or unblock Track B. Engineering plumbing only.

Controlling prereg: PREREG_TRACK_B_H2_GENERATION_CONDITIONING.md (d3a32e2, arithmetic e147575).
Parity fix: 64b0f40. Track G negative preserved; Track B remains BLOCKED.
"""
from __future__ import annotations

import argparse
import random
import re
import statistics
from dataclasses import dataclass, field

BANNER = "B1_DRY_RUN_MOCK_ONLY — no real model, no real scoring, not evidence, not a B1 run"

# ---------------------------------------------------------------- 1. frozen inputs (mock loader) --
# Mirrors the controlling prereg's eval set/tasks/arms. Flagged DRY-RUN: NOT the frozen B0 package.
PRIMARY_WORDS = ("grief", "courage", "patience", "justice", "silence", "mountain", "river", "music",
                 "friendship", "teacher", "shadow", "freedom", "honesty", "empathy", "ocean", "envy",
                 "order", "integrity", "autumn", "echo")
PRIVATIVE_WORDS = ("amoral", "apathy", "asymmetry", "anarchy", "anonymity")
TASKS = {
    "T1": "Write a short reflective paragraph about {w}.",
    "T2": "Write a gentle, kind message on the theme of {w}.",
    "T3": "Write one original metaphor for {w}.",
    "T4": "Explain {w} plainly and accurately in 3-4 sentences.",
    "T5": "Respond to someone reflecting on {w}, matching the emotional tone.",
    "T6": "Rewrite this line to evoke {w}: 'The day went on as usual.'",
}
ARMS = ("A", "R", "S", "C", "X", "D")
MOCK_MODELS = ("MOCK_MODEL_A", "MOCK_MODEL_B")          # two nominally distinct mock families
SEEDS = (1101, 2027)
CO_PRIMARIES = ("D", "R", "S", "C", "X")               # A vs each of these
DECODE = {"temperature": 0.7, "top_p": 0.95, "max_tokens": 300, "frequency_penalty": 0,
          "presence_penalty": 0, "system_prompt": None, "stop_sequences": None,
          "arm_specific_decoding": False}
WRAPPER = ("Soft orientation, not a definition: {conditioning}. Use this only as a gentle "
           "tonal/conceptual guide while following the task exactly.\n\nTask:\n{task}")

# Frozen analysis / judging protocol (prereg §9-§10). Bootstrap seed == runtime-lock
# `bootstrap_statistical`. These pin researcher degrees of freedom before any output exists.
BOOTSTRAP = {"n_boot": 2000, "seed": 60617}
JUDGING = {"n_judges_min": 3, "n_judges_preferred": 5, "tie": 0.5, "both_bad": 0.5,
           "attention_exclude_rule": ("exclude a judge only if they fail more than 1 attention check "
                                      "OR fail more than 25% of attention checks (whichever is "
                                      "stricter); all exclusions applied before outcome analysis")}

FORBIDDEN = ("ontology", "ontological validation", "sanskrit proves", "sanskrit privilege",
             "semantic truth", "validated meaning", "therefore means", "varṇas prove",
             "varnas prove", "phonemes encode true meaning", "track b support", "track g rescue")

VERDICT_LABELS = ("NO_SIGNAL", "DICTIONARY_DOMINATES", "RANDOM_OR_SCRAMBLED_MATCHES",
                  "SURFACE_STRUCTURE_EXPLAINS", "CORRECTNESS_DEGRADED", "INVALID_POSTHOC",
                  "LEAKAGE_FAIL", "NOT_ROBUST", "LIMITED_GENERATION_UTILITY")


def load_frozen_inputs():
    """Mock prereg/frozen-input loader. Returns the eval set; flagged NOT frozen (B0 still open)."""
    return {"primary": PRIMARY_WORDS, "privative": PRIVATIVE_WORDS, "tasks": tuple(TASKS),
            "arms": ARMS, "models": MOCK_MODELS, "seeds": SEEDS, "co_primaries": CO_PRIMARIES,
            "frozen": False, "note": "DRY-RUN mock inputs — NOT a frozen B0 package"}


# ---------------------------------------------------------------- 2. expansion --------------------
@dataclass(frozen=True)
class RawRow:
    row_id: str
    key_word: str
    stratum: str
    task: str
    arm: str
    model: str
    seed: int


def expand_rows(inputs=None):
    """word × task × arm × model × seed. primary 20*6*6*2*2=2880, privative 5*6*6*2*2=720; total 3600."""
    inputs = inputs or load_frozen_inputs()
    rows = []
    for stratum, words in (("primary", inputs["primary"]), ("privative", inputs["privative"])):
        for w in words:
            for t in inputs["tasks"]:
                for arm in inputs["arms"]:
                    for m in inputs["models"]:
                        for s in inputs["seeds"]:
                            rows.append(RawRow(f"{w}|{t}|{arm}|{m}|{s}", w, stratum, t, arm, m, s))
    return rows


# ---------------------------------------------------------------- 3. raw output schema ------------
@dataclass
class RawOutput:
    row_id: str
    key_word: str
    stratum: str
    task: str
    arm: str
    model: str
    seed: int
    conditioning: str
    output_text: str
    mock: bool = True


def _mock_conditioning(key_word, arm):
    """Deterministic DRY-RUN conditioning stand-in per (word, arm). Real conditioning is wired at
    freeze from the committed generators + D-table; here it is a labeled mock (hidden from judges)."""
    return f"[MOCK {arm}-arm conditioning core for '{key_word}']"


def build_prompt(key_word, task_template, arm, conditioning_fn=None):
    """Build (conditioning_core, full_prompt). conditioning_fn(word, arm) -> bare core; default is
    the labeled mock. Pass b1_real_conditioning.real_core for real deterministic conditioning."""
    cond = conditioning_fn(key_word, arm) if conditioning_fn else _mock_conditioning(key_word, arm)
    return cond, WRAPPER.format(conditioning=cond, task=task_template.format(w=key_word))


# ---------------------------------------------------------------- 4-5. model adapters -------------
class ModelAdapter:
    is_real = False
    name = "base"

    def generate(self, prompt, decode, seed):
        raise NotImplementedError


class RealModelAdapter(ModelAdapter):
    """Intentionally NOT wired. Proves the real path cannot be invoked in the dry-run."""
    is_real = True
    name = "REAL_NOT_WIRED"

    def generate(self, prompt, decode, seed):
        raise RuntimeError("RealModelAdapter is not wired in the B1 dry-run — no real model call allowed")


class MockModelAdapter(ModelAdapter):
    """Deterministic placeholder generator. Counts calls; never contacts a model/network."""
    is_real = False
    name = "MOCK"

    def __init__(self):
        self.call_count = 0

    def generate(self, prompt, decode, seed):
        self.call_count += 1
        # NOTE: no arm/model/seed embedded — keeps mock outputs blind-safe for judge packets.
        return f"MOCK_DRY_RUN_OUTPUT #{self.call_count} | (no real generation performed)"


# ---------------------------------------------------------------- 6. generation runner ------------
def run_generation(rows, adapter, dry_run=True, conditioning_fn=None):
    """Produce (mock) outputs for every row. dry_run must be True; a real adapter is refused.
    conditioning_fn(word, arm) supplies the bare core (default = mock; pass real_core for real)."""
    if not dry_run:
        raise RuntimeError("run_generation supports DRY-RUN only in this harness")
    if getattr(adapter, "is_real", False):
        raise RuntimeError("refusing to run: real model adapter passed to the dry-run harness")
    outputs = []
    for r in rows:
        cond, prompt = build_prompt(r.key_word, TASKS[r.task], r.arm, conditioning_fn=conditioning_fn)
        txt = adapter.generate(prompt, DECODE, r.seed)
        outputs.append(RawOutput(r.row_id, r.key_word, r.stratum, r.task, r.arm, r.model, r.seed,
                                 cond, txt))
    return outputs


# ---------------------------------------------------------------- 7. leak scanner -----------------
def leak_scan(text):
    low = (text or "").lower()
    hits = [p for p in FORBIDDEN if p in low]
    if re.search(r"\brescue\b", low):
        hits.append("rescue")
    if re.search(r"\barm [arscxd]\b", low):
        hits.append("arm-label")
    return hits


def scan_outputs(outputs):
    """Return list of (row_id, hits) for any output with leak hits (empty => clean)."""
    return [(o.row_id, leak_scan(o.output_text)) for o in outputs if leak_scan(o.output_text)]


# ---------------------------------------------------------------- 8. blinded judge packets --------
@dataclass
class JudgePacket:
    packet_id: str              # internal id (encodes model/seed/A_vs_ctrl) — NEVER judge-visible
    display_id: str             # neutral opaque id shown to the judge
    control_arm: str            # which control A is compared against (internal, NOT judge-visible)
    key_word: str
    task_text: str
    outputs: list               # [{"id":"Output 1","text":...}, {"id":"Output 2","text":...}]
    truth: dict = field(default_factory=dict)   # {"Output 1":"A"/ctrl, ...} — scorer only, hidden


def judge_view(packet):
    """The ONLY thing a judge sees: a neutral display id + key word + task + neutrally-labelled
    outputs. No internal packet_id, no arm labels, no conditioning, no model, no seed, no truth map."""
    return {"display_id": packet.display_id, "key_word": packet.key_word,
            "task_text": packet.task_text,
            "outputs": [{"id": o["id"], "text": o["text"]} for o in packet.outputs]}


def build_judge_packets(outputs, rand_seed):
    """Blinded pairwise packets: A vs each of D/R/S/C/X, per (key_word, task, model, seed) group.
    Left/right order randomized deterministically from rand_seed. Arm/conditioning/model/seed are NOT
    placed in the judge-visible view."""
    by_group = {}
    for o in outputs:
        by_group.setdefault((o.key_word, o.task, o.model, o.seed), {})[o.arm] = o
    rng = random.Random(rand_seed)
    packets = []
    idx = 0
    for (kw, task, model, seed), arms in sorted(by_group.items()):
        if "A" not in arms:
            continue
        task_text = TASKS[task].format(w=kw)
        for ctrl in CO_PRIMARIES:
            if ctrl not in arms:
                continue
            pair = [("A", arms["A"].output_text), (ctrl, arms[ctrl].output_text)]
            rng.shuffle(pair)                         # deterministic left/right randomization
            outs = [{"id": f"Output {i + 1}", "text": txt} for i, (_a, txt) in enumerate(pair)]
            truth = {f"Output {i + 1}": arm for i, (arm, _t) in enumerate(pair)}
            pid = f"{kw}|{task}|{model}|{seed}|A_vs_{ctrl}"
            packets.append(JudgePacket(pid, f"P{idx:05d}", ctrl, kw, task_text, outs, truth))
            idx += 1
    return packets


# ---------------------------------------------------------------- 9. judge response schema --------
@dataclass
class JudgeResponse:
    packet_id: str
    choice: str                 # "left" | "right" | "tie" | "both_bad"
    judge_id: str = "mock"


def mock_judge(packets, rand_seed, a_win_prob=0.5):
    """DRY-RUN mock judging that exercises the scorer. Deterministic from rand_seed. a_win_prob steers
    how often the A side is chosen (0.0 => A always loses, 1.0 => A always wins). Forced-choice only
    (tie/both_bad are supported by the scorer but not emitted by this mock)."""
    rng = random.Random(rand_seed)
    responses = []
    for p in packets:
        a_side = "left" if p.truth["Output 1"] == "A" else "right"
        other = "right" if a_side == "left" else "left"
        choice = a_side if rng.random() < a_win_prob else other
        responses.append(JudgeResponse(p.packet_id, choice))
    return responses


# ---------------------------------------------------------------- 10. pairwise aggregator ---------
def _choice_to_a_score(packet, choice):
    """Map a forced-choice response to an A-win score in {0, 0.5, 1}."""
    if choice in ("tie", "both_bad"):
        return 0.5
    picked_id = "Output 1" if choice == "left" else "Output 2"
    return 1.0 if packet.truth[picked_id] == "A" else 0.0


def aggregate_pairwise(packets, responses):
    """Per co-primary (A vs D/R/S/C/X): item-clustered A-win scores. Cluster unit = (key_word, task).
    Returns {control: {"item_scores":[...], "win_rate":float, "n_items":int, "n_judgments":int}}."""
    by_pid = {p.packet_id: p for p in packets}
    # control -> item(key_word,task) -> list of A-win scores across model/seed/judge
    buckets = {c: {} for c in CO_PRIMARIES}
    for resp in responses:
        p = by_pid.get(resp.packet_id)
        if p is None:
            continue
        item = tuple(p.packet_id.split("|")[:2])      # (key_word, task)
        buckets[p.control_arm].setdefault(item, []).append(_choice_to_a_score(p, resp.choice))
    out = {}
    for c, items in buckets.items():
        item_scores = [statistics.mean(v) for _k, v in sorted(items.items())]
        n_j = sum(len(v) for v in items.values())
        out[c] = {"item_scores": item_scores,
                  "win_rate": statistics.mean(item_scores) if item_scores else float("nan"),
                  "n_items": len(item_scores), "n_judgments": n_j}
    return out


# ---------------------------------------------------------------- 11. clustered bootstrap ---------
def clustered_bootstrap_ci(item_scores, n_boot=1000, seed=0, alpha=0.05):
    """Percentile bootstrap over item-clustered units. Returns (mean, ci_lo, ci_hi, p_one_sided_gt_half).
    p is the bootstrap fraction of resampled means <= 0.5 (one-sided test that A beats the control)."""
    n = len(item_scores)
    if n == 0:
        return float("nan"), float("nan"), float("nan"), 1.0
    rng = random.Random(seed)
    means = []
    for _ in range(n_boot):
        s = [item_scores[rng.randrange(n)] for _ in range(n)]
        means.append(statistics.mean(s))
    means.sort()
    lo = means[int((alpha / 2) * n_boot)]
    hi = means[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]
    p = sum(1 for m in means if m <= 0.5) / n_boot
    return statistics.mean(item_scores), lo, hi, p


# ---------------------------------------------------------------- 12. Holm-Bonferroni -------------
def holm_bonferroni(pvals, alpha=0.05):
    """Return {key: (adjusted_p, reject_bool)} for a dict of {key: p}. Standard step-down Holm."""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    out = {}
    prev = 0.0
    still_rejecting = True
    for i, (k, p) in enumerate(items):
        adj = min(1.0, (m - i) * p)
        adj = max(adj, prev)                          # enforce monotonic non-decreasing adjusted p
        prev = adj
        reject = still_rejecting and adj <= alpha
        if not reject:
            still_rejecting = False
        out[k] = (adj, reject)
    return out


# ---------------------------------------------------------------- 13. verdict-label applier -------
def apply_verdict(results, flags=None):
    """results: {control: {"ci_lo":float, "holm_reject":bool}} for D/R/S/C/X.
    flags: optional {"invalid_posthoc","leakage_fail","correctness_degraded","not_robust": bool}.
    'A beats control' == ci_lo > 0.5 AND Holm-rejected. Returns one VERDICT_LABELS entry."""
    flags = flags or {}
    if flags.get("invalid_posthoc"):
        return "INVALID_POSTHOC"
    if flags.get("leakage_fail"):
        return "LEAKAGE_FAIL"
    if flags.get("correctness_degraded"):
        return "CORRECTNESS_DEGRADED"
    if flags.get("not_robust"):
        return "NOT_ROBUST"

    def beats(c):
        r = results.get(c, {})
        return bool(r.get("ci_lo", 0.0) > 0.5 and r.get("holm_reject", False))

    beaten = {c for c in CO_PRIMARIES if beats(c)}
    if beaten <= {"X"}:                     # beats nothing, or only the weakest control
        return "NO_SIGNAL"
    if "D" not in beaten:
        return "DICTIONARY_DOMINATES"
    if not {"R", "S"} <= beaten:
        return "RANDOM_OR_SCRAMBLED_MATCHES"
    if "C" not in beaten:
        return "SURFACE_STRUCTURE_EXPLAINS"
    if "X" not in beaten:
        return "NO_SIGNAL"
    return "LIMITED_GENERATION_UTILITY"     # beats ALL of D/R/S/C/X


def score_from_aggregate(agg, boot_seed=BOOTSTRAP["seed"], n_boot=BOOTSTRAP["n_boot"]):
    """Convenience: aggregate -> per-control CI + Holm -> results dict for apply_verdict."""
    per = {}
    pvals = {}
    for c in CO_PRIMARIES:
        mean, lo, hi, p = clustered_bootstrap_ci(agg[c]["item_scores"], n_boot=n_boot, seed=boot_seed)
        per[c] = {"win_rate": mean, "ci_lo": lo, "ci_hi": hi, "p": p}
        pvals[c] = p
    holm = holm_bonferroni(pvals)
    for c in CO_PRIMARIES:
        per[c]["holm_p"], per[c]["holm_reject"] = holm[c]
    return per


# ---------------------------------------------------------------- dry-run demo (no files) ---------
def dry_run(a_win_prob=0.5, boot_seed=0, n_boot=400, verbose=True, conditioning_fn=None):
    """Full mock pipeline. Returns a summary dict. Writes NO files, calls NO real model.
    conditioning_fn: None => labeled mock conditioning; pass b1_real_conditioning.real_core for real."""
    inputs = load_frozen_inputs()
    rows = expand_rows(inputs)
    adapter = MockModelAdapter()
    outputs = run_generation(rows, adapter, dry_run=True, conditioning_fn=conditioning_fn)
    leaks = scan_outputs(outputs)
    packets = build_judge_packets(outputs, rand_seed=40411)
    responses = mock_judge(packets, rand_seed=50513, a_win_prob=a_win_prob)
    agg = aggregate_pairwise(packets, responses)
    per = score_from_aggregate(agg, boot_seed=boot_seed, n_boot=n_boot)
    verdict = apply_verdict({c: per[c] for c in CO_PRIMARIES})
    summary = {
        "rows": len(rows),
        "rows_primary": sum(1 for r in rows if r.stratum == "primary"),
        "rows_privative": sum(1 for r in rows if r.stratum == "privative"),
        "mock_generations": adapter.call_count,
        "leak_hits": len(leaks),
        "judge_packets": len(packets),
        "co_primary_win_rates": {c: round(per[c]["win_rate"], 3) for c in CO_PRIMARIES},
        "co_primary_ci_lo": {c: round(per[c]["ci_lo"], 3) for c in CO_PRIMARIES},
        "verdict_MOCK": verdict,
        "no_real_model_called": adapter.is_real is False,
        "no_files_written": True,
    }
    if verbose:
        print(BANNER)
        for k, v in summary.items():
            print(f"  {k}: {v}")
        print("no_real_model_called: true | no_real_scoring: true | not_evidence: true")
        print(BANNER)
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description="B1 dry-run harness — MOCK ONLY (no real model, no scoring).")
    ap.add_argument("--a-win-prob", type=float, default=0.5,
                    help="mock judge A-side probability (dry-run only; not evidence)")
    ap.add_argument("--n-boot", type=int, default=400)
    args = ap.parse_args(argv)
    dry_run(a_win_prob=args.a_win_prob, n_boot=args.n_boot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
