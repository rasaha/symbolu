"""Model execution fixture layer (Phase 10). Default: recorded/deterministic fixture. Never implies a
live model ran. Stdlib-only, deterministic.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

FIXTURE_VERSION = "fixture_v1"


@dataclass
class ExecutionResult:
    selected_model: str
    fixture_model_identity: str
    execution_occurred: bool          # ALWAYS False in fixture mode
    provider: str
    model_family: str
    prompt_hash: str
    output_hash: str
    output_text: str
    token_estimate_in: int
    token_estimate_out: int
    cost_estimate_usd: float
    latency_units: int
    execution_error: str = ""
    fallback_path: str = ""
    mode: str = "fixture"


def execute(selected_model: str, prompt: str, recorded_output: str, registry_entry: Dict[str, Any],
            mode: str = "fixture") -> ExecutionResult:
    if mode not in ("fixture", "recorded", "opt_in_local"):
        mode = "fixture"
    occurred = False   # opt_in_local is not enabled in this track; never runs a live model by default
    tok_in = max(1, len(prompt) // 4)
    tok_out = max(1, len(recorded_output) // 4)
    price_in = registry_entry.get("price_in_per_mtok", registry_entry.get("cost", 0.0))
    price_out = registry_entry.get("price_out_per_mtok", registry_entry.get("cost", 0.0))
    cost = round((tok_in * price_in + tok_out * price_out) / 1e6, 8) if price_in or price_out else \
        round(registry_entry.get("cost", 0.0) * 0.001, 8)
    return ExecutionResult(
        selected_model=selected_model,
        fixture_model_identity=f"{registry_entry.get('provider','?')}/{selected_model}#fixture",
        execution_occurred=occurred, provider=registry_entry.get("provider", "?"),
        model_family=registry_entry.get("family", "?"),
        prompt_hash=hashlib.sha256(prompt.encode()).hexdigest()[:16],
        output_hash=hashlib.sha256(recorded_output.encode()).hexdigest()[:16],
        output_text=recorded_output, token_estimate_in=tok_in, token_estimate_out=tok_out,
        cost_estimate_usd=cost, latency_units=2, mode=mode)
