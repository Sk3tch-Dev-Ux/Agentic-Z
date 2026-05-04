// Sidecar HTTP client.
// In production the Tauri shell tells us the port via `get_sidecar_status`.
// In dev mode we default to 7321 (the sidecar's first-try port).

import { invoke } from "@tauri-apps/api/core";

let cachedPort: number | null = null;

export interface SidecarStatus {
  port: number | null;
  pid: number | null;
  error: string | null;
}

async function getPort(): Promise<number> {
  if (cachedPort !== null) return cachedPort;
  // Try the Tauri command first.
  try {
    const status = await invoke<SidecarStatus>("get_sidecar_status");
    if (status.port) {
      cachedPort = status.port;
      return cachedPort;
    }
  } catch {
    // Browser dev mode (non-Tauri) — fall through to default.
  }
  cachedPort = 7321;
  return cachedPort;
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

// Typed endpoint wrappers --------------------------------------------------

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

export const Api = {
  health: () => api<HealthResponse>("/api/health"),
  repoInfo: () => api<RepoInfo>("/api/repo/info"),
  preflight: () => api<PreflightResponse>("/api/preflight"),
  listMods: () => api<ModListResponse>("/api/mods"),
};
