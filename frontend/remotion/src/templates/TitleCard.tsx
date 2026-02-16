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
 * Professional title card animation with spring physics.
 *
 * Features:
 * - Main title with spring-bounced entrance
 * - Subtitle fade-in
 * - Animated underline
 * - Particle background
 */
export const TitleCard: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Title animation
  const titleScale = spring({
    frame,
    fps,
    config: { damping: 10, stiffness: 150, mass: 0.8 },
  });
  const titleOpacity = interpolate(frame, [0, 15], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Subtitle
  const subOpacity = interpolate(frame, [25, 45], [0, 1], {
    extrapolateRight: "clamp",
  });
  const subY = interpolate(frame, [25, 45], [20, 0], {
    extrapolateRight: "clamp",
  });

  // Underline
  const lineWidth = interpolate(frame, [40, 80], [0, 400], {
    extrapolateRight: "clamp",
  });

  // Logo mark
  const logoRotation = interpolate(frame, [0, 60], [0, 360], {
    extrapolateRight: "clamp",
  });
  const logoScale = spring({
    frame: Math.max(0, frame - 5),
    fps,
    config: { damping: 8, stiffness: 120 },
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#0f0f23",
        justifyContent: "center",
        alignItems: "center",
        fontFamily: "Inter, Helvetica Neue, Arial, sans-serif",
      }}
    >
      {/* Radial glow */}
      <div
        style={{
          position: "absolute",
          width: 600,
          height: 600,
          borderRadius: "50%",
          background:
            "radial-gradient(circle, rgba(99,102,241,0.15) 0%, transparent 70%)",
          opacity: interpolate(frame, [0, 30], [0, 1], {
            extrapolateRight: "clamp",
          }),
        }}
      />

      {/* Logo diamond */}
      <Sequence from={0}>
        <div
          style={{
            transform: `scale(${logoScale}) rotate(${logoRotation}deg)`,
            width: 40,
            height: 40,
            backgroundColor: "#6366f1",
            marginBottom: 30,
            borderRadius: 4,
            boxShadow: "0 0 30px rgba(99,102,241,0.5)",
          }}
        />
      </Sequence>

      {/* Title */}
      <Sequence from={0}>
        <div
          style={{
            opacity: titleOpacity,
            transform: `scale(${titleScale})`,
            fontSize: 72,
            fontWeight: 800,
            color: "white",
            textAlign: "center",
            letterSpacing: -2,
            lineHeight: 1.1,
          }}
        >
          Symbol-U
        </div>
      </Sequence>

      {/* Subtitle */}
      <Sequence from={25}>
        <div
          style={{
            opacity: subOpacity,
            transform: `translateY(${subY}px)`,
            fontSize: 28,
            color: "#a78bfa",
            marginTop: 12,
            fontWeight: 300,
            letterSpacing: 4,
            textTransform: "uppercase",
          }}
        >
          Deterministic AGI Engine
        </div>
      </Sequence>

      {/* Underline */}
      <Sequence from={40}>
        <div
          style={{
            width: lineWidth,
            height: 2,
            background: "linear-gradient(90deg, transparent, #6366f1, transparent)",
            marginTop: 20,
          }}
        />
      </Sequence>

      {/* Bottom tagline */}
      <Sequence from={70}>
        <div
          style={{
            position: "absolute",
            bottom: 80,
            opacity: interpolate(frame - 70, [0, 20], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            fontSize: 18,
            color: "#64748b",
            letterSpacing: 2,
          }}
        >
          99.7% Test Pass Rate &bull; 48-Phase Pipeline &bull; 7 Coherence Metrics
        </div>
      </Sequence>
    </AbsoluteFill>
  );
};
