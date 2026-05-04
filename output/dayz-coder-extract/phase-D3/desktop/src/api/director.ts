// D3 — director status types + endpoint helpers + SSE hook.

import { useEventStream } from "./events";
import { api } from "./client";

export interface DirectorTransition {
  from: string;
  to: string;
  ts: number;
  notes: string;
}

export interface DirectorSubagentCall {
  ts: number;
  agent: string;
  mode: string;
  digest: string;
}

export interface DirectorSkillInvocation {
  ts: number;
  skill: string;
  exit: number;
  elapsed: number;
}

export interface DirectorStatus {
  run_id?: string;
  goal?: string;
  mod?: string;
  status?: "running" | "done" | "halted" | "refused";
  current_state?: string;
  transitions?: DirectorTransition[];
  subagent_calls?: DirectorSubagentCall[];
  files_changed?: string[];
  skill_invocations?: DirectorSkillInvocation[];
  halt_reason?: string | null;
  started_at?: number;
  updated_at?: number;
  _empty?: boolean;
}

export interface PostmortemSummary {
  name: string;
  path: string;
  modified_at: number;
  size_bytes: number;
  first_line: string;
}

export interface PostmortemListResponse {
  runs: PostmortemSummary[];
}

export interface PostmortemDetail {
  name: string;
  path: string;
  content: string;
}

export const DirectorApi = {
  listRuns: () => api<PostmortemListResponse>("/api/director/runs"),
  getRun: (name: string) =>
    api<PostmortemDetail>(`/api/director/runs/${encodeURIComponent(name)}`),
  reset: () => api<{ ok: boolean }>("/api/director/reset", { method: "POST" }),
};

/** SSE hook that returns the LATEST director status (not a list of events). */
export function useDirectorStatus() {
  const { items, connected, error } = useEventStream<DirectorStatus>({
    url: "/api/events/director",
    parse: (data) => {
      try {
        return JSON.parse(data) as DirectorStatus;
      } catch {
        return null;
      }
    },
    maxItems: 50,
  });
  // The latest non-empty record wins.
  const latest = [...items].reverse().find((s) => !s._empty) ?? null;
  return { status: latest, connected, error };
}
