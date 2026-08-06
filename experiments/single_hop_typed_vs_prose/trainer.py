"""Deterministic in-memory training primitives; no automatic execution or writes."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import random
from typing import Sequence

import torch

from .config import FROZEN_TRAIN_RECIPE, TrainRecipe
from .dataset import EncodedExample, collate_encoded
from .model import StructuredOutputModel


@dataclass(frozen=True)
class TrainResult:
    updates: int
    first_loss: float
    final_loss: float
    batch_order_digest: str
    final_parameter_digest: str


def deterministic_batch_order(size: int, updates: int, batch_size: int, seed: int) -> tuple[int, ...]:
    if size <= 0:
        raise ValueError("training set must be non-empty")
    rng = random.Random(int(seed))
    order: list[int] = []
    pool = list(range(size))
    while len(order) < updates * batch_size:
        rng.shuffle(pool)
        order.extend(pool)
    return tuple(order[: updates * batch_size])


def order_digest(order: Sequence[int]) -> str:
    payload = ",".join(str(index) for index in order).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def train_in_memory(
    model: StructuredOutputModel,
    examples: Sequence[EncodedExample],
    *,
    seed: int,
    recipe: TrainRecipe = FROZEN_TRAIN_RECIPE,
    updates: int | None = None,
    device: torch.device | str = "cpu",
) -> TrainResult:
    """Train one arm with a precomputed deterministic episode-index order.

    Callers must apply the execution seed gate before constructing benchmark data or
    the model. This function intentionally performs no filesystem or network I/O.
    """
    recipe.validate()
    n_updates = recipe.maximum_updates if updates is None else int(updates)
    if n_updates <= 0 or n_updates > recipe.maximum_updates:
        raise ValueError("updates must lie in [1, frozen maximum_updates]")
    order = deterministic_batch_order(len(examples), n_updates, recipe.batch_size, seed)
    model = model.to(device).train()
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=recipe.learning_rate,
        betas=(recipe.beta1, recipe.beta2),
        eps=recipe.epsilon,
        weight_decay=recipe.weight_decay,
    )
    losses: list[float] = []
    for step in range(n_updates):
        start = step * recipe.batch_size
        batch_indices = order[start : start + recipe.batch_size]
        batch = [examples[index] for index in batch_indices]
        input_ids, labels = collate_encoded(batch)
        input_ids = input_ids.to(device)
        labels = labels.to(device)
        optimizer.zero_grad(set_to_none=True)
        loss = model.loss(input_ids, labels)
        if not torch.isfinite(loss):
            raise FloatingPointError(f"non-finite loss at update {step}")
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), recipe.gradient_clip)
        optimizer.step()
        losses.append(float(loss.detach().cpu()))
    return TrainResult(
        updates=n_updates,
        first_loss=losses[0],
        final_loss=losses[-1],
        batch_order_digest=order_digest(order),
        final_parameter_digest=model.parameter_digest(),
    )
