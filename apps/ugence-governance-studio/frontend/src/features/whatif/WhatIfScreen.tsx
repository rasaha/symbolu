// Controlled What-If Explorer (§24, §25). Only the nine allowlisted bounded
// operations, driven by constrained controls (dropdowns from pinned data,
// validated numeric inputs). No arbitrary JSON/policy/URL/code input. The frozen
// scenario is never mutated — the API evaluates a temporary copy.
import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { useRegistry, useWhatIf } from "@/hooks/queries";
import { PlanningNote } from "@/components/MaturityBanner";
import { Card, Field, Fingerprint, Section, StatusPill } from "@/design-system/primitives";
import { planState } from "@/lib/domain-p3d";
import { LoadingState, QueryError } from "@/design-system/states";
import { WHAT_IF_OPERATIONS, type WhatIfOperation } from "@/api/types-p3d";
import type { AgentProfile } from "@/api/types";

const PERMISSION_CHOICES = ["read_context", "write_context", "invoke_tool"];

export function WhatIfScreen() {
  const { scenarioId } = useParams<{ scenarioId: string }>();
  const registry = useRegistry(scenarioId);
  const [op, setOp] = useState<WhatIfOperation>("FORBID_PROVIDER");
  const [submitted, setSubmitted] = useState<{ op: WhatIfOperation; params: Record<string, unknown> } | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});

  const profiles = useMemo(
    () => (registry.data?.registry_snapshot.agent_profiles ?? []) as AgentProfile[],
    [registry.data],
  );
  const providers = useMemo(() => [...new Set(profiles.map((p) => p.provider_id))].sort(), [profiles]);
  const residencies = useMemo(() => [...new Set(profiles.map((p) => p.residency).filter(Boolean))].sort(), [profiles]);
  const agents = useMemo(() => profiles.map((p) => ({ id: p.agent_id, v: p.agent_version })), [profiles]);

  const set = (k: string, v: string) => setFields((f) => ({ ...f, [k]: v }));
  const whatif = useWhatIf(scenarioId, submitted?.op ?? null, submitted?.params ?? null);

  function buildParams(): Record<string, unknown> | null {
    switch (op) {
      case "FORBID_PROVIDER":
        return { provider: fields.provider || providers[0] };
      case "REQUIRE_RESIDENCY":
        return { residency: fields.residency || residencies[0] || "IN" };
      case "TIGHTEN_COST_CEILING":
      case "TIGHTEN_LATENCY_CEILING": {
        const n = Number(fields.ceiling);
        if (!Number.isFinite(n) || n < 0) return null;
        return { ceiling: n };
      }
      case "REVOKE_AGENT_VERSION": {
        const a = fields.agent || (agents[0] && `${agents[0].id}@${agents[0].v}`);
        return a ? { agent_version: a } : null;
      }
      case "EXPIRE_EVIDENCE":
        return {};
      case "TIGHTEN_PERMISSION_POLICY":
        return { permission: fields.permission || PERMISSION_CHOICES[0] };
      case "TIGHTEN_PROVIDER_CONCENTRATION": {
        const n = Number(fields.limit_pct);
        if (!Number.isInteger(n) || n < 0 || n > 100) return null;
        return { limit_pct: n };
      }
      case "REMOVE_CANDIDATE": {
        const sel = fields.candidate || (agents[0] && `${agents[0].id}@${agents[0].v}`);
        if (!sel) return null;
        const [agent_id, agent_version] = sel.split("@");
        return { agent_id, agent_version };
      }
      default:
        return null;
    }
  }

  const submit = () => {
    const params = buildParams();
    if (params === null) return;
    setSubmitted({ op, params });
  };
  const reset = () => {
    setSubmitted(null);
    setFields({});
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
          <select id="op" value={op} onChange={(e) => { setOp(e.target.value as WhatIfOperation); setFields({}); }} className="rounded border border-surface-border bg-surface-0 px-2 py-1 text-sm text-ink-1">
            {WHAT_IF_OPERATIONS.map((o) => <option key={o} value={o}>{o}</option>)}
          </select>
        </div>
        <Controls op={op} fields={fields} set={set} providers={providers} residencies={residencies} agents={agents} />
        <button type="button" onClick={submit} className="rounded border border-[#6aa9ff] bg-surface-3 px-3 py-1.5 text-sm text-ink-0 hover:bg-surface-2" data-testid="whatif-apply">
          Apply
        </button>
        {submitted && (
          <button type="button" onClick={reset} className="rounded border border-surface-border px-3 py-1.5 text-sm text-ink-2 hover:bg-surface-2" data-testid="whatif-reset">
            Reset to baseline
          </button>
        )}
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
  op, fields, set, providers, residencies, agents,
}: {
  op: WhatIfOperation;
  fields: Record<string, string>;
  set: (k: string, v: string) => void;
  providers: string[];
  residencies: string[];
  agents: { id: string; v: string }[];
}) {
  const sel = (id: string, key: string, opts: { value: string; label: string }[]) => (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-[11px] text-ink-3">{key}</label>
      <select id={id} value={fields[key] ?? ""} onChange={(e) => set(key, e.target.value)} className="rounded border border-surface-border bg-surface-0 px-2 py-1 text-sm text-ink-1">
        {opts.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
  const numField = (id: string, key: string, label: string) => (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-[11px] text-ink-3">{label}</label>
      <input id={id} type="number" min={0} value={fields[key] ?? ""} onChange={(e) => set(key, e.target.value)} className="w-28 rounded border border-surface-border bg-surface-0 px-2 py-1 text-sm text-ink-1" />
    </div>
  );

  switch (op) {
    case "FORBID_PROVIDER":
      return sel("f-provider", "provider", providers.map((p) => ({ value: p, label: p })));
    case "REQUIRE_RESIDENCY":
      return sel("f-residency", "residency", [...residencies, "IN"].map((r) => ({ value: r, label: r })));
    case "TIGHTEN_COST_CEILING":
    case "TIGHTEN_LATENCY_CEILING":
      return numField("f-ceiling", "ceiling", "ceiling");
    case "REVOKE_AGENT_VERSION":
      return sel("f-agentv", "agent", agents.map((a) => ({ value: `${a.id}@${a.v}`, label: `${a.id}@${a.v}` })));
    case "EXPIRE_EVIDENCE":
      return <span className="text-[11px] text-ink-3">Advances logical time past evidence validity.</span>;
    case "TIGHTEN_PERMISSION_POLICY":
      return sel("f-perm", "permission", PERMISSION_CHOICES.map((p) => ({ value: p, label: p })));
    case "TIGHTEN_PROVIDER_CONCENTRATION":
      return numField("f-pct", "limit_pct", "limit %");
    case "REMOVE_CANDIDATE":
      return sel("f-cand", "candidate", agents.map((a) => ({ value: `${a.id}@${a.v}`, label: `${a.id}@${a.v}` })));
    default:
      return null;
  }
}
