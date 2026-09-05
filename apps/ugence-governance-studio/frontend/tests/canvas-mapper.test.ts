// Round-trip property: PolicyPack → graph → PolicyPack loses nothing.
//
// Driven by the REAL frozen reference pack (fixtures/v2/policy_pack.json), not a
// toy fixture, plus randomised mutations of it. The failure this guards against is
// not subtle-but-rare: a mapper that rebuilt a pack from only the four collections it
// understands would delete the other sixteen, and the canvas would still look fine.
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";

import {
  graphToPack,
  packToGraph,
  roundTrip,
  type PolicyPackLike,
} from "@/features/canvas/mapper";
import {
  MAPPED_COLLECTIONS,
  NODE_KINDS,
  UnknownNodeKindError,
  allDescriptors,
  assertKnownNodeKind,
  isNodeKind,
  nodeKindForCollection,
  nodeKindForObjectType,
} from "@/features/canvas/nodeRegistry";

const PACK: PolicyPackLike = JSON.parse(
  readFileSync(
    path.resolve(__dirname, "..", "..", "fixtures", "v2", "policy_pack.json"),
    "utf-8",
  ),
);

describe("closed node registry", () => {
  it("has exactly the four governance kinds and no generic node", () => {
    expect([...NODE_KINDS].sort()).toEqual(
      ["capability", "obligation", "policy_clause", "role"].sort(),
    );
    for (const banned of ["llm", "prompt", "api", "http", "model", "agent", "tool"]) {
      expect(NODE_KINDS as readonly string[]).not.toContain(banned);
    }
  });

  it("refuses an unknown kind rather than rendering it", () => {
    expect(() => assertKnownNodeKind("llm")).toThrow(UnknownNodeKindError);
    expect(() => assertKnownNodeKind("prompt")).toThrow(/registry is closed/);
    expect(() => assertKnownNodeKind(undefined)).toThrow(UnknownNodeKindError);
    expect(isNodeKind("policy_clause")).toBe(true);
    expect(isNodeKind("anything_else")).toBe(false);
  });

  it("binds each kind 1:1 to a real pack collection and object_type", () => {
    const collections = allDescriptors().map((d) => d.collection);
    const objectTypes = allDescriptors().map((d) => d.objectType);
    expect(new Set(collections).size).toBe(NODE_KINDS.length);
    expect(new Set(objectTypes).size).toBe(NODE_KINDS.length);
    for (const d of allDescriptors()) {
      expect(nodeKindForCollection(d.collection)).toBe(d.kind);
      expect(nodeKindForObjectType(d.objectType)).toBe(d.kind);
    }
    expect(nodeKindForCollection("test_scenarios")).toBeNull();
    expect(nodeKindForObjectType("HUMAN_APPROVAL_RECORD")).toBeNull();
  });

  it("every mapped object_type matches what the frozen pack actually stamps", () => {
    for (const d of allDescriptors()) {
      const objects = (PACK[d.collection] ?? []) as { object_type?: string }[];
      for (const o of objects) {
        expect(o.object_type).toBe(d.objectType);
      }
    }
  });
});

describe("round trip", () => {
  it("is exactly the identity on the frozen reference pack", () => {
    expect(roundTrip(PACK)).toEqual(PACK);
  });

  it("preserves every collection the canvas does NOT own", () => {
    const after = roundTrip(PACK) as Record<string, unknown>;
    const unmapped = Object.keys(PACK).filter((k) => !MAPPED_COLLECTIONS.includes(k));
    expect(unmapped.length).toBeGreaterThan(10); // the pack really is mostly unmapped
    for (const key of unmapped) {
      expect(after[key]).toEqual(PACK[key]);
    }
  });

  it("surfaces the mapped collections as nodes", () => {
    const graph = packToGraph(PACK);
    for (const collection of MAPPED_COLLECTIONS) {
      const inPack = ((PACK[collection] ?? []) as unknown[]).length;
      const inGraph = graph.nodes.filter(
        (n) => n.kind === nodeKindForCollection(collection),
      ).length;
      expect(inGraph).toBe(inPack);
    }
  });

  it("derives edges only from the pack's own related_object_ids", () => {
    const graph = packToGraph(PACK);
    const ids = new Set(graph.nodes.map((n) => n.id));
    for (const edge of graph.edges) {
      expect(ids.has(edge.source)).toBe(true);
      expect(ids.has(edge.target)).toBe(true);
      const related = graph.nodes.find((n) => n.id === edge.source)?.source.related_object_ids;
      expect(related).toContain(edge.target);
    }
  });

  it("is deterministic — the same pack always yields the same layout", () => {
    expect(packToGraph(PACK).nodes.map((n) => [n.id, n.position])).toEqual(
      packToGraph(PACK).nodes.map((n) => [n.id, n.position]),
    );
  });
});

// --------------------------------------------------------------------------- //
// randomised property check
// --------------------------------------------------------------------------- //
function mutate(pack: PolicyPackLike, seed: number): PolicyPackLike {
  // A tiny deterministic PRNG: reproducible failures matter more than entropy here.
  let state = seed * 1103515245 + 12345;
  const next = () => {
    state = (state * 1103515245 + 12345) & 0x7fffffff;
    return state / 0x7fffffff;
  };
  const clone: PolicyPackLike = JSON.parse(JSON.stringify(pack));
  for (const collection of MAPPED_COLLECTIONS) {
    const objects = clone[collection] as Record<string, unknown>[] | undefined;
    if (!Array.isArray(objects)) continue;
    for (const object of objects) {
      const roll = next();
      if (roll < 0.3) object.name = `renamed-${Math.floor(next() * 1000)}`;
      else if (roll < 0.5) object.description = `changed-${Math.floor(next() * 1000)}`;
      else if (roll < 0.6) object.enabled = !(object.enabled !== false);
    }
  }
  return clone;
}

describe("round trip — randomised", () => {
  it("is the identity over 50 mutated packs", () => {
    for (let seed = 1; seed <= 50; seed += 1) {
      const mutated = mutate(PACK, seed);
      expect(roundTrip(mutated)).toEqual(mutated);
    }
  });

  it("carries a canvas edit back into the pack, and only that edit", () => {
    const graph = packToGraph(PACK);
    expect(graph.nodes.length).toBeGreaterThan(0);
    const target = graph.nodes[0];
    const edited = {
      ...graph,
      nodes: graph.nodes.map((n) =>
        n.id === target.id ? { ...n, label: "Renamed on the canvas", enabled: false } : n,
      ),
    };

    const after = graphToPack(edited) as Record<string, unknown>;
    const collection = allDescriptors().find((d) => d.kind === target.kind)!.collection;
    const written = (after[collection] as Record<string, unknown>[]).find(
      (o) => o.object_id === target.id,
    )!;

    expect(written.name).toBe("Renamed on the canvas");
    expect(written.enabled).toBe(false);

    // Nothing else moved.
    const before = (PACK[collection] as Record<string, unknown>[]).find(
      (o) => o.object_id === target.id,
    )!;
    for (const key of Object.keys(before)) {
      if (key === "name" || key === "enabled") continue;
      expect(written[key]).toEqual(before[key]);
    }
  });

  it("does not invent a collection the pack never had", () => {
    const sparse: PolicyPackLike = { pack_id: "p", name: "n", version: "1" };
    const after = roundTrip(sparse) as Record<string, unknown>;
    for (const collection of MAPPED_COLLECTIONS) {
      expect(collection in after).toBe(false);
    }
    expect(after).toEqual(sparse);
  });
});
