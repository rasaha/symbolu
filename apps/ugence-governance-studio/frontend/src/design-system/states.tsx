// Explicit loading / error / empty states (§25). An empty result is NEVER
// rendered as success, and distinct failure kinds (not-ready, fingerprint
// mismatch, missing scenario, network) are visually distinct.
import type { ReactNode } from "react";
import { AlertTriangle, Loader2, Inbox } from "lucide-react";
import { ApiClientError } from "@/api/client";

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex items-center gap-3 p-6 text-ink-2">
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function EmptyState({ title, detail }: { title: string; detail?: string }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-surface-border p-8 text-center text-ink-2">
      <Inbox className="h-5 w-5" aria-hidden="true" />
      <p className="font-medium text-ink-1">{title}</p>
      {detail && <p className="text-sm">{detail}</p>}
    </div>
  );
}

export function ErrorState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div
      role="alert"
      className="flex flex-col gap-2 rounded-lg border border-state-ineligible/40 bg-state-ineligible/10 p-6 text-ink-1"
    >
      <div className="flex items-center gap-2 font-semibold text-state-ineligible">
        <AlertTriangle className="h-4 w-4" aria-hidden="true" />
        {title}
      </div>
      {children && <div className="text-sm text-ink-2">{children}</div>}
    </div>
  );
}

export function QueryError({ error }: { error: unknown }) {
  if (error instanceof ApiClientError) {
    if (error.status === 0) return <ErrorState title="Backend unavailable">The Governance Studio API is unreachable. Confirm the backend is running.</ErrorState>;
    if (error.status === 404) return <ErrorState title="Not found">{error.message}</ErrorState>;
    if (error.status === 503) return <ErrorState title="Backend not ready">{error.message}</ErrorState>;
    return (
      <ErrorState title={`Request failed (${error.status})`}>
        {error.message}
        {error.requestId && <span className="ml-1 font-mono text-[11px]">[{error.requestId}]</span>}
      </ErrorState>
    );
  }
  return <ErrorState title="Unexpected error">{error instanceof Error ? error.message : String(error)}</ErrorState>;
}
