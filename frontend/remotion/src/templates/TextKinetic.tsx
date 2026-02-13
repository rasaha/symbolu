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
 * Kinetic typography animation.
 *
 * Words appear one by one with spring physics, building
 * a complete phrase with emphasis on key terms.
 */

interface WordProps {
  text: string;
  delay: number;
  isHighlight?: boolean;
  size?: number;
}

const AnimatedWord: React.FC<WordProps> = ({
  text,
  delay,
  isHighlight = false,
  size = 56,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const adjustedFrame = Math.max(0, frame - delay);

  const scale = spring({
    frame: adjustedFrame,
    fps,
    config: { damping: 10, stiffness: 200, mass: 0.6 },
  });

  const opacity = interpolate(adjustedFrame, [0, 8], [0, 1], {
    extrapolateRight: "clamp",
  });

  const y = interpolate(
    spring({
      frame: adjustedFrame,
      fps,
      config: { damping: 12, stiffness: 150 },
    }),
    [0, 1],
    [40, 0]
  );

  return (
    <div
      style={{
        opacity,
        transform: `scale(${scale}) translateY(${y}px)`,
        fontSize: size,
        fontWeight: isHighlight ? 800 : 400,
        color: isHighlight ? "#a78bfa" : "white",
        display: "inline-block",
        marginRight: 16,
        textShadow: isHighlight ? "0 0 30px rgba(167,139,250,0.4)" : "none",
      }}
    >
      {text}
    </div>
  );
};

const LINES = [
  {
    words: [
      { text: "Making", isHighlight: false },
      { text: "AI", isHighlight: true },
    ],
    y: -60,
  },
  {
    words: [
      { text: "Trustworthy", isHighlight: true },
    ],
    y: 20,
  },
  {
    words: [
      { text: "for", isHighlight: false },
      { text: "Enterprise", isHighlight: true },
    ],
    y: 100,
  },
];

export const TextKinetic: React.FC = () => {
  const frame = useCurrentFrame();

  // Final fade out
  const fadeOut = interpolate(frame, [140, 170], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  let wordIndex = 0;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#0f0f23",
        justifyContent: "center",
        alignItems: "center",
        fontFamily: "Inter, Helvetica Neue, Arial, sans-serif",
        opacity: fadeOut,
      }}
    >
      {/* Background gradient pulse */}
      <div
        style={{
          position: "absolute",
          width: "100%",
          height: "100%",
          background: `radial-gradient(circle at 50% 50%, rgba(99,102,241,${
            interpolate(frame, [0, 90, 180], [0, 0.08, 0], {
              extrapolateRight: "clamp",
            })
          }) 0%, transparent 70%)`,
        }}
      />

      <div style={{ textAlign: "center" }}>
        {LINES.map((line, lineIdx) => {
          const lineDelay = lineIdx * 25;
          return (
            <div
              key={lineIdx}
              style={{
                display: "flex",
                justifyContent: "center",
                alignItems: "baseline",
                marginBottom: 10,
              }}
            >
              {line.words.map((word) => {
                const delay = lineDelay + wordIndex * 8;
                wordIndex++;
                return (
                  <Sequence key={word.text} from={delay}>
                    <AnimatedWord
                      text={word.text}
                      delay={delay}
                      isHighlight={word.isHighlight}
                      size={word.isHighlight ? 72 : 56}
                    />
                  </Sequence>
                );
              })}
            </div>
          );
        })}
      </div>

      {/* Bottom accent line */}
      <Sequence from={80}>
        <div
          style={{
            position: "absolute",
            bottom: 120,
            width: interpolate(frame - 80, [0, 40], [0, 300], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            height: 3,
            background: "linear-gradient(90deg, transparent, #6366f1, transparent)",
          }}
        />
      </Sequence>
    </AbsoluteFill>
  );
};
