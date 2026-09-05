// Screen 4 — Simulate.
//
// The banner is the most important element on this screen. A run cleared by a
// permissive test hook is not a governance result, and a trace shown without saying
// so would present a foregone conclusion as an outcome. LIVE is not offered: the mode
// selector lists only the non-mutating modes, and the backend refuses LIVE anyway.
import { useState } from "react";

import { GapNotice, PermissiveHookBanner } from "./GapNotice";
import { ActionButton, Json, Panel, ScreenFrame } from "./ScreenFrame";
import { useRunSimulation } from "./hooks";
import { isUnavailable } from "@/api/types-v2";

/** The studio never executes, so LIVE is absent by construction, not disabled. */
const MODES = ["DRY_RUN", "SIMULATION", "SHADOW"] as const;

const SAMPLE_WORKFLOW = {
  workflow_id: "studio-simulation",
  tasks: [{ task_id: "t1", operation: "prepare", provider_id: "fixture", consequential: true }],
};

export function SimulateScreen() {
  const [mode, setMode] = useState<(typeof MODES)[number]>("DRY_RUN");
  const run = useRunSimulation();

  return (
    <ScreenFrame
      title="Simulate"
      subtitle="Run a compiled workflow against fixtures and see every governance decision the runtime made."
      neverDoes="Nothing consequential is reachable from here. There is no live execution mode."
    >
      <Panel title="Run">
        <label htmlFor="execution-mode" className="mb-1 block text-[11px] text-ink-2">
          Execution mode
        </label>
        <select
          id="execution-mode"
          value={mode}
          onChange={(e) => setMode(e.target.value as (typeof MODES)[number])}
          className="rounded border border-surface-border bg-surface-0 px-2 py-1 text-[12px] text-ink-0"
        >
          {MODES.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
        <div className="mt-2">
          <ActionButton
            onClick={() => run.mutate({ workflow: SAMPLE_WORKFLOW, execution_mode: mode, max_quanta: 8 })}
            disabled={run.isPending}
          >
            Run simulation
          </ActionButton>
        </div>
      </Panel>

      {run.data ? (
        <Panel title="Result">
          {isUnavailable(run.data) ? (
            <GapNotice gap={run.data} />
          ) : (
            <div className="space-y-3">
              <PermissiveHookBanner
                permissive={Boolean((run.data as { governance_hook_permissive?: boolean }).governance_hook_permissive)}
                configured={Boolean((run.data as { governance_hook_configured?: boolean }).governance_hook_configured)}
              />
              <div className="text-[12px] text-ink-1">
                Mode{" "}
                <span className="font-mono text-[11px]">
                  {String((run.data as { execution_mode?: string }).execution_mode ?? "")}
                </span>{" "}
                · instance{" "}
                <span className="font-mono text-[11px]">
                  {String((run.data as { instance_id?: string }).instance_id ?? "")}
                </span>
              </div>
              <Json value={(run.data as { quanta?: unknown }).quanta} label="Advance trace" />
            </div>
          )}
        </Panel>
      ) : null}
    </ScreenFrame>
  );
}
