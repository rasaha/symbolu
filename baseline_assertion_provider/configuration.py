"""Baseline assertion provider configuration + factory."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from governance_providers.api import ProviderConfigurationError

from .core import BaselineAssertionEngine
from .provider import BaselineAssertionProvider


@dataclass(frozen=True)
class BaselineAssertionSettings:
    provider_id: str = "baseline-assertion"
    default: bool = False
    contract_version: str = "1.0.0"
    fail_safe: bool = True

    def validate(self) -> None:
        if self.contract_version.split(".")[0] != "1":
            raise ProviderConfigurationError(
                f"unsupported contract_version '{self.contract_version}'")


def build_baseline_assertion_provider(engine: Optional[BaselineAssertionEngine] = None, *,
                                      settings: Optional[BaselineAssertionSettings] = None
                                      ) -> BaselineAssertionProvider:
    settings = settings or BaselineAssertionSettings()
    settings.validate()
    return BaselineAssertionProvider(
        engine or BaselineAssertionEngine(), provider_id=settings.provider_id,
        default=settings.default, fail_safe=settings.fail_safe)


__all__ = ["BaselineAssertionSettings", "build_baseline_assertion_provider"]
