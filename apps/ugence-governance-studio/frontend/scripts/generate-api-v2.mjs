// Deterministic OpenAPI → TypeScript type generation for the v2 contract (GAS-4/5).
//
// A SEPARATE generator from generate-api.mjs, reading a separate frozen contract
// and writing a separate output. The two documents are produced by two different
// backend applications precisely so neither can perturb the other, and mirroring
// that separation here keeps the v1 client's own drift check meaningful.
//
// Types only — no runtime dependency is generated. Hand-written request types are
// drift waiting to happen, so every v2 request/response shape comes from here.
import { readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import path from "node:path";
import openapiTS, { astToString } from "openapi-typescript";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.dirname(HERE);
const CONTRACT = path.resolve(FRONTEND, "..", "contracts", "openapi_v2.json");
const OUT = path.resolve(FRONTEND, "src", "generated", "api-v2.ts");
const HASH_OUT = path.resolve(FRONTEND, "src", "generated", "openapi-v2.hash.json");

// Every operation the studio screens consume. A contract that lost one of these would
// break a screen silently at runtime; failing generation is the cheaper discovery.
export const REQUIRED_V2_OPERATIONS = [
  "v2_constitution_validate",
  "v2_constitution_preflight",
  "v2_policy_validate",
  "v2_policy_synthesize",
  "v2_policy_compile",
  "v2_authority_list_policies",
  "v2_authority_read_policy",
  "v2_authority_read_decision",
  "v2_simulate_run",
  "v2_publish_shadow",
  "v2_observe_audit_ids",
  "v2_observe_audit_chain",
  // GAS-7 HR-D: the Review Queue and Run Detail screens (display and relay only).
  "v2_review_list_queue",
  "v2_review_read_run",
  "v2_review_read_run_events",
  "v2_review_read_approval",
  "v2_review_submit_decision",
];

// SD-2, enforced at generation time as well as in the backend suite. If a route
// naming an authority act ever reaches the contract, the client is never built.
const PROHIBITED_VERBS = ["issue", "activate", "revoke", "grant", "authorize", "clear", "execute"];

export async function generate() {
  const raw = readFileSync(CONTRACT, "utf-8");
  const sha256 = createHash("sha256").update(raw).digest("hex");
  const schema = JSON.parse(raw);

  const opIds = new Set();
  for (const [routePath, methods] of Object.entries(schema.paths ?? {})) {
    for (const op of Object.values(methods)) {
      if (op && typeof op === "object" && "operationId" in op) {
        opIds.add(op.operationId);
        const haystack = `${op.operationId} ${routePath}`.toLowerCase();
        for (const verb of PROHIBITED_VERBS) {
          if (haystack.includes(verb)) {
            throw new Error(
              `SD-2 violation in the v2 contract: ${op.operationId} (${routePath}) names '${verb}'`,
            );
          }
        }
      }
    }
  }
  const missing = REQUIRED_V2_OPERATIONS.filter((o) => !opIds.has(o));
  if (missing.length) {
    throw new Error(`v2 contract missing required operations: ${missing.join(", ")}`);
  }

  const ast = await openapiTS(schema);
  const body = astToString(ast);
  const header =
    `// AUTO-GENERATED from apps/ugence-governance-studio/contracts/openapi_v2.json\n` +
    `// DO NOT EDIT BY HAND. Regenerate with: npm run generate:api-v2\n` +
    `// source_openapi_sha256: ${sha256}\n` +
    `// api_contract_version: ${schema.info?.version}\n\n`;
  writeFileSync(OUT, header + body);
  writeFileSync(
    HASH_OUT,
    JSON.stringify(
      {
        source_openapi_sha256: sha256,
        api_contract_version: schema.info?.version,
        required_operations: REQUIRED_V2_OPERATIONS,
        operation_ids: [...opIds].sort(),
      },
      null,
      2,
    ) + "\n",
  );
  return { sha256, count: opIds.size };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  generate()
    .then(({ sha256, count }) => {
      console.log(`generated src/generated/api-v2.ts (openapi sha256 ${sha256}, ${count} operations)`);
    })
    .catch((err) => {
      console.error(String(err.message ?? err));
      process.exit(1);
    });
}
