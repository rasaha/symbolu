// Screen 5 — Publish.
//
// SHADOW is the only mode this screen can reach, and the client cannot reach the
// console's authorize or clear routes at all. The button says "shadow" because that
// is what it does; a button labelled "publish" that quietly meant shadow would be the
// wrong kind of reassuring.
//
// The only thing this screen can send is the release the Policy screen compiled in
// this session. With no such release there is nothing to send, and the screen says
// so rather than posting an empty package and letting the console answer for it.
import { GapNotice } from "./GapNotice";
import { useStudioRelease } from "./release";
import { ActionButton, Json, Panel, ScreenFrame } from "./ScreenFrame";
import { usePublishShadow } from "./hooks";
import { isUnavailable, type Unavailable } from "@/api/types-v2";

const NO_RELEASE: Unavailable = {
  available: false,
  capability: "compiled_release",
  reason:
    "No compiled release exists in this session. Compile a reviewed pack with its approval record on the Policy screen first; only that output can be sent to the shadow loop.",
  result: null,
};

export function PublishScreen() {
  const publish = usePublishShadow();
  const { release } = useStudioRelease();

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
        {release ? (
          <div
            data-testid="compiled-release"
            className="mb-2 rounded border border-surface-border bg-surface-2 px-3 py-2 text-[12px]"
          >
            Compiled release{" "}
            <span className="font-mono text-[11px] text-ink-2">{release.logicalDigest}</span>
          </div>
        ) : (
          <div className="mb-2">
            <GapNotice gap={NO_RELEASE} />
          </div>
        )}
        <ActionButton
          onClick={() => {
            if (release) publish.mutate({ compiled_package: release.compiledPackage });
          }}
          disabled={release === null || publish.isPending}
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
