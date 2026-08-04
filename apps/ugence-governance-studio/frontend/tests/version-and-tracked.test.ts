import { describe, expect, it } from "vitest";
import path from "node:path";
import { checkVersions, EXPECTED_FRONTEND_VERSION } from "../scripts/verify-version.mjs";
import { parseSpecifiers, resolveSpecifier, findUntracked } from "../scripts/verify-tracked-sources.mjs";

const FRONTEND = path.resolve(__dirname, "..");
const SRC = path.join(FRONTEND, "src");

const goodPkg = { name: "@ugence/governance-studio-frontend", version: "0.2.0", private: true };
const goodLock = { name: "@ugence/governance-studio-frontend", version: "0.2.0", packages: { "": { version: "0.2.0" } } };
const goodReadme = "Package: `@ugence/governance-studio-frontend` `0.2.0` (private)";
const goodAudit = { frontend: { version_before: "0.1.0", version_after: "0.2.0" } };

describe("C5 — version consistency", () => {
  it("passes when package, lockfile, README and audit agree on 0.2.0", () => {
    expect(EXPECTED_FRONTEND_VERSION).toBe("0.2.0");
    const { errors } = checkVersions({ pkg: goodPkg, lock: goodLock, readme: goodReadme, auditLiveState: goodAudit });
    expect(errors).toEqual([]);
  });

  it("fails when package.json version is stale", () => {
    const { errors } = checkVersions({ pkg: { ...goodPkg, version: "0.1.0" }, lock: goodLock, readme: goodReadme, auditLiveState: goodAudit });
    expect(errors.some((e: string) => e.includes("package.json version"))).toBe(true);
  });

  it("fails when the lockfile root/package version is stale (the real bug)", () => {
    const staleLock = { name: goodLock.name, version: "0.1.0", packages: { "": { version: "0.1.0" } } };
    const { errors } = checkVersions({ pkg: goodPkg, lock: staleLock, readme: goodReadme, auditLiveState: goodAudit });
    expect(errors.some((e: string) => e.includes("package-lock.json root version"))).toBe(true);
    expect(errors.some((e: string) => e.includes('packages[""]'))).toBe(true);
  });

  it("fails when private is not true", () => {
    const { errors } = checkVersions({ pkg: { ...goodPkg, private: false }, lock: goodLock, readme: goodReadme, auditLiveState: goodAudit });
    expect(errors.some((e: string) => e.includes("private"))).toBe(true);
  });

  it("fails when the README still shows the 0.1.0 frontend badge", () => {
    const stale = "Package: `@ugence/governance-studio-frontend` `0.1.0` (private)";
    const { errors } = checkVersions({ pkg: goodPkg, lock: goodLock, readme: stale, auditLiveState: goodAudit });
    expect(errors.some((e: string) => e.includes("0.1.0 frontend badge"))).toBe(true);
  });

  it("fails when the audit record disagrees", () => {
    const { errors } = checkVersions({ pkg: goodPkg, lock: goodLock, readme: goodReadme, auditLiveState: { frontend: { version_after: "0.1.0" } } });
    expect(errors.some((e: string) => e.includes("version_after"))).toBe(true);
  });
});

describe("C5 — tracked-source resolution", () => {
  it("parses import/export-from and bare import specifiers", () => {
    const text = [
      'import { a } from "@/lib/config";',
      'import b from "./local";',
      'export { c } from "../shared/x";',
      'import "@/styles.css";',
      'import type { T } from "react";',
    ].join("\n");
    expect(parseSpecifiers(text)).toEqual(["@/lib/config", "./local", "../shared/x", "@/styles.css", "react"]);
  });

  it("resolves the @/ alias to a real src file", () => {
    const resolved = resolveSpecifier("@/lib/config", path.join(SRC, "api", "client.ts"), { frontendDir: FRONTEND, srcDir: SRC });
    expect(resolved).toBe(path.join(SRC, "lib", "config.ts"));
  });

  it("resolves a relative import to a real file", () => {
    const resolved = resolveSpecifier("./operations", path.join(SRC, "features", "whatif", "WhatIfScreen.tsx"), { frontendDir: FRONTEND, srcDir: SRC });
    expect(resolved).toBe(path.join(SRC, "features", "whatif", "operations.ts"));
  });

  it("returns null for bare package specifiers", () => {
    expect(resolveSpecifier("react", path.join(SRC, "app", "App.tsx"), { frontendDir: FRONTEND, srcDir: SRC })).toBeNull();
  });

  it("flags a resolved import that is not in the tracked set", () => {
    const target = path.join(SRC, "lib", "domain-p3d.ts");
    expect(findUntracked([target], new Set())).toEqual([target]); // untracked
    expect(findUntracked([target], new Set([target]))).toEqual([]); // tracked
  });
});
