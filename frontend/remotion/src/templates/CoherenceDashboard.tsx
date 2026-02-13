import React from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  AbsoluteFill,
  Sequence,
} from "remotion";

/**
 * Animated coherence dashboard visualization.
 *
 * Shows Symbol-U's 7 coherence metrics as animated circular gauges
 * with staggered entrance animations and color-coded values.
 */

interface MetricGaugeProps {
  label: string;
  value: number;
  delay: number;
  x: number;
  y: number;
}

const MetricGauge: React.FC<MetricGaugeProps> = ({ label, value, delay, x, y }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const adjustedFrame = Math.max(0, frame - delay);
  const progress = spring({
    frame: adjustedFrame,
    fps,
    config: { damping: 15, stiffness: 80 },
  });

  const opacity = interpolate(adjustedFrame, [0, 15], [0, 1], {
    extrapolateRight: "clamp",
  });

  const arcProgress = progress * value;
  const radius = 60;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference * (1 - arcProgress);

  const color =
    value > 0.7 ? "#22c55e" : value > 0.4 ? "#eab308" : "#ef4444";

  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        opacity,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
      }}
    >
      <svg width={140} height={140} viewBox="0 0 140 140">
        <circle
          cx={70}
          cy={70}
          r={radius}
          fill="none"
          stroke="#1e1e3f"
          strokeWidth={8}
        />
        <circle
          cx={70}
          cy={70}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={8}
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          transform="rotate(-90 70 70)"
          style={{ filter: `drop-shadow(0 0 8px ${color}40)` }}
        />
        <text
          x={70}
          y={70}
          textAnchor="middle"
          dominantBaseline="central"
          fill="white"
          fontSize={24}
          fontWeight="bold"
          fontFamily="Inter, Helvetica Neue, Arial, sans-serif"
        >
          {(arcProgress * 100).toFixed(0)}%
        </text>
      </svg>
      <div
        style={{
          marginTop: 8,
          fontSize: 14,
          color: "#a0a0c0",
          fontFamily: "Inter, Helvetica Neue, Arial, sans-serif",
          textAlign: "center",
          maxWidth: 120,
        }}
      >
        {label}
      </div>
    </div>
  );
};

const METRICS = [
  { label: "Coherence Quality", value: 0.87 },
  { label: "Drift Fusion", value: 0.72 },
  { label: "Entropy Volatility", value: 0.45 },
  { label: "Schema Stability", value: 0.91 },
  { label: "Identity Harmonics", value: 0.68 },
  { label: "UCF Score", value: 0.83 },
  { label: "Insight Depth", value: 0.56 },
];

export const CoherenceDashboard: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleOpacity = interpolate(frame, [0, 20], [0, 1], {
    extrapolateRight: "clamp",
  });
  const titleY = spring({
    frame,
    fps,
    config: { damping: 12, stiffness: 200 },
  });

  // Grid layout for 7 metrics (4 + 3)
  const positions = [
    { x: 180, y: 200 },
    { x: 540, y: 200 },
    { x: 900, y: 200 },
    { x: 1260, y: 200 },
    { x: 360, y: 480 },
    { x: 720, y: 480 },
    { x: 1080, y: 480 },
  ];

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#0f0f23",
        fontFamily: "Inter, Helvetica Neue, Arial, sans-serif",
      }}
    >
      {/* Background dots */}
      {Array.from({ length: 30 }).map((_, i) => {
        const dotX = (i * 137.5) % 1920;
        const dotY = (i * 89.3) % 1080;
        const dotOpacity = interpolate(
          frame,
          [i * 2, i * 2 + 30],
          [0, 0.15],
          { extrapolateRight: "clamp" }
        );
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: dotX,
              top: dotY,
              width: 4,
              height: 4,
              borderRadius: "50%",
              backgroundColor: "#6366f1",
              opacity: dotOpacity,
            }}
          />
        );
      })}

      {/* Title */}
      <Sequence from={0}>
        <div
          style={{
            position: "absolute",
            top: 60,
            left: 0,
            right: 0,
            textAlign: "center",
            opacity: titleOpacity,
            transform: `translateY(${interpolate(titleY, [0, 1], [30, 0])}px)`,
          }}
        >
          <div
            style={{
              fontSize: 48,
              fontWeight: "bold",
              color: "white",
              letterSpacing: -1,
            }}
          >
            Symbol-U Coherence Report
          </div>
          <div
            style={{
              fontSize: 18,
              color: "#6366f1",
              marginTop: 8,
            }}
          >
            Real-time 7-Metric Coherence Analysis
          </div>
        </div>
      </Sequence>

      {/* Metric gauges */}
      {METRICS.map((metric, i) => (
        <Sequence key={metric.label} from={20 + i * 8}>
          <MetricGauge
            label={metric.label}
            value={metric.value}
            delay={20 + i * 8}
            x={positions[i].x}
            y={positions[i].y}
          />
        </Sequence>
      ))}

      {/* Bottom bar */}
      <Sequence from={90}>
        <div
          style={{
            position: "absolute",
            bottom: 40,
            left: 180,
            right: 180,
          }}
        >
          <div
            style={{
              height: 4,
              backgroundColor: "#1e1e3f",
              borderRadius: 2,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${interpolate(frame - 90, [0, 60], [0, 100], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}%`,
                height: "100%",
                background:
                  "linear-gradient(90deg, #6366f1, #8b5cf6, #a78bfa)",
                borderRadius: 2,
              }}
            />
          </div>
        </div>
      </Sequence>
    </AbsoluteFill>
  );
};
