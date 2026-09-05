// v2 OpenAPI client drift verifier.
//
// Separate from verify-openapi.mjs for the same reason the generators are separate:
// v1 and v2 are frozen independently, and a shared verifier would couple them.
import { readFileSync, existsSync } from "node:fs";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { generate, REQUIRED_V2_OPERATIONS } from "./generate-api-v2.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.dirname(HERE);
const CONTRACT = path.resolve(FRONTEND, "..", "contracts", "openapi_v2.json");
const OUT = path.resolve(FRONTEND, "src", "generated", "api-v2.ts");
const HASH_OUT = path.resolve(FRONTEND, "src", "generated", "openapi-v2.hash.json");

const SUPPORTED_CONTRACT = "governance_studio.api.v2";

async function main() {
  const raw = readFileSync(CONTRACT, "utf-8");
  const sha256 = createHash("sha256").update(raw).digest("hex");
  const schema = JSON.parse(raw);

  if (schema.info?.version !== SUPPORTED_CONTRACT) {
    console.error(`unsupported v2 contract ${schema.info?.version} (need ${SUPPORTED_CONTRACT})`);
    process.exit(1);
  }
  if (!existsSync(OUT) || !existsSync(HASH_OUT)) {
    console.error("V2 DRIFT: generated client missing — run npm run generate:api-v2");
    process.exit(1);
  }

  const before = readFileSync(OUT, "utf-8");
  const beforeHash = JSON.parse(readFileSync(HASH_OUT, "utf-8"));
  await generate();
  const after = readFileSync(OUT, "utf-8");

  if (before !== after) {
    console.error("V2 DRIFT: generated api-v2.ts is stale — regenerate and commit");
    process.exit(1);
  }
  if (beforeHash.source_openapi_sha256 !== sha256) {
    console.error("V2 DRIFT: committed hash does not match the contract");
    process.exit(1);
  }
  const missing = REQUIRED_V2_OPERATIONS.filter((o) => !beforeHash.operation_ids.includes(o));
  if (missing.length) {
    console.error(`V2 DRIFT: required operations missing: ${missing.join(", ")}`);
    process.exit(1);
  }
  console.log(`v2 client in sync (openapi sha256 ${sha256}, ${beforeHash.operation_ids.length} operations)`);
}

main();
