"""Trace adapters — real public traces → canonical workload series."""

from cloud_controller.replay.adapters.base import (
    AdapterStatus,
    TraceAdapter,
    TraceSeries,
)
from cloud_controller.replay.adapters.azure_llm import AzureLLMInferenceAdapter
from cloud_controller.replay.adapters.azure_vm_noise import AzureVMNoiseAdapter
from cloud_controller.replay.adapters.alibaba_microservices import (
    AlibabaMicroservicesAdapter,
)
from cloud_controller.replay.adapters.google_borg import GoogleBorgAdapter

__all__ = [
    "AdapterStatus",
    "TraceAdapter",
    "TraceSeries",
    "AzureLLMInferenceAdapter",
    "AzureVMNoiseAdapter",
    "AlibabaMicroservicesAdapter",
    "GoogleBorgAdapter",
]
