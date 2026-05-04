// SSE consumer hooks for D2.
// Native EventSource handles auto-reconnect, framing, etc. — we just adapt to React.

import { useEffect, useRef, useState } from "react";
import { sidecarBaseUrl, WatchLogEvent, RunStreamLine } from "./client";

export interface UseEventStreamOptions<T> {
  url: string;
  parse: (data: string) => T | null;
  onMessage?: (item: T) => void;
  enabled?: boolean;
  maxItems?: number;          // ring-buffer cap
}

/** Generic SSE consumer hook. Maintains a bounded list of received items. */
export function useEventStream<T>({
  url,
  parse,
  onMessage,
  enabled = true,
  maxItems = 500,
}: UseEventStreamOptions<T>) {
  const [items, setItems] = useState<T[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;

    (async () => {
      const base = await sidecarBaseUrl();
      if (cancelled) return;
      const es = new EventSource(`${base}${url}`);
      sourceRef.current = es;

      es.onopen = () => {
        setConnected(true);
        setError(null);
      };
      es.onerror = () => {
        setConnected(false);
        // EventSource auto-reconnects; we surface a soft error message.
        setError("Connection interrupted; retrying…");
      };
      es.onmessage = (ev) => {
        const item = parse(ev.data);
        if (item === null) return;
        setItems((prev) => {
          const next = [...prev, item];
          return next.length > maxItems ? next.slice(next.length - maxItems) : next;
        });
        onMessage?.(item);
      };
    })();

    return () => {
      cancelled = true;
      sourceRef.current?.close();
      sourceRef.current = null;
    };
  }, [url, enabled]);

  return { items, connected, error, clear: () => setItems([]) };
}

// -------- specialized hooks --------

export function useWatchEvents(opts: { onError?: (e: WatchLogEvent) => void } = {}) {
  return useEventStream<WatchLogEvent>({
    url: "/api/events/watch-log",
    maxItems: 500,
    parse: (data) => {
      try {
        const obj = JSON.parse(data);
        if (typeof obj !== "object" || obj === null) return null;
        return obj as WatchLogEvent;
      } catch {
        return null;
      }
    },
    onMessage: (ev) => {
      if (ev.event === "log_error") {
        opts.onError?.(ev);
      }
    },
  });
}

export function useRunStream(runId: string | null) {
  return useEventStream<RunStreamLine>({
    url: runId ? `/api/runs/${runId}/stream` : "",
    enabled: !!runId,
    maxItems: 2000,
    parse: (data) => {
      try {
        return JSON.parse(data) as RunStreamLine;
      } catch {
        return null;
      }
    },
  });
}
