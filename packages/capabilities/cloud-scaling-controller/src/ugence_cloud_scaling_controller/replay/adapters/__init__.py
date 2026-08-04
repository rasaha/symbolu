"""Trace adapters — real public traces → canonical workload series."""

from ugence_cloud_scaling_controller.replay.adapters.base import (
    AdapterStatus,
    TraceAdapter,
    TraceSeries,
)
from ugence_cloud_scaling_controller.replay.adapters.azure_llm import AzureLLMInferenceAdapter
from ugence_cloud_scaling_controller.replay.adapters.azure_vm_noise import AzureVMNoiseAdapter
from ugence_cloud_scaling_controller.replay.adapters.alibaba_microservices import (
    AlibabaMicroservicesAdapter,
)
from ugence_cloud_scaling_controller.replay.adapters.google_borg import GoogleBorgAdapter
from ugence_cloud_scaling_controller.replay.adapters.partner_prometheus import (
    PartnerPrometheusAdapter,
)

__all__ = [
    "AdapterStatus",
    "TraceAdapter",
    "TraceSeries",
    "AzureLLMInferenceAdapter",
    "AzureVMNoiseAdapter",
    "AlibabaMicroservicesAdapter",
    "GoogleBorgAdapter",
    "PartnerPrometheusAdapter",
]
