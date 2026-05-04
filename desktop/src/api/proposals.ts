// D5 — proposal API.

import { api } from "./client";

export interface ProposalSummary {
  slug: string;
  path: string;
  skill_md_size: number;
  py_files: string[];
  modified_at: number;
  first_line: string;
}

export interface ProposalListResponse {
  proposals: ProposalSummary[];
  proposals_dir: string;
}

export interface ProposalDetail {
  slug: string;
  skill_md: string;
  py_files: Record<string, string>;
}

export const ProposalsApi = {
  list: () => api<ProposalListResponse>("/api/proposals"),
  get: (slug: string) => api<ProposalDetail>(`/api/proposals/${encodeURIComponent(slug)}`),
  edit: (slug: string, body: { skill_md?: string; py_files?: Record<string, string> }) =>
    api<{ ok: boolean; modified_at: number }>(
      `/api/proposals/${encodeURIComponent(slug)}/edit`,
      { method: "POST", body: JSON.stringify(body) }
    ),
  promote: (slug: string, deleteProposal = true) =>
    api<{
      ok: boolean;
      target_dir: string;
      files_copied: string[];
      sync_skills_exit?: number;
      sync_skills_log?: string;
    }>("/api/proposals/promote", {
      method: "POST",
      body: JSON.stringify({ slug, delete_proposal: deleteProposal }),
    }),
  refresh: (threshold = 2) =>
    api<{ ok: boolean; exit?: number; log?: string; error?: string }>(
      `/api/proposals/refresh?threshold=${threshold}`,
      { method: "POST" }
    ),
};
