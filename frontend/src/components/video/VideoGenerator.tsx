import React, { useState, useCallback } from 'react';

/**
 * VideoGenerator: AI-powered video generation UI component.
 *
 * Allows users to describe a video in natural language, select a template,
 * and generate motion graphics via the Phase Quad LLM + Remotion pipeline.
 *
 * Flow:
 *   1. User enters description + selects template
 *   2. POST /video/generate sends to backend
 *   3. Phase Quad LLM generates TSX code
 *   4. Remotion renders to MP4 (if available)
 *   5. User sees TSX code preview + download link
 */

interface VideoTemplate {
  id: string;
  label: string;
  description: string;
}

const TEMPLATES: VideoTemplate[] = [
  { id: 'title_card', label: 'Title Card', description: 'Professional title with animated entrance' },
  { id: 'data_visualization', label: 'Data Viz', description: 'Animated chart or graph' },
  { id: 'logo_reveal', label: 'Logo Reveal', description: 'Logo animation with effects' },
  { id: 'text_animation', label: 'Kinetic Text', description: 'Words appearing in sequence' },
  { id: 'metrics_dashboard', label: 'Metrics Dashboard', description: 'Animated KPIs and progress bars' },
  { id: 'coherence_viz', label: 'Coherence Viz', description: 'Symbol-U coherence metrics' },
  { id: 'explainer', label: 'Explainer', description: 'Icons and text explainer' },
  { id: 'countdown', label: 'Countdown', description: 'Animated countdown timer' },
];

interface GenerationResult {
  video_id: string;
  status: string;
  tsx_code: string;
  video_path: string | null;
  generation_time_ms: number;
  render_time_ms: number;
  total_time_ms: number;
  error: string | null;
}

const API_BASE = import.meta.env.VITE_API_URL || '/api';

export const VideoGenerator: React.FC = () => {
  const [description, setDescription] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [duration, setDuration] = useState(5);
  const [isGenerating, setIsGenerating] = useState(false);
  const [result, setResult] = useState<GenerationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showCode, setShowCode] = useState(false);

  const handleGenerate = useCallback(async () => {
    if (!description.trim()) return;

    setIsGenerating(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch(`${API_BASE}/video/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          description: description.trim(),
          template: selectedTemplate,
          duration_seconds: duration,
          render: true,
        }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || `Request failed: ${response.status}`);
      }

      const data: GenerationResult = await response.json();
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Generation failed');
    } finally {
      setIsGenerating(false);
    }
  }, [description, selectedTemplate, duration]);

  return (
    <div style={{
      maxWidth: 800,
      margin: '0 auto',
      padding: 24,
      fontFamily: 'Inter, Helvetica Neue, Arial, sans-serif',
    }}>
      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <h2 style={{
          fontSize: 28,
          fontWeight: 700,
          color: '#e2e8f0',
          margin: 0,
        }}>
          AI Video Generator
        </h2>
        <p style={{
          fontSize: 14,
          color: '#94a3b8',
          marginTop: 8,
        }}>
          Describe a video in natural language. The Phase Quad LLM generates
          Remotion TSX code that renders to MP4 motion graphics.
        </p>
      </div>

      {/* Description input */}
      <div style={{ marginBottom: 20 }}>
        <label style={{
          display: 'block',
          fontSize: 13,
          fontWeight: 600,
          color: '#94a3b8',
          marginBottom: 6,
          textTransform: 'uppercase',
          letterSpacing: 1,
        }}>
          Video Description
        </label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Describe the video you want to create... e.g. 'An animated title card for Symbol-U with glowing purple text that scales in with spring physics, followed by a tagline fading in below'"
          rows={4}
          style={{
            width: '100%',
            padding: '12px 16px',
            backgroundColor: '#1e1e3f',
            border: '1px solid #2d2d5f',
            borderRadius: 8,
            color: '#e2e8f0',
            fontSize: 15,
            resize: 'vertical',
            outline: 'none',
            fontFamily: 'inherit',
            boxSizing: 'border-box',
          }}
        />
      </div>

      {/* Template selector */}
      <div style={{ marginBottom: 20 }}>
        <label style={{
          display: 'block',
          fontSize: 13,
          fontWeight: 600,
          color: '#94a3b8',
          marginBottom: 8,
          textTransform: 'uppercase',
          letterSpacing: 1,
        }}>
          Template (optional)
        </label>
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 8,
        }}>
          {TEMPLATES.map((t) => (
            <button
              key={t.id}
              onClick={() => setSelectedTemplate(
                selectedTemplate === t.id ? null : t.id
              )}
              title={t.description}
              style={{
                padding: '8px 14px',
                borderRadius: 6,
                border: selectedTemplate === t.id
                  ? '1px solid #6366f1'
                  : '1px solid #2d2d5f',
                backgroundColor: selectedTemplate === t.id
                  ? '#6366f120'
                  : '#1e1e3f',
                color: selectedTemplate === t.id ? '#a78bfa' : '#94a3b8',
                fontSize: 13,
                cursor: 'pointer',
                transition: 'all 0.15s',
                fontFamily: 'inherit',
              }}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Duration */}
      <div style={{ marginBottom: 24 }}>
        <label style={{
          display: 'block',
          fontSize: 13,
          fontWeight: 600,
          color: '#94a3b8',
          marginBottom: 6,
          textTransform: 'uppercase',
          letterSpacing: 1,
        }}>
          Duration: {duration}s
        </label>
        <input
          type="range"
          min={2}
          max={15}
          value={duration}
          onChange={(e) => setDuration(Number(e.target.value))}
          style={{ width: 200 }}
        />
      </div>

      {/* Generate button */}
      <button
        onClick={handleGenerate}
        disabled={isGenerating || !description.trim()}
        style={{
          padding: '12px 32px',
          borderRadius: 8,
          border: 'none',
          backgroundColor: isGenerating ? '#4b5563' : '#6366f1',
          color: 'white',
          fontSize: 15,
          fontWeight: 600,
          cursor: isGenerating ? 'not-allowed' : 'pointer',
          transition: 'background-color 0.15s',
          fontFamily: 'inherit',
        }}
      >
        {isGenerating ? 'Generating...' : 'Generate Video'}
      </button>

      {/* Error */}
      {error && (
        <div style={{
          marginTop: 16,
          padding: '12px 16px',
          backgroundColor: '#7f1d1d20',
          border: '1px solid #7f1d1d',
          borderRadius: 8,
          color: '#fca5a5',
          fontSize: 14,
        }}>
          {error}
        </div>
      )}

      {/* Result */}
      {result && (
        <div style={{ marginTop: 24 }}>
          {/* Status banner */}
          <div style={{
            padding: '12px 16px',
            backgroundColor: result.status === 'success'
              ? '#14532d20'
              : result.status === 'tsx_generated'
                ? '#713f1220'
                : '#7f1d1d20',
            border: `1px solid ${
              result.status === 'success'
                ? '#14532d'
                : result.status === 'tsx_generated'
                  ? '#713f12'
                  : '#7f1d1d'
            }`,
            borderRadius: 8,
            marginBottom: 16,
          }}>
            <div style={{
              fontSize: 15,
              fontWeight: 600,
              color: result.status === 'success'
                ? '#86efac'
                : result.status === 'tsx_generated'
                  ? '#fbbf24'
                  : '#fca5a5',
            }}>
              {result.status === 'success'
                ? 'Video rendered successfully'
                : result.status === 'tsx_generated'
                  ? 'TSX code generated (Remotion not available for rendering)'
                  : 'Generation failed'}
            </div>
            <div style={{
              fontSize: 12,
              color: '#94a3b8',
              marginTop: 4,
            }}>
              ID: {result.video_id} | TSX: {result.generation_time_ms.toFixed(0)}ms
              {result.render_time_ms > 0 && ` | Render: ${result.render_time_ms.toFixed(0)}ms`}
              {' '}| Total: {result.total_time_ms.toFixed(0)}ms
            </div>
            {result.error && (
              <div style={{ fontSize: 12, color: '#fca5a5', marginTop: 4 }}>
                {result.error}
              </div>
            )}
          </div>

          {/* Video download */}
          {result.video_path && (
            <div style={{ marginBottom: 16 }}>
              <a
                href={result.video_path}
                download
                style={{
                  color: '#6366f1',
                  fontSize: 14,
                  textDecoration: 'underline',
                }}
              >
                Download {result.video_path.split('/').pop()}
              </a>
            </div>
          )}

          {/* TSX code toggle */}
          <button
            onClick={() => setShowCode(!showCode)}
            style={{
              padding: '8px 16px',
              borderRadius: 6,
              border: '1px solid #2d2d5f',
              backgroundColor: '#1e1e3f',
              color: '#94a3b8',
              fontSize: 13,
              cursor: 'pointer',
              fontFamily: 'inherit',
            }}
          >
            {showCode ? 'Hide' : 'Show'} Generated TSX Code
          </button>

          {showCode && (
            <pre style={{
              marginTop: 12,
              padding: 16,
              backgroundColor: '#0a0a1a',
              border: '1px solid #1e1e3f',
              borderRadius: 8,
              color: '#e2e8f0',
              fontSize: 12,
              lineHeight: 1.6,
              overflow: 'auto',
              maxHeight: 400,
              fontFamily: 'JetBrains Mono, Fira Code, monospace',
            }}>
              {result.tsx_code}
            </pre>
          )}
        </div>
      )}
    </div>
  );
};
