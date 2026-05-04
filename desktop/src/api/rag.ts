// D4 — RAG search API + types.

import { api } from "./client";

export type Corpus = "vanilla" | "wiki" | "workspace" | "all";
export type FileType =
  | "c" | "cpp" | "hpp" | "h" | "layout" | "cfg" | "rvmat" | "xml" | "json" | "csv";

export interface SearchHit {
  path: string;
  file_type: string;
  parent_context: string;
  line_start: number;
  line_end: number;
  score: number;
  snippet: string;
  corpus: "vanilla" | "wiki" | "workspace";
  mod_name?: string | null;
}

export interface SearchResponse {
  hits: SearchHit[];
  corpora_queried: string[];
  rag_available: boolean;
  error?: string | null;
}

export interface FileSliceResponse {
  path: string;
  line_start: number;
  line_end: number;
  content: string;
  error?: string | null;
}

export interface ManifestSummary {
  total_chunks: number;
  embed_model: string | null;
  indexed_at_iso: string | null;
}

export interface ManifestsResponse {
  rag_available: boolean;
  vanilla?: ManifestSummary | null;
  wiki?: ManifestSummary | null;
  workspace?: ManifestSummary | null;
  total_chunks: number;
  error?: string | null;
}

export const RagApi = {
  search: (params: {
    q: string;
    corpus?: Corpus;
    top_k?: number;
    file_type?: FileType;
    mod?: string;
  }) => {
    const sp = new URLSearchParams();
    sp.set("q", params.q);
    if (params.corpus) sp.set("corpus", params.corpus);
    if (params.top_k) sp.set("top_k", String(params.top_k));
    if (params.file_type) sp.set("file_type", params.file_type);
    if (params.mod) sp.set("mod", params.mod);
    return api<SearchResponse>(`/api/rag/search?${sp.toString()}`);
  },
  fileSlice: (path: string, lineStart?: number, lineEnd?: number) => {
    const sp = new URLSearchParams({ path });
    if (lineStart) sp.set("line_start", String(lineStart));
    if (lineEnd) sp.set("line_end", String(lineEnd));
    return api<FileSliceResponse>(`/api/rag/file?${sp.toString()}`);
  },
  manifests: () => api<ManifestsResponse>("/api/rag/manifests"),
  open: (path: string, line: number = 1) =>
    api<{ ok: boolean; method?: string }>(
      `/api/rag/open?path=${encodeURIComponent(path)}&line=${line}`,
      { method: "POST" }
    ),
};
