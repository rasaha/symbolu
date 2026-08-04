#!/usr/bin/env python3
"""Generate the deterministic local fixture scenarios (section 12 coverage).

Writes one JSON scenario per case into ``fixtures/`` plus a combined ``fixtures/suite.json``.
Every scenario is a self-contained ``{name, registry, request, [policy], [expect]}`` object.
These are FAKE_LOCAL_FIXTURE inputs: no provider is contacted, no model is executed.

Run:  python packages/capabilities/llm-steering-controller/scripts/generate_fixtures.py
"""

from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.dirname(_HERE)
_FIX = os.path.join(_PKG, "fixtures")
sys.path.insert(0, os.path.join(_PKG, "tests"))
sys.path.insert(0, os.path.join(_PKG, "src"))

from support import base_registry, single_model_registry, tie_registry  # noqa: E402

REG = base_registry()


def scn(name, request, expect=None, policy=None, registry=None):
    s = {"name": name, "registry": registry or REG, "request": request}
    if policy is not None:
        s["policy"] = policy
    if expect is not None:
        s["expect"] = expect
    return s


SCENARIOS = [
    scn("single_eligible_model",
        {"task_category": "chat", "approved_models": ["gpt-fast"],
         "requirements": {"estimated_input_tokens": 4000}},
        {"status": "RECOMMENDED", "recommended_model": "gpt-fast"}),
    scn("multiple_eligible_models_quality_first",
        {"task_category": "chat", "quality_preference": "quality_first",
         "requirements": {"estimated_input_tokens": 4000}},
        {"status": "RECOMMENDED", "recommended_model": "claude-premium"}),
    scn("no_eligible_model_context",
        {"requirements": {"min_context_window": 10_000_000}},
        {"status": "NO_ELIGIBLE_CANDIDATE"}),
    scn("privacy_restricted_request",
        {"privacy_classification": "restricted",
         "requirements": {"estimated_input_tokens": 2000}},
        {"status": "RECOMMENDED"}),  # only high-tier, non-training providers survive
    scn("regional_restriction_eu",
        {"data_residency": ["eu"], "requirements": {"estimated_input_tokens": 2000}},
        {"status": "RECOMMENDED"}),
    scn("cost_limited_request",
        {"cost_budget": 0.10, "requirements": {"estimated_input_tokens": 1000}},
        {"status": "RECOMMENDED"}),
    scn("latency_limited_request",
        {"latency_budget_ms": 500, "requirements": {"estimated_input_tokens": 1000}},
        {"status": "RECOMMENDED"}),
    scn("long_context_request",
        {"requirements": {"estimated_input_tokens": 150000, "min_context_window": 150000}},
        {"status": "RECOMMENDED", "recommended_model": "claude-premium"}),
    scn("structured_output_requirement",
        {"requirements": {"structured_output_required": True, "estimated_input_tokens": 2000}},
        {"status": "RECOMMENDED"}),
    scn("tool_use_requirement",
        {"requirements": {"tool_use_required": True, "estimated_input_tokens": 2000}},
        {"status": "RECOMMENDED"}),
    scn("multimodal_requirement",
        {"requirements": {"required_modalities": ["image"], "estimated_input_tokens": 2000}},
        {"status": "RECOMMENDED", "recommended_model": "claude-premium"}),
    scn("provider_prohibited",
        {"prohibited_providers": ["anthropic", "trainy", "local"],
         "requirements": {"estimated_input_tokens": 2000}},
        {"status": "RECOMMENDED", "recommended_model": "gpt-fast"}),
    scn("model_deprecated_excluded",
        {"approved_models": ["legacy-deprecated"],
         "requirements": {"estimated_input_tokens": 1000}},
        {"status": "NO_ELIGIBLE_CANDIDATE"}),
    scn("missing_capability_metadata",
        {"requirements": {"required_capabilities": ["vision"], "estimated_input_tokens": 2000}},
        {"status": "RECOMMENDED", "recommended_model": "claude-premium"}),
    scn("unknown_capability_unsupported",
        {"requirements": {"required_capabilities": ["telepathy"], "estimated_input_tokens": 2000}},
        {"status": "NO_ELIGIBLE_CANDIDATE"}),
    scn("fallback_permitted",
        {"fallback_permitted": True, "requirements": {"estimated_input_tokens": 2000}},
        {"status": "RECOMMENDED"}),
    scn("fallback_prohibited",
        {"fallback_permitted": False, "requirements": {"estimated_input_tokens": 2000}},
        {"status": "RECOMMENDED"}),
    scn("equal_score_tie",
        {"requirements": {"estimated_input_tokens": 2000}},
        {"status": "RECOMMENDED", "recommended_model": "m-a"}, registry=tie_registry()),
    scn("policy_version_change",
        {"policy_version": "steering-policy-CUSTOM-9",
         "requirements": {"estimated_input_tokens": 2000}},
        {"status": "RECOMMENDED"}),
    scn("single_model_registry_only",
        {"requirements": {"estimated_input_tokens": 2000}},
        {"status": "RECOMMENDED", "recommended_model": "only"},
        registry=single_model_registry()),
]


def main() -> int:
    os.makedirs(_FIX, exist_ok=True)
    for s in SCENARIOS:
        path = os.path.join(_FIX, f"scenario_{s['name']}.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(s, sort_keys=True, indent=2) + "\n")
    suite_path = os.path.join(_FIX, "suite.json")
    with open(suite_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"scenarios": SCENARIOS}, sort_keys=True, indent=2) + "\n")
    print(f"wrote {len(SCENARIOS)} scenarios + suite.json to {_FIX}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
