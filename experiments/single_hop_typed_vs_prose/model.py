"""Shared non-memory model and output-only objective."""
from __future__ import annotations

import hashlib
from typing import Iterable

import torch
import torch.nn as nn
import torch.nn.functional as F

from symbolu_neural.clean_softmax.backbone import BackboneConfig, SoftmaxTransformerLM

from .config import EOS_ID, FROZEN_MODEL_RECIPE, ModelRecipe
from .tokenizer import LexicalTokenizer


class StructuredOutputModel(nn.Module):
    """One plain causal Transformer used identically for B0 and B1."""

    def __init__(self, recipe: ModelRecipe = FROZEN_MODEL_RECIPE):
        super().__init__()
        recipe.validate()
        self.recipe = recipe
        self.lm = SoftmaxTransformerLM(
            BackboneConfig(
                vocab_size=recipe.vocab_size,
                d_model=recipe.d_model,
                n_layers=recipe.n_layers,
                n_heads=recipe.n_heads,
                d_ff=recipe.d_ff,
                max_seq=recipe.max_seq,
                dropout=recipe.dropout,
            )
        )

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        if input_ids.ndim != 2:
            raise ValueError("input_ids must have shape [batch, sequence]")
        if input_ids.shape[1] > self.recipe.max_seq:
            raise ValueError("input sequence exceeds frozen model context")
        return self.lm(input_ids)

    def loss(self, input_ids: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
        if input_ids.shape != labels.shape:
            raise ValueError("input_ids and labels must have the same shape")
        logits = self(input_ids)
        # Standard causal next-token alignment: logits[i] predicts input_ids[i+1] == labels[i+1].
        shift_logits = logits[:, :-1, :].reshape(-1, logits.shape[-1])
        shift_labels = labels[:, 1:].reshape(-1)
        return F.cross_entropy(shift_logits, shift_labels, ignore_index=-100)

    def parameter_count(self) -> int:
        return sum(parameter.numel() for parameter in self.parameters())

    def parameter_digest(self) -> str:
        digest = hashlib.sha256()
        for name, parameter in sorted(self.state_dict().items()):
            digest.update(name.encode("utf-8"))
            digest.update(str(parameter.dtype).encode("ascii"))
            digest.update(str(tuple(parameter.shape)).encode("ascii"))
            # Numpy-free raw-byte extraction (torch-only environments): reinterpreting a
            # contiguous CPU tensor as uint8 yields the exact same little-endian bytes as
            # numpy().tobytes(), so recorded digest values are unchanged.
            raw = parameter.detach().cpu().contiguous().flatten().view(torch.uint8)
            digest.update(bytes(raw.tolist()))
        return digest.hexdigest()


def build_model(
    initialization_seed: int, recipe: ModelRecipe = FROZEN_MODEL_RECIPE
) -> StructuredOutputModel:
    """Build without mutating the caller's global PyTorch RNG state."""
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(int(initialization_seed))
        model = StructuredOutputModel(recipe)
    return model


@torch.no_grad()
def greedy_generate(
    model: StructuredOutputModel,
    prompt_ids: Iterable[int],
    *,
    tokenizer: LexicalTokenizer | None = None,
    max_output_tokens: int | None = None,
    device: torch.device | str = "cpu",
) -> str:
    from .config import FROZEN_TRAIN_RECIPE
    tokenizer = tokenizer or LexicalTokenizer()
    model = model.to(device).eval()
    ids = list(int(token) for token in prompt_ids)
    limit = int(max_output_tokens) if max_output_tokens is not None else FROZEN_TRAIN_RECIPE.output_token_limit
    if len(ids) >= model.recipe.max_seq:
        raise ValueError("prompt exceeds model context")
    generated: list[int] = []
    for _ in range(limit):
        tensor = torch.tensor([ids], dtype=torch.long, device=device)
        next_id = int(model(tensor)[0, -1].argmax().item())
        if next_id == EOS_ID:
            break
        generated.append(next_id)
        ids.append(next_id)
        if len(ids) >= model.recipe.max_seq:
            break
    return tokenizer.decode(generated)
