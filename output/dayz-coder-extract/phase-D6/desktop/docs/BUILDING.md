# Building Agentic-Z Desktop from Source

For developers. End users: download the installer from [Releases](https://github.com/dayznchill/Agentic-Z/releases) and follow [`INSTALL.md`](INSTALL.md).

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Node.js | 20+ | with `npm` |
| pnpm | 9+ | `npm install -g pnpm` after Node |
| Python | 3.10+ | "Add to PATH" during installer |
| Rust toolchain | stable | via [rustup.rs](https://rustup.rs/) |
| MSVC build tools | Latest | Windows only — see below |
| WebView2 runtime | Latest | usually preinstalled on Windows 10/11 |

### Windows-specific: MSVC build tools

Tauri needs the C++ build tools to link the Rust binary. If `pnpm tauri:dev` fails with "MSVC not found" or LINK errors:

1. Download [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/).
2. In the installer, select the **"Desktop development with C++"** workload.
3. ~2 GB download. One-time install.
4. Restart your terminal.

---

## Get the source

```cmd
git clone https://github.com/dayznchill/Agentic-Z
cd Agentic-Z\desktop
```

---

## Dev mode (hot reload)

```cmd
pnpm install                              :: ~30-60s, ~200 MB into node_modules
pip install -r sidecar\requirements.txt   :: ~15 MB
pnpm tauri:dev
```

What happens:

1. Vite spins up at `http://localhost:5173`.
2. Tauri compiles the Rust shell (5-10 minutes first run, sub-second after).
3. Tauri spawns `python sidecar/main.py` as a child process.
4. The sidecar discovers a free port (7321 first), writes it to `.claude/local-memory/agentic-z-desktop.port`.
5. The Tauri window opens; the WebView reads the port via the `get_sidecar_status` Tauri command and starts hitting `http://127.0.0.1:<port>/api/*`.

Edit any file under `src/` → instant hot-reload in the app window. Edit `sidecar/*.py` → restart `pnpm tauri:dev` (or run the sidecar standalone with `pnpm sidecar:dev` and reload the window).

---

## Sidecar standalone (no Tauri)

For backend-only iteration:

```cmd
cd desktop\sidecar
python main.py
```

Open <http://localhost:7321/docs> in a browser → FastAPI Swagger UI for every endpoint. Click "Try it out" on any endpoint, see the live response.

---

## Production build

```cmd
pnpm tauri:build
```

Output: `desktop\src-tauri\target\release\bundle\nsis\Agentic-Z_<version>_x64-setup.exe` (and `msi`).

First production build takes ~5-10 minutes (Rust release compile with LTO + size optimizations). Subsequent builds are faster thanks to incremental compilation. The final `.exe` is ~5-10 MB.

---

## CI builds

GitHub Actions builds tag-triggered. To cut a release:

```cmd
:: Bump version in package.json + Cargo.toml + tauri.conf.json
:: Then:
git tag desktop-v0.6.0
git push origin desktop-v0.6.0
```

Watch the Actions tab. A draft Release will appear under **Releases** when the build completes. Edit the description, attach screenshots, click Publish.

The workflow at `.github/workflows/desktop-release.yml` currently builds Windows only. To enable macOS/Linux: uncomment the relevant matrix entries.

---

## Tauri prerequisites by OS

For users building on non-Windows:

| OS | Setup |
|---|---|
| Windows | MSVC build tools (above) + WebView2 (usually preinstalled) |
| macOS | Xcode command line tools (`xcode-select --install`) |
| Linux | `webkit2gtk` + build essentials — see [Tauri docs](https://v2.tauri.app/start/prerequisites/) |

DayZ is Windows-only, so non-Windows builds are best-effort and primarily useful for working on the search/proposal/editor UI in isolation.

---

## Common build issues

**`pnpm: command not found`** → install Node, then `npm install -g pnpm`.

**`error: Microsoft Visual C++ Build Tools not found`** → install MSVC build tools (above). Restart your terminal afterward so Tauri sees the new PATH entries.

**`failed to run cargo metadata`** with `can't find library 'X'` → check `Cargo.toml` for any `[lib]` section that points to a non-existent file. Drop the `[lib]` block if you're not building a library.

**`unknown field 'scope'` in Tauri plugin config** → Tauri 2 changed several plugin configs from v1. The `fs` plugin's scope moved to capability files (`src-tauri/capabilities/`). For v1.0 we don't use fs scope; the `plugins.fs` block is removed entirely.

**Sidecar can't find skills** → the sidecar resolves the repo root from its own location (`<repo>/desktop/sidecar/main.py`). Make sure `desktop/` is at the repo root and `.claude/skills/dayz-preflight/preflight.py` exists.

**Window opens but blank** → Vite didn't start on 5173. Check that nothing else is listening on that port. Try `pnpm dev` directly to see the error.

**Anthropic key tests pass but Mod Creator hangs** → make sure the model is available on your account. Default is `claude-opus-4-7`. Override via `VOYAGE_MODEL` env var (in .env) for both keys.

**OneDrive sync issues during dev** → if files appear out of sync between editors and the running sidecar, pause OneDrive sync briefly. Polling the file system is OneDrive's enemy.

---

## Architecture deep-dive

[`ARCHITECTURE.md`](ARCHITECTURE.md) covers the full design — why Tauri over Electron, why FastAPI sidecar over native Rust, the IPC model, path safety patterns, and the build pipeline.

For PR-time orientation, [`CONTRIBUTING.md`](CONTRIBUTING.md) is shorter.
