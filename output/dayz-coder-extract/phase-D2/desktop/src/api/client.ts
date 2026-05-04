// Sidecar HTTP client — D1 endpoints + D2 additions.

import { invoke } from "@tauri-apps/api/core";

let cachedPort: number | null = null;

export interface SidecarStatus {
  port: number | null;
  pid: number | null;
  error: string | null;
}

async function getPort(): Promise<number> {
  if (cachedPort !== null) return cachedPort;
  try {
    const status = await invoke<SidecarStatus>("get_sidecar_status");
    if (status.port) {
      cachedPort = status.port;
      return cachedPort;
    }
  } catch {
    // Browser dev mode (non-Tauri) — fall through.
  }
  cachedPort = 7321;
  return cachedPort;
}

export async function sidecarBaseUrl(): Promise<string> {
  return `http://127.0.0.1:${await getPort()}`;
}

export async function api<T = unknown>(path: string, init?: RequestInit): Promise<T> {
  const port = await getPort();
  const res = await fetch(`http://127.0.0.1:${port}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${path} failed: ${res.status} ${res.statusText} ${text}`);
  }
  return res.json();
}

// -------- D1 types --------

export interface HealthResponse {
  status: string;
  sidecar_started_at: number;
  repo_root: string;
}

export interface RepoInfo {
  repo_root: string;
  claude_dir: string;
  workspace_dir: string;
  has_dayz_preflight_skill: boolean;
  sidecar_version: string;
}

export interface PreflightResponse {
  p_drive_mounted: boolean;
  dayz_tools_path: string | null;
  vanilla_data_path: string | null;
  workshop_junction_ok: boolean;
  overall_ok: boolean;
  errors: string[];
  warnings: string[];
}

export interface ModSummary {
  name: string;
  path: string;
  has_config_cpp: boolean;
  has_pboprefix: boolean;
  has_p_junction: boolean;
  last_modified: number;
}

export interface ModListResponse {
  mods: ModSummary[];
}

// -------- D2 types --------

export interface StartRunResponse {
  run_id: string;
  skill: string;
  args: string[];
  started_at: number;
}

export interface ActiveRun {
  run_id: string;
  mod_name: string | null;
  skill: string;
  started_at: number;
  pid: number;
}

export interface ActiveRunsResponse {
  runs: ActiveRun[];
}

export interface WatchLogEvent {
  ts: number;
  ts_iso?: string;
  event: string;
  // Common fields across event types:
  mod?: string;
  severity?: "error" | "warning" | "info";
  lane?: "config" | "script" | "asset" | "server" | "ui" | "debug" | string;
  pattern?: string;
  hint?: string;
  excerpt?: string;
  log_path?: string;
  log_tail?: string;
  exit_code?: number;
  elapsed_seconds?: number;
  consecutive_failures?: number;
  // Allow forward-compat fields:
  [key: string]: unknown;
}

export interface RunStreamLine {
  ts: number;
  stream: "stdout" | "stderr" | "exit" | "_eof";
  line?: string;
  exit_code?: number;
  elapsed?: number;
}

// -------- D1 endpoint wrappers --------

export const Api = {
  // D1
  health: () => api<HealthResponse>("/api/health"),
  repoInfo: () => api<RepoInfo>("/api/repo/info"),
  preflight: () => api<PreflightResponse>("/api/preflight"),
  listMods: () => api<ModListResponse>("/api/mods"),

  // D2
  newMod: (name: string, author?: string) =>
    api<StartRunResponse>("/api/mods/new", {
      method: "POST",
      body: JSON.stringify({ name, author }),
    }),
  buildMod: (name: string, opts: { clean?: boolean } = {}) =>
    api<StartRunResponse>(
      `/api/mods/${encodeURIComponent(name)}/build${opts.clean ? "?clean=true" : ""}`,
      { method: "POST" }
    ),
  launchMod: (name: string, mapName = "chernarus") =>
    api<StartRunResponse>(
      `/api/mods/${encodeURIComponent(name)}/launch?map_name=${encodeURIComponent(mapName)}`,
      { method: "POST" }
    ),
  stopDiag: (name: string) =>
    api<StartRunResponse>(`/api/mods/${encodeURIComponent(name)}/stop`, { method: "POST" }),
  activeRuns: () => api<ActiveRunsResponse>("/api/runs/active"),
  killRun: (runId: string) =>
    api<{ ok: boolean }>(`/api/runs/${runId}/kill`, { method: "POST" }),
};
