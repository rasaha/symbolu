// Screen 3 — Workflow visualization (§13-§15). Graph + accessible list (center)
// synchronized with the node details panel (right). Complete node/edge accounting;
// all dispositions come from the API.
import { useEffect, useMemo } from "react";
import { useParams } from "react-router-dom";
import { useWorkflow } from "@/hooks/queries";
import { useExplorerStore } from "@/state/store";
import { LoadingState, QueryError, EmptyState } from "@/design-system/states";
import { WorkflowGraph } from "./WorkflowGraph";
import { WorkflowNodeList } from "./WorkflowNodeList";
import { NodeDetails } from "./NodeDetails";

export function WorkflowScreen() {
  const { scenarioId } = useParams<{ scenarioId: string }>();
  const { data, isLoading, error } = useWorkflow(scenarioId);
  const selectedNodeId = useExplorerStore((s) => s.selectedNodeId);
  const setSelectedNode = useExplorerStore((s) => s.setSelectedNode);

  const dispositions = useMemo(
    () => new Map((data?.node_dispositions ?? []).map((d) => [d.node_id, d])),
    [data],
  );
  const roleByNode = useMemo(
    () => new Map((data?.role_requirements ?? []).map((r) => [r.source_node_id, r])),
    [data],
  );

  // Default-select the first node once loaded (never leaves the panel empty).
  useEffect(() => {
    if (data && !selectedNodeId && data.nodes.length > 0) {
      setSelectedNode(data.nodes[0].node_id);
    }
  }, [data, selectedNodeId, setSelectedNode]);

  if (isLoading) return <LoadingState label="Loading workflow…" />;
  if (error) return <QueryError error={error} />;
  if (!data) return null;
  if (data.nodes.length === 0)
    return <EmptyState title="No workflow nodes" detail="The workflow contains no nodes." />;

  const selectedNode = data.nodes.find((n) => n.node_id === selectedNodeId);
  const upstream = data.edges.filter((e) => e.target_id === selectedNodeId).map((e) => e.source_id);
  const downstream = data.edges.filter((e) => e.source_id === selectedNodeId).map((e) => e.target_id);

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-lg font-semibold text-ink-0">Workflow</h1>
        <p className="text-xs text-ink-3">
          {data.nodes.length} nodes · {data.edges.length} edges · contract {data.contract_version}
        </p>
      </header>

      <div className="grid gap-4 xl:grid-cols-[1.5fr_1fr]">
        <div className="space-y-4">
          <WorkflowGraph
            nodes={data.nodes}
            edges={data.edges}
            dispositions={dispositions}
            selectedNodeId={selectedNodeId}
            onSelect={setSelectedNode}
          />
          <WorkflowNodeList
            nodes={data.nodes}
            edges={data.edges}
            dispositions={dispositions}
            selectedNodeId={selectedNodeId}
            onSelect={setSelectedNode}
          />
        </div>
        <div className="xl:sticky xl:top-4 xl:self-start">
          <NodeDetails
            node={selectedNode}
            nodeDisposition={selectedNodeId ? dispositions.get(selectedNodeId) : undefined}
            role={selectedNodeId ? roleByNode.get(selectedNodeId) : undefined}
            edgesUpstream={upstream}
            edgesDownstream={downstream}
          />
        </div>
      </div>
    </div>
  );
}
