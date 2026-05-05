// D6.2 — server map setup API.

import { api } from "./client";

export interface MapStatus {
  map: string;
  mission_template: string;
  mission_present: boolean;
  mission_path: string;
  cfg_present: boolean;
  cfg_path: string;
  profiles_present: boolean;
  ready: boolean;
}

export interface MapsListResponse {
  maps: MapStatus[];
  server_dir: string;
  dayz_server_install_present: boolean;
}

export const ServerMapsApi = {
  list: () => api<MapsListResponse>("/api/server/maps"),
  setup: (map: string) =>
    api<{ run_id: string; skill: string; args: string[]; started_at: number }>(
      `/api/server/maps/${encodeURIComponent(map)}/setup`,
      { method: "POST" }
    ),
};
