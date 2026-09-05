// Screen 5 — Publish.
//
// SHADOW is the only mode this screen can reach, and the client cannot reach the
// console's authorize or clear routes at all. The button says "shadow" because that
// is what it does; a button labelled "publish" that quietly meant shadow would be the
// wrong kind of reassuring.
import { GapNotice } from "./GapNotice";
import { ActionButton, Json, Panel, ScreenFrame } from "./ScreenFrame";
import { usePublishShadow } from "./hooks";
import { isUnavailable } from "@/api/types-v2";

export function PublishScreen({ compiledPackage }: { compiledPackage: Record<string, unknown> }) {
  const publish = usePublishShadow();

  return (
    <ScreenFrame
      title="Publish"
      subtitle="Hand a compiled release package to the console's shadow governed loop and see what came back."
      neverDoes="Shadow only. This screen cannot authorize an action, clear one, or run a live loop."
    >
      <Panel title="Shadow governed loop">
        <p className="mb-2 text-[11px] text-ink-3">
          A shadow run observes; it changes nothing in any target system. The studio&rsquo;s
          console client is restricted to four read and shadow routes, so no other console
          operation is reachable from this screen even by mistake.
        </p>
        <ActionButton
          onClick={() => publish.mutate({ compiled_package: compiledPackage })}
          disabled={publish.isPending}
        >
          Send to shadow loop
        </ActionButton>
      </Panel>

      {publish.data ? (
        <Panel title="Console response">
          {isUnavailable(publish.data) ? (
            <GapNotice gap={publish.data} />
          ) : (
            <div className="space-y-2">
              <div className="rounded border border-surface-border bg-surface-2 px-3 py-2 text-[12px]">
                Mode{" "}
                <span className="font-mono text-[11px]">
                  {String((publish.data as { mode?: string }).mode ?? "")}
                </span>
              </div>
              <Json value={(publish.data as { result?: unknown }).result} label="Governed loop result" />
            </div>
          )}
        </Panel>
      ) : null}
    </ScreenFrame>
  );
}
