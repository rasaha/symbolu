// The one piece of state the six screens share: the compiled release the Policy
// screen produced in this session, which is the only thing the Publish screen may
// send to the shadow loop.
//
// It lives in the studio layout and reaches screens through the router's outlet
// context, so a screen rendered outside the layout sees "no release" rather than a
// missing provider. There is deliberately no other way to obtain a release: the
// Publish screen cannot construct or accept one from anywhere but a compile.
import { useOutletContext } from "react-router-dom";

export interface CompiledRelease {
  compiledPackage: Record<string, unknown>;
  logicalDigest: string;
}

export interface StudioReleaseContext {
  release: CompiledRelease | null;
  setRelease: (release: CompiledRelease | null) => void;
}

const DETACHED: StudioReleaseContext = { release: null, setRelease: () => undefined };

export function useStudioRelease(): StudioReleaseContext {
  return useOutletContext<StudioReleaseContext | undefined>() ?? DETACHED;
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
