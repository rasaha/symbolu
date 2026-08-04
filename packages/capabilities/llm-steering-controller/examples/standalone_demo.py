#!/usr/bin/env python3
"""Standalone, offline demo of the advisory LLM Steering Controller.

Run:  PYTHONPATH=../src python standalone_demo.py

Prints a routing recommendation. No provider is contacted; no model is executed.
"""

from __future__ import annotations

import json

from ugence_llm_steering_controller import recommend

REGISTRY = {
    "providers": [
        {"provider_id": "openai", "regions": ["us", "eu"]},
        {"provider_id": "anthropic", "regions": ["us"]},
        {"provider_id": "local", "deployment_mode": "on_prem", "regions": ["eu"]},
    ],
    "models": [
        {"model_id": "gpt-fast", "provider_id": "openai", "modalities_in": ["text"],
         "context_limit": 128000, "structured_output": True, "tool_use": True,
         "cost_class": "medium", "latency_class": "fast", "quality_tier": "advanced",
         "reliability_class": "high", "availability_class": "global"},
        {"model_id": "claude-premium", "provider_id": "anthropic",
         "modalities_in": ["text", "image"], "context_limit": 200000,
         "structured_output": True, "tool_use": True, "cost_class": "high",
         "latency_class": "medium", "quality_tier": "frontier", "privacy_tier": "high",
         "reliability_class": "very_high"},
        {"model_id": "onprem-small", "provider_id": "local", "modalities_in": ["text"],
         "context_limit": 32000, "cost_class": "very_low", "quality_tier": "standard",
         "privacy_tier": "high"},
    ],
}


def main() -> None:
    print("ROUTING RECOMMENDATION ONLY / NO PROVIDER REQUEST WAS EXECUTED\n")
    for pref in ("quality_first", "cost_first", "latency_first"):
        res = recommend(REGISTRY, {
            "task_category": "chat", "quality_preference": pref,
            "requirements": {"estimated_input_tokens": 5000},
        })
        rec = res.recommendation
        print(f"[{pref}] -> {rec.recommended_model} via {rec.recommended_provider} "
              f"(confidence {rec.confidence}, execution_status={rec.execution_status})")

    # A privacy-restricted request fails closed onto high-tier providers only.
    res = recommend(REGISTRY, {
        "privacy_classification": "confidential",
        "requirements": {"estimated_input_tokens": 3000}})
    print("\n[confidential] ->", res.recommendation.recommended_model)
    print("\nfull recommendation (quality_first):")
    print(json.dumps(recommend(REGISTRY, {"quality_preference": "quality_first",
          "requirements": {"estimated_input_tokens": 5000}}).to_dict(), indent=2, sort_keys=True)[:1200], "...")


if __name__ == "__main__":
    main()
