"""
Remotion Video Generation Service.

Orchestrates the full pipeline:
    prompt → LLM (TSX generation) → Remotion (render to MP4)

This service uses the existing ChatService to generate TSX code,
writes it into the Remotion project, and invokes the Remotion CLI
to render the final video.
"""

import logging
import os
import re
import time
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List

from symbolu.service.video_gen.prompt_builder import RemotionPromptBuilder

logger = logging.getLogger(__name__)


# Path to the Remotion project relative to project root
REMOTION_PROJECT_DIR = Path(__file__).parent.parent.parent.parent / "frontend" / "remotion"
OUTPUT_DIR = Path(__file__).parent.parent.parent.parent / "artifacts" / "videos"


@dataclass
class VideoGenerationRequest:
    """Request for AI video generation."""
    description: str
    template: Optional[str] = None
    style: Optional[Dict[str, Any]] = None
    duration_seconds: int = 5
    resolution: Optional[Dict[str, int]] = None
    fps: int = 30
    output_format: str = "mp4"


@dataclass
class VideoGenerationResult:
    """Result of AI video generation."""
    video_id: str
    video_path: Optional[str]
    tsx_code: str
    generation_time_ms: float
    render_time_ms: float
    total_time_ms: float
    status: str  # "success", "tsx_generated", "render_failed"
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences from LLM output if present."""
    # Remove ```tsx ... ``` or ```typescript ... ``` or ``` ... ```
    pattern = r'^```(?:tsx|typescript|jsx|js)?\s*\n?(.*?)\n?\s*```$'
    match = re.match(pattern, text.strip(), re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def _validate_tsx(code: str) -> List[str]:
    """
    Basic validation of generated TSX code.

    Returns list of warnings (empty = valid).
    """
    warnings = []

    if "export default" not in code:
        warnings.append("Missing 'export default' - component may not be importable")

    if "useCurrentFrame" not in code:
        warnings.append("Missing 'useCurrentFrame' - video may be static")

    if "remotion" not in code.lower() and "import" in code:
        warnings.append("No Remotion imports detected")

    # Check for potentially dangerous patterns
    dangerous = ["eval(", "Function(", "require(", "process.", "fs.", "__dirname"]
    for pattern in dangerous:
        if pattern in code:
            warnings.append(f"Potentially unsafe pattern: {pattern}")

    return warnings


class RemotionVideoService:
    """
    Service for generating videos using LLM + Remotion.

    Workflow:
        1. Build prompt from user description
        2. Send to Phase Quad LLM via ChatService
        3. Extract and validate TSX code
        4. Write to Remotion project
        5. Invoke Remotion CLI to render
        6. Return video file path

    Example:
        service = RemotionVideoService()
        result = await service.generate(
            VideoGenerationRequest(
                description="An animated logo reveal for Symbol-U with glowing text",
                duration_seconds=5,
            )
        )
        print(result.video_path)
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        remotion_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
    ):
        self.prompt_builder = RemotionPromptBuilder()
        self.provider = provider
        self.remotion_dir = remotion_dir or REMOTION_PROJECT_DIR
        self.output_dir = output_dir or OUTPUT_DIR

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def generate(
        self,
        request: VideoGenerationRequest,
    ) -> VideoGenerationResult:
        """
        Generate a video from a natural language description.

        Args:
            request: VideoGenerationRequest with description and options.

        Returns:
            VideoGenerationResult with video path and metadata.
        """
        start_time = time.time()
        video_id = str(uuid.uuid4())[:8]

        # Step 1: Build the prompt
        user_prompt = self.prompt_builder.build_prompt(
            description=request.description,
            template=request.template,
            style=request.style,
            duration_seconds=request.duration_seconds,
            resolution=request.resolution,
        )

        # Step 2: Generate TSX code via ChatService
        tsx_code = await self._generate_tsx(user_prompt)
        generation_time = (time.time() - start_time) * 1000

        # Step 3: Validate
        warnings = _validate_tsx(tsx_code)
        if warnings:
            logger.warning(f"TSX validation warnings for {video_id}: {warnings}")

        # Step 4: Write TSX to Remotion project
        composition_path = self._write_composition(video_id, tsx_code, request)

        # Step 5: Render via Remotion CLI
        render_start = time.time()
        video_path, render_error = self._render_video(
            video_id, request
        )
        render_time = (time.time() - render_start) * 1000

        total_time = (time.time() - start_time) * 1000

        status = "success" if video_path else "tsx_generated"
        if render_error and not video_path:
            status = "render_failed"

        return VideoGenerationResult(
            video_id=video_id,
            video_path=str(video_path) if video_path else None,
            tsx_code=tsx_code,
            generation_time_ms=generation_time,
            render_time_ms=render_time,
            total_time_ms=total_time,
            status=status,
            error=render_error,
            metadata={
                "warnings": warnings,
                "composition_path": str(composition_path),
                "template": request.template,
                "duration_seconds": request.duration_seconds,
                "fps": request.fps,
                "format": request.output_format,
            },
        )

    async def generate_coherence_video(
        self,
        metrics: Dict[str, float],
        session_id: Optional[str] = None,
    ) -> VideoGenerationResult:
        """
        Generate a coherence metrics visualization video.

        Args:
            metrics: Coherence metrics dict.
            session_id: Optional session ID.

        Returns:
            VideoGenerationResult with the visualization.
        """
        user_prompt = self.prompt_builder.build_coherence_viz_prompt(
            metrics, session_id
        )

        start_time = time.time()
        video_id = f"coherence-{str(uuid.uuid4())[:8]}"

        tsx_code = await self._generate_tsx(user_prompt)
        generation_time = (time.time() - start_time) * 1000

        request = VideoGenerationRequest(
            description="Coherence metrics visualization",
            duration_seconds=6,
            template="coherence_viz",
        )

        composition_path = self._write_composition(video_id, tsx_code, request)

        render_start = time.time()
        video_path, render_error = self._render_video(video_id, request)
        render_time = (time.time() - render_start) * 1000

        total_time = (time.time() - start_time) * 1000

        return VideoGenerationResult(
            video_id=video_id,
            video_path=str(video_path) if video_path else None,
            tsx_code=tsx_code,
            generation_time_ms=generation_time,
            render_time_ms=render_time,
            total_time_ms=total_time,
            status="success" if video_path else "tsx_generated",
            error=render_error,
            metadata={"metrics": metrics, "session_id": session_id},
        )

    async def _generate_tsx(self, user_prompt: str) -> str:
        """
        Generate TSX code using the Phase Quad LLM via ChatService.

        Falls back to a template if the chat service is unavailable.
        """
        try:
            from symbolu.service.chat_service import ChatService

            service = ChatService(provider=self.provider)
            response = await service.chat(
                message=user_prompt,
                tier="power_user",
                system_prompt=self.prompt_builder.system_prompt,
                temperature=0.3,  # Lower temperature for code generation
                max_tokens=4000,
            )

            tsx_code = _strip_code_fences(response.content)
            logger.info(
                f"Generated TSX code ({len(tsx_code)} chars) "
                f"via {response.provider}/{response.model}"
            )
            return tsx_code

        except Exception as e:
            logger.warning(f"ChatService unavailable ({e}), using fallback template")
            return self._get_fallback_template(user_prompt)

    def _get_fallback_template(self, description: str) -> str:
        """Return a basic template when LLM is unavailable."""
        # Extract a title from the description
        title = description[:50].strip()
        if len(description) > 50:
            title = title.rsplit(" ", 1)[0] + "..."

        return f'''import {{ useCurrentFrame, useVideoConfig, interpolate, spring, AbsoluteFill, Sequence }} from "remotion";

const GeneratedVideo: React.FC = () => {{
  const frame = useCurrentFrame();
  const {{ fps }} = useVideoConfig();

  const titleScale = spring({{ frame, fps, config: {{ damping: 12, stiffness: 200 }} }});
  const titleOpacity = interpolate(frame, [0, 20], [0, 1], {{ extrapolateRight: "clamp" }});

  const subtitleOpacity = interpolate(frame, [30, 50], [0, 1], {{ extrapolateRight: "clamp" }});
  const subtitleY = interpolate(frame, [30, 50], [20, 0], {{ extrapolateRight: "clamp" }});

  const barWidth = interpolate(frame, [60, 120], [0, 80], {{ extrapolateRight: "clamp" }});

  return (
    <AbsoluteFill
      style={{{{
        backgroundColor: "#0f0f23",
        justifyContent: "center",
        alignItems: "center",
        fontFamily: "Inter, Helvetica Neue, Arial, sans-serif",
      }}}}
    >
      <Sequence from={{0}}>
        <div
          style={{{{
            opacity: titleOpacity,
            transform: `scale(${{titleScale}})`,
            fontSize: 64,
            fontWeight: "bold",
            color: "white",
            textAlign: "center",
            marginBottom: 20,
          }}}}
        >
          {title}
        </div>
      </Sequence>

      <Sequence from={{30}}>
        <div
          style={{{{
            opacity: subtitleOpacity,
            transform: `translateY(${{subtitleY}}px)`,
            fontSize: 24,
            color: "#a0a0c0",
            textAlign: "center",
            marginBottom: 40,
          }}}}
        >
          Generated by Symbol-U Phase Quad Engine
        </div>
      </Sequence>

      <Sequence from={{60}}>
        <div
          style={{{{
            width: 400,
            height: 6,
            backgroundColor: "#1a1a3e",
            borderRadius: 3,
            overflow: "hidden",
          }}}}
        >
          <div
            style={{{{
              width: `${{barWidth}}%`,
              height: "100%",
              background: "linear-gradient(90deg, #6366f1, #8b5cf6, #a78bfa)",
              borderRadius: 3,
            }}}}
          />
        </div>
      </Sequence>
    </AbsoluteFill>
  );
}};

export default GeneratedVideo;
'''

    def _write_composition(
        self,
        video_id: str,
        tsx_code: str,
        request: VideoGenerationRequest,
    ) -> Path:
        """Write the generated TSX to the Remotion project."""
        compositions_dir = self.remotion_dir / "src" / "compositions"
        compositions_dir.mkdir(parents=True, exist_ok=True)

        filename = f"Generated_{video_id}.tsx"
        filepath = compositions_dir / filename

        filepath.write_text(tsx_code, encoding="utf-8")
        logger.info(f"Wrote composition to {filepath}")

        return filepath

    def _render_video(
        self,
        video_id: str,
        request: VideoGenerationRequest,
    ) -> tuple:
        """
        Render video using Remotion CLI.

        Returns:
            (video_path, error_message) - video_path is None if render failed.
        """
        output_filename = f"{video_id}.{request.output_format}"
        output_path = self.output_dir / output_filename

        # Check if npx/remotion is available
        npx_path = self._find_npx()
        if not npx_path:
            return None, "npx not found - install Node.js to enable video rendering"

        # Check if Remotion project has been initialized
        if not (self.remotion_dir / "package.json").exists():
            return None, (
                "Remotion project not initialized. "
                "Run 'cd frontend/remotion && npm install' first."
            )

        try:
            # Build the render command
            composition_id = f"Generated_{video_id}"
            frames = request.duration_seconds * request.fps

            cmd = [
                npx_path, "remotion", "render",
                str(self.remotion_dir / "src" / "index.ts"),
                composition_id,
                str(output_path),
                "--frames", str(frames),
                "--fps", str(request.fps),
            ]

            if request.resolution:
                cmd.extend(["--width", str(request.resolution.get("width", 1920))])
                cmd.extend(["--height", str(request.resolution.get("height", 1080))])

            logger.info(f"Rendering video: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(self.remotion_dir),
            )

            if result.returncode == 0:
                logger.info(f"Rendered video to {output_path}")
                return output_path, None
            else:
                error = result.stderr or result.stdout
                logger.error(f"Render failed: {error}")
                return None, f"Render failed: {error[:500]}"

        except subprocess.TimeoutExpired:
            return None, "Render timed out after 120 seconds"
        except FileNotFoundError:
            return None, "Remotion CLI not found"
        except Exception as e:
            return None, f"Render error: {str(e)}"

    @staticmethod
    def _find_npx() -> Optional[str]:
        """Find npx binary."""
        import shutil
        return shutil.which("npx")
