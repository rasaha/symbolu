"""Quad Generative Regularization — CPU-only falsification study package."""
from .quad_model import (
    QuadConfig, QuadTransformer, QuadAttention, GenericRelationHead, build_model,
)
from .mqar import MQARConfig, MQARBatch, generate_batch, iter_batches, split_seed, IGNORE_INDEX
from .losses import (
    task_loss, quad_aux_loss, generic_relational_loss, quad_margin_loss,
    mechanism_diagnostics,
)
from .metrics import evaluate, quad_mechanism
from .train import TrainConfig, train_arm

__all__ = [
    "QuadConfig", "QuadTransformer", "QuadAttention", "GenericRelationHead", "build_model",
    "MQARConfig", "MQARBatch", "generate_batch", "iter_batches", "split_seed", "IGNORE_INDEX",
    "task_loss", "quad_aux_loss", "generic_relational_loss", "quad_margin_loss",
    "mechanism_diagnostics", "evaluate", "quad_mechanism",
    "TrainConfig", "train_arm",
]
