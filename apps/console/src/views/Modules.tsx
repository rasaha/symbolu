import { useEffect, useState } from 'react';
import { api, Health } from '../api';
import { TypedGap } from './TypedGap';

/**
 * The module registry lived behind `/v1/modules`, one of the six routes ruling CP-3
 * withheld from the packaged console API; ruling MA-4 retired this app's call to it.
 * What the service still serves is `/health`, whose per-module availability probes are
 * the only module data this view may show. They are rendered under the keys the
 * service returns and nothing is added to them: no name, layer, maturity or wiring is
 * known here, and none is invented.
 */
export function Modules() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api.health().then(setHealth).catch((e) => setError(String(e)));
  }, []);

  const probes = health ? Object.entries(health.modules) : [];

  return (
    <div className="space-y-6">
      <TypedGap
        code="CONSOLE_ROUTE_WITHHELD"
        source="GET /v1/modules"
        ruling="CP-3 withheld · MA-4 retired the call"
      >
        The nine-module registry — name, layer, capability, maturity and wiring — is not
        served by the packaged console API. Nothing below is a module description; it is
        the service's own availability probe for each engine it can reach.
      </TypedGap>

      {error && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-700">{error}</div>
      )}

      {health && (
        <div>
          <h3 className="text-xs uppercase tracking-wide text-black mb-2">
            Availability probes · from GET /health
          </h3>
          <div className="grid sm:grid-cols-2 gap-3">
            {probes.map(([key, probe]) => (
              <div key={key} className="rounded-xl border border-neutral-300 bg-neutral-50 p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="font-mono text-sm">{key}</div>
                  <span
                    className={`shrink-0 w-2.5 h-2.5 rounded-full mt-1.5 ${probe.available ? 'bg-verdict-allow' : 'bg-neutral-400'}`}
                    title={probe.available ? 'engine available' : probe.reason || 'not wired'}
                  />
                </div>
                <div className="text-xs text-black mt-2">
                  {probe.available ? 'engine available' : probe.reason || 'not wired'}
                </div>
              </div>
            ))}
          </div>
          <p className="mt-3 text-[11px] text-black">
            Audit ceiling, as the service declares it on every answer: {health.audit_ceiling}
          </p>
        </div>
      )}
    </div>
  );
}
