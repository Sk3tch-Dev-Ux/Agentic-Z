// Full director page: live state machine diagram + transition log + recent
// postmortems. Also surfaces the "Ship It" handoff for triggering a run.

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, FileText, Clipboard, Check, RotateCcw } from "lucide-react";
import { Link } from "react-router-dom";
import { DirectorApi, useDirectorStatus, PostmortemSummary } from "../api/director";
import { StateMachineDiagram } from "../components/StateMachineDiagram";

export function DirectorPage() {
  const { status, connected } = useDirectorStatus();
  const runs = useQuery({ queryKey: ["directorRuns"], queryFn: DirectorApi.listRuns,
    refetchInterval: 5000 });
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);

  async function onReset() {
    if (!confirm("Clear the active director status? This won't affect the running agent.")) return;
    setResetting(true);
    try { await DirectorApi.reset(); } finally { setResetting(false); }
  }

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6 min-h-0">
      <div className="flex items-center gap-3">
        <Activity className="w-5 h-5 text-accent-bright" />
        <h1 className="text-2xl font-bold">Director</h1>
        <span className={"pill " + (
          status?.status === "running" ? "pill-warn" :
          status?.status === "halted"  ? "pill-err"  :
          status?.status === "done"    ? "pill-ok"   : "pill-muted")}>
          {status?.status ?? "idle"}
        </span>
        <span className="text-xs text-muted ml-2">
          {connected ? "live" : "connecting…"}
        </span>
        {status && (
          <button
            onClick={onReset}
            disabled={resetting}
            className="btn ml-auto flex items-center gap-1 text-xs"
            title="clear the status file (use between sessions)"
          >
            <RotateCcw className="w-3 h-3" /> Reset
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[400px_1fr] gap-6 min-h-[400px]">
        {/* State diagram */}
        <div className="panel p-3">
          <div className="text-sm font-medium mb-2">State machine</div>
          <StateMachineDiagram
            currentState={status?.current_state}
            transitions={status?.transitions}
          />
        </div>

        {/* Right column */}
        <div className="space-y-4 min-h-0">
          <RunSummary />
          <TransitionLog />
          <FilesChanged />
          <ShipItHelper />
        </div>
      </div>

      <div className="panel">
        <div className="px-3 py-2 border-b border-bg-elevated flex items-center gap-2">
          <FileText className="w-4 h-4 text-accent-bright" />
          <span className="font-medium text-sm">Past runs (postmortems)</span>
          <span className="ml-auto text-xs text-muted">
            {runs.data?.runs.length ?? "—"}
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-[260px_1fr]">
          <div className="border-r border-bg-elevated max-h-[400px] overflow-y-auto">
            {runs.data?.runs.length === 0 && (
              <div className="text-xs text-muted px-3 py-4">
                No runs yet. Use Claude Code to invoke <code>dayz-director</code> with a goal.
              </div>
            )}
            {runs.data?.runs.map((r) => (
              <button
                key={r.name}
                onClick={() => setSelectedRun(r.name)}
                className={"w-full text-left px-3 py-2 text-xs border-b border-bg-elevated/40 " +
                  (selectedRun === r.name ? "bg-accent-dim" : "hover:bg-bg-elevated")}
              >
                <div className="font-mono text-gray-200">{r.name}</div>
                <div className="text-muted truncate">{r.first_line}</div>
              </button>
            ))}
          </div>
          <PostmortemBody name={selectedRun} />
        </div>
      </div>
    </div>
  );
}

function RunSummary() {
  const { status } = useDirectorStatus();
  if (!status) return null;
  return (
    <div className="panel p-4 text-sm space-y-1">
      <div className="font-medium">{status.goal}</div>
      <div className="text-muted text-xs">
        run <span className="font-mono">{status.run_id}</span>
        {status.mod && <> · mod <span className="text-accent-bright">{status.mod}</span></>}
        {status.started_at && <> · started {new Date(status.started_at * 1000).toLocaleString()}</>}
      </div>
      {status.halt_reason && (
        <div className="text-err text-xs mt-1">halt: {status.halt_reason}</div>
      )}
    </div>
  );
}

function TransitionLog() {
  const { status } = useDirectorStatus();
  if (!status?.transitions || status.transitions.length === 0) return null;
  return (
    <div className="panel">
      <div className="px-3 py-2 border-b border-bg-elevated text-sm font-medium">
        Transition log
      </div>
      <div className="max-h-[200px] overflow-y-auto font-mono text-xs">
        {status.transitions.map((t, i) => (
          <div key={i} className="px-3 py-1 border-t border-bg-elevated/40 grid grid-cols-[auto_auto_1fr] gap-2 items-baseline">
            <span className="text-muted">
              {new Date(t.ts * 1000).toLocaleTimeString()}
            </span>
            <span className="pill-muted">
              {t.from} → {t.to}
            </span>
            <span className="text-gray-300">{t.notes}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function FilesChanged() {
  const { status } = useDirectorStatus();
  if (!status?.files_changed || status.files_changed.length === 0) return null;
  return (
    <div className="panel p-3">
      <div className="text-sm font-medium mb-2">
        Files changed ({status.files_changed.length})
      </div>
      <ul className="text-xs font-mono text-gray-200 space-y-0.5 max-h-[120px] overflow-y-auto">
        {status.files_changed.map((p) => (
          <li key={p}>{p}</li>
        ))}
      </ul>
    </div>
  );
}

function ShipItHelper() {
  const [copied, setCopied] = useState(false);
  const [goal, setGoal] = useState("ship MyMod");

  async function copyPrompt() {
    const prompt = `Use dayz-director with goal: ${goal}`;
    try {
      await navigator.clipboard.writeText(prompt);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Browser/Tauri fallback: prompt fallback
      window.prompt("Copy this and paste into Claude Code:", prompt);
    }
  }

  return (
    <div className="panel p-4 space-y-2">
      <div className="text-sm font-medium">Ship It</div>
      <p className="text-xs text-muted">
        Direct Anthropic API integration lands in D6. For now: copy the prompt below
        and paste it into your Claude Code session. The director writes status to
        the JSON file this page tails — you'll see the diagram light up live.
      </p>
      <input
        value={goal}
        onChange={(e) => setGoal(e.target.value)}
        className="w-full bg-bg border border-bg-elevated rounded px-3 py-1.5 text-sm font-mono focus:outline-none focus:border-accent"
      />
      <button
        onClick={copyPrompt}
        className="btn-accent flex items-center gap-2 text-sm"
      >
        {copied ? <Check className="w-4 h-4" /> : <Clipboard className="w-4 h-4" />}
        {copied ? "Copied" : "Copy goal prompt"}
      </button>
    </div>
  );
}

function PostmortemBody({ name }: { name: string | null }) {
  const detail = useQuery({
    queryKey: ["postmortem", name],
    queryFn: () => DirectorApi.getRun(name!),
    enabled: !!name,
  });

  if (!name) {
    return (
      <div className="text-muted text-sm p-6">
        Select a run on the left to view its postmortem.
      </div>
    );
  }
  if (detail.isLoading) return <div className="text-muted p-6 text-sm">Loading…</div>;
  if (detail.isError) return <div className="text-err p-6 text-sm">Failed to load.</div>;

  return (
    <div className="p-4 max-h-[400px] overflow-y-auto">
      <pre className="text-xs whitespace-pre-wrap font-mono text-gray-200">
        {detail.data?.content}
      </pre>
    </div>
  );
}
