// Deterministic layered-DAG layout (§13). Positions are computed purely from the
// API-provided nodes and edges: layer = longest path from a source, row = stable
// index within the layer ordered by node_id. Identical input always yields
// identical positions (no randomness, no animation-derived state). This does NOT
// classify nodes or infer edges — it only places API-provided ones.
import type { WorkflowEdge, WorkflowNode } from "@/api/types";

export interface NodePosition {
  node_id: string;
  layer: number;
  row: number;
  x: number;
  y: number;
}

export interface GraphLayout {
  positions: Map<string, NodePosition>;
  width: number;
  height: number;
  layerCount: number;
}

const COL_W = 220;
const ROW_H = 92;
const PAD_X = 40;
const PAD_Y = 40;

export function computeLayout(nodes: WorkflowNode[], edges: WorkflowEdge[]): GraphLayout {
  const ids = nodes.map((n) => n.node_id);
  const idSet = new Set(ids);
  const incoming = new Map<string, string[]>();
  const outgoing = new Map<string, string[]>();
  for (const id of ids) {
    incoming.set(id, []);
    outgoing.set(id, []);
  }
  for (const e of edges) {
    if (!idSet.has(e.source_id) || !idSet.has(e.target_id)) continue;
    outgoing.get(e.source_id)!.push(e.target_id);
    incoming.get(e.target_id)!.push(e.source_id);
  }

  // Longest-path layering (stable; guards against accidental cycles).
  const layer = new Map<string, number>();
  const visiting = new Set<string>();
  const depth = (id: string): number => {
    if (layer.has(id)) return layer.get(id)!;
    if (visiting.has(id)) return 0; // cycle guard — never expected in a compiled DAG
    visiting.add(id);
    const preds = incoming.get(id)!;
    const d = preds.length === 0 ? 0 : Math.max(...preds.map(depth)) + 1;
    visiting.delete(id);
    layer.set(id, d);
    return d;
  };
  for (const id of [...ids].sort()) depth(id);

  // Group by layer, order within layer by node_id (deterministic).
  const byLayer = new Map<number, string[]>();
  for (const id of ids) {
    const l = layer.get(id)!;
    if (!byLayer.has(l)) byLayer.set(l, []);
    byLayer.get(l)!.push(id);
  }
  let maxRows = 0;
  const positions = new Map<string, NodePosition>();
  const layers = [...byLayer.keys()].sort((a, b) => a - b);
  for (const l of layers) {
    const rows = byLayer.get(l)!.sort();
    maxRows = Math.max(maxRows, rows.length);
    rows.forEach((id, row) => {
      positions.set(id, {
        node_id: id,
        layer: l,
        row,
        x: PAD_X + l * COL_W,
        y: PAD_Y + row * ROW_H,
      });
    });
  }

  return {
    positions,
    width: PAD_X * 2 + (layers.length || 1) * COL_W,
    height: PAD_Y * 2 + Math.max(1, maxRows) * ROW_H,
    layerCount: layers.length,
  };
}
