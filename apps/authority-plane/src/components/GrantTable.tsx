import type { Grant } from "@/api/client";

function str(grant: Grant, key: string): string {
  const v = grant[key];
  return v === null || v === undefined ? "—" : typeof v === "object" ? JSON.stringify(v) : String(v);
}

function principalId(grant: Grant): string {
  const p = grant.principal as Record<string, unknown> | undefined;
  return p ? String(p.principal_id ?? "—") : "—";
}

function principalKind(grant: Grant): string {
  const p = grant.principal as Record<string, unknown> | undefined;
  return p ? String(p.principal_kind ?? "—") : "—";
}

function validity(grant: Grant, key: "issued_at" | "expires_at"): string {
  const v = grant.validity as Record<string, unknown> | undefined;
  return v ? String(v[key] ?? "—") : "—";
}

function isRevoked(grant: Grant): boolean {
  const v = grant.revoked_at;
  return v !== null && v !== undefined && v !== "";
}

export function GrantTable({ grants, label, onEvents, onRevoke, revokeEnabled = false }: {
  grants: Grant[];
  label: string;
  onEvents?: (grantId: string) => void;
  /** Present when the screen offers the revoke write; disabled until a token is presented (AW-3). */
  onRevoke?: (grantId: string) => void;
  revokeEnabled?: boolean;
}) {
  if (grants.length === 0) {
    return (
      <p role="status" aria-label={`${label} empty`} className="text-[12px] text-neutral-700">
        No grant of this tenant matches, at this instant. An empty list is what the directory holds, not a refusal.
      </p>
    );
  }
  const actions = Boolean(onEvents || onRevoke);
  return (
    <div className="overflow-x-auto">
      <table aria-label={label} className="w-full text-[12px]">
        <thead>
          <tr className="border-b border-neutral-300 text-left text-[11px] uppercase tracking-wide text-neutral-700">
            <th className="py-1 pr-3">Principal</th>
            <th className="py-1 pr-3">Kind</th>
            <th className="py-1 pr-3">Role</th>
            <th className="py-1 pr-3">Scope</th>
            <th className="py-1 pr-3">Issued</th>
            <th className="py-1 pr-3">Expires</th>
            <th className="py-1 pr-3">Loaded by</th>
            <th className="py-1 pr-3">Grant id</th>
            {actions ? <th className="py-1" /> : null}
          </tr>
        </thead>
        <tbody>
          {grants.map((g) => (
            <tr key={g.grant_id} className="border-b border-neutral-200 align-top">
              <td className="py-1 pr-3 font-mono">{principalId(g)}</td>
              <td className="py-1 pr-3">{principalKind(g)}</td>
              <td className="py-1 pr-3">{g.role}</td>
              <td className="py-1 pr-3 font-mono">{g.scope}</td>
              <td className="py-1 pr-3 font-mono">{validity(g, "issued_at")}</td>
              <td className="py-1 pr-3 font-mono">{validity(g, "expires_at")}</td>
              <td className="py-1 pr-3 font-mono">{str(g, "loaded_by")}</td>
              <td className="py-1 pr-3 font-mono">{g.grant_id}</td>
              {actions ? (
                <td className="py-1">
                  <div className="flex gap-1">
                    {onEvents ? (
                      <button type="button" className="btn-action px-2 py-0.5 text-[11px]" onClick={() => onEvents(g.grant_id)}>
                        Events
                      </button>
                    ) : null}
                    {onRevoke && !isRevoked(g) ? (
                      <button
                        type="button"
                        className="btn-action px-2 py-0.5 text-[11px]"
                        aria-label={`revoke ${g.grant_id}`}
                        title={revokeEnabled ? "revoke this grant" : "present an issuer token to revoke"}
                        disabled={!revokeEnabled}
                        onClick={() => onRevoke(g.grant_id)}
                      >
                        Revoke…
                      </button>
                    ) : null}
                  </div>
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
