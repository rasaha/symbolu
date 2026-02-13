import React from "react";
import { Composition } from "remotion";
import { CoherenceDashboard } from "./templates/CoherenceDashboard";
import { TitleCard } from "./templates/TitleCard";
import { MetricsAnimation } from "./templates/MetricsAnimation";
import { TextKinetic } from "./templates/TextKinetic";

/**
 * Root component that registers all available Remotion compositions.
 *
 * Each composition is a video template that can be:
 * 1. Used directly with predefined content
 * 2. Generated dynamically by the Phase Quad LLM
 *
 * The LLM generates new compositions in src/compositions/ which are
 * dynamically registered via the API.
 */
export const RemotionRoot: React.FC = () => {
  return (
    <>
      {/* Built-in templates */}
      <Composition
        id="CoherenceDashboard"
        component={CoherenceDashboard}
        durationInFrames={180}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="TitleCard"
        component={TitleCard}
        durationInFrames={150}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="MetricsAnimation"
        component={MetricsAnimation}
        durationInFrames={210}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="TextKinetic"
        component={TextKinetic}
        durationInFrames={180}
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};
