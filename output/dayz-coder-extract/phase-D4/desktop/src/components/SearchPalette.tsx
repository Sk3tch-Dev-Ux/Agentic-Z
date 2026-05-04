// Cmd+K / Ctrl+K search palette over vanilla / wiki / workspace corpora.

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, X, ExternalLink, Loader2, FileCode } from "lucide-react";
import { RagApi, SearchHit, Corpus } from "../api/rag";
import { useHotkey } from "../hooks/useHotkey";

interface Props {
  open: boolean;
  onClose: () => void;
}

const CORPORA: { id: Corpus; label: string; tone: string }[] = [
  { id: "all",       label: "All",        tone: "text-gray-200" },
  { id: "vanilla",   label: "Vanilla",    tone: "text-accent-bright" },
  { id: "workspace", label: "My code",    tone: "text-warn" },
  { id: "wiki",      label: "Wiki",       tone: "text-muted" },
];

function corpusBadge(corpus: string): string {
  switch (corpus) {
    case "vanilla":   return "pill-ok";
    case "workspace": return "pill-warn";
    case "wiki":      return "pill-muted";
    default:          return "pill-muted";
  }
}

function shortenPath(p: string, maxLen = 60): string {
  if (p.length <= maxLen) return p;
  // Show the trailing portion (file name + closest folders).
  return "…" + p.slice(p.length - maxLen + 1);
}

export function SearchPalette({ open, onClose }: Props) {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [corpus, setCorpus] = useState<Corpus>("all");
  const [activeHit, setActiveHit] = useState<SearchHit | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Debounce 300ms
  useEffect(() => {
    const t = setTimeout(() => setDebounced(query), 300);
    return () => clearTimeout(t);
  }, [query]);

  const search = useQuery({
    queryKey: ["rag", "search", debounced, corpus],
    queryFn: () => RagApi.search({ q: debounced, corpus, top_k: 5 }),
    enabled: open && debounced.trim().length >= 2,
    refetchInterval: false,
    staleTime: 60_000,
  });

  // Focus the input on open
  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  // Esc closes
  useHotkey({ key: "Escape" }, onClose, open);

  if (!open) return null;

  const hits = search.data?.hits || [];
  const ragAvailable = search.data?.rag_available;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/70 flex items-start justify-center pt-[12vh]"
      onClick={onClose}
    >
      <div
        className="panel w-full max-w-3xl mx-4 flex flex-col max-h-[70vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-bg-elevated">
          <Search className="w-4 h-4 text-muted" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search vanilla / wiki / your code…"
            className="flex-1 bg-transparent outline-none text-sm placeholder-muted"
          />
          {search.isFetching && <Loader2 className="w-4 h-4 animate-spin text-muted" />}
          <button onClick={onClose} className="text-muted hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Corpus filter */}
        <div className="flex items-center gap-2 px-4 py-2 border-b border-bg-elevated text-xs">
          {CORPORA.map((c) => (
            <button
              key={c.id}
              onClick={() => setCorpus(c.id)}
              className={
                "pill " +
                (corpus === c.id
                  ? "bg-accent-dim text-white"
                  : "bg-bg-elevated text-muted hover:text-white")
              }
            >
              {c.label}
            </button>
          ))}
          <span className="ml-auto text-muted">
            {hits.length > 0 && `${hits.length} hit${hits.length === 1 ? "" : "s"}`}
            {search.data?.error && <span className="text-err">{search.data.error}</span>}
          </span>
        </div>

        {/* Results */}
        <div className="flex flex-1 min-h-0">
          <div className="flex-1 overflow-y-auto">
            {!ragAvailable && search.data && (
              <div className="p-4 text-sm text-warn">
                RAG isn't available. Run <code>/dayz-rag-download</code> or
                <code> /dayz-rag-index</code> first.
              </div>
            )}
            {debounced.trim().length < 2 && (
              <div className="p-4 text-sm text-muted">
                Type at least 2 characters to search. Esc to close.
              </div>
            )}
            {hits.length === 0 && debounced.trim().length >= 2 && !search.isFetching && (
              <div className="p-4 text-sm text-muted">No matches.</div>
            )}
            {hits.map((hit, i) => (
              <button
                key={i}
                onClick={() => setActiveHit(hit)}
                className={
                  "w-full text-left px-4 py-2 border-b border-bg-elevated/40 " +
                  (activeHit === hit ? "bg-bg-elevated" : "hover:bg-bg-elevated/50")
                }
              >
                <div className="flex items-center gap-2 text-xs mb-1">
                  <span className={corpusBadge(hit.corpus)}>{hit.corpus}</span>
                  {hit.mod_name && (
                    <span className="pill-muted text-warn">{hit.mod_name}</span>
                  )}
                  {hit.file_type && (
                    <span className="pill-muted">.{hit.file_type}</span>
                  )}
                  <span className="font-mono text-muted truncate">
                    {shortenPath(hit.path)}
                    {hit.line_start > 0 && `:${hit.line_start}`}
                  </span>
                  <span className="ml-auto text-muted text-[10px] font-mono">
                    {hit.score.toFixed(3)}
                  </span>
                </div>
                {hit.parent_context && (
                  <div className="text-xs text-accent-bright font-mono mb-1">
                    {hit.parent_context}
                  </div>
                )}
                <pre className="text-xs whitespace-pre-wrap text-gray-300 line-clamp-3 font-mono">
                  {hit.snippet}
                </pre>
              </button>
            ))}
          </div>

          {/* Preview pane */}
          {activeHit && (
            <div className="w-2/5 border-l border-bg-elevated flex flex-col min-h-0">
              <PreviewPane hit={activeHit} />
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-2 border-t border-bg-elevated text-[11px] text-muted flex items-center gap-3">
          <kbd className="font-mono">↑↓</kbd> navigate
          <kbd className="font-mono">Enter</kbd> open in editor
          <kbd className="font-mono">Esc</kbd> close
        </div>
      </div>
    </div>
  );
}

function PreviewPane({ hit }: { hit: SearchHit }) {
  const slice = useQuery({
    queryKey: ["rag", "fileSlice", hit.path, hit.line_start, hit.line_end],
    queryFn: () => RagApi.fileSlice(
      hit.path,
      Math.max(1, hit.line_start - 5),
      hit.line_end + 5,
    ),
    enabled: !!hit.path,
    staleTime: 60_000,
  });

  async function onOpenInEditor() {
    try {
      await RagApi.open(hit.path, hit.line_start || 1);
    } catch (e) {
      console.error(e);
    }
  }

  return (
    <div className="flex flex-col min-h-0 h-full">
      <div className="px-3 py-2 border-b border-bg-elevated flex items-center gap-2">
        <FileCode className="w-4 h-4 text-accent-bright" />
        <span className="text-xs font-mono truncate">{hit.path}</span>
        <button
          onClick={onOpenInEditor}
          className="btn ml-auto flex items-center gap-1 text-xs"
          title="open in your editor"
        >
          <ExternalLink className="w-3 h-3" /> Open
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-3">
        {slice.isLoading && <div className="text-xs text-muted">loading…</div>}
        {slice.isError && (
          <div className="text-xs text-err">
            {(slice.error as Error)?.message || "fetch failed"}
          </div>
        )}
        {slice.data && (
          <pre className="text-xs font-mono whitespace-pre-wrap text-gray-200">
            {slice.data.content}
          </pre>
        )}
      </div>
    </div>
  );
}
