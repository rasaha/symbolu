"""
AI Video Generation Service using Remotion + Phase Quad LLM.

This module bridges the Phase Quad LLM text generation pipeline with
Remotion's React-based video rendering. Instead of neural video diffusion,
the LLM generates TSX code that Remotion deterministically renders to MP4.

Architecture:
    1. User provides a natural language video description
    2. Phase Quad LLM generates Remotion-compatible TSX code via the chat service
    3. TSX code is written to the Remotion project
    4. Remotion CLI renders the React components to MP4 frames
    5. Result is returned as a video file path

This approach is complementary to the existing PhaseQuadVideoPipeline:
    - PhaseQuadVideoPipeline: Neural diffusion for photorealistic/artistic video
    - RemotionVideoPipeline: Code-based rendering for motion graphics, data viz, text animations
"""

from symbolu_core.service.video_gen.service import RemotionVideoService
from symbolu_core.service.video_gen.prompt_builder import RemotionPromptBuilder

__all__ = ["RemotionVideoService", "RemotionPromptBuilder"]
