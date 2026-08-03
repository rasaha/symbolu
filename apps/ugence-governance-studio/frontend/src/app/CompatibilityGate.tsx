// Blocking API compatibility screen (§9). When the backend is unreachable,
// not-ready, or on an unsupported contract, the app refuses to render partial
// functionality and shows honest diagnostics with a retry.
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, XCircle, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";
import { checkCompatibility } from "@/api/compatibility";
import { apiBaseUrl } from "@/lib/config";
import { LoadingState } from "@/design-system/states";

export function CompatibilityGate({ children }: { children: ReactNode }) {
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["compatibility"],
    queryFn: checkCompatibility,
    retry: 0,
    staleTime: 60_000,
  });

  if (isLoading) return <LoadingState label="Checking API compatibility…" />;
  if (data?.compatible) return <>{children}</>;

  return (
    <main className="mx-auto max-w-2xl p-8" aria-labelledby="compat-title">
      <h1 id="compat-title" className="mb-2 text-xl font-semibold text-ink-0">
        Governance Studio API is not compatible
      </h1>
      <p className="mb-4 text-sm text-ink-2">
        The Eligibility Explorer requires the frozen <code>{data?.requiredContract}</code> contract.
        It will not render partial functionality against an unsupported or unavailable backend.
      </p>

      <dl className="mb-4 grid grid-cols-2 gap-2 rounded border border-surface-border bg-surface-1 p-4 text-sm">
        <dt className="text-ink-3">API base URL</dt>
        <dd className="font-mono text-ink-1">{apiBaseUrl}</dd>
        <dt className="text-ink-3">Detected contract</dt>
        <dd className="text-ink-1">{data?.detectedContract ?? "unknown"}</dd>
        <dt className="text-ink-3">Required contract</dt>
        <dd className="text-ink-1">{data?.requiredContract}</dd>
      </dl>

      {data?.error && (
        <p role="alert" className="mb-4 rounded border border-state-ineligible/40 bg-state-ineligible/10 p-3 text-sm text-ink-1">
          {data.error}
        </p>
      )}

      {data && data.checks.length > 0 && (
        <ul className="mb-4 space-y-1.5">
          {data.checks.map((c) => (
            <li key={c.key} className="flex items-start gap-2 text-sm">
              {c.ok ? (
                <CheckCircle2 className="mt-0.5 h-4 w-4 text-state-eligible" aria-hidden="true" />
              ) : (
                <XCircle className="mt-0.5 h-4 w-4 text-state-ineligible" aria-hidden="true" />
              )}
              <span className="text-ink-1">
                {c.label}
                <span className="sr-only">: {c.ok ? "ok" : "failed"}</span>
                <span className="ml-1 text-ink-3">— {c.detail}</span>
              </span>
            </li>
          ))}
        </ul>
      )}

      <div className="rounded border border-surface-border bg-surface-1 p-4 text-sm text-ink-2">
        <p className="mb-2 font-medium text-ink-1">Local setup</p>
        <pre className="overflow-x-auto rounded bg-surface-0 p-3 font-mono text-xs">
{`# start the P3B backend
pip install -c apps/ugence-governance-studio/backend/constraints.txt \\
  apps/ugence-governance-studio/backend
python -m ugence_governance_studio_api.cli serve`}
        </pre>
      </div>

      <button
        type="button"
        onClick={() => refetch()}
        className="mt-4 inline-flex items-center gap-2 rounded border border-surface-border bg-surface-2 px-3 py-2 text-sm text-ink-0 hover:bg-surface-3"
      >
        <RefreshCw className={isFetching ? "h-4 w-4 animate-spin" : "h-4 w-4"} aria-hidden="true" />
        Retry compatibility check
      </button>
    </main>
  );
}
