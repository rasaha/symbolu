"""Controlled single-hop typed-vs-prose implementation package.

Importing this package performs no generation, model initialization, training,
filesystem write, network call, or benchmark execution.
"""
from .config import FROZEN_MODEL_RECIPE, FROZEN_TRAIN_RECIPE
from .dataset import PairedEpisode, SyntheticEpisodeGenerator, encode_pair_arm, make_pair
from .execution import ExecutionNotAuthorized, guard_seed
from .model import StructuredOutputModel, build_model
from .schema import CanonicalEpisode, StructuredOutput
from .serializers import serialize_b0, serialize_b1
from .tokenizer import LexicalTokenizer

__all__ = [
    "CanonicalEpisode",
    "ExecutionNotAuthorized",
    "FROZEN_MODEL_RECIPE",
    "FROZEN_TRAIN_RECIPE",
    "LexicalTokenizer",
    "PairedEpisode",
    "StructuredOutput",
    "StructuredOutputModel",
    "SyntheticEpisodeGenerator",
    "build_model",
    "encode_pair_arm",
    "guard_seed",
    "make_pair",
    "serialize_b0",
    "serialize_b1",
]
