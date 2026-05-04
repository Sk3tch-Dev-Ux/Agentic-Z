"""DayZ log tail + pattern classification.

Phase 3 of Agentic-Z Live Mode. Imported by watch.py when --with-logs is set.

Tails the diag server's RPT + script.log + BattlEye logs AND the diag client's
RPTs / script logs. On each polling tick, reads any new bytes since last tick,
runs known-bad-pattern regexes against each new line, and emits structured
events to the same dayz-watch.log the watcher already writes to.

Each emitted event carries:
  - severity:  "error" | "warning"
  - lane:      "script" | "config" | "asset" | "server" | "ui" | "debug"
  - pattern:   short label identifying which detector fired
  - log_path:  full path of the log file that produced the line
  - log_tail:  which tail group ("server" | "client" | "battleye")
  - excerpt:   first 200 chars of the line
  - match:     the matched substring (first 200 chars)
  - captures:  up to 3 regex capture groups (e.g. extracted class name)

Dedup: any (pattern, first-60-chars) pair fires at most once per
DEDUP_WINDOW_SECONDS. Stops a cascading error from spamming 1000 events.

Log-file rotation: every tick, each tailer re-globs its pattern set, so files
created mid-session (a freshly-rotated `*.RPT`) are picked up automatically.
A new file's initial position is end-of-file (we only want events that happen
AFTER --with-logs starts). A truncated file resets to its current size.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# Suppress duplicate events for this many seconds.
DEDUP_WINDOW_SECONDS = 30
# Read events older than this are dropped when an agent reads the log.
DEFAULT_AGENT_READ_WINDOW_SECONDS = 30 * 60  # 30 minutes


# ---------- patterns -------------------------------------------------------

# Each entry: (compiled regex, severity, lane, pattern_label, hint).
# Order matters — first match wins per line. Place specific before generic.
PATTERNS: list[tuple[re.Pattern, str, str, str, str]] = [
    # --- Class declaration / config ---
    (
        re.compile(r"Class\s+'([^']+)'\s+is\s+not\s+declared\s+in\s+script", re.I),
        "error", "config", "missing_class_declaration",
        "Add the class to CfgPatches units[]/weapons[] or check scriptModules wiring.",
    ),
    (
        re.compile(r"Cannot\s+find\s+(?:base\s+class|template)\s+'([^']+)'", re.I),
        "error", "config", "missing_base_class",
        "Inheritance points at a class that isn't loaded — check mod load order or vanilla data extraction.",
    ),
    (
        re.compile(r"Cannot\s+register\s+enum\s+'([^']+)'", re.I),
        "error", "config", "enum_collision",
        "Two mods declared the same enum entry — prefix yours.",
    ),

    # --- Script compile / runtime ---
    (
        re.compile(r"unexpected\s+(?:eof|EOF)|unexpected\s+end\s+of\s+file", re.I),
        "error", "script", "unexpected_eof",
        "Missing closing brace or semicolon — check the bottom of the most-recently-edited .c file.",
    ),
    (
        re.compile(r"compile\s+error", re.I),
        "error", "script", "compile_error",
        "Generic compile error — open the cited file and look at the line above the message.",
    ),
    (
        re.compile(r"'([^']+)'\s+(?:cannot evaluate type|is not a valid type)", re.I),
        "error", "script", "null_pointer_eval",
        "Null reference dereferenced — add a null check before the call.",
    ),
    (
        re.compile(r"Variable\s+'([^']+)'\s+(?:does not exist|not defined|undefined)", re.I),
        "error", "script", "undefined_variable",
        "Symbol not visible at this scope — typo, missing import/include, or modded-class with inheritance clause.",
    ),
    (
        re.compile(r"Function\s+'([^']+)'\s+is\s+not\s+declared", re.I),
        "error", "script", "undefined_function",
        "Method not on this class — check signature or add `override` if extending vanilla.",
    ),

    # --- Mission / server lifecycle ---
    (
        re.compile(r"Mission\s+script\s+has\s+no\s+main\s+function", re.I),
        "error", "server", "mission_init_missing",
        "Mission folder doesn't have a valid init.c with main() — re-run /dayz-add-map.",
    ),
    (
        re.compile(r"Cannot\s+open\s+mission", re.I),
        "error", "server", "mission_path_unresolved",
        "Server can't find the mission folder; pass -mission=<absolute path>.",
    ),

    # --- Networking / filePatching ---
    (
        re.compile(r"0x00020005|filePatching\s+setting", re.I),
        "error", "server", "filepatching_mismatch",
        "Server's serverDZ.cfg is missing `allowFilePatching = 1;` — re-run /dayz-launch-test.",
    ),
    (
        re.compile(r"NetworkServer:\s+Cannot\s+create", re.I),
        "error", "script", "network_create_failure",
        "RPC handler may be misregistered or class not networked — check OnRPC / RegisterNetSyncVariable wiring.",
    ),

    # --- BattlEye ---
    (
        re.compile(r"BattlEye\s+Server:\s+Player\s+#?\d+\s+\S+\s+\(.*?\)\s+kicked", re.I),
        "warning", "server", "battleye_kick",
        "Player kicked — check workspace/_server/!ClientDiagLogs/BattlEye/*.log for the rule that fired.",
    ),
    (
        re.compile(r"Script\s+Restriction\s+#(\d+)", re.I),
        "warning", "server", "battleye_filter_violation",
        "Server-side BattlEye filter rejected an action — add a whitelist line in workspace/_server/maps/<map>/profiles/BattlEye/scripts.txt.",
    ),

    # --- Engine / asset ---
    (
        re.compile(r"Cannot\s+open\s+file\s+'([^']+)'", re.I),
        "error", "asset", "missing_file",
        "Path doesn't resolve — check $PBOPREFIX$ and that the file is included in the PBO.",
    ),
    (
        re.compile(r"No\s+entry\s+'([^']+)'", re.I),
        "warning", "config", "missing_config_entry",
        "config.cpp is referencing a property that doesn't exist on the parent class.",
    ),
    (
        re.compile(r"Cannot\s+load\s+texture\s+([\w/\\\.:]+)", re.I),
        "error", "asset", "missing_texture",
        "Texture path resolved but couldn't load — wrong format (must be .paa) or corrupt.",
    ),

    # --- Engine crash signals (RPT) ---
    (
        re.compile(r"Application\s+crashed", re.I),
        "error", "debug", "engine_crash",
        "Engine crashed — capture the full crash log + last 200 lines of script.log for the debug lane.",
    ),
    (
        re.compile(r"Access\s+violation", re.I),
        "error", "debug", "access_violation",
        "Native crash — usually a script holding a stale reference. Check for delete-then-use or autoptr misuse.",
    ),

    # --- UI ---
    (
        re.compile(r"Cannot\s+find\s+widget\s+'([^']+)'", re.I),
        "error", "ui", "missing_widget",
        "Layout references a widget name that doesn't exist; check the .layout for a typo.",
    ),
]


# ---------- tailer ---------------------------------------------------------


@dataclass
class LogTailer:
    """Glob-based log tailer with rotation handling and per-file position."""
    glob_patterns: list[str]
    label: str  # e.g. "server", "client", "battleye"
    file_positions: dict[str, int] = field(default_factory=dict)

    def discover_files(self, repo_root: Path) -> list[Path]:
        seen: set[Path] = set()
        for gp in self.glob_patterns:
            for p in repo_root.glob(gp):
                try:
                    if p.is_file():
                        seen.add(p)
                except OSError:
                    continue
        return sorted(seen)

    def tick(self, repo_root: Path) -> list[dict]:
        """Read new bytes from each file. Return one record per non-empty line."""
        out: list[dict] = []
        for path in self.discover_files(repo_root):
            try:
                size = path.stat().st_size
            except OSError:
                continue
            key = str(path)
            pos = self.file_positions.get(key)
            if pos is None:
                # First time we see this file — start at end (only NEW lines).
                self.file_positions[key] = size
                continue
            if size < pos:
                # Truncation or rotation; reset.
                self.file_positions[key] = size
                continue
            if size == pos:
                continue
            try:
                with path.open("rb") as f:
                    f.seek(pos)
                    data = f.read(size - pos)
            except OSError:
                continue
            self.file_positions[key] = size
            try:
                text = data.decode("utf-8", errors="replace")
            except Exception:
                continue
            for line in text.splitlines():
                if line.strip():
                    out.append({"path": str(path), "line": line, "tail": self.label})
        return out


# ---------- classification + dedup -----------------------------------------


def classify_line(record: dict, dedup: dict[tuple, float]) -> dict | None:
    """Match a log line against PATTERNS. Return event dict or None.

    `dedup` is a caller-owned dict mapping (pattern_label, line_prefix) -> last_emit_ts;
    we mutate it in place so repeat lines within DEDUP_WINDOW_SECONDS are suppressed.
    """
    line = record["line"]
    now = time.time()
    for regex, severity, lane, label, hint in PATTERNS:
        m = regex.search(line)
        if not m:
            continue
        key = (label, line[:60])
        last = dedup.get(key, 0.0)
        if now - last < DEDUP_WINDOW_SECONDS:
            return None
        dedup[key] = now
        # Capture groups, truncated for safety
        captures = [g[:200] if isinstance(g, str) else str(g) for g in m.groups()][:3]
        return {
            "severity": severity,
            "lane": lane,
            "pattern": label,
            "hint": hint,
            "log_path": record["path"],
            "log_tail": record["tail"],
            "excerpt": line[:200],
            "match": (m.group(0) or "")[:200],
            "captures": captures,
        }
    return None


def gc_dedup(dedup: dict[tuple, float]) -> None:
    """Drop dedup entries older than the window so the dict doesn't grow unbounded."""
    cutoff = time.time() - DEDUP_WINDOW_SECONDS * 4
    stale = [k for k, ts in dedup.items() if ts < cutoff]
    for k in stale:
        del dedup[k]


# ---------- defaults --------------------------------------------------------


def configure_default_tailers() -> list[LogTailer]:
    """Standard set of tailers for the Agentic-Z diag-server-with-mod test layout."""
    return [
        LogTailer(
            glob_patterns=[
                "workspace/_server/maps/*/profiles/*.RPT",
                "workspace/_server/maps/*/profiles/*.log",
                "workspace/_server/maps/*/profiles/script_*.log",
            ],
            label="server",
        ),
        LogTailer(
            glob_patterns=[
                "workspace/_server/!ClientDiagLogs/*.RPT",
                "workspace/_server/!ClientDiagLogs/*.log",
                "workspace/_server/!ClientDiagLogs/script_*.log",
            ],
            label="client",
        ),
        LogTailer(
            glob_patterns=[
                "workspace/_server/maps/*/profiles/BattlEye/*.log",
            ],
            label="battleye",
        ),
    ]


# ---------- agent helper ----------------------------------------------------


def read_recent_events(
    log_path: Path,
    window_seconds: int = DEFAULT_AGENT_READ_WINDOW_SECONDS,
    severities: Iterable[str] | None = None,
) -> list[dict]:
    """Read dayz-watch.log and return events from the last `window_seconds`.

    Filtered to relevant agent-facing events by default: log_error, log_warning,
    build_failed, backoff_triggered. Pass severities=("error",) to scope tighter.
    """
    if not log_path.exists():
        return []
    cutoff = time.time() - window_seconds
    relevant_events = {
        "log_error", "log_warning",
        "build_failed", "backoff_triggered",
        "workspace_reindex_failed", "texture_pack_failed",
    }
    if severities is not None:
        sev_set = set(severities)
        relevant_events = {e for e in relevant_events if any(s in e for s in sev_set)}

    out: list[dict] = []
    try:
        with log_path.open("r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    import json as _json
                    rec = _json.loads(raw)
                except Exception:
                    continue
                if rec.get("ts", 0) < cutoff:
                    continue
                if rec.get("event") in relevant_events:
                    out.append(rec)
    except OSError:
        return []
    return out
