// Controlled What-If Explorer (§24, §25; C2). Only the nine allowlisted bounded
// operations, driven by constrained controls (selects from pinned registry data,
// validated numeric inputs). No arbitrary JSON/policy/URL/code input. The frozen
// scenario is never mutated — the API evaluates a temporary copy and returns the
// modified plan and diff. Request assembly is delegated to the pure, table-tested
// OPERATION_SPECS so the submitted payload is exact and never silently defaulted.
import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { useRegistry, useWhatIf } from "@/hooks/queries";
import { PlanningNote } from "@/components/MaturityBanner";
import { Card, Field, Fingerprint, Section, StatusPill } from "@/design-system/primitives";
import { planState } from "@/lib/domain-p3d";
import { LoadingState, QueryError } from "@/design-system/states";
import { WHAT_IF_OPERATIONS, type WhatIfOperation } from "@/api/types-p3d";
import type { AgentProfile } from "@/api/types";
import {
  OPERATION_SPECS,
  PERMISSION_CHOICES,
  seedDefaults,
  type WhatIfOptions,
} from "./operations";

export function WhatIfScreen() {
  const { scenarioId } = useParams<{ scenarioId: string }>();
  const registry = useRegistry(scenarioId);
  const [op, setOp] = useState<WhatIfOperation>("FORBID_PROVIDER");
  const [submitted, setSubmitted] = useState<{ op: WhatIfOperation; params: Record<string, unknown> } | null>(null);

  const options = useMemo<WhatIfOptions>(() => {
    const profiles = (registry.data?.registry_snapshot.agent_profiles ?? []) as AgentProfile[];
    return {
      providers: [...new Set(profiles.map((p) => p.provider_id))].sort(),
      residencies: [...new Set(profiles.map((p) => p.residency).filter(Boolean))].sort(),
      agentRefs: profiles.map((p) => `${p.agent_id}@${p.agent_version}`),
      permissions: PERMISSION_CHOICES,
    };
  }, [registry.data]);

  const [fields, setFields] = useState<Record<string, string>>(() => seedDefaults("FORBID_PROVIDER", options));

  // When the pinned registry loads, fill any empty select with its first allowed
  // option so the displayed selection equals what will be submitted (never a silent
  // default). Existing user selections and numeric inputs are left untouched.
  useEffect(() => {
    setFields((f) => {
      const seeded = seedDefaults(op, options);
      const merged = { ...f };
      for (const k of Object.keys(seeded)) if (!merged[k]) merged[k] = seeded[k];
      return merged;
    });
  }, [options, op]);

  const changeOp = (next: WhatIfOperation) => {
    setOp(next);
    setSubmitted(null);
    setFields(seedDefaults(next, options)); // drop stale fields from the previous operation
  };
  const set = (k: string, v: string) => setFields((f) => ({ ...f, [k]: v }));

  const spec = OPERATION_SPECS[op];
  const built = spec.build(fields, options);
  const canApply = "params" in built;

  const whatif = useWhatIf(scenarioId, submitted?.op ?? null, submitted?.params ?? null);

  const submit = () => {
    if (!("params" in built)) return;
    setSubmitted({ op, params: built.params }); // exact params only for the current operation
  };
  const reset = () => {
    setSubmitted(null);
    setFields(seedDefaults(op, options));
  };

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-lg font-semibold text-ink-0">Controlled what-if</h1>
      </header>
      <PlanningNote />
      <p className="rounded border border-surface-border bg-surface-2/50 p-3 text-xs text-ink-2" data-testid="whatif-notice">
        What-if analysis evaluates a temporary copied scenario. It does not modify the frozen scenario,
        enterprise policy, registry or any production system.
      </p>

      <Card className="flex flex-wrap items-end gap-3 p-3">
        <div className="flex flex-col gap-1">
          <label htmlFor="op" className="text-[11px] text-ink-3">Perturbation (bounded)</label>
          <select id="op" value={op} onChange={(e) => changeOp(e.target.value as WhatIfOperation)} className="rounded border border-surface-border bg-surface-0 px-2 py-1 text-sm text-ink-1">
            {WHAT_IF_OPERATIONS.map((o) => <option key={o} value={o}>{o}</option>)}
          </select>
        </div>
        <Controls op={op} fields={fields} set={set} options={options} />
        <button type="button" onClick={submit} disabled={!canApply} className="rounded border border-[#6aa9ff] bg-surface-3 px-3 py-1.5 text-sm text-ink-0 hover:bg-surface-2 disabled:opacity-50" data-testid="whatif-apply">
          Apply
        </button>
        {submitted && (
          <button type="button" onClick={reset} className="rounded border border-surface-border px-3 py-1.5 text-sm text-ink-2 hover:bg-surface-2" data-testid="whatif-reset">
            Reset to baseline
          </button>
        )}
        {!canApply && <span className="text-[11px] text-state-ineligible" data-testid="whatif-invalid">{built.error}</span>}
      </Card>

      {whatif.isLoading && <LoadingState label="Evaluating what-if…" />}
      {whatif.error && <QueryError error={whatif.error} />}
      {whatif.data && (
        <div className="space-y-3" data-testid="whatif-result">
          <div className="grid gap-3 sm:grid-cols-2">
            <Card className="p-3">
              <p className="text-xs text-ink-3">Baseline</p>
              <StatusPill descriptor={planState(whatif.data.baseline_state)} />
              <div className="mt-1"><Fingerprint value={whatif.data.baseline_plan.plan_fingerprint} label="baseline" /></div>
            </Card>
            <Card className="p-3">
              <p className="text-xs text-ink-3">Modified (temporary copy)</p>
              <StatusPill descriptor={planState(whatif.data.modified_state)} />
              <div className="mt-1"><Fingerprint value={whatif.data.modified_plan.plan_fingerprint} label="modified" /></div>
            </Card>
          </div>
          <Card className="p-4">
            <Section title="What changed">
              <dl>
                <Field label="Perturbation">{whatif.data.perturbation_applied.operation} {JSON.stringify(whatif.data.perturbation_applied.params)}</Field>
                <Field label="Changed input digests">{Object.keys(whatif.data.changed_input_digests).join(", ") || "none"}</Field>
                <Field label="Assignment changes">{whatif.data.plan_diff.assignment_changes.length}</Field>
                <Field label="Permission changes">{whatif.data.plan_diff.permission_changes.length}</Field>
                <Field label="Fallback changes">{whatif.data.plan_diff.fallback_changes.length}</Field>
                <Field label="State change">{whatif.data.baseline_state} → {whatif.data.modified_state}</Field>
              </dl>
            </Section>
          </Card>
        </div>
      )}
    </div>
  );
}

function Controls({
  op, fields, set, options,
}: {
  op: WhatIfOperation;
  fields: Record<string, string>;
  set: (k: string, v: string) => void;
  options: WhatIfOptions;
}) {
  const spec = OPERATION_SPECS[op];
  if (spec.controls.length === 0) {
    return <span className="text-[11px] text-ink-3">No parameters — advances logical time past evidence validity.</span>;
  }
  return (
    <>
      {spec.controls.map((c) => {
        const id = `wf-${op}-${c.key}`;
        if (c.kind === "select") {
          const opts = c.options(options);
          return (
            <div key={c.key} className="flex flex-col gap-1">
              <label htmlFor={id} className="text-[11px] text-ink-3">{c.label}</label>
              <select id={id} value={fields[c.key] ?? ""} onChange={(e) => set(c.key, e.target.value)} className="rounded border border-surface-border bg-surface-0 px-2 py-1 text-sm text-ink-1">
                {opts.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            </div>
          );
        }
        return (
          <div key={c.key} className="flex flex-col gap-1">
            <label htmlFor={id} className="text-[11px] text-ink-3">{c.label}</label>
            <input
              id={id}
              type="number"
              min={c.min}
              max={c.max}
              step={c.integer ? 1 : "any"}
              value={fields[c.key] ?? ""}
              onChange={(e) => set(c.key, e.target.value)}
              className="w-28 rounded border border-surface-border bg-surface-0 px-2 py-1 text-sm text-ink-1"
            />
          </div>
        );
      })}
    </>
  );
}
