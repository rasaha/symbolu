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
  // ranking / selection language that would misrepresent a recommendation
  "recommended agent",
  "preferred agent",
  "preferred eligible",
  "best agent",
  "top agent",
  "ranking score",
  "rank score",
  "recommended candidate",
  "agent selected",
  "selected agent",
  "assigned agent",
  // grant / provisioning / authorization / execution language (§19). P3D DISPLAYS
  // permission proposals and feasibility (now legitimate), but must never imply
  // that access was granted, credentials issued, runtime permissions activated,
  // or an external system changed. Negated notes ("do not grant/provision/activate")
  // do not match these positive bigrams.
  "permission granted",
  "grant permission",
  "granting permission to",
  "provision permission",
  "permission provisioning",
  "runtime provisioning",
  "access granted",
  "credentials issued",
  "permission activated",
  "permissions became active",
  "authorized to execute",
  "action authorized",
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
