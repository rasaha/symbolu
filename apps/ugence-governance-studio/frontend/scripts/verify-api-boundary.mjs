// Exact public-operation allowlist verifier (P3D final hardening, C1).
//
// Instead of a permissive path denylist, this enforces a POSITIVE allowlist: the
// frontend may consume only the operations named in security/approved-api-operations.json,
// and that manifest is validated against the frozen OpenAPI contract.
//
// It inspects ACTUAL consumption — the fetch call sites in the canonical client
// (src/api/client.ts) — not merely the generated client's complete operation set.
// The generated types (src/generated/**) legitimately contain every operation and
// are excluded from consumption/forbidden scans.
//
//   node scripts/verify-api-boundary.mjs
//
// Pure helpers are exported for unit testing.
import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.dirname(HERE);
const CONTRACT = path.resolve(FRONTEND, "..", "contracts", "openapi.json");
const MANIFEST = path.join(FRONTEND, "security", "approved-api-operations.json");
const CLIENT = path.join(FRONTEND, "src", "api", "client.ts");
const SRC = path.join(FRONTEND, "src");
const TESTS = path.join(FRONTEND, "tests");
const NEGATIVE_FIXTURE_MARKER = "api-allowlist-negative-fixtures";

// -- OpenAPI indexing ------------------------------------------------------
export function indexOperations(spec) {
  const byId = new Map();
  const byKey = new Map();
  for (const [p, item] of Object.entries(spec.paths ?? {})) {
    for (const [method, op] of Object.entries(item)) {
      if (op && typeof op === "object" && "operationId" in op) {
        const key = `${method.toUpperCase()} ${p}`;
        byId.set(op.operationId, { method: method.toUpperCase(), path: p });
        byKey.set(key, op.operationId);
      }
    }
  }
  return { byId, byKey };
}

// -- consumption detection -------------------------------------------------
export function normalizePath(raw) {
  return raw.split("?")[0].replace(/\$\{[^}]*\}/g, "{scenario_id}");
}

// Extract every request()/envelope() call site and resolve its (method, path).
export function detectConsumption(clientText, spec) {
  const { byKey } = indexOperations(spec);
  const re = /\b(request|envelope)\s*(<[^(]*>)?\s*\(/g;
  const calls = [];
  while (re.exec(clientText) !== null) {
    const open = re.lastIndex - 1;
    let depth = 0, end = -1;
    for (let i = open; i < clientText.length; i++) {
      const c = clientText[i];
      if (c === "(") depth++;
      else if (c === ")" && --depth === 0) { end = i; break; }
    }
    if (end === -1) continue;
    const args = clientText.slice(open + 1, end);
    const lit = args.match(/`([^`]*)`|"([^"]*)"|'([^']*)'/);
    if (!lit) continue; // e.g. the request()/envelope() internal definition
    const rawPath = lit[1] ?? lit[2] ?? lit[3];
    if (!rawPath.startsWith("/")) continue;
    const method = /postJson\s*\(|method:\s*["']POST["']/.test(args) ? "POST" : "GET";
    const norm = normalizePath(rawPath);
    const opId = byKey.get(`${method} ${norm}`) ?? null;
    calls.push({ rawPath, method, path: norm, operationId: opId });
  }
  const consumed = new Set(calls.map((c) => c.operationId).filter(Boolean));
  const unmatched = calls.filter((c) => !c.operationId);
  return { calls, consumed, unmatched };
}

// -- manifest validation ---------------------------------------------------
function dupes(arr) {
  const seen = new Set(), dup = new Set();
  for (const x of arr) (seen.has(x) ? dup : seen).add(x);
  return [...dup];
}

export function validateManifest(manifest, spec, specSha) {
  const errors = [];
  const { byId } = indexOperations(spec);
  if (manifest.openapi_sha256 !== specSha) {
    errors.push(`manifest OpenAPI hash ${manifest.openapi_sha256} != frozen ${specSha}`);
  }
  const approved = manifest.approved_operation_ids ?? [];
  const forbidden = manifest.forbidden_operation_ids ?? [];
  for (const [label, arr] of [
    ["approved_operation_ids", approved],
    ["forbidden_operation_ids", forbidden],
    ["approved_paths", manifest.approved_paths ?? []],
  ]) {
    const d = dupes(arr);
    if (d.length) errors.push(`duplicate ${label}: ${d.join(", ")}`);
  }
  const overlap = approved.filter((o) => forbidden.includes(o));
  if (overlap.length) errors.push(`approved/forbidden overlap: ${overlap.join(", ")}`);
  for (const o of approved) if (!byId.has(o)) errors.push(`approved operation not in OpenAPI: ${o}`);
  for (const o of forbidden) if (!byId.has(o)) errors.push(`forbidden operation not in OpenAPI: ${o}`);
  // approved_paths must correspond exactly to approved operation ids
  const approvedKeys = new Set(approved.map((o) => byId.has(o) ? `${byId.get(o).method} ${byId.get(o).path}` : null));
  for (const key of manifest.approved_paths ?? []) {
    if (!approvedKeys.has(key)) errors.push(`approved_path not backed by an approved operation: ${key}`);
  }
  return { errors };
}

// -- file scanning ---------------------------------------------------------
export function walk(dir, exts = [".ts", ".tsx"]) {
  const out = [];
  if (!existsSync(dir)) return out;
  for (const name of readdirSync(dir)) {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) out.push(...walk(full, exts));
    else if (exts.some((e) => name.endsWith(e))) out.push(full);
  }
  return out;
}

// A bare `fetch(` (not `.fetch(`, `refetch(`, etc.) anywhere but the canonical client.
export function detectRawFetch(files) {
  const re = /(^|[^A-Za-z0-9_$.])fetch\s*\(/;
  return files.filter((f) => re.test(f.text)).map((f) => ({ file: f.rel }));
}

// Forbidden operation ids / paths must not appear in application or test code
// (excluding generated types and explicit negative-fixture files).
export function detectForbiddenReferences(files, manifest) {
  const tokens = [
    ...(manifest.forbidden_operation_ids ?? []),
    ...(manifest.forbidden_paths ?? []).map((p) => p.split(" ")[1]),
  ];
  const violations = [];
  for (const f of files) {
    if (f.text.includes(NEGATIVE_FIXTURE_MARKER)) continue;
    for (const t of tokens) {
      if (f.text.includes(t)) violations.push({ file: f.rel, token: t });
    }
  }
  return violations;
}

export function verify({ spec, specSha, manifest, clientText, appFiles, testFiles }) {
  const report = { violations: [], consumed: [], unapproved_consumed: [], forbidden_consumed: [], unmatched: [], raw_fetch: [], forbidden_refs: [], manifest_errors: [] };
  const { errors } = validateManifest(manifest, spec, specSha);
  report.manifest_errors = errors;

  const { calls, consumed, unmatched } = detectConsumption(clientText, spec);
  report.consumed = [...consumed].sort();
  report.calls = calls;
  report.unmatched = unmatched;

  const approved = new Set(manifest.approved_operation_ids ?? []);
  const forbidden = new Set(manifest.forbidden_operation_ids ?? []);
  report.unapproved_consumed = [...consumed].filter((o) => !approved.has(o)).sort();
  report.forbidden_consumed = [...consumed].filter((o) => forbidden.has(o)).sort();

  // application code = src minus generated; raw-fetch also excludes the canonical client
  report.raw_fetch = detectRawFetch(appFiles.filter((f) => f.rel !== "src/api/client.ts"));
  report.forbidden_refs = detectForbiddenReferences([...appFiles, ...testFiles], manifest);

  if (errors.length) report.violations.push(...errors.map((e) => `manifest: ${e}`));
  if (report.unmatched.length) report.violations.push(...report.unmatched.map((u) => `consumed path not in OpenAPI: ${u.method} ${u.path}`));
  if (report.unapproved_consumed.length) report.violations.push(`unapproved operations consumed: ${report.unapproved_consumed.join(", ")}`);
  if (report.forbidden_consumed.length) report.violations.push(`forbidden operations consumed: ${report.forbidden_consumed.join(", ")}`);
  if (report.raw_fetch.length) report.violations.push(...report.raw_fetch.map((r) => `raw fetch outside canonical client: ${r.file}`));
  if (report.forbidden_refs.length) report.violations.push(...report.forbidden_refs.map((r) => `forbidden reference ${r.token} in ${r.file}`));

  report.ok = report.violations.length === 0;
  return report;
}

// -- CLI -------------------------------------------------------------------
function loadFiles(root, exts = [".ts", ".tsx"]) {
  return walk(root, exts).map((full) => ({
    full,
    rel: path.relative(FRONTEND, full),
    text: readFileSync(full, "utf-8"),
  }));
}

async function run() {
  const crypto = await import("node:crypto");
  const specRaw = readFileSync(CONTRACT);
  const specSha = crypto.createHash("sha256").update(specRaw).digest("hex");
  const spec = JSON.parse(specRaw.toString());
  const manifest = JSON.parse(readFileSync(MANIFEST, "utf-8"));
  const clientText = readFileSync(CLIENT, "utf-8");
  const appFiles = loadFiles(SRC).filter((f) => !f.rel.startsWith(path.join("src", "generated") + path.sep) && !f.rel.startsWith("src/generated/"));
  const testFiles = loadFiles(TESTS);

  const report = verify({ spec, specSha, manifest, clientText, appFiles, testFiles });

  console.log("API operation allowlist (positive)");
  console.log(`  contract: ${manifest.contract}  sha256: ${specSha.slice(0, 12)}…`);
  console.log(`  approved: ${manifest.approved_operation_ids.length}  forbidden: ${manifest.forbidden_operation_ids.length}`);
  console.log(`  consumed (${report.consumed.length}): ${report.consumed.join(", ")}`);
  if (report.violations.length) {
    for (const v of report.violations) console.error(`  FAIL  ${v}`);
    process.exit(1);
  }
  console.log("  OK — consumed ⊆ approved, consumed ∩ forbidden = ∅, no raw fetch, no forbidden refs");
}

if (import.meta.url === `file://${process.argv[1]}`) run();
