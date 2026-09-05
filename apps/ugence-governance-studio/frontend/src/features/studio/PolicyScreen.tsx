// Screen 2 — Policy.
//
// The React Flow canvas is the authoring surface; the compiler is the authority on
// whether a pack is valid, synthesizable and compilable. This screen sends and shows;
// it derives nothing. Compilation always carries a real approval record — there is no
// compile-without-approval path anywhere in the studio.
import { useMemo, useState } from "react";

import { CanvasLegend, PolicyCanvas } from "@/features/canvas/PolicyCanvas";
import { packToGraph, type PolicyPackLike } from "@/features/canvas/mapper";
import { GapNotice } from "./GapNotice";
import { ActionButton, Json, Panel, ScreenFrame } from "./ScreenFrame";
import {
  useCompilePolicyPack,
  useSynthesizePolicyPack,
  useValidatePolicyPack,
} from "./hooks";
import { isUnavailable } from "@/api/types-v2";

export function PolicyScreen({
  pack,
  approval,
}: {
  pack: PolicyPackLike;
  approval: Record<string, unknown>;
}) {
  const graph = useMemo(() => packToGraph(pack), [pack]);
  const validate = useValidatePolicyPack();
  const synthesize = useSynthesizePolicyPack();
  const compile = useCompilePolicyPack();
  const [showIr, setShowIr] = useState(false);

  return (
    <ScreenFrame
      title="Policy"
      subtitle="Author a policy pack on the canvas, preview the Workflow IR it compiles to, and compile a reviewed pack."
      neverDoes="This screen never grants a permission and never executes a workflow; the compiler decides what is valid."
    >
      <Panel title="Canvas">
        <div className="mb-2">
          <CanvasLegend />
        </div>
        <PolicyCanvas graph={graph} />
        <p className="mt-2 text-[11px] text-ink-3">
          {graph.nodes.length} governance objects across four kinds. The canvas owns
          capabilities, roles, obligations and policy clauses; every other part of the
          pack passes through unchanged.
        </p>
      </Panel>

      <Panel title="Compiler">
        <div className="flex flex-wrap gap-2">
          <ActionButton onClick={() => validate.mutate({ pack })} disabled={validate.isPending}>
            Validate
          </ActionButton>
          <ActionButton
            onClick={() => {
              setShowIr(true);
              synthesize.mutate({ pack });
            }}
            disabled={synthesize.isPending}
          >
            Preview Workflow IR
          </ActionButton>
          <ActionButton
            onClick={() => compile.mutate({ pack, approval })}
            disabled={compile.isPending}
          >
            Compile with approval
          </ActionButton>
        </div>
        <p className="mt-2 text-[11px] text-ink-3">
          Validate and preview require no approval and produce no release. Compile
          requires a human approval record and is the only action that produces one.
        </p>
      </Panel>

      {validate.data ? (
        <Panel title="Validation">
          {isUnavailable(validate.data) ? (
            <GapNotice gap={validate.data} />
          ) : (
            <Json value={(validate.data as { result?: unknown }).result} label="Validation report" />
          )}
        </Panel>
      ) : null}

      {showIr && synthesize.data ? (
        <Panel title="Workflow IR preview">
          {isUnavailable(synthesize.data) ? (
            <GapNotice gap={synthesize.data} />
          ) : (synthesize.data as { synthesized?: boolean }).synthesized ? (
            <Json value={(synthesize.data as { result?: unknown }).result} label="Workflow IR" />
          ) : (
            <div className="space-y-2">
              <div role="alert" className="rounded border border-rose-300 bg-rose-50 px-3 py-2 text-[12px] text-rose-950">
                The compiler refused to synthesize this pack.{" "}
                <span className="font-mono text-[11px]">
                  {String((synthesize.data as { error_type?: string }).error_type ?? "")}
                </span>
              </div>
              <Json value={(synthesize.data as { result?: unknown }).result} label="Compiler report" />
            </div>
          )}
        </Panel>
      ) : null}

      {compile.data ? (
        <Panel title="Compiled release">
          {isUnavailable(compile.data) ? (
            <GapNotice gap={compile.data} />
          ) : (
            <div className="space-y-2">
              <div className="rounded border border-surface-border bg-surface-2 px-3 py-2 text-[12px]">
                <span className="font-semibold">
                  {(compile.data as { success?: boolean }).success ? "Compiled" : "Not compiled"}
                </span>{" "}
                <span className="font-mono text-[11px] text-ink-2">
                  {String((compile.data as { logical_digest?: string }).logical_digest ?? "")}
                </span>
              </div>
              <Json value={(compile.data as { assurance_manifest?: unknown }).assurance_manifest} label="Assurance manifest" />
            </div>
          )}
        </Panel>
      ) : null}
    </ScreenFrame>
  );
}
