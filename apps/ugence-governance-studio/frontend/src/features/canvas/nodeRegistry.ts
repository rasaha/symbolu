// The closed governance node registry.
//
// Four node kinds, each bound 1:1 to a collection the PolicyPack already carries and
// to the `object_type` discriminator the pack already stamps on every object. The
// canvas does not invent a vocabulary: it renders the one the compiler owns.
//
// The registry is CLOSED. `nodeKindFor` returns null for anything unlisted and
// `assertKnownNodeKind` throws, so a graph imported from elsewhere — a Langflow
// export, a hand-edited file — cannot introduce a node type the compiler has never
// heard of. There is deliberately no generic LLM, prompt or API node: those are not
// governance objects, and a canvas that offered them would be a different product.

export const NODE_KINDS = ["capability", "role", "obligation", "policy_clause"] as const;
export type NodeKind = (typeof NODE_KINDS)[number];

export interface NodeKindDescriptor {
  readonly kind: NodeKind;
  /** Human label shown on the node and in the palette. */
  readonly label: string;
  /** The PolicyPack collection this kind round-trips through. */
  readonly collection: string;
  /** The pack's own `object_type` for objects in that collection. */
  readonly objectType: string;
  /** One line explaining what the node means, shown as the node's title attribute. */
  readonly description: string;
  /** Tailwind classes for the node body — kept here so a kind cannot be styled ad hoc. */
  readonly tone: string;
}

const REGISTRY: Readonly<Record<NodeKind, NodeKindDescriptor>> = Object.freeze({
  capability: {
    kind: "capability",
    label: "Capability",
    collection: "connector_mappings",
    objectType: "CONNECTOR_MAPPING",
    description: "A capability the policy binds to, and the connector that realises it.",
    tone: "border-sky-300 bg-sky-50 text-sky-950",
  },
  role: {
    kind: "role",
    label: "Role",
    collection: "authority_requirements",
    objectType: "AUTHORITY_REQUIREMENT",
    description: "Who must decide: the authority required, and the scope it decides over.",
    tone: "border-violet-300 bg-violet-50 text-violet-950",
  },
  obligation: {
    kind: "obligation",
    label: "Obligation",
    collection: "audit_requirements",
    objectType: "AUDIT_REQUIREMENT",
    description: "What must be recorded when the policy is exercised.",
    tone: "border-amber-300 bg-amber-50 text-amber-950",
  },
  policy_clause: {
    kind: "policy_clause",
    label: "Policy clause",
    collection: "decision_rules",
    objectType: "DECISION_RULE",
    description: "A decision rule: the conditions, and the outcome when they are satisfied.",
    tone: "border-emerald-300 bg-emerald-50 text-emerald-950",
  },
});

/** Every collection the canvas owns. Anything else in a pack passes through untouched. */
export const MAPPED_COLLECTIONS: readonly string[] = Object.freeze(
  NODE_KINDS.map((k) => REGISTRY[k].collection),
);

export function descriptorFor(kind: NodeKind): NodeKindDescriptor {
  return REGISTRY[kind];
}

export function allDescriptors(): NodeKindDescriptor[] {
  return NODE_KINDS.map((k) => REGISTRY[k]);
}

/** The node kind for a pack collection, or null when the canvas does not own it. */
export function nodeKindForCollection(collection: string): NodeKind | null {
  const found = NODE_KINDS.find((k) => REGISTRY[k].collection === collection);
  return found ?? null;
}

/** The node kind for a pack `object_type`, or null when unrecognised. */
export function nodeKindForObjectType(objectType: string): NodeKind | null {
  const found = NODE_KINDS.find((k) => REGISTRY[k].objectType === objectType);
  return found ?? null;
}

export class UnknownNodeKindError extends Error {
  readonly received: string;
  constructor(received: string) {
    super(
      `unknown canvas node kind ${JSON.stringify(received)}; the registry is closed and ` +
        `accepts only: ${NODE_KINDS.join(", ")}`,
    );
    this.name = "UnknownNodeKindError";
    this.received = received;
  }
}

export function isNodeKind(value: unknown): value is NodeKind {
  return typeof value === "string" && (NODE_KINDS as readonly string[]).includes(value);
}

/** Refuse an unknown kind. Fails closed: an unrecognised node is never rendered. */
export function assertKnownNodeKind(value: unknown): NodeKind {
  if (!isNodeKind(value)) {
    throw new UnknownNodeKindError(String(value));
  }
  return value;
}
