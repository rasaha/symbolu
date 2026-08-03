// Node details panel (§15). API-provided values only. Source provenance is
// visibly distinguished; unresolved values render honestly (Not supplied /
// None), never synthesized.
import { Link, useParams } from "react-router-dom";
import type { NodeDisposition, RoleRequirement, WorkflowNode } from "@/api/types";
import { disposition, displayOrUnresolved } from "@/lib/domain";
import { Badge, Field, Fingerprint, Section, StatusPill } from "@/design-system/primitives";
import { EmptyState } from "@/design-system/states";

export function NodeDetails({
  node,
  nodeDisposition,
  role,
  edgesUpstream,
  edgesDownstream,
}: {
  node: WorkflowNode | undefined;
  nodeDisposition: NodeDisposition | undefined;
  role: RoleRequirement | undefined;
  edgesUpstream: string[];
  edgesDownstream: string[];
}) {
  const { scenarioId } = useParams<{ scenarioId: string }>();
  if (!node) {
    return <EmptyState title="No node selected" detail="Select a workflow node to see its details." />;
  }
  const d = disposition(nodeDisposition?.disposition ?? "");

  return (
    <div className="rounded-lg border border-surface-border bg-surface-1 p-4" aria-live="polite">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-ink-0">{node.label || node.node_id}</h3>
          <code className="font-mono text-[11px] text-ink-3">{node.node_id}</code>
        </div>
        <StatusPill descriptor={d} />
      </div>

      <Section title="Disposition (AWC-derived)">
        <dl>
          <Field label="Disposition">
            {d.label} <Badge tone="governance">AWC-derived</Badge>
          </Field>
          <Field label="Reason codes">{displayOrUnresolved(nodeDisposition?.reason_codes, "list")}</Field>
          <Field label="Is agent role">{nodeDisposition?.is_agent_role ? "Yes" : "No"}</Field>
        </dl>
      </Section>

      <Section title="Compiler-derived workflow semantics">
        <dl>
          <Field label="Node kind">
            {node.kind} <Badge>Compiler</Badge>
          </Field>
          <Field label="Semantic purpose">{displayOrUnresolved(node.owning_capability)}</Field>
          <Field label="Authority type">{displayOrUnresolved(node.authority_type)}</Field>
          <Field label="Failure behavior">{displayOrUnresolved(node.failure_behavior)}</Field>
          <Field label="Output contract">{displayOrUnresolved(node.output_contract)}</Field>
          <Field label="Input objects">{displayOrUnresolved(node.input_object_ids, "list")}</Field>
          <Field label="Audit requirements">{displayOrUnresolved(node.audit_requirements, "list")}</Field>
        </dl>
      </Section>

      <Section title="Dependencies">
        <dl>
          <Field label="Upstream">{displayOrUnresolved(edgesUpstream, "list")}</Field>
          <Field label="Downstream">{displayOrUnresolved(edgesDownstream, "list")}</Field>
        </dl>
      </Section>

      {role && (
        <Section title="AI-agent role">
          <p className="mb-2 text-sm text-ink-2">
            This node is AI-agent eligible. Its full role requirements are shown on the role page.
          </p>
          <Link
            to={`/scenarios/${scenarioId}/roles/${role.role_id}`}
            className="inline-flex rounded border border-surface-border bg-surface-2 px-3 py-1.5 text-sm text-ink-0 hover:bg-surface-3"
          >
            View role requirements → {role.role_name}
          </Link>
          <dl className="mt-2">
            <Field label="Role fingerprint">
              <Fingerprint value={role.role_fingerprint} label="role" />
            </Field>
          </dl>
        </Section>
      )}
    </div>
  );
}
