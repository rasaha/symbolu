// The Governed Agent Studio section: its own nav, mounted alongside the v1 explorer.
//
// Kept separate from the v1 scenario routes so the eligibility explorer's own
// navigation, screens and tests are untouched by the studio existing.
import { useMemo, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import type { CompiledRelease, StudioReleaseContext } from "./release";

const SCREENS = [
  { to: "constitution", label: "Constitution" },
  { to: "policy", label: "Policy" },
  { to: "authority", label: "Authority" },
  { to: "simulate", label: "Simulate" },
  { to: "publish", label: "Publish" },
  { to: "observe", label: "Observe" },
] as const;

export function StudioLayout() {
  const [release, setRelease] = useState<CompiledRelease | null>(null);
  const context = useMemo<StudioReleaseContext>(() => ({ release, setRelease }), [release]);
  return (
    <div className="space-y-4">
      <nav aria-label="Governed Agent Studio screens" className="flex flex-wrap gap-1">
        {SCREENS.map((s) => (
          <NavLink
            key={s.to}
            to={s.to}
            className={({ isActive }) =>
              `rounded border px-3 py-1.5 text-[12px] font-medium ${
                isActive
                  ? "border-ink-3 bg-surface-3 text-ink-0"
                  : "border-surface-border bg-surface-1 text-ink-1 hover:bg-surface-2"
              }`
            }
          >
            {s.label}
          </NavLink>
        ))}
      </nav>
      <div className="rounded border border-surface-border bg-surface-2 px-3 py-2 text-[11px] text-ink-2">
        <span className="font-mono">governance_studio.api.v2</span> · additive contract
        alongside the frozen v1 explorer · planning, preflight and observation only ·
        no screen here issues, activates, revokes, grants, authorizes, clears or executes
      </div>
      <Outlet context={context} />
    </div>
  );
}
