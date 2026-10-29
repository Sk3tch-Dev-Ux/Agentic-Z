// D5 — settings + Anthropic test-key API.

import { api } from "./client";

export interface SettingsResponse {
  anthropic_key_set: boolean;
  anthropic_key_masked: string;
  voyage_key_set: boolean;
  voyage_key_masked: string;
  author: string | null;
  env_path: string;
}

export interface SettingsUpdate {
  anthropic_key?: string;
  voyage_key?: string;
  author?: string;
}

export interface TestKeyResponse {
  ok: boolean;
  model?: string | null;
  error?: string | null;
  latency_ms?: number | null;
}

export const SettingsApi = {
  get: () => api<SettingsResponse>("/api/settings"),
  update: (body: SettingsUpdate) =>
    api<SettingsResponse>("/api/settings", {
      method: "POST", body: JSON.stringify(body),
    }),
  testAnthropic: () =>
    api<TestKeyResponse>("/api/anthropic/test-key", { method: "POST" }),
};
