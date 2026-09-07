// The authority plane's boundary verifier (ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md §11
// step 3; §18, AP-3 controlling).
//
// Five properties, checked against the worker's own committed contract rather than
// against this app's manifest alone, so a manifest edited to permit something the
// contract forbids still fails:
//
//   1. the manifest's contract hash is the hash of the worker's committed contract;
//   2. every approved operation is one the contract marks served (today the four
//      reads; a write only once the contract names it served after enterprise issuer
//      validation), and the forbidden set is exactly the contract's unserved writes;
//   3. the client consumes exactly the approved operations, by real call site and
//      method;
//   4. no file outside src/api/client.ts opens an HTTP connection or names a write
//      method;
//   5. no file in src names a forbidden path or a forbidden operation id, outside
//      negative fixtures. The AP-4 verb rule is enforced on the contract itself by the
//      worker's test.
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
  // Every get<...>(`...`) and post<...>(`...`) call site. The helper's name fixes the
  // method, so a POST literal behind get, or a GET literal behind post, is unmatched.
  const re = /\b(get|post)<[^>]*>\(\s*`([^`]*)`/g;
  let match;
  while ((match = re.exec(clientText)) !== null) {
    const method = match[1].toUpperCase();
    const raw = match[2].split("?")[0];
    const normalized = raw.replace(/\$\{[^}]*\}/g, "{param}");
    const opId = byKey.get(`${method} ${normalized}`);
    if (opId) consumed.add(opId);
    else unmatched.push(`${method} ${normalized}`);
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

/**
 * A forbidden path, a forbidden operation id, or (outside the client) a write method.
 * A forbidden path is matched by its literal prefix up to the first parameter, unless
 * an approved path shares that prefix (the read on /authority/grants shares its
 * literal with the served POST).
 */
export function detectForbiddenReferences(text, manifest, { allowWriteMethod = false } = {}) {
  const hits = [];
  if (text.includes(NEGATIVE_FIXTURE_MARKER)) return hits;
  const approvedPrefixes = manifest.approved_paths.map((a) => a.split(" ")[1].split("{")[0]);
  for (const p of manifest.forbidden_paths) {
    const literal = p.split(" ")[1];
    const prefix = literal.split("{")[0];
    if (manifest.approved_paths.some((a) => a.split(" ")[1] === literal)) {
      // the same literal is an approved read (GET and POST on /authority/grants);
      // the method cannot be told apart statically, so the write-method scan covers it
      continue;
    }
    if (approvedPrefixes.some((a) => a.startsWith(prefix) || prefix.startsWith(a))) {
      // a shared prefix cannot be told apart statically; the exact literal still can
      if (text.includes(literal)) hits.push(`forbidden path ${literal}`);
      continue;
    }
    if (text.includes(prefix)) hits.push(`forbidden path ${literal}`);
  }
  for (const id of manifest.forbidden_operation_ids) {
    if (text.includes(id)) hits.push(`forbidden operation ${id}`);
  }
  if (!allowWriteMethod && /method:\s*["'](POST|PUT|PATCH|DELETE)["']/.test(text)) hits.push("a write method");
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

  // 2. approved == served; forbidden == unserved writes
  const served = contract.operations.filter((o) => o.served === true);
  const unserved = contract.operations.filter((o) => o.served !== true);
  for (const id of manifest.approved_operation_ids) {
    const op = contract.operations.find((o) => o.operation_id === id);
    if (!op) errors.push(`approved ${id} is not an operation of the contract`);
    else if (op.served !== true) errors.push(`approved ${id} is not served by the worker`);
  }
  const forbidden = [...manifest.forbidden_operation_ids].sort();
  const unservedIds = unserved.map((o) => o.operation_id).sort();
  if (JSON.stringify(forbidden) !== JSON.stringify(unservedIds)) errors.push(`forbidden set ${forbidden} != contract's unserved operations ${unservedIds}`);
  for (const u of unserved) if (u.kind !== "write") errors.push(`contract read ${u.operation_id} is unserved; this app's manifest cannot stand`);
  const approvedPaths = manifest.approved_paths.slice().sort();
  const servedPaths = served.map((o) => `${o.method} ${o.path}`).sort();
  if (JSON.stringify(approvedPaths) !== JSON.stringify(servedPaths)) errors.push(`approved paths ${approvedPaths} != contract served paths ${servedPaths}`);
  if (manifest.write_proof_header !== contract.write_proof_header) errors.push(`manifest write_proof_header ${manifest.write_proof_header} != contract ${contract.write_proof_header}`);

  // 3. the client's real consumption
  const clientText = readFileSync(path.join(APP, CLIENT_REL), "utf-8");
  const { consumed, unmatched } = detectConsumption(clientText, contract);
  if (unmatched.length) errors.push(`client reaches paths outside the contract: ${unmatched.join(", ")}`);
  const consumedSorted = [...consumed].sort();
  const approvedSorted = [...manifest.approved_operation_ids].sort();
  if (JSON.stringify(consumedSorted) !== JSON.stringify(approvedSorted)) errors.push(`client consumes ${consumedSorted} but the manifest approves ${approvedSorted}`);
  if (!clientText.includes(`export const PROOF_HEADER = "${contract.write_proof_header}"`)) errors.push("the client's proof header is not the contract's");

  // 4 and 5. the rest of the source
  for (const f of loadTree(path.join(APP, "src"))) {
    if (f.rel !== CLIENT_REL) {
      for (const hit of detectRawFetch(f.text)) errors.push(`${f.rel}: opens an HTTP connection (${hit})`);
    }
    for (const hit of detectForbiddenReferences(f.text, manifest, { allowWriteMethod: f.rel === CLIENT_REL })) errors.push(`${f.rel}: ${hit}`);
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
  console.log(`authority plane boundary OK (${consumed.length} operations consumed; contract sha256 ${sha})`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();
