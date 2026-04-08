"""
MistralTeacher — Frozen Mistral backbone for knowledge distillation.

Loads a pretrained Mistral model as a pure teacher for distilling knowledge
into smaller student models (hybrid, ontological_hybrid). No CG modules,
no adapters — just forward pass → logits.

Usage:
    python train_unified_llm.py \
        --model_type ontological_hybrid \
        --distill_from_mistral \
        --mistral_model_name mistralai/Mistral-7B-v0.3 \
        --mistral_quantize 4bit \
        --distill_temperature 2.0 \
        --distill_alpha 0.5
"""

from typing import Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


class MistralTeacher(nn.Module):
    """
    Frozen Mistral model for knowledge distillation.
    No trainable parameters — just produces soft logit targets.
    """

    def __init__(
        self,
        model_name: str = "mistralai/Mistral-7B-v0.3",
        quantize: Optional[str] = None,
        device_map: str = "auto",
        trust_remote_code: bool = False,
    ):
        super().__init__()
        self.backbone, self.tokenizer = self._load_mistral(
            model_name, quantize, device_map, trust_remote_code,
        )

        # Freeze everything
        for param in self.backbone.parameters():
            param.requires_grad = False

        self.vocab_size = self.backbone.config.vocab_size
        self.hidden_dim = self.backbone.config.hidden_size

    def _load_mistral(self, model_name, quantize, device_map, trust_remote_code):
        """Load Mistral with optional quantization."""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError:
            raise ImportError(
                "transformers package required for distillation. "
                "Install with: pip install transformers"
            )

        load_kwargs = {
            "device_map": device_map,
            "trust_remote_code": trust_remote_code,
            "torch_dtype": torch.bfloat16,
        }

        if quantize in ("4bit", "8bit"):
            try:
                from transformers import BitsAndBytesConfig
                import bitsandbytes as _bnb  # noqa: F401
            except ImportError:
                raise ImportError(
                    "bitsandbytes required for quantization. "
                    "Install with: pip install -U bitsandbytes>=0.46.1"
                )
            if quantize == "4bit":
                load_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.bfloat16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4",
                )
            else:
                load_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_8bit=True,
                )

        # PyTorch < 2.1 lacks set_submodule, required by transformers' bnb integration
        if not hasattr(torch.nn.Module, "set_submodule"):
            def _set_submodule(self_mod, target, module):
                atoms = target.split(".")
                mod = self_mod
                for item in atoms[:-1]:
                    mod = getattr(mod, item)
                setattr(mod, atoms[-1], module)
            torch.nn.Module.set_submodule = _set_submodule

        print(f"  Loading Mistral teacher: {model_name}")
        print(f"  Quantization: {quantize or 'none (bf16)'}")
        print(f"  Device map: {device_map}")

        backbone = AutoModelForCausalLM.from_pretrained(model_name, **load_kwargs)
        tokenizer = AutoTokenizer.from_pretrained(
            model_name, trust_remote_code=trust_remote_code,
        )
        return backbone, tokenizer

    @torch.no_grad()
    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Forward pass through frozen Mistral.

        Args:
            input_ids: [B, T] token IDs (must use Mistral's tokenizer)
            attention_mask: [B, T] optional

        Returns:
            logits: [B, T, V_mistral] raw logits
        """
        out = self.backbone(
            input_ids=input_ids,
            attention_mask=attention_mask,
        )
        return out.logits

    def print_summary(self):
        total = sum(p.numel() for p in self.parameters())
        print(f"  [Mistral Teacher] {total / 1e6:.0f}M params (all frozen)")
        print(f"    Vocab: {self.vocab_size}, Hidden: {self.hidden_dim}")


def compute_distillation_loss(
    student_logits: torch.Tensor,
    teacher_logits: torch.Tensor,
    labels: torch.Tensor,
    temperature: float = 2.0,
    alpha: float = 0.5,
    vocab_map: Optional[torch.Tensor] = None,
) -> Tuple[torch.Tensor, dict]:
    """
    Compute knowledge distillation loss.

    L = α * KL(softmax(s/T), softmax(t/T)) * T² + (1-α) * CE(s, y)

    Args:
        student_logits: [B, T, V_student] student model logits
        teacher_logits: [B, T, V_teacher] teacher model logits
        labels: [B, T] ground truth token IDs
        temperature: Softmax temperature for soft targets (higher = softer)
        alpha: Weight for distillation loss (1.0 = pure distillation)
        vocab_map: [V_student] optional mapping from student vocab → teacher vocab
                   For aligning different tokenizers. If None, assumes shared vocab
                   and truncates/pads to min(V_student, V_teacher).

    Returns:
        (loss, metrics_dict)
    """
    B, T, V_s = student_logits.shape
    V_t = teacher_logits.shape[-1]

    # Align vocabularies if sizes differ
    if V_s != V_t:
        if vocab_map is not None:
            # Gather teacher logits at student vocab positions
            # vocab_map[i] = teacher token ID corresponding to student token i
            # Shape: [V_student] → index into teacher's V_teacher dimension
            teacher_logits = teacher_logits.gather(
                -1, vocab_map.unsqueeze(0).unsqueeze(0).expand(B, T, -1)
            )
        else:
            # Simple truncation to shared prefix (works when tokenizers overlap)
            V_min = min(V_s, V_t)
            student_logits_kd = student_logits[..., :V_min]
            teacher_logits = teacher_logits[..., :V_min]
    else:
        student_logits_kd = student_logits

    # Soft targets from teacher
    teacher_probs = F.log_softmax(teacher_logits / temperature, dim=-1)
    student_log_probs = F.log_softmax(student_logits_kd / temperature, dim=-1)

    # KL divergence: KL(teacher || student)
    # Using log-space inputs for numerical stability
    kd_loss = F.kl_div(
        student_log_probs,
        teacher_probs,
        log_target=True,
        reduction="batchmean",
    ) * (temperature ** 2)

    # Hard target CE loss (on full student vocab)
    ce_loss = F.cross_entropy(
        student_logits.view(-1, V_s),
        labels.view(-1),
        ignore_index=-100,
    )

    # Combined loss
    loss = alpha * kd_loss + (1 - alpha) * ce_loss

    metrics = {
        "distill_kd_loss": kd_loss.item(),
        "distill_ce_loss": ce_loss.item(),
        "distill_total_loss": loss.item(),
        "distill_temperature": temperature,
        "distill_alpha": alpha,
    }

    return loss, metrics
