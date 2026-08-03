// Deterministic OpenAPI → TypeScript type generation (§8).
//
// Reads the FROZEN committed contract and emits src/generated/api.ts with a
// header recording the source OpenAPI sha256, so drift is detectable. No runtime
// dependency is generated — types only.
import { readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import path from "node:path";
import openapiTS, { astToString } from "openapi-typescript";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.dirname(HERE);
const CONTRACT = path.resolve(FRONTEND, "..", "contracts", "openapi.json");
const OUT = path.resolve(FRONTEND, "src", "generated", "api.ts");
const HASH_OUT = path.resolve(FRONTEND, "src", "generated", "openapi.hash.json");

const REQUIRED_OPERATIONS = [
  "get_health",
  "get_ready",
  "get_version",
  "list_scenarios",
  "get_scenario",
  "get_scenario_workflow",
  "get_scenario_registry",
  "get_scenario_eligibility",
  "explain_eligibility",
];

export async function generate() {
  const raw = readFileSync(CONTRACT, "utf-8");
  const sha256 = createHash("sha256").update(raw).digest("hex");
  const schema = JSON.parse(raw);

  // Sanity: every operation P3C consumes must exist in the frozen contract.
  const opIds = new Set();
  for (const methods of Object.values(schema.paths ?? {})) {
    for (const op of Object.values(methods)) {
      if (op && typeof op === "object" && "operationId" in op) opIds.add(op.operationId);
    }
  }
  const missing = REQUIRED_OPERATIONS.filter((o) => !opIds.has(o));
  if (missing.length) {
    throw new Error(`contract missing required operations: ${missing.join(", ")}`);
  }

  const ast = await openapiTS(schema);
  const body = astToString(ast);
  const header =
    `// AUTO-GENERATED from apps/ugence-governance-studio/contracts/openapi.json\n` +
    `// DO NOT EDIT BY HAND. Regenerate with: npm run generate:api\n` +
    `// source_openapi_sha256: ${sha256}\n` +
    `// api_contract_version: ${schema.info?.version}\n\n`;
  writeFileSync(OUT, header + body);
  writeFileSync(
    HASH_OUT,
    JSON.stringify(
      {
        source_openapi_sha256: sha256,
        api_contract_version: schema.info?.version,
        required_operations: REQUIRED_OPERATIONS,
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
      console.log(`generated src/generated/api.ts (openapi sha256 ${sha256}, ${count} operations)`);
    })
    .catch((err) => {
      console.error(String(err.message ?? err));
      process.exit(1);
    });
}
