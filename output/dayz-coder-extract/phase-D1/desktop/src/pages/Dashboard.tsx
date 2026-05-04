import { useQuery } from "@tanstack/react-query";
import { Activity, Zap, Search, Lightbulb } from "lucide-react";
import { Api } from "../api/client";

export function Dashboard() {
  const preflight = useQuery({ queryKey: ["preflight"], queryFn: Api.preflight });
  const mods = useQuery({ queryKey: ["mods"], queryFn: Api.listMods });

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-muted text-sm mt-1">
          DayZ modding command center. Pick a mod from the sidebar to start working,
          or use the panels below to check environment health.
        </p>
      </div>

      {preflight.data && !preflight.data.overall_ok && (
        <div className="panel border-err/40 p-4 space-y-2">
          <div className="flex items-center gap-2 text-err font-medium">
            <Activity className="w-4 h-4" /> Preflight blocking issues
          </div>
          <ul className="text-sm space-y-1 list-disc list-inside text-gray-300">
            {preflight.data.errors.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
          {preflight.data.warnings.length > 0 && (
            <>
              <div className="text-warn font-medium text-sm pt-2">Warnings</div>
              <ul className="text-sm space-y-1 list-disc list-inside text-gray-400">
                {preflight.data.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="panel p-4">
          <div className="flex items-center gap-2 text-accent-bright text-sm font-medium">
            <Zap className="w-4 h-4" /> Mods
          </div>
          <div className="text-3xl font-bold mt-2">{mods.data?.mods.length ?? "—"}</div>
          <div className="text-xs text-muted mt-1">
            in <code>workspace/</code>
          </div>
        </div>

        <div className="panel p-4 opacity-60">
          <div className="flex items-center gap-2 text-muted text-sm font-medium">
            <Search className="w-4 h-4" /> RAG (D4)
          </div>
          <div className="text-3xl font-bold mt-2">—</div>
          <div className="text-xs text-muted mt-1">indexed chunks</div>
        </div>

        <div className="panel p-4 opacity-60">
          <div className="flex items-center gap-2 text-muted text-sm font-medium">
            <Lightbulb className="w-4 h-4" /> Proposals (D5)
          </div>
          <div className="text-3xl font-bold mt-2">—</div>
          <div className="text-xs text-muted mt-1">pending review</div>
        </div>
      </div>

      <div className="panel p-4">
        <div className="font-medium mb-2">D1 status</div>
        <ul className="text-sm space-y-1 text-gray-300 font-mono">
          <li>✓ Sidecar reachable</li>
          <li>✓ Preflight wired to existing /dayz-preflight resolvers</li>
          <li>✓ Mod list reads workspace/ directly</li>
          <li className="text-muted">
            → D2 will add live event stream + one-click skill buttons
          </li>
        </ul>
      </div>
    </div>
  );
}
