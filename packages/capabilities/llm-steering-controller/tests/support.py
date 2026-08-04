"""Shared deterministic fixtures for the package-local test suite.

All registries are metadata only — no credentials, no live clients, no network.
"""

from __future__ import annotations

from typing import Any, Dict


def base_registry() -> Dict[str, Any]:
    """A small, deterministic registry spanning providers/regions/tiers."""
    return {
        "providers": [
            {"provider_id": "openai", "regions": ["us", "eu"], "trains_on_data": False},
            {"provider_id": "anthropic", "regions": ["us"], "trains_on_data": False},
            {"provider_id": "trainy", "regions": ["us"], "trains_on_data": True},
            {"provider_id": "local", "deployment_mode": "on_prem", "regions": ["eu"]},
        ],
        "models": [
            {
                "model_id": "gpt-fast", "provider_id": "openai",
                "modalities_in": ["text"], "modalities_out": ["text"],
                "context_limit": 128000, "structured_output": True, "tool_use": True,
                "cost_class": "medium", "latency_class": "fast", "quality_tier": "advanced",
                "reliability_class": "high", "availability_class": "global",
                "regions": ["us", "eu"], "capabilities": ["chat", "code"],
            },
            {
                "model_id": "claude-premium", "provider_id": "anthropic",
                "modalities_in": ["text", "image"], "modalities_out": ["text"],
                "context_limit": 200000, "structured_output": True, "tool_use": True,
                "cost_class": "high", "latency_class": "medium", "quality_tier": "frontier",
                "reliability_class": "very_high", "availability_class": "broad",
                "privacy_tier": "high", "regions": ["us"], "capabilities": ["chat", "code", "vision"],
            },
            {
                "model_id": "onprem-small", "provider_id": "local",
                "modalities_in": ["text"], "context_limit": 32000,
                "cost_class": "very_low", "latency_class": "medium", "quality_tier": "standard",
                "reliability_class": "medium", "privacy_tier": "high",
                "regions": ["eu"], "capabilities": ["chat"],
            },
            {
                "model_id": "trainy-cheap", "provider_id": "trainy",
                "modalities_in": ["text"], "context_limit": 64000,
                "cost_class": "very_low", "latency_class": "very_fast", "quality_tier": "economy",
                "reliability_class": "low", "privacy_tier": "standard",
                "regions": ["us"], "capabilities": ["chat"],
            },
            {
                "model_id": "legacy-deprecated", "provider_id": "openai",
                "modalities_in": ["text"], "context_limit": 8000,
                "cost_class": "low", "latency_class": "fast", "quality_tier": "standard",
                "deprecation_state": "deprecated", "regions": ["us"],
            },
        ],
    }


def single_model_registry() -> Dict[str, Any]:
    return {
        "providers": [{"provider_id": "p1", "regions": ["us"]}],
        "models": [{"model_id": "only", "provider_id": "p1", "modalities_in": ["text"],
                    "context_limit": 16000, "regions": ["us"]}],
    }


def tie_registry() -> Dict[str, Any]:
    """Two models with identical metadata (equal score) to exercise tie-breaking."""
    common = {
        "provider_id": "p", "modalities_in": ["text"], "context_limit": 16000,
        "cost_class": "medium", "latency_class": "medium", "quality_tier": "standard",
        "reliability_class": "medium", "availability_class": "broad", "regions": ["us"],
    }
    return {
        "providers": [{"provider_id": "p", "regions": ["us"]}],
        "models": [
            {**common, "model_id": "m-b"},
            {**common, "model_id": "m-a"},
        ],
    }
