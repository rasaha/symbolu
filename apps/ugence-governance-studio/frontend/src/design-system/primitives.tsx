// Small, accessible presentation primitives. State is never conveyed by color
// alone — every status carries a glyph and an accessible label (§23, §24).
import { clsx } from "clsx";
import type { ReactNode } from "react";
import type { Descriptor } from "@/lib/domain";

const TONE_CLASSES: Record<string, string> = {
  eligible: "text-state-eligible border-state-eligible/40 bg-state-eligible/10",
  ineligible: "text-state-ineligible border-state-ineligible/40 bg-state-ineligible/10",
  indeterminate: "text-state-indeterminate border-state-indeterminate/40 bg-state-indeterminate/10",
  invalid: "text-state-invalid border-state-invalid/40 bg-state-invalid/10",
  authority: "text-state-authority border-state-authority/40 bg-state-authority/10",
  review: "text-state-review border-state-review/40 bg-state-review/10",
  governance: "text-state-governance border-state-governance/40 bg-state-governance/10",
  deterministic: "text-ink-2 border-surface-border bg-surface-2",
  neutral: "text-ink-2 border-surface-border bg-surface-2",
};

export function StatusPill({ descriptor, title }: { descriptor: Descriptor; title?: string }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-xs font-medium",
        TONE_CLASSES[descriptor.tone] ?? TONE_CLASSES.neutral,
      )}
      title={title ?? descriptor.code}
    >
      <span aria-hidden="true">{descriptor.glyph}</span>
      <span>{descriptor.label}</span>
      <span className="sr-only"> ({descriptor.code})</span>
    </span>
  );
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: string }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded border px-1.5 py-0.5 text-[11px] font-medium",
        TONE_CLASSES[tone] ?? TONE_CLASSES.neutral,
      )}
    >
      {children}
    </span>
  );
}

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={clsx("rounded-lg border border-surface-border bg-surface-1", className)}>{children}</div>
  );
}

export function Section({ title, children, count }: { title: string; children: ReactNode; count?: number }) {
  return (
    <section className="mb-4">
      <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-ink-2">
        {title}
        {count !== undefined && (
          <span className="rounded bg-surface-2 px-1.5 py-0.5 text-[10px] text-ink-2">{count}</span>
        )}
      </h3>
      {children}
    </section>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[minmax(9rem,11rem)_1fr] gap-2 border-b border-surface-border/50 py-1.5 text-sm last:border-0">
      <dt className="text-ink-3">{label}</dt>
      <dd className="break-words text-ink-1">{children}</dd>
    </div>
  );
}

export function Fingerprint({ value, label }: { value: string | null | undefined; label?: string }) {
  if (!value) return <span className="text-ink-3">—</span>;
  const short = value.replace(/^sha256:/, "");
  return (
    <code
      className="font-mono text-[11px] text-ink-2"
      title={value}
      aria-label={`${label ?? "fingerprint"} ${value}`}
    >
      {short.length > 20 ? `${short.slice(0, 12)}…${short.slice(-6)}` : short}
    </code>
  );
}
