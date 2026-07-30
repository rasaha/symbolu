import React, { useEffect, useState } from 'react';
import {
  ShieldCheck,
  Filter,
  Gavel,
  Radio,
  FileClock,
  Play,
  Loader2,
} from 'lucide-react';
import { api, GovernedLoopResult, ScenarioSummary } from '../api';
import { band, BAND_CLASS } from '../decision';

const STAGE_ICON: Record<string, React.ReactNode> = {
  Gateway: <Filter className="w-4 h-4" />,
  Verify: <ShieldCheck className="w-4 h-4" />,
  Authorize: <Gavel className="w-4 h-4" />,
  Clear: <Radio className="w-4 h-4" />,
  Record: <FileClock className="w-4 h-4" />,
};

export function GovernedLoop() {
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [selected, setSelected] = useState<string>('');
  const [result, setResult] = useState<GovernedLoopResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    api.scenarios().then((s) => {
      setScenarios(s);
      if (s.length) setSelected(s[0].id);
    }).catch((e) => setError(String(e)));
  }, []);

  async function run() {
    if (!selected) return;
    setRunning(true);
    setError('');
    try {
      setResult(await api.runScenario(selected));
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
      <div className="flex items-center gap-2 text-xs font-medium text-amber-400">
        <span className="px-2 py-0.5 rounded-full border border-amber-400/40 bg-amber-400/10">
          SHADOW MODE
        </span>
        <span className="text-slate-400">evaluate &amp; record — nothing is changed</span>
      </div>

      {/* scenario picker */}
      <div className="rounded-xl border border-white/10 bg-white/5 p-4">
        <label className="block text-sm text-slate-300 mb-2">
          Kubernetes / infrastructure-agent workflow
        </label>
        <div className="flex flex-col sm:flex-row gap-3">
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="flex-1 bg-slate-900 border border-white/10 rounded-lg px-3 py-2 text-sm"
          >
            {scenarios.map((s) => (
              <option key={s.id} value={s.id}>{s.title}</option>
            ))}
          </select>
          <button
            onClick={run}
            disabled={running || !selected}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-ugence-primary hover:bg-indigo-500 disabled:opacity-50 text-sm font-medium"
          >
            {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            Run governed loop
          </button>
        </div>
        {scenarios.find((s) => s.id === selected) && (
          <p className="mt-2 text-xs text-slate-400">
            {scenarios.find((s) => s.id === selected)!.description}
          </p>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">
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
          <ol className="relative border-l border-white/10 ml-3 space-y-4">
            {result.stages.map((s, i) => {
              const b = band(s.decision);
              return (
                <li key={i} className="ml-6">
                  <span className="absolute -left-3 flex items-center justify-center w-6 h-6 rounded-full bg-slate-800 border border-white/10">
                    {STAGE_ICON[s.stage] || <Filter className="w-4 h-4" />}
                  </span>
                  <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <span className="text-xs uppercase tracking-wide text-slate-400">
                          {s.stage} · {s.capability}
                        </span>
                        <div className="text-sm font-medium">{s.module}</div>
                      </div>
                      <span className={`shrink-0 px-2 py-0.5 rounded-md border text-xs font-semibold ${BAND_CLASS[b]}`}>
                        {s.decision}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-slate-400 italic">{s.question}</p>
                    <p className="mt-1 text-sm text-slate-200">{s.summary}</p>
                    <div className="mt-1 text-[11px] text-slate-500">{s.module_maturity}</div>
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
