import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, XCircle, Hammer, Play, Square, ClipboardCheck, Rocket } from "lucide-react";
import { Api } from "../api/client";

export function ModDetail() {
  const { name } = useParams<{ name: string }>();
  const mods = useQuery({ queryKey: ["mods"], queryFn: Api.listMods });

  const mod = mods.data?.mods.find((m) => m.name === name);
  if (!mod) {
    return (
      <div className="flex-1 p-6">
        <h1 className="text-2xl font-bold">Mod not found</h1>
        <p className="text-muted mt-2">No mod named <code>{name}</code> in workspace.</p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{mod.name}</h1>
        <p className="text-muted text-xs mt-1 font-mono">{mod.path}</p>
      </div>

      <div className="panel p-4">
        <div className="font-medium mb-3">Source state</div>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <Row label="config.cpp"   ok={mod.has_config_cpp} />
          <Row label="$PBOPREFIX$"  ok={mod.has_pboprefix} />
          <Row label="P:\\ junction" ok={mod.has_p_junction} />
        </div>
      </div>

      <div className="panel p-4">
        <div className="font-medium mb-3">Actions (D2 wires these to subprocess)</div>
        <div className="flex flex-wrap gap-2">
          <button className="btn-accent flex items-center gap-2" disabled>
            <Hammer className="w-4 h-4" /> Build
          </button>
          <button className="btn flex items-center gap-2" disabled>
            <Play className="w-4 h-4" /> Launch
          </button>
          <button className="btn flex items-center gap-2" disabled>
            <Square className="w-4 h-4" /> Stop
          </button>
          <button className="btn flex items-center gap-2" disabled>
            <ClipboardCheck className="w-4 h-4" /> Audit
          </button>
          <button className="btn flex items-center gap-2" disabled>
            <Rocket className="w-4 h-4" /> Ship It
          </button>
        </div>
        <div className="text-xs text-muted mt-2">
          Buttons land in D2. The wiring is done; the disabled state is intentional for D1.
        </div>
      </div>
    </div>
  );
}

function Row({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="flex items-center gap-2">
      {ok ? (
        <CheckCircle2 className="w-4 h-4 text-ok" />
      ) : (
        <XCircle className="w-4 h-4 text-err" />
      )}
      <span className={ok ? "text-gray-200" : "text-err"}>{label}</span>
    </div>
  );
}
