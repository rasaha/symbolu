"""Shared runtime for the RunPod Qwen execution package.

Deployment/execution machinery ONLY. It reuses the frozen benchmark leaf functions
(real_llm_bench._surviving/_prompt/_SYSTEM, llm_tasks.build_tasks, the task scorers)
and never modifies ActionGate, the compressor, extractor, detector, corpus, prompts,
budgets, or scoring. It adds: config-from-env, frozen-artifact fingerprinting,
atomic durable JSONL persistence, resume/guard logic, and secret redaction.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess
import sys

# --- locate the experiment package and put it on sys.path -------------------
_RUNPOD_DIR = pathlib.Path(__file__).resolve().parent
EXPERIMENT_DIR = _RUNPOD_DIR.parent                    # experiments/actiongate_context_ablation
PKG_DIR = EXPERIMENT_DIR / "actiongate_context_ablation"
if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

SMOKE_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
PRIMARY_MODEL = "Qwen/Qwen2.5-7B-Instruct"
RUN_KIND_SMOKE = "SMOKE_ONLY"
RUN_KIND_PRIMARY = "PRIMARY"

# frozen source files whose change must invalidate a resume
_FROZEN_FILES = [
    "adapter.py", "ablation.py", "effects.py", "units.py", "concepts.py", "textnorm.py",
    "compressor.py", "extractor.py", "extractor_v2.py", "structured_extractor.py",
    "semantic_extractor.py", "validator_extractor.py", "detector.py",
    "protected_detector.py", "metrics.py", "annotation.py", "milestone_bench.py",
    "real_llm_bench.py", "llm_tasks.py", "llm_client.py", "task_benchmark.py",
]


def _sha256_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def frozen_fingerprint() -> dict:
    """Hash of every frozen source file + corpus + ActionGate policy id. Any change
    to the frozen benchmark surface changes this fingerprint."""
    parts = {}
    for rel in _FROZEN_FILES:
        p = PKG_DIR / rel
        parts[rel] = _sha256_file(p) if p.exists() else "MISSING"
    corpus_dir = PKG_DIR / "corpus"
    if corpus_dir.exists():
        for p in sorted(corpus_dir.rglob("*.py")):
            parts[str(p.relative_to(PKG_DIR))] = _sha256_file(p)
    # ActionGate policy identity (best effort, no import failure propagation)
    policy_id = "unknown"
    try:
        from actiongate_context_ablation import adapter  # noqa: E402
        sp = adapter.default_signed_policy()
        policy_id = f"{adapter.REF_VERSION}:{sp.get('policy_hash','')[:16]}"
    except Exception as exc:  # pragma: no cover - env dependent
        policy_id = f"ERR:{exc.__class__.__name__}"
    parts["_actiongate_policy"] = policy_id
    digest = hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()
    return {"fingerprint": "sha256:" + digest, "policy": policy_id, "files": parts}


def git_state() -> dict:
    def _git(*args):
        try:
            return subprocess.check_output(["git", *args], cwd=str(EXPERIMENT_DIR),
                                           stderr=subprocess.DEVNULL).decode().strip()
        except Exception:
            return ""
    dirty = bool(_git("status", "--porcelain"))
    return {"branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "commit": _git("rev-parse", "HEAD"), "dirty": dirty}


def _env(name, default=None):
    v = os.environ.get(name)
    return v if v not in (None, "") else default


def load_config() -> dict:
    """Runner config from environment. Defaults reproduce the preregistered PRIMARY run."""
    budgets = [float(x) for x in _env("BUDGETS", "0.2,0.3,0.4").split(",") if x.strip()]
    methods = [m.strip() for m in _env(
        "METHODS", "original,structural_only,protected,protection_unaware").split(",") if m.strip()]
    run_kind = _env("RUN_KIND", RUN_KIND_PRIMARY)
    model_id = _env("MODEL_ID", PRIMARY_MODEL)
    results_root = _env("RESULTS_ROOT", "/workspace/results/actiongate-context-qwen")
    run_id = _env("RUN_ID", f"{run_kind.lower()}_{model_id.split('/')[-1]}")
    return {
        "model_id": model_id,
        "model_dir": _env("MODEL_DIR", f"/workspace/models/{model_id.split('/')[-1]}"),
        "budgets": budgets,
        "methods": methods,
        "run_id": run_id,
        "run_kind": run_kind,
        "max_new_tokens": int(_env("MAX_NEW_TOKENS", "64")),
        "batch_size": int(_env("BATCH_SIZE", "1")),
        "dtype": _env("DTYPE", "auto"),
        "device": _env("DEVICE", "cuda"),
        "results_root": results_root,
        "contexts_limit": (int(_env("CONTEXTS_LIMIT")) if _env("CONTEXTS_LIMIT") else None),
        "allow_mock": _env("ALLOW_MOCK", "0") == "1",
        "allow_dirty": _env("ALLOW_DIRTY", "0") == "1",
        "min_vram_gb": float(_env("MIN_VRAM_GB", "24")),
    }


def run_dir(config) -> pathlib.Path:
    return pathlib.Path(config["results_root"]) / config["run_id"]


def records_path(config) -> pathlib.Path:
    return run_dir(config) / "records.jsonl"


def config_path(config) -> pathlib.Path:
    return run_dir(config) / "run_config.json"


def example_key(run_id, revision, method, budget, example_id, task_type) -> str:
    return f"{run_id}|{revision}|{method}|{budget:.4f}|{example_id}|{task_type}"


# --- atomic durable JSONL store --------------------------------------------
def atomic_append_jsonl(path: pathlib.Path, record: dict) -> None:
    """Append one JSON record durably: write+fsync a single line, fsync the dir.
    A crash mid-write leaves either nothing or a complete line (verify drops partials)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True) + "\n"
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


def read_records(path: pathlib.Path) -> list:
    if not path.exists():
        return []
    out = []
    with open(path, "r") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                continue  # drop a torn trailing line from a crash
    return out


def write_json_atomic(path: pathlib.Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
    os.replace(str(tmp), str(path))


# --- secret redaction -------------------------------------------------------
_SECRET_KEYS = ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")


def redact(text: str) -> str:
    out = str(text)
    for k in _SECRET_KEYS:
        v = os.environ.get(k)
        if v:
            out = out.replace(v, "***REDACTED***")
    return out


def has_hf_token() -> bool:
    return bool(os.environ.get("HF_TOKEN"))
