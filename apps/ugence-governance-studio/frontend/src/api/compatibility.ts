// Startup API compatibility gate (§9). Blocks the app with an honest screen when
// the backend contract/version/readiness is unsupported. No version guessing.
import { SUPPORTED_API_CONTRACT } from "@/lib/config";
import { getHealth, getReady, getVersion } from "./client";
import type { ReadinessInfo, VersionInfo } from "./types";

export interface CompatibilityCheck {
  key: string;
  label: string;
  ok: boolean;
  detail: string;
}

export interface CompatibilityReport {
  compatible: boolean;
  detectedContract: string | null;
  requiredContract: string;
  version: VersionInfo | null;
  readiness: ReadinessInfo | null;
  checks: CompatibilityCheck[];
  error?: string;
}

export async function checkCompatibility(): Promise<CompatibilityReport> {
  const required = SUPPORTED_API_CONTRACT;
  try {
    const [health, ready, version] = await Promise.all([getHealth(), getReady(), getVersion()]);
    const checks: CompatibilityCheck[] = [
      {
        key: "health",
        label: "Service healthy",
        ok: health.status === "healthy",
        detail: `status = ${health.status}`,
      },
      {
        key: "ready",
        label: "Service ready",
        ok: ready.ready === true,
        detail: ready.ready ? "ready" : "not ready — check fixture integrity / AWC version",
      },
      {
        key: "contract",
        label: "API contract supported",
        ok: version.api_contract_version === required,
        detail: `${version.api_contract_version} (required ${required})`,
      },
      {
        key: "awc",
        label: "AWC version supported by backend",
        ok: version.awc_version_supported === true,
        detail: `${version.awc_distribution_version} in ${version.supported_awc_range}`,
      },
      {
        key: "v1",
        label: "workflow_ir.v1 supported",
        ok: version.supported_workflow_contracts.includes("workflow_ir.v1"),
        detail: version.supported_workflow_contracts.join(", "),
      },
      {
        key: "v2",
        label: "workflow_ir.v2 supported",
        ok: version.supported_workflow_contracts.includes("workflow_ir.v2"),
        detail: version.supported_workflow_contracts.join(", "),
      },
      {
        key: "fixtures",
        label: "Fixture integrity ready",
        ok: ready.checks?.bundled_fixture_manifest_ok === true && ready.checks?.fixture_hashes_match === true,
        detail: "bundled + source fixture hashes match the recorded manifest",
      },
    ];
    return {
      compatible: checks.every((c) => c.ok),
      detectedContract: version.api_contract_version,
      requiredContract: required,
      version,
      readiness: ready,
      checks,
    };
  } catch (err) {
    return {
      compatible: false,
      detectedContract: null,
      requiredContract: required,
      version: null,
      readiness: null,
      checks: [],
      error: err instanceof Error ? err.message : String(err),
    };
  }
}
