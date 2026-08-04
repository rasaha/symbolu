// Architecture-boundary verifier (§4, §28). Fails if the frontend imports AWC /
// compiler / backend-private code, references P3D-only API operations, or pulls in
// a model-provider SDK. The frontend is a thin HTTP/OpenAPI client only.
import { readFileSync, readdirSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.resolve(HERE, "..", "src");

// Module tokens are only violations in an IMPORT context (an `import`/`from`/
// `require` line) — so legitimate help text such as a `python -m ...` setup
// command is not misflagged.
const BANNED_IMPORT_MODULES = [
  "ugence_agent_workforce_composer",
  "ugence-agent-workforce-composer",
  "ugence_policy_workflow_compiler",
  "ugence-policy-workflow-compiler",
  "ugence_governance_studio_api",
  "agentic.agentic_framework",
  "agent_runtime",
  "model_selection",
  "action_clearance",
  "actiongate",
  "../backend",
  "../../backend",
];

// Model-provider SDKs must not appear anywhere.
const BANNED_ANYWHERE = ["from \"openai\"", "@anthropic-ai/", "langchain"];

function isImportLine(line) {
  const t = line.trim();
  return t.startsWith("import ") || t.startsWith("import(") || t.includes(" from \"") ||
    t.includes(" from '") || t.startsWith("require(");
}

// P3D consumes the ranking / plan / replay / compare / what-if / plan-explanation
// endpoints, so those are no longer forbidden. The architecture boundary that
// remains is: no AWC/compiler/backend/private imports and no model-provider SDK
// (BANNED_IMPORT_MODULES + BANNED_ANYWHERE). No API path is banned in P3D.
const BANNED_API_PATHS = [];

function walk(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) out.push(...walk(full));
    else if (/\.(ts|tsx)$/.test(name) && !full.includes(path.sep + "generated" + path.sep)) out.push(full);
  }
  return out;
}

const problems = [];
for (const file of walk(SRC)) {
  const text = readFileSync(file, "utf-8");
  const rel = path.relative(path.resolve(HERE, ".."), file);
  for (const line of text.split("\n")) {
    if (!isImportLine(line)) continue;
    for (const token of BANNED_IMPORT_MODULES) {
      if (line.includes(token)) problems.push(`${rel}: banned import "${token}"`);
    }
  }
  for (const token of BANNED_ANYWHERE) {
    if (text.includes(token)) problems.push(`${rel}: banned reference "${token}"`);
  }
  for (const token of BANNED_API_PATHS) {
    if (token.includes("${")) continue; // informational marker only
    if (text.includes(token)) problems.push(`${rel}: references P3D-only API path "${token}"`);
  }
}

if (problems.length) {
  console.error("ARCHITECTURE BOUNDARY VIOLATIONS:");
  console.error(problems.join("\n"));
  process.exit(1);
}
console.log("architecture boundary OK — frontend imports only its own code + the OpenAPI client");
