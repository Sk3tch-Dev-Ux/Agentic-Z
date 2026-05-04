import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, AlertTriangle, XCircle, Activity } from "lucide-react";
import { Api } from "../api/client";

export function StatusBar() {
  const preflight = useQuery({ queryKey: ["preflight"], queryFn: Api.preflight });
  const repoInfo = useQuery({ queryKey: ["repoInfo"], queryFn: Api.repoInfo });
  const health = useQuery({
    queryKey: ["health"],
    queryFn: Api.health,
    refetchInterval: 3000,
  });

  const status = preflight.data;
  const overallIcon = !status
    ? <Activity className="w-4 h-4 text-muted animate-pulse" />
    : status.overall_ok
      ? <CheckCircle2 className="w-4 h-4 text-ok" />
      : <XCircle className="w-4 h-4 text-err" />;

  return (
    <header className="border-b border-bg-elevated bg-bg-panel px-4 py-2 flex items-center gap-4 text-sm">
      <div className="flex items-center gap-2 font-semibold">
        <span className="text-accent-bright">⌘</span>
        Agentic-Z
      </div>

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

      <div className="ml-auto flex items-center gap-3 text-xs text-muted font-mono">
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
