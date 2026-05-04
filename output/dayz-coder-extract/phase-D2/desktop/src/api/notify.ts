// Native Tauri notifications. Asks for permission on first use, caches grant.
// Falls back to a no-op in browser dev mode (where Tauri APIs aren't available).

import { useCallback, useEffect, useRef } from "react";
import { WatchLogEvent } from "./client";

let permissionGranted: boolean | null = null;
let permissionRequested = false;

async function ensurePermission(): Promise<boolean> {
  if (permissionGranted !== null) return permissionGranted;
  if (permissionRequested) return false;
  permissionRequested = true;
  try {
    const mod = await import("@tauri-apps/plugin-notification");
    let granted = await mod.isPermissionGranted();
    if (!granted) {
      const result = await mod.requestPermission();
      granted = result === "granted";
    }
    permissionGranted = granted;
    return granted;
  } catch {
    permissionGranted = false;
    return false;
  }
}

export async function notify(title: string, body: string): Promise<void> {
  const ok = await ensurePermission();
  if (!ok) return;
  try {
    const mod = await import("@tauri-apps/plugin-notification");
    await mod.sendNotification({ title, body });
  } catch {
    // Tauri plugin missing — non-fatal.
  }
}

/** React hook: returns a callback that fires a Windows toast for an error event. */
export function useNotifyOnError() {
  const lastShown = useRef<Map<string, number>>(new Map());

  // Pre-warm permission on mount (silently).
  useEffect(() => {
    ensurePermission();
  }, []);

  return useCallback((ev: WatchLogEvent) => {
    if (ev.event !== "log_error") return;
    // Replay events shouldn't fire toasts.
    if ((ev as any)._replay) return;
    // Dedup: same (pattern, lane) within 60s shouldn't double-toast.
    const key = `${ev.lane ?? ""}::${ev.pattern ?? ev.event}`;
    const now = Date.now();
    const last = lastShown.current.get(key) ?? 0;
    if (now - last < 60_000) return;
    lastShown.current.set(key, now);

    const title = `Agentic-Z — ${ev.lane ?? "error"}`;
    const body =
      (ev.pattern ? ev.pattern + ": " : "") +
      (ev.excerpt || ev.hint || "see live event feed");
    notify(title, body);
  }, []);
}
