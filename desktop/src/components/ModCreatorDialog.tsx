// Mod Creator: pitch a mod idea, watch Claude scaffold it live, navigate to
// the new mod when done. Streams from POST /api/mod-creator (SSE).

import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import {
  X, Loader2, Wand2, FileText, AlertTriangle, CheckCircle2, ChevronRight,
} from "lucide-react";
import { streamModCreator, ModCreatorMessage } from "../api/modCreator";
import { SettingsApi } from "../api/settings";

interface Props {
  open: boolean;
  onClose: () => void;
}

const NAME_PATTERN = /^[A-Za-z][A-Za-z0-9_]{0,63}$/;

export function ModCreatorDialog({ open, onClose }: Props) {
  const settings = useQuery({ queryKey: ["settings"], queryFn: SettingsApi.get, enabled: open });
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [pitch, setPitch] = useState("");
  const [running, setRunning] = useState(false);
  const [events, setEvents] = useState<ModCreatorMessage[]>([]);
  const [done, setDone] = useState<{ summary: string; files: string[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const cancelRef = useRef<(() => void) | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) {
      setName(""); setPitch(""); setEvents([]); setDone(null); setError(null); setRunning(false);
      cancelRef.current?.(); cancelRef.current = null;
    }
  }, [open]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [events.length]);

  if (!open) return null;

  const nameOk = NAME_PATTERN.test(name);
  const hasKey = settings.data?.anthropic_key_set;

  async function onGenerate() {
    setError(null); setEvents([]); setDone(null); setRunning(true);
    try {
      const { cancel, promise } = await streamModCreator(
        { name, pitch, author: settings.data?.author || undefined },
        (msg) => {
          setEvents((prev) => [...prev, msg]);
          if (msg.type === "control" && msg.data.event === "done") {
            setDone({
              summary: msg.data.summary || "",
              files: msg.data.files || [],
            });
            setRunning(false);
          }
          if (msg.type === "error") {
            setError(msg.data.error || "unknown error");
            setRunning(false);
          }
        },
      );
      cancelRef.current = cancel;
      await promise;
    } catch (e) {
      setError((e as Error)?.message || "stream failed");
      setRunning(false);
    } finally {
      cancelRef.current = null;
      queryClient.invalidateQueries({ queryKey: ["mods"] });
    }
  }

  function onCancel() {
    cancelRef.current?.();
    cancelRef.current = null;
    setRunning(false);
  }

  function onOpenMod() {
    queryClient.invalidateQueries({ queryKey: ["mods"] });
    navigate(`/mod/${name}`);
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4"
         onClick={onClose}>
      <div className="panel w-full max-w-3xl max-h-[85vh] flex flex-col"
           onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 px-5 py-3 border-b border-bg-elevated">
          <Wand2 className="w-4 h-4 text-accent-bright" />
          <h2 className="font-semibold">Mod Creator</h2>
          <span className="text-xs text-muted ml-2">
            pitch → scaffold via Claude
          </span>
          <button onClick={onClose} className="ml-auto text-muted hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="px-5 py-4 space-y-3 border-b border-bg-elevated">
          {!hasKey && settings.data && (
            <div className="text-warn text-sm flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" />
              No Anthropic API key set.{" "}
              <Link to="/settings" className="underline" onClick={onClose}>
                Add one in Settings
              </Link>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="text-sm text-muted">Mod name</span>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="MyMod"
                disabled={running}
                className="mt-1 w-full bg-bg border border-bg-elevated rounded px-3 py-2 text-sm font-mono focus:outline-none focus:border-accent disabled:opacity-50"
              />
              {!nameOk && name.length > 0 && (
                <span className="text-xs text-warn">
                  letters/digits/underscores, must start with a letter, ≤64 chars
                </span>
              )}
            </label>
            <label className="block">
              <span className="text-sm text-muted">Author</span>
              <input
                value={settings.data?.author || ""}
                disabled
                className="mt-1 w-full bg-bg border border-bg-elevated rounded px-3 py-2 text-sm font-mono opacity-60"
                placeholder="(set in Settings)"
              />
            </label>
          </div>

          <label className="block">
            <span className="text-sm text-muted">Pitch your mod</span>
            <textarea
              value={pitch}
              onChange={(e) => setPitch(e.target.value)}
              disabled={running}
              rows={4}
              placeholder='e.g. "make players regenerate stamina faster after sleeping next to a campfire"'
              className="mt-1 w-full bg-bg border border-bg-elevated rounded px-3 py-2 text-sm focus:outline-none focus:border-accent disabled:opacity-50"
            />
          </label>

          <div className="flex items-center justify-end gap-2">
            {running && (
              <button onClick={onCancel} className="btn flex items-center gap-2">
                <X className="w-4 h-4" /> Cancel
              </button>
            )}
            <button
              onClick={onGenerate}
              disabled={!nameOk || !pitch.trim() || running || !hasKey}
              className="btn-accent flex items-center gap-2"
            >
              {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wand2 className="w-4 h-4" />}
              {running ? "Generating…" : "Generate"}
            </button>
          </div>
        </div>

        {/* Stream view */}
        {(events.length > 0 || error || done) && (
          <div className="flex-1 min-h-0 flex flex-col">
            <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 py-3 space-y-2 text-sm">
              {events.map((m, i) => <EventRow key={i} m={m} />)}
              {error && (
                <div className="text-err flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 mt-0.5" />
                  <div>{error}</div>
                </div>
              )}
            </div>

            {done && (
              <div className="px-5 py-3 border-t border-bg-elevated flex items-center gap-3 bg-accent-dim/20">
                <CheckCircle2 className="w-5 h-5 text-ok" />
                <div className="flex-1">
                  <div className="font-medium">Created {done.files.length} file(s)</div>
                  {done.summary && (
                    <div className="text-xs text-muted mt-1">{done.summary}</div>
                  )}
                </div>
                <button onClick={onOpenMod} className="btn-accent flex items-center gap-2">
                  Open mod <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function EventRow({ m }: { m: ModCreatorMessage }) {
  if (m.type === "file_written") {
    return (
      <div className="flex items-center gap-2 font-mono text-xs">
        <FileText className="w-3 h-3 text-accent-bright" />
        <span className="text-gray-200">{m.data.path}</span>
        <span className="text-muted">({m.data.bytes} bytes)</span>
      </div>
    );
  }
  if (m.type === "thought" && m.data.text) {
    return (
      <div className="text-xs text-muted italic pl-5 border-l-2 border-bg-elevated">
        {m.data.text}
      </div>
    );
  }
  if (m.type === "control" && m.data.event === "started") {
    return (
      <div className="text-xs text-accent-bright">
        ▸ Claude is generating <span className="font-mono">{m.data.mod}</span>{" "}
        with model <span className="font-mono">{m.data.model}</span>…
      </div>
    );
  }
  if (m.type === "error") {
    return (
      <div className="text-xs text-err flex items-center gap-2">
        <AlertTriangle className="w-3 h-3" /> {m.data.error}
      </div>
    );
  }
  return null;
}
