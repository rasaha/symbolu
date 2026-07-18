"""Shared builders for Stage-1 scripts: backbone/tokenizer/model + meta detection."""
from __future__ import annotations

import json
import os
from typing import List, Optional, Tuple

import torch

from .data import CharTokenizer, HFTokenizer
from .featurizer import ToyFeatureBackbone, HFEncodeAdapter
from .model_stage1 import Stage1GroundingModel


def build_backbone_and_tokenizer(spec: str, d_model: int, seed: int = 0):
    """spec = 'dummy' (toy char featurizer) or 'hf:<model-name>'.

    Returns (backbone, tokenizer, d_model_effective).
    """
    if spec == "dummy":
        bb = ToyFeatureBackbone(d_model=d_model, seed=seed)
        return bb, CharTokenizer(), d_model
    if spec.startswith("hf:"):
        name = spec[3:]
        bb = HFEncodeAdapter(name)
        return bb, HFTokenizer(name), bb.d_model
    raise ValueError(f"unknown backbone spec '{spec}' (use 'dummy' or 'hf:<name>')")


def build_model(spec: str, d_model: int, heads: List[str], seed: int = 0
                ) -> Tuple[Stage1GroundingModel, object, int]:
    bb, tok, d_eff = build_backbone_and_tokenizer(spec, d_model, seed)
    model = Stage1GroundingModel(bb, d_eff, heads)
    model.assert_backbone_frozen()
    return model, tok, d_eff


def detect_meta(data_path: str) -> Optional[dict]:
    meta_path = os.path.join(os.path.dirname(os.path.abspath(data_path)), "meta.json")
    if os.path.exists(meta_path):
        with open(meta_path, encoding="utf-8") as f:
            return json.load(f)
    return None


def synthetic_banner(meta: Optional[dict]) -> str:
    if meta and meta.get("synthetic"):
        return ("\n" + "!" * 72 +
                "\n!! SYNTHETIC TOY DATA — a PASS validates the harness + a learnable\n"
                "!! surface signal, NOT the real Vritti grounding hypothesis.\n"
                "!! Real validation requires a pretrained LM + human-labeled data.\n"
                + "!" * 72 + "\n")
    return ""
