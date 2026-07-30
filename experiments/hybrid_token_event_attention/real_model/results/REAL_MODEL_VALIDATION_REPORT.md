# RM1 Real-Model Validation Report

> RM1 tests an actual frozen token-language model inside the external governed dual-domain architecture. It does not validate FSCS, model-weight adaptation, production deployment, or universal superiority of event attention.

## Status: RESOURCE_BLOCKED

The RM1 harness is complete and unit-tested, but an ACTUAL open-weight model could not be loaded in this environment. No real-model scientific claim is made. Per RM1 §2/§16 the harness stops here rather than substitute the stand-in.

### Block detail
```json
{
  "reason": "required package(s) not installed: torch, transformers",
  "requested_model": "mistralai/Mistral-7B-v0.3",
  "detected": {
    "python_version": "3.11.15",
    "platform": "Linux-6.18.5-x86_64-with-glibc2.39",
    "cpu_count": 4,
    "disk_free_gb": 31.87,
    "packages": {
      "torch": null,
      "transformers": null,
      "accelerate": null,
      "safetensors": null,
      "bitsandbytes": null,
      "numpy": null,
      "tokenizers": null
    },
    "cuda_available": false,
    "mps_available": false,
    "gpu_count": 0,
    "vram_gb": null,
    "ram_gb": 16.86,
    "supported_dtypes": [
      "float32"
    ]
  },
  "missing": [
    "torch",
    "transformers"
  ],
  "param_count_estimate": null,
  "est_memory_gb": null,
  "remediation": [
    "pip install -r experiments/hybrid_token_event_attention/real_model/requirements-real-model.txt"
  ],
  "recommended_command": "On a CUDA machine (>=16GB VRAM for a 7B bf16 model) with deps installed:\n  pip install -r experiments/hybrid_token_event_attention/real_model/requirements-real-model.txt\n  export UGENCE_REAL_MODEL_ID=mistralai/Mistral-7B-v0.3\n  python -m experiments.hybrid_token_event_attention.real_model.run_real_model \\\n      --model-id \"$UGENCE_REAL_MODEL_ID\" --mode smoke --limit 20",
  "status": "RESOURCE_BLOCKED"
}
```

### Detected environment
```json
{
  "python_version": "3.11.15",
  "platform": "Linux-6.18.5-x86_64-with-glibc2.39",
  "cpu_count": 4,
  "disk_free_gb": 31.87,
  "packages": {
    "torch": null,
    "transformers": null,
    "accelerate": null,
    "safetensors": null,
    "bitsandbytes": null,
    "numpy": null,
    "tokenizers": null
  },
  "cuda_available": false,
  "mps_available": false,
  "gpu_count": 0,
  "vram_gb": null,
  "ram_gb": 16.86,
  "supported_dtypes": [
    "float32"
  ]
}
```

### Remediation

- pip install -r experiments/hybrid_token_event_attention/real_model/requirements-real-model.txt

### Recommended command
```
On a CUDA machine (>=16GB VRAM for a 7B bf16 model) with deps installed:
  pip install -r experiments/hybrid_token_event_attention/real_model/requirements-real-model.txt
  export UGENCE_REAL_MODEL_ID=mistralai/Mistral-7B-v0.3
  python -m experiments.hybrid_token_event_attention.real_model.run_real_model \
      --model-id "$UGENCE_REAL_MODEL_ID" --mode smoke --limit 20
```


---

Actual model:
    mistralai/Mistral-7B-v0.3

Actual-model execution:
    RESOURCE_BLOCKED

Corpus:
    CONTROLLED (not executed — blocked before inference)

Token-only result:
    RESOURCE_BLOCKED (not measured)

Retrieval result:
    RESOURCE_BLOCKED (not measured)

Governed-event deterministic result:
    RESOURCE_BLOCKED (not measured)

Router-gated event-attention result:
    RESOURCE_BLOCKED (not measured)

Event attention incremental relational gain:
    RESOURCE_BLOCKED (not measured)

Oracle-to-predicted construction gap:
    RESOURCE_BLOCKED (not measured)

Required-event survival:
    RESOURCE_BLOCKED (not measured)

Evidence-ID preservation:
    RESOURCE_BLOCKED (not measured)

Unauthorized-event inclusion:
    RESOURCE_BLOCKED (not measured)

Explanation supported precision:
    RESOURCE_BLOCKED (not measured)

Unsupported-claim recall:
    RESOURCE_BLOCKED (not measured)

Best architecture:
    RESOURCE_BLOCKED

Primary bottleneck:
    resources

Evidence classification:
    RESOURCE BLOCKED

Authorized next step:
    hardware rerun (load an actual open-weight model on a suitable machine with deps installed; see remediation)


> RM1 tests an actual frozen token-language model inside the external governed dual-domain architecture. It does not validate FSCS, model-weight adaptation, production deployment, or universal superiority of event attention.
