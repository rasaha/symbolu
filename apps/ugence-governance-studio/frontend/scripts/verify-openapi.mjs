// OpenAPI client drift verifier (§8, §27).
//
// Fails when: the OpenAPI hash changes, generated types are stale, required
// operations disappear, operation IDs change unexpectedly, or the contract
// version is unsupported.
import { readFileSync, existsSync } from "node:fs";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { generate } from "./generate-api.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.dirname(HERE);
const CONTRACT = path.resolve(FRONTEND, "..", "contracts", "openapi.json");
const OUT = path.resolve(FRONTEND, "src", "generated", "api.ts");
const HASH_OUT = path.resolve(FRONTEND, "src", "generated", "openapi.hash.json");

const SUPPORTED_CONTRACT = "governance_studio.api.v1";

async function main() {
  const raw = readFileSync(CONTRACT, "utf-8");
  const sha256 = createHash("sha256").update(raw).digest("hex");
  const schema = JSON.parse(raw);

  if (schema.info?.version !== SUPPORTED_CONTRACT) {
    console.error(`unsupported API contract ${schema.info?.version} (need ${SUPPORTED_CONTRACT})`);
    process.exit(1);
  }
  if (!existsSync(OUT) || !existsSync(HASH_OUT)) {
    console.error("OPENAPI DRIFT: generated client missing — run npm run generate:api");
    process.exit(1);
  }

  const before = readFileSync(OUT, "utf-8");
  const beforeHash = JSON.parse(readFileSync(HASH_OUT, "utf-8"));
  await generate(); // regenerate in place
  const after = readFileSync(OUT, "utf-8");

  if (before !== after) {
    console.error("OPENAPI DRIFT: generated api.ts is stale — regenerate and commit");
    process.exit(1);
  }
  if (beforeHash.source_openapi_sha256 !== sha256) {
    console.error(
      `OPENAPI DRIFT: recorded hash ${beforeHash.source_openapi_sha256} != contract ${sha256}`,
    );
    process.exit(1);
  }
  console.log(`OpenAPI client in sync (sha256 ${sha256}, contract ${schema.info.version})`);
}

main().catch((err) => {
  console.error(String(err.message ?? err));
  process.exit(1);
});
