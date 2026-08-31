#!/usr/bin/env python3
"""Leakage / shortcut suite for the factorial = the inherited temporal suite PLUS explicit
no-oracle-at-inference proofs for F1/F2/F3. Torch-free (AST + source scan) so it runs in CI.

The oracle proof is structural: at inference the model's scoring entry points receive ONLY
(key_tokens, query_tokens, tau); no ground-truth target index, target value, evaluator entity label, or
episode metadata is in scope inside any factor's forward. A runtime permutation-equivariance check
(candidate order carries no target information) is run separately in the execution script.
"""
from __future__ import annotations

import ast
import pathlib

TEMPORAL_DIR = pathlib.Path(__file__).resolve().parents[1] / "bindingslots_e1_temporal"
import sys
if str(TEMPORAL_DIR) not in sys.path:
    sys.path.insert(0, str(TEMPORAL_DIR))
import temporal_leakage as TL         # noqa: E402  (inherited suite)

HERE = pathlib.Path(__file__).resolve().parent
MODEL_SRC = HERE / "factor_model.py"

# identifiers that would indicate ground-truth / evaluator / metadata access inside scoring code
BANNED = {"target_index", "target_value", "key_values", "identity_pools", "status_of",
          "build_eval_splits", "cohort", "_entity", "meta"}
SCORE_ENTRY_ARGS = {"scores": {"self", "key_tokens", "query_tokens", "tau"},
                    "forward": {"self", "key_tokens", "query_tokens", "tau"}}
FACTOR_CLASSES = {"F1NullGate", "F2EntityResidual", "F3TemporalResidual"}


def _names(node):
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            out.add(n.id)
        elif isinstance(n, ast.Attribute):
            out.add(n.attr)
    return out


def check_scoring_no_oracle():
    """E1F.scores/forward take only (key_tokens, query_tokens, tau); no banned identifier appears in the
    scoring path or in any factor's forward."""
    tree = ast.parse(MODEL_SRC.read_text())
    problems = []
    sig_ok = {"scores": False, "forward": False}
    for cls in ast.walk(tree):
        if not isinstance(cls, ast.ClassDef):
            continue
        if cls.name == "E1F":
            for fn in cls.body:
                if isinstance(fn, ast.FunctionDef) and fn.name in SCORE_ENTRY_ARGS:
                    args = {a.arg for a in fn.args.args}
                    if args != SCORE_ENTRY_ARGS[fn.name]:
                        problems.append(f"E1F.{fn.name} args {sorted(args)} != {sorted(SCORE_ENTRY_ARGS[fn.name])}")
                    else:
                        sig_ok[fn.name] = True
                    hit = _names(fn) & BANNED
                    if hit:
                        problems.append(f"E1F.{fn.name} references {sorted(hit)}")
        if cls.name in FACTOR_CLASSES:
            for fn in cls.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == "forward":
                    hit = _names(fn) & BANNED
                    if hit:
                        problems.append(f"{cls.name}.forward references {sorted(hit)}")
    if not all(sig_ok.values()):
        problems.append(f"missing/renamed scoring entry point(s): {sig_ok}")
    return {"pass": not problems, "problems": problems, "signature_ok": sig_ok}


def check_no_table_import():
    banned = ("ephemeral_table", "EphemeralTable", "v100_table", "external_fallback")
    hit = []
    for p in [HERE / "factor_model.py", HERE / "factor_train.py", HERE / "factor_eval.py",
              HERE / "factor_gates.py"]:
        if p.exists():
            s = p.read_text()
            hit += [f"{p.name}:{b}" for b in banned if b in s]
    return {"pass": not hit, "banned_hits": hit}


def run_all(eval_splits):
    r = dict(TL.run_all(eval_splits))                 # inherited suite (renames all_pass below)
    inherited_pass = r.pop("all_pass")
    r["factor_scoring_no_oracle"] = check_scoring_no_oracle()
    r["factor_no_table_import"] = check_no_table_import()
    r["inherited_suite_pass"] = inherited_pass
    r["all_pass"] = inherited_pass and r["factor_scoring_no_oracle"]["pass"] and r["factor_no_table_import"]["pass"]
    return r
