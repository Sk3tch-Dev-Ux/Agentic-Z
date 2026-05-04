// About dialog — version, attribution, links to docs/repo/Discord.

import { useQuery } from "@tanstack/react-query";
import { X, ExternalLink, Github, MessageSquare } from "lucide-react";
import { Api } from "../api/client";

interface Props {
  open: boolean;
  onClose: () => void;
}

export function AboutDialog({ open, onClose }: Props) {
  const repoInfo = useQuery({ queryKey: ["repoInfo"], queryFn: Api.repoInfo, enabled: open });
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" onClick={onClose}>
      <div className="panel w-full max-w-md p-5 space-y-4" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <span className="text-accent-bright">⌘</span> About Agentic-Z
          </h2>
          <button onClick={onClose} className="ml-auto text-muted hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="text-sm text-muted">
          DayZ modding command center. Built on top of the Agentic-Z CLI toolkit
          and the dayz-coder agent stack.
        </div>

        <div className="panel p-3 text-xs font-mono space-y-1">
          <Row label="Sidecar" value={repoInfo.data?.sidecar_version || "—"} />
          <Row label="Repo" value={repoInfo.data?.repo_root?.split(/[\\/]/).slice(-2).join("/") || "—"} />
        </div>

        <div className="space-y-2 text-sm">
          <a
            href="https://github.com/dayznchill/Agentic-Z"
            target="_blank" rel="noreferrer"
            className="flex items-center gap-2 text-accent-bright hover:underline"
          >
            <Github className="w-4 h-4" /> GitHub repository
            <ExternalLink className="w-3 h-3 ml-auto" />
          </a>
          <a
            href="https://discord.gg/dayznchill"
            target="_blank" rel="noreferrer"
            className="flex items-center gap-2 text-accent-bright hover:underline"
          >
            <MessageSquare className="w-4 h-4" /> DayZ n' Chill Discord
            <ExternalLink className="w-3 h-3 ml-auto" />
          </a>
        </div>

        <div className="text-xs text-muted border-t border-bg-elevated pt-3">
          Free to use for developing DayZ modifications. Built by the DayZ
          modding community. See LICENSE for details.
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex">
      <span className="text-muted w-20">{label}</span>
      <span className="text-gray-200 truncate flex-1">{value}</span>
    </div>
  );
}
