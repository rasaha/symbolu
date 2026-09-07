import { useEffect, useState } from 'react';
import { Search } from 'lucide-react';
import { api, AuditChain } from '../api';
import { band, BAND_CLASS } from '../decision';

export function Audit() {
  const [ids, setIds] = useState<string[]>([]);
  const [query, setQuery] = useState('');
  const [chain, setChain] = useState<AuditChain | null>(null);
  const [error, setError] = useState('');

  function refresh() {
    api.auditIds().then(setIds).catch((e) => setError(String(e)));
  }
  useEffect(refresh, []);

  async function load(correlationId: string) {
    setError('');
    try {
      setChain(await api.auditChain(correlationId));
      setQuery(correlationId);
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <div className="space-y-5">
      <p className="text-sm text-black">
        Reconstruct a complete decision chain by correlation id — what the agent asserted,
        whether it was supported, who authorized the action, and whether it was safe.
      </p>

      <div className="flex gap-2">
        <div className="flex-1 flex items-center gap-2 bg-white border border-neutral-300 rounded-lg px-3">
          <Search className="w-4 h-4 text-black" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && load(query.trim())}
            placeholder="correlation id"
            className="flex-1 bg-transparent py-2 text-sm outline-none"
          />
        </div>
        <button
          onClick={() => load(query.trim())}
          className="px-4 py-2 rounded-lg bg-red-700 hover:bg-red-800 text-white text-sm font-medium"
        >
          Reconstruct
        </button>
      </div>

      {ids.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {ids.map((id) => (
            <button
              key={id}
              onClick={() => load(id)}
              className="px-2 py-1 rounded-md bg-red-700 text-white text-xs hover:bg-red-800 font-mono"
            >
              {id}
            </button>
          ))}
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-700">{error}</div>
      )}

      {chain && (
        <div className="rounded-xl border border-neutral-300 bg-neutral-50 p-4">
          <div className="text-xs text-black">
            {chain.correlation_id} · {chain.cer_id} · mode {chain.mode}
          </div>
          <div className="text-sm font-medium mt-1">{chain.final_disposition}</div>
          <table className="w-full mt-4 text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-black border-b border-neutral-300">
                <th className="py-2 pr-3">Stage</th>
                <th className="py-2 pr-3">Module</th>
                <th className="py-2 pr-3">Decision</th>
                <th className="py-2">Summary</th>
              </tr>
            </thead>
            <tbody>
              {chain.entries.map((e, i) => (
                <tr key={i} className="border-b border-neutral-200 align-top">
                  <td className="py-2 pr-3 whitespace-nowrap text-black">{e.stage}</td>
                  <td className="py-2 pr-3 whitespace-nowrap text-black">{e.module}</td>
                  <td className="py-2 pr-3">
                    <span className={`px-2 py-0.5 rounded-md border text-xs font-semibold ${BAND_CLASS[band(e.decision)]}`}>
                      {e.decision}
                    </span>
                  </td>
                  <td className="py-2 text-black">{e.summary}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
