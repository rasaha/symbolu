// Tracked-source integrity verifier (P3D final hardening, C5 / clean-checkout).
//
// P3D discovered that the repo-root `lib/` ignore rule silently excluded the
// frontend's `src/lib/` application source, so a clean checkout could not build.
// This verifier walks every import in src/ (resolving the `@/*` alias and relative
// specifiers), and FAILS if any imported application source file that exists on disk
// is NOT tracked by Git — i.e. it is ignored or untracked and would be missing from
// a clean clone.
//
//   node scripts/verify-tracked-sources.mjs
//
// Pure helpers are exported for unit testing.
import { readFileSync, existsSync, statSync, readdirSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.dirname(HERE);
const SRC = path.join(FRONTEND, "src");
const RESOLVE_EXTS = ["", ".ts", ".tsx", ".d.ts", ".js", ".mjs", ".json", "/index.ts", "/index.tsx", "/index.js"];

export function parseSpecifiers(text) {
  const specs = [];
  const re = /(?:import|export)\b[^'"]*?from\s*['"]([^'"]+)['"]|import\s*['"]([^'"]+)['"]/g;
  let m;
  while ((m = re.exec(text))) specs.push(m[1] ?? m[2]);
  return specs;
}

// Resolve a specifier to an existing file path, or null for bare packages / unresolved.
export function resolveSpecifier(spec, fromFile, { frontendDir, srcDir }) {
  let baseNoExt;
  if (spec.startsWith("@/")) baseNoExt = path.join(srcDir, spec.slice(2));
  else if (spec.startsWith(".")) baseNoExt = path.resolve(path.dirname(fromFile), spec);
  else return null; // bare module (node_modules)
  for (const ext of RESOLVE_EXTS) {
    const candidate = baseNoExt + ext;
    if (existsSync(candidate) && statSync(candidate).isFile()) return candidate;
  }
  return null;
}

export function walk(dir, exts = [".ts", ".tsx"]) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) out.push(...walk(full, exts));
    else if (exts.some((e) => name.endsWith(e))) out.push(full);
  }
  return out;
}

// Given resolved import targets and the tracked-file set, return the untracked ones.
export function findUntracked(importTargets, trackedSet) {
  return [...new Set(importTargets)].filter((f) => !trackedSet.has(f)).sort();
}

function main() {
  const trackedRel = execFileSync("git", ["ls-files"], { cwd: FRONTEND }).toString().split("\n").filter(Boolean);
  const trackedSet = new Set(trackedRel.map((r) => path.join(FRONTEND, r)));

  const files = walk(SRC);
  const targets = [];
  const edges = [];
  for (const f of files) {
    for (const spec of parseSpecifiers(readFileSync(f, "utf-8"))) {
      const resolved = resolveSpecifier(spec, f, { frontendDir: FRONTEND, srcDir: SRC });
      if (resolved) { targets.push(resolved); edges.push({ from: f, spec, resolved }); }
    }
  }
  const untracked = findUntracked(targets, trackedSet);

  console.log("Tracked-source integrity");
  console.log(`  src files scanned: ${files.length} · resolved intra-repo imports: ${new Set(targets).size}`);
  const libTracked = walk(path.join(SRC, "lib")).every((f) => trackedSet.has(f));
  console.log(`  src/lib files tracked: ${libTracked ? "yes" : "NO"}`);
  if (untracked.length) {
    for (const u of untracked) {
      const importers = edges.filter((e) => e.resolved === u).map((e) => path.relative(FRONTEND, e.from));
      let ignoredBy = "";
      try { ignoredBy = execFileSync("git", ["check-ignore", "-v", u], { cwd: FRONTEND }).toString().trim(); } catch { /* not ignored */ }
      console.error(`  FAIL  imported but not git-tracked: ${path.relative(FRONTEND, u)}  (imported by ${importers.join(", ")})${ignoredBy ? `  [${ignoredBy}]` : ""}`);
    }
    process.exit(1);
  }
  console.log("  OK — every imported application source file is tracked by Git");
}

if (import.meta.url === `file://${process.argv[1]}`) main();
