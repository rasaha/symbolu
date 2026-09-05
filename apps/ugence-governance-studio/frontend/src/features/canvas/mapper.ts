// The bidirectional PolicyPack ↔ graph mapper.
//
// The property that matters is that a round trip loses nothing. The canvas owns four
// collections; a real pack carries twenty. A mapper that rebuilt a pack from only the
// nodes it understood would silently delete test scenarios, source documents, replay
// cases and approval paths — a data-loss bug that would look like a working canvas.
//
// So `graphToPack` starts from the ORIGINAL pack and replaces only the mapped
// collections. Unmapped collections are carried through by identity. `roundTrip` and
// the property test in `tests/canvas-mapper.test.ts` assert exactly that.
import {
  MAPPED_COLLECTIONS,
  assertKnownNodeKind,
  nodeKindForCollection,
  type NodeKind,
} from "./nodeRegistry";

export interface PolicyObjectLike {
  object_id?: string;
  object_type?: string;
  name?: string;
  description?: string;
  enabled?: boolean;
  related_object_ids?: string[];
  [key: string]: unknown;
}

export type PolicyPackLike = Record<string, unknown>;

export interface GraphNode {
  id: string;
  kind: NodeKind;
  label: string;
  description: string;
  enabled: boolean;
  position: { x: number; y: number };
  /** The full pack object, preserved verbatim so the round trip is lossless. */
  source: PolicyObjectLike;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
}

export interface PolicyGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  /** The pack the graph came from. `graphToPack` rebuilds onto this. */
  origin: PolicyPackLike;
}

const COLUMN_WIDTH = 280;
const ROW_HEIGHT = 120;

function asObjects(value: unknown): PolicyObjectLike[] {
  return Array.isArray(value) ? (value.filter((v) => typeof v === "object" && v !== null) as PolicyObjectLike[]) : [];
}

/**
 * Build a graph from a pack.
 *
 * Layout is deterministic — one column per node kind, ordered as the pack lists them —
 * so the same pack always yields the same picture. A canvas that shuffled on every
 * open would make review impossible.
 */
export function packToGraph(pack: PolicyPackLike): PolicyGraph {
  const nodes: GraphNode[] = [];
  const byId = new Map<string, GraphNode>();

  MAPPED_COLLECTIONS.forEach((collection, column) => {
    const kind = nodeKindForCollection(collection);
    if (kind === null) return; // unreachable: MAPPED_COLLECTIONS is derived from the registry
    asObjects(pack[collection]).forEach((object, row) => {
      const id = String(object.object_id ?? `${collection}:${row}`);
      const node: GraphNode = {
        id,
        kind,
        label: String(object.name ?? id),
        description: String(object.description ?? ""),
        enabled: object.enabled !== false,
        position: { x: column * COLUMN_WIDTH, y: row * ROW_HEIGHT },
        source: object,
      };
      nodes.push(node);
      byId.set(id, node);
    });
  });

  // Edges come from the pack's own `related_object_ids`; the canvas invents no
  // relationships. An edge to an object outside the mapped collections is dropped
  // from the picture but survives in `source`, so the round trip still restores it.
  const edges: GraphEdge[] = [];
  for (const node of nodes) {
    const related = Array.isArray(node.source.related_object_ids)
      ? node.source.related_object_ids
      : [];
    for (const target of related) {
      const targetId = String(target);
      if (byId.has(targetId)) {
        edges.push({ id: `${node.id}->${targetId}`, source: node.id, target: targetId });
      }
    }
  }

  return { nodes, edges, origin: pack };
}

/**
 * Rebuild a pack from a graph.
 *
 * Every unmapped collection is taken from `graph.origin` unchanged. Only the four
 * mapped collections are rewritten, and each object is written back from its own
 * preserved `source` with the canvas-editable fields applied over it.
 */
export function graphToPack(graph: PolicyGraph): PolicyPackLike {
  const rebuilt: PolicyPackLike = { ...graph.origin };

  for (const collection of MAPPED_COLLECTIONS) {
    const kind = nodeKindForCollection(collection);
    const objects = graph.nodes
      .filter((node) => node.kind === kind)
      .map((node) => {
        assertKnownNodeKind(node.kind); // closed registry, enforced on the way back too
        const next: PolicyObjectLike = { ...node.source };
        // Only fields the canvas actually edits are written back. Writing the whole
        // node would clobber pack fields the canvas never showed.
        if (node.label !== String(node.source.name ?? node.id)) next.name = node.label;
        if (node.description !== String(node.source.description ?? "")) {
          next.description = node.description;
        }
        if (node.enabled !== (node.source.enabled !== false)) next.enabled = node.enabled;
        return next;
      });
    // Preserve absence: a pack without the collection must not gain an empty one.
    if (objects.length > 0 || Array.isArray(graph.origin[collection])) {
      rebuilt[collection] = objects;
    }
  }

  return rebuilt;
}

/** `graphToPack(packToGraph(pack))`. The identity the property test asserts. */
export function roundTrip(pack: PolicyPackLike): PolicyPackLike {
  return graphToPack(packToGraph(pack));
}
