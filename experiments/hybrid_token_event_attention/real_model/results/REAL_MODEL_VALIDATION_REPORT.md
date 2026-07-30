# RM1 — Real-Model Validation Report

## STATUS: RESOURCE_BLOCKED

A genuine open-weight causal language model could not be loaded in this environment, so no real-model scientific claim is made. The harness, its unit tests, and the frozen governed architecture were exercised; only the real-model forward pass is blocked.

- Requested model: `mistralai/Mistral-7B-Instruct-v0.3`
- Reason: `missing_packages:torch,transformers`

### Detected environment
```json
{
  "versions": {
    "python": "3.11.15",
    "platform": "Linux-6.18.5-x86_64-with-glibc2.39",
    "torch": null,
    "transformers": null,
    "accelerate": null,
    "safetensors": null,
    "bitsandbytes": null,
    "numpy": null
  },
  "hardware": {
    "cpu_count": 4,
    "total_ram_bytes": 16856244224,
    "cuda_available": false,
    "cuda_device_count": 0,
    "mps_available": false,
    "vram_bytes_per_device": [],
    "supported_fp": [
      "float32"
    ]
  }
}
```

### Exact remediation
```json
{
  "missing_package_or_access_requirement": [
    "torch",
    "transformers"
  ],
  "detected_hardware": {
    "cpu_count": 4,
    "total_ram_bytes": 16856244224,
    "cuda_available": false,
    "cuda_device_count": 0,
    "mps_available": false,
    "vram_bytes_per_device": [],
    "supported_fp": [
      "float32"
    ]
  },
  "estimated_memory_requirement": "Estimated memory ~= parameter_count * bytes_per_param (2 for bf16/fp16, 4 for fp32) plus KV cache and activations; e.g. a 7B model needs ~14 GB in fp16, ~28 GB in fp32, and ~5-6 GB under 4-bit CUDA quantization.",
  "recommended_steps": [
    "pip install -r experiments/hybrid_token_event_attention/real_model/requirements-real-model.txt",
    "Run on a machine with a CUDA GPU (>= 16 GB VRAM for a 7B model in bf16/fp16, or use --load-in-4bit on CUDA for ~6 GB), or a CPU host with >= 32 GB RAM for fp32 (slow).",
    "Recommended command on a suitable machine:\n  export UGENCE_REAL_MODEL_ID=\"mistralai/Mistral-7B-Instruct-v0.3\"\n  python -m experiments.hybrid_token_event_attention.real_model.run_real_model \\\n      --model-id \"$UGENCE_REAL_MODEL_ID\" --mode smoke --limit 20 --device auto --dtype auto"
  ]
}
```

## Final summary

```
Actual model:
mistralai/Mistral-7B-Instruct-v0.3 @ None

Actual-model execution:
RESOURCE_BLOCKED

Corpus:
CONTROLLED

Token-only result:
RESOURCE_BLOCKED

Retrieval result:
RESOURCE_BLOCKED

Governed-event deterministic result:
RESOURCE_BLOCKED

Router-gated event-attention result:
RESOURCE_BLOCKED

Event attention incremental relational gain:
RESOURCE_BLOCKED

Oracle-to-predicted construction gap:
RESOURCE_BLOCKED

Required-event survival:
RESOURCE_BLOCKED

Evidence-ID preservation:
RESOURCE_BLOCKED

Unauthorized-event inclusion:
RESOURCE_BLOCKED

Explanation supported precision:
RESOURCE_BLOCKED

Unsupported-claim recall:
RESOURCE_BLOCKED

Best architecture:
RESOURCE_BLOCKED

Primary bottleneck:
resources

Evidence classification:
RESOURCE BLOCKED

Authorized next step:
hardware rerun
```

RM1 tests an actual frozen token-language model inside the external governed dual-domain architecture. It does not validate FSCS, model-weight adaptation, production deployment, or universal superiority of event attention.
