import { useEffect, useRef } from "react";
import { Square, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { useRunStream } from "../api/events";
import { Api, RunStreamLine } from "../api/client";

interface SkillRunPanelProps {
  runId: string | null;
  title: string;
  onClose?: () => void;
}

function exitPill(line: RunStreamLine | undefined) {
  if (!line) return null;
  if (line.stream === "exit" && line.exit_code === 0) {
    return <span className="pill-ok flex items-center gap-1"><CheckCircle2 className="w-3 h-3" /> exit 0</span>;
  }
  if (line.stream === "exit") {
    return <span className="pill-err flex items-center gap-1"><XCircle className="w-3 h-3" /> exit {line.exit_code}</span>;
  }
  return null;
}

export function SkillRunPanel({ runId, title, onClose }: SkillRunPanelProps) {
  const { items } = useRunStream(runId);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [items.length]);

  if (!runId) return null;

  const exitLine = items.find((l) => l.stream === "exit");
  const isRunning = !exitLine;

  async function onKill() {
    if (!runId) return;
    try {
      await Api.killRun(runId);
    } catch (e) {
      console.error(e);
    }
  }

  return (
    <div className="panel flex flex-col min-h-[200px] max-h-[400px]">
      <div className="px-3 py-2 border-b border-bg-elevated flex items-center gap-2 text-sm">
        {isRunning ? (
          <Loader2 className="w-4 h-4 text-accent-bright animate-spin" />
        ) : (
          exitPill(exitLine)
        )}
        <span className="font-medium">{title}</span>
        <span className="text-xs text-muted font-mono ml-2">
          run {runId.slice(0, 8)}
        </span>
        <div className="ml-auto flex items-center gap-2">
          {isRunning && (
            <button
              onClick={onKill}
              className="btn flex items-center gap-1 text-xs"
              title="kill subprocess"
            >
              <Square className="w-3 h-3" /> Kill
            </button>
          )}
          {onClose && (
            <button onClick={onClose} className="btn text-xs">
              Close
            </button>
          )}
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-2 font-mono text-xs">
        {items.length === 0 && (
          <div className="text-muted text-center py-4">starting subprocess…</div>
        )}
        {items.map((line, i) => {
          if (line.stream === "exit") {
            return (
              <div key={i} className="text-muted py-1">
                ── exit {line.exit_code} ({line.elapsed?.toFixed(1)}s) ──
              </div>
            );
          }
          if (line.stream === "_eof") return null;
          return (
            <div key={i} className="whitespace-pre-wrap text-gray-200">
              {line.line}
            </div>
          );
        })}
      </div>
    </div>
  );
}
