"""Deterministic dataset builder: episodes -> {input, output} training/eval examples. Torch-free.

Training uses one identity pool (role 'train'); evaluation uses a disjoint pool (role 'final') so
PATH_DISCOVERY generalization is over unseen identities. Every builder passes through the centralized
fail-closed guard (reserved seeds require the two-key authorization).
"""
from __future__ import annotations

from .base_capability import P0_SUBTASKS, generate_p0
from .generator import SPLITS, generate_split
from .output import serialize_output
from .serializer import serialize_input


def example_from_ctx(ctx) -> dict:
    return {"input": serialize_input(ctx),
            "output": serialize_output(ctx.authoritative_output),
            "split": ctx.split}


def build_examples(seed: int, n_per_split: int, role: str = "train",
                   authorization_token: str | None = None) -> list[dict]:
    out: list[dict] = []
    for s in SPLITS:
        for ctx in generate_split(s, seed, n_per_split, role, authorization_token):
            out.append(example_from_ctx(ctx))
    return out


def build_p0_examples(seed: int, n_per_subtask: int, role: str = "train",
                      authorization_token: str | None = None) -> list[dict]:
    out: list[dict] = []
    for sub in P0_SUBTASKS:
        for ctx in generate_p0(sub, seed, n_per_subtask, role, authorization_token):
            out.append(example_from_ctx(ctx))
    return out


def eval_cohorts_r(seed: int, n: int, role: str = "final",
                   authorization_token: str | None = None) -> dict[str, list]:
    return {s: list(generate_split(s, seed, n, role, authorization_token)) for s in SPLITS}


def eval_cohorts_p0(seed: int, n: int, role: str = "final",
                    authorization_token: str | None = None) -> dict[str, list]:
    return {sub: list(generate_p0(sub, seed, n, role, authorization_token)) for sub in P0_SUBTASKS}


def gold_predictions(cohorts: dict[str, list]) -> dict[str, list]:
    """Turn cohorts {key: [ctx,...]} into {key: [(ctx, gold_output_text),...]} — a perfect-model stand-in
    for torch-free pipeline testing (NOT a model output)."""
    return {k: [(c, serialize_output(c.authoritative_output)) for c in ctxs] for k, ctxs in cohorts.items()}
