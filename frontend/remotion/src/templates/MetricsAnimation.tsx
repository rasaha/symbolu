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
 * Animated metrics/KPI visualization with progress bars and counters.
 *
 * Shows key performance indicators with:
 * - Counting number animations
 * - Animated progress bars
 * - Staggered entrance effects
 */

interface MetricRowProps {
  label: string;
  value: number;
  maxValue: number;
  unit: string;
  color: string;
  delay: number;
}

const MetricRow: React.FC<MetricRowProps> = ({
  label,
  value,
  maxValue,
  unit,
  color,
  delay,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const adjustedFrame = Math.max(0, frame - delay);

  const slideIn = spring({
    frame: adjustedFrame,
    fps,
    config: { damping: 14, stiffness: 120 },
  });

  const opacity = interpolate(adjustedFrame, [0, 10], [0, 1], {
    extrapolateRight: "clamp",
  });

  const barProgress = interpolate(adjustedFrame, [10, 50], [0, value / maxValue], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const countUp = interpolate(adjustedFrame, [10, 50], [0, value], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const translateX = interpolate(slideIn, [0, 1], [-60, 0]);

  return (
    <div
      style={{
        opacity,
        transform: `translateX(${translateX}px)`,
        marginBottom: 30,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginBottom: 8,
        }}
      >
        <span style={{ fontSize: 20, color: "#e2e8f0", fontWeight: 500 }}>
          {label}
        </span>
        <span style={{ fontSize: 24, color, fontWeight: 700 }}>
          {Math.round(countUp).toLocaleString()}
          {unit}
        </span>
      </div>
      <div
        style={{
          height: 12,
          backgroundColor: "#1e1e3f",
          borderRadius: 6,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${barProgress * 100}%`,
            height: "100%",
            backgroundColor: color,
            borderRadius: 6,
            boxShadow: `0 0 12px ${color}60`,
          }}
        />
      </div>
    </div>
  );
};

const METRICS_DATA = [
  { label: "Pipeline Phases", value: 48, maxValue: 50, unit: "", color: "#6366f1" },
  { label: "Test Pass Rate", value: 99.7, maxValue: 100, unit: "%", color: "#22c55e" },
  { label: "Coherence Score", value: 87, maxValue: 100, unit: "%", color: "#8b5cf6" },
  { label: "Latency (STL)", value: 0.13, maxValue: 1, unit: "ms", color: "#06b6d4" },
  { label: "Ontological Dims", value: 12, maxValue: 15, unit: "", color: "#f59e0b" },
];

export const MetricsAnimation: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleOpacity = interpolate(frame, [0, 20], [0, 1], {
    extrapolateRight: "clamp",
  });

  const titleScale = spring({
    frame,
    fps,
    config: { damping: 12, stiffness: 180 },
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#0f0f23",
        fontFamily: "Inter, Helvetica Neue, Arial, sans-serif",
        padding: "80px 200px",
      }}
    >
      {/* Title */}
      <Sequence from={0}>
        <div
          style={{
            opacity: titleOpacity,
            transform: `scale(${titleScale})`,
            marginBottom: 60,
          }}
        >
          <div
            style={{
              fontSize: 44,
              fontWeight: 800,
              color: "white",
              letterSpacing: -1,
            }}
          >
            Performance Metrics
          </div>
          <div
            style={{
              fontSize: 18,
              color: "#6366f1",
              marginTop: 8,
              fontWeight: 400,
            }}
          >
            Symbol-U Engine Dashboard
          </div>
        </div>
      </Sequence>

      {/* Metrics */}
      {METRICS_DATA.map((metric, i) => (
        <Sequence key={metric.label} from={15 + i * 12}>
          <MetricRow
            label={metric.label}
            value={metric.value}
            maxValue={metric.maxValue}
            unit={metric.unit}
            color={metric.color}
            delay={15 + i * 12}
          />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
