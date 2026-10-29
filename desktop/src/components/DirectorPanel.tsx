// Compact director status panel used on the Dashboard and ModDetail.
// Shows: current state, last transition, active subagent, halt reason.
// Click-through to the full DirectorPage with the state diagram.

import { Link } from "react-router-dom";
import { Activity, ArrowRight, Pause } from "lucide-react";
import { useDirectorStatus } from "../api/director";

export function DirectorPanel() {
  const { status, connected } = useDirectorStatus();

  if (!status) {
    return (
      <div className="panel p-4">
        <div className="flex items-center gap-2 text-sm font-medium text-muted">
          <Activity className="w-4 h-4" /> Director
        </div>
        <div className="text-sm text-muted mt-2">
          {connected ? "No active run." : "Connecting…"}
          {" "}
          <Link to="/director" className="text-accent-bright hover:underline">
            View runs →
          </Link>
        </div>
      </div>
    );
  }

  const lastTransition = status.transitions?.[status.transitions.length - 1];
  const lastSub = status.subagent_calls?.[status.subagent_calls.length - 1];
  const lastSkill = status.skill_invocations?.[status.skill_invocations.length - 1];

  let tone = "text-accent-bright";
  if (status.status === "halted") tone = "text-err";
  else if (status.status === "done") tone = "text-ok";

  return (
    <div className="panel p-4 space-y-3">
      <div className="flex items-center gap-2">
        <Activity className={`w-4 h-4 ${tone}`} />
        <span className="font-medium text-sm">Director</span>
        <span className={"pill " + (
          status.status === "running" ? "pill-warn" :
          status.status === "halted"  ? "pill-err"  :
          status.status === "done"    ? "pill-ok"   : "pill-muted")}>
          {status.status ?? "unknown"}
        </span>
        <span className="text-xs text-muted ml-auto">
          {status.run_id ?? ""}
        </span>
      </div>

      {status.goal && (
        <div className="text-sm">
          <span className="text-muted">goal:</span>{" "}
          <span className="text-gray-200">{status.goal}</span>
          {status.mod && (
            <span className="text-muted"> · mod:{" "}
              <span className="text-accent-bright">{status.mod}</span>
            </span>
          )}
        </div>
      )}

      <div className="flex items-center gap-2 text-sm">
        <span className="text-muted">state:</span>
        <span className="pill-muted text-gray-200 font-mono">
          {status.current_state ?? "—"}
        </span>
        {lastTransition && (
          <>
            <ArrowRight className="w-3 h-3 text-muted" />
            <span className="text-muted text-xs font-mono">
              {lastTransition.from} → {lastTransition.to}
              {lastTransition.notes && <span className="text-gray-300"> ({lastTransition.notes})</span>}
            </span>
          </>
        )}
      </div>

      {lastSub && (
        <div className="text-xs text-muted">
          last subagent: <span className="text-gray-200">{lastSub.agent}</span>{" "}
          <span className="font-mono">({lastSub.mode})</span>
          {lastSub.digest && <span> — {lastSub.digest.slice(0, 100)}</span>}
        </div>
      )}

      {lastSkill && (
        <div className="text-xs text-muted">
          last skill: <span className="text-gray-200 font-mono">{lastSkill.skill}</span>{" "}
          <span className={lastSkill.exit === 0 ? "text-ok" : "text-err"}>
            exit {lastSkill.exit}
          </span>{" "}
          ({lastSkill.elapsed.toFixed(1)}s)
        </div>
      )}

      {status.halt_reason && (
        <div className="text-sm text-err flex items-center gap-1">
          <Pause className="w-3 h-3" /> {status.halt_reason}
        </div>
      )}

      <div className="flex items-center justify-between text-xs">
        <span className="text-muted">
          {status.transitions?.length ?? 0} transitions ·{" "}
          {status.files_changed?.length ?? 0} files ·{" "}
          {status.skill_invocations?.length ?? 0} skills
        </span>
        <Link to="/director" className="text-accent-bright hover:underline">
          Diagram →
        </Link>
      </div>
    </div>
  );
}
