// Deterministic P3D presentation mappings. Every label/tone is a fixed mapping of
// an API-provided code; unknown codes fall back to a normalized form. No planning
// value is computed. Tones reuse the contrast-verified `state.*` tokens so no new
// colors are introduced.
import { normalizeCode, type Descriptor } from "./domain";

function map(table: Record<string, Descriptor>, fallbackTone: string) {
  return (code: string): Descriptor =>
    table[code] ?? { code, label: normalizeCode(code), tone: fallbackTone, glyph: "•" };
}

export const PLAN_STATES: Record<string, Descriptor> = {
  COMPLETE: { code: "COMPLETE", label: "Complete", tone: "eligible", glyph: "✓" },
  PARTIAL: { code: "PARTIAL", label: "Partial", tone: "indeterminate", glyph: "◑" },
  NO_FEASIBLE_TEAM: { code: "NO_FEASIBLE_TEAM", label: "No feasible team", tone: "ineligible", glyph: "✕" },
  SEARCH_SPACE_EXCEEDED: { code: "SEARCH_SPACE_EXCEEDED", label: "Search space exceeded", tone: "invalid", glyph: "!" },
  INVALID_INPUT: { code: "INVALID_INPUT", label: "Invalid input", tone: "invalid", glyph: "!" },
};
export const planState = map(PLAN_STATES, "indeterminate");

export const SELECTION_STATES: Record<string, Descriptor> = {
  SELECTED_PRIMARY: { code: "SELECTED_PRIMARY", label: "Selected primary", tone: "eligible", glyph: "★" },
  SELECTED_FALLBACK: { code: "SELECTED_FALLBACK", label: "Selected fallback", tone: "governance", glyph: "☆" },
  ELIGIBLE_NOT_SELECTED: { code: "ELIGIBLE_NOT_SELECTED", label: "Eligible, not selected", tone: "indeterminate", glyph: "○" },
  INELIGIBLE: { code: "INELIGIBLE", label: "Ineligible", tone: "ineligible", glyph: "✕" },
};
export const selectionState = map(SELECTION_STATES, "indeterminate");

export const FALLBACK_STATES: Record<string, Descriptor> = {
  COMPLETE: { code: "COMPLETE", label: "Fallback available", tone: "eligible", glyph: "✓" },
  PARTIAL: { code: "PARTIAL", label: "Limited fallback", tone: "indeterminate", glyph: "◑" },
  LIMITED_FALLBACK: { code: "LIMITED_FALLBACK", label: "Limited fallback", tone: "indeterminate", glyph: "◑" },
  NO_FALLBACK_AVAILABLE: { code: "NO_FALLBACK_AVAILABLE", label: "No fallback available", tone: "ineligible", glyph: "✕" },
  NOT_APPLICABLE: { code: "NOT_APPLICABLE", label: "Not applicable", tone: "deterministic", glyph: "–" },
};
export const fallbackState = map(FALLBACK_STATES, "indeterminate");

export const PERMISSION_CATEGORIES: Record<string, Descriptor> = {
  REQUIRED: { code: "REQUIRED", label: "Required", tone: "authority", glyph: "◈" },
  REQUESTED: { code: "REQUESTED", label: "Requested", tone: "indeterminate", glyph: "○" },
  PROPOSED: { code: "PROPOSED", label: "Proposed", tone: "governance", glyph: "⬢" },
  PROHIBITED: { code: "PROHIBITED", label: "Prohibited", tone: "ineligible", glyph: "✕" },
  HUMAN_REVIEW: { code: "HUMAN_REVIEW", label: "Human review", tone: "review", glyph: "⬡" },
  GOVERNANCE_OWNED: { code: "GOVERNANCE_OWNED", label: "Governance-owned", tone: "governance", glyph: "⬢" },
};
export const permissionCategory = map(PERMISSION_CATEGORIES, "deterministic");

export const DIFF_CATEGORIES: Record<string, Descriptor> = {
  ADDED: { code: "ADDED", label: "Added", tone: "eligible", glyph: "＋" },
  REMOVED: { code: "REMOVED", label: "Removed", tone: "ineligible", glyph: "－" },
  CHANGED: { code: "CHANGED", label: "Changed", tone: "indeterminate", glyph: "≠" },
  UNCHANGED: { code: "UNCHANGED", label: "Unchanged", tone: "deterministic", glyph: "＝" },
  INCOMPATIBLE: { code: "INCOMPATIBLE", label: "Incompatible", tone: "invalid", glyph: "!" },
};
export const diffCategory = map(DIFF_CATEGORIES, "deterministic");
