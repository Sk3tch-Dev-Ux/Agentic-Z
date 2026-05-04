# Installing Agentic-Z Desktop

For end users. Developers building from source: see [`BUILDING.md`](BUILDING.md).

---

## 1. Prerequisites

You need these things on your Windows machine before installing Agentic-Z:

| | Get it | Why |
|---|---|---|
| **Windows 10 or 11** | already on your PC | OS support |
| **DayZ** | Steam | The actual game (also where the diag client lives) |
| **DayZ Tools** | Steam → Library → Tools (free) | AddonBuilder, P-drive mounting, ImageToPAA |
| **Python 3.10+** | [python.org](https://python.org) — check "Add to PATH" during install | Sidecar + all skill scripts |
| **Anthropic API key** | [console.anthropic.com](https://console.anthropic.com) | Mod Creator. Pay-as-you-go on your account. |
| **Voyage AI key** *(optional)* | [dash.voyageai.com](https://dash.voyageai.com) | Cmd+K semantic search. Free tier covers full DayZ index. |

If you've already got the [Agentic-Z CLI toolkit](https://github.com/dayznchill/Agentic-Z) cloned and working, you have everything except possibly the Anthropic key.

---

## 2. Download

Grab the latest `Agentic-Z_<version>_x64-setup.exe` from [Releases](https://github.com/dayznchill/Agentic-Z/releases).

Pick the most recent `desktop-v*.*.*` tag.

---

## 3. Install

Run the `.exe`. Windows SmartScreen will probably warn:

> **Windows protected your PC**
> Microsoft Defender SmartScreen prevented an unrecognized app from starting…

This is because v1.0 isn't code-signed (a code-signing certificate costs ~$200/year and is on the post-1.0 roadmap). Click **"More info"** → **"Run anyway"**. The installer is NSIS-based and lands at `C:\Users\<you>\AppData\Local\Agentic-Z\` by default.

---

## 4. First run

Agentic-Z's first-run wizard pops up the first time you launch the app. Five steps:

1. **Welcome** — feature overview.
2. **Anthropic API key** — paste your `sk-ant-…` key. The "Test" button validates it with a 1-token request.
3. **Voyage AI key** *(optional)* — paste your `pa-…` key for semantic search. Skippable.
4. **Author handle** — what gets written into `config.cpp` as the mod author when you scaffold.
5. **Done** — environment summary.

You can skip any step. Settings are reachable later via the gear icon top-right.

---

## 5. Make your first mod

From the Dashboard:

1. Click **"New mod from pitch"** (top-right).
2. **Mod name:** something like `MyFirstMod` (letters, digits, underscores; must start with a letter; max 64 chars).
3. **Pitch:** describe what you want in plain English. Examples that work well:
   - *"Add a custom medkit that heals over 30 seconds and spawns at 2% rate in military zones"*
   - *"Make players regenerate stamina faster after sleeping next to a campfire"*
   - *"Add a tactical vest with 3 attachment slots for plate carriers"*
4. Click **Generate**.
5. Watch Claude write the files. Each `file_written` event lands at `workspace/MyFirstMod/`.
6. When done, click **"Open mod"**.
7. On the mod detail page, click **Build** → AddonBuilder runs, output streams live.
8. Click **Launch** → diag server + client come up.

---

## 6. What's where on disk

| Path | What |
|---|---|
| `<repo>/workspace/<ModName>/` | Your mod source. Edit here. Junctioned to `P:\<ModName>\`. |
| `P:\Mods\@<ModName>\Addons\<ModName>.pbo` | Built artifact. Engine reads from here. |
| `<repo>/.claude/local-memory/` | Per-clone runtime state (gitignored). API keys (.env), watch logs, director status. |
| `<repo>/.claude/agent-memory/<agent>/` | Persistent committed memory. Director postmortems live under `dayz-director/runs/`. |
| `<repo>/.env` | API keys (gitignored). Written by the Settings page. |

---

## 7. Troubleshooting

**Sidecar offline pill in the status bar.**
The Python process didn't start. Open Settings → Advanced (or run `python desktop\sidecar\main.py` from a terminal in the install dir) to see the actual error. Most common: Python isn't on PATH.

**Mod Creator says "ANTHROPIC_API_KEY not set".**
Go to Settings → paste your key → Save. Then retry. If the key is set but Test fails: the key is invalid or expired.

**Build button fails with "AddonBuilder.exe not found".**
DayZ Tools isn't installed or isn't on the standard path. Set `DAYZ_TOOLS_PATH` in `.env` to your Tools install root, restart the app.

**Preflight fail: "P:\\ is not mounted".**
Open DayZ Tools → mount the P drive. Or run `/dayz-mount-p` in a terminal. P:\ doesn't auto-mount across reboots.

**Cmd+K shows "RAG offline".**
Either Voyage key isn't set, or the index isn't built. Set the key in Settings, then run `/dayz-rag-download` in a terminal (~1 minute, ~280 MB).

**Director's "Ship It" button copies a prompt to clipboard but nothing happens.**
The director runs inside Claude Code (the CLI), not directly in the app — direct API integration for the director lands post-v1. For now: open Claude Code, paste the prompt, watch the diagram light up live in the app's `/director` page.

---

## 8. Update

Future releases will support in-app update notifications. For v1.0, check [Releases](https://github.com/dayznchill/Agentic-Z/releases) periodically. Download the new installer, run it — your settings + mods are preserved (they live in your repo, not the install dir).

---

## 9. Uninstall

Control Panel → Apps → Agentic-Z → Uninstall. The installer removes the app dir; your repo / `workspace/` / API keys (in `.env`) stay intact.

To fully remove all traces, also delete:
- `<repo>/.claude/local-memory/` (runtime state)
- `<repo>/.claude/agent-memory/dayz-director/` (postmortems)
- `~/.claude/dayz-rag-index/` (RAG index, ~250 MB)
- `<repo>/.env` (your API keys — be sure)
