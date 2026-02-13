"""
Prompt builder for generating Remotion TSX code via the Phase Quad LLM.

This module constructs the system prompt and user prompt that guide
the LLM to produce valid, renderable Remotion React components.
"""

from typing import Optional, Dict, Any


# The system prompt that teaches the LLM how to write Remotion TSX
REMOTION_SYSTEM_PROMPT = """You are an expert motion graphics developer using Remotion (React-based video framework).
You generate TSX code for Remotion compositions that render to MP4 video.

## Rules

1. Output ONLY valid TSX code. No explanations, no markdown fences, just pure TSX.
2. Use only these Remotion imports:
   - `useCurrentFrame`, `useVideoConfig`, `interpolate`, `spring`, `Sequence`, `AbsoluteFill`
   - `Easing` from "remotion"
3. Export a single default React component that is the video composition.
4. The component receives no props - all configuration is internal.
5. Use `useCurrentFrame()` for animation timing and `useVideoConfig()` for fps/dimensions.
6. Use `interpolate()` for smooth value transitions between keyframes.
7. Use `spring()` for natural-feeling motion with spring physics.
8. Use `<Sequence from={frame}>` to sequence elements appearing over time.
9. Use inline styles (React CSSProperties) for all styling - no external CSS.
10. Keep the composition self-contained in a single file.
11. Use readable colors with good contrast. Default background: #0f0f23.
12. For text, use system fonts: 'Inter', 'Helvetica Neue', Arial, sans-serif.
13. Target 30fps, 1920x1080 resolution unless specified otherwise.
14. Duration should be 3-10 seconds (90-300 frames at 30fps) unless specified.

## Animation Patterns

### Fade In
```
const opacity = interpolate(frame, [0, 30], [0, 1], { extrapolateRight: 'clamp' });
```

### Slide In from Left
```
const translateX = interpolate(frame, [0, 30], [-100, 0], { extrapolateRight: 'clamp' });
```

### Spring Bounce
```
const scale = spring({ frame, fps, config: { damping: 12, stiffness: 200 } });
```

### Staggered Elements
```
<Sequence from={0}><Element1 /></Sequence>
<Sequence from={15}><Element2 /></Sequence>
<Sequence from={30}><Element3 /></Sequence>
```

## Example Composition

```tsx
import { useCurrentFrame, useVideoConfig, interpolate, spring, AbsoluteFill, Sequence } from "remotion";

const MyVideo: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleOpacity = interpolate(frame, [0, 30], [0, 1], { extrapolateRight: 'clamp' });
  const titleY = spring({ frame, fps, config: { damping: 12 } });

  return (
    <AbsoluteFill style={{ backgroundColor: '#0f0f23', justifyContent: 'center', alignItems: 'center' }}>
      <div style={{
        opacity: titleOpacity,
        transform: `translateY(${interpolate(titleY, [0, 1], [50, 0])}px)`,
        fontSize: 72,
        fontWeight: 'bold',
        color: 'white',
        fontFamily: 'Inter, Helvetica Neue, Arial, sans-serif',
      }}>
        Hello World
      </div>
    </AbsoluteFill>
  );
};

export default MyVideo;
```

Now generate TSX code for the user's request."""


# Template categories for common video types
VIDEO_TEMPLATES = {
    "title_card": "A professional title card with animated text entrance",
    "data_visualization": "An animated chart/graph showing data with smooth transitions",
    "logo_reveal": "A logo reveal animation with particle effects or geometric shapes",
    "text_animation": "Kinetic typography with words appearing in sequence",
    "countdown": "An animated countdown timer with visual effects",
    "metrics_dashboard": "An animated dashboard showing metrics/KPIs with progress bars",
    "explainer": "An animated explainer with icons and text appearing in sequence",
    "coherence_viz": "Symbol-U coherence metrics visualization with animated gauges",
}


class RemotionPromptBuilder:
    """
    Builds prompts for the LLM to generate Remotion TSX code.

    Handles:
    - System prompt with Remotion API documentation
    - User prompt construction from natural language descriptions
    - Template-based prompting for common video types
    - Symbol-U specific visualizations (coherence, entropy, ontological)
    """

    def __init__(self):
        self.system_prompt = REMOTION_SYSTEM_PROMPT

    def build_prompt(
        self,
        description: str,
        template: Optional[str] = None,
        style: Optional[Dict[str, Any]] = None,
        duration_seconds: Optional[int] = None,
        resolution: Optional[Dict[str, int]] = None,
    ) -> str:
        """
        Build the user prompt for TSX generation.

        Args:
            description: Natural language description of the video.
            template: Optional template category from VIDEO_TEMPLATES.
            style: Optional style overrides (colors, fonts, etc).
            duration_seconds: Video duration in seconds.
            resolution: Video resolution {"width": int, "height": int}.

        Returns:
            Formatted user prompt string.
        """
        parts = []

        # Add template context if specified
        if template and template in VIDEO_TEMPLATES:
            parts.append(f"Video type: {VIDEO_TEMPLATES[template]}")

        # Add the user description
        parts.append(f"Create a Remotion video composition: {description}")

        # Add duration constraint
        if duration_seconds:
            fps = 30
            frames = duration_seconds * fps
            parts.append(f"Duration: {duration_seconds} seconds ({frames} frames at {fps}fps)")

        # Add resolution
        if resolution:
            parts.append(f"Resolution: {resolution.get('width', 1920)}x{resolution.get('height', 1080)}")

        # Add style overrides
        if style:
            if "background_color" in style:
                parts.append(f"Background color: {style['background_color']}")
            if "primary_color" in style:
                parts.append(f"Primary text/accent color: {style['primary_color']}")
            if "font_family" in style:
                parts.append(f"Font: {style['font_family']}")

        parts.append("Output only the TSX code, nothing else.")

        return "\n".join(parts)

    def build_coherence_viz_prompt(
        self,
        metrics: Dict[str, float],
        session_id: Optional[str] = None,
    ) -> str:
        """
        Build a prompt for Symbol-U coherence metrics visualization.

        Args:
            metrics: Dict of coherence metrics (stability, drift, entropy, etc).
            session_id: Optional session ID to display.

        Returns:
            Formatted prompt for coherence visualization video.
        """
        metrics_str = "\n".join(f"  - {k}: {v:.3f}" for k, v in metrics.items())

        prompt = f"""Create an animated dashboard visualization for Symbol-U coherence metrics.

The metrics to display:
{metrics_str}

Requirements:
- Show each metric as an animated circular gauge or progress bar
- Stagger the animations so metrics appear one by one
- Use color coding: green (>0.7), yellow (0.4-0.7), red (<0.4)
- Add a title "Symbol-U Coherence Report"
- Include subtle particle/dot background animation
- Professional dark theme (#0f0f23 background)"""

        if session_id:
            prompt += f"\n- Show session ID: {session_id} in the corner"

        prompt += "\nOutput only the TSX code, nothing else."
        return prompt

    def build_ontological_viz_prompt(
        self,
        dimensions: Dict[str, float],
    ) -> str:
        """
        Build a prompt for ontological dimension visualization.

        Args:
            dimensions: Dict of 12D ontological values.

        Returns:
            Formatted prompt for ontological visualization video.
        """
        dims_str = "\n".join(f"  - {k}: {v:.3f}" for k, v in dimensions.items())

        return f"""Create an animated radar/spider chart visualization for Symbol-U's 12-dimensional ontological profile.

Dimensions:
{dims_str}

Requirements:
- Animate the radar chart drawing from center outward
- Label each axis with the dimension name
- Use gradient fills (purple to cyan) for the radar area
- Add a pulsing glow effect on the vertices
- Show numeric values appearing next to each vertex
- Title: "Ontological State Profile"
- Dark background (#0f0f23), white labels
- Duration: 5 seconds

Output only the TSX code, nothing else."""

    @staticmethod
    def get_available_templates() -> Dict[str, str]:
        """Get available video template categories."""
        return VIDEO_TEMPLATES.copy()
