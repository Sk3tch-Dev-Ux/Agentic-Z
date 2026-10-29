import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useLocation } from "react-router-dom";
import { Boxes, Plus, AlertTriangle } from "lucide-react";
import { Api } from "../api/client";
import { useStatus } from "../stores/useStatus";
import { NewModDialog } from "./NewModDialog";

export function ModSidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const setSelected = useStatus((s) => s.setSelectedMod);
  const mods = useQuery({ queryKey: ["mods"], queryFn: Api.listMods });
  const [dialogOpen, setDialogOpen] = useState(false);

  return (
    <aside className="w-64 border-r border-bg-elevated bg-bg-panel flex flex-col">
      <div className="px-3 py-2 border-b border-bg-elevated flex items-center gap-2">
        <Boxes className="w-4 h-4 text-accent-bright" />
        <span className="font-medium text-sm">Mods</span>
        <span className="ml-auto text-xs text-muted font-mono">
          {mods.data?.mods.length ?? "—"}
        </span>
      </div>

      <nav className="flex-1 overflow-y-auto p-2 space-y-1">
        {mods.isLoading && <div className="text-xs text-muted px-2 py-3">Loading…</div>}
        {mods.isError && (
          <div className="text-xs text-err px-2 py-3 flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" /> Sidecar unreachable
          </div>
        )}
        {mods.data?.mods.length === 0 && (
          <div className="text-xs text-muted px-2 py-3">
            No mods under <code className="text-accent-bright">workspace/</code>.
            Click "+ New mod" below to scaffold one.
          </div>
        )}
        {mods.data?.mods.map((mod) => {
          const active = location.pathname === `/mod/${mod.name}`;
          const issues =
            (!mod.has_config_cpp ? 1 : 0) +
            (!mod.has_pboprefix ? 1 : 0) +
            (!mod.has_p_junction ? 1 : 0);
          return (
            <button
              key={mod.name}
              onClick={() => {
                setSelected(mod.name);
                navigate(`/mod/${mod.name}`);
              }}
              className={
                "w-full text-left px-2 py-1.5 rounded text-sm flex items-center gap-2 " +
                (active ? "bg-accent-dim text-white" : "hover:bg-bg-elevated text-gray-200")
              }
            >
              <span className="flex-1 truncate">{mod.name}</span>
              {issues > 0 && (
                <span className="pill-warn" title={`${issues} issue(s)`}>{issues}</span>
              )}
            </button>
          );
        })}
      </nav>

      <div className="p-2 border-t border-bg-elevated">
        <button
          onClick={() => setDialogOpen(true)}
          className="btn w-full flex items-center justify-center gap-2 text-xs"
        >
          <Plus className="w-3 h-3" /> New mod
        </button>
      </div>

      <NewModDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onCreated={(name) => {
          navigate(`/mod/${name}`);
        }}
      />
    </aside>
  );
}
