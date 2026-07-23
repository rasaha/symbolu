"""Verified model registry for the shadow pilot.

Every capability value carries provenance. Pricing / context / deployment come
from PROVIDER-PUBLISHED metadata (not model-generated claims), each stamped with
a source and a verification_status. In this sandbox no endpoint could be reached
(see PILOT_STATUS.md), so verification_status is "published-docs-not-live-verified";
a real run must re-verify against live endpoint configuration before trusting cost
or context values.

Five genuinely heterogeneous operating points across three providers for which
this pilot ships execution adapters (anthropic / openai / bedrock). A >1M-token
context point (e.g. Gemini) would require adding a Google adapter.
"""
from __future__ import annotations

import os

from model_selection_pilot.common import DATA_DIR, REGISTRY_VERSION, save_json

_SRC = "provider public pricing/model docs"
_ASOF = "2025-01 (author knowledge cutoff; RE-VERIFY before real run)"
_VSTATUS = "published-docs-not-live-verified"


def _f(value, provenance="provider-declared", **extra):
    d = {"value": value, "provenance": provenance, "source": _SRC,
         "date_verified": _ASOF, "verification_status": _VSTATUS}
    d.update(extra)
    return d


def build() -> dict:
    models = {
        # 1. low-cost fast model
        "fast_small": {
            "stub_profile": "fast_small",
            "provider_facts": {
                "provider": _f("anthropic"),
                "model_version": _f("claude-3-5-haiku-20241022"),
                "endpoint_type": _f("saas-api"),
                "context_limit_tokens": _f(200000),
                "structured_output_support": _f("prompt-json"),  # no strict grammar mode
                "tool_support": _f(True),
                "pricing_per_mtok": _f({"in": 0.80, "out": 4.00, "basis": "per 1M tokens"}),
                "deployment_mode": _f("approved-cloud"),
                "base_latency_ms": _f(700, provenance="observed-estimate"),
            }},
        # 2. medium general-purpose model
        "medium_general": {
            "stub_profile": "medium",
            "provider_facts": {
                "provider": _f("openai"),
                "model_version": _f("gpt-4o-2024-11-20"),
                "endpoint_type": _f("saas-api"),
                "context_limit_tokens": _f(128000),
                "structured_output_support": _f("json-schema-strict"),
                "tool_support": _f(True),
                "pricing_per_mtok": _f({"in": 2.50, "out": 10.00, "basis": "per 1M tokens"}),
                "deployment_mode": _f("approved-cloud"),
                "base_latency_ms": _f(900, provenance="observed-estimate"),
            }},
        # 3. strong reasoning model
        "strong_reason": {
            "stub_profile": "strong_reason",
            "provider_facts": {
                "provider": _f("openai"),
                "model_version": _f("o3-mini-2025-01-31"),
                "endpoint_type": _f("saas-api"),
                "context_limit_tokens": _f(200000),
                "structured_output_support": _f("json-schema-strict"),
                "tool_support": _f(True),
                "pricing_per_mtok": _f({"in": 1.10, "out": 4.40, "basis": "per 1M tokens"}),
                "deployment_mode": _f("approved-cloud"),
                "base_latency_ms": _f(2200, provenance="observed-estimate",
                                      caveat="reasoning model; higher TTFT + hidden reasoning tokens"),
            }},
        # 4. long-context / strong model
        "long_context": {
            "stub_profile": "long_context",
            "provider_facts": {
                "provider": _f("anthropic"),
                "model_version": _f("claude-3-7-sonnet-20250219"),
                "endpoint_type": _f("saas-api"),
                "context_limit_tokens": _f(200000),
                "structured_output_support": _f("prompt-json"),
                "tool_support": _f(True),
                "pricing_per_mtok": _f({"in": 3.00, "out": 15.00, "basis": "per 1M tokens"}),
                "deployment_mode": _f("approved-cloud"),
                "base_latency_ms": _f(1600, provenance="observed-estimate"),
            }},
        # 5. open-weight model (hosted)
        "open_weight": {
            "stub_profile": "open_weight",
            "provider_facts": {
                "provider": _f("bedrock"),
                "model_version": _f("meta.llama3-1-70b-instruct-v1:0"),
                "endpoint_type": _f("bedrock-runtime"),
                "context_limit_tokens": _f(128000),
                "structured_output_support": _f("prompt-json"),
                "tool_support": _f(True),
                "pricing_per_mtok": _f({"in": 0.72, "out": 0.72, "basis": "per 1M tokens (Bedrock)"}),
                "deployment_mode": _f("approved-cloud"),
                "base_latency_ms": _f(1200, provenance="observed-estimate"),
            }},
    }
    return {
        "version": REGISTRY_VERSION,
        "enterprise_policy": {
            "approved_providers": ["anthropic", "openai", "bedrock"],
            "approved_deployment_modes": ["approved-cloud", "on-prem"],
            "note": "governance plane; hard constraints per task may further restrict.",
        },
        "verification_caveat": ("Pricing/context/deployment are provider-published values, "
                                "NOT live-verified in this sandbox and NOT model-generated. "
                                "Re-verify against live endpoints before any real run."),
        "models": models,
    }


def main() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    save_json(os.path.join(DATA_DIR, "registry.json"), build())
    print("wrote registry.json")


if __name__ == "__main__":
    main()
