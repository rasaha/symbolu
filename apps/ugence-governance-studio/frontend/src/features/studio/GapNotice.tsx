// The shared gap renderer.
//
// Every v2 service reports a missing dependency the same way, and every screen shows
// it. This component exists so that "the backend says this capability is absent" has
// exactly one appearance across the six screens, and so a screen physically cannot
// render a result without having handled the unavailable case first.
//
// It is deliberately NOT an error state. An absent trust root or an unconfigured
// console is a fact about this deployment, not a fault — styling it as an error would
// tell an operator to go looking for a bug that is not there.
import type { ReactNode } from "react";
import { isUnavailable, type GapAware } from "@/api/types-v2";

export function GapNotice({ gap }: { gap: GapAware }) {
  if (!isUnavailable(gap)) return null;
  return (
    <div
      role="note"
      aria-label="capability unavailable"
      className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-[12px] text-amber-950"
    >
      <div className="font-semibold">
        Not available in this deployment:{" "}
        <span className="font-mono text-[11px]">{gap.capability}</span>
      </div>
      <p className="mt-1 leading-relaxed">{gap.reason}</p>
    </div>
  );
}

/**
 * Render `children` only once the capability is available, and the gap otherwise.
 *
 * The callback receives the narrowed available result, so a screen cannot read a
 * field off an unavailable one by mistake.
 */
export function WithGap({
  gap,
  children,
}: {
  gap: GapAware | undefined;
  children: (available: Record<string, unknown>) => ReactNode;
}) {
  if (gap === undefined) return null;
  if (isUnavailable(gap)) return <GapNotice gap={gap} />;
  return <>{children(gap as unknown as Record<string, unknown>)}</>;
}

/**
 * The Simulate banner.
 *
 * A run cleared by a permissive test hook is not a governance result, and a screen
 * that showed its trace without saying so would present a foregone conclusion as an
 * outcome. This is the loudest thing on that screen for exactly that reason.
 */
export function PermissiveHookBanner({
  permissive,
  configured,
}: {
  permissive: boolean;
  configured: boolean;
}) {
  if (permissive) {
    return (
      <div
        role="alert"
        className="rounded border-2 border-rose-400 bg-rose-50 px-3 py-2 text-[12px] text-rose-950"
      >
        <div className="font-semibold uppercase tracking-wide">
          Not a governance result
        </div>
        <p className="mt-1 leading-relaxed">
          This run was cleared by a permissive test hook, which clears every proposal by
          construction. It demonstrates the execution path; it says nothing about whether
          the action would be permitted.
        </p>
      </div>
    );
  }
  if (!configured) {
    return (
      <div
        role="note"
        aria-label="no governance adapter configured"
        className="rounded border border-slate-300 bg-slate-50 px-3 py-2 text-[12px] text-slate-900"
      >
        <div className="font-semibold">No governance adapter configured</div>
        <p className="mt-1 leading-relaxed">
          The runtime is using its own default, which blocks every consequential
          transition. That is the correct behaviour for an unconfigured deployment, and
          it is why the trace below stops where it does.
        </p>
      </div>
    );
  }
  return null;
}

/** A one-line statement of which registry answered, shown on the Authority screen. */
export function RegistryKindNotice({ kind }: { kind: string }) {
  const inMemory = kind.toLowerCase().includes("inmemory");
  return (
    <div
      role="note"
      aria-label="registry provenance"
      className={
        inMemory
          ? "rounded border border-amber-300 bg-amber-50 px-3 py-2 text-[12px] text-amber-950"
          : "rounded border border-surface-border bg-surface-2 px-3 py-2 text-[12px] text-ink-1"
      }
    >
      <span className="font-semibold">Registry:</span>{" "}
      <span className="font-mono text-[11px]">{kind}</span>
      {inMemory ? (
        <p className="mt-1 leading-relaxed">
          An in-memory registry holds one process&rsquo;s view. What is listed here is not
          an enterprise registry, and an empty list does not mean nothing was issued.
        </p>
      ) : null}
    </div>
  );
}
