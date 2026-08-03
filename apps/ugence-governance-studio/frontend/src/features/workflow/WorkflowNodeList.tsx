// Accessible, synchronized workflow representation (§14). Keyboard-navigable list
// mirroring the graph: name, kind, disposition, dependencies. Selection is kept in
// sync with the graph via the shared store. State is never color-only.
import type { NodeDisposition, WorkflowEdge, WorkflowNode } from "@/api/types";
import { disposition } from "@/lib/domain";
import { StatusPill } from "@/design-system/primitives";

export function WorkflowNodeList({
  nodes,
  edges,
  dispositions,
  selectedNodeId,
  onSelect,
}: {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  dispositions: Map<string, NodeDisposition>;
  selectedNodeId: string | null;
  onSelect: (id: string) => void;
}) {
  const upstream = (id: string) => edges.filter((e) => e.target_id === id).map((e) => e.source_id);
  const downstream = (id: string) => edges.filter((e) => e.source_id === id).map((e) => e.target_id);

  return (
    <section aria-label="Workflow nodes (accessible list)" className="rounded-lg border border-surface-border bg-surface-1">
      <h3 className="border-b border-surface-border px-3 py-2 text-xs font-semibold uppercase tracking-wide text-ink-2">
        Workflow nodes
        <span className="ml-2 rounded bg-surface-2 px-1.5 py-0.5 text-[10px]">{nodes.length}</span>
      </h3>
      <ul className="divide-y divide-surface-border/60">
        {nodes.map((n) => {
          const disp = dispositions.get(n.node_id);
          const d = disposition(disp?.disposition ?? "");
          const selected = n.node_id === selectedNodeId;
          return (
            <li key={n.node_id}>
              <button
                type="button"
                aria-pressed={selected}
                onClick={() => onSelect(n.node_id)}
                className={
                  "flex w-full flex-col gap-1 px-3 py-2 text-left hover:bg-surface-2 " +
                  (selected ? "bg-surface-2" : "")
                }
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-ink-0">{n.label || n.node_id}</span>
                  <StatusPill descriptor={d} />
                </span>
                <span className="text-[11px] text-ink-3">
                  {n.kind} · in: {upstream(n.node_id).length} · out: {downstream(n.node_id).length}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
