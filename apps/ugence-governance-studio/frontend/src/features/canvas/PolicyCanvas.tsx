// The Ugence-owned studio canvas.
//
// React Flow renders the graph; the node types are ours and the registry is closed.
// `nodeTypes` is built from the registry, so a kind that is not in the registry has
// no renderer and cannot appear — the closure is structural, not a runtime check that
// could be skipped.
//
// The canvas is a VIEW of a PolicyPack. It does not compile, validate or decide; the
// Policy screen sends the pack to the compiler for that.
import { useMemo } from "react";
import ReactFlow, {
  Background,
  Controls,
  Handle,
  MiniMap,
  Position,
  type Edge,
  type Node,
  type NodeProps,
} from "reactflow";
import "reactflow/dist/style.css";

import {
  allDescriptors,
  descriptorFor,
  isNodeKind,
  type NodeKind,
} from "./nodeRegistry";
import type { PolicyGraph } from "./mapper";

interface GovernanceNodeData {
  label: string;
  description: string;
  enabled: boolean;
  kind: NodeKind;
}

function GovernanceNode({ data }: NodeProps<GovernanceNodeData>) {
  const descriptor = descriptorFor(data.kind);
  return (
    <div
      className={`rounded border px-3 py-2 text-[12px] shadow-sm ${descriptor.tone} ${
        data.enabled ? "" : "opacity-50"
      }`}
      title={descriptor.description}
      data-testid={`canvas-node-${data.kind}`}
    >
      <Handle type="target" position={Position.Left} />
      <div className="text-[10px] font-semibold uppercase tracking-wide opacity-70">
        {descriptor.label}
      </div>
      <div className="mt-0.5 max-w-[200px] truncate font-medium">{data.label}</div>
      {data.enabled ? null : (
        <div className="mt-0.5 text-[10px] font-semibold uppercase">disabled</div>
      )}
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

/** One renderer per registry entry. A kind outside the registry has no renderer. */
const nodeTypes = Object.fromEntries(
  allDescriptors().map((d) => [d.kind, GovernanceNode]),
) as Record<string, typeof GovernanceNode>;

export function CanvasLegend() {
  return (
    <ul className="flex flex-wrap gap-2" aria-label="canvas node kinds">
      {allDescriptors().map((d) => (
        <li
          key={d.kind}
          className={`rounded border px-2 py-1 text-[11px] ${d.tone}`}
          title={d.description}
        >
          <span className="font-semibold">{d.label}</span>{" "}
          <span className="font-mono text-[10px] opacity-70">{d.objectType}</span>
        </li>
      ))}
    </ul>
  );
}

export function PolicyCanvas({ graph }: { graph: PolicyGraph }) {
  const nodes: Node<GovernanceNodeData>[] = useMemo(
    () =>
      graph.nodes
        // Defence in depth: the mapper only emits registry kinds, and anything else
        // is dropped here rather than handed to React Flow without a renderer.
        .filter((n) => isNodeKind(n.kind))
        .map((n) => ({
          id: n.id,
          type: n.kind,
          position: n.position,
          data: {
            label: n.label,
            description: n.description,
            enabled: n.enabled,
            kind: n.kind,
          },
        })),
    [graph],
  );

  const edges: Edge[] = useMemo(
    () => graph.edges.map((e) => ({ id: e.id, source: e.source, target: e.target })),
    [graph],
  );

  return (
    <div
      className="h-[520px] w-full rounded border border-surface-border bg-surface-1"
      data-testid="policy-canvas"
      role="group"
      aria-label={`Policy pack canvas: ${nodes.length} governance objects, ${edges.length} relationships`}
    >
      {/*
        The canvas is a picture, but it is not `role="img"`: React Flow's controls are
        focusable, and an img containing focusable descendants is both an axe violation
        and a lie about the content. Worse, it would reduce the whole graph to one
        label for a screen-reader user.

        So the region is a labelled group, and the real content is offered as a list
        that assistive technology can actually walk. A canvas whose content is only
        reachable by looking at it is not a governance surface anyone can review.
      */}
      <ul className="sr-only">
        {nodes.map((n) => (
          <li key={n.id}>
            {descriptorFor(n.data.kind).label}: {n.data.label}
            {n.data.enabled ? "" : " (disabled)"}
            {n.data.description ? `. ${n.data.description}` : ""}
          </li>
        ))}
      </ul>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        proOptions={{ hideAttribution: false }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
      >
        <Background />
        <Controls showInteractive={false} />
        <MiniMap pannable zoomable />
      </ReactFlow>
    </div>
  );
}
