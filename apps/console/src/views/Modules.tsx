import { useEffect, useState } from 'react';
import { api, ModuleInfo, Health } from '../api';

const WIRING_LABEL: Record<string, string> = {
  loop: 'Live in governed loop',
  standalone: 'Registered · endpoint / next phase',
  'read-only': 'Substrate / status only',
};

const WIRING_CLASS: Record<string, string> = {
  loop: 'bg-verdict-allow/15 text-verdict-allow border-verdict-allow/30',
  standalone: 'bg-ugence-accent/15 text-ugence-accent border-ugence-accent/30',
  'read-only': 'bg-slate-500/15 text-slate-300 border-slate-500/30',
};

export function Modules() {
  const [modules, setModules] = useState<ModuleInfo[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([api.modules(), api.health()])
      .then(([m, h]) => { setModules(m); setHealth(h); })
      .catch((e) => setError(String(e)));
  }, []);

  const layers = ['Specialized AI Systems', 'AI Control Plane'];

  return (
    <div className="space-y-6">
      <p className="text-sm text-slate-400">
        Nine consolidated modules across two layers. The two AI-Infrastructure modules
        (KVPro, Cloud Scaling Controller) are intentionally excluded — they never govern.
      </p>
      {error && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">{error}</div>
      )}
      {layers.map((layer) => (
        <div key={layer}>
          <h3 className="text-xs uppercase tracking-wide text-slate-500 mb-2">{layer}</h3>
          <div className="grid sm:grid-cols-2 gap-3">
            {modules.filter((m) => m.layer.startsWith(layer)).map((m) => {
              const probe = health?.modules[m.key];
              return (
                <div key={m.key} className="rounded-xl border border-white/10 bg-white/5 p-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="font-medium">{m.name}</div>
                    {probe && (
                      <span
                        className={`shrink-0 w-2.5 h-2.5 rounded-full mt-1.5 ${probe.available ? 'bg-verdict-allow' : 'bg-slate-600'}`}
                        title={probe.available ? 'engine available' : probe.reason || 'not wired'}
                      />
                    )}
                  </div>
                  <div className="text-xs text-slate-400 mt-0.5">{m.capability}</div>
                  <p className="text-xs text-slate-400 italic mt-2">{m.question}</p>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <span className={`px-2 py-0.5 rounded-md border text-[11px] ${WIRING_CLASS[m.wiring]}`}>
                      {WIRING_LABEL[m.wiring]}
                    </span>
                    <span className="text-[11px] text-slate-500">{m.maturity}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
