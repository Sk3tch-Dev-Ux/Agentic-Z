---
name: dayz-watch
description: Watch `workspace/<ModName>/` for file changes and auto-dispatch the right downstream skill — `/dayz-build-pbo` on config/asset changes, a hint on `.c` script-only changes (filePatching picks them up), and `/dayz-rag-workspace-index` after each cycle so the agent's semantic recall stays current. Pass `--with-logs` to also tail diag server/client RPTs + BattlEye and emit classified error events back to dayz-coder.
---

# /dayz-watch

Live-iteration daemon for DayZ modding. Polls `workspace/<ModName>/` (or every mod under `workspace/` if no name is given), classifies each change by file type, and runs the right skill automatically. With `--with-logs`, also tails the diag server/client logs every tick and emits structured error events that `dayz-coder` reads at the start of every turn. Stop with Ctrl+C.

Phases 2 + 3 of Agentic-Z Live Mode. Builds on Phase 1 (workspace RAG). Phase 4 (the autonomous director agent) consumes the events this skill emits.

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

## What it does with `--with-logs` (Phase 3)

Each polling tick also walks these globs (re-resolved every tick so freshly-rotated `*.RPT` files get picked up automatically):

| Tail group | Globs |
|---|---|
| `server` | `workspace/_server/maps/*/profiles/*.RPT`, `workspace/_server/maps/*/profiles/*.log`, `workspace/_server/maps/*/profiles/script_*.log` |
| `client` | `workspace/_server/!ClientDiagLogs/*.RPT`, `workspace/_server/!ClientDiagLogs/*.log`, `workspace/_server/!ClientDiagLogs/script_*.log` |
| `battleye` | `workspace/_server/maps/*/profiles/BattlEye/*.log` |

Files are tailed from end-of-file at first sight (only events that happen *after* the watcher starts get processed). Each new line is matched against ~20 known DayZ error patterns. On match, a structured event is emitted with severity, suggested fix lane, and a one-line hint:

```
[ERROR  ] [config] missing_class_declaration  Class 'MyMod_Vest' is not declared in script
         hint: Add the class to CfgPatches units[]/weapons[] or check scriptModules wiring.
[ERROR  ] [script] unexpected_eof              File: scripts\4_World\Hello.c, line 42: unexpected EOF
         hint: Missing closing brace or semicolon — check the bottom of the most-recently-edited .c file.
[WARNING] [server] battleye_filter_violation   Script Restriction #45 detected for player ABC
         hint: Server-side BattlEye filter rejected an action — add a whitelist line in workspace/_server/maps/<map>/profiles/BattlEye/scripts.txt.
```

Detected categories include: missing class declarations, missing base classes, enum collisions, compile errors, unexpected EOF, null-pointer evaluations, undefined variables/functions, mission-init failures, file-patching mismatches, network create failures, BattlEye kicks/filter violations, missing files/textures/widgets, engine crashes, access violations.

Dedup: any (pattern, first-60-chars-of-line) pair fires at most once per 30 seconds — cascading errors don't spam the log.

## How `dayz-coder` consumes the events

When the unified `dayz-coder` agent (`.claude/agents/dayz-coder.md`) starts a turn, it reads the last 30 minutes of `.claude/local-memory/dayz-watch.log` and surfaces any `log_error` / `log_warning` / `build_failed` / `backoff_triggered` events under a "RECENT EVENTS" preamble before answering whatever you asked.

Effect: you save buggy code → server reloads → script.log spits the error → 2 seconds later the watcher has classified it → the next time you say *anything* to `dayz-coder`, it leads with "I see your server logged a missing_class_declaration two minutes ago — that's a config lane fix; here's what to change."

## How to run

```cmd
:: Bare watcher (Phase 2 features only) — file-watch + smart rebuild
python .claude\skills\dayz-watch\watch.py MyMod

:: With log tailing (Phase 3) — recommended whenever you have a server running
python .claude\skills\dayz-watch\watch.py MyMod --with-logs

:: Auto-convert PNG/TGA + tail logs + watch all mods
python .claude\skills\dayz-watch\watch.py --with-logs --auto-pack

:: One classification cycle, exit (smoke testing)
python .claude\skills\dayz-watch\watch.py MyMod --once

:: Detect + log everything but don't run builds (preview mode)
python .claude\skills\dayz-watch\watch.py MyMod --dry-run --with-logs

:: Skip the workspace re-index after each cycle (faster, less semantic recall)
python .claude\skills\dayz-watch\watch.py MyMod --no-rag

:: Tune timing
python .claude\skills\dayz-watch\watch.py MyMod --debounce 2.0 --interval 0.5
```

## Polling, not watchdog

Pure stdlib polling instead of the `watchdog` library. Reasons:

- OneDrive folders flake on inotify-style events. Polling is bulletproof.
- No extra dependency to install.
- 0.5-second interval + 1-second debounce is plenty fast for the edit-save-rebuild loop.

Drop `--interval 0.1 --debounce 0.5` if you want lower latency on a non-OneDrive folder. Don't go below 0.1 — polling cost gets noticeable.

## Backoff behavior

If `/dayz-build-pbo` fails 3 times in a row for a given mod, the watcher enters a 60-second cooldown for that mod and stops trying to rebuild it (still keeps watching for changes; just doesn't dispatch). The cooldown clears on the next successful build, or you can wait it out and save any source file to retry.

This stops a typo'd `config.cpp` from spinning the build infinitely. The watcher logs `backoff_triggered` so the agent can see what happened.

## Output

Two layers:

**Stdout (live):** Human-readable per-event log so you can watch the loop in a terminal.

```
DayZ live watcher

[OK]    Watching: MyMod
[INFO]  Debounce: 1.0s  Polling: 0.5s  Auto-pack: False  RAG re-index: True  With logs: True
[INFO]  Log: <repo>/.claude/local-memory/dayz-watch.log
[INFO]  Ctrl+C to stop.

[OK]    Log tailers active: ['server', 'client', 'battleye']

[14:32:08] watch_started  mods=['MyMod']  with_logs=True  ...
[14:34:12] changes_detected  mod=MyMod  rebuild_triggers=['config.cpp']  changes=1
  [ACT]  /dayz-build-pbo: python .claude\skills\dayz-build-pbo\build.py MyMod
  ... AddonBuilder output streamed live ...
[14:34:21] build_ok  mod=MyMod  elapsed_seconds=8.3
[14:34:38] log_error  severity=error  lane=config  pattern=missing_class_declaration  log_path=...\server.RPT
  [ERROR  ] [config] missing_class_declaration  Class 'MyMod_TacticalVest' is not declared in script
           hint: Add the class to CfgPatches units[]/weapons[] or check scriptModules wiring.
```

**`.claude/local-memory/dayz-watch.log` (structured JSON):** One JSON object per line, append-only. The `dayz-coder` agent reads this on every turn.

```json
{"ts":1735843952.31,"ts_iso":"2026-05-04T14:32:08","event":"watch_started","mods":["MyMod"]}
{"ts":1735844078.55,"ts_iso":"2026-05-04T14:34:38","event":"log_error","severity":"error","lane":"config","pattern":"missing_class_declaration","hint":"Add the class to CfgPatches units[]/weapons[] or check scriptModules wiring.","log_path":"...\\server.RPT","log_tail":"server","excerpt":"...","captures":["MyMod_TacticalVest"]}
```

## Preflight gate

Per L2 conventions, the watcher runs `/dayz-preflight` once at startup and halts on non-zero exit. If `P:\` isn't mounted, you get the standard preflight error and the watcher refuses to start.

Pass `--no-preflight` to skip the gate (useful only in tests on a Linux dev box).

## Do not

- Don't run two watchers on the same mod simultaneously — they'll race and both try to build.
- Don't watch `workspace/_server/` source files — that's mission/server staging, not your mod source. The walker excludes it. (`--with-logs` does read from there, but as logs only.)
- Don't let the JSON log grow forever in production — for now, manual housekeeping: `del .claude\local-memory\dayz-watch.log` between sessions if it gets bulky. A future enhancement will add automatic rolling-window truncation.
- Don't trust the watcher's "build succeeded" as "the mod loads in-game". A clean PBO build doesn't catch runtime script errors. That's exactly why `--with-logs` exists — turn it on whenever you have a server running.

## What changes the watcher cannot reload

- **Mod load order in the launcher / server cfg.** If you add a new mod to your test set, you have to relaunch `/dayz-launch-test` with the new `-mod=` arg.
- **`serverDZ.cfg`.** Server config changes need a server restart, which the watcher will not do automatically (server-restart logic lands in a future phase, behind a feature flag).
- **PBO contents that aren't in `workspace/<ModName>/`.** The watcher only sees the mod source you're editing.
