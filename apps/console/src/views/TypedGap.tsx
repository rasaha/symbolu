/**
 * A typed gap: what a view cannot show, with the code and the ruling that say why.
 *
 * The console shows a gap where a data source is not served, never an empty list that
 * a reader could mistake for "nothing exists". The shape follows the studio's screens,
 * which report a typed gap when a seam is unset rather than rendering a blank.
 */
import type { ReactNode } from 'react';

export interface TypedGapProps {
  /** Stable machine-readable code, e.g. CONSOLE_ROUTE_WITHHELD. */
  code: string;
  /** The route or source that is not served. */
  source: string;
  /** The ruling that withholds it, and the one that retired the call. */
  ruling: string;
  /** What the reader would have seen here. */
  children: ReactNode;
}

export function TypedGap({ code, source, ruling, children }: TypedGapProps) {
  return (
    <div
      role="status"
      className="rounded-xl border border-dashed border-slate-500/40 bg-slate-500/5 p-4 text-sm text-slate-300"
    >
      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <span className="px-2 py-0.5 rounded-md border border-slate-500/40 font-mono">{code}</span>
        <span className="font-mono text-slate-400">{source}</span>
        <span className="text-slate-500">{ruling}</span>
      </div>
      <p className="mt-2 text-slate-400">{children}</p>
    </div>
  );
}
