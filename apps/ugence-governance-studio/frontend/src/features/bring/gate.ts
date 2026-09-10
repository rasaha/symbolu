// The Bring Your Workflow gate (ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md §22, BW-2).
//
// Pure, table-tested, and the only place the screen reads the operator's text. It
// refuses, with a typed code, everything the ruling says the surface never accepts:
// anything but JSON, an oversized or over-deep document, too many nodes or edges, a
// version outside the two the backend supports, a credential-shaped value, a remote
// reference. The figures are the owner's and the backend enforces the same ones
// (workflow_limits.py); this gate is the courtesy that saves a round trip, the backend
// is the authority. Nothing here stores, fetches or executes anything.

export const LIMITS = {
  document_bytes: 1024 * 1024,
  depth: 32,
  nodes: 200,
  edges: 400,
  elements: 50_000,
} as const;

export const SUPPORTED_CONTRACTS = ["workflow_ir.v1", "workflow_ir.v2"] as const;
export type SupportedContract = (typeof SUPPORTED_CONTRACTS)[number];

export type GateRefusalCode =
  | "EMPTY"
  | "TOO_LARGE"
  | "NOT_JSON"
  | "NOT_AN_OBJECT"
  | "TOO_DEEP"
  | "TOO_MANY_ELEMENTS"
  | "TOO_MANY_NODES"
  | "TOO_MANY_EDGES"
  | "UNSUPPORTED_VERSION"
  | "CREDENTIAL_SHAPED"
  | "REMOTE_REFERENCE";

export interface GateRefusal {
  ok: false;
  code: GateRefusalCode;
  message: string;
}

export interface Measures {
  depth: number;
  elements: number;
  nodes: number;
  edges: number;
}

export interface WorkflowSummary {
  nodeCount: number;
  edgeCount: number;
  kinds: Record<string, number>;
  dispositions: Record<string, number>;
  humanReviewNodes: string[];
  humanAuthorityNodes: string[];
  toolRefs: string[];
  capabilityRefs: string[];
  policyPack: string | null;
  workflowFingerprint: string | null;
}

export interface GatedDocument {
  ok: true;
  document: Record<string, unknown>;
  declaredVersion: SupportedContract;
  bytes: number;
  measures: Measures;
  summary: WorkflowSummary;
}

export type GateResult = GateRefusal | GatedDocument;

type Json = Record<string, unknown>;

const isObject = (v: unknown): v is Json => !!v && typeof v === "object" && !Array.isArray(v);

const CREDENTIAL_KEY = /(secret|password|passwd|token|api[_-]?key|private[_-]?key|authorization|bearer|credential)/i;
const CREDENTIAL_VALUE = /^(eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.|-----BEGIN [A-Z ]*PRIVATE KEY|sk-[A-Za-z0-9_-]{16,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,}|xox[abprs]-[A-Za-z0-9-]{10,})/;
const REMOTE_VALUE = /^\s*(https?|ftp|ftps|file|ws|wss|s3|gs|git|ssh):\/\//i;

const refuse = (code: GateRefusalCode, message: string): GateRefusal => ({ ok: false, code, message });

export function byteLength(text: string): number {
  return new TextEncoder().encode(text).length;
}

/** The backend's own rule (adapter_v2.declared_contract_version), never guessed from field presence. */
export function declaredVersion(document: Json): string {
  const top = String(document.ir_version ?? document.contract_version ?? "");
  if (top) return top;
  const wf = document.workflow_ir;
  if (isObject(wf)) return String(wf.ir_version ?? "");
  return "";
}

/**
 * Depth, element count and the longest `nodes` / `edges` lists, in one iterative walk
 * (no recursion), stopping as soon as any limit is passed. Also the credential and
 * remote-reference scan, since it walks every string anyway.
 */
export function measure(document: unknown): { measures: Measures; refusal: GateRefusal | null } {
  const measures: Measures = { depth: 0, elements: 0, nodes: 0, edges: 0 };
  const stack: Array<{ value: unknown; level: number; key: string | null }> = [{ value: document, level: 1, key: null }];
  while (stack.length) {
    const { value, level, key } = stack.pop()!;
    measures.elements += 1;
    if (measures.elements > LIMITS.elements) {
      return { measures, refusal: refuse("TOO_MANY_ELEMENTS", `the document holds more than ${LIMITS.elements} values`) };
    }
    if (level > measures.depth) measures.depth = level;
    if (measures.depth > LIMITS.depth) {
      return { measures, refusal: refuse("TOO_DEEP", `nesting deeper than ${LIMITS.depth} levels`) };
    }
    if (typeof value === "string") {
      if (key !== null && CREDENTIAL_KEY.test(key) && value.trim() !== "") {
        return { measures, refusal: refuse("CREDENTIAL_SHAPED", `"${key}" carries a value; credentials never belong in a workflow document`) };
      }
      if (CREDENTIAL_VALUE.test(value)) {
        return { measures, refusal: refuse("CREDENTIAL_SHAPED", `a value under "${key ?? "(list item)"}" is shaped like a token or private key`) };
      }
      if (REMOTE_VALUE.test(value)) {
        return { measures, refusal: refuse("REMOTE_REFERENCE", `a value under "${key ?? "(list item)"}" is a remote reference; this surface fetches nothing`) };
      }
    } else if (Array.isArray(value)) {
      if (key === "nodes" && value.length > measures.nodes) measures.nodes = value.length;
      if (key === "edges" && value.length > measures.edges) measures.edges = value.length;
      if (measures.nodes > LIMITS.nodes) {
        return { measures, refusal: refuse("TOO_MANY_NODES", `${measures.nodes} nodes exceed the limit of ${LIMITS.nodes}`) };
      }
      if (measures.edges > LIMITS.edges) {
        return { measures, refusal: refuse("TOO_MANY_EDGES", `${measures.edges} edges exceed the limit of ${LIMITS.edges}`) };
      }
      for (const item of value) stack.push({ value: item, level: level + 1, key: null });
    } else if (isObject(value)) {
      for (const [k, v] of Object.entries(value)) stack.push({ value: v, level: level + 1, key: k });
    }
  }
  return { measures, refusal: null };
}

function asList(v: unknown): Json[] {
  return Array.isArray(v) ? v.filter(isObject) : [];
}

function count(items: Json[], key: string): Record<string, number> {
  const out: Record<string, number> = {};
  for (const item of items) {
    const k = String(item[key] ?? "");
    if (!k) continue;
    out[k] = (out[k] ?? 0) + 1;
  }
  return out;
}

/** What the document declares, read verbatim; nothing inferred. */
export function summarize(document: Json): WorkflowSummary {
  const ir = isObject(document.workflow_ir) ? document.workflow_ir : isObject(document.base_ir) ? document.base_ir : document;
  const nodes = asList(ir.nodes);
  const edges = asList(ir.edges);
  const semantics: Json[] = Array.isArray(document.node_semantics)
    ? asList(document.node_semantics)
    : isObject(document.node_semantics)
      ? Object.values(document.node_semantics).filter(isObject)
      : [];
  const humanReviewNodes: string[] = [];
  const humanAuthorityNodes: string[] = [];
  const toolRefs = new Set<string>();
  for (const s of semantics) {
    const id = String(s.node_id ?? "");
    const review = s.human_review_requirement;
    if (isObject(review) && review.required === true && id) humanReviewNodes.push(id);
    if (s.human_authority_requirement === true && id) humanAuthorityNodes.push(id);
    for (const t of Array.isArray(s.required_tool_refs) ? s.required_tool_refs : []) toolRefs.add(String(t));
  }
  for (const n of nodes) {
    const id = String(n.node_id ?? "");
    const kind = String(n.kind ?? "");
    if (kind === "HUMAN_REVIEW" && id && !humanReviewNodes.includes(id)) humanReviewNodes.push(id);
    if (String(n.authority_type ?? "") && id && !humanAuthorityNodes.includes(id)) humanAuthorityNodes.push(id);
  }
  const caps = Array.isArray(ir.referenced_capabilities) ? ir.referenced_capabilities.map(String) : [];
  const manifest = isObject(document.manifest) ? document.manifest : null;
  return {
    nodeCount: nodes.length,
    edgeCount: edges.length,
    kinds: count(nodes, "kind"),
    dispositions: count(nodes, "disposition"),
    humanReviewNodes,
    humanAuthorityNodes,
    toolRefs: [...toolRefs].sort(),
    capabilityRefs: [...new Set(caps)].sort(),
    policyPack: ir.policy_pack_id ? `${String(ir.policy_pack_id)}@${String(ir.policy_pack_version ?? "?")}` : null,
    workflowFingerprint:
      typeof document.workflow_fingerprint === "string"
        ? document.workflow_fingerprint
        : typeof document.structural_digest === "string"
          ? document.structural_digest
          : manifest && typeof manifest.structural_digest === "string"
            ? manifest.structural_digest
            : null,
  };
}

/** The whole gate: text in, a typed refusal or a measured, summarized document out. */
export function gateWorkflowText(text: string): GateResult {
  if (!text || text.trim() === "") return refuse("EMPTY", "paste a Workflow IR document or choose a local JSON file");
  const bytes = byteLength(text);
  if (bytes > LIMITS.document_bytes) {
    return refuse("TOO_LARGE", `${bytes} bytes exceed the limit of ${LIMITS.document_bytes} (1 MiB)`);
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch (err) {
    return refuse("NOT_JSON", `not JSON: ${err instanceof Error ? err.message : String(err)}. YAML, code and archives are never accepted`);
  }
  if (!isObject(parsed)) return refuse("NOT_AN_OBJECT", "a Workflow IR document is a JSON object");
  const { measures, refusal } = measure(parsed);
  if (refusal) return refusal;
  const version = declaredVersion(parsed);
  if (!(SUPPORTED_CONTRACTS as readonly string[]).includes(version)) {
    return refuse(
      "UNSUPPORTED_VERSION",
      version
        ? `declared version "${version}" is not one of ${SUPPORTED_CONTRACTS.join(", ")}`
        : `no ir_version or contract_version is declared; the version is never guessed`,
    );
  }
  return {
    ok: true,
    document: parsed,
    declaredVersion: version as SupportedContract,
    bytes,
    measures,
    summary: summarize(parsed),
  };
}

// -- provenance --------------------------------------------------------------- //

function sortKeys(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortKeys);
  if (isObject(value)) {
    const out: Json = {};
    for (const k of Object.keys(value).sort()) out[k] = sortKeys(value[k]);
    return out;
  }
  return value;
}

/**
 * The backend's canonical encoding (serialization/canonical.py: sorted keys, two-space
 * indent, trailing newline). A JSON number the two runtimes print differently (1.0)
 * makes the client digest differ from the server's; the screen shows both and the
 * server's `computed_digest` is the one of record.
 */
export function canonicalText(document: unknown): string {
  return JSON.stringify(sortKeys(document), null, 2) + "\n";
}

export async function clientDigest(document: unknown): Promise<string | null> {
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) return null;
  const data = new TextEncoder().encode(canonicalText(document));
  const hash = await subtle.digest("SHA-256", data);
  const hex = [...new Uint8Array(hash)].map((b) => b.toString(16).padStart(2, "0")).join("");
  return `sha256:${hex}`;
}
