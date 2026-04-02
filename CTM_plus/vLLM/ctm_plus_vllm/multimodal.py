"""
Multimodal Token Type Extension for TurboQuant + CTM+ Simulator

Extends the text-only token importance map with multimodal token types
(image patches, video frames, audio onsets) and adds modality-aware
scoring to the eviction policy.

Key insight: Different modalities have very different importance profiles.
- Image CLS tokens anchor visual understanding (high importance)
- Image patches are mostly redundant (low importance, except ROI)
- Video keyframes carry scene changes (high importance)
- Video B-frames are interpolatable (low importance)
- Audio onset tokens mark speech/sound boundaries (medium-high importance)

The math (PolarQuant + QJL) is modality-agnostic — it compresses any
vector. But the eviction policy must be modality-aware to retain the
right tokens when memory pressure hits.
"""

import math
import time
import random
from dataclasses import dataclass, field
from typing import Optional
from collections import deque
from enum import Enum

import numpy as np

from .turboquant import TurboQuantCompressor, TurboQuantConfig, MemoryBudget
from .turboquant_integration import (
    TurboQuantCTMSimulator,
    TurboQuantTokenState,
    IntegratedConfig,
    IntegrationMode,
)
from .kv_cache_simulator import CTMKVConfig, WorkloadGenerator, AttentionPatternGenerator


# ---------------------------------------------------------------------------
# Extended Token Importance Map (text + multimodal)
# ---------------------------------------------------------------------------

MULTIMODAL_TOKEN_IMPORTANCE = {
    # --- Text tokens (unchanged from base) ---
    "bos": 1.0,
    "entity": 0.9,
    "number": 0.85,
    "code": 0.8,
    "instruction": 0.75,
    "eos": 0.5,
    "regular": 0.4,
    "punctuation": 0.2,
    # --- Image tokens ---
    "image_cls": 0.95,      # CLS token anchors the image representation
    "image_patch": 0.35,    # Generic patch — mostly redundant, compresses well
    "image_roi": 0.85,      # Region-of-interest patch (face, object, text in image)
    "image_border": 0.15,   # Border/padding patches — least important
    # --- Video tokens ---
    "video_keyframe": 0.80, # I-frame: scene change, new visual information
    "video_pframe": 0.45,   # P-frame: predicted, partially redundant
    "video_bframe": 0.25,   # B-frame: bidirectional, most redundant
    "video_scene_change": 0.90,  # Scene boundary token
    # --- Audio tokens ---
    "audio_onset": 0.70,    # Speech/sound onset boundary
    "audio_silence": 0.10,  # Silence tokens — safe to evict
    "audio_speech": 0.55,   # Mid-speech tokens
}

# Modality groupings for aggregate stats
MODALITY_GROUPS = {
    "text": {"bos", "entity", "number", "code", "instruction", "eos", "regular", "punctuation"},
    "image": {"image_cls", "image_patch", "image_roi", "image_border"},
    "video": {"video_keyframe", "video_pframe", "video_bframe", "video_scene_change"},
    "audio": {"audio_onset", "audio_silence", "audio_speech"},
}


def get_modality(token_type: str) -> str:
    """Return the modality group for a token type."""
    for modality, types in MODALITY_GROUPS.items():
        if token_type in types:
            return modality
    return "text"


# ---------------------------------------------------------------------------
# Multimodal-Aware Simulator
# ---------------------------------------------------------------------------

class MultimodalTQCTMSimulator(TurboQuantCTMSimulator):
    """
    TurboQuant + CTM+ simulator with multimodal token type support.

    Overrides:
    - TOKEN_IMPORTANCE: extended with image/video/audio types
    - _score(): adds modality-aware weighting
    - _simulate_compression(): models modality-specific compression quality
    - get_stats(): adds per-modality breakdown
    """

    TOKEN_IMPORTANCE = MULTIMODAL_TOKEN_IMPORTANCE

    def __init__(
        self,
        base_max_tokens: int,
        config: IntegratedConfig,
        modality_weight: float = 0.05,
    ):
        """
        Args:
            base_max_tokens: Cache capacity in FP16 tokens
            config: Integrated TQ + CTM+ configuration
            modality_weight: Extra scoring weight for modality signal (default 0.05)
        """
        super().__init__(base_max_tokens, config)
        self.modality_weight = modality_weight

        # Per-modality statistics
        self.modality_stats = {
            mod: {"inserted": 0, "evicted": 0, "retained": 0}
            for mod in MODALITY_GROUPS
        }

    def reset(self):
        super().reset()
        self.modality_stats = {
            mod: {"inserted": 0, "evicted": 0, "retained": 0}
            for mod in MODALITY_GROUPS
        }

    def access(self, position: int, token_type: str = "regular",
               attention_weight: float = 0.01) -> bool:
        hit = super().access(position, token_type, attention_weight)
        if not hit:
            mod = get_modality(token_type)
            self.modality_stats[mod]["inserted"] += 1
        return hit

    def _evict(self):
        """Override to track per-modality evictions."""
        if not self.cache:
            return
        self.stats["evictions"] += 1
        victim = self._ctm_select_victim()
        victim_type = self.cache[victim].token_type
        mod = get_modality(victim_type)
        self.modality_stats[mod]["evicted"] += 1
        del self.cache[victim]
        if victim in self.lru_order:
            self.lru_order.remove(victim)

    def _simulate_compression(self, token_type: str) -> dict:
        """
        Model modality-specific compression quality.

        Image patches tend to compress very well (smooth gradients).
        Video B-frames compress well (temporal redundancy).
        Text entities compress slightly worse (high-norm, structured).
        """
        importance = self.TOKEN_IMPORTANCE.get(token_type, 0.4)
        modality = get_modality(token_type)
        bits = self.config.tq_config.angle_bits

        # Base quality by bit-width
        if bits <= 2:
            base_cosine, base_mse = 0.858, 0.016
        elif bits == 3:
            base_cosine, base_mse = 0.965, 0.004
        else:
            base_cosine, base_mse = 0.991, 0.001

        # Modality-specific adjustments
        if modality == "image":
            if token_type == "image_patch":
                # Patches are smooth, compress very well
                base_cosine += 0.008
                base_mse *= 0.7
            elif token_type == "image_cls":
                # CLS token has more structure
                base_cosine -= 0.003
                base_mse *= 1.2
        elif modality == "video":
            if token_type == "video_bframe":
                # B-frames are highly redundant
                base_cosine += 0.010
                base_mse *= 0.6
            elif token_type == "video_keyframe":
                base_cosine -= 0.005
                base_mse *= 1.3
        elif modality == "audio":
            if token_type == "audio_silence":
                base_cosine += 0.015
                base_mse *= 0.4
            elif token_type == "audio_onset":
                base_cosine -= 0.002
                base_mse *= 1.1
        else:  # text
            if importance > 0.7:
                base_cosine -= 0.005
                base_mse += 0.001

        # Add noise
        cosine = base_cosine + self.rng.uniform(-0.008, 0.008)
        mse = base_mse + self.rng.uniform(-0.0008, 0.0008)
        base_norm = 1.0 + importance * 2.0

        self.stats["tokens_compressed"] += 1
        self.stats["compression_mse_sum"] += mse
        self.stats["compression_cosine_sum"] += cosine

        return {
            "mse": max(0, mse),
            "cosine_similarity": min(1.0, max(0.0, cosine)),
            "original_norm": base_norm,
        }

    def _score(self, position: int) -> float:
        """
        Multimodal-aware scoring.

        Adds a modality signal: cross-modal anchor tokens (image_cls,
        video_keyframe) get a bonus because they bridge modalities.
        """
        # Base score from parent (6 signals + quality-aware)
        score = super()._score(position)

        # Signal 7: Modality anchor bonus
        meta = self.cache[position]
        modality = get_modality(meta.token_type)

        if modality != "text":
            # Cross-modal anchors are more valuable
            anchor_types = {"image_cls", "image_roi", "video_keyframe",
                           "video_scene_change", "audio_onset"}
            if meta.token_type in anchor_types:
                score += self.modality_weight * 1.0
            else:
                # Non-anchor multimodal tokens get slight penalty
                # (they compress well and are more expendable)
                score += self.modality_weight * (-0.2)

        return score

    def get_stats(self) -> dict:
        """Extended stats with per-modality breakdown."""
        base_stats = super().get_stats()

        # Count retained tokens per modality
        for pos, meta in self.cache.items():
            mod = get_modality(meta.token_type)
            self.modality_stats[mod]["retained"] += 1

        # Compute per-modality retention rates
        modality_retention = {}
        for mod, ms in self.modality_stats.items():
            inserted = ms["inserted"]
            retained = ms["retained"]
            modality_retention[mod] = {
                "inserted": inserted,
                "evicted": ms["evicted"],
                "retained": retained,
                "retention_rate": retained / max(1, inserted),
            }

        base_stats["modality_breakdown"] = modality_retention
        return base_stats


# ---------------------------------------------------------------------------
# Multimodal Workload Generators
# ---------------------------------------------------------------------------

class MultimodalWorkloadGenerator:
    """
    Generates realistic multimodal token access workloads.

    Models how vision-language models (VLMs) process mixed inputs:
    - Text tokens with standard LLM attention patterns
    - Image tokens (CLS + patches) with spatial attention
    - Video tokens (keyframes + P/B-frames) with temporal attention
    - Audio tokens (onsets + speech) with spectral attention
    """

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.np_rng = np.random.RandomState(seed)

    def text_only(self, seq_len: int) -> list[tuple[int, str, float]]:
        """Pure text workload (baseline)."""
        wg = WorkloadGenerator(seq_len, seed=self.rng.randint(0, 99999))
        return wg.sequential(seq_len)

    def image_text(
        self,
        text_tokens: int = 256,
        num_images: int = 1,
        patches_per_image: int = 196,  # ViT-B/16 on 224x224
        roi_fraction: float = 0.15,
    ) -> list[tuple[int, str, float]]:
        """
        Image + text workload (typical VLM input).

        Layout: [BOS] [IMG_CLS] [patches...] [text tokens...]
        """
        accesses = []
        pos = 0

        # BOS
        accesses.append((pos, "bos", 0.15))
        pos += 1

        for img_idx in range(num_images):
            # Image CLS token — high attention from all subsequent tokens
            cls_pos = pos
            accesses.append((pos, "image_cls", 0.12))
            pos += 1

            # Image patches
            roi_patches = set(self.rng.sample(
                range(patches_per_image),
                max(1, int(patches_per_image * roi_fraction))
            ))

            for p in range(patches_per_image):
                if p in roi_patches:
                    tt = "image_roi"
                    attn = 0.03 + self.rng.uniform(0, 0.02)
                elif p < 10 or p >= patches_per_image - 10:
                    tt = "image_border"
                    attn = 0.002
                else:
                    tt = "image_patch"
                    attn = 0.005 + self.rng.uniform(0, 0.005)
                accesses.append((pos, tt, attn))
                pos += 1

        # Text tokens that attend back to image
        for t in range(text_tokens):
            if t == 0 and text_tokens > 20:
                tt = "instruction"
            elif self.rng.random() < 0.05:
                tt = "entity"
            elif self.rng.random() < 0.05:
                tt = "number"
            elif self.rng.random() < 0.08:
                tt = "punctuation"
            else:
                tt = "regular"

            # Text tokens attend to image CLS + ROI patches
            attn = 0.01 + self.rng.uniform(0, 0.005)
            accesses.append((pos, tt, attn))
            pos += 1

            # Simulate cross-attention: text token accesses image CLS
            accesses.append((cls_pos, "image_cls", 0.08))
            # Occasionally re-attend to ROI patches
            if self.rng.random() < 0.2:
                roi_pos = self.rng.randint(cls_pos + 1, cls_pos + patches_per_image)
                accesses.append((roi_pos, "image_roi", 0.04))

        return accesses

    def video_text(
        self,
        text_tokens: int = 128,
        num_frames: int = 16,
        patches_per_frame: int = 49,  # 7x7 spatial tokens per frame
        keyframe_interval: int = 4,
    ) -> list[tuple[int, str, float]]:
        """
        Video + text workload.

        Layout: [BOS] [frame0_tokens...] [frame1_tokens...] ... [text...]
        Keyframes every keyframe_interval frames; rest are P/B-frames.
        """
        accesses = []
        pos = 0
        keyframe_positions = []

        accesses.append((pos, "bos", 0.10))
        pos += 1

        for f in range(num_frames):
            is_keyframe = (f % keyframe_interval == 0)
            is_scene_change = (f == 0 or (f > 0 and self.rng.random() < 0.1))

            if is_scene_change:
                frame_type = "video_scene_change"
            elif is_keyframe:
                frame_type = "video_keyframe"
            elif f % 2 == 0:
                frame_type = "video_pframe"
            else:
                frame_type = "video_bframe"

            # First token of each frame represents the frame type
            frame_start = pos
            attn = 0.06 if is_keyframe else 0.02
            accesses.append((pos, frame_type, attn))
            if is_keyframe or is_scene_change:
                keyframe_positions.append(pos)
            pos += 1

            # Spatial patches for this frame
            for p in range(patches_per_frame - 1):
                if is_keyframe:
                    patch_tt = "image_roi" if self.rng.random() < 0.15 else "image_patch"
                else:
                    patch_tt = "image_patch"
                patch_attn = 0.005 if is_keyframe else 0.002
                accesses.append((pos, patch_tt, patch_attn))
                pos += 1

        # Text tokens (caption/question about video)
        for t in range(text_tokens):
            tt = "regular"
            if t == 0:
                tt = "instruction"
            elif self.rng.random() < 0.05:
                tt = "entity"
            accesses.append((pos, tt, 0.01))
            pos += 1

            # Text attends to keyframes
            for kf_pos in keyframe_positions:
                if self.rng.random() < 0.3:
                    accesses.append((kf_pos, "video_keyframe", 0.05))

        return accesses

    def mixed_multimodal(
        self,
        text_tokens: int = 200,
        num_images: int = 1,
        patches_per_image: int = 64,
        num_video_frames: int = 8,
        patches_per_frame: int = 16,
        audio_tokens: int = 50,
    ) -> list[tuple[int, str, float]]:
        """
        Fully mixed: text + image + video + audio.

        Layout: [BOS] [images...] [video...] [audio...] [text...]
        """
        accesses = []
        pos = 0

        accesses.append((pos, "bos", 0.10))
        pos += 1

        # Images
        for _ in range(num_images):
            accesses.append((pos, "image_cls", 0.10))
            pos += 1
            for p in range(patches_per_image):
                tt = "image_roi" if self.rng.random() < 0.12 else "image_patch"
                accesses.append((pos, tt, 0.005))
                pos += 1

        # Video frames
        for f in range(num_video_frames):
            if f % 4 == 0:
                ft = "video_keyframe"
                attn = 0.05
            elif f % 2 == 0:
                ft = "video_pframe"
                attn = 0.02
            else:
                ft = "video_bframe"
                attn = 0.008
            accesses.append((pos, ft, attn))
            pos += 1
            for p in range(patches_per_frame - 1):
                accesses.append((pos, "image_patch", 0.003))
                pos += 1

        # Audio tokens
        for a in range(audio_tokens):
            if a == 0 or self.rng.random() < 0.15:
                tt = "audio_onset"
                attn = 0.04
            elif self.rng.random() < 0.1:
                tt = "audio_silence"
                attn = 0.001
            else:
                tt = "audio_speech"
                attn = 0.01
            accesses.append((pos, tt, attn))
            pos += 1

        # Text
        for t in range(text_tokens):
            if t == 0:
                tt = "instruction"
            elif self.rng.random() < 0.06:
                tt = "entity"
            elif self.rng.random() < 0.04:
                tt = "number"
            else:
                tt = "regular"
            accesses.append((pos, tt, 0.01))
            pos += 1

        return accesses


# ---------------------------------------------------------------------------
# Multimodal Benchmark Runner
# ---------------------------------------------------------------------------

def run_multimodal_benchmark(
    base_max_tokens: int = 40,
    head_dim: int = 64,
    verbose: bool = True,
) -> dict:
    """
    Run multimodal benchmark comparing text-only vs multimodal workloads
    across different configurations.

    Uses small base_max_tokens to force eviction pressure even after
    TurboQuant's ~3.8x expansion (40 * 3.8 ≈ 152 effective tokens,
    which is smaller than most workloads below).

    Returns dict of workload_name -> config_name -> stats.
    """
    gen = MultimodalWorkloadGenerator(seed=42)

    workloads = {
        "text_only": gen.text_only(seq_len=512),
        "image_text": gen.image_text(text_tokens=256, num_images=2, patches_per_image=96),
        "video_text": gen.video_text(text_tokens=128, num_frames=16, patches_per_frame=24),
        "mixed_multimodal": gen.mixed_multimodal(
            text_tokens=200, num_images=2, patches_per_image=64,
            num_video_frames=8, patches_per_frame=16, audio_tokens=50,
        ),
    }

    configs = {
        "LRU (text-only scoring)": {
            "config": IntegratedConfig(
                tq_config=TurboQuantConfig.three_bit(head_dim),
                ctm_config=CTMKVConfig(
                    weight_recency=0.90, weight_frequency=0.05,
                    weight_attention_strength=0.025, weight_token_importance=0.025,
                    weight_position=0.0, weight_sequence_priority=0.0,
                ),
                mode=IntegrationMode.CAPACITY_ONLY,
                fast_mode=True,
            ),
            "multimodal": False,
        },
        "CTM+ (text-only scoring)": {
            "config": IntegratedConfig(
                tq_config=TurboQuantConfig.three_bit(head_dim),
                ctm_config=CTMKVConfig(),
                mode=IntegrationMode.QUALITY_AWARE,
                fast_mode=True,
            ),
            "multimodal": False,
        },
        "CTM+ (multimodal-aware)": {
            "config": IntegratedConfig(
                tq_config=TurboQuantConfig.three_bit(head_dim),
                ctm_config=CTMKVConfig(),
                mode=IntegrationMode.QUALITY_AWARE,
                fast_mode=True,
            ),
            "multimodal": True,
        },
    }

    all_results = {}

    for wl_name, workload in workloads.items():
        all_results[wl_name] = {}

        for cfg_name, cfg_info in configs.items():
            start = time.perf_counter()

            if cfg_info["multimodal"]:
                sim = MultimodalTQCTMSimulator(
                    base_max_tokens, cfg_info["config"], modality_weight=0.05,
                )
            else:
                sim = TurboQuantCTMSimulator(base_max_tokens, cfg_info["config"])

            for pos, token_type, attn in workload:
                sim.access(pos, token_type, attn)

            elapsed = time.perf_counter() - start
            stats = sim.get_stats()
            stats["elapsed_seconds"] = elapsed
            stats["workload_size"] = len(workload)
            all_results[wl_name][cfg_name] = stats

    if verbose:
        _print_multimodal_results(all_results, base_max_tokens)

    return all_results


def run_multimodal_retention_benchmark(
    base_max_tokens: int = 30,
    head_dim: int = 64,
    verbose: bool = True,
) -> dict:
    """
    Measure how well each config retains important multimodal anchor tokens
    (image_cls, video_keyframe, entities) vs expendable tokens.

    Uses small base_max_tokens (30 * 3.8 ≈ 114 effective) to force
    eviction among the ~400 unique tokens in the workload.
    """
    gen = MultimodalWorkloadGenerator(seed=123)
    workload = gen.mixed_multimodal(
        text_tokens=200, num_images=2, patches_per_image=64,
        num_video_frames=8, patches_per_frame=16, audio_tokens=50,
    )

    # Identify anchor positions
    anchor_types = {"bos", "image_cls", "image_roi", "video_keyframe",
                    "video_scene_change", "audio_onset", "entity", "instruction"}
    anchor_positions = set()
    for pos, tt, _ in workload:
        if tt in anchor_types:
            anchor_positions.add(pos)

    configs = {
        "TQ-3bit + LRU": (
            IntegratedConfig(
                tq_config=TurboQuantConfig.three_bit(head_dim),
                ctm_config=CTMKVConfig(
                    weight_recency=0.90, weight_frequency=0.05,
                    weight_attention_strength=0.025, weight_token_importance=0.025,
                    weight_position=0.0, weight_sequence_priority=0.0,
                ),
                mode=IntegrationMode.CAPACITY_ONLY, fast_mode=True,
            ),
            False,
        ),
        "TQ-3bit + CTM+ (text)": (
            IntegratedConfig(
                tq_config=TurboQuantConfig.three_bit(head_dim),
                ctm_config=CTMKVConfig(),
                mode=IntegrationMode.QUALITY_AWARE, fast_mode=True,
            ),
            False,
        ),
        "TQ-3bit + CTM+ (multimodal)": (
            IntegratedConfig(
                tq_config=TurboQuantConfig.three_bit(head_dim),
                ctm_config=CTMKVConfig(),
                mode=IntegrationMode.QUALITY_AWARE, fast_mode=True,
            ),
            True,
        ),
    }

    results = {}
    for name, (config, is_mm) in configs.items():
        if is_mm:
            sim = MultimodalTQCTMSimulator(base_max_tokens, config, modality_weight=0.05)
        else:
            sim = TurboQuantCTMSimulator(base_max_tokens, config)

        for pos, tt, attn in workload:
            sim.access(pos, tt, attn)

        retained_anchors = len(anchor_positions.intersection(sim.cache.keys()))
        total_retained = len(sim.cache)

        results[name] = {
            "anchor_retention": retained_anchors / max(1, len(anchor_positions)),
            "retained_anchors": retained_anchors,
            "total_anchors": len(anchor_positions),
            "cache_occupancy": total_retained,
            "effective_capacity": sim.effective_max_tokens,
            "hit_rate": sim.hit_rate,
        }

        if is_mm and hasattr(sim, "modality_stats"):
            results[name]["modality_breakdown"] = dict(sim.modality_stats)

    if verbose:
        print("\n" + "=" * 72)
        print("MULTIMODAL ANCHOR RETENTION BENCHMARK")
        print("=" * 72)
        print(f"  Base cache: {base_max_tokens} tokens | Anchor tokens: {len(anchor_positions)}")
        print()
        print(f"  {'Configuration':<35} {'Anchor Ret.':>12} {'Hit Rate':>10} {'Kept':>8}")
        print(f"  {'-'*67}")
        for name, r in results.items():
            print(f"  {name:<35} {r['anchor_retention']:>11.1%}"
                  f" {r['hit_rate']:>9.2%}"
                  f" {r['retained_anchors']:>3}/{r['total_anchors']}")
        print("=" * 72)

    return results


def _print_multimodal_results(results: dict, base_max_tokens: int):
    """Pretty-print multimodal benchmark results."""
    print("\n" + "=" * 80)
    print("MULTIMODAL TURBOQUANT + CTM+ BENCHMARK")
    print("=" * 80)
    print(f"  Base cache capacity (FP16): {base_max_tokens} tokens")
    print()

    for wl_name, configs in results.items():
        print(f"\n  Workload: {wl_name}")
        print(f"  {'Configuration':<35} {'Hit Rate':>9} {'Eff.Size':>9}"
              f" {'Evictions':>10} {'Time':>8}")
        print(f"  {'-'*73}")

        for cfg_name, stats in configs.items():
            hr = stats.get("hit_rate", 0)
            eff = stats.get("effective_max_tokens", base_max_tokens)
            evictions = stats.get("evictions", 0)
            elapsed = stats.get("elapsed_seconds", 0)
            print(f"  {cfg_name:<35} {hr:>8.2%} {eff:>8,}"
                  f" {evictions:>9,} {elapsed:>7.3f}s")

        # Show modality breakdown for multimodal-aware config
        for cfg_name, stats in configs.items():
            if "modality_breakdown" in stats:
                print(f"\n  Modality breakdown ({cfg_name}):")
                for mod, ms in stats["modality_breakdown"].items():
                    if ms["inserted"] > 0:
                        print(f"    {mod:<8}: inserted={ms['inserted']:>4}"
                              f"  retained={ms['retained']:>4}"
                              f"  retention={ms['retention_rate']:>6.1%}")

    print("\n" + "=" * 80)
