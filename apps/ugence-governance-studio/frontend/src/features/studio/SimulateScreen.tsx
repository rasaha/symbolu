// Screen 4 — Simulate.
//
// Two labelled paths, never merged (front-door ruling FD-10.5 TWO_LABELLED_PATHS).
//
// Path A is the seam-3 in-process fixture run: this studio's own Agent Runtime over
// the one pinned fixture provider, with the runtime's default hook, which blocks every
// consequential task. Path B is the seam-6 worker relay: the governed runtime worker
// starts the worker's own shadow workflow under the worker's governed hook, and a
// consequential task parks on ESCALATE in the review queue until a recorded human
// decision. Each path names its executor, its hook and its maturity beside its own
// control, and neither is chosen for the operator: nothing runs until a specific
// control is used.
//
// The banner on path A is its most important element. A run cleared by a permissive
// test hook is not a governance result, and a trace shown without saying so would
// present a foregone conclusion as an outcome. LIVE is not offered on either path: the
// mode selector lists only the non-mutating modes, the backend refuses LIVE, and the
// worker relay has no mode parameter at all (the backend pins the word `shadow`).
import { useState } from "react";

import { GapNotice, PermissiveHookBanner } from "./GapNotice";
import { ActionButton, Json, Panel, ScreenFrame } from "./ScreenFrame";
import { useRunSimulation, useStartWorkerShadowRun } from "./hooks";
import { isUnavailable } from "@/api/types-v2";

/** The studio never executes, so LIVE is absent by construction, not disabled. */
const MODES = ["DRY_RUN", "SIMULATION", "SHADOW"] as const;

const SAMPLE_WORKFLOW = {
  workflow_id: "studio-simulation",
  tasks: [{ task_id: "t1", operation: "prepare", provider_id: "fixture", consequential: true }],
};

/** FD-10.5: what each path is, stated where its control is. */
const PATHS = {
  local: {
    label: "Path A · In-process fixture run",
    executor: "this studio's own Agent Runtime (seam 3)",
    hook: "the runtime's default hook: every consequential task blocks (GOVERNANCE_NOT_CONFIGURED)",
    maturity: "DEMONSTRATION_ONLY fixture provider; no external effect",
  },
  worker: {
    label: "Path B · Worker shadow run",
    executor: "the governed runtime worker, a separate unit (seam 6); the studio executes nothing",
    hook: "the worker's governed hook over the approval-bound source: a consequential task parks on ESCALATE in the review queue until a recorded human decision",
    maturity: "REFERENCE_GRADE_SHADOW_ONLY; the worker's providers are FIXTURE_ONLY",
  },
} as const;

/** FD-4: a correlation id is a typed token, or nothing at all. */
const CORRELATION_ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$/;

function PathLabel({ path }: { path: (typeof PATHS)[keyof typeof PATHS] }) {
  return (
    <dl className="mb-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-[11px] text-ink-2">
      <dt className="font-medium text-ink-3">Executor</dt>
      <dd>{path.executor}</dd>
      <dt className="font-medium text-ink-3">Hook</dt>
      <dd>{path.hook}</dd>
      <dt className="font-medium text-ink-3">Maturity</dt>
      <dd className="font-mono">{path.maturity}</dd>
    </dl>
  );
}

function str(value: unknown, key: string): string {
  return String((value as Record<string, unknown>)[key] ?? "");
}

export function SimulateScreen() {
  const [mode, setMode] = useState<(typeof MODES)[number]>("DRY_RUN");
  const [correlationId, setCorrelationId] = useState("");
  const run = useRunSimulation();
  const relay = useStartWorkerShadowRun();
  const correlationValid = correlationId === "" || CORRELATION_ID.test(correlationId);

  return (
    <ScreenFrame
      title="Simulate"
      subtitle="Two distinct paths: run a compiled workflow in this studio against fixtures, or ask the governed runtime worker to start its own shadow run. Each is labelled with its executor, its hook and its maturity."
      neverDoes="Nothing consequential is reachable from here. There is no live execution mode on either path, and no path is chosen for you."
    >
      <Panel title={PATHS.local.label}>
        <PathLabel path={PATHS.local} />
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
        {run.data ? (
          <div className="mt-3" data-testid="local-result">
            {isUnavailable(run.data) ? (
              <GapNotice gap={run.data} />
            ) : (
              <div className="space-y-3">
                <PermissiveHookBanner
                  permissive={Boolean((run.data as { governance_hook_permissive?: boolean }).governance_hook_permissive)}
                  configured={Boolean((run.data as { governance_hook_configured?: boolean }).governance_hook_configured)}
                />
                <div className="text-[12px] text-ink-1">
                  Mode <span className="font-mono text-[11px]">{str(run.data, "execution_mode")}</span> ·
                  instance <span className="font-mono text-[11px]">{str(run.data, "instance_id")}</span>
                </div>
                <Json value={(run.data as { quanta?: unknown }).quanta} label="Advance trace" />
              </div>
            )}
          </div>
        ) : null}
      </Panel>

      <Panel title={PATHS.worker.label}>
        <PathLabel path={PATHS.worker} />
        <p className="mb-2 text-[11px] text-ink-2">
          The worker holds the definition. Nothing is sent from here but an optional correlation id:
          no workflow, task, provider, mode or digest (FD-10.3). The worker&rsquo;s own definition
          digest binds the run; a repeated start with the same correlation id replays the same instance.
        </p>
        <label htmlFor="worker-correlation-id" className="mb-1 block text-[11px] text-ink-2">
          Correlation id (optional)
        </label>
        <input
          id="worker-correlation-id"
          value={correlationId}
          onChange={(e) => setCorrelationId(e.target.value)}
          aria-invalid={!correlationValid}
          className="w-full max-w-sm rounded border border-surface-border bg-surface-0 px-2 py-1 font-mono text-[12px] text-ink-0"
        />
        {!correlationValid ? (
          <p role="alert" className="mt-1 text-[11px] text-red-700">
            A correlation id is a typed token: letters, digits, &lsquo;.&rsquo;, &lsquo;_&rsquo;, &lsquo;:&rsquo; and
            &lsquo;-&rsquo;, at most 64 characters. Nothing is sent until it is.
          </p>
        ) : null}
        <div className="mt-2">
          <ActionButton
            onClick={() => relay.mutate(correlationId === "" ? {} : { correlation_id: correlationId })}
            disabled={relay.isPending || !correlationValid}
          >
            Start worker shadow run
          </ActionButton>
        </div>
        {relay.data ? (
          <div className="mt-3" data-testid="worker-result">
            {isUnavailable(relay.data) ? (
              <GapNotice gap={relay.data} />
            ) : (
              <WorkerOutcome data={relay.data as Record<string, unknown>} />
            )}
          </div>
        ) : null}
      </Panel>
    </ScreenFrame>
  );
}

/** The worker's typed outcome, rendered as the worker said it. */
function WorkerOutcome({ data }: { data: Record<string, unknown> }) {
  const outcome = (data.result ?? {}) as Record<string, unknown>;
  const started = outcome.started === true;
  const result = str(outcome, "result");
  return (
    <div className="space-y-2">
      <div
        role="status"
        aria-label="worker outcome"
        className={
          started
            ? "rounded border border-surface-border bg-surface-2 px-3 py-2 text-[12px] text-ink-1"
            : "rounded border border-amber-300 bg-amber-50 px-3 py-2 text-[12px] text-amber-950"
        }
      >
        <span className="font-semibold">{result || "no outcome"}</span>
        {result === "REPLAYED" ? " — this correlation id already names an instance; nothing was re-run." : null}
        {result === "STARTED" && outcome.awaiting_external === true
          ? " — parked; a consequential task waits on the review queue for a recorded decision."
          : null}
        {!started && str(outcome, "reason") ? <p className="mt-1">{str(outcome, "reason")}</p> : null}
      </div>
      <div className="text-[12px] text-ink-1">
        Instance <span className="font-mono text-[11px]">{str(outcome, "instance_id")}</span> · workflow{" "}
        <span className="font-mono text-[11px]">{str(outcome, "workflow_id")}</span> · definition digest{" "}
        <span className="font-mono text-[11px]">{str(outcome, "definition_digest")}</span> · mode{" "}
        <span className="font-mono text-[11px]">{str(outcome, "mode")}</span>
      </div>
      <div className="text-[11px] text-ink-2">
        Maturity <span className="font-mono">{str(outcome, "maturity")}</span> · providers{" "}
        <span className="font-mono">{str(outcome, "workload_maturity")}</span> · identity proof{" "}
        <span className="font-mono">{str(outcome, "identity_proof")}</span>
      </div>
      <Json value={outcome} label="Worker answer" />
    </div>
  );
}
