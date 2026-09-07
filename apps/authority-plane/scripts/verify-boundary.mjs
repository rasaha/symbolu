// The authority plane's boundary verifier (ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md §11 step 3).
//
// Five properties, checked against the worker's own committed contract rather than
// against this app's manifest alone, so a manifest edited to permit something the
// contract forbids still fails:
//
//   1. the manifest's contract hash is the hash of the worker's committed contract;
//   2. every approved operation is a read the contract marks served, and the forbidden
//      set is exactly the contract's writes;
//   3. the client consumes exactly the approved operations, by real call site;
//   4. no file outside src/api/client.ts opens an HTTP connection;
//   5. no file in src names a forbidden path, a forbidden operation id, or a write
//      method, outside negative fixtures. The AP-4 verb rule is enforced on the
//      contract itself by the worker's test.
//
//   node scripts/verify-boundary.mjs
//
// Pure helpers are exported for unit testing.
import { readFileSync, readdirSync, statSync } from "node:fs";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import path from "node:path";

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const APP = path.dirname(HERE);
const REPO = path.resolve(APP, "..", "..");
export const CONTRACT_PATH = path.join(REPO, "deployment", "governed-runtime-worker", "authority-plane-contract.json");
export const MANIFEST_PATH = path.join(APP, "security", "approved-operations.json");
export const CLIENT_REL = "src/api/client.ts";
const NEGATIVE_FIXTURE_MARKER = "authority-plane-negative-fixtures";

export function sha256(text) {
  return createHash("sha256").update(text).digest("hex");
}

export function loadContract() {
  const raw = readFileSync(CONTRACT_PATH, "utf-8");
  return { raw, sha: sha256(raw), contract: JSON.parse(raw) };
}

/** Which operations the client's source actually reaches, by (method, path) literal. */
export function detectConsumption(clientText, contract) {
  const byKey = new Map();
  for (const op of contract.operations) {
    byKey.set(`${op.method} ${op.path.replace(/\{[^}]*\}/g, "{param}")}`, op.operation_id);
  }
  const consumed = new Set();
  const unmatched = [];
  // Every get<...>(`...`) call site. The client has no post helper; a POST literal
  // would be unmatched and fail the exactness check.
  const re = /\bget<[^>]*>\(\s*`([^`]*)`/g;
  let match;
  while ((match = re.exec(clientText)) !== null) {
    const raw = match[1].split("?")[0];
    const normalized = raw.replace(/\$\{[^}]*\}/g, "{param}");
    const opId = byKey.get(`GET ${normalized}`);
    if (opId) consumed.add(opId);
    else unmatched.push(normalized);
  }
  return { consumed, unmatched };
}

/** Any fetch/XMLHttpRequest/WebSocket outside the approved client. */
export function detectRawFetch(text) {
  const hits = [];
  for (const re of [/\bfetch\s*\(/g, /\bXMLHttpRequest\b/g, /\bWebSocket\s*\(/g, /\baxios\b/g]) {
    if (re.test(text)) hits.push(re.source);
  }
  return hits;
}

/** A forbidden path, a write on a plane path, or a refused verb in application source. */
export function detectForbiddenReferences(text, manifest) {
  const hits = [];
  if (text.includes(NEGATIVE_FIXTURE_MARKER)) return hits;
  for (const p of manifest.forbidden_paths) {
    const literal = p.split(" ")[1];
    if (text.includes(literal) && !text.includes("GET " + literal)) {
      // the read on /authority/grants shares its literal with the POST; only flag
      // literal write paths that are not also approved read paths
      const isReadToo = manifest.approved_paths.some((a) => a.split(" ")[1] === literal);
      if (!isReadToo) hits.push(`forbidden path ${literal}`);
    }
  }
  for (const id of manifest.forbidden_operation_ids) {
    if (text.includes(id)) hits.push(`forbidden operation ${id}`);
  }
  if (/method:\s*["'](POST|PUT|PATCH|DELETE)["']/.test(text)) hits.push("a write method");
  // The AP-4 verb rule (no authorize, clear, execute) is enforced on the contract by the
  // worker's own test; this app's prose may name those verbs to say it never performs
  // them, so the verbs are not scanned in source here. Paths and ids are.
  return hits;
}

function loadTree(dir) {
  const out = [];
  const walk = (d) => {
    for (const name of readdirSync(d)) {
      const full = path.join(d, name);
      if (statSync(full).isDirectory()) walk(full);
      else if (/\.(ts|tsx)$/.test(name)) out.push({ rel: path.relative(APP, full), text: readFileSync(full, "utf-8") });
    }
  };
  walk(dir);
  return out;
}

export function verify() {
  const errors = [];
  const { sha, contract } = loadContract();
  const manifest = JSON.parse(readFileSync(MANIFEST_PATH, "utf-8"));

  // 1. the hash
  if (manifest.contract_sha256 !== sha) errors.push(`manifest contract_sha256 ${manifest.contract_sha256} != contract ${sha}`);
  if (manifest.contract !== contract.schema) errors.push(`manifest contract ${manifest.contract} != ${contract.schema}`);

  // 2. approved ⊆ served reads; forbidden == writes
  const reads = contract.operations.filter((o) => o.kind === "read");
  const writes = contract.operations.filter((o) => o.kind === "write");
  for (const id of manifest.approved_operation_ids) {
    const op = reads.find((o) => o.operation_id === id);
    if (!op) errors.push(`approved ${id} is not a read of the contract`);
    else if (op.served !== true) errors.push(`approved ${id} is not served by the worker`);
  }
  const forbidden = [...manifest.forbidden_operation_ids].sort();
  const writeIds = writes.map((o) => o.operation_id).sort();
  if (JSON.stringify(forbidden) !== JSON.stringify(writeIds)) errors.push(`forbidden set ${forbidden} != contract writes ${writeIds}`);
  for (const w of writes) if (w.served !== false) errors.push(`contract write ${w.operation_id} is marked served; this app's manifest cannot stand`);
  const approvedPaths = manifest.approved_paths.slice().sort();
  const readPaths = reads.map((o) => `${o.method} ${o.path}`).sort();
  if (JSON.stringify(approvedPaths) !== JSON.stringify(readPaths)) errors.push(`approved paths ${approvedPaths} != contract read paths ${readPaths}`);

  // 3. the client's real consumption
  const clientText = readFileSync(path.join(APP, CLIENT_REL), "utf-8");
  const { consumed, unmatched } = detectConsumption(clientText, contract);
  if (unmatched.length) errors.push(`client reaches paths outside the contract: ${unmatched.join(", ")}`);
  const consumedSorted = [...consumed].sort();
  const approvedSorted = [...manifest.approved_operation_ids].sort();
  if (JSON.stringify(consumedSorted) !== JSON.stringify(approvedSorted)) errors.push(`client consumes ${consumedSorted} but the manifest approves ${approvedSorted}`);

  // 4 and 5. the rest of the source
  for (const f of loadTree(path.join(APP, "src"))) {
    if (f.rel !== CLIENT_REL) {
      for (const hit of detectRawFetch(f.text)) errors.push(`${f.rel}: opens an HTTP connection (${hit})`);
    }
    for (const hit of detectForbiddenReferences(f.text, manifest)) errors.push(`${f.rel}: ${hit}`);
  }
  return { errors, consumed: consumedSorted, sha };
}

function main() {
  const { errors, consumed, sha } = verify();
  if (errors.length) {
    console.error("AUTHORITY PLANE BOUNDARY FAILED");
    for (const e of errors) console.error("  - " + e);
    process.exit(1);
  }
  console.log(`authority plane boundary OK (${consumed.length} reads consumed; contract sha256 ${sha})`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();
