// Zustand store for app-wide status.
// Currently small (one selected mod). Will grow in D2-D5.

import { create } from "zustand";

interface StatusState {
  selectedMod: string | null;
  setSelectedMod: (name: string | null) => void;
}

export const useStatus = create<StatusState>((set) => ({
  selectedMod: null,
  setSelectedMod: (name) => set({ selectedMod: name }),
}));
