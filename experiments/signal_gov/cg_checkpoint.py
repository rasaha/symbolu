"""
cg_checkpoint.py — load + verify a trained CG wrapper state-dict for --mode real_cg.

`--checkpoint` is the BASE backbone (model_name passed to MistralCGWrapper). The trained
CG head (state_projector / intent_projector / phase_adapter) lives in a separately saved
state-dict (e.g. checkpoints_unified/best_model.pt). This module loads that state-dict into
a fresh MistralCGWrapper and wraps it in a MistralCGAdapter(pretrained_model=...).

Fail-closed: if the state-dict has no CG-head keys (vanilla base) or the phase_adapter
output weight is ~0 (untrained, zero-init), we refuse unless allow_untrained=True. This is
what stops the GPU pilot from silently running an untrained head.

The verification core (unwrap/verify/enforce/companion-aux path) is pure and torch-free, so
it is unit-testable with fake dicts. Only the actual wrapper construction needs torch (via
injectable factories that default to the real implementations).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

CG_HEAD_PREFIXES = ("state_projector", "intent_projector", "phase_adapter")
_DEFAULT_EPS = 1e-6


class CGCheckpointError(RuntimeError):
    """Raised when a --cg-state-dict checkpoint is vanilla/untrained (and not allowed)."""


@dataclass(frozen=True)
class CGCheckVerdict:
    has_cg_keys: bool
    n_cg_keys: int
    n_backbone_keys: int
    phase_output_key: Optional[str]
    phase_output_norm: float
    is_trained: bool
    summary: str


# ---------------------------------------------------------------------------
# Pure / torch-free helpers
# ---------------------------------------------------------------------------

def unwrap_state_dict(obj: Any) -> Dict[str, Any]:
    """Unwrap common checkpoint containers into the raw {name: tensor} state-dict."""
    if not isinstance(obj, dict):
        raise CGCheckpointError(
            f"unsupported checkpoint object type: {type(obj).__name__} (expected a dict)")
    for key in ("model_state_dict", "model", "state_dict"):
        inner = obj.get(key)
        if isinstance(inner, dict):
            return inner
    return obj  # assume already a raw state-dict


def _l2_norm(value: Any) -> float:
    """L2 norm of a tensor/array-like, torch-free where possible."""
    try:
        import numpy as np
        return float(np.linalg.norm(np.asarray(value, dtype=float).ravel()))
    except Exception:
        pass
    try:  # torch tensor fallback
        return float(value.detach().float().norm().item())
    except Exception:
        return float("nan")


def verify_cg_state_dict(state_dict: Dict[str, Any], *, eps: float = _DEFAULT_EPS) -> CGCheckVerdict:
    """Inspect a raw state-dict for trained CG-head signatures."""
    keys = list(state_dict.keys())
    cg_keys = [k for k in keys if any(h in k for h in CG_HEAD_PREFIXES)]
    backbone_keys = [k for k in keys if "backbone" in k or k.startswith("model.")]
    # phase_adapter output Linear is the highest-index phase_adapter *.weight
    # (Sequential[Linear, GELU, Linear]); it is zero-initialised when untrained.
    pa_weights = sorted(k for k in keys if "phase_adapter" in k and k.endswith(".weight"))
    out_key = pa_weights[-1] if pa_weights else None
    out_norm = _l2_norm(state_dict[out_key]) if out_key is not None else float("nan")
    has_cg = len(cg_keys) > 0
    is_trained = bool(has_cg and out_key is not None
                      and not math.isnan(out_norm) and out_norm > eps)
    if not has_cg:
        summary = "no CG-head keys found (state_projector/intent_projector/phase_adapter) — vanilla base"
    elif is_trained:
        summary = (f"CG head present ({len(cg_keys)} tensors); "
                   f"phase_adapter output L2={out_norm:.4g} > {eps:g} → TRAINED")
    else:
        summary = (f"CG head present ({len(cg_keys)} tensors) but phase_adapter output "
                   f"L2={out_norm:.4g} ≈ 0 → UNTRAINED (zero-init)")
    return CGCheckVerdict(
        has_cg_keys=has_cg, n_cg_keys=len(cg_keys), n_backbone_keys=len(backbone_keys),
        phase_output_key=out_key, phase_output_norm=out_norm,
        is_trained=is_trained, summary=summary)


def _enforce(verdict: CGCheckVerdict, allow_untrained: bool) -> None:
    if verdict.has_cg_keys and verdict.is_trained:
        logger.info("CG checkpoint check: %s", verdict.summary)
        return
    if allow_untrained:
        logger.warning("CG checkpoint check: %s. Proceeding due to --allow-untrained-cg-head "
                       "(PLUMBING ONLY; not a trained-signal run).", verdict.summary)
        return
    raise CGCheckpointError(
        f"Refusing to run real_cg with this --cg-state-dict: {verdict.summary}. "
        "Verify you passed a trained CG checkpoint (e.g. checkpoints_unified/best_model.pt), "
        "or pass --allow-untrained-cg-head to override (plumbing only).")


def prepare_cg_state_dict(obj: Any, *, allow_untrained: bool = False,
                          eps: float = _DEFAULT_EPS) -> Tuple[Dict[str, Any], CGCheckVerdict]:
    """Unwrap + verify a loaded checkpoint object; fail closed unless allow_untrained.

    Torch-free (operates on an in-memory object). Returns (raw_state_dict, verdict).
    """
    sd = unwrap_state_dict(obj)
    verdict = verify_cg_state_dict(sd, eps=eps)
    _enforce(verdict, allow_untrained)
    return sd, verdict


def companion_aux_path(model_path: str | Path) -> Optional[Path]:
    """Derive the companion '*_aux.pt' for a '*_model.pt' checkpoint, else None."""
    p = Path(model_path)
    if p.name.endswith("_model.pt"):
        return p.with_name(p.name[: -len("_model.pt")] + "_aux.pt")
    return None


# ---------------------------------------------------------------------------
# Default torch-backed factories (overridable for tests)
# ---------------------------------------------------------------------------

def _default_torch_load(path: str | Path) -> Any:
    try:
        import torch
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "real_cg --cg-state-dict requires torch. Use --real-cg-stub for a torch-free run."
        ) from exc
    return torch.load(path, map_location="cpu", weights_only=False)


def _default_wrapper_factory(base_model: str, quantize: Optional[str], device_map: str) -> Any:  # pragma: no cover
    from symbolu_training.training.unified.mistral_wrapper import MistralCGWrapper
    return MistralCGWrapper(model_name=base_model, quantize=quantize, device_map=device_map)


def _default_adapter_factory(wrapper: Any) -> Any:  # pragma: no cover
    from agentic.agentic_framework.llm_adapters import MistralCGAdapter
    # The harness consumes ONLY adapter.last_cg_metadata (the 32-D state captured by
    # the single metadata forward pass, llm_adapters.py:534). The autoregressive
    # generation that follows is discarded — features.py uses a text_confidence
    # PLACEHOLDER, not the generated text. Generating the default 512 tokens per
    # scenario through a no-KV-cache O(n^2) loop costs ~30-50s/scenario of pure
    # waste (hours across a 400-600 benchmark). Cap at 1 token; the metadata (and
    # therefore every signal) is captured before the loop and is unaffected.
    return MistralCGAdapter(pretrained_model=wrapper, max_new_tokens=1)


def _load_into_wrapper(wrapper: Any, sd: Dict[str, Any]) -> None:
    # Load ONLY the trained CG head (non-backbone params). The backbone is loaded fresh
    # from the base model and frozen — bit-identical to what training used — so copying
    # backbone.* weights from the checkpoint is both unnecessary and BROKEN under
    # quantization: a 4-bit/8-bit backbone has bitsandbytes-packed param shapes (e.g.
    # [8388608, 1]) that don't match the checkpoint's full-precision [4096, 4096], which
    # raises a load_state_dict size mismatch. Filtering to the head (state_projector /
    # intent_projector / phase_adapter / adapter_gate / adapter_output_norm) avoids that
    # entirely and works for any quantization setting. The head is never quantized.
    head_sd = {k: v for k, v in sd.items() if not k.startswith("backbone.")}
    try:
        wrapper.load_state_dict(head_sd, strict=False)
    except TypeError:  # wrappers without a strict kwarg
        wrapper.load_state_dict(head_sd)


def load_cg_adapter(*, base_model: str, state_dict_path: str | Path,
                    quantize: Optional[str] = None, device_map: str = "auto",
                    allow_untrained: bool = False, eps: float = _DEFAULT_EPS,
                    state_dict_loader: Optional[Callable[[Any], Any]] = None,
                    wrapper_factory: Optional[Callable[..., Any]] = None,
                    adapter_factory: Optional[Callable[[Any], Any]] = None) -> Any:
    """Load a trained CG state-dict into a MistralCGWrapper -> MistralCGAdapter.

    Verifies the checkpoint (fail-closed unless allow_untrained), constructs the wrapper on
    the base backbone, loads the head (strict=False), best-effort merges a companion
    '*_aux.pt' if present, and returns a MistralCGAdapter(pretrained_model=wrapper).
    The *_loader/*_factory params default to the real torch-backed implementations and are
    overridable for testing.
    """
    state_dict_loader = state_dict_loader or _default_torch_load
    wrapper_factory = wrapper_factory or _default_wrapper_factory
    adapter_factory = adapter_factory or _default_adapter_factory

    sd, verdict = prepare_cg_state_dict(
        state_dict_loader(state_dict_path), allow_untrained=allow_untrained, eps=eps)

    wrapper = wrapper_factory(base_model, quantize, device_map)
    _load_into_wrapper(wrapper, sd)

    aux = companion_aux_path(state_dict_path)
    if aux is not None and Path(aux).exists():
        _load_into_wrapper(wrapper, unwrap_state_dict(state_dict_loader(aux)))
        logger.info("loaded companion aux weights: %s", aux)
    elif aux is not None:
        logger.warning("companion aux not found (%s) — continuing without it "
                       "(not required for the 32-D signal path).", aux)

    if hasattr(wrapper, "eval"):
        wrapper.eval()
    logger.info("CG adapter ready (base=%s, head=%s)", base_model, verdict.summary)
    return adapter_factory(wrapper)
