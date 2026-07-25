"""Baseline action provider configuration + factory."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from governance_providers.api import ProviderConfigurationError

from .core import BaselineActionEngine
from .provider import BaselineActionProvider


@dataclass(frozen=True)
class BaselineActionSettings:
    provider_id: str = "baseline-action"
    default: bool = False
    contract_version: str = "1.0.0"

    def validate(self) -> None:
        if self.contract_version.split(".")[0] != "1":
            raise ProviderConfigurationError(
                f"unsupported contract_version '{self.contract_version}'")


def build_baseline_action_provider(engine: Optional[BaselineActionEngine] = None, *,
                                   settings: Optional[BaselineActionSettings] = None
                                   ) -> BaselineActionProvider:
    settings = settings or BaselineActionSettings()
    settings.validate()
    return BaselineActionProvider(engine or BaselineActionEngine(),
                                  provider_id=settings.provider_id, default=settings.default)


__all__ = ["BaselineActionSettings", "build_baseline_action_provider"]
