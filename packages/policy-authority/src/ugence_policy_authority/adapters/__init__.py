"""Policy-family adapters registered with the shared authority core.

UVI is the **first** adapter, not the owner of the boundary. Additional
families are added here (or by any consumer) without touching the core.
"""

from .uvi import (
    SUPPORTED_UVI_POLICY_FAMILIES,
    UVI_ADAPTER_ID,
    UviPolicyFamilyAdapter,
    uvi_coordinate,
)

__all__ = [
    "UVI_ADAPTER_ID",
    "SUPPORTED_UVI_POLICY_FAMILIES",
    "UviPolicyFamilyAdapter",
    "uvi_coordinate",
]
