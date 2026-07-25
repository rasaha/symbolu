"""Pilot provider configuration (Task 104).

Declares provider identity, kind, enabled state, default assignment, and mode via
the framework's neutral ``ProvidersConfiguration``. Provider *selection* flows
through this config + the registry; engine *behavior* comes from scenario policy.
"""
from __future__ import annotations

from governance_providers.api import ProviderKind, ProvidersConfiguration

#: The canonical pilot provider configuration (matches docs + Task 104 YAML).
PILOT_PROVIDERS_CONFIG: dict = {
    "providers": {
        "assertion_governance": {
            "default": "tap-primary",
            "registered": [
                {"id": "tap-primary", "implementation": "tap", "enabled": True,
                 "contract_version": "1.0",
                 "settings": {"mode": "in_process", "evidence_resolution": "caller_supplied"}},
            ],
        },
        "action_governance": {
            "default": "actiongate-primary",
            "registered": [
                {"id": "actiongate-primary", "implementation": "actiongate", "enabled": True,
                 "contract_version": "1.0", "settings": {"mode": "in_process"}},
            ],
        },
    }
}


def load_config() -> ProvidersConfiguration:
    cfg = ProvidersConfiguration.from_mapping(PILOT_PROVIDERS_CONFIG)
    cfg.validate()
    return cfg


def assertion_provider_id(cfg: ProvidersConfiguration) -> str:
    return cfg.default_for(ProviderKind.ASSERTION_GOVERNANCE)


def action_provider_id(cfg: ProvidersConfiguration) -> str:
    return cfg.default_for(ProviderKind.ACTION_GOVERNANCE)
