import React, { useState } from 'react';
import {
  ShieldCheck,
  Filter,
  Gavel,
  Radio,
  FileClock,
  Play,
  Loader2,
} from 'lucide-react';
import { api, GovernedLoopResult } from '../api';
import { band, BAND_CLASS } from '../decision';
import { TypedGap } from './TypedGap';

const STAGE_ICON: Record<string, React.ReactNode> = {
  Gateway: <Filter className="w-4 h-4" />,
  Verify: <ShieldCheck className="w-4 h-4" />,
  Authorize: <Gavel className="w-4 h-4" />,
  Clear: <Radio className="w-4 h-4" />,
  Record: <FileClock className="w-4 h-4" />,
};

/**
 * The scenario catalogue lived behind `/v1/scenarios`, one of the six routes ruling
 * CP-3 withheld from the packaged console API; ruling MA-4 retired this app's call to
 * it. The run route, `POST /v1/governed-loop/scenario/{scenario_id}`, is served, so the
 * scenario id is typed here — the same shape the Audit view uses for a correlation id —
 * and an unknown id is the service's own 404, shown verbatim. No scenario list is kept
 * in this app: a list here would be the withheld route re-implemented in the browser.
 */
export function GovernedLoop() {
  const [selected, setSelected] = useState<string>('');
  const [result, setResult] = useState<GovernedLoopResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string>('');

  async function run() {
    const id = selected.trim();
    if (!id) return;
    setRunning(true);
    setError('');
    try {
      setResult(await api.runScenario(id));
    } catch (e) {
      setError(String(e));
    } finally {
      setRunning(false);
    }
  }

  const dispositionBand = result
    ? result.would_execute ? 'allow' : 'block'
    : 'neutral';

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-xs font-medium text-amber-800">
        <span className="px-2 py-0.5 rounded-full border border-amber-400/40 bg-amber-400/10">
          SHADOW MODE
        </span>
        <span className="text-black">evaluate &amp; record — nothing is changed</span>
      </div>

      <TypedGap
        code="CONSOLE_ROUTE_WITHHELD"
        source="GET /v1/scenarios"
        ruling="CP-3 withheld · MA-4 retired the call"
      >
        The scenario catalogue — titles and descriptions of the shipped shadow
        workflows — is not served by the packaged console API. The run route is. Enter a
        scenario id; one the service does not hold is its own 404, shown below verbatim.
      </TypedGap>

      {/* scenario id, typed */}
      <div className="rounded-xl border border-neutral-300 bg-neutral-50 p-4">
        <label htmlFor="scenario-id" className="block text-sm text-black mb-2">
          Kubernetes / infrastructure-agent workflow · scenario id
        </label>
        <div className="flex flex-col sm:flex-row gap-3">
          <input
            id="scenario-id"
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && run()}
            placeholder="scenario id"
            className="flex-1 bg-white border border-neutral-300 rounded-lg px-3 py-2 text-sm font-mono outline-none"
          />
          <button
            onClick={run}
            disabled={running || !selected.trim()}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-red-700 hover:bg-red-800 text-white disabled:opacity-50 text-sm font-medium"
          >
            {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            Run governed loop
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-4">
          {/* disposition banner */}
          <div className={`rounded-xl border p-4 ${BAND_CLASS[dispositionBand]}`}>
            <div className="text-xs uppercase tracking-wide opacity-70">Final disposition</div>
            <div className="text-lg font-semibold">{result.final_disposition}</div>
            <div className="mt-1 text-xs opacity-70">
              correlation {result.correlation_id} · {result.cer_id}
            </div>
          </div>

          {/* stage trail */}
          <ol className="relative border-l border-neutral-300 ml-3 space-y-4">
            {result.stages.map((s, i) => {
              const b = band(s.decision);
              return (
                <li key={i} className="ml-6">
                  <span className="absolute -left-3 flex items-center justify-center w-6 h-6 rounded-full bg-neutral-100 border border-neutral-300">
                    {STAGE_ICON[s.stage] || <Filter className="w-4 h-4" />}
                  </span>
                  <div className="rounded-lg border border-neutral-300 bg-neutral-50 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <span className="text-xs uppercase tracking-wide text-black">
                          {s.stage} · {s.capability}
                        </span>
                        <div className="text-sm font-medium">{s.module}</div>
                      </div>
                      <span className={`shrink-0 px-2 py-0.5 rounded-md border text-xs font-semibold ${BAND_CLASS[b]}`}>
                        {s.decision}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-black italic">{s.question}</p>
                    <p className="mt-1 text-sm text-black">{s.summary}</p>
                    <div className="mt-1 text-[11px] text-black">{s.module_maturity}</div>
                  </div>
                </li>
              );
            })}
          </ol>
        </div>
      )}
    </div>
  );
}
