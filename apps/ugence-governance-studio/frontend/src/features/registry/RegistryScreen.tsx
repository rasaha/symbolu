// Screen 5 — Agent registry (§17). Renders the pinned synthetic registry. Evidence
// is grouped by DECLARED / MEASURED / OBSERVED and always labeled synthetic;
// expired evidence stays visible and flagged.
import { useMemo } from "react";
import { useParams } from "react-router-dom";
import { FlaskConical } from "lucide-react";
import { useRegistry } from "@/hooks/queries";
import type { AgentProfile, CapabilityEvidence } from "@/api/types";
import { displayOrUnresolved } from "@/lib/domain";
import { Badge, Card, Field, Fingerprint, Section } from "@/design-system/primitives";
import { LoadingState, QueryError, EmptyState } from "@/design-system/states";

function evidenceExpired(e: CapabilityEvidence): boolean {
  const vu = typeof e.valid_until === "number" ? e.valid_until : undefined;
  // Logical time of the pinned scenarios is 1_000_000. Anything earlier is stale.
  return vu !== undefined && vu < 1_000_000;
}

function EvidenceRow({ e }: { e: CapabilityEvidence }) {
  const expired = evidenceExpired(e);
  return (
    <tr className="border-b border-surface-border/50">
      <th scope="row" className="py-1 pr-3 text-left font-normal text-ink-1">{e.capability_id}</th>
      <td className="py-1 pr-3">{displayOrUnresolved(e.value)} {e.unit}</td>
      <td className="py-1 pr-3 text-ink-2">{displayOrUnresolved(e.benchmark_id)}</td>
      <td className="py-1 pr-3 text-ink-2">{displayOrUnresolved(e.issuer)}</td>
      <td className="py-1 pr-3">
        {expired ? <Badge tone="ineligible">Expired</Badge> : <Badge tone="eligible">Valid</Badge>}
      </td>
      <td className="py-1"><Fingerprint value={e.evidence_fingerprint} label="evidence" /></td>
    </tr>
  );
}

function AgentCard({ profile, evidence }: { profile: AgentProfile; evidence: CapabilityEvidence[] }) {
  const byClass = useMemo(() => {
    const groups: Record<string, CapabilityEvidence[]> = { DECLARED: [], MEASURED: [], OBSERVED: [] };
    for (const e of evidence) (groups[e.evidence_class] ??= []).push(e);
    return groups;
  }, [evidence]);

  return (
    <Card className="p-4">
      <div className="mb-2 flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-ink-0">{profile.agent_id}</h3>
          <span className="text-[11px] text-ink-3">v{profile.agent_version} · {profile.provider_id}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Badge tone="indeterminate">
            <FlaskConical className="mr-1 h-3 w-3" aria-hidden="true" /> Synthetic
          </Badge>
          <Badge>{profile.status}</Badge>
        </div>
      </div>

      <dl className="mb-3">
        <Field label="Domain">{displayOrUnresolved(profile.supported_domains, "list")}</Field>
        <Field label="Residency">{displayOrUnresolved(profile.residency)}</Field>
        <Field label="Deployment">{displayOrUnresolved(profile.deployment_environment)}</Field>
        <Field label="Security class">{displayOrUnresolved(profile.security_classification)}</Field>
        <Field label="Tools">{displayOrUnresolved(profile.supported_tools, "list")}</Field>
        <Field label="Requested permissions">{displayOrUnresolved(profile.requested_permissions, "list")}</Field>
        <Field label="Max authority">{displayOrUnresolved(profile.maximum_authority_scope)}</Field>
        <Field label="Audit capabilities">{displayOrUnresolved(profile.audit_capabilities, "list")}</Field>
        <Field label="Validity">
          {displayOrUnresolved(profile.valid_from)} → {displayOrUnresolved(profile.valid_until)}
        </Field>
        <Field label="Profile fingerprint">
          <Fingerprint value={profile.profile_fingerprint} label="profile" />
        </Field>
      </dl>

      {(["DECLARED", "MEASURED", "OBSERVED"] as const).map((cls) => {
        const items = byClass[cls] ?? [];
        return (
          <Section key={cls} title={`${cls} evidence`} count={items.length}>
            {items.length === 0 ? (
              <p className="text-xs text-ink-3">None</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[520px] text-xs">
                  <thead>
                    <tr className="text-left text-ink-3">
                      <th scope="col" className="py-1 pr-3">Capability</th>
                      <th scope="col" className="py-1 pr-3">Value</th>
                      <th scope="col" className="py-1 pr-3">Benchmark</th>
                      <th scope="col" className="py-1 pr-3">Issuer</th>
                      <th scope="col" className="py-1 pr-3">Validity</th>
                      <th scope="col" className="py-1">Fingerprint</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((e) => (
                      <EvidenceRow key={e.evidence_id} e={e} />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Section>
        );
      })}
    </Card>
  );
}

export function RegistryScreen() {
  const { scenarioId } = useParams<{ scenarioId: string }>();
  const { data, isLoading, error } = useRegistry(scenarioId);

  if (isLoading) return <LoadingState label="Loading registry…" />;
  if (error) return <QueryError error={error} />;
  const snapshot = data?.registry_snapshot;
  if (!snapshot || snapshot.agent_profiles.length === 0)
    return <EmptyState title="No registered agents" detail="The pinned registry contains no agents." />;

  const evidenceByAgent = new Map<string, CapabilityEvidence[]>();
  for (const e of snapshot.capability_evidence) {
    const key = `${e.agent_id}@${e.agent_version}`;
    (evidenceByAgent.get(key) ?? evidenceByAgent.set(key, []).get(key)!).push(e);
  }

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-lg font-semibold text-ink-0">Agent registry</h1>
        <p className="text-xs text-ink-3">
          {snapshot.agent_profiles.length} synthetic agents · snapshot{" "}
          <Fingerprint value={snapshot.snapshot_digest} label="snapshot" />
        </p>
      </header>
      <div className="grid gap-4 lg:grid-cols-2">
        {snapshot.agent_profiles.map((p) => (
          <AgentCard
            key={`${p.agent_id}@${p.agent_version}`}
            profile={p}
            evidence={evidenceByAgent.get(`${p.agent_id}@${p.agent_version}`) ?? []}
          />
        ))}
      </div>
    </div>
  );
}
