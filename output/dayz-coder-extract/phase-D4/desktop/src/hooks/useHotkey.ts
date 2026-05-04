// Global keyboard shortcut hook. Cmd+K on macOS, Ctrl+K elsewhere.

import { useEffect } from "react";

export interface Hotkey {
  key: string;          // e.g. "k", "p", "/", "Escape"
  ctrl?: boolean;       // Ctrl on Win/Linux
  meta?: boolean;       // Cmd on macOS
  shift?: boolean;
  alt?: boolean;
}

function matches(ev: KeyboardEvent, hk: Hotkey): boolean {
  if (ev.key.toLowerCase() !== hk.key.toLowerCase()) return false;
  // For Ctrl/Cmd: treat them as either-or so Cmd+K works on both platforms.
  const wantsModifier = !!(hk.ctrl || hk.meta);
  const hasModifier = ev.ctrlKey || ev.metaKey;
  if (wantsModifier && !hasModifier) return false;
  if (!wantsModifier && hasModifier) return false;
  if (!!hk.shift !== ev.shiftKey) return false;
  if (!!hk.alt !== ev.altKey) return false;
  return true;
}

export function useHotkey(hk: Hotkey, handler: () => void, enabled = true) {
  useEffect(() => {
    if (!enabled) return;
    function onKey(ev: KeyboardEvent) {
      // Don't intercept if the user is typing in an input/textarea.
      const target = ev.target as HTMLElement | null;
      const tag = target?.tagName?.toLowerCase();
      // Allow Esc through in inputs (for closing palettes).
      if (hk.key.toLowerCase() !== "escape") {
        if (tag === "input" || tag === "textarea" || target?.isContentEditable) {
          return;
        }
      }
      if (matches(ev, hk)) {
        ev.preventDefault();
        handler();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [hk.key, hk.ctrl, hk.meta, hk.shift, hk.alt, enabled, handler]);
}
