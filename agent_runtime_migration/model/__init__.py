"""Model integration for the Agent Runtime.

A model may PROPOSE decomposition, plan steps, tool selection, arguments, uncertainty
evidence, and reflection text. A model may NOT produce authoritative authorization,
operational-safety decisions, execution references, or tool risk-tier classification.
All model output is parsed into typed runtime contracts and fails closed on malformed
or incomplete output.

No live/local model runs in this environment (no API credentials, no torch/transformers/
ollama). This package therefore drives the runtime with a deterministic recorded-model
replay adapter and a realistic model-shaped mock — never fabricated live-model evidence.
"""
from .interface import LanguageModel
from .replay import ReplayModel
from .mock import RealisticPlannerModel
from .parsing import parse_plan_payload, ModelParseError
from .live import LiveHTTPModel, LiveModelConfig, build_live_model_from_env
from .capture import CaptureRecorder, replay_from_capture


__all__ = ["LanguageModel", "ReplayModel", "RealisticPlannerModel",
           "parse_plan_payload", "ModelParseError",
           "LiveHTTPModel", "LiveModelConfig", "build_live_model_from_env",
           "CaptureRecorder", "replay_from_capture"]
