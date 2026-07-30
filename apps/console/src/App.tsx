import React, { useEffect, useState } from 'react';
import { Workflow, Boxes, ScrollText, ShieldCheck } from 'lucide-react';
import { api, Health } from './api';
import { GovernedLoop } from './views/GovernedLoop';
import { Modules } from './views/Modules';
import { Audit } from './views/Audit';

type Tab = 'loop' | 'modules' | 'audit';

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: 'loop', label: 'Governed Loop', icon: <Workflow className="w-4 h-4" /> },
  { id: 'modules', label: 'Modules', icon: <Boxes className="w-4 h-4" /> },
  { id: 'audit', label: 'Audit', icon: <ScrollText className="w-4 h-4" /> },
];

export default function App() {
  const [tab, setTab] = useState<Tab>('loop');
  const [health, setHealth] = useState<Health | null>(null);
  const [down, setDown] = useState(false);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setDown(true));
  }, []);

  return (
    <div className="min-h-screen">
      <header className="border-b border-white/10 bg-slate-900/50 backdrop-blur">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-ugence-primary to-ugence-accent flex items-center justify-center">
              <ShieldCheck className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-sm font-semibold leading-tight">Ugence AI Control Plane</h1>
              <p className="text-xs text-slate-400">Unified governance console</p>
            </div>
          </div>
          <div className="text-xs text-slate-400">
            {down ? (
              <span className="text-red-400">API offline</span>
            ) : health ? (
              <span>API v{health.version} · {health.status}</span>
            ) : (
              <span>connecting…</span>
            )}
          </div>
        </div>
        <nav className="max-w-5xl mx-auto px-6 flex gap-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`inline-flex items-center gap-2 px-3 py-2 text-sm border-b-2 -mb-px transition-colors ${
                tab === t.id
                  ? 'border-ugence-primary text-white'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              {t.icon}
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8">
        {down && (
          <div className="mb-6 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-300">
            Cannot reach the console API. Start it with{' '}
            <code className="font-mono">python -m ugence_console_api</code> (port 8090).
          </div>
        )}
        {tab === 'loop' && <GovernedLoop />}
        {tab === 'modules' && <Modules />}
        {tab === 'audit' && <Audit />}
      </main>
    </div>
  );
}
