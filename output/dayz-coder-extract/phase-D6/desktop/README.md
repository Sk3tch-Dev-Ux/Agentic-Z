# Agentic-Z Desktop

DayZ modding command center. Pitch a mod idea, watch Claude write it. Audit and ship mods autonomously. Live error stream, semantic search across vanilla + your code, skill proposals you can promote with one click.

Built on top of the [Agentic-Z CLI toolkit](../README.md) — same agents, same skills, same `.claude/` layout, just with a real interface around them.

---

## What it does

| Feature | What it gets you |
|---|---|
| **Mod Creator** | Type a plain-English pitch ("medkit that heals over 30s, 2% military spawn"). Claude writes the full scaffold — `config.cpp`, `$PBOPREFIX$`, scripts in 3_Game/4_World/5_Mission, types.xml entries — following the EnScript style guide. Click Build → Launch. |
| **Director** | Goal-pursuing agent. Say "ship MyMod" → it audits → fixes → re-audits → builds → launches → tails logs. Live state-machine diagram. Hard caps prevent runaway loops. |
| **Live event feed** | Diag server/client RPTs + script.log + BattlEye logs streamed into the app, classified by lane (script / config / asset / server / ui / debug) with one-line fix hints. |
| **One-click build/launch** | Build, Launch, Stop buttons. AddonBuilder output streams live in a panel. PIDs surface for the diag server + client. |
| **RAG search (Ctrl+K)** | Semantic search across vanilla DayZ, the Bohemia community wiki, and your own workspace mods. File:line preview. "Open in editor" jumps you to VS Code. |
| **Skill proposal manager** | The `/agentic-z-promote-skill` meta-skill scans your agent memory for recurring patterns and drafts new skills. Review them in the UI, edit inline, promote with one click. |

---

## Install (end users)

For developers building from source, see [`docs/BUILDING.md`](docs/BUILDING.md).

### Prerequisites

| What | Why |
|---|---|
| **Windows 10 or 11** | DayZ Tools is Windows-only; v1 is Windows-first. |
| **DayZ + DayZ Tools** (Steam) | The actual modding environment. |
| **Python 3.10+** on PATH | The sidecar runtime + every CLI skill. |
| **Anthropic API key** | For the Mod Creator and Audit features. Pay-as-you-go on your account. |
| **Voyage AI key** *(optional)* | For Cmd+K semantic search. Free tier covers 200M tokens. |

### Steps

1. Download the latest `Agentic-Z_<version>_x64-setup.exe` from [Releases](https://github.com/dayznchill/Agentic-Z/releases).
2. Run the installer. (Windows SmartScreen will warn — the installer isn't code-signed for v1.0; click "More info" → "Run anyway".)
3. Launch Agentic-Z. The first-run wizard walks you through API keys + author handle + DayZ environment check.
4. From the Dashboard, click **"New mod from pitch"** → describe your idea → watch Claude generate.

Full install + first-run walkthrough: [`docs/INSTALL.md`](docs/INSTALL.md).

---

## Architecture (one paragraph)

A Tauri 2 shell over a Python (FastAPI) sidecar over the existing Agentic-Z CLI skills. The Tauri Rust binary spawns the sidecar at startup, the sidecar imports the existing skill modules as a long-lived process, and the React frontend talks to it over HTTP + Server-Sent Events on `localhost`. The `dayz-coder.md` agent definition is loaded as the Mod Creator's system prompt; tool calls (`write_file`, `done`) generate the actual mod files. No business logic in Rust — the shell just spawns and cleans up. No Python embedded in Rust — the sidecar runs as a normal subprocess and can be tested standalone via `python sidecar/main.py`.

Full architecture rationale + alternatives considered: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Build from source

```cmd
:: Prerequisites: Node 20, pnpm, Rust toolchain (rustup), Python 3.10+
git clone https://github.com/dayznchill/Agentic-Z
cd Agentic-Z\desktop
pnpm install
pip install -r sidecar\requirements.txt
pnpm tauri:dev          :: dev mode with hot reload
:: or:
pnpm tauri:build        :: production .exe at src-tauri\target\release\bundle\nsis\
```

CI builds on tag push (`desktop-v*.*.*`) — see `.github/workflows/desktop-release.yml`.

---

## Roadmap (post-1.0)

- Code signing for Windows (no SmartScreen warning) — ~$200/year cert decision pending
- macOS + Linux builds (Tauri supports them; v1 is Windows because DayZ is)
- Workshop publishing inside the app (`PublisherCmd.exe` integration)
- BattlEye filter sync — diff your server filters against recent kicks, suggest whitelist additions
- Visual mod-merger — diff/merge UI for combining workspace mods

Open issues + feature requests at [github.com/dayznchill/Agentic-Z/issues](https://github.com/dayznchill/Agentic-Z/issues).

---

## Community

- **Discord:** [discord.gg/dayznchill](https://discord.gg/dayznchill) — DayZ n' Chill modding community.
- **Contributing:** [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md). PRs welcome — small ones especially. The codebase is intentionally boring (React + TypeScript + Tailwind + FastAPI) so newcomers can land changes fast.

---

## License

Free to use for developing DayZ modifications. See [`../LICENSE`](../LICENSE) (Copyright © 2026 Brian Orr / DayZ n' Chill).
