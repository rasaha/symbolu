"""Logging + run-manifest utilities for the §6 benchmark + §4 scripts.

Captures everything needed to reconstruct a failing run on a remote
GPU (RunPod, etc.) without re-executing: environment versions, CLI
args, model configuration, git state, per-step timings, exceptions.

Public API:

    configure_logging(log_path, verbose=False) -> logging.Logger
        Dual-handler logger: console (INFO by default, DEBUG if verbose)
        + file (always DEBUG, structured format).

    capture_environment() -> dict
        Python / OS / torch / transformers / datasets / numpy / CUDA
        device info. Optional imports fail gracefully.

    capture_git_state(repo_root) -> dict
        Branch / commit SHA / dirty flag via `git` CLI. If git isn't
        available, returns {"available": False}.

    write_manifest(path, manifest) -> None
        Pretty-printed JSON dump with a stable schema.

    format_exception(exc) -> dict
        Structured exception capture (type, message, traceback).

All functions are safe to call when torch / transformers / datasets
are missing — they just record the absence in the manifest.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import os
import platform
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, Optional


LOGGER_NAME = "symbolu_bcvf_llm"
_FILE_FORMAT = (
    "%(asctime)s.%(msecs)03d %(levelname)-7s %(name)s "
    "[%(filename)s:%(lineno)d] %(message)s"
)
_CONSOLE_FORMAT = "%(asctime)s %(levelname)-7s %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(
    log_path: Optional[Path] = None,
    verbose: bool = False,
) -> logging.Logger:
    """Configure a dual-handler logger returning the ``symbolu_bcvf_llm``
    named logger.

    Args:
        log_path: Destination for the file handler; parent directory is
            created if missing. If None, only the console handler is
            attached (test-only use).
        verbose: If True, console handler is set to DEBUG instead of
            INFO; the file handler is always DEBUG regardless.

    Idempotent: calling twice replaces the previously-attached handlers
    on this logger (so CLI tools can re-configure without duplicate lines).
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)

    # Remove any existing handlers owned by us.
    for h in list(logger.handlers):
        logger.removeHandler(h)
        try:
            h.close()
        except Exception:  # pragma: no cover
            pass

    console = logging.StreamHandler(stream=sys.stderr)
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(logging.Formatter(_CONSOLE_FORMAT, _DATE_FORMAT))
    logger.addHandler(console)

    if log_path is not None:
        log_path = Path(log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(_FILE_FORMAT, _DATE_FORMAT))
        logger.addHandler(file_handler)

    logger.propagate = False
    return logger


# --------------------------------------------------------------------------- #
# Environment capture
# --------------------------------------------------------------------------- #


def _optional_version(module_name: str) -> Optional[str]:
    try:
        mod = __import__(module_name)
    except Exception:
        return None
    return str(getattr(mod, "__version__", "unknown"))


def capture_environment() -> Dict[str, Any]:
    """Return a dict of runtime environment info.

    Safe when torch / transformers / datasets are not installed.
    """
    env: Dict[str, Any] = {
        "timestamp_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "python_version": sys.version.split()[0],
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "hostname": platform.node(),
        "cpu_count": os.cpu_count(),
    }

    env["numpy_version"] = _optional_version("numpy")
    env["torch_version"] = _optional_version("torch")
    env["transformers_version"] = _optional_version("transformers")
    env["datasets_version"] = _optional_version("datasets")
    env["accelerate_version"] = _optional_version("accelerate")

    # CUDA-specific info, if torch is available.
    env["cuda"] = _capture_cuda_info()
    return env


def _capture_cuda_info() -> Dict[str, Any]:
    out: Dict[str, Any] = {"available": False}
    try:
        import torch
    except ImportError:
        return out
    try:
        out["available"] = bool(torch.cuda.is_available())
        if out["available"]:
            out["device_count"] = int(torch.cuda.device_count())
            out["current_device"] = int(torch.cuda.current_device())
            out["device_name"] = torch.cuda.get_device_name()
            props = torch.cuda.get_device_properties(torch.cuda.current_device())
            out["total_memory_gb"] = round(props.total_memory / (1024 ** 3), 2)
            out["compute_capability"] = (
                f"{props.major}.{props.minor}"
            )
            out["cuda_runtime"] = torch.version.cuda
            out["cudnn_version"] = (
                torch.backends.cudnn.version()
                if torch.backends.cudnn.is_available() else None
            )
    except Exception as exc:  # pragma: no cover
        out["error"] = repr(exc)
    return out


# --------------------------------------------------------------------------- #
# Git capture
# --------------------------------------------------------------------------- #


def capture_git_state(repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """Return branch / commit / dirty-flag via the `git` CLI.

    Returns ``{"available": False}`` if git isn't on PATH or the path
    isn't a git repo.
    """
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[1]
    out: Dict[str, Any] = {"available": False, "repo_root": str(root)}
    try:
        branch = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL, text=True, timeout=5,
        ).strip()
        commit = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL, text=True, timeout=5,
        ).strip()
        status = subprocess.check_output(
            ["git", "-C", str(root), "status", "--porcelain"],
            stderr=subprocess.DEVNULL, text=True, timeout=5,
        )
        out.update(
            available=True,
            branch=branch,
            commit=commit,
            dirty=bool(status.strip()),
            dirty_file_count=len([l for l in status.splitlines() if l]),
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return out


# --------------------------------------------------------------------------- #
# Manifest + exception utilities
# --------------------------------------------------------------------------- #


def write_manifest(path: Path, manifest: Dict[str, Any]) -> None:
    """Atomic-ish pretty-printed JSON dump."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(manifest, indent=2, default=str))
    tmp_path.replace(path)


def format_exception(exc: BaseException) -> Dict[str, Any]:
    """Structured exception capture (type, message, full traceback)."""
    tb = "".join(
        traceback.format_exception(type(exc), exc, exc.__traceback__)
    )
    return {
        "type": type(exc).__name__,
        "module": type(exc).__module__,
        "message": str(exc),
        "traceback": tb,
    }


# --------------------------------------------------------------------------- #
# Human-readable summary for console use
# --------------------------------------------------------------------------- #


def log_environment(logger: logging.Logger) -> Dict[str, Any]:
    """Log a one-screen environment summary at INFO; return the full dict."""
    env = capture_environment()
    git = capture_git_state()
    logger.info("Host: %s  Python: %s  Platform: %s",
                env["hostname"], env["python_version"], env["platform"])
    logger.info("numpy=%s torch=%s transformers=%s datasets=%s",
                env["numpy_version"], env["torch_version"],
                env["transformers_version"], env["datasets_version"])
    cuda = env["cuda"]
    if cuda.get("available"):
        logger.info(
            "CUDA: %s (%s GB, compute %s, runtime %s)",
            cuda.get("device_name"), cuda.get("total_memory_gb"),
            cuda.get("compute_capability"), cuda.get("cuda_runtime"),
        )
    else:
        logger.info("CUDA: unavailable (CPU-only mode)")
    if git.get("available"):
        logger.info(
            "git: branch=%s commit=%s dirty=%s",
            git.get("branch"), (git.get("commit") or "?")[:12], git.get("dirty"),
        )
    else:
        logger.info("git: unavailable")
    return {"environment": env, "git": git}
