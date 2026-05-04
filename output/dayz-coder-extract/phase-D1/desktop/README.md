# Agentic-Z Desktop

Desktop interface for the Agentic-Z DayZ modding toolkit. Tauri 2 shell wrapping a React + TypeScript frontend that talks to a long-lived Python (FastAPI) sidecar.

This is **D1 — scaffold + dashboard**. It proves the architecture end-to-end: Tauri spawns the sidecar at startup, the sidecar imports the existing CLI skills and exposes them over HTTP, the React frontend reads preflight + mod-list state and renders a dashboard. D2-D6 layer features on top without changing the foundation.

## Prerequisites

| What | Why | Install |
|---|---|---|
| **Python 3.10+** | sidecar runtime + every CLI skill | python.org |
| **Node.js 18+** + **pnpm** | frontend build | nodejs.org → `npm i -g pnpm` |
| **Rust toolchain** (`rustup`) | Tauri shell | rustup.rs |
| **Tauri prerequisites** (Microsoft Edge WebView2 on Windows) | OS WebView | usually preinstalled on Windows 10+ |

The Tauri docs at <https://v2.tauri.app/start/prerequisites/> have the OS-by-OS breakdown.

## First-time setup

From the repo root:

```cmd
cd desktop
pnpm install                         :: frontend deps
pip install -r sidecar\requirements.txt
```

That's it. No global installs, no codegen, no native compilation up front (Tauri compiles its Rust shell on first `pnpm tauri:dev`).

## Dev workflow

```cmd
:: From the desktop\ folder:
pnpm tauri:dev
```

What this does:

1. Starts Vite on `http://localhost:5173` (frontend hot-reload).
2. Builds the Tauri Rust shell (~30-60 s on first run, sub-second on subsequent).
3. Tauri spawns `python sidecar\main.py` as a child process.
4. The sidecar discovers a free port (7321 by default), writes it to `<repo>/.claude/local-memory/agentic-z-desktop.port`.
5. The Tauri window opens; the frontend reads the port via the Tauri `get_sidecar_status` command and starts hitting `http://127.0.0.1:<port>/api/*`.

Edit any file under `src/` → instant hot-reload in the window. Edit `sidecar/main.py` → Tauri restart needed (or run the sidecar standalone with `pnpm sidecar:dev` and reload the window).

## Sidecar standalone (no Tauri)

The sidecar runs fine without the Tauri shell — useful for testing endpoints from the browser at <http://localhost:7321/docs> (FastAPI Swagger UI).

```cmd
cd desktop\sidecar
python main.py --reload
```

Or with hot-reload via the package script:

```cmd
cd desktop
pnpm sidecar:dev
```

## Production build

```cmd
cd desktop
pnpm tauri:build
```

Output: `desktop\src-tauri\target\release\bundle\nsis\Agentic-Z_0.1.0_x64-setup.exe` (and msi). Distribute that single .exe.

The first production build takes 5-10 minutes (Rust release compile). Subsequent builds are faster thanks to incremental compilation.

## Architecture in one paragraph

The desktop app is a thin Tauri shell over a Python sidecar. The sidecar is a long-lived FastAPI process that imports the existing Agentic-Z skill modules (preflight, mod walking, RAG search, etc.) and exposes them as HTTP endpoints. The React frontend talks to localhost over HTTP for synchronous calls and SSE for live event streams (D2). The Tauri Rust shell does only three things: spawn the sidecar at startup, expose the chosen port to the frontend via `get_sidecar_status`, and clean up the sidecar process when the window closes. No Python is embedded in Rust; no Rust does business logic. This separation lets you run the sidecar standalone for testing and keeps the frontend a regular SPA.

## File map

```
desktop/
├── package.json              # pnpm workspace root
├── pnpm-workspace.yaml       # (optional)
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
├── index.html
├── README.md  ← you are here
├── src/                      # React + TypeScript
│   ├── main.tsx              # entrypoint + providers
│   ├── App.tsx               # routes
│   ├── index.css             # tailwind base
│   ├── api/client.ts         # sidecar HTTP client
│   ├── stores/useStatus.ts   # zustand
│   ├── components/
│   │   ├── StatusBar.tsx     # top bar (preflight, P:\, sidecar)
│   │   └── ModSidebar.tsx    # left rail (mod list)
│   └── pages/
│       ├── Dashboard.tsx     # default page
│       └── ModDetail.tsx     # per-mod page (D2 will activate buttons)
├── src-tauri/                # Tauri Rust shell
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   ├── build.rs
│   └── src/main.rs           # spawns sidecar, exposes commands
└── sidecar/                  # FastAPI Python backend
    ├── main.py               # all D1 endpoints (will split in D2)
    └── requirements.txt
```

## Roadmap

| Phase | What | When |
|---|---|---|
| **D1** | Scaffold + dashboard (preflight, mod list, sidecar wiring) | shipped |
| **D2** | Live event stream (SSE over dayz-watch.log) + skill buttons (Build / Launch / Stop / Audit / Ship It) | next |
| **D3** | dayz-director state-machine visualizer | |
| **D4** | Inline RAG search (Cmd+K, all 3 corpora) | |
| **D5** | Skill proposal manager | |
| **D6** | Polish + GitHub release | |

See [`output/dayz-coder-extract/desktop-design.md`](../output/dayz-coder-extract/desktop-design.md) for the full design rationale and the alternatives considered.

## Troubleshooting

**Sidecar offline pill in status bar.** The Python process didn't start or crashed. Run `pnpm sidecar:dev` in a separate terminal to see the actual error.

**`pnpm tauri:dev` fails with "Rust not found".** Install via <https://rustup.rs>. Restart the terminal afterward.

**Tauri window opens but the dashboard is blank.** Vite dev server didn't start. Check that nothing else is listening on port 5173.

**Build output is huge / slow.** First Tauri build is always heavy. Subsequent builds are incremental. The release `.exe` is ~5-10 MB.

**Sidecar can't find skills.** The sidecar resolves the repo root from its own location (`<repo>/desktop/sidecar/main.py`). Make sure `desktop/` is at the repo root and the existing `.claude/skills/dayz-preflight/preflight.py` exists.
