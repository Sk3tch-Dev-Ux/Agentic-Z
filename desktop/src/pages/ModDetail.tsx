// D3 ModDetail — Ship It button now navigates to the director page after copying
// the prompt to the clipboard. Also gets a DirectorPanel summary.

import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2, XCircle, Hammer, Play, Square, ClipboardCheck, Rocket, Loader2,
} from "lucide-react";
import { Api } from "../api/client";
import { useStatus } from "../stores/useStatus";
import { SkillRunPanel } from "../components/SkillRunPanel";
import { EventFeed } from "../components/EventFeed";
import { DirectorPanel } from "../components/DirectorPanel";

export function ModDetail() {
  const { name } = useParams<{ name: string }>();
  const navigate = useNavigate();
  const mods = useQuery({ queryKey: ["mods"], queryFn: Api.listMods });
  const queryClient = useQueryClient();
  const modRuns = useStatus((s) => s.modRuns);
  const setModRun = useStatus((s) => s.setModRun);

  const mod = mods.data?.mods.find((m) => m.name === name);
  const myRuns = name ? modRuns[name] || {} : {};

  const buildMut = useMutation({
    mutationFn: () => Api.buildMod(name!),
    onSuccess: (r) => {
      setModRun(name!, "buildRunId", r.run_id);
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ["mods"] }), 5000);
    },
  });
  const launchMut = useMutation({
    mutationFn: () => Api.launchMod(name!),
    onSuccess: (r) => setModRun(name!, "launchRunId", r.run_id),
  });
  const stopMut = useMutation({
    mutationFn: () => Api.stopDiag(name!),
    onSuccess: (r) => setModRun(name!, "stopRunId", r.run_id),
  });

  if (!mod) {
    return (
      <div className="flex-1 p-6">
        <h1 className="text-2xl font-bold">Mod not found</h1>
        <p className="text-muted mt-2">No mod named <code>{name}</code> in workspace.</p>
      </div>
    );
  }

  const anyMutating = buildMut.isPending || launchMut.isPending || stopMut.isPending;

  async function onShipIt() {
    const prompt = `Use dayz-director with goal: ship ${mod!.name}`;
    try { await navigator.clipboard.writeText(prompt); } catch {}
    navigate("/director");
  }

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6 min-h-0">
      <div>
        <h1 className="text-2xl font-bold">{mod.name}</h1>
        <p className="text-muted text-xs mt-1 font-mono">{mod.path}</p>
      </div>

      <div className="panel p-4">
        <div className="font-medium mb-3">Source state</div>
        <div className="grid grid-cols-3 gap-2 text-sm">
          <Row label="config.cpp"   ok={mod.has_config_cpp} />
          <Row label="$PBOPREFIX$"  ok={mod.has_pboprefix} />
          <Row label="P:\\ junction" ok={mod.has_p_junction} />
        </div>
      </div>

      <div className="panel p-4">
        <div className="font-medium mb-3">Actions</div>
        <div className="flex flex-wrap gap-2">
          <button className="btn-accent flex items-center gap-2"
            onClick={() => buildMut.mutate()} disabled={anyMutating}>
            {buildMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Hammer className="w-4 h-4" />}
            Build
          </button>
          <button className="btn flex items-center gap-2"
            onClick={() => launchMut.mutate()} disabled={anyMutating}>
            {launchMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            Launch
          </button>
          <button className="btn flex items-center gap-2"
            onClick={() => stopMut.mutate()} disabled={anyMutating}>
            {stopMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Square className="w-4 h-4" />}
            Stop
          </button>
          <button className="btn flex items-center gap-2 opacity-50" disabled
                  title="Anthropic API integration lands in D6">
            <ClipboardCheck className="w-4 h-4" /> Audit (D6)
          </button>
          <button className="btn flex items-center gap-2"
                  onClick={onShipIt}
                  title="Copies the goal to clipboard and opens the director page">
            <Rocket className="w-4 h-4" /> Ship It
          </button>
        </div>
      </div>

      <DirectorPanel />

      {myRuns.buildRunId && (
        <SkillRunPanel
          runId={myRuns.buildRunId}
          title={`/dayz-build-pbo ${mod.name}`}
          onClose={() => setModRun(mod.name, "buildRunId", undefined)}
        />
      )}
      {myRuns.launchRunId && (
        <SkillRunPanel
          runId={myRuns.launchRunId}
          title={`/dayz-launch-test ${mod.name}`}
          onClose={() => setModRun(mod.name, "launchRunId", undefined)}
        />
      )}
      {myRuns.stopRunId && (
        <SkillRunPanel
          runId={myRuns.stopRunId}
          title={`/dayz-stop-test`}
          onClose={() => setModRun(mod.name, "stopRunId", undefined)}
        />
      )}

      <div className="min-h-[300px]">
        <EventFeed modFilter={mod.name} />
      </div>
    </div>
  );
}

function Row({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="flex items-center gap-2">
      {ok ? <CheckCircle2 className="w-4 h-4 text-ok" /> : <XCircle className="w-4 h-4 text-err" />}
      <span className={ok ? "text-gray-200" : "text-err"}>{label}</span>
    </div>
  );
}
