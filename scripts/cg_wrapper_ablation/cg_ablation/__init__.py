"""cg_ablation — CPU-safe library for the CG-wrapper generation-quality ablation.

Pure-Python / numpy where possible (metrics, stats, eval-set loading, scorers) so it is
unit-testable without torch or a GPU. Torch-dependent pieces (arms, stub backend, diagnostics)
import torch lazily and skip cleanly when it is absent.

This package is RESEARCH-track only: it evaluates the CG wrapper as a generation-quality
modifier. It does not import or touch governance code (trust observables, JEPA governance,
Vritti/Guna/Kosha governance, shadow/parity).
"""

from .metrics import (
    extract_final_integer,
    exact_match,
    json_parse_ok,
    json_has_keys,
    constraint_satisfied,
    pairwise_agreement,
    paired_bootstrap_ci,
    mcnemar_exact,
    logit_kl_per_token,
    top1_flip_rate,
)
from .evalsets import load_eval_set, EVAL_SETS, SEEDS

__all__ = [
    "extract_final_integer",
    "exact_match",
    "json_parse_ok",
    "json_has_keys",
    "constraint_satisfied",
    "pairwise_agreement",
    "paired_bootstrap_ci",
    "mcnemar_exact",
    "logit_kl_per_token",
    "top1_flip_rate",
    "load_eval_set",
    "EVAL_SETS",
    "SEEDS",
]
