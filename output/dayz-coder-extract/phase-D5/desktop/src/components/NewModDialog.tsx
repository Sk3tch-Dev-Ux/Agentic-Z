// New mod dialog with two tabs: classic scaffold (/dayz-new-mod) and Pitch
// (Mod Creator). The latter is the marquee feature — user types an idea,
// Claude writes the mod.

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { X, Loader2, Wand2, FileText } from "lucide-react";
import { Api } from "../api/client";
import { ModCreatorDialog } from "./ModCreatorDialog";

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated?: (name: string, runId?: string) => void;
}

const NAME_PATTERN = /^[A-Za-z][A-Za-z0-9_]{0,63}$/;

type Tab = "pitch" | "classic";

export function NewModDialog({ open, onClose, onCreated }: Props) {
  const [tab, setTab] = useState<Tab>("pitch");
  const [name, setName] = useState("");
  const [author, setAuthor] = useState("");
  const queryClient = useQueryClient();
  const [creatorOpen, setCreatorOpen] = useState(false);

  const mutation = useMutation({
    mutationFn: () => Api.newMod(name, author || undefined),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["mods"] });
      onCreated?.(name, data.run_id);
      setName(""); setAuthor("");
      onClose();
    },
  });

  if (!open && !creatorOpen) return null;
  if (creatorOpen) {
    return <ModCreatorDialog open={creatorOpen} onClose={() => { setCreatorOpen(false); onClose(); }} />;
  }

  const nameOk = NAME_PATTERN.test(name);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="panel w-full max-w-md p-5 space-y-4 m-4" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center">
          <h2 className="text-lg font-semibold">New mod</h2>
          <button onClick={onClose} className="ml-auto text-muted hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex border-b border-bg-elevated">
          <button
            onClick={() => setTab("pitch")}
            className={"px-4 py-2 text-sm flex items-center gap-2 border-b-2 " + (
              tab === "pitch"
                ? "border-accent text-white"
                : "border-transparent text-muted hover:text-white"
            )}
          >
            <Wand2 className="w-4 h-4" /> Pitch
          </button>
          <button
            onClick={() => setTab("classic")}
            className={"px-4 py-2 text-sm flex items-center gap-2 border-b-2 " + (
              tab === "classic"
                ? "border-accent text-white"
                : "border-transparent text-muted hover:text-white"
            )}
          >
            <FileText className="w-4 h-4" /> Classic scaffold
          </button>
        </div>

        {tab === "pitch" ? (
          <div className="space-y-3">
            <p className="text-sm text-muted">
              Describe your mod in plain English. Claude reads the dayz-coder agent
              definition and writes a full mod scaffold — config.cpp, $PBOPREFIX$,
              scripts in 3_Game/4_World/5_Mission, types.xml entries — following
              the EnScript style guide.
            </p>
            <button
              onClick={() => setCreatorOpen(true)}
              className="btn-accent w-full flex items-center justify-center gap-2"
            >
              <Wand2 className="w-4 h-4" /> Open Mod Creator
            </button>
            <p className="text-xs text-muted">
              Requires an Anthropic API key (set in Settings).
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-muted">
              Empty scaffold via <code>/dayz-new-mod</code>. You write the code by hand.
            </p>
            <label className="block">
              <span className="text-sm">Mod name</span>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="MyMod"
                className="mt-1 w-full bg-bg border border-bg-elevated rounded px-3 py-2 text-sm font-mono focus:outline-none focus:border-accent"
              />
              {!nameOk && name.length > 0 && (
                <span className="text-xs text-warn">
                  letters/digits/underscores, start with a letter, ≤64 chars
                </span>
              )}
            </label>
            <label className="block">
              <span className="text-sm">Author <span className="text-muted">(optional)</span></span>
              <input
                value={author}
                onChange={(e) => setAuthor(e.target.value)}
                placeholder="KurtE"
                className="mt-1 w-full bg-bg border border-bg-elevated rounded px-3 py-2 text-sm font-mono focus:outline-none focus:border-accent"
              />
            </label>
            {mutation.isError && (
              <div className="text-err text-xs">
                {(mutation.error as Error)?.message || "scaffold failed"}
              </div>
            )}
            <div className="flex gap-2 justify-end">
              <button onClick={onClose} className="btn">Cancel</button>
              <button
                onClick={() => mutation.mutate()}
                disabled={!nameOk || mutation.isPending}
                className="btn-accent flex items-center gap-2"
              >
                {mutation.isPending && <Loader2 className="w-3 h-3 animate-spin" />}
                Scaffold
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
