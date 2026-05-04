// Zustand store for app-wide status.

import { create } from "zustand";

export interface ModRunState {
  buildRunId?: string;
  launchRunId?: string;
  stopRunId?: string;
}

interface StatusState {
  selectedMod: string | null;
  setSelectedMod: (name: string | null) => void;

  // Map mod name -> latest run IDs for that mod's actions.
  modRuns: Record<string, ModRunState>;
  setModRun: (mod: string, action: keyof ModRunState, runId: string | undefined) => void;
}

export const useStatus = create<StatusState>((set) => ({
  selectedMod: null,
  setSelectedMod: (name) => set({ selectedMod: name }),

  modRuns: {},
  setModRun: (mod, action, runId) =>
    set((state) => ({
      modRuns: {
        ...state.modRuns,
        [mod]: { ...(state.modRuns[mod] || {}), [action]: runId },
      },
    })),
}));
