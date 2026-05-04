# Agentic-Z Desktop — Architecture

How the app fits together. For contributors.

---

## TL;DR

Tauri 2 shell (Rust, ~150 LOC) spawns a Python FastAPI sidecar (long-lived process), which imports the existing Agentic-Z CLI skill modules and exposes them over HTTP + Server-Sent Events on `localhost`. A React + TypeScript SPA in the WebView talks to the sidecar like any normal web app. No business logic in Rust. No Python embedded in Rust. Each layer can be tested independently.

```
┌─────────────────────────────────────────────────────────────┐
│                    Agentic-Z.exe (Tauri)                     │
│   ┌────────────────────────────────────────────────────┐    │
│   │   WebView (React + TypeScript + Tailwind)          │    │
│   │   - Dashboard, ModDetail, DirectorPage,            │    │
│   │     SearchPalette, SettingsPage, ProposalsPage,    │    │
│   │     ModCreatorDialog, OnboardingWizard, ...        │    │
│   └────────────────────────┬───────────────────────────┘    │
│                            │ HTTP + SSE                      │
│                            ▼                                 │
│   ┌────────────────────────────────────────────────────┐    │
│   │   Tauri Rust shell (src-tauri/src/main.rs)         │    │
│   │   - Spawns sidecar at startup                      │    │
│   │   - Exposes get_sidecar_status / get_repo_root     │    │
│   │   - Kills sidecar on window close                  │    │
│   └────────────────────────┬───────────────────────────┘    │
│                            │ subprocess                      │
│                            ▼                                 │
│   ┌────────────────────────────────────────────────────┐    │
│   │   FastAPI sidecar (sidecar/)                       │    │
│   │   - main.py: endpoint registry + lifecycle         │    │
│   │   - proposals.py / director.py / rag.py /          │    │
│   │     anthropic_api.py                               │    │
│   │   - Imports existing Agentic-Z skill modules       │    │
│   └────────────────────────┬───────────────────────────┘    │
└────────────────────────────┼─────────────────────────────────┘
                             │ subprocess + filesystem
                             ▼
              ┌──────────────────────────────────┐
              │  Agentic-Z CLI skills            │
              │  + dayz-watch process            │
              │  + dayz-coder agent (via API)    │
              │  + dayz-director (via Claude     │
              │    Code; status via JSON file)   │
              └──────────────────────────────────┘
```

---

## Why these choices

### Tauri over Electron

| | Tauri 2 | Electron |
|---|---|---|
| Bundle size | ~5-10 MB | ~150 MB |
| Memory | ~50-80 MB | ~300+ MB |
| WebView | OS-native (Edge/Safari/WebKit) | Bundled Chromium |
| Security | Allowlist by default | Permissive by default |
| Native APIs | Rust + JS bridge | Node.js |

Tauri wins on memory + bundle + security defaults. The trade-off is Rust at build time (invisible to end users; hits us as a one-time setup cost for contributors).

### FastAPI sidecar over native Rust

- Existing CLI skills are already Python modules with clean entry points. Importing them into a long-lived FastAPI process is a one-line change per skill.
- Streaming logs via SSE is a 5-line FastAPI endpoint; in Rust it's an async runtime + an event channel + a TCP server.
- The sidecar runs **standalone** for testing — `python sidecar/main.py` opens Swagger UI at `localhost:7321/docs`. Cuts iteration time massively.

### React + TypeScript + Tailwind + Zustand + TanStack Query

Boring choices on purpose. Maximum ecosystem support, easy hiring for community contributors, fast iteration.

- **Zustand** over Redux: 1 KB, no provider hell, 5 stores total — Redux is overkill.
- **TanStack Query** over plain fetch: SSE-aware, built-in retry, caching, invalidation.
- **Tailwind** over hand-rolled CSS: avoids the "designer sells you on a custom design system" problem.
- **Vite** over webpack: Tauri's default, fast HMR, simple config.

### SSE over WebSockets

Live-event streams (watch log, director status, mod creator, run output) are all server-push only. SSE is:

- One-directional (server → client) — matches our use case
- HTTP/1.1 friendly (no upgrade dance)
- Native browser API (`EventSource`) with auto-reconnect
- Trivially proxyable through Tauri's CSP

WebSockets buy us bidirectional but we don't need it. Keep simple things simple.

### Status-file IPC for the director

The `dayz-director` agent runs inside the user's CLI session (Claude Code / Codex / Gemini), not inside the desktop app. The app needs to know what state the director is in.

Options considered:

- **Status file** (chosen): director writes `.claude/local-memory/dayz-director-status.json` on every state transition. Sidecar polls; SSE pushes deltas to the frontend.
- **WebSocket from agent to app**: requires the agent to be aware of the app, which couples them — bad.
- **Anthropic API direct from app**: requires us to re-implement the director state machine in TypeScript. Massive duplication, divergence guaranteed.

The status-file approach decouples the two. The director can run with or without the desktop app open. The desktop app shows whatever the most recent run was, regardless of how it was triggered.

### Anthropic API direct (BYOK) for Mod Creator

The Mod Creator needs Claude. Three options:

- **Anthropic API direct** (chosen): user provides their API key in Settings (stored in `.env` at the repo root, gitignored). Sidecar makes API calls. Costs go on the user's account.
- **IPC with the user's CLI session**: brittle, no stable IPC for any of these CLIs, would break on every CLI update.
- **Clipboard handoff**: user pastes a prompt into Claude Code. Works but feels hacky for a marquee feature.

Direct API integration is best for the Mod Creator's UX. The director still uses clipboard handoff for v1 (option C) because it requires multi-turn reasoning across many state transitions; bringing that into the API path is post-v1 work.

---

## Endpoint reference

### Sidecar HTTP API

| Endpoint | Method | Purpose | Returns |
|---|---|---|---|
| `/api/health` | GET | sidecar self-check | `{status, sidecar_started_at, repo_root}` |
| `/api/repo/info` | GET | repo paths + sidecar version | `{repo_root, claude_dir, workspace_dir, ...}` |
| `/api/preflight` | GET | DayZ environment check | `{p_drive_mounted, dayz_tools_path, ..., errors[], warnings[]}` |
| `/api/mods` | GET | list workspace mods | `{mods: [{name, path, has_config_cpp, ...}]}` |
| `/api/mods/new` | POST | scaffold a new mod | `StartRunResponse` |
| `/api/mods/{name}/build` | POST | invoke /dayz-build-pbo | `StartRunResponse` |
| `/api/mods/{name}/launch` | POST | invoke /dayz-launch-test | `StartRunResponse` |
| `/api/mods/{name}/stop` | POST | invoke /dayz-stop-test | `StartRunResponse` |
| `/api/runs/active` | GET | currently-running subprocesses | `{runs: [...]}` |
| `/api/runs/{id}/stream` | GET (SSE) | stdout for a running subprocess | line events |
| `/api/runs/{id}/kill` | POST | kill a subprocess | `{ok}` |
| `/api/events/watch-log` | GET (SSE) | tail dayz-watch.log | event-per-line |
| `/api/events/director` | GET (SSE) | tail dayz-director-status.json | full status JSON |
| `/api/director/runs` | GET | list postmortems | `{runs: [...]}` |
| `/api/director/runs/{name}` | GET | fetch one postmortem | `{name, content}` |
| `/api/director/reset` | POST | clear stale director status | `{ok}` |
| `/api/rag/search` | GET | semantic search | `{hits, corpora_queried, rag_available}` |
| `/api/rag/file` | GET | file slice (path-safe) | `{path, line_start, line_end, content}` |
| `/api/rag/manifests` | GET | index counts | `{vanilla, wiki, workspace, total_chunks}` |
| `/api/rag/open` | POST | open file in editor | `{ok, method}` |
| `/api/proposals` | GET | list skill proposals | `{proposals: [...]}` |
| `/api/proposals/{slug}` | GET | get a proposal | `{slug, skill_md, py_files}` |
| `/api/proposals/{slug}/edit` | POST | edit SKILL.md / scripts | `{ok}` |
| `/api/proposals/promote` | POST | promote → .claude/skills/ | `{ok, target_dir, files_copied, sync_skills_*}` |
| `/api/proposals/refresh` | POST | re-run /agentic-z-promote-skill | `{ok, exit, log}` |
| `/api/settings` | GET / POST | API keys + author handle | `SettingsResponse` |
| `/api/anthropic/test-key` | POST | validate Anthropic key | `{ok, model, latency_ms, error}` |
| `/api/mod-creator` | POST (SSE) | pitch → mod scaffold | `started`, `thought`, `file_written`, `error`, `done` events |

Browse the live OpenAPI docs at `http://localhost:7321/docs` while the sidecar is running.

---

## Path safety

Anything that takes a user-supplied path validates it resolves under an allowed root.

- `_safe_path_in_mod(mod_root, rel_path)` — for Mod Creator's `write_file` tool. Resolves rel_path under mod_root or returns None.
- `_resolve_safe_path(path)` (rag.py) — for `/api/rag/file`. Allows P:\ (vanilla) or repo_root (workspace).
- `_safe_proposal_dir(slug)` (proposals.py) — for proposal endpoints. Allows only direct children of `output/skill-proposals/`.
- `get_dayz_file_impl(path, ...)` (dayz-rag MCP server) — sandboxed to P:\.

Pattern: **resolve → check `relative_to(allowed_root)` → reject on ValueError.** Never trust string-prefix checks (vulnerable to symlink/junction tricks).

---

## Forward references gotcha (Pydantic v2)

Modules that define Pydantic models inside `make_router()` closures **must omit** `from __future__ import annotations`. With that import on, all annotations become ForwardRefs that Pydantic v2's TypeAdapter rebuild can't resolve when the class is local to a function.

Affected files: `proposals.py`, `anthropic_api.py`. Symptom: `pydantic.errors.PydanticUserError: ... is not fully defined` at request time.

Module-level Pydantic models work either way.

---

## Build pipeline

GitHub Actions workflow at `.github/workflows/desktop-release.yml`. Triggered by:

- Push of a tag matching `desktop-v*.*.*`.
- Manual dispatch via the Actions tab UI.

Steps per OS (currently just `windows-latest`):

1. Checkout
2. Setup Node 20, pnpm 9, Python 3.11, Rust stable
3. Cache Cargo registry + pnpm store
4. `pnpm install --frozen-lockfile` (frontend)
5. `pip install -r sidecar/requirements.txt`
6. Sanity-import the sidecar (`python -c "import main"`)
7. `pnpm tauri build` (produces `.exe` + `.msi`)
8. Upload artifact

Tag-triggered runs also create a GitHub Release (draft) with the artifacts attached. Body templated to `desktop-vX.Y.Z`.

macOS / Linux build matrix entries are commented out — DayZ is Windows-only so v1 is Windows-first. Easy to enable for community use of the search/proposal UI on other OSes.
