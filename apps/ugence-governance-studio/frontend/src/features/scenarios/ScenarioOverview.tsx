// Screen 2 — Scenario overview (§12). Metadata, versions, verification, digests,
// maturity and presentation counts. No ranking or team-selection metrics.
import { useParams, Link } from "react-router-dom";
import { CheckCircle2, XCircle } from "lucide-react";
import { useEligibility, useRegistry, useScenario, useVersion, useWorkflow } from "@/hooks/queries";
import { Card, Field, Fingerprint, Section } from "@/design-system/primitives";
import { EligibilityMeaningNote } from "@/components/MaturityBanner";
import { LoadingState, QueryError } from "@/design-system/states";

function Metric({ label, value, to }: { label: string; value: number | string; to?: string }) {
  const inner = (
    <Card className="p-3">
      <div className="text-2xl font-semibold text-ink-0">{value}</div>
      <div className="mt-1 text-xs text-ink-2">{label}</div>
    </Card>
  );
  return to ? (
    <Link to={to} className="block rounded-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-[#6aa9ff]">
      {inner}
    </Link>
  ) : (
    inner
  );
}

export function ScenarioOverview() {
  const { scenarioId } = useParams<{ scenarioId: string }>();
  const scenario = useScenario(scenarioId);
  const workflow = useWorkflow(scenarioId);
  const registry = useRegistry(scenarioId);
  const eligibility = useEligibility(scenarioId);
  const version = useVersion();

  if (scenario.isLoading) return <LoadingState label="Loading scenario…" />;
  if (scenario.error) return <QueryError error={scenario.error} />;
  if (!scenario.data) return null;

  const meta = scenario.data.metadata;
  const nodes = workflow.data?.nodes.length ?? 0;
  const edges = workflow.data?.edges.length ?? 0;
  const roles = workflow.data?.role_requirements.length ?? 0;
  const nonAgent = workflow.data
    ? workflow.data.node_dispositions.filter((d) => !d.is_agent_role).length
    : 0;
  const agents = registry.data?.registry_snapshot.agent_profiles.length ?? 0;
  const reports = eligibility.data?.role_reports ?? [];
  const eligible = reports.reduce((n, r) => n + r.eligible_agent_ids.length, 0);
  const ineligible = reports.reduce((n, r) => n + r.eliminated_agent_ids.length, 0);
  const indeterminate = reports.reduce((n, r) => n + r.indeterminate_agent_ids.length, 0);
  const verification = eligibility.data?.verification;

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-lg font-semibold text-ink-0">{meta.title}</h1>
        <p className="mt-1 text-sm text-ink-2">{meta.description}</p>
        {scenario.data.narrative && (
          <p className="mt-1 text-sm text-ink-2">{scenario.data.narrative}</p>
        )}
      </header>

      <EligibilityMeaningNote />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="Workflow nodes" value={nodes} to={`/scenarios/${scenarioId}/workflow`} />
        <Metric label="Workflow edges" value={edges} to={`/scenarios/${scenarioId}/workflow`} />
        <Metric label="AI-agent roles" value={roles} to={`/scenarios/${scenarioId}/workflow`} />
        <Metric label="Non-agent steps" value={nonAgent} />
        <Metric label="Registered agents" value={agents} to={`/scenarios/${scenarioId}/registry`} />
        <Metric label="Eligible pairs" value={eligible} to={`/scenarios/${scenarioId}/eligibility`} />
        <Metric label="Ineligible pairs" value={ineligible} to={`/scenarios/${scenarioId}/eligibility`} />
        <Metric label="Indeterminate pairs" value={indeterminate} />
      </div>

      <Card className="p-4">
        <Section title="Identity & versions">
          <dl>
            <Field label="Scenario ID">{meta.scenario_id}</Field>
            <Field label="Domain">{meta.domain}</Field>
            <Field label="Workflow identity">{workflow.data?.workflow_identity ?? "—"}</Field>
            <Field label="Workflow contract">{meta.workflow_contract_version}</Field>
            <Field label="API contract">{version.data?.api_contract_version ?? "—"}</Field>
            <Field label="AWC version">{version.data?.awc_distribution_version ?? "—"}</Field>
            <Field label="Compiler version">
              {version.data?.compiler_distribution_version ?? "consumed via AWC adapter"}
            </Field>
            <Field label="Fixture version">{meta.fixture_version ?? "—"}</Field>
          </dl>
        </Section>

        <Section title="Deterministic verification">
          {verification ? (
            <div
              className="flex items-center gap-2 text-sm"
              data-testid="verification-state"
            >
              {verification.match ? (
                <CheckCircle2 className="h-4 w-4 text-state-eligible" aria-hidden="true" />
              ) : (
                <XCircle className="h-4 w-4 text-state-ineligible" aria-hidden="true" />
              )}
              <span className="text-ink-1">
                Observed eligibility fingerprint {verification.match ? "matches" : "does NOT match"} the
                frozen expected value
              </span>
            </div>
          ) : (
            <p className="text-sm text-ink-2">Verification not reported.</p>
          )}
          <dl className="mt-2">
            <Field label="Expected fingerprint">
              <Fingerprint value={verification?.expected_fingerprint} label="expected" />
            </Field>
            <Field label="Observed fingerprint">
              <Fingerprint value={verification?.observed_fingerprint} label="observed" />
            </Field>
            <Field label="Workflow adaptation">
              <Fingerprint value={workflow.data?.adaptation_fingerprint} label="adaptation" />
            </Field>
            <Field label="Registry snapshot">
              <Fingerprint value={registry.data?.registry_snapshot.snapshot_digest} label="registry" />
            </Field>
          </dl>
        </Section>

        <Section title="Maturity">
          <p className="text-sm text-ink-2">{scenario.data.synthetic_data_notice}</p>
        </Section>
      </Card>
    </div>
  );
}
