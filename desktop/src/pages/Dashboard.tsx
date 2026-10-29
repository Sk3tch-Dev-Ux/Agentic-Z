// D5 Dashboard — Proposals stat card now live, "Create from pitch" hero button.

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, Zap, Search, Lightbulb, Wand2 } from "lucide-react";
import { Link } from "react-router-dom";
import { Api, WatchLogEvent } from "../api/client";
import { RagApi } from "../api/rag";
import { ProposalsApi } from "../api/proposals";
import { EventFeed } from "../components/EventFeed";
import { useNotifyOnError } from "../api/notify";
import { DirectorPanel } from "../components/DirectorPanel";
import { ModCreatorDialog } from "../components/ModCreatorDialog";

export function Dashboard() {
  const preflight = useQuery({ queryKey: ["preflight"], queryFn: Api.preflight });
  const mods = useQuery({ queryKey: ["mods"], queryFn: Api.listMods });
  const activeRuns = useQuery({
    queryKey: ["activeRuns"], queryFn: Api.activeRuns, refetchInterval: 2000,
  });
  const ragManifests = useQuery({ queryKey: ["ragManifests"], queryFn: RagApi.manifests });
  const proposals = useQuery({ queryKey: ["proposals"], queryFn: ProposalsApi.list });
  const notify = useNotifyOnError();
  const [creatorOpen, setCreatorOpen] = useState(false);

  function onError(ev: WatchLogEvent) { notify(ev); }

  const ragValue = ragManifests.data?.total_chunks ?? "—";
  const ragSub = ragManifests.data?.rag_available
    ? [
        ragManifests.data.vanilla   && `${ragManifests.data.vanilla.total_chunks} vanilla`,
        ragManifests.data.workspace && `${ragManifests.data.workspace.total_chunks} workspace`,
        ragManifests.data.wiki      && `${ragManifests.data.wiki.total_chunks} wiki`,
      ].filter(Boolean).join(" · ") || "no chunks indexed"
    : "RAG offline";
  const proposalCount = proposals.data?.proposals.length ?? 0;

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6 min-h-0">
      <div className="flex items-start gap-4">
        <div className="flex-1">
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-muted text-sm mt-1">
            Live event stream below. Pick a mod from the sidebar — or hit{" "}
            <kbd className="font-mono text-[11px] bg-bg-elevated px-1 rounded">Ctrl+K</kbd>{" "}
            to search across vanilla, your code, and the wiki.
          </p>
        </div>
        <button
          onClick={() => setCreatorOpen(true)}
          className="btn-accent flex items-center gap-2"
        >
          <Wand2 className="w-4 h-4" /> New mod from pitch
        </button>
      </div>

      {preflight.data && !preflight.data.overall_ok && (
        <div className="panel border-err/40 p-4 space-y-2">
          <div className="flex items-center gap-2 text-err font-medium">
            <Activity className="w-4 h-4" /> Preflight blocking issues
          </div>
          <ul className="text-sm space-y-1 list-disc list-inside text-gray-300">
            {preflight.data.errors.map((e, i) => <li key={i}>{e}</li>)}
          </ul>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard label="Mods" value={mods.data?.mods.length ?? "—"}
                  icon={<Zap className="w-4 h-4" />} sub="in workspace/" />
        <StatCard label="Active runs" value={activeRuns.data?.runs.length ?? 0}
                  icon={<Activity className="w-4 h-4" />}
                  sub={(activeRuns.data?.runs ?? []).map((r) => r.skill).slice(0, 2).join(", ") || "idle"} />
        <StatCard label="RAG"
                  value={ragValue}
                  icon={<Search className="w-4 h-4" />}
                  sub={ragSub} />
        <Link to="/proposals" className="block">
          <StatCard label="Proposals" value={proposalCount}
                    icon={<Lightbulb className="w-4 h-4" />}
                    sub={proposalCount === 0 ? "(none pending)" : "click to review"} />
        </Link>
      </div>

      <DirectorPanel />

      <div className="min-h-[400px] flex">
        <EventFeed onError={onError} />
      </div>

      <ModCreatorDialog open={creatorOpen} onClose={() => setCreatorOpen(false)} />
    </div>
  );
}

function StatCard({
  label, value, icon, sub, muted,
}: {
  label: string; value: number | string; icon: React.ReactNode; sub: string; muted?: boolean;
}) {
  return (
    <div className={"panel p-4 " + (muted ? "opacity-60" : "")}>
      <div className={"flex items-center gap-2 text-sm font-medium " +
        (muted ? "text-muted" : "text-accent-bright")}>
        {icon} {label}
      </div>
      <div className="text-3xl font-bold mt-2">{value}</div>
      <div className="text-xs text-muted mt-1 truncate">{sub}</div>
    </div>
  );
}
