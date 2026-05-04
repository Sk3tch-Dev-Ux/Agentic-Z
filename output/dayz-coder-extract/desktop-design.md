# Agentic-Z Desktop — Design Document

Turning the Live Mode CLI stack into a real shipped product. Tauri-based desktop app, public release on GitHub, four v1 features: live event stream + skill buttons, director visualizer, inline RAG search, skill proposal manager.

This doc locks the architecture before code is written. Every choice has a "why" and an "alternative considered" so the trade-offs are visible.

---

## 1. End-to-end picture

```
┌──────────────────────────────────────────────────────────────┐
│                    Agentic-Z.exe (Tauri)                      │
│                                                                │
│   ┌────────────────────────────────────────────────────┐      │
│   │   WebView (React + TypeScript + Tailwind)          │      │
│   │                                                    │      │
│   │   - Dashboard / mod list / status bar              │      │
│   │   - Live event stream (SSE)                        │      │
│   │   - Director visualizer (state-machine diagram)    │      │
│   │   - RAG search (workspace / vanilla / wiki)        │      │
│   │   - Skill proposal manager                         │      │
│   └────────────────────────┬───────────────────────────┘      │
│                            │ HTTP/SSE on localhost:7321        │
│                            ▼                                   │
│   ┌────────────────────────────────────────────────────┐      │
│   │   Tauri Rust shell                                 │      │
│   │   - Spawns FastAPI sidecar at startup              │      │
│   │   - System tray + native notifications             │      │
│   │   - Allowlist: localhost HTTP + repo-scoped FS     │      │
│   │   - Reads tauri.conf.json for security             │      │
│   └────────────────────────┬───────────────────────────┘      │
│                            │ subprocess (stdin/stdout)         │
│                            ▼                                   │
│   ┌────────────────────────────────────────────────────┐      │
│   │   FastAPI sidecar (Python 3.11)                    │      │
│   │   - Imports + dispatches existing Agentic-Z skills │      │
│   │   - SSE endpoint streams dayz-watch.log            │      │
│   │   - Polled endpoint reads dayz-director status     │      │
│   │   - Exposes search_dayz_* via HTTP                 │      │
│   │   - Reads .claude/agent-memory/, /skills/, etc.    │      │
│   └────────────────────────┬───────────────────────────┘      │
└────────────────────────────┼──────────────────────────────────┘
                             │ subprocess
                             ▼
              ┌──────────────────────────┐
              │  Existing skill scripts  │
              │  + dayz-watch process    │
              │  + dayz-coder agent      │
              │  + dayz-director agent   │
              └──────────────────────────┘
```

The desktop app is a thin shell over a Python sidecar. The sidecar speaks HTTP. The frontend is a regular SPA that talks to localhost. Every existing CLI skill stays unmodified — the app just orchestrates them.

---

## 2. Why Tauri (vs Electron, native, web-only)

| | Tauri | Electron | Native (Win32/Qt) | Web-only (localhost) |
|---|---|---|---|---|
| Bundle size | ~3-10 MB | ~150 MB | ~1 MB | n/a |
| Memory | ~50 MB | ~300 MB | ~30 MB | n/a |
| Cross-platform | ✓ | ✓ | painful | ✓ |
| WebView | OS-native | Bundled Chromium | n/a | Browser of choice |
| Native APIs | Rust + JS bridge | Node.js | Direct | None |
| Distribution | .exe / .dmg / .deb | .exe / .dmg / .deb | .exe per-OS | None |
| Security model | Allowlist-based | Permissive by default | OS-level | None |

Tauri wins on memory, bundle size, and security. Electron's only real advantage is mature tooling — for a v1 with a small surface, that's not enough to justify 30× the memory cost. Native is too painful for cross-platform. Web-only forces the user to manage a backend manually, which defeats the "make it a real tool" goal.

**One caveat:** Tauri requires Rust toolchain at build time. That's a setup cost for contributors but invisible to end users (they just download the .exe). Documented in the build runbook.

---

## 3. Why FastAPI sidecar (vs Rust commands, vs in-process Python)

The Tauri shell needs to invoke the existing Python skills somehow. Three options:

**(A) Tauri commands in Rust that shell out per call.**
Pro: native, no extra process. Con: every call to a skill spawns a subprocess (slow), no shared state, no streaming logs without per-call event setup.

**(B) FastAPI sidecar process spawned by Tauri at startup.**
Pro: skills run in a long-lived Python process (caches imports, holds state, streams cleanly). Con: extra process, port to manage.

**(C) In-process Python via `pyo3` embedded in Rust.**
Pro: single process. Con: pyo3 setup is non-trivial, GIL issues, harder to debug, breaks "Python script can run standalone for testing."

**Decision: B (FastAPI sidecar).**

- The existing skills are already designed as standalone Python entry points. Importing them into a long-lived FastAPI process is a one-line change per skill.
- The sidecar can run independently for testing without Tauri (`python sidecar/main.py` → open `localhost:7321/docs` for Swagger UI).
- HTTP/SSE is the right transport for the live event stream anyway.
- Port collision is solved with a discovery dance: try `7321`, then `7322`, then `7323`, write the chosen port to a session file the frontend reads.

---

## 4. Why React + TypeScript + Tailwind + Zustand

| Layer | Choice | Why |
|---|---|---|
| Framework | React | Largest ecosystem, easy hiring for community contributors. Vue would also be fine; SolidJS would be more performant but smaller community. |
| Language | TypeScript | Static types over a 5+ kLOC frontend prevent dumb bugs. |
| Build | Vite | Tauri's default. Fast HMR, simple config. |
| Styling | Tailwind | Pragmatic. Avoids the "designer sells you on a custom design system" problem. |
| State | Zustand | Lightweight (~1 kB), no Redux ceremony, no provider hell. The frontend has maybe 5 stores total. |
| Data fetching | TanStack Query | SSE-aware, caches, retries — exactly what we need over HTTP. |
| Routing | React Router | Standard. Single-page app with 4-5 routes. |
| Charts/diagrams | React Flow (for director state machine) + Recharts (for any metrics) | React Flow is purpose-built for state machine viz. Recharts for everything else. |
| Icons | Lucide | Open-source, comprehensive, tree-shakeable. |

These are boring choices on purpose. Boring stack means more time on Agentic-Z-specific UX, less on framework wars.

---

## 5. IPC model

Three flows of data between the components:

### 5a. Frontend ↔ sidecar: HTTP

- `GET /api/preflight` — runs `/dayz-preflight`, returns `{p_drive: bool, dayz_tools_path: str|None, ...}`.
- `GET /api/mods` — lists `workspace/<ModName>/` folders.
- `POST /api/mods/<ModName>/build` — invokes `/dayz-build-pbo`. Streams stdout via SSE (sub-endpoint `/api/mods/<ModName>/build/stream`).
- `POST /api/mods/<ModName>/launch` / `/stop` — same pattern.
- `POST /api/mods/<ModName>/audit` — invokes dayz-coder via Anthropic API or local agent — see §7.
- `GET /api/rag/search?q=...&corpus=workspace|vanilla|wiki&top_k=5` — direct call into `dayz-rag` MCP search functions.
- `GET /api/proposals` — lists `output/skill-proposals/`.
- `POST /api/proposals/<slug>/promote` — copies to `.claude/skills/`, runs sync.

### 5b. Frontend ↔ sidecar: SSE (Server-Sent Events)

- `GET /api/events/watch-log` — opens an SSE stream that tails `.claude/local-memory/dayz-watch.log` and emits each new JSON event as an SSE message. Client filters by lane / severity in-browser.
- `GET /api/events/director` — streams `.claude/local-memory/dayz-director-status.json` changes for the active director run.

SSE chosen over WebSockets because:
- One-way (server → client) is all we need.
- HTTP/1.1 friendly. No upgrade dance.
- Native browser API (`EventSource`).
- Auto-reconnect built in.

### 5c. Director ↔ desktop app: status file

The director agent runs inside the user's CLI session (Claude Code, Codex, Gemini), not inside the desktop app. The app needs to know what state the director is in.

**Mechanism:** Director writes `.claude/local-memory/dayz-director-status.json` on every state transition:

```json
{
  "run_id": "2026-05-04T15-32-08",
  "goal": "ship MyMod",
  "current_state": "BUILD",
  "transitions": [
    {"from": "AUDIT", "to": "PLAN", "ts": 1735844000, "notes": "12 findings"},
    ...
  ],
  "subagent_calls": [...],
  "max_state_turns": 20,
  "turn_counter": 8
}
```

The sidecar polls this file every 1 second; SSE pushes deltas to the frontend. Simple and cheap.

This means the director agent definition needs a small addition: a `## STATUS FILE` section that defines the schema and where to write. That's a Phase 4 (desktop) follow-up update to Phase 4 (Live Mode)'s director.

---

## 6. Security model

Tauri is allowlist-based, which is the right default for a public release.

**Allowlisted:**

- `http://localhost:<discovered-port>` for the sidecar API.
- File system reads scoped to the repo root (resolved at startup via `__TAURI_INVOKE__("get_repo_root")`).
- File system writes scoped to: `output/skill-proposals/`, `.claude/local-memory/`, `.claude/agent-memory/dayz-director/runs/`. The frontend never writes to `.claude/agents/`, `.claude/skills/`, `workspace/`, or anything else — those are sidecar-only.
- Shell exec ONLY for: spawning the sidecar at startup, "open in editor" (uses OS default handler).
- System tray icon + notifications.

**NOT allowlisted:**

- Outbound HTTP to anywhere except `voyageai.com` (only when the user explicitly clicks "rebuild RAG" — and the API key never leaves the repo's `.env`, the sidecar uses it directly).
- Arbitrary file system access.
- Arbitrary shell exec.

The Tauri `tauri.conf.json` enforces all of this. Frontend code that tries to exceed the allowlist gets a runtime error.

---

## 7. The dayz-coder integration question (the hard one)

The four v1 features all want to invoke `dayz-coder`. How? The agent is a Markdown file that lives in `.claude/agents/`; it's interpreted by Claude Code / Codex / Gemini, not by Python directly.

Three options:

**(A) Anthropic API direct.** The sidecar makes API calls to `claude-opus-4-7`, sending the agent definition as the system prompt + the user's request. The desktop app becomes a Claude Code-lite specifically for DayZ work.
- Pro: works without the user having a CLI session running. Ships with a clear "Bring Your Own API Key" model.
- Con: now we're a chat app on top of the toolkit. Significant scope.

**(B) IPC with the user's existing CLI session.** Detect Claude Code / Codex / Gemini running, send messages over its IPC.
- Pro: zero duplication; user keeps their existing workflow.
- Con: brittle, no stable IPC for any of these CLIs, would break on every CLI update.

**(C) "Open in your CLI" buttons.** The desktop app generates the prompt and copies it to clipboard with a "now paste this into your Claude Code session" message.
- Pro: trivial to implement, no API costs.
- Con: feels hacky for a public-release product.

**Decision: A (Anthropic API), with optional fallback to C.**

The sidecar holds the user's API key (set in app settings, stored in OS keychain via Tauri's `secure-storage` plugin — never in plaintext). When the user clicks "Audit MyMod", the sidecar reads the dayz-coder agent's body, formats it as a system prompt, sends the user request, streams the response back. For users who prefer their existing CLI workflow, settings has a "use clipboard mode" toggle that falls back to option C.

This means **"Bring Your Own Anthropic API Key"** in the public release. Documented prominently in onboarding. Costs are the user's; the app makes them visible (running token counter in the status bar).

---

## 8. Repo layout

The desktop app is its own substantial sub-product. Layout:

```
<repo-root>/
├── desktop/
│   ├── README.md
│   ├── package.json              # Tauri + frontend deps
│   ├── tauri.conf.json           # Tauri config (allowlist, build target)
│   ├── src/                      # React + TypeScript frontend
│   │   ├── App.tsx
│   │   ├── pages/
│   │   ├── components/
│   │   ├── stores/               # Zustand
│   │   ├── api/                  # Sidecar HTTP client
│   │   └── ...
│   ├── src-tauri/                # Rust shell
│   │   ├── Cargo.toml
│   │   ├── src/main.rs
│   │   └── icons/
│   ├── sidecar/                  # FastAPI Python backend
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── preflight.py
│   │   │   ├── mods.py
│   │   │   ├── rag.py
│   │   │   ├── events.py         # SSE endpoints
│   │   │   ├── proposals.py
│   │   │   └── director.py
│   │   ├── requirements.txt
│   │   └── tests/
│   └── docs/
│       ├── ARCHITECTURE.md
│       ├── BUILDING.md
│       └── CONTRIBUTING.md
├── .claude/        (existing)
├── workspace/      (existing)
├── output/         (existing)
├── docs/           (existing)
└── ...
```

`desktop/` is gitignored at the build-output level (`desktop/dist/`, `desktop/src-tauri/target/`, `desktop/node_modules/`) but the source is committed. It's a sibling sub-project, not a workspace — analogous to how some monorepos have a `frontend/` and `backend/` at the root.

---

## 9. Branding

For public release, the app needs a name + identity.

**Working name:** Agentic-Z (matches the repo). Could rebrand for the app — "DayZ Pilot", "ChernoFlow", "Agentic Workshop" — but Agentic-Z has the advantage of already existing as a community-facing brand on the Discord (DayZ n' Chill).

**Visual direction (proposed, open to user):**

- Color: deep DayZ-green (`#1f4d2e` ish) accent over a near-black UI.
- Icon: stylized "AZ" monogram or a DayZ-shaped arrow / tools-and-gears motif.
- Typography: Inter for UI, JetBrains Mono for code/log views.
- Theme: dark only for v1. Light theme post-v1 if requested.

This is the area I have least conviction on — would defer to user preference or skip until v1 ships and we can iterate from feedback.

---

## 10. Phased build plan (6 phases, ~5-6 weeks)

Each phase is independently shippable. If you stop at Phase 3, what you have still works.

### Phase D1 — Project scaffold + dashboard skeleton (~1 week)

**Deliverables:**
- Tauri project scaffolded with React + TS + Tailwind + Zustand.
- FastAPI sidecar running on `localhost:7321` with three endpoints:
  - `GET /api/preflight` (wraps existing `/dayz-preflight`)
  - `GET /api/mods` (lists `workspace/`)
  - `GET /api/health` (sidecar self-check)
- Frontend: status bar (preflight check, P:\ status, mod count), mod list (sidebar), placeholder mod detail page.
- Dev workflow: `pnpm tauri dev` runs everything. Sidecar auto-spawns from Tauri.
- Distribution: `.exe` builds via `pnpm tauri build`, manual artifact for now.

**What's usable:** A real desktop app that knows about your repo and shows preflight + mod list. Not yet feature-rich, but proves the architecture end-to-end.

### Phase D2 — Live event stream + skill buttons (~1 week)

**Deliverables:**
- SSE endpoint `/api/events/watch-log` tailing `.claude/local-memory/dayz-watch.log`.
- Frontend live feed component: virtualized list, filter by lane / severity, color-coded.
- Skill buttons: Build / Launch / Stop / Audit-trigger. Each spawns the existing skill subprocess; stdout streams to a per-mod panel.
- Notification on `log_error` events (Tauri native notification API).

**What's usable:** You can run the entire `/dayz-watch` workflow without ever opening a terminal.

### Phase D3 — Director visualizer (~1 week)

**Deliverables:**
- `/api/events/director` SSE stream from `.claude/local-memory/dayz-director-status.json`.
- React Flow state-machine diagram with current node highlighted.
- Subagent call list with prompt + digest expandable rows.
- Postmortem viewer reading `.claude/agent-memory/dayz-director/runs/*.md`.
- Director run trigger: a "Ship It" button on each mod that spawns a new director run.
- Director agent updated to write status JSON (small Phase 4 follow-up).

**What's usable:** Click "Ship It" on a mod, watch the director run live, read the postmortem when done.

### Phase D4 — Inline RAG search (~3-5 days)

**Deliverables:**
- `/api/rag/search` endpoint wrapping existing `search_dayz_source` / `search_dayz_workspace` / `search_dayz_wiki`.
- Search bar component (Cmd+K) with corpus selector and file_type filter.
- Result cards with `path:line_start-line_end`, score, snippet preview.
- "Open in editor" button (uses Tauri shell to invoke `code <file>:<line>` or OS default).

**What's usable:** Cmd+K from anywhere → semantic search across vanilla / wiki / your code → jump to source.

### Phase D5 — Skill proposal manager (~3-5 days)

**Deliverables:**
- `/api/proposals` endpoints: list, get, edit, promote.
- Proposal card UI with inline Markdown editor for SKILL.md.
- "Promote" action: copies to `.claude/skills/<slug>/`, runs `/sync-skills`, removes the proposal folder.
- Phase 5's `/agentic-z-promote-skill` re-run trigger button.

**What's usable:** Ship cycle gets a closing step — review and promote skill proposals from the UI without touching the terminal.

### Phase D6 — Polish + distribution (~1-2 weeks)

**Deliverables:**
- Icons + branding finalized.
- Onboarding flow: first-run wizard for `VOYAGE_API_KEY`, `ANTHROPIC_API_KEY`, P:\ check.
- Settings page: API keys (in OS keychain), watch interval, theme.
- GitHub Actions: build .exe / .dmg / .AppImage on tag push.
- Code signing for Windows (cert via Sectigo or similar — ~$200/year, optional for community release; users will see SmartScreen warning otherwise).
- Public docs: install guide, architecture overview, contributing guide.
- Demo video / screenshots for README.
- v1.0.0 release on GitHub.

**What's usable:** A real product anyone can download, install, and use without technical setup beyond having DayZ Tools and Python.

---

## 11. Effort summary

| Phase | Effort | Cumulative |
|---|---|---|
| D1. Scaffold + dashboard | 1 week | 1w |
| D2. Live event stream + skill buttons | 1 week | 2w |
| D3. Director visualizer | 1 week | 3w |
| D4. RAG search | 3-5 days | 3.5-4w |
| D5. Proposal manager | 3-5 days | 4-4.5w |
| D6. Polish + distribution | 1-2 weeks | 5-6.5w |

About **5-6.5 weeks of focused build** for v1.0.0. Two weeks to land the first usable version (D1+D2). Could ship a "developer preview" after D2-D3 for the Discord and gather feedback before locking the polish phase.

---

## 12. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Tauri build flakiness on different Windows versions | Medium | Pin Rust version in `rust-toolchain.toml`. Test build matrix in GitHub Actions. |
| Anthropic API rate limits / cost surprises | Medium | Token counter in status bar. Hard-stop after configurable spend cap. |
| Sidecar port collision with another app | Low | Port discovery dance (try 7321 → 7322 → ...) with chosen port written to a session file. |
| User has no API keys | High | First-run wizard makes BYOK explicit. Docs link to dashboards. |
| Frontend grows into bloat | Medium | Stick to boring stack. No new deps without justification. Lighthouse audit per release. |
| OneDrive interference (we already saw this twice) | Confirmed | Sidecar's file-watch uses polling, not inotify. Document as known issue. |
| Code signing cert cost for Windows | Low | Ship unsigned for v1; document SmartScreen workaround. Add signing in v1.1 if budget allows. |

---

## 13. What this is NOT

- **Not a Claude Code replacement.** The director and dayz-coder agents still live in `.claude/agents/`. The app calls Claude API for those interactions but doesn't try to replace the user's primary CLI session for arbitrary work.
- **Not a mod editor.** No code editing in the app. Users stay in VS Code / their editor of choice. The app's "open in editor" buttons jump there.
- **Not a Workshop publisher (yet).** Workshop publish is a separate skill (upgrade B4 from `01-upgrades.md`) that the app could later trigger via a button. Not v1 scope.
- **Not multi-user.** Single user, single repo, single session. No accounts, no cloud sync.
- **Not a server admin panel.** Live diag testing only. Real server admin (RCon, types.xml live tuning) is a separate product space.

---

## 14. Decisions to confirm before building

The doc above commits to a stack. A few choices benefit from explicit user sign-off:

1. **App name** — keep "Agentic-Z" or rebrand for the app?
2. **Visual direction** — DayZ-green dark theme as default, or something different?
3. **Icon** — propose 2-3 icon concepts at the start of D6, or have the user provide?
4. **Code signing** — ship unsigned for v1.0 (free, SmartScreen warning) or pay for a cert ($200/year)?
5. **API-key UX** — first-run wizard mandatory, or can the app run in "no AI" mode (just dashboard + RAG + buttons)?

These are mostly v1.0 polish decisions — they don't block D1-D5. We can iterate on them as we approach D6.

---

## 15. Recommendation

Start D1 today. The scaffold is mostly mechanical (Tauri + Vite + FastAPI boilerplate), and once it's running the rest of the design becomes concrete.

Before D1: confirm the architectural choices (next AskUserQuestion).
