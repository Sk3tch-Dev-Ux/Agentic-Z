# Contributing to Agentic-Z Desktop

PRs welcome. Small ones especially. The codebase is intentionally boring tech (React + TypeScript + Tailwind + FastAPI + Tauri 2) so newcomers can land changes fast.

---

## What to contribute

### Easiest wins

- **Fix typos / clarify docs.** Always welcome.
- **New error pattern in `log_tail.py`.** Hit a recurring DayZ error the watcher doesn't classify yet? Add a regex + lane + hint. ~5-line change. Real impact.
- **New skill scaffolding.** Have a workflow you keep doing manually? Write a SKILL.md + `.py` for it, ship it as a PR.

### Medium

- **New corpus filter / file type for RAG search.** E.g. `corpus="materials"` over `.rvmat` files.
- **New theme.** The dark theme is set up via Tailwind tokens; light theme support requires a token swap.
- **macOS / Linux build pipeline.** Tauri targets all three; the GitHub Actions matrix is commented out for non-Windows. Re-enable + test.

### Larger (talk to us first on Discord)

- **Workshop publishing UI.** Wrapping `PublisherCmd.exe` with a proper publish flow.
- **Visual mod-merger.** Diff/merge UI for combining two workspace mods.
- **Embedded code editor.** Replace the "Open in VS Code" button with an inline Monaco editor.

---

## Setup

```cmd
git clone https://github.com/dayznchill/Agentic-Z
cd Agentic-Z\desktop
pnpm install
pip install -r sidecar\requirements.txt
pnpm tauri:dev
```

You need: Node 20+, pnpm, Rust stable, Python 3.10+, MSVC build tools (Windows). [`docs/BUILDING.md`](BUILDING.md) has the per-OS detail.

For frontend-only iteration without Tauri:

```cmd
:: Terminal 1: sidecar standalone
cd desktop\sidecar
python main.py

:: Terminal 2: Vite alone
cd desktop
pnpm dev
```

Open <http://localhost:5173> in a browser. Saves Rust compile time during UI churn.

---

## Project layout

```
desktop/
├── package.json
├── README.md          ← public-facing
├── docs/              ← user + contributor docs (you are here)
├── src/               ← React + TypeScript frontend
│   ├── api/           ← sidecar HTTP client + SSE consumers
│   ├── components/    ← reusable UI
│   ├── hooks/         ← useHotkey, etc.
│   ├── pages/         ← route pages (Dashboard, ModDetail, DirectorPage, ...)
│   ├── stores/        ← Zustand
│   └── App.tsx        ← routes + global modals
├── src-tauri/         ← Rust shell (only does process spawn + cleanup)
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   └── src/main.rs
└── sidecar/           ← Python FastAPI backend
    ├── main.py        ← endpoint registry + lifecycle
    ├── proposals.py   ← skill proposal manager
    ├── director.py    ← director status SSE + postmortems
    ├── rag.py         ← search + file slice + open-in-editor
    ├── anthropic_api.py  ← settings + Mod Creator
    └── requirements.txt
```

---

## Code style

### Frontend (TypeScript / React)

- Components are functional + hooks. No classes.
- State management: **Zustand** for cross-component state, **TanStack Query** for server state, plain `useState` for local UI.
- Styling: **Tailwind utility classes**. Custom design tokens live in `tailwind.config.js`. Avoid global CSS.
- Files: kebab-case for non-component files (`use-hotkey.ts` if you prefer; the existing convention is camelCase like `useHotkey.ts` — match the surrounding files).
- TypeScript strict mode is on. No `any` without justification.
- Imports: relative paths (`../api/client`) — no path aliases for v1.

### Backend (Python / FastAPI)

- One file per logical surface (proposals, rag, director, anthropic). Keep `main.py` thin — it just mounts routers.
- Pydantic v2. Schemas defined inside `make_router()` factories work, BUT **omit `from __future__ import annotations`** in modules that define schemas inside closures — Pydantic's ForwardRef resolution breaks otherwise. (See the comments in `proposals.py` and `anthropic_api.py`.)
- Type hints everywhere. `Optional[X]` not `X | None` for compatibility with older Pydantic.
- Async endpoints when they do I/O; sync when they don't.
- Path safety: never accept a user-supplied path without validating it resolves under an allowed root. See `_safe_path_in_mod()` and `_safe_proposal_dir()` for the patterns.

### Rust (Tauri shell)

- The shell stays small. No business logic. Spawn the sidecar, expose the port to the frontend, clean up on close. That's it.
- New native APIs: prefer adding a Tauri plugin from the official set over rolling our own. Notification → `tauri-plugin-notification`. Filesystem → `tauri-plugin-fs`. Etc.

---

## Testing

The codebase doesn't have a formal test suite for v1. The smoke-test pattern that worked across phases:

1. For a new sidecar endpoint, write a short Python script using `fastapi.testclient.TestClient` that hits the endpoint and asserts the response shape.
2. For a new frontend component, render it manually in dev mode and exercise the user paths.
3. For full-stack changes, dev mode end-to-end test (Tauri + sidecar + UI) is the truth.

A proper Vitest + Playwright + pytest setup is on the post-1.0 roadmap. PRs for that scaffolding are very welcome.

---

## Submitting a PR

1. Branch off `main`. Name your branch descriptively: `feature/cui-theme-builder`, `fix/sidecar-port-collision`, etc.
2. Keep PRs small. One logical change per PR.
3. Include a brief description: what changed, why, what you tested.
4. Tag a maintainer on Discord ([discord.gg/dayznchill](https://discord.gg/dayznchill)) once the PR is up. We watch GH but Discord pings us faster.
5. Be patient — DayZ modding is volunteer work; reviews can take a few days.

---

## Code of conduct

Be kind. The DayZ modding community is small. Your PR review interaction will be visible to people you'll see again. Apply that pressure to your tone.

If you hit something rude or unwelcoming, message a maintainer privately on Discord.

---

## License

By contributing, you agree your contributions are licensed under the same terms as the project — see [`../../LICENSE`](../../LICENSE) (Copyright © 2026 Brian Orr / DayZ n' Chill, free for DayZ modding use).
