// Terminology verifier (§21, §28). Fails if the UI uses ranking/selection/
// authorization language that would misrepresent eligibility as selection.
// Scenario-level "recommended demo" phrasing is allowed; agent-level ranking or
// preference language is not.
import { readFileSync, readdirSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.resolve(HERE, "..", "src");

const BANNED = [
  // ranking / selection / assignment language
  "recommended agent",
  "preferred agent",
  "preferred eligible",
  "best agent",
  "top agent",
  "ranking score",
  "rank score",
  "recommended candidate",
  "authorized to execute",
  "permission granted",
  "agent selected",
  "selected agent",
  "assigned agent",
  // P3D permission-PROPOSAL / granting / provisioning language (C2). P3C displays
  // permission REQUIREMENTS used during eligibility, never composition-time
  // proposals or grants. These phrases only appear if that boundary is crossed;
  // the correct negated banner text ("No permission granting") does not match them.
  "permission proposal",
  "proposed permission",
  "permission-bound proposal",
  "permission bound proposal",
  "grant permission",
  "granting permission to",
  "provision permission",
  "permission provisioning",
  "permission-feasibility",
];

function walk(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) out.push(...walk(full));
    else if (/\.(ts|tsx)$/.test(name)) out.push(full);
  }
  return out;
}

const problems = [];
for (const file of walk(SRC)) {
  const text = readFileSync(file, "utf-8").toLowerCase();
  const rel = path.relative(path.resolve(HERE, ".."), file);
  for (const phrase of BANNED) {
    if (text.includes(phrase)) problems.push(`${rel}: banned phrase "${phrase}"`);
  }
}

if (problems.length) {
  console.error("TERMINOLOGY VIOLATIONS:");
  console.error(problems.join("\n"));
  process.exit(1);
}
console.log("terminology OK — no ranking/selection/authorization language");
