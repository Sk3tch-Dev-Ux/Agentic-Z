// Proposals page — review skill drafts produced by /agentic-z-promote-skill.

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Lightbulb, RefreshCw, FileText, ArrowUpRight, Save, Loader2, Trash2, AlertTriangle,
} from "lucide-react";
import { ProposalsApi, ProposalSummary } from "../api/proposals";

export function ProposalsPage() {
  const list = useQuery({ queryKey: ["proposals"], queryFn: ProposalsApi.list });
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const [editorContent, setEditorContent] = useState<string>("");
  const [editorDirty, setEditorDirty] = useState(false);

  const refreshMut = useMutation({
    mutationFn: () => ProposalsApi.refresh(2),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["proposals"] }),
  });

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6 min-h-0">
      <div className="flex items-center gap-3">
        <Lightbulb className="w-5 h-5 text-accent-bright" />
        <h1 className="text-2xl font-bold">Skill proposals</h1>
        <span className="ml-auto text-xs text-muted">
          {list.data?.proposals_dir}
        </span>
        <button
          onClick={() => refreshMut.mutate()}
          disabled={refreshMut.isPending}
          className="btn flex items-center gap-2 text-sm"
        >
          {refreshMut.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
          Re-scan
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-[320px_1fr] gap-6 min-h-[500px]">
        {/* List */}
        <div className="panel">
          <div className="px-3 py-2 border-b border-bg-elevated text-sm font-medium flex items-center gap-2">
            <span>Drafts</span>
            <span className="ml-auto text-xs text-muted">
              {list.data?.proposals.length ?? "—"}
            </span>
          </div>
          <div className="max-h-[600px] overflow-y-auto">
            {list.data?.proposals.length === 0 && (
              <div className="text-xs text-muted px-3 py-4">
                No proposals yet. Run the promoter via "Re-scan" or invoke{" "}
                <code>/agentic-z-promote-skill</code> manually after a few mods.
              </div>
            )}
            {list.data?.proposals.map((p) => (
              <button
                key={p.slug}
                onClick={() => {
                  setSelected(p.slug); setEditorDirty(false);
                }}
                className={"w-full text-left px-3 py-2 text-sm border-b border-bg-elevated/40 " +
                  (selected === p.slug ? "bg-accent-dim text-white" : "hover:bg-bg-elevated text-gray-200")}
              >
                <div className="font-mono">{p.slug}</div>
                <div className="text-xs text-muted truncate">{p.first_line}</div>
                <div className="text-[10px] text-muted mt-0.5">
                  {p.py_files.length} script · SKILL.md {p.skill_md_size}B
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Detail / editor */}
        <div className="min-h-0 flex flex-col">
          {!selected && (
            <div className="text-muted text-sm p-6">
              Select a draft on the left.
            </div>
          )}
          {selected && (
            <ProposalEditor
              slug={selected}
              editorContent={editorContent}
              setEditorContent={setEditorContent}
              dirty={editorDirty}
              setDirty={setEditorDirty}
              onPromoted={() => {
                setSelected(null); setEditorContent(""); setEditorDirty(false);
                queryClient.invalidateQueries({ queryKey: ["proposals"] });
              }}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function ProposalEditor({
  slug, editorContent, setEditorContent, dirty, setDirty, onPromoted,
}: {
  slug: string;
  editorContent: string;
  setEditorContent: (s: string) => void;
  dirty: boolean;
  setDirty: (b: boolean) => void;
  onPromoted: () => void;
}) {
  const detail = useQuery({
    queryKey: ["proposal", slug],
    queryFn: () => ProposalsApi.get(slug),
  });
  const queryClient = useQueryClient();

  // Sync detail → editor on first load only.
  if (detail.data && !dirty && editorContent !== detail.data.skill_md && editorContent === "") {
    setEditorContent(detail.data.skill_md);
  }

  const saveMut = useMutation({
    mutationFn: () => ProposalsApi.edit(slug, { skill_md: editorContent }),
    onSuccess: () => {
      setDirty(false);
      queryClient.invalidateQueries({ queryKey: ["proposal", slug] });
    },
  });

  const promoteMut = useMutation({
    mutationFn: () => ProposalsApi.promote(slug, true),
    onSuccess: onPromoted,
  });

  if (detail.isLoading) return <div className="text-muted p-4">loading…</div>;
  if (!detail.data) return null;

  return (
    <div className="panel flex flex-col flex-1 min-h-0">
      <div className="px-3 py-2 border-b border-bg-elevated flex items-center gap-2">
        <FileText className="w-4 h-4 text-accent-bright" />
        <span className="font-mono text-sm">{slug}/SKILL.md</span>
        {dirty && <span className="pill-warn">unsaved</span>}
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={() => saveMut.mutate()}
            disabled={!dirty || saveMut.isPending}
            className="btn flex items-center gap-2 text-xs"
          >
            {saveMut.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
            Save
          </button>
          <button
            onClick={() => {
              if (confirm(`Promote ${slug} into .claude/skills/? The proposal folder will be deleted afterward.`)) {
                promoteMut.mutate();
              }
            }}
            disabled={dirty || promoteMut.isPending}
            className="btn-accent flex items-center gap-2 text-xs"
            title={dirty ? "save before promoting" : "promote into .claude/skills/"}
          >
            {promoteMut.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : <ArrowUpRight className="w-3 h-3" />}
            Promote
          </button>
        </div>
      </div>

      <textarea
        value={editorContent}
        onChange={(e) => { setEditorContent(e.target.value); setDirty(true); }}
        spellCheck={false}
        className="flex-1 bg-bg p-4 text-xs font-mono leading-relaxed text-gray-200 outline-none resize-none"
      />

      {Object.keys(detail.data.py_files).length > 0 && (
        <div className="border-t border-bg-elevated px-3 py-2 text-xs">
          <div className="text-muted mb-1">Skeleton scripts (read-only here; edit on disk):</div>
          {Object.keys(detail.data.py_files).map((name) => (
            <div key={name} className="font-mono text-gray-300">{name}</div>
          ))}
        </div>
      )}

      {promoteMut.isError && (
        <div className="text-xs text-err px-3 py-2 flex items-center gap-2">
          <AlertTriangle className="w-3 h-3" /> {(promoteMut.error as Error).message}
        </div>
      )}
      {promoteMut.data?.sync_skills_log && (
        <div className="text-xs px-3 py-2 border-t border-bg-elevated">
          <div className="text-muted">/sync-skills exit {promoteMut.data.sync_skills_exit}</div>
          <pre className="mt-1 whitespace-pre-wrap text-[10px] max-h-24 overflow-y-auto">
            {promoteMut.data.sync_skills_log}
          </pre>
        </div>
      )}
    </div>
  );
}
