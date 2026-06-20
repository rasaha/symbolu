"""Runtime helpers for the GPU ablation run: env config, model build, arm-aware generation.

Torch + a real checkpoint are required here — this module is exercised on RunPod, not in the
CPU tests. It builds the wrapper through ``experiments.signal_gov.cg_checkpoint`` so the
fail-closed untrained-head guard applies.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .arms import Arm, run_arm_logits


@dataclass
class RunConfig:
    model_id: str = "mistralai/Mistral-7B-v0.3"
    checkpoint: Optional[str] = None          # trained CG head state-dict
    device: str = "auto"                      # device_map
    dtype: str = "bf16"                       # bf16 | 4bit | 8bit
    seeds: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])
    n_samples: Optional[int] = None           # cap examples per set (None = all)
    max_new_tokens: int = 256
    allow_untrained: bool = False             # plumbing-only override

    @property
    def quantize(self) -> Optional[str]:
        return self.dtype if self.dtype in ("4bit", "8bit") else None


def parse_env() -> RunConfig:
    """Build a RunConfig from the pre-registered env vars (see README.md)."""
    seeds_raw = os.environ.get("SEEDS", "0,1,2,3,4")
    seeds = [int(x) for x in seeds_raw.replace(" ", "").split(",") if x != ""]
    n = os.environ.get("N_SAMPLES")
    return RunConfig(
        model_id=os.environ.get("MODEL_ID", "mistralai/Mistral-7B-v0.3"),
        checkpoint=os.environ.get("CG_CHECKPOINT"),
        device=os.environ.get("DEVICE", "auto"),
        dtype=os.environ.get("DTYPE", "bf16"),
        seeds=seeds,
        n_samples=int(n) if n else None,
        max_new_tokens=int(os.environ.get("MAX_NEW_TOKENS", "256")),
        allow_untrained=os.environ.get("ALLOW_UNTRAINED_CG_HEAD", "0") == "1",
    )


def build_wrapper(cfg: RunConfig):
    """Load the base backbone + trained CG head and return (wrapper, tokenizer).

    Uses cg_checkpoint.load_cg_adapter (fail-closed on untrained heads) when a checkpoint is
    given; otherwise constructs a fresh wrapper on the base model (head zero-init → effectively
    base-only, which is fine for a plumbing smoke but will be INERT by construction).
    """
    if cfg.checkpoint:
        from experiments.signal_gov.cg_checkpoint import load_cg_adapter

        adapter = load_cg_adapter(
            base_model=cfg.model_id,
            state_dict_path=cfg.checkpoint,
            quantize=cfg.quantize,
            device_map=cfg.device,
            allow_untrained=cfg.allow_untrained,
        )
        wrapper = adapter.model
    else:
        from symbolu_training.training.unified.mistral_wrapper import MistralCGWrapper

        wrapper = MistralCGWrapper(
            model_name=cfg.model_id,
            quantize=cfg.quantize,
            device_map=cfg.device,
        )
    wrapper.eval()
    return wrapper, wrapper.tokenizer


def detect_csr_present(wrapper: Any) -> bool:
    """True iff a CSR/Varna stage is actually wired into the wrapper's forward (controls arm E).

    The audit found none; this re-checks at runtime so arm E auto-activates if that ever changes.
    """
    for attr in ("_csr", "csr", "varna", "_varna_path", "csr_path"):
        if getattr(wrapper, attr, None) is not None:
            return True
    return False


def _greedy_step_logits(wrapper, arm: Arm, input_ids, attention_mask):
    """Return next-token logits [B, V] for one decoding step under ``arm``."""
    out = run_arm_logits(wrapper, arm, input_ids, attention_mask)
    return out["logits"][:, -1, :], out


def generate(
    wrapper,
    tokenizer,
    prompt: str,
    arm: Arm,
    *,
    max_new_tokens: int = 256,
    temperature: float = 0.0,
    top_p: float = 0.9,
    top_k: int = 50,
    seed: int = 0,
) -> Dict[str, Any]:
    """Arm-aware autoregressive generation. temperature=0 → greedy (deterministic).

    Returns {text, n_new_tokens, last_diag} where last_diag holds CG diagnostics from the final
    step (adapter_gate, adapter_output_norm, delta_bhava_norm).
    """
    import torch

    torch.manual_seed(seed)
    device = next(wrapper.parameters()).device
    enc = tokenizer(prompt, return_tensors="pt")
    input_ids = enc["input_ids"].to(device)
    attn = enc.get("attention_mask")
    attn = attn.to(device) if attn is not None else None

    start_len = input_ids.shape[1]
    eos = tokenizer.eos_token_id
    last_out: Dict[str, Any] = {}

    for _ in range(max_new_tokens):
        next_logits, last_out = _greedy_step_logits(wrapper, arm, input_ids, attn)
        if temperature and temperature > 0:
            logits = next_logits / temperature
            if top_k > 0:
                kth = torch.topk(logits, top_k).values[:, -1, None]
                logits = torch.where(logits < kth, torch.full_like(logits, float("-inf")), logits)
            probs = torch.softmax(logits, dim=-1)
            nxt = torch.multinomial(probs, num_samples=1)
        else:
            nxt = next_logits.argmax(dim=-1, keepdim=True)
        if eos is not None and nxt.item() == eos:
            break
        input_ids = torch.cat([input_ids, nxt], dim=-1)
        if attn is not None:
            attn = torch.cat([attn, torch.ones(1, 1, device=device, dtype=attn.dtype)], dim=-1)

    text = tokenizer.decode(input_ids[0, start_len:], skip_special_tokens=True).strip()
    diag = {
        "adapter_gate": float(last_out.get("adapter_gate", 0.0) or 0.0),
        "adapter_output_norm": float(last_out.get("adapter_output_norm", 0.0) or 0.0),
    }
    db = last_out.get("delta_bhava")
    if db is not None:
        try:
            diag["delta_bhava_norm"] = float(db.float().norm(dim=-1).mean().item())
        except Exception:
            diag["delta_bhava_norm"] = 0.0
    return {"text": text, "n_new_tokens": input_ids.shape[1] - start_len, "diag": diag}


def prompt_logit_diag(wrapper, tokenizer, prompt: str, base_arm: Arm, wrapper_arm: Arm) -> Dict[str, float]:
    """Teacher-forced base-vs-wrapper logit KL + top-1 flip on the SAME prompt tokens.

    Compares full [T, V] logit tensors so the comparison is well-defined (both arms see identical
    inputs). This is the inert/effect discriminator (K1).
    """
    import torch

    from .diagnostics import tensor_logit_kl, tensor_top1_flip, correction_diagnostics

    device = next(wrapper.parameters()).device
    enc = tokenizer(prompt, return_tensors="pt")
    ids = enc["input_ids"].to(device)
    attn = enc.get("attention_mask")
    attn = attn.to(device) if attn is not None else None

    base_out = run_arm_logits(wrapper, base_arm, ids, attn)
    wrap_out = run_arm_logits(wrapper, wrapper_arm, ids, attn)
    diag = correction_diagnostics(wrapper, wrap_out)
    diag["logit_kl_vs_base"] = tensor_logit_kl(base_out["logits"], wrap_out["logits"])
    diag["top1_flip_rate_vs_base"] = tensor_top1_flip(base_out["logits"], wrap_out["logits"])
    # K0 sanity: max abs logit diff between gate0/base handled by caller for arm D.
    diag["max_abs_logit_diff_vs_base"] = float(
        (base_out["logits"].float() - wrap_out["logits"].float()).abs().max().item()
    )
    return diag
