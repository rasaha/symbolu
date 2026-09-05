// Screen 3 — Authority. A reader.
//
// The screen shows WHICH registry answered, because an in-memory registry holds one
// process's view: an empty list from it does not mean nothing was issued anywhere.
// There is no issue and no revoke control — those entry points are permanently
// outside the studio's allowlist (SD-2).
import { GapNotice, RegistryKindNotice } from "./GapNotice";
import { Json, Panel, ScreenFrame } from "./ScreenFrame";
import { useAuthorityPolicies } from "./hooks";
import { LoadingState, QueryError } from "@/design-system/states";
import { isUnavailable } from "@/api/types-v2";

export function AuthorityScreen() {
  const policies = useAuthorityPolicies();

  return (
    <ScreenFrame
      title="Authority"
      subtitle="Which policies are issued, resolvable, revoked or superseded, and the decisions a run rested on."
      neverDoes="This screen is a reader. It never issues, revokes or supersedes a policy."
    >
      <Panel title="Issued policy records">
        {policies.isLoading ? <LoadingState label="Reading the registry…" /> : null}
        {policies.error ? <QueryError error={policies.error} /> : null}
        {policies.data ? (
          isUnavailable(policies.data) ? (
            <GapNotice gap={policies.data} />
          ) : (
            <div className="space-y-2">
              <RegistryKindNotice
                kind={String((policies.data as { registry_kind?: string }).registry_kind ?? "unknown")}
              />
              {(() => {
                const records = ((policies.data as { result?: unknown[] }).result ?? []) as unknown[];
                if (records.length === 0) {
                  return (
                    <p className="text-[12px] text-ink-2">
                      No issued records for the identities this deployment queries.
                    </p>
                  );
                }
                return <Json value={records} label={`${records.length} issued record(s)`} />;
              })()}
              <p className="text-[11px] text-ink-3">
                Identities queried:{" "}
                <span className="font-mono">
                  {(((policies.data as { identities_queried?: string[] }).identities_queried ?? []).join(", ")) ||
                    "none configured"}
                </span>
              </p>
            </div>
          )
        ) : null}
      </Panel>
    </ScreenFrame>
  );
}
