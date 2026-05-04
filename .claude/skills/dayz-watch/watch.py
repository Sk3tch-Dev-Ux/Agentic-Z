"""DayZ live-iteration watcher.

Watch `workspace/<ModName>/` for changes. Classify each change. Dispatch the
right downstream skill automatically:

  - `.c` (Enforce Script) -> log "filePatching will pick this up; reconnect to apply"
  - `.cpp` / `.hpp` / `.h` / `.layout` / `$PBOPREFIX$` / anything in `data/`
        -> run /dayz-build-pbo <ModName>
  - `.png` / `.tga` next to a `_co` / `_nohq` / `_smdi` suffix
        -> log a hint to run /dayz-pack-texture (auto-pack opt-in via --auto-pack)
  - `types.xml` / `events.xml` / `cfgspawnabletypes.xml`
        -> log "server reload required to apply"
  - everything in `_server/`, `.git/`, `__pycache__/`, build artifacts -> ignore

Also re-runs `/dayz-rag-workspace-index <ModName>` on every change cycle so the
agents always have an up-to-date semantic index of your code (cheap thanks to
the chunk-hash skip in Phase 1). Pass --no-rag to disable.

Implementation choice: pure stdlib polling, not `watchdog`. OneDrive folders
flake on inotify-style events; polling is dumb and bulletproof. Polling
interval defaults to 0.5s, debounce window 1.0s. Both are tunable.

Run:
    python .claude/skills/dayz-watch/watch.py                   # all mods, run forever
    python .claude/skills/dayz-watch/watch.py MyMod             # one mod
    python .claude/skills/dayz-watch/watch.py --once            # one classification cycle, exit
    python .claude/skills/dayz-watch/watch.py --dry-run         # detect + log, never build
    python .claude/skills/dayz-watch/watch.py --no-rag          # skip workspace re-index on each save
    python .claude/skills/dayz-watch/watch.py --debounce 2.0    # wait 2s of quiet before dispatching
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

# Resolve repo root from this file: <repo>/.claude/skills/dayz-watch/watch.py
_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parents[2]
WORKSPACE_DIR = REPO_ROOT / "workspace"

# Reuse preflight resolvers + L2-aware constants if present
sys.path.insert(0, str(_HERE.parent / "dayz-preflight"))
try:
    from preflight import find_dayz_tools  # noqa: F401  (sanity check that import works)
except ImportError:
    pass

LOG_DIR = REPO_ROOT / ".claude" / "local-memory"
LOG_PATH = LOG_DIR / "dayz-watch.log"

# --------- ignore rules -----------------------------------------------------

IGNORE_DIR_NAMES = {
    ".git", ".hg", ".svn", "__pycache__", ".venv", "node_modules",
    ".idea", ".vscode", "_server",
}
# Files we never react to (build artifacts + editor temps).
IGNORE_SUFFIXES = {
    ".pbo", ".bisign", ".bikey",                  # build artifacts
    ".tmp", ".swp", ".swo", ".bak", ".orig",      # editor temps
    ".log",                                        # our own log + game logs
}
# Editors save atomically through temp files like `.foo.c.swpx` or `~$config.cpp`.
# Skip names matching these patterns.
IGNORE_NAME_PREFIXES = ("~$",)
IGNORE_NAME_SUFFIXES = ("~",)
# Specific file extensions we DO classify (everything else gets ignored).
TRIGGER_SUFFIXES = {
    ".c", ".cpp", ".hpp", ".h", ".layout", ".cfg",
    ".xml", ".json", ".csv",
    ".rvmat",
    ".png", ".tga",
}
SCRIPT_ONLY_SUFFIXES = {".c"}
NEEDS_REBUILD_SUFFIXES = {".cpp", ".hpp", ".h", ".layout", ".cfg", ".rvmat"}
TEXTURE_SUFFIXES = {".png", ".tga"}
TEXTURE_NAME_TAILS = ("_co", "_nohq", "_smdi", "_as", "_sm")  # accepted DayZ suffixes
SERVER_XML_NAMES = {"types.xml", "events.xml", "cfgspawnabletypes.xml", "cfgeconomycore.xml"}
SPECIAL_FILENAMES_REBUILD = {"$PBOPREFIX$", "config.cpp"}

# --------- pretty stdout ----------------------------------------------------

OK = "[OK]   "
WARN = "[WARN] "
FAIL = "[FAIL] "
INFO = "[INFO] "
ACT = "[ACT]  "


def _ts() -> str:
    return time.strftime("%H:%M:%S")


def _log_event(event: str, **fields) -> None:
    """Append one JSON line to dayz-watch.log + print a human-readable line."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": time.time(),
        "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "event": event,
        **fields,
    }
    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except OSError as e:
        print(f"{WARN} failed to write watch log: {e}", file=sys.stderr)

    summary_parts = [f"{k}={v}" for k, v in fields.items() if k not in ("changes",)]
    if "changes" in fields:
        summary_parts.append(f"changes={len(fields['changes'])}")
    print(f"[{_ts()}] {event}  {'  '.join(summary_parts)}")


# --------- snapshot + diff --------------------------------------------------


def _is_ignored(rel_parts: tuple[str, ...], name: str, suffix: str) -> bool:
    if any(p in IGNORE_DIR_NAMES for p in rel_parts):
        return True
    if suffix in IGNORE_SUFFIXES:
        return True
    for prefix in IGNORE_NAME_PREFIXES:
        if name.startswith(prefix):
            return True
    for tail in IGNORE_NAME_SUFFIXES:
        if name.endswith(tail):
            return True
    return False


def _walk_snapshot(root: Path) -> dict[str, tuple[float, int]]:
    """Map full-path -> (mtime, size). One entry per indexable file."""
    snap: dict[str, tuple[float, int]] = {}
    if not root.exists():
        return snap
    for f in root.rglob("*"):
        try:
            if not f.is_file():
                continue
        except OSError:
            continue
        rel = f.relative_to(root)
        suffix = f.suffix.lower()
        if _is_ignored(rel.parts, f.name, suffix):
            continue
        # Only track files we actually care about (or might fire ignore-style
        # special filenames like $PBOPREFIX$ which has no extension).
        if suffix not in TRIGGER_SUFFIXES and f.name not in SPECIAL_FILENAMES_REBUILD:
            continue
        try:
            stat = f.stat()
        except OSError:
            continue
        snap[str(f)] = (stat.st_mtime, stat.st_size)
    return snap


def _diff_snapshots(
    old: dict[str, tuple[float, int]], new: dict[str, tuple[float, int]]
) -> list[dict]:
    """Return list of {path, kind} for files that changed since last snapshot."""
    changes: list[dict] = []
    for path, (mtime, size) in new.items():
        prev = old.get(path)
        if prev is None:
            changes.append({"path": path, "kind": "added"})
        elif prev[0] != mtime or prev[1] != size:
            changes.append({"path": path, "kind": "modified"})
    for path in old:
        if path not in new:
            changes.append({"path": path, "kind": "deleted"})
    return changes


# --------- classification ---------------------------------------------------


@dataclass
class Classification:
    needs_rebuild: bool = False
    script_only_changes: list[str] = field(default_factory=list)
    rebuild_triggers: list[str] = field(default_factory=list)
    texture_sources: list[str] = field(default_factory=list)
    server_xml_changes: list[str] = field(default_factory=list)
    other: list[str] = field(default_factory=list)


def _classify(changes: Iterable[dict], mod_root: Path) -> Classification:
    cls = Classification()
    for c in changes:
        path = Path(c["path"])
        try:
            rel = path.relative_to(mod_root)
        except ValueError:
            cls.other.append(str(path))
            continue
        suffix = path.suffix.lower()
        name = path.name

        if name in SPECIAL_FILENAMES_REBUILD:
            cls.needs_rebuild = True
            cls.rebuild_triggers.append(str(rel))
            continue
        if name in SERVER_XML_NAMES:
            cls.server_xml_changes.append(str(rel))
            continue
        if suffix in SCRIPT_ONLY_SUFFIXES:
            cls.script_only_changes.append(str(rel))
            continue
        if suffix in NEEDS_REBUILD_SUFFIXES:
            cls.needs_rebuild = True
            cls.rebuild_triggers.append(str(rel))
            continue
        if suffix in TEXTURE_SUFFIXES:
            stem = path.stem.lower()
            if any(stem.endswith(t) for t in TEXTURE_NAME_TAILS):
                cls.texture_sources.append(str(rel))
            else:
                cls.other.append(str(rel))
            continue
        # data/ folder catch-all (assets without a known suffix)
        if "data" in rel.parts:
            cls.needs_rebuild = True
            cls.rebuild_triggers.append(str(rel))
            continue
        cls.other.append(str(rel))
    return cls


# --------- subprocess dispatch ----------------------------------------------


@dataclass
class ModState:
    consecutive_failures: int = 0
    last_build_at: float = 0.0
    backoff_until: float = 0.0


BACKOFF_THRESHOLD = 3
BACKOFF_SECONDS = 60.0


def _run_skill(args: list[str], label: str) -> tuple[int, float]:
    """Run a skill subprocess. Stream stdout/stderr live so the user sees build
    progress. Return (exit_code, elapsed_seconds)."""
    started = time.time()
    print(f"  {ACT} {label}: {' '.join(args)}")
    try:
        result = subprocess.run(args, check=False)
    except FileNotFoundError as e:
        print(f"  {FAIL} {label}: {e}")
        return 127, time.time() - started
    return result.returncode, time.time() - started


def _build_pbo(mod_name: str, mod_state: ModState, dry_run: bool) -> int:
    if dry_run:
        print(f"  {INFO} (dry-run) skipped /dayz-build-pbo {mod_name}")
        return 0
    if time.time() < mod_state.backoff_until:
        remaining = int(mod_state.backoff_until - time.time())
        _log_event(
            "build_skipped_backoff",
            mod=mod_name,
            consecutive_failures=mod_state.consecutive_failures,
            remaining_seconds=remaining,
        )
        return -1
    skill = REPO_ROOT / ".claude" / "skills" / "dayz-build-pbo" / "build.py"
    if not skill.exists():
        print(f"  {FAIL} dayz-build-pbo skill not found at {skill}")
        return 127
    rc, elapsed = _run_skill([sys.executable, str(skill), mod_name], "/dayz-build-pbo")
    mod_state.last_build_at = time.time()
    if rc == 0:
        mod_state.consecutive_failures = 0
        _log_event("build_ok", mod=mod_name, elapsed_seconds=round(elapsed, 1))
    else:
        mod_state.consecutive_failures += 1
        _log_event(
            "build_failed",
            mod=mod_name,
            exit_code=rc,
            elapsed_seconds=round(elapsed, 1),
            consecutive_failures=mod_state.consecutive_failures,
        )
        if mod_state.consecutive_failures >= BACKOFF_THRESHOLD:
            mod_state.backoff_until = time.time() + BACKOFF_SECONDS
            _log_event(
                "backoff_triggered",
                mod=mod_name,
                cooldown_seconds=BACKOFF_SECONDS,
                hint="fix the build error then save any source file to retry",
            )
    return rc


def _reindex_workspace(mod_name: str, dry_run: bool) -> int:
    if dry_run:
        print(f"  {INFO} (dry-run) skipped /dayz-rag-workspace-index {mod_name}")
        return 0
    skill = REPO_ROOT / ".claude" / "skills" / "dayz-rag-workspace-index" / "index.py"
    if not skill.exists():
        # Phase 1 not deployed yet — silently skip.
        return 0
    rc, elapsed = _run_skill(
        [sys.executable, str(skill), mod_name],
        "/dayz-rag-workspace-index",
    )
    _log_event(
        "workspace_reindex" if rc == 0 else "workspace_reindex_failed",
        mod=mod_name,
        exit_code=rc,
        elapsed_seconds=round(elapsed, 1),
    )
    return rc


def _pack_texture(source_rel: str, mod_root: Path, dry_run: bool) -> int:
    """Auto-pack a PNG/TGA into a sibling .paa via /dayz-pack-texture."""
    src = mod_root / source_rel
    out = src.with_suffix(".paa")
    if dry_run:
        print(f"  {INFO} (dry-run) would pack {source_rel} -> {out.name}")
        return 0
    skill = REPO_ROOT / ".claude" / "skills" / "dayz-pack-texture" / "pack_texture.py"
    if not skill.exists():
        print(f"  {WARN} dayz-pack-texture skill not found; skipping {source_rel}")
        return 127
    rc, elapsed = _run_skill(
        [sys.executable, str(skill), str(src), str(out)],
        f"/dayz-pack-texture ({source_rel})",
    )
    _log_event(
        "texture_packed" if rc == 0 else "texture_pack_failed",
        source=source_rel,
        output=str(out.relative_to(mod_root)) if out.is_relative_to(mod_root) else str(out),
        exit_code=rc,
        elapsed_seconds=round(elapsed, 1),
    )
    return rc


def _run_preflight() -> int:
    skill = REPO_ROOT / ".claude" / "skills" / "dayz-preflight" / "preflight.py"
    if not skill.exists():
        print(f"{FAIL} preflight skill not found at {skill}", file=sys.stderr)
        return 1
    return subprocess.run([sys.executable, str(skill)], check=False).returncode


# --------- mod resolution ---------------------------------------------------


def _list_mods(name: Optional[str]) -> list[Path]:
    if not WORKSPACE_DIR.exists():
        return []
    if name:
        target = WORKSPACE_DIR / name
        return [target] if target.is_dir() else []
    return sorted(
        p for p in WORKSPACE_DIR.iterdir()
        if p.is_dir() and not p.name.startswith("_") and p.name not in IGNORE_DIR_NAMES
    )


# --------- main loop --------------------------------------------------------


def _handle_changes(
    mod: Path,
    changes: list[dict],
    mod_state: ModState,
    args: argparse.Namespace,
) -> None:
    cls = _classify(changes, mod)
    _log_event(
        "changes_detected",
        mod=mod.name,
        rebuild_triggers=cls.rebuild_triggers,
        script_only=cls.script_only_changes,
        textures=cls.texture_sources,
        server_xml=cls.server_xml_changes,
        other=cls.other,
        changes=changes,
    )

    # 1. Texture packing (opt-in).
    if cls.texture_sources:
        if args.auto_pack:
            for src in cls.texture_sources:
                _pack_texture(src, mod, args.dry_run)
            # A new/updated .paa written next to the source counts as a
            # rebuild trigger because the .paa is what AddonBuilder packs.
            cls.needs_rebuild = True
        else:
            print(
                f"  {INFO} {len(cls.texture_sources)} texture source(s) changed; "
                f"run /dayz-pack-texture or pass --auto-pack to auto-convert."
            )

    # 2. Build PBO if any rebuild trigger fired.
    if cls.needs_rebuild:
        _build_pbo(mod.name, mod_state, args.dry_run)
    elif cls.script_only_changes:
        print(
            f"  {INFO} script-only change ({len(cls.script_only_changes)} file(s)) — "
            f"engine will re-read via -filePatching on next reconnect; "
            f"no PBO rebuild needed."
        )
        _log_event("script_filepatching_only", mod=mod.name, files=cls.script_only_changes)

    # 3. Server-XML changes: log a hint, don't auto-reload.
    if cls.server_xml_changes:
        print(
            f"  {INFO} server XML changed ({', '.join(cls.server_xml_changes)}). "
            f"Restart the local server to apply economy/event changes."
        )
        _log_event("server_xml_changed", mod=mod.name, files=cls.server_xml_changes)

    # 4. Re-index the workspace RAG so dayz-coder sees the new code.
    if not args.no_rag:
        _reindex_workspace(mod.name, args.dry_run)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mod_name", nargs="?", default=None,
                        help="One mod under workspace/ to watch. Omit to watch all mods.")
    parser.add_argument("--once", action="store_true",
                        help="Run a single classification cycle and exit (useful in tests).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Detect changes and log them, but don't run any subprocess.")
    parser.add_argument("--no-rag", action="store_true",
                        help="Skip the /dayz-rag-workspace-index call after each cycle.")
    parser.add_argument("--auto-pack", action="store_true",
                        help="Auto-run /dayz-pack-texture on PNG/TGA with valid suffix tails.")
    parser.add_argument("--debounce", type=float, default=1.0,
                        help="Quiet seconds before dispatching (default 1.0).")
    parser.add_argument("--interval", type=float, default=0.5,
                        help="Polling interval in seconds (default 0.5).")
    parser.add_argument("--no-preflight", action="store_true",
                        help="Skip /dayz-preflight at startup. Don't use this in normal work.")
    args = parser.parse_args()

    print("DayZ live watcher\n")

    if not args.no_preflight:
        rc = _run_preflight()
        if rc != 0:
            print(f"\n{FAIL} preflight failed with exit {rc}; halting per L2 conventions.",
                  file=sys.stderr)
            return rc
        print()

    mods = _list_mods(args.mod_name)
    if not mods:
        if args.mod_name:
            print(f"{FAIL} No mod folder at workspace/{args.mod_name}/", file=sys.stderr)
        else:
            print(f"{FAIL} No mods under workspace/. Scaffold one with /dayz-new-mod.",
                  file=sys.stderr)
        return 1
    print(f"{OK} Watching: {', '.join(m.name for m in mods)}")
    print(f"{INFO} Debounce: {args.debounce:.1f}s  Polling: {args.interval:.1f}s  "
          f"Auto-pack: {args.auto_pack}  RAG re-index: {not args.no_rag}")
    print(f"{INFO} Log: {LOG_PATH}")
    print(f"{INFO} Ctrl+C to stop.\n")

    states = {m.name: ModState() for m in mods}
    snapshots = {m.name: _walk_snapshot(m) for m in mods}
    pending: dict[str, dict] = {}

    _log_event(
        "watch_started",
        mods=[m.name for m in mods],
        debounce_seconds=args.debounce,
        polling_interval_seconds=args.interval,
        auto_pack=args.auto_pack,
        no_rag=args.no_rag,
        dry_run=args.dry_run,
    )

    try:
        while True:
            now = time.time()

            # 1. Walk + detect per mod
            for mod in mods:
                new_snap = _walk_snapshot(mod)
                changes = _diff_snapshots(snapshots[mod.name], new_snap)
                snapshots[mod.name] = new_snap
                if changes:
                    p = pending.setdefault(mod.name, {"first_seen": now, "changes": []})
                    p["changes"].extend(changes)
                    p["last_seen"] = now

            # 2. Dispatch any pending bucket whose quiet window has elapsed
            for mod_name in list(pending.keys()):
                info = pending[mod_name]
                last_seen = info.get("last_seen", info["first_seen"])
                if now - last_seen >= args.debounce:
                    mod = next(m for m in mods if m.name == mod_name)
                    _handle_changes(mod, info["changes"], states[mod_name], args)
                    del pending[mod_name]

            if args.once:
                # Flush any not-yet-debounced pending immediately and exit.
                for mod_name, info in pending.items():
                    mod = next(m for m in mods if m.name == mod_name)
                    _handle_changes(mod, info["changes"], states[mod_name], args)
                _log_event("watch_stopped", reason="once")
                return 0

            time.sleep(args.interval)
    except KeyboardInterrupt:
        print(f"\n{INFO} stopping watcher...")
        _log_event("watch_stopped", reason="keyboard_interrupt")
        return 0


if __name__ == "__main__":
    sys.exit(main())
