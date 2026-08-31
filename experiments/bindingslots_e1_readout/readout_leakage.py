#!/usr/bin/env python3
"""Leakage / shortcut suite for the readout diagnostic = inherited temporal suite + AST no-oracle proof
over every readout forward + shortcut-baseline ceiling (lexical and global-latest must be <= 0.15 on the
final cohort). Torch-free (AST + source scan + the inherited torch-free checks)."""
from __future__ import annotations

import ast
import pathlib
import sys

TEMPORAL_DIR = pathlib.Path(__file__).resolve().parents[1] / "bindingslots_e1_temporal"
if str(TEMPORAL_DIR) not in sys.path:
    sys.path.insert(0, str(TEMPORAL_DIR))
import temporal_leakage as TL         # noqa: E402

import readout_config as C            # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
MODEL_SRC = HERE / "readout_model.py"

BANNED = {"target_index", "target_value", "key_values", "identity_pools", "status_of",
          "build_eval_splits", "cohort", "_entity", "meta"}
# forward paths that must be oracle-free
FORWARD_METHODS = {"forward", "scores", "_pooled_keys", "_score_from_pooled"}
ATTN_FORWARD_CLASSES = {"_AttnHead"}


def _names(node):
    out = set()
    for x in ast.walk(node):
        if isinstance(x, ast.Name):
            out.add(x.id)
        elif isinstance(x, ast.Attribute):
            out.add(x.attr)
    return out


def check_scoring_no_oracle():
    tree = ast.parse(MODEL_SRC.read_text())
    problems = []
    scores_sig_ok = False
    for cls in ast.walk(tree):
        if not isinstance(cls, ast.ClassDef):
            continue
        if cls.name == "Readout":
            for fn in cls.body:
                if isinstance(fn, ast.FunctionDef) and fn.name in FORWARD_METHODS:
                    hit = _names(fn) & BANNED
                    if hit:
                        problems.append(f"Readout.{fn.name} references {sorted(hit)}")
                    if fn.name == "scores":
                        args = {a.arg for a in fn.args.args}
                        # scores(self, key_tokens, query_tokens, tau=None) — no ground-truth arg
                        scores_sig_ok = args <= {"self", "key_tokens", "query_tokens", "tau"} and \
                            {"key_tokens", "query_tokens"} <= args
        if cls.name in ATTN_FORWARD_CLASSES:
            for fn in cls.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == "forward":
                    hit = _names(fn) & BANNED
                    if hit:
                        problems.append(f"{cls.name}.forward references {sorted(hit)}")
    if not scores_sig_ok:
        problems.append("Readout.scores signature admits a non-(key,query,tau) argument")
    return {"pass": not problems, "problems": problems, "scores_signature_ok": scores_sig_ok}


def check_no_table_import():
    banned = ("ephemeral_table", "EphemeralTable", "v100_table", "external_fallback")
    hit = []
    for p in [HERE / "readout_model.py", HERE / "readout_train.py", HERE / "readout_eval.py",
              HERE / "readout_gates.py"]:
        if p.exists():
            s = p.read_text()
            hit += [f"{p.name}:{b}" for b in banned if b in s]
    return {"pass": not hit, "banned_hits": hit}


def shortcut_baselines(eval_splits, ceiling=None):
    """Lexical-overlap matcher and global-latest heuristic must both be <= ceiling on the final cohort."""
    ceiling = C.GATES["shortcut_baseline_max"] if ceiling is None else ceiling
    valid = [e for v in eval_splits.values() for e in v if e["target_index"] >= 0]
    lex = TL.check_lexical_overlap_uninformative(valid)["lexical_overlap_accuracy"]
    glat = TL.check_latest_heuristic_uninformative(eval_splits["T4_latest"])["global_latest_heuristic_accuracy"]
    return {"pass": (lex <= ceiling and glat <= ceiling), "ceiling": ceiling,
            "lexical_accuracy": lex, "global_latest_accuracy": glat}


def run_all(eval_splits):
    r = dict(TL.run_all(eval_splits))
    inherited_pass = r.pop("all_pass")
    r["factor_scoring_no_oracle"] = check_scoring_no_oracle()
    r["readout_no_table_import"] = check_no_table_import()
    r["shortcut_baselines"] = shortcut_baselines(eval_splits)
    r["inherited_suite_pass"] = inherited_pass
    r["all_pass"] = (inherited_pass and r["factor_scoring_no_oracle"]["pass"]
                     and r["readout_no_table_import"]["pass"] and r["shortcut_baselines"]["pass"])
    return r
