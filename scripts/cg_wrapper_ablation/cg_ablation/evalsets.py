"""Pre-registered eval-set loading for the CG-wrapper ablation.

The sets themselves live as JSONL under ``scripts/cg_wrapper_ablation/eval_sets/`` so they are
version-controlled and offline-reproducible. This module only loads + validates them.

Seeds and the set registry are frozen here (pre-registration). See RESEARCH_PLAN.md §4.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

# Pre-registered seeds (RESEARCH_PLAN.md §4). Do not change after results are seen.
SEEDS: List[int] = [0, 1, 2, 3, 4]

# Registry: name -> (filename, task kind). Frozen at pre-registration.
EVAL_SETS: Dict[str, Dict[str, str]] = {
    "gsm8k_style": {"file": "gsm8k_style.jsonl", "kind": "exact_match"},
    "format_constraints": {"file": "format_constraints.jsonl", "kind": "constraint"},
    "json_format": {"file": "json_format.jsonl", "kind": "json"},
}

_EVAL_DIR = Path(__file__).resolve().parent.parent / "eval_sets"


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path.name}:{line_no}: invalid JSON ({exc})") from exc
    return rows


def load_eval_set(name: str, eval_dir: Path | None = None) -> List[Dict[str, Any]]:
    """Load and minimally validate a pre-registered eval set by name."""
    if name not in EVAL_SETS:
        raise KeyError(f"unknown eval set {name!r}; known: {sorted(EVAL_SETS)}")
    base = eval_dir or _EVAL_DIR
    rows = _read_jsonl(base / EVAL_SETS[name]["file"])
    kind = EVAL_SETS[name]["kind"]
    for r in rows:
        if "id" not in r or "prompt" not in r:
            raise ValueError(f"{name}: every row needs 'id' and 'prompt'")
        if kind == "exact_match" and "answer" not in r:
            raise ValueError(f"{name}: exact_match rows need integer 'answer'")
        if kind == "constraint" and "constraints" not in r:
            raise ValueError(f"{name}: constraint rows need 'constraints' list")
        if kind == "json" and "required_keys" not in r:
            raise ValueError(f"{name}: json rows need 'required_keys' list")
    return rows


def load_all(eval_dir: Path | None = None) -> Dict[str, List[Dict[str, Any]]]:
    """Load every registered eval set."""
    return {name: load_eval_set(name, eval_dir) for name in EVAL_SETS}
