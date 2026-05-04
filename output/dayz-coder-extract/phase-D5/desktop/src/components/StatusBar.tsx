import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { CheckCircle2, XCircle, Activity, Search, Settings, Lightbulb } from "lucide-react";
import { Api } from "../api/client";

interface StatusBarProps {
  onOpenSearch?: () => void;
}

export function StatusBar({ onOpenSearch }: StatusBarProps) {
  const preflight = useQuery({ queryKey: ["preflight"], queryFn: Api.preflight });
  const repoInfo = useQuery({ queryKey: ["repoInfo"], queryFn: Api.repoInfo });
  const health = useQuery({
    queryKey: ["health"], queryFn: Api.health, refetchInterval: 3000,
  });

  const status = preflight.data;
  const overallIcon = !status
    ? <Activity className="w-4 h-4 text-muted animate-pulse" />
    : status.overall_ok
      ? <CheckCircle2 className="w-4 h-4 text-ok" />
      : <XCircle className="w-4 h-4 text-err" />;

  return (
    <header className="border-b border-bg-elevated bg-bg-panel px-4 py-2 flex items-center gap-4 text-sm">
      <Link to="/" className="flex items-center gap-2 font-semibold hover:text-accent-bright">
        <span className="text-accent-bright">⌘</span>
        Agentic-Z
      </Link>

      <div className="flex items-center gap-2">
        {overallIcon}
        <span className="text-muted">Preflight</span>
        {status && (
          <span className={status.overall_ok ? "pill-ok" : "pill-err"}>
            {status.overall_ok ? "OK" : "FAIL"}
          </span>
        )}
      </div>

      <div className="flex items-center gap-2">
        <span className="text-muted">P:\</span>
        <span className={status?.p_drive_mounted ? "pill-ok" : "pill-err"}>
          {status?.p_drive_mounted ? "mounted" : "not mounted"}
        </span>
      </div>

      <div className="flex items-center gap-2">
        <span className="text-muted">DayZ Tools</span>
        <span className={status?.dayz_tools_path ? "pill-ok" : "pill-warn"}>
          {status?.dayz_tools_path ? "found" : "missing"}
        </span>
      </div>

      <div className="flex items-center gap-2">
        <span className="text-muted">Vanilla data</span>
        <span className={status?.vanilla_data_path ? "pill-ok" : "pill-warn"}>
          {status?.vanilla_data_path ? "found" : "missing"}
        </span>
      </div>

      {onOpenSearch && (
        <button
          onClick={onOpenSearch}
          className="ml-2 btn flex items-center gap-2 text-xs"
          title="Search vanilla / wiki / your code (Ctrl+K)"
        >
          <Search className="w-3 h-3" />
          <span className="text-muted">search…</span>
          <kbd className="font-mono text-[10px] text-muted ml-2">Ctrl+K</kbd>
        </button>
      )}

      <div className="ml-auto flex items-center gap-3 text-xs text-muted font-mono">
        <Link to="/proposals" className="flex items-center gap-1 hover:text-white" title="Skill proposals">
          <Lightbulb className="w-3 h-3" />
        </Link>
        <Link to="/settings" className="flex items-center gap-1 hover:text-white" title="Settings">
          <Settings className="w-3 h-3" />
        </Link>
        {repoInfo.data?.repo_root && (
          <span>repo: {repoInfo.data.repo_root.split(/[\\/]/).slice(-2).join("/")}</span>
        )}
        <span className={health.isError ? "pill-err" : "pill-muted"}>
          {health.isError ? "sidecar offline" : "sidecar ok"}
        </span>
      </div>
    </header>
  );
}
