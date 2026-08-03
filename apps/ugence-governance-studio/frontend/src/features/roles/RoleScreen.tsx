// Screen 4 — Role requirements (§16). Compiler / enterprise-policy / AWC-derived
// fields are visibly distinguished with source badges. No field is inferred.
import { Link, useParams } from "react-router-dom";
import { useWorkflow } from "@/hooks/queries";
import type { RoleRequirement } from "@/api/types";
import { displayOrUnresolved } from "@/lib/domain";
import { Badge, Card, Field, Fingerprint, Section } from "@/design-system/primitives";
import { LoadingState, QueryError, EmptyState } from "@/design-system/states";

function SourceBadge({ kind }: { kind: "Compiler" | "Enterprise policy" | "AWC-derived" }) {
  const tone = kind === "Compiler" ? "governance" : kind === "Enterprise policy" ? "authority" : "eligible";
  return <Badge tone={tone}>{kind}</Badge>;
}

export function RoleScreen() {
  const { scenarioId, roleId } = useParams<{ scenarioId: string; roleId: string }>();
  const { data, isLoading, error } = useWorkflow(scenarioId);

  if (isLoading) return <LoadingState label="Loading role…" />;
  if (error) return <QueryError error={error} />;
  const role: RoleRequirement | undefined = data?.role_requirements.find((r) => r.role_id === roleId);
  if (!role) return <EmptyState title="Role not found" detail={`No AI-agent role ${roleId} in this scenario.`} />;

  return (
    <div className="space-y-4">
      <header>
        <div className="mb-1 flex items-center gap-2">
          <h1 className="text-lg font-semibold text-ink-0">{role.role_name}</h1>
          <Badge tone="eligible">AI-agent role</Badge>
        </div>
        <p className="text-sm text-ink-2">{role.role_description}</p>
      </header>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-4">
          <Section title="Identity">
            <dl>
              <Field label="Role ID">{role.role_id}</Field>
              <Field label="Source node">
                <Link className="text-ink-0 underline" to={`/scenarios/${scenarioId}/workflow`}>
                  {role.source_node_id}
                </Link>
              </Field>
              <Field label="Workflow identity">{role.workflow_id}</Field>
              <Field label="Role fingerprint">
                <Fingerprint value={role.role_fingerprint} label="role" />
              </Field>
            </dl>
          </Section>

          <Section title="Functional requirements">
            <dl>
              <Field label="Required capabilities">
                {displayOrUnresolved(role.required_capabilities, "list")} <SourceBadge kind="Compiler" />
              </Field>
              <Field label="Optional capabilities">{displayOrUnresolved(role.optional_capabilities, "list")}</Field>
              <Field label="Domain">{displayOrUnresolved(role.domain_requirements, "list")}</Field>
              <Field label="Supported tools">{displayOrUnresolved(role.required_tools, "list")}</Field>
              <Field label="Input contracts">{displayOrUnresolved(role.input_contract_refs, "list")}</Field>
              <Field label="Output contracts">{displayOrUnresolved(role.output_contract_refs, "list")}</Field>
            </dl>
          </Section>
        </Card>

        <Card className="p-4">
          <Section title="Enterprise constraints">
            <dl>
              <Field label="Provider rules">
                {displayOrUnresolved(role.provider_constraints, "list")} <SourceBadge kind="Enterprise policy" />
              </Field>
              <Field label="Residency">{displayOrUnresolved(role.residency_constraints, "list")}</Field>
              <Field label="Deployment">{displayOrUnresolved(role.deployment_constraints, "list")}</Field>
              <Field label="Data classification">{displayOrUnresolved(role.data_classification)}</Field>
              <Field label="Security floor">{displayOrUnresolved(role.required_security_classification)}</Field>
              <Field label="Audit requirement">{displayOrUnresolved(role.required_audit_capabilities, "list")}</Field>
              <Field label="Evidence classes">{displayOrUnresolved(role.required_evidence_classes, "list")}</Field>
              <Field label="Quality floor">{displayOrUnresolved(role.minimum_quality_constraint)}</Field>
              <Field label="Latency ceiling">{displayOrUnresolved(role.maximum_latency_constraint)}</Field>
              <Field label="Cost ceiling">{displayOrUnresolved(role.maximum_cost_constraint)}</Field>
            </dl>
          </Section>

          <Section title="Authority & permission boundaries">
            <dl>
              <Field label="Required permissions">{displayOrUnresolved(role.required_permissions, "list")}</Field>
              <Field label="Prohibited permissions">{displayOrUnresolved(role.prohibited_permissions, "list")}</Field>
              <Field label="Authority ceiling">{displayOrUnresolved(role.authority_ceiling)}</Field>
              <Field label="Human review">{displayOrUnresolved(role.human_review_requirement)}</Field>
            </dl>
          </Section>

          <Section title="Provenance">
            <dl>
              <Field label="Compiler contract">
                {role.contract_version} <SourceBadge kind="AWC-derived" />
              </Field>
              <Field label="Source package digest">
                <Fingerprint value={role.source_package_digest} label="source package" />
              </Field>
              <Field label="Policy references">{displayOrUnresolved(role.policy_refs, "list")}</Field>
            </dl>
          </Section>
        </Card>
      </div>

      <Link
        to={`/scenarios/${scenarioId}/eligibility`}
        className="inline-flex rounded border border-surface-border bg-surface-2 px-3 py-2 text-sm text-ink-0 hover:bg-surface-3"
      >
        View eligibility for this role →
      </Link>
    </div>
  );
}
