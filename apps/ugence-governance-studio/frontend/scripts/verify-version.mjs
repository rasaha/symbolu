// Frontend version-consistency verifier (P3D final hardening, C5).
//
// The frontend product version is 0.2.0. This must agree across package.json,
// package-lock.json (root + root package entry), the README badge and the P3D audit
// record — WITHOUT disturbing the DISTINCT backend/API/AWC/compiler versions:
//   frontend product : 0.2.0
//   backend API dist : 0.1.0
//   API contract     : governance_studio.api.v1
//   AWC              : 0.2.1
//   compiler         : 0.2.0
//
//   node scripts/verify-version.mjs
//
// Pure helpers are exported for unit testing.
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.dirname(HERE);
const REPO = path.resolve(FRONTEND, "..", "..", "..");

export const EXPECTED_FRONTEND_VERSION = "0.2.0";
export const EXPECTED_NAME = "@ugence/governance-studio-frontend";

export function checkVersions({ pkg, lock, readme, auditLiveState }) {
  const errors = [];
  const v = EXPECTED_FRONTEND_VERSION;

  if (pkg.name !== EXPECTED_NAME) errors.push(`package.json name ${pkg.name} != ${EXPECTED_NAME}`);
  if (pkg.version !== v) errors.push(`package.json version ${pkg.version} != ${v}`);
  if (pkg.private !== true) errors.push(`package.json private must be true`);

  if (lock.version !== v) errors.push(`package-lock.json root version ${lock.version} != ${v}`);
  const rootPkg = lock.packages && lock.packages[""];
  if (!rootPkg || rootPkg.version !== v) errors.push(`package-lock.json packages[""].version ${rootPkg?.version} != ${v}`);
  if (lock.name !== EXPECTED_NAME) errors.push(`package-lock.json name ${lock.name} != ${EXPECTED_NAME}`);

  if (readme !== undefined) {
    if (!readme.includes(`\`${v}\``)) errors.push(`README does not advertise \`${v}\``);
    // the old frontend badge "`@ugence/governance-studio-frontend` `0.1.0`" must be gone
    if (/governance-studio-frontend`?\s*`?0\.1\.0/.test(readme)) errors.push(`README still shows the 0.1.0 frontend badge`);
  }

  if (auditLiveState !== undefined) {
    const after = auditLiveState?.frontend?.version_after;
    if (after !== v) errors.push(`P3D audit LIVE_STATE.json frontend.version_after ${after} != ${v}`);
  }

  return { errors, staleCount: errors.filter((e) => /0\.1\.0/.test(e)).length };
}

function main() {
  const pkg = JSON.parse(readFileSync(path.join(FRONTEND, "package.json"), "utf-8"));
  const lock = JSON.parse(readFileSync(path.join(FRONTEND, "package-lock.json"), "utf-8"));
  const readmePath = path.join(FRONTEND, "README.md");
  const readme = existsSync(readmePath) ? readFileSync(readmePath, "utf-8") : undefined;
  const auditPath = path.join(REPO, "docs", "audits", "ugence_governance_studio_p3d", "LIVE_STATE.json");
  const auditLiveState = existsSync(auditPath) ? JSON.parse(readFileSync(auditPath, "utf-8")) : undefined;

  const { errors, staleCount } = checkVersions({ pkg, lock, readme, auditLiveState });

  console.log(`Frontend version consistency (expected ${EXPECTED_FRONTEND_VERSION})`);
  console.log(`  package.json: ${pkg.version} · lockfile: ${lock.version} · lockfile packages[""]: ${lock.packages?.[""]?.version}`);
  console.log(`  stale 0.1.0 frontend references: ${staleCount}`);
  if (errors.length) {
    for (const e of errors) console.error(`  FAIL  ${e}`);
    process.exit(1);
  }
  console.log("  OK — package, lockfile, README and audit agree on 0.2.0");
}

if (import.meta.url === `file://${process.argv[1]}`) main();
