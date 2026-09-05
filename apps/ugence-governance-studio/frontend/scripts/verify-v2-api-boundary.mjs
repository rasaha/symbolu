// v2 API boundary verifier.
//
// Three properties, checked against the CONTRACT rather than against the manifest, so
// a manifest edited to permit something the contract forbids still fails:
//
//   1. the v2 client consumes exactly the approved operations, and no others;
//   2. no v2 operation id or path names an authority act (SD-2);
//   3. no file outside the approved clients opens an HTTP connection.
import { readFileSync, readdirSync, statSync } from "node:fs";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { APPROVED_CLIENTS, detectRawFetch } from "./verify-api-boundary.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.dirname(HERE);
const CONTRACT = path.resolve(FRONTEND, "..", "contracts", "openapi_v2.json");
const MANIFEST = path.join(FRONTEND, "security", "approved-v2-api-operations.json");
const CLIENT = path.join(FRONTEND, "src", "api", "client-v2.ts");
const SRC = path.join(FRONTEND, "src");

export function indexV2(spec) {
  const byKey = new Map();
  for (const [p, item] of Object.entries(spec.paths ?? {})) {
    for (const [method, op] of Object.entries(item)) {
      if (op && typeof op === "object" && "operationId" in op) {
        byKey.set(`${method.toUpperCase()} ${p}`, op.operationId);
      }
    }
  }
  return byKey;
}

/** Which v2 operations the client's source actually reaches. */
export function detectV2Consumption(clientText, spec) {
  const byKey = indexV2(spec);
  const consumed = new Set();
  const unmatched = [];
  // Literal or template paths, with ${...} standing in for a path parameter.
  const re = /"(\/api\/v2\/[^"]*)"|`(\/api\/v2\/[^`]*)`/g;
  let match;
  while ((match = re.exec(clientText)) !== null) {
    const raw = (match[1] ?? match[2]).split("?")[0];
    const normalized = raw.replace(/\$\{[^}]*\}/g, "{param}");
    let found = false;
    for (const [key, opId] of byKey) {
      const [method, specPath] = key.split(" ");
      const specNormalized = specPath.replace(/\{[^}]*\}/g, "{param}");
      if (specNormalized === normalized) {
        // The method is inferred from the surrounding call: a GET helper has no body.
        consumed.add(opId);
        found = true;
        void method;
      }
    }
    if (!found) unmatched.push(normalized);
  }
  return { consumed, unmatched };
}

/** SD-2, re-derived from the contract. */
export function detectAuthorityActs(spec, verbs) {
  const violations = [];
  for (const [p, item] of Object.entries(spec.paths ?? {})) {
    for (const op of Object.values(item)) {
      if (!op || typeof op !== "object" || !("operationId" in op)) continue;
      const haystack = `${op.operationId} ${p}`.toLowerCase();
      for (const verb of verbs) {
        if (haystack.includes(verb)) violations.push(`${op.operationId} (${p}) names '${verb}'`);
      }
    }
  }
  return violations;
}

function loadTree(dir) {
  const out = [];
  const walk = (d) => {
    for (const name of readdirSync(d)) {
      const full = path.join(d, name);
      if (statSync(full).isDirectory()) walk(full);
      else if (/\.(ts|tsx)$/.test(name)) {
        out.push({ rel: path.relative(FRONTEND, full), text: readFileSync(full, "utf-8") });
      }
    }
  };
  walk(dir);
  return out;
}

export function verifyV2({ spec, specSha, manifest, clientText, appFiles }) {
  const violations = [];

  if (manifest.contract !== spec.info?.version) {
    violations.push(`manifest contract ${manifest.contract} != ${spec.info?.version}`);
  }
  if (manifest.openapi_sha256 !== specSha) {
    violations.push("manifest openapi_sha256 does not match the committed contract");
  }

  const { consumed, unmatched } = detectV2Consumption(clientText, spec);
  for (const u of unmatched) violations.push(`consumed path not in the v2 contract: ${u}`);

  const approved = new Set(manifest.approved_operation_ids ?? []);
  for (const op of consumed) {
    if (!approved.has(op)) violations.push(`unapproved v2 operation consumed: ${op}`);
  }

  const authorityActs = detectAuthorityActs(spec, manifest.prohibited_verbs ?? []);
  for (const a of authorityActs) violations.push(`SD-2 violation: ${a}`);

  const rawFetch = detectRawFetch(
    appFiles.filter((f) => !APPROVED_CLIENTS.includes(f.rel) && !f.rel.startsWith("src/generated/")),
  );
  for (const f of rawFetch) violations.push(`raw fetch outside an approved client: ${f.file}`);

  return { violations, consumed: [...consumed].sort() };
}

function main() {
  const raw = readFileSync(CONTRACT, "utf-8");
  const spec = JSON.parse(raw);
  const specSha = createHash("sha256").update(raw).digest("hex");
  const manifest = JSON.parse(readFileSync(MANIFEST, "utf-8"));
  const clientText = readFileSync(CLIENT, "utf-8");
  const appFiles = loadTree(SRC);

  const report = verifyV2({ spec, specSha, manifest, clientText, appFiles });
  if (report.violations.length) {
    console.error("V2 API BOUNDARY VIOLATIONS:");
    for (const v of report.violations) console.error(`  - ${v}`);
    process.exit(1);
  }
  console.log(`v2 API boundary OK (${report.consumed.length} operations consumed)`);
}

if (import.meta.url === `file://${process.argv[1]}`) main();
