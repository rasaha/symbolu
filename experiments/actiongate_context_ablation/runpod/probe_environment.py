"""Environment probe for the RunPod Qwen run. Human-readable + JSON. Fails loudly.

A primary run must never silently fall back to CPU or the mock reader, so the fatal
checks below refuse to proceed on a broken environment.
"""

from __future__ import annotations

import json
import os
import pathlib
import platform
import shutil
import sys

import runpod_common as RC

_WEIGHT_GLOBS = ("*.safetensors", "model.safetensors.index.json", "pytorch_model*.bin")
_REQUIRED_META = ("config.json", "tokenizer_config.json")


def model_complete(model_dir: str) -> tuple:
    d = pathlib.Path(model_dir)
    if not d.exists():
        return False, "model dir missing"
    for m in _REQUIRED_META:
        if not (d / m).exists():
            return False, f"missing {m}"
    if not any(any(d.glob(g)) for g in _WEIGHT_GLOBS):
        return False, "no weight files"
    return True, "complete"


def _gpu_info():
    try:
        import torch
        if not torch.cuda.is_available():
            return {"cuda_available": False}
        i = 0
        props = torch.cuda.get_device_properties(i)
        return {
            "cuda_available": True,
            "gpu_count": torch.cuda.device_count(),
            "gpu_name": props.name,
            "vram_gb": round(props.total_memory / (1024 ** 3), 2),
            "bf16_supported": bool(torch.cuda.is_bf16_supported()),
            "cuda_version": torch.version.cuda,
            "torch_version": torch.__version__,
        }
    except Exception as e:
        return {"cuda_available": False, "error": e.__class__.__name__}


def _versions():
    out = {}
    for mod in ("torch", "transformers", "accelerate", "safetensors", "huggingface_hub"):
        try:
            out[mod] = __import__(mod).__version__
        except Exception:
            out[mod] = None
    return out


def _benchmark_imports():
    try:
        from actiongate_context_ablation import real_llm_bench, llm_tasks, llm_client  # noqa: F401
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": f"{e.__class__.__name__}: {RC.redact(str(e))}"}


def probe(config=None) -> dict:
    config = config or RC.load_config()
    gpu = _gpu_info()
    du = shutil.disk_usage("/workspace" if pathlib.Path("/workspace").exists() else ".")
    complete, cmsg = model_complete(config["model_dir"])
    return {
        "python": sys.version.split()[0],
        "os": platform.platform(),
        "cpu": platform.processor() or platform.machine(),
        "cpu_count": os.cpu_count(),
        "ram_gb": round(_ram_gb(), 1),
        "gpu": gpu,
        "versions": _versions(),
        "disk_free_gb": round(du.free / (1024 ** 3), 1),
        "model_dir": config["model_dir"],
        "model_complete": complete, "model_status": cmsg,
        "git": RC.git_state(),
        "benchmark_imports": _benchmark_imports(),
        "frozen": RC.frozen_fingerprint(),
        "config": {k: config[k] for k in ("model_id", "run_kind", "budgets", "methods",
                                          "dtype", "device", "min_vram_gb")},
    }


def _ram_gb():
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / (1024 ** 3)
    except Exception:
        return 0.0


def check(config=None, *, require_gpu=True, require_model=True) -> list:
    """Return list of fatal problems (empty == ok). require_gpu/require_model let the
    smoke/primary scripts enforce a real run; local tests can relax them."""
    config = config or RC.load_config()
    p = probe(config)
    fatal = []
    if not p["benchmark_imports"]["ok"]:
        fatal.append("benchmark cannot import: " + p["benchmark_imports"].get("error", ""))
    if p["git"]["dirty"] and not config["allow_dirty"]:
        fatal.append("repository tree is dirty (set ALLOW_DIRTY=1 to override)")
    if require_gpu:
        if not p["gpu"].get("cuda_available"):
            fatal.append("CUDA unavailable — refusing CPU fallback for a real run")
        elif p["gpu"].get("vram_gb", 0) < config["min_vram_gb"]:
            fatal.append(f"VRAM {p['gpu'].get('vram_gb')}GB < required {config['min_vram_gb']}GB")
    if require_model and not p["model_complete"]:
        fatal.append(f"model incomplete at {config['model_dir']}: {p['model_status']}")
    return fatal


def main():
    config = RC.load_config()
    p = probe(config)
    print("=== RunPod environment probe ===")
    print(f"python={p['python']} os={p['os']}")
    print(f"cpu={p['cpu']} cores={p['cpu_count']} ram={p['ram_gb']}GB disk_free={p['disk_free_gb']}GB")
    g = p["gpu"]
    if g.get("cuda_available"):
        print(f"GPU: {g['gpu_name']} x{g['gpu_count']} vram={g['vram_gb']}GB "
              f"bf16={g['bf16_supported']} cuda={g['cuda_version']} torch={g['torch_version']}")
    else:
        print("GPU: NONE / CUDA unavailable")
    print("versions:", {k: v for k, v in p["versions"].items()})
    print(f"model: {p['model_dir']} complete={p['model_complete']} ({p['model_status']})")
    print(f"git: {p['git']['branch']} @ {p['git']['commit'][:12]} dirty={p['git']['dirty']}")
    print(f"benchmark_imports_ok={p['benchmark_imports']['ok']}")
    print(f"frozen_fingerprint={p['frozen']['fingerprint']}")
    print(f"actiongate_policy={p['frozen']['policy']}")
    require_gpu = os.environ.get("PROBE_REQUIRE_GPU", "1") == "1"
    fatal = check(config, require_gpu=require_gpu,
                  require_model=os.environ.get("PROBE_REQUIRE_MODEL", "0") == "1")
    outp = RC.run_dir(config) / "environment_probe.json"
    RC.write_json_atomic(outp, p)
    print(f"wrote {outp}")
    if fatal:
        print("FATAL:")
        for f in fatal:
            print("  -", f)
        sys.exit(2)
    print("probe OK")


if __name__ == "__main__":
    main()
