// Shared frame for the six studio screens: a title, a one-line statement of what the
// screen does NOT do, and the body. The disclaimer is a prop rather than boilerplate
// because it differs per screen and each one is load-bearing.
import type { ReactNode } from "react";

export function ScreenFrame({
  title,
  subtitle,
  neverDoes,
  children,
}: {
  title: string;
  subtitle: string;
  neverDoes: string;
  children: ReactNode;
}) {
  return (
    <section className="space-y-4">
      <header className="space-y-1">
        <h1 className="text-base font-semibold tracking-tight text-ink-0">{title}</h1>
        <p className="text-[12px] text-ink-2">{subtitle}</p>
        <p className="text-[11px] font-medium text-ink-3">{neverDoes}</p>
      </header>
      {children}
    </section>
  );
}

export function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded border border-surface-border bg-surface-1 p-3">
      <h2 className="mb-2 text-[12px] font-semibold text-ink-1">{title}</h2>
      {children}
    </div>
  );
}

export function ActionButton({
  onClick,
  disabled,
  children,
}: {
  onClick: () => void;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="rounded border border-surface-border bg-surface-2 px-3 py-1.5 text-[12px] font-medium text-ink-0 hover:bg-surface-3 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {children}
    </button>
  );
}

export function Json({ value, label }: { value: unknown; label: string }) {
  return (
    <div>
      <div className="mb-1 text-[11px] font-medium text-ink-2">{label}</div>
      <pre className="max-h-72 overflow-auto rounded bg-surface-2 p-2 font-mono text-[11px] leading-relaxed text-ink-1">
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  );
}
