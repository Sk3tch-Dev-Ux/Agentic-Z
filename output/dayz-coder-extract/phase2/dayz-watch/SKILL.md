---
name: dayz-watch
description: Watch `workspace/<ModName>/` for file changes and auto-dispatch the right downstream skill — `/dayz-build-pbo` on config/asset changes, a hint on `.c` script-only changes (filePatching picks them up), and `/dayz-rag-workspace-index` after each cycle so the agent's semantic recall stays current. Closes the inner edit-build loop.
---

# /dayz-watch

Live-iteration daemon for DayZ modding. Polls `workspace/<ModName>/` (or every mod under `workspace/` if no name is given), classifies each change by file type, and runs the right skill automatically. Stop with Ctrl+C.

Phase 2 of Agentic-Z Live Mode. Builds on Phase 1 (workspace RAG). Phase 3 will add log tail + auto error routing on top of this.

Follow `.claude/skills/_shared/dayz-conventions.md`.

## What it does on each change

| Change type | What it dispatches |
|---|---|
| `*.c` (Enforce Script) | Logs that `-filePatching` will pick it up on next reconnect. **No rebuild.** |
| `*.cpp` / `*.hpp` / `*.h` / `*.layout` / `*.cfg` / `*.rvmat` | Runs `/dayz-build-pbo <ModName>` |
| `$PBOPREFIX$` or `config.cpp` | Runs `/dayz-build-pbo <ModName>` |
| Anything in `data/` (textures, models, materials) | Runs `/dayz-build-pbo <ModName>` |
| `*.png` / `*.tga` with `_co` / `_nohq` / `_smdi` / `_as` / `_sm` suffix | Logs a hint to run `/dayz-pack-texture`. With `--auto-pack`, runs it automatically and then triggers a rebuild. |
| `types.xml` / `events.xml` / `cfgspawnabletypes.xml` / `cfgeconomycore.xml` | Logs that the local server needs a restart to apply. **No PBO rebuild.** |
| Anything else (binary artifacts, editor temps, `.git/`, `_server/`, `__pycache__/`) | Ignored. |

After every cycle that touched anything, runs `/dayz-rag-workspace-index <ModName>` so the agent's semantic recall stays in sync with your code. Cheap thanks to Phase 1's chunk-hash skip — typical re-index after a small edit costs cents and finishes in 1-2 seconds.

## How to run

```cmd
:: Watch all mods in workspace/, run forever
python .claude\skills\dayz-watch\watch.py

:: Watch one specific mod
python .claude\skills\dayz-watch\watch.py MyMod

:: Run a single classification cycle and exit (useful in tests)
python .claude\skills\dayz-watch\watch.py MyMod --once

:: Detect + log changes but don't run any builds (preview mode)
python .claude\skills\dayz-watch\watch.py MyMod --dry-run

:: Skip the workspace re-index after each cycle (faster, less semantic recall)
python .claude\skills\dayz-watch\watch.py MyMod --no-rag

:: Auto-convert PNG/TGA with valid DayZ suffixes into .paa
python .claude\skills\dayz-watch\watch.py MyMod --auto-pack

:: Tune timing
python .claude\skills\dayz-watch\watch.py MyMod --debounce 2.0 --interval 0.5
```

## Polling, not watchdog

Implementation choice: pure stdlib polling instead of the `watchdog` library. Reasons:

- OneDrive folders flake on inotify-style events. Polling is slow but bulletproof.
- No extra dependency to install.
- 0.5-second interval + 1-second debounce is plenty fast for the edit-save-rebuild loop.

If you want lower latency on a non-OneDrive folder, drop `--interval 0.1 --debounce 0.5`. Don't go below 0.1 — the polling cost gets noticeable.

## Backoff behavior

If `/dayz-build-pbo` fails 3 times in a row for a given mod, the watcher enters a 60-second cooldown for that mod and stops trying to rebuild it (still keeps watching for changes; just doesn't dispatch). The cooldown clears on the next successful build, or you can wait it out and save any source file to retry.

This stops a typo'd `config.cpp` from spinning the build infinitely. The watcher logs `backoff_triggered` so you can see what happened.

## Output

Two layers:

**Stdout (live):** Human-readable per-event log so you can watch the loop in a terminal.

```
DayZ live watcher

[OK]    Watching: MyMod
[INFO]  Debounce: 1.0s  Polling: 0.5s  Auto-pack: False  RAG re-index: True
[INFO]  Log: <repo>/.claude/local-memory/dayz-watch.log
[INFO]  Ctrl+C to stop.

[14:32:08] watch_started  mods=['MyMod']  ...
[14:34:12] changes_detected  mod=MyMod  rebuild_triggers=['config.cpp']  changes=1
  [ACT]  /dayz-build-pbo: python .claude\skills\dayz-build-pbo\build.py MyMod
  ... AddonBuilder output streamed live ...
[14:34:21] build_ok  mod=MyMod  elapsed_seconds=8.3
  [ACT]  /dayz-rag-workspace-index: python .claude\skills\dayz-rag-workspace-index\index.py MyMod
[14:34:23] workspace_reindex  mod=MyMod  exit_code=0  elapsed_seconds=1.2
```

**`.claude/local-memory/dayz-watch.log` (structured JSON):** One JSON object per line, append-only. Phase 3 of Live Mode will read this log to surface errors back to `dayz-coder` automatically. Until then it's a forensics tool — `tail -f` it to see the agent-visible event stream.

```json
{"ts":1735843952.31,"ts_iso":"2026-05-04T14:32:08","event":"watch_started","mods":["MyMod"]}
{"ts":1735844052.18,"ts_iso":"2026-05-04T14:34:12","event":"changes_detected","mod":"MyMod","rebuild_triggers":["config.cpp"]}
{"ts":1735844061.45,"ts_iso":"2026-05-04T14:34:21","event":"build_ok","mod":"MyMod","elapsed_seconds":8.3}
```

## Preflight gate

Per L2 conventions, the watcher runs `/dayz-preflight` once at startup and halts on non-zero exit. If `P:\` isn't mounted, you get the standard preflight error and the watcher refuses to start.

Pass `--no-preflight` to skip the gate (useful only in tests on a Linux dev box).

## Do not

- Don't run two watchers on the same mod simultaneously — they'll race and both try to build.
- Don't watch `workspace/_server/` — that's mission/server staging, not your mod source. The walker excludes it.
- Don't let the JSON log grow forever in production — when Phase 3 lands, it'll truncate to a rolling window. For now, manual housekeeping: `del .claude\local-memory\dayz-watch.log` between sessions if it gets bulky.
- Don't trust the watcher's "build succeeded" as "the mod loads in-game". A clean PBO build doesn't catch runtime script errors. That's what the post-launch tail in Phase 3 is for.

## What changes the watcher cannot reload

- **Mod load order in the launcher / server cfg.** If you add a new mod to your test set, you have to relaunch `/dayz-launch-test` with the new `-mod=` arg.
- **`serverDZ.cfg`.** Server config changes need a server restart, which the watcher will not do automatically (server-restart logic lands in a future phase, behind a feature flag).
- **PBO contents that aren't in `workspace/<ModName>/`.** The watcher only sees the mod source you're editing.
