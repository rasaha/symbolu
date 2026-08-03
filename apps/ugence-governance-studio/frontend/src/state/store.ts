// Client state (§26). Limited to selection, filters, presentation sort and panel
// state. Server responses are authoritative and never mutated into editable
// business state here.
import { create } from "zustand";

export type SortKey = "identity" | "state" | "provider" | "failed" | "unknown";

export interface EligibilityFilters {
  states: string[]; // eligibility states to show; empty = all
  provider: string | null;
  residency: string | null;
  evidenceClass: string | null;
  reason: string | null;
  agentStatus: string | null;
}

export const EMPTY_FILTERS: EligibilityFilters = {
  states: [],
  provider: null,
  residency: null,
  evidenceClass: null,
  reason: null,
  agentStatus: null,
};

interface ExplorerState {
  selectedNodeId: string | null;
  selectedRoleId: string | null;
  selectedAgentKey: string | null; // `${agent_id}@${agent_version}`
  filters: EligibilityFilters;
  sort: SortKey;
  reducedMotion: boolean;
  setSelectedNode: (id: string | null) => void;
  setSelectedRole: (id: string | null) => void;
  setSelectedAgent: (key: string | null) => void;
  setFilters: (patch: Partial<EligibilityFilters>) => void;
  resetFilters: () => void;
  setSort: (sort: SortKey) => void;
  setReducedMotion: (v: boolean) => void;
}

export const useExplorerStore = create<ExplorerState>((set) => ({
  selectedNodeId: null,
  selectedRoleId: null,
  selectedAgentKey: null,
  filters: EMPTY_FILTERS,
  sort: "identity",
  reducedMotion: false,
  setSelectedNode: (id) => set({ selectedNodeId: id }),
  setSelectedRole: (id) => set({ selectedRoleId: id, selectedAgentKey: null }),
  setSelectedAgent: (key) => set({ selectedAgentKey: key }),
  setFilters: (patch) => set((s) => ({ filters: { ...s.filters, ...patch } })),
  resetFilters: () => set({ filters: EMPTY_FILTERS }),
  setSort: (sort) => set({ sort }),
  setReducedMotion: (v) => set({ reducedMotion: v }),
}));
