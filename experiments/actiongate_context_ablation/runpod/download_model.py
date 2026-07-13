"""Download a Qwen model snapshot to /workspace/models, once, and record its revision.

Authentication is read ONLY from HF_TOKEN and is never printed or persisted. Skips
downloading when a complete, verified local snapshot already exists.
"""

from __future__ import annotations

import os
import pathlib
import sys

import runpod_common as RC
from probe_environment import model_complete


def _ensure_hf_transfer_ok():
    """Some RunPod images set HF_HUB_ENABLE_HF_TRANSFER=1 without installing the
    'hf_transfer' package, which makes every download fail. If the accelerator is
    enabled but not importable, disable it so downloads still work (a bit slower)."""
    if os.environ.get("HF_HUB_ENABLE_HF_TRANSFER") == "1":
        try:
            import hf_transfer  # noqa: F401
        except Exception:
            os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"
            print("[download] hf_transfer not installed; disabling fast-transfer "
                  "(pip install hf_transfer to re-enable)")


def download(model_id: str, model_dir: str, *, force: bool = False) -> dict:
    _ensure_hf_transfer_ok()
    d = pathlib.Path(model_dir)
    complete, msg = model_complete(model_dir)
    if complete and not force:
        rev = (d / "revision.txt").read_text().strip() if (d / "revision.txt").exists() else "local"
        return {"model_id": model_id, "model_dir": model_dir, "skipped": True,
                "revision": rev, "status": "already complete"}
    try:
        from huggingface_hub import snapshot_download
    except Exception as e:   # pragma: no cover - env dependent
        raise RuntimeError(f"huggingface_hub not installed: {e.__class__.__name__}")

    token = os.environ.get("HF_TOKEN") or None    # read ONLY from HF_TOKEN
    d.mkdir(parents=True, exist_ok=True)
    local = snapshot_download(
        repo_id=model_id, local_dir=model_dir, token=token,
        allow_patterns=["*.json", "*.safetensors", "*.model", "*.txt", "tokenizer*",
                        "*.index.json", "merges.txt", "vocab.json"])
    # resolve the exact commit revision (never contains the token)
    revision = _resolve_revision(model_id, token)
    (d / "revision.txt").write_text(revision + "\n")
    complete, msg = model_complete(model_dir)
    if not complete:
        raise RuntimeError(f"download finished but snapshot incomplete: {msg}")
    return {"model_id": model_id, "model_dir": local, "skipped": False,
            "revision": revision, "status": "downloaded"}


def _resolve_revision(model_id, token) -> str:
    try:
        from huggingface_hub import HfApi
        info = HfApi().model_info(model_id, token=token)
        return getattr(info, "sha", None) or "unknown"
    except Exception:
        return "unknown"


def main():
    config = RC.load_config()
    model_id = os.environ.get("MODEL_ID", config["model_id"])
    model_dir = os.environ.get("MODEL_DIR", config["model_dir"])
    force = os.environ.get("FORCE_DOWNLOAD", "0") == "1"
    print(f"downloading {model_id} -> {model_dir} (hf_token={'set' if RC.has_hf_token() else 'unset'})")
    try:
        res = download(model_id, model_dir, force=force)
    except Exception as e:
        print("DOWNLOAD FAILED:", RC.redact(str(e)))
        sys.exit(2)
    print(f"status={res['status']} revision={res['revision']} dir={res['model_dir']}")


if __name__ == "__main__":
    main()
