import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { X, Loader2 } from "lucide-react";
import { Api } from "../api/client";

interface NewModDialogProps {
  open: boolean;
  onClose: () => void;
  onCreated?: (name: string, runId: string) => void;
}

const NAME_PATTERN = /^[A-Za-z][A-Za-z0-9_]{0,63}$/;

export function NewModDialog({ open, onClose, onCreated }: NewModDialogProps) {
  const [name, setName] = useState("");
  const [author, setAuthor] = useState("");
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => Api.newMod(name, author || undefined),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["mods"] });
      onCreated?.(name, data.run_id);
      setName("");
      setAuthor("");
      onClose();
    },
  });

  if (!open) return null;

  const nameOk = NAME_PATTERN.test(name);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="panel w-full max-w-md p-5 space-y-4 m-4">
        <div className="flex items-center">
          <h2 className="text-lg font-semibold">New mod</h2>
          <button onClick={onClose} className="ml-auto text-muted hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        <p className="text-sm text-muted">
          Scaffolds <code>workspace/&lt;Name&gt;/</code> with config.cpp, $PBOPREFIX$,
          scripts/, data/, gui/, plus the <code>P:\&lt;Name&gt;\</code> junction.
          Runs <code>/dayz-new-mod</code> under the hood.
        </p>

        <label className="block">
          <span className="text-sm">Mod name</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. MyMod"
            className="mt-1 w-full bg-bg border border-bg-elevated rounded px-3 py-2 text-sm font-mono focus:outline-none focus:border-accent"
          />
          {!nameOk && name.length > 0 && (
            <span className="text-xs text-warn">
              Letters, digits, underscores only. Must start with a letter. Max 64 chars.
            </span>
          )}
        </label>

        <label className="block">
          <span className="text-sm">
            Author handle <span className="text-muted">(optional — cached after first use)</span>
          </span>
          <input
            value={author}
            onChange={(e) => setAuthor(e.target.value)}
            placeholder="e.g. KurtE"
            className="mt-1 w-full bg-bg border border-bg-elevated rounded px-3 py-2 text-sm font-mono focus:outline-none focus:border-accent"
          />
        </label>

        {mutation.isError && (
          <div className="text-err text-xs">
            {(mutation.error as Error)?.message || "scaffold failed"}
          </div>
        )}

        <div className="flex gap-2 justify-end">
          <button onClick={onClose} className="btn">
            Cancel
          </button>
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
    </div>
  );
}
