import { useMemo, useRef, useEffect, useState } from "react";
import { Activity, Filter, Trash2 } from "lucide-react";
import { useWatchEvents } from "../api/events";
import { WatchLogEvent } from "../api/client";

const SEVERITIES = ["error", "warning", "info"] as const;
const LANES = ["config", "script", "asset", "server", "ui", "debug"] as const;

type Severity = typeof SEVERITIES[number];

function severityOf(ev: WatchLogEvent): Severity {
  if (ev.event === "log_error" || ev.event === "build_failed" || ev.event === "backoff_triggered") {
    return "error";
  }
  if (ev.event === "log_warning") return "warning";
  return "info";
}

function severityClass(sev: Severity): string {
  switch (sev) {
    case "error":   return "text-err";
    case "warning": return "text-warn";
    case "info":    return "text-muted";
  }
}

function severityPill(sev: Severity): string {
  switch (sev) {
    case "error":   return "pill-err";
    case "warning": return "pill-warn";
    case "info":    return "pill-muted";
  }
}

function shortTimestamp(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString();
}

interface EventFeedProps {
  /** Optional filter — only show events for this mod (or unscoped events). */
  modFilter?: string;
  /** Notify the parent on new error events (used to fire native toasts). */
  onError?: (ev: WatchLogEvent) => void;
}

export function EventFeed({ modFilter, onError }: EventFeedProps) {
  const { items, connected, error, clear } = useWatchEvents({ onError });

  const [enabledSeverities, setEnabledSeverities] = useState<Set<Severity>>(
    new Set(SEVERITIES)
  );
  const [enabledLanes, setEnabledLanes] = useState<Set<string>>(new Set(LANES));
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  // Filter
  const filtered = useMemo(() => {
    return items.filter((ev) => {
      if (modFilter && ev.mod && ev.mod !== modFilter) return false;
      const sev = severityOf(ev);
      if (!enabledSeverities.has(sev)) return false;
      if (ev.lane && !enabledLanes.has(String(ev.lane))) return false;
      return true;
    });
  }, [items, enabledSeverities, enabledLanes, modFilter]);

  // Auto-scroll to bottom on new events
  useEffect(() => {
    if (!autoScroll || !scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [filtered.length, autoScroll]);

  function toggleSeverity(s: Severity) {
    setEnabledSeverities((prev) => {
      const next = new Set(prev);
      next.has(s) ? next.delete(s) : next.add(s);
      return next;
    });
  }
  function toggleLane(l: string) {
    setEnabledLanes((prev) => {
      const next = new Set(prev);
      next.has(l) ? next.delete(l) : next.add(l);
      return next;
    });
  }

  return (
    <div className="panel flex flex-col min-h-0">
      <div className="px-3 py-2 border-b border-bg-elevated flex items-center gap-3 text-sm">
        <Activity className={"w-4 h-4 " + (connected ? "text-ok" : "text-muted")} />
        <span className="font-medium">Live events</span>

        <span className="text-xs text-muted ml-2">
          {filtered.length} / {items.length}
        </span>

        <div className="ml-auto flex items-center gap-2 text-xs">
          <Filter className="w-3 h-3 text-muted" />
          {SEVERITIES.map((s) => (
            <button
              key={s}
              onClick={() => toggleSeverity(s)}
              className={
                enabledSeverities.has(s)
                  ? severityPill(s)
                  : "pill-muted opacity-40"
              }
              title={`toggle ${s}`}
            >
              {s}
            </button>
          ))}
          <span className="text-muted mx-1">·</span>
          {LANES.map((l) => (
            <button
              key={l}
              onClick={() => toggleLane(l)}
              className={
                enabledLanes.has(l) ? "pill-muted text-gray-200" : "pill-muted opacity-40"
              }
              title={`toggle ${l}`}
            >
              {l}
            </button>
          ))}
          <button
            onClick={clear}
            className="ml-2 text-muted hover:text-white"
            title="clear feed"
          >
            <Trash2 className="w-3 h-3" />
          </button>
        </div>
      </div>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto font-mono text-xs"
        onScroll={(e) => {
          const el = e.currentTarget;
          const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 20;
          setAutoScroll(atBottom);
        }}
      >
        {error && (
          <div className="px-3 py-2 text-err text-xs">{error}</div>
        )}
        {filtered.length === 0 && (
          <div className="px-3 py-6 text-muted text-center">
            No events yet. Run <code className="text-accent-bright">/dayz-watch --with-logs</code> in
            a terminal, or trigger a build, to see events stream here.
          </div>
        )}
        {filtered.map((ev, i) => {
          const sev = severityOf(ev);
          const ts = shortTimestamp(ev.ts);
          return (
            <div
              key={i}
              className="px-3 py-1 border-t border-bg-elevated/40 grid grid-cols-[auto_auto_auto_1fr] gap-2 items-baseline"
            >
              <span className="text-muted">{ts}</span>
              <span className={severityPill(sev)}>{sev}</span>
              <span className="pill-muted">
                {ev.lane ?? ev.event}
              </span>
              <span className={severityClass(sev)}>
                {ev.pattern || ev.event}
                {ev.excerpt && (
                  <span className="text-gray-300 ml-2">{ev.excerpt}</span>
                )}
                {ev.hint && (
                  <span className="text-muted block pl-2 mt-0.5">→ {ev.hint}</span>
                )}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
