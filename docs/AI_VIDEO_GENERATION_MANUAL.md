# Symbol-U AI Video Generation

## User Manual: Remotion + Phase Quad LLM Video Pipeline

**Version:** 1.0
**Last Updated:** 2026-02-13
**Module Path:** `symbolu/service/video_gen/`
**Remotion Project:** `frontend/remotion/`

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Prerequisites](#3-prerequisites)
4. [Installation](#4-installation)
5. [Quick Start](#5-quick-start)
6. [API Reference](#6-api-reference)
7. [Built-in Templates](#7-built-in-templates)
8. [Using the Frontend UI](#8-using-the-frontend-ui)
9. [Python SDK Usage](#9-python-sdk-usage)
10. [How the LLM Generates Video Code](#10-how-the-llm-generates-video-code)
11. [Remotion Studio (Preview & Development)](#11-remotion-studio-preview--development)
12. [Command-Line Rendering](#12-command-line-rendering)
13. [Customization](#13-customization)
14. [Two Video Pipelines Compared](#14-two-video-pipelines-compared)
15. [Troubleshooting](#15-troubleshooting)
16. [File Reference](#16-file-reference)

---

## 1. Overview

Symbol-U provides **two complementary video generation approaches**:

| Approach | Engine | Best For | Requires |
|----------|--------|----------|----------|
| **Neural Diffusion** | `PhaseQuadVideoPipeline` (CogVideoX VAE) | Photorealistic, artistic video | Trained model weights, GPU |
| **Code-Based Rendering** | `RemotionVideoService` (LLM + Remotion) | Motion graphics, data viz, text animations | Node.js only (no GPU) |

This manual covers the **Code-Based Rendering** pipeline. The core idea is simple:

1. You describe a video in plain English
2. The Phase Quad LLM writes React/TSX code using Remotion's animation APIs
3. Remotion renders those React components frame-by-frame into an MP4

Because the LLM generates **code** (not pixels), the output is:
- **100% deterministic** -- same code always produces the same video
- **Editable** -- you can modify the generated TSX before rendering
- **Lightweight** -- no GPU, no model weights, just Node.js
- **Unlimited variety** -- if you can describe it, the LLM can code it

---

## 2. Architecture

```
                    Symbol-U AI Video Generation Pipeline
                    ====================================

    User                    Backend                         Frontend
    ----                    -------                         --------

  "Create an          POST /video/generate
   animated       ──────────────────────────►
   title card"         │
                       │  RemotionVideoService
                       │
                       ▼
                ┌──────────────┐
                │  Prompt      │   Constructs system prompt with
                │  Builder     │   Remotion API docs + animation
                │              │   patterns + user description
                └──────┬───────┘
                       │
                       ▼
                ┌──────────────┐
                │  Phase Quad  │   ChatService.chat()
                │  LLM         │   tier="power_user"
                │  (Claude /   │   temperature=0.3
                │   Gemini)    │   max_tokens=4000
                └──────┬───────┘
                       │
                       │  Generated TSX code
                       ▼
                ┌──────────────┐
                │  Validator   │   Checks for: export default,
                │              │   useCurrentFrame, Remotion imports,
                │              │   dangerous patterns (eval, fs, etc.)
                └──────┬───────┘
                       │
                       ▼
                ┌──────────────┐
                │  Write to    │   frontend/remotion/src/compositions/
                │  Remotion    │   Generated_{video_id}.tsx
                │  Project     │
                └──────┬───────┘
                       │
                       ▼
                ┌──────────────┐
                │  Remotion    │   npx remotion render
                │  CLI         │   → MP4 frame-by-frame
                │  Renderer    │
                └──────┬───────┘
                       │
                       ▼
                ┌──────────────┐
                │  Output      │   artifacts/videos/{video_id}.mp4
                │  MP4 File    │
                └──────────────┘
                       │
                       │  VideoGenerateResponse
                       │  { video_id, status, tsx_code, video_path }
                       ▼
               ◄───────────────────────────
                                        VideoGenerator.tsx
                                        Shows: status, code preview,
                                        download link
```

### Key Components

| Component | File | Role |
|-----------|------|------|
| `RemotionVideoService` | `symbolu/service/video_gen/service.py` | Orchestrates the full pipeline |
| `RemotionPromptBuilder` | `symbolu/service/video_gen/prompt_builder.py` | Constructs LLM prompts with Remotion API docs |
| API Endpoints | `symbolu/service/api_server.py` | HTTP interface (`/video/generate`, `/video/coherence`, `/video/templates`) |
| Remotion Project | `frontend/remotion/` | React-based video rendering project |
| Template Compositions | `frontend/remotion/src/templates/` | 4 pre-built video templates |
| Frontend UI | `frontend/src/components/video/VideoGenerator.tsx` | User-facing video generation interface |

---

## 3. Prerequisites

### Required

- **Python 3.10+** -- for the Symbol-U backend
- **Node.js 18+** -- for Remotion video rendering
- **npm** -- comes with Node.js

### Required for LLM-powered generation

At least one LLM provider API key:

- **Anthropic API key** (`ANTHROPIC_API_KEY`) -- for Claude models
- **Google API key** (`GOOGLE_API_KEY`) -- for Gemini models

Without an API key, the service falls back to a basic template (still produces a valid video, just not AI-customized).

### Optional

- **Chrome/Chromium** -- Remotion uses it internally for rendering (usually auto-installed by Remotion)

---

## 4. Installation

### Step 1: Install the Remotion project dependencies

```bash
cd frontend/remotion
npm install
```

This installs Remotion 4.x, React 18, and TypeScript.

### Step 2: Verify the backend dependencies

The video generation service uses the existing `ChatService`, so ensure the Symbol-U backend dependencies are installed:

```bash
pip install -r requirements.txt
```

### Step 3: Set your LLM API key

```bash
# Option A: Anthropic Claude (recommended)
export ANTHROPIC_API_KEY="sk-ant-..."

# Option B: Google Gemini
export GOOGLE_API_KEY="AIza..."
```

Or add to your `.env` file:

```
ANTHROPIC_API_KEY=sk-ant-...
LLM_PROVIDER=anthropic
```

### Step 4: Verify installation

```bash
# Check Remotion is working
cd frontend/remotion
npx remotion studio src/index.ts
# Opens a browser preview of the built-in templates

# Check the backend
python -c "from symbolu.service.video_gen import RemotionVideoService; print('OK')"
```

---

## 5. Quick Start

### Option A: Via the API (fastest)

Start the Symbol-U server:

```bash
python -m uvicorn symbolu.service.api_server:create_app --host 0.0.0.0 --port 8000
```

Generate a video:

```bash
curl -X POST http://localhost:8000/video/generate \
  -H "Content-Type: application/json" \
  -d '{
    "description": "An animated title card with the text Symbol-U scaling in with spring physics, followed by the tagline Deterministic AGI Engine fading in below, on a dark purple background",
    "template": "title_card",
    "duration_seconds": 5
  }'
```

Response:

```json
{
  "video_id": "a1b2c3d4",
  "status": "success",
  "tsx_code": "import { useCurrentFrame, ... } ...",
  "video_path": "/path/to/artifacts/videos/a1b2c3d4.mp4",
  "generation_time_ms": 2340.5,
  "render_time_ms": 8920.1,
  "total_time_ms": 11260.6,
  "error": null,
  "metadata": { ... }
}
```

### Option B: Via Python SDK

```python
import asyncio
from symbolu.service.video_gen import RemotionVideoService
from symbolu.service.video_gen.service import VideoGenerationRequest

async def main():
    service = RemotionVideoService()

    result = await service.generate(
        VideoGenerationRequest(
            description="A bar chart animating Q1 through Q4 revenue growth with green bars",
            template="data_visualization",
            duration_seconds=7,
        )
    )

    print(f"Status: {result.status}")
    print(f"Video: {result.video_path}")
    print(f"Time: {result.total_time_ms:.0f}ms")

asyncio.run(main())
```

### Option C: Render a built-in template directly

```bash
cd frontend/remotion

# Render the CoherenceDashboard template
npx remotion render src/index.ts CoherenceDashboard output/coherence.mp4

# Render the TitleCard template
npx remotion render src/index.ts TitleCard output/title.mp4

# Render the MetricsAnimation template
npx remotion render src/index.ts MetricsAnimation output/metrics.mp4

# Render the TextKinetic template
npx remotion render src/index.ts TextKinetic output/kinetic.mp4
```

---

## 6. API Reference

### POST /video/generate

Generate a video from a natural language description.

**Request Body:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `description` | string | *required* | Natural language description of the video |
| `template` | string | `null` | Template category (see [Templates](#7-built-in-templates)) |
| `style` | object | `null` | Style overrides: `background_color`, `primary_color`, `font_family` |
| `duration_seconds` | int | `5` | Video duration (1-30 seconds) |
| `resolution` | object | `null` | `{ "width": 1920, "height": 1080 }` |
| `fps` | int | `30` | Frames per second |
| `output_format` | string | `"mp4"` | Output format: `mp4`, `gif`, `webm` |
| `render` | bool | `true` | Whether to render or just return TSX code |

**Example Request:**

```json
{
  "description": "An animated pie chart showing market share: Symbol-U 45%, Competitor A 30%, Competitor B 25%. Each slice should animate in with a spring bounce effect.",
  "template": "data_visualization",
  "duration_seconds": 6,
  "style": {
    "background_color": "#0a0a1a",
    "primary_color": "#8b5cf6"
  }
}
```

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `video_id` | string | Unique identifier (8-char) |
| `status` | string | `"success"`, `"tsx_generated"`, or `"render_failed"` |
| `tsx_code` | string | The full generated TSX source code |
| `video_path` | string or null | File path to rendered MP4 |
| `generation_time_ms` | float | Time for LLM to generate TSX |
| `render_time_ms` | float | Time for Remotion to render |
| `total_time_ms` | float | Total pipeline time |
| `error` | string or null | Error message if render failed |
| `metadata` | object | Warnings, composition path, config |

**Status Codes:**

| Status | Meaning |
|--------|---------|
| `success` | TSX generated AND rendered to MP4 |
| `tsx_generated` | TSX generated but rendering unavailable (Remotion not installed, or Node.js not found) |
| `render_failed` | TSX generated but rendering failed (check `error` field) |

---

### POST /video/coherence

Generate a coherence metrics visualization video.

**Request Body:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `session_id` | string | `null` | Fetch metrics from this session |
| `metrics` | object | `null` | Explicit metrics dict (overrides session) |

If neither is provided, demo metrics are used.

**Example:**

```json
{
  "metrics": {
    "coherence_quality": 0.87,
    "drift_fusion": 0.72,
    "entropy_volatility": 0.45,
    "schema_stability": 0.91,
    "identity_harmonics": 0.68,
    "ucf_score": 0.83,
    "insight_depth": 0.56
  }
}
```

---

### GET /video/templates

Returns available template categories.

**Response:**

```json
{
  "templates": {
    "title_card": "A professional title card with animated text entrance",
    "data_visualization": "An animated chart/graph showing data with smooth transitions",
    "logo_reveal": "A logo reveal animation with particle effects or geometric shapes",
    "text_animation": "Kinetic typography with words appearing in sequence",
    "countdown": "An animated countdown timer with visual effects",
    "metrics_dashboard": "An animated dashboard showing metrics/KPIs with progress bars",
    "explainer": "An animated explainer with icons and text appearing in sequence",
    "coherence_viz": "Symbol-U coherence metrics visualization with animated gauges"
  }
}
```

---

## 7. Built-in Templates

Four pre-built Remotion compositions are included in `frontend/remotion/src/templates/`. These can be rendered directly without the LLM.

### CoherenceDashboard

**File:** `frontend/remotion/src/templates/CoherenceDashboard.tsx`
**Duration:** 6 seconds (180 frames)
**Description:** Animated circular gauges showing 7 Symbol-U coherence metrics with staggered entrance, color-coded values (green > 0.7, yellow 0.4-0.7, red < 0.4), particle background, and animated progress bar.

**Render command:**
```bash
npx remotion render src/index.ts CoherenceDashboard coherence.mp4
```

### TitleCard

**File:** `frontend/remotion/src/templates/TitleCard.tsx`
**Duration:** 5 seconds (150 frames)
**Description:** Professional title card with spring-bounced "Symbol-U" text entrance, rotating logo diamond, subtitle fade-in with letter spacing, gradient underline, and bottom tagline. Includes radial glow background effect.

**Render command:**
```bash
npx remotion render src/index.ts TitleCard title.mp4
```

### MetricsAnimation

**File:** `frontend/remotion/src/templates/MetricsAnimation.tsx`
**Duration:** 7 seconds (210 frames)
**Description:** Animated KPI dashboard with 5 metrics (Pipeline Phases, Test Pass Rate, Coherence Score, Latency, Ontological Dims). Each metric slides in from the left with spring physics, progress bars fill with glow effects, and numbers count up in real-time.

**Render command:**
```bash
npx remotion render src/index.ts MetricsAnimation metrics.mp4
```

### TextKinetic

**File:** `frontend/remotion/src/templates/TextKinetic.tsx`
**Duration:** 6 seconds (180 frames)
**Description:** Kinetic typography animation building the phrase "Making AI Trustworthy for Enterprise." Words appear one-by-one with spring scale+slide physics. Key words are highlighted in purple with glow effects. Includes radial gradient pulse and animated accent line.

**Render command:**
```bash
npx remotion render src/index.ts TextKinetic kinetic.mp4
```

---

## 8. Using the Frontend UI

The `VideoGenerator` React component provides a graphical interface for video generation.

### Location

```
frontend/src/components/video/VideoGenerator.tsx
```

### Features

1. **Description input** -- textarea where you describe the video in natural language
2. **Template selector** -- clickable chips for 8 template categories (optional, helps guide the LLM)
3. **Duration slider** -- 2-15 seconds range
4. **Generate button** -- triggers the API call
5. **Status banner** -- shows success/warning/error with timing stats
6. **Code preview** -- toggle to view the generated TSX source code
7. **Download link** -- link to download the rendered MP4 (when available)

### Adding to your app

Import and use the component in any page:

```tsx
import { VideoGenerator } from '../components/video/VideoGenerator';

const MyPage: React.FC = () => {
  return (
    <div>
      <VideoGenerator />
    </div>
  );
};
```

### Status indicators

| Status | Color | Meaning |
|--------|-------|---------|
| Green | `"success"` | Video rendered and ready to download |
| Yellow | `"tsx_generated"` | TSX code generated, but Remotion rendering not available |
| Red | `"render_failed"` | Something went wrong during rendering |

Even in the yellow state, you can copy the generated TSX code and render it manually using the Remotion CLI.

---

## 9. Python SDK Usage

### Basic generation

```python
import asyncio
from symbolu.service.video_gen import RemotionVideoService
from symbolu.service.video_gen.service import VideoGenerationRequest

async def generate_title():
    service = RemotionVideoService()

    result = await service.generate(
        VideoGenerationRequest(
            description="A futuristic loading animation with pulsing circles and a progress bar",
            template="countdown",
            duration_seconds=5,
            fps=30,
            output_format="mp4",
        )
    )

    print(f"Video ID: {result.video_id}")
    print(f"Status: {result.status}")
    print(f"TSX code length: {len(result.tsx_code)} chars")
    if result.video_path:
        print(f"Saved to: {result.video_path}")
    if result.error:
        print(f"Error: {result.error}")

asyncio.run(generate_title())
```

### Coherence visualization

```python
async def generate_coherence():
    service = RemotionVideoService()

    result = await service.generate_coherence_video(
        metrics={
            "coherence_quality": 0.92,
            "drift_fusion": 0.78,
            "entropy_volatility": 0.35,
            "schema_stability": 0.95,
            "identity_harmonics": 0.71,
            "ucf_score": 0.88,
            "insight_depth": 0.62,
        },
        session_id="sess_abc123",
    )

    print(f"Coherence video: {result.video_path}")

asyncio.run(generate_coherence())
```

### Custom style overrides

```python
async def generate_styled():
    service = RemotionVideoService()

    result = await service.generate(
        VideoGenerationRequest(
            description="Quarterly revenue comparison with animated bars",
            template="data_visualization",
            style={
                "background_color": "#1a1a2e",
                "primary_color": "#e94560",
                "font_family": "Georgia, serif",
            },
            duration_seconds=8,
            resolution={"width": 1920, "height": 1080},
        )
    )

asyncio.run(generate_styled())
```

### Specifying an LLM provider

```python
# Use Google Gemini instead of the default Anthropic
service = RemotionVideoService(provider="google")
```

### Getting just the TSX code (no render)

If you only want the generated code without rendering:

```python
from symbolu.service.video_gen.prompt_builder import RemotionPromptBuilder

builder = RemotionPromptBuilder()

# Build the prompt
prompt = builder.build_prompt(
    description="A spinning globe with data points",
    template="data_visualization",
    duration_seconds=10,
)

# Use the prompt with any LLM
print(builder.system_prompt)  # System prompt with Remotion API docs
print(prompt)                  # User prompt with the description
```

---

## 10. How the LLM Generates Video Code

### The system prompt

The Phase Quad LLM receives a detailed system prompt (`RemotionPromptBuilder.system_prompt`) that teaches it:

1. **Remotion API** -- which imports to use (`useCurrentFrame`, `interpolate`, `spring`, `Sequence`, `AbsoluteFill`)
2. **Rules** -- output only TSX, single file, single default export, inline styles only
3. **Animation patterns** -- fade in, slide in, spring bounce, staggered sequences
4. **Complete example** -- a working reference composition
5. **Defaults** -- 30fps, 1920x1080, dark background (#0f0f23), system fonts

### Animation primitives the LLM uses

| Primitive | Remotion API | What it does |
|-----------|-------------|--------------|
| Frame timing | `useCurrentFrame()` | Returns current frame number (0, 1, 2, ...) |
| Value interpolation | `interpolate(frame, [0, 30], [0, 1])` | Maps frame ranges to value ranges (e.g., opacity 0 to 1 over 30 frames) |
| Spring physics | `spring({ frame, fps, config })` | Natural spring animation (configurable damping, stiffness) |
| Sequencing | `<Sequence from={30}>` | Delays a child component by N frames |
| Full-screen container | `<AbsoluteFill>` | Full-width, full-height positioned container |
| Video config | `useVideoConfig()` | Gets fps, width, height from composition |

### Code validation

Before rendering, the generated TSX passes through `_validate_tsx()` which checks:

- Has `export default` (required for Remotion to import it)
- Uses `useCurrentFrame` (ensures the video is animated, not static)
- Has Remotion imports
- Does **not** contain dangerous patterns: `eval()`, `Function()`, `require()`, `process.`, `fs.`, `__dirname`

Warnings are logged but do not block rendering.

### Temperature setting

The LLM is called with `temperature=0.3` (lower than the default 1.0) to produce more consistent, compilable code. This means:

- Less creative variation between runs
- Higher probability of syntactically correct TSX
- More predictable animation patterns

---

## 11. Remotion Studio (Preview & Development)

Remotion includes a visual studio for previewing and developing compositions in the browser.

### Launch the studio

```bash
cd frontend/remotion
npm run dev
# or: npx remotion studio src/index.ts
```

This opens a browser window where you can:

- **Preview all compositions** -- see them play in real-time
- **Scrub the timeline** -- drag to any frame
- **Adjust props** -- modify parameters on the fly
- **Hot-reload** -- edit TSX files and see changes instantly
- **Inspect** -- view each frame's render tree

### Useful for

- Previewing built-in templates before rendering
- Editing LLM-generated compositions before final render
- Developing new template compositions
- Debugging animation timing

---

## 12. Command-Line Rendering

### Render a specific composition

```bash
cd frontend/remotion

# Basic render
npx remotion render src/index.ts CoherenceDashboard output.mp4

# With custom frame count and FPS
npx remotion render src/index.ts TitleCard title.mp4 --frames 300 --fps 60

# Custom resolution
npx remotion render src/index.ts MetricsAnimation metrics.mp4 --width 3840 --height 2160

# Render as GIF
npx remotion render src/index.ts TextKinetic kinetic.gif --image-format png
```

### Render an LLM-generated composition

After the API generates a composition, it's saved to `frontend/remotion/src/compositions/Generated_{video_id}.tsx`. To re-render it:

```bash
cd frontend/remotion
npx remotion render src/index.ts Generated_a1b2c3d4 re-rendered.mp4
```

### Performance notes

| Video Length | Typical Render Time | Notes |
|-------------|-------------------|-------|
| 3 seconds | 5-15 seconds | Fast, simple animations |
| 5 seconds | 10-30 seconds | Standard compositions |
| 10 seconds | 20-60 seconds | Complex animations |
| 15+ seconds | 60+ seconds | Consider splitting into segments |

Rendering happens on CPU. Times are approximate for an average machine.

---

## 13. Customization

### Adding a new built-in template

1. Create a new component in `frontend/remotion/src/templates/`:

```tsx
// frontend/remotion/src/templates/MyTemplate.tsx
import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate, AbsoluteFill } from "remotion";

export const MyTemplate: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const opacity = interpolate(frame, [0, 30], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: "#0f0f23" }}>
      <div style={{ opacity, color: "white", fontSize: 48 }}>
        My Custom Template
      </div>
    </AbsoluteFill>
  );
};
```

2. Register it in `frontend/remotion/src/Root.tsx`:

```tsx
import { MyTemplate } from "./templates/MyTemplate";

// Inside RemotionRoot:
<Composition
  id="MyTemplate"
  component={MyTemplate}
  durationInFrames={150}
  fps={30}
  width={1920}
  height={1080}
/>
```

### Adding a new template category for the LLM

Add it to `VIDEO_TEMPLATES` in `symbolu/service/video_gen/prompt_builder.py`:

```python
VIDEO_TEMPLATES = {
    # ... existing templates ...
    "social_media_post": "An animated social media post card with engagement metrics",
}
```

The LLM will use this description as context when the template is selected.

### Customizing the system prompt

Edit `REMOTION_SYSTEM_PROMPT` in `symbolu/service/video_gen/prompt_builder.py` to:

- Add new animation patterns
- Change default styling (colors, fonts, background)
- Add domain-specific guidelines
- Include additional Remotion APIs

### Changing the output directory

By default, rendered videos are saved to `artifacts/videos/`. To change:

```python
service = RemotionVideoService(
    output_dir=Path("/my/custom/output/directory")
)
```

### Changing the LLM model tier

The service uses `tier="power_user"` (Sonnet/Pro) by default. To use a cheaper/faster model:

Edit `symbolu/service/video_gen/service.py`, in `_generate_tsx()`:

```python
response = await service.chat(
    message=user_prompt,
    tier="consumer",  # Uses Haiku/Flash (faster, cheaper)
    ...
)
```

---

## 14. Two Video Pipelines Compared

Symbol-U now has two video generation capabilities. Here's when to use each:

### Use RemotionVideoService (this module) when you need:

- Motion graphics (titles, intros, outros)
- Data visualizations (animated charts, graphs, dashboards)
- Kinetic typography (text animations)
- UI/product mockup animations
- Symbol-U metric visualizations (coherence, ontological, entropy)
- Explainer animations with icons and text
- Countdown timers, progress indicators
- Anything that can be described as "animated graphics"

### Use PhaseQuadVideoPipeline when you need:

- Photorealistic video from text prompts ("a cat playing in a garden")
- Artistic/creative video generation
- Style transfer or visual effects that require pixel-level generation
- Video that looks like real camera footage

### Using both together

You can combine both pipelines. For example:

1. Generate a product demo video with `PhaseQuadVideoPipeline` (realistic footage)
2. Generate an animated title card and metrics overlay with `RemotionVideoService`
3. Composite them together using video editing tools

---

## 15. Troubleshooting

### "npx not found"

**Problem:** Node.js is not installed.
**Solution:** Install Node.js 18+ from https://nodejs.org

### "Remotion project not initialized"

**Problem:** Dependencies not installed.
**Solution:**
```bash
cd frontend/remotion
npm install
```

### "ChatService unavailable, using fallback template"

**Problem:** No LLM API key configured.
**Solution:** Set `ANTHROPIC_API_KEY` or `GOOGLE_API_KEY` environment variable. The service still works without it, but generates a basic template instead of AI-customized code.

### "Render timed out after 120 seconds"

**Problem:** Video is too long or complex for the 120-second render timeout.
**Solution:** Reduce `duration_seconds` or simplify the description. You can also increase the timeout in `service.py` by changing the `timeout=120` parameter in `subprocess.run()`.

### "Missing 'export default'" warning

**Problem:** The LLM generated code without a default export.
**Solution:** This is a warning, not an error. The code may still work if it uses a named export. If rendering fails, try regenerating with a simpler description.

### Status is "tsx_generated" but no video file

**Problem:** TSX was generated successfully but Remotion couldn't render it.
**Solution:** This typically means Remotion isn't installed (`npm install` not run) or Node.js isn't available. The TSX code in the response is still valid -- you can copy it into the Remotion project and render manually.

### Generated video has no animation (static frame)

**Problem:** The LLM generated code that doesn't use `useCurrentFrame()`.
**Solution:** Regenerate with a more explicit description mentioning animation (e.g., "animated," "fade in," "slide in," "spring bounce").

### Render produces a black screen

**Problem:** The component renders but nothing is visible.
**Solution:** Check the generated TSX code for:
- Missing or transparent background color
- Elements positioned off-screen
- Zero opacity that never changes
- Conditional rendering that evaluates to false

---

## 16. File Reference

```
symbolu/
  service/
    video_gen/
      __init__.py                    # Package exports
      service.py                     # RemotionVideoService (main orchestrator)
      prompt_builder.py              # RemotionPromptBuilder (LLM prompt construction)
    api_server.py                    # API endpoints (/video/generate, /video/coherence, /video/templates)
    request_models.py                # Pydantic models (VideoGenerateRequest, VideoGenerateResponse, etc.)

frontend/
  remotion/
    package.json                     # Remotion 4.x dependencies
    tsconfig.json                    # TypeScript configuration
    src/
      index.ts                       # Remotion entry point (registerRoot)
      Root.tsx                       # Composition registry (all templates)
      templates/
        CoherenceDashboard.tsx        # 7-metric coherence gauge animation
        TitleCard.tsx                 # Spring-physics title card
        MetricsAnimation.tsx          # KPI dashboard with counting numbers
        TextKinetic.tsx               # Kinetic typography animation
      compositions/                   # LLM-generated compositions (auto-created)
        Generated_{video_id}.tsx      # Each generated video's TSX code

  src/
    api/
      client.ts                      # API client (generateVideo, generateCoherenceVideo, getVideoTemplates)
    components/
      video/
        VideoGenerator.tsx            # Frontend UI component

artifacts/
  videos/                            # Rendered MP4 output directory
    {video_id}.mp4                   # Rendered video files
```

---

## Summary

The Symbol-U AI Video Generation pipeline bridges the Phase Quad LLM's text capabilities with Remotion's deterministic video rendering. Instead of requiring trained diffusion models and GPU hardware, you describe a video in plain English and get a professionally animated MP4 in seconds. The generated TSX code is fully editable, the output is 100% deterministic, and the system works alongside the existing neural video pipeline for complete multi-modal coverage.
