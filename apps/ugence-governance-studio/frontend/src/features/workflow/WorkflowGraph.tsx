// Workflow graph (§13). Deterministic layered SVG. Every node and edge comes from
// the API; dispositions are the API-authoritative values. Nodes are selectable by
// mouse and keyboard; a synchronized accessible list (WorkflowNodeList) is the
// primary keyboard path. Zoom/pan via scaling + a scrollable region; fit-to-view.
import { useMemo, useState } from "react";
import { ZoomIn, ZoomOut, Maximize2 } from "lucide-react";
import type { NodeDisposition, WorkflowEdge, WorkflowNode } from "@/api/types";
import { disposition, DISPOSITIONS } from "@/lib/domain";
import { computeLayout } from "./layout";

const TONE_HEX: Record<string, string> = {
  eligible: "#1f9d6b",
  ineligible: "#c2453a",
  indeterminate: "#c08a2e",
  invalid: "#7a5cd0",
  authority: "#2f6fb0",
  review: "#b06fb0",
  governance: "#3a8f96",
  deterministic: "#6b7280",
};

export function WorkflowGraph({
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
  const layout = useMemo(() => computeLayout(nodes, edges), [nodes, edges]);
  const [scale, setScale] = useState(1);
  const nodeById = useMemo(() => new Map(nodes.map((n) => [n.node_id, n])), [nodes]);

  return (
    <div className="rounded-lg border border-surface-border bg-surface-1">
      <div className="flex items-center justify-between border-b border-surface-border px-3 py-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-ink-2">Workflow graph</span>
        <div className="flex items-center gap-1" role="group" aria-label="Graph zoom controls">
          <button type="button" aria-label="Zoom out" className="rounded p-1 hover:bg-surface-2" onClick={() => setScale((s) => Math.max(0.4, +(s - 0.15).toFixed(2)))}>
            <ZoomOut className="h-4 w-4" aria-hidden="true" />
          </button>
          <button type="button" aria-label="Fit to view" className="rounded p-1 hover:bg-surface-2" onClick={() => setScale(1)}>
            <Maximize2 className="h-4 w-4" aria-hidden="true" />
          </button>
          <button type="button" aria-label="Zoom in" className="rounded p-1 hover:bg-surface-2" onClick={() => setScale((s) => Math.min(2, +(s + 0.15).toFixed(2)))}>
            <ZoomIn className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </div>

      <div className="max-h-[460px] overflow-auto p-2" role="region" aria-label="Workflow graph (visual). Use the node list below for keyboard access.">
        <svg
          width={layout.width * scale}
          height={layout.height * scale}
          viewBox={`0 0 ${layout.width} ${layout.height}`}
          className="min-w-full"
          aria-hidden="true"
        >
          {edges.map((e) => {
            const a = layout.positions.get(e.source_id);
            const b = layout.positions.get(e.target_id);
            if (!a || !b) return null;
            return (
              <line
                key={e.edge_id}
                x1={a.x + 170}
                y1={a.y + 26}
                x2={b.x}
                y2={b.y + 26}
                stroke="#39425a"
                strokeWidth={1.5}
                markerEnd="url(#arrow)"
              />
            );
          })}
          <defs>
            <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">
              <path d="M0,0 L7,3 L0,6 Z" fill="#39425a" />
            </marker>
          </defs>
          {nodes.map((n) => {
            const p = layout.positions.get(n.node_id);
            if (!p) return null;
            const disp = dispositions.get(n.node_id);
            const d = disposition(disp?.disposition ?? "");
            const hex = TONE_HEX[d.tone] ?? "#6b7280";
            const selected = n.node_id === selectedNodeId;
            const node = nodeById.get(n.node_id);
            return (
              <g
                key={n.node_id}
                transform={`translate(${p.x},${p.y})`}
                role="button"
                tabIndex={0}
                aria-label={`${node?.label ?? n.node_id}, ${d.label}`}
                onClick={() => onSelect(n.node_id)}
                onKeyDown={(ev) => {
                  if (ev.key === "Enter" || ev.key === " ") {
                    ev.preventDefault();
                    onSelect(n.node_id);
                  }
                }}
                style={{ cursor: "pointer" }}
              >
                <rect
                  width={170}
                  height={52}
                  rx={6}
                  fill="#161c2a"
                  stroke={selected ? "#6aa9ff" : hex}
                  strokeWidth={selected ? 2.5 : 1.5}
                />
                <rect width={4} height={52} rx={2} fill={hex} />
                <text x={12} y={20} fill="#f5f7fa" fontSize={11} fontWeight={600}>
                  {truncate(node?.label ?? n.node_id, 22)}
                </text>
                <text x={12} y={38} fill={hex} fontSize={9}>
                  {d.glyph} {d.label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      <GraphLegend />
    </div>
  );
}

function GraphLegend() {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 border-t border-surface-border px-3 py-2 text-[11px] text-ink-2">
      {Object.values(DISPOSITIONS).map((d) => (
        <li key={d.code} className="flex items-center gap-1.5">
          <span aria-hidden="true" style={{ color: TONE_HEX[d.tone] }}>
            {d.glyph}
          </span>
          {d.label}
        </li>
      ))}
    </ul>
  );
}

function truncate(s: string, n: number): string {
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}
