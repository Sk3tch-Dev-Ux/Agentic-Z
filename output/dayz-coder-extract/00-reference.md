# Agentic-Z — Extracted Reference

A single readable map of the cloned [Agentic-Z](../../README.md) DayZ-modding agent stack. Built so you can remix it for your own ventures without re-reading 40+ files.

Source repo: `C:\Users\KurtE\OneDrive\Documents\GitHub\Agentic-Z`
Author of upstream template: Brian Orr (DayZ n' Chill). License: see `LICENSE`. Free to use for DayZ modding.

---

## 1. The Three-Layer Rule System

The whole stack is structured around layered rules. The deeper layer wins ties.

| Layer | Scope | Source of truth |
|---|---|---|
| **L1 — Default rules** | Every clone, every agent, every skill (DayZ or not). | `CLAUDE.md` / `AGENTS.md` / `GEMINI.md` (same content, three filenames so each CLI auto-loads its own). |
| **L2 — DayZ conventions** | When working inside the DayZ domain. | `.claude/skills/_shared/dayz-conventions.md`, plus the EnScript style guide alongside it (`enscript-style.md`). |
| **L3 — Specific agent / skill** | The unit of work. | `.claude/agents/<name>.md` or `.claude/skills/<name>/SKILL.md`. |

L3 references L2 in one line ("Follow `.claude/skills/_shared/dayz-conventions.md`."). Agents are expected to read L2 when invoked.

### L1 highlights (worth keeping in your head)

- **Communication — answer first, caveat after.** Deliver the answer; mention any tool/access limitation as a one-liner *after*, never as the lead.
- **Tooling — pick the fastest tool for the job.** Dedicated `Read` / `Edit` / `Write` / `Glob` / `Grep` first. Default to Python for non-trivial work (~150 ms cold start). PowerShell only when explicitly asked or genuinely faster (~1.5 s cold start). Bash trivial one-liners only.
- **Memory — `.claude/local-memory/` for user/machine notes; never for rules.** Rules go in the repo so they travel with every clone.
- **Repository layout** — `output/` for one-shot deliverables (default), `workspace/<ModName>/` for in-progress mods, `scripts/` for helper automation, `.claude/agent-memory/` for committed per-agent memory.
- **DayZ exception to `output/`** — built `.pbo`s deploy to `P:\Mods\@<ModName>\Addons\` because that's where the engine looks. DayZ skills must preflight that `P:\` is mounted.

### L2 highlights (DayZ-specific)

- **`P:\` drive must be mounted** before any DayZ work. Every DayZ skill that does work MUST gate on `/dayz-preflight` and halt if it returns non-zero. Only exception: `/dayz-stop-test` (emergency abort).
- **`P:\Mods\` must be a directory junction → `<DayZ install>\!Workshop\`** so PBOs land where the engine reads them. Preflight auto-creates this junction when missing and the install is locatable; hard-fails if the existing path is the wrong shape.
- **DayZ cannot be tested standalone.** `/dayz-launch-test` always launches a local server alongside the client.
- **Both client and server must be `DayZDiag_x64.exe`**, not retail. Retail blocks past the loading screen with `-filePatching` enabled. Server `serverDZ.cfg` must contain `allowFilePatching = 1;` or the client gets `0x00020005`.
- **Workspace mod source** lives at `workspace/<ModName>/`. A directory junction `P:\<ModName>\` → `workspace/<ModName>/` is created at scaffold time so AddonBuilder/engine see the same source the user edits.
- **Server staging** lives at `workspace/_server/` with `missions/<template>/` (editable copies) and `maps/<map>/` (per-map serverDZ.cfg + profiles).
- **UI is not centralized.** Color/theme changes touch three independent places: `.layout` files (per-widget RGBA), inline ARGB in `5_mission/gui/` script (override the calling method, not the constant), and `Colors`/`FadeColors` constants in `3_game/colors.c` (`modded class Colors { const ... }` is a no-op for compile-time constants). "Change all the red UI" is hours of work, not minutes.
- **Path resolution** uses shared resolvers (`find_dayz_tools`, `find_dayz_game`, `find_dayz_diag`, `find_dayz_server`, `find_vanilla_data` in `dayz-preflight/preflight.py`). Skills MUST import these — never re-implement.
- **Optional env vars** (set only when your install is non-default): `DAYZ_TOOLS_PATH`, `DAYZ_GAME_PATH`, `DAYZ_DIAG_PATH`, `DAYZ_SERVER_PATH`, `DAYZ_VANILLA_DATA_PATH`, `DAYZ_WORK_DRIVE`.

### L2 — EnScript style essentials

The full guide is at `.claude/skills/_shared/enscript-style.md`; these are the load-bearing rules.

- **Naming.** Classes PascalCase. Members `m_PascalCase`, statics `s_PascalCase`, locals camelCase, methods PascalCase, parameters camelCase, defines UPPERCASE. Tabs, not spaces.
- **`ref` / `autoptr`.** Member variables ONLY. NEVER on params, returns, locals, or typedefs. NEVER `new ref X()`.
- **`modded class`.** Use to extend vanilla. **Never add `: ParentClass`** — modded classes already inherit from the original; the inheritance clause is silently ignored and is the #1 cause of "my modded class isn't running."
- **`super` ordering.** `super.foo()` first if you want the original logic to run before yours; last if after. Choose deliberately.
- **Null checks.** `if (x)` checks both null and out-of-bounds. Use `notnull` to propagate guarantees rather than re-checking. Don't gate at the wrong layer.
- **Client/server during load.** `IsClient()` / `IsServer()` lie during init. Use `!g_Game.IsDedicatedServer()` for client; `g_Game.IsDedicatedServer()` for server-only. `g_Game.IsServer() && !g_Game.IsMultiplayer()` for offline/SP.
- **No `delete`.** Null the reference and let GC handle it. `delete` segfaults on entities.
- **Empty `#ifdef` blocks segfault.** Add a statement or remove the block.
- **Complex array assignments segfault.** `m_arr[i] = vector.DistanceSq(...) <= d;` — store in an intermediate first.
- **Prefer `EXTrace.Start()` over `CF_Trace_0`** for tracing — minimal overhead when disabled.
- **`GetType()` over `ClassName()`** for entities — returns the config class name even when no script class exists.

---

## 2. The 11 Specialist Agents (L3)

All specialists default to `model: opus`, `memory: project`, and reference L2. Each has its own `.claude/agent-memory/<name>/MEMORY.md`.

| Agent | Lane | Strongest rule(s) |
|---|---|---|
| **dayz-script-specialist** (blue) | Enforce Script — modded classes, RPCs, replication, gameplay logic. Owns all of `P:\scripts\` *except* the UI subtree. | Conform to the EnScript style guide. Modded class over new class. Network-efficient (don't spam `SetSynchDirty` / RPCs). Clean script-layer placement (`3_Game` / `4_World` / `5_Mission`). |
| **dayz-config-specialist** (yellow) | `config.cpp`, CfgPatches, CfgVehicles, CfgWeapons, hidden selections, item properties. | Every mod must have a `CfgPatches` entry. Inherit from the closest logical base. Prefix class names to avoid collisions. Always declare hidden selections for retextures. |
| **dayz-asset-specialist** (cyan) | `.p3d` / `.paa` / `.rvmat`, Workbench asset integration. | Texture suffixes (`_co`, `_nohq`, `_smdi`) are mandatory. Every model needs a Geometry LOD. Power-of-two textures. Paths must be absolute to `P:\` or mod root. |
| **dayz-object-builder** (purple) | `.p3d` LODs, named selections, geometry, damage zones, proxy attachment points — Object Builder workflow only. | LOD order matters. Named selections drive everything (hidden selections, damage, attachments). Hidden selection names must match `config.cpp` exactly. `autocenter = 0` for player-held items. Don't bake materials into the `.p3d`. |
| **dayz-map-specialist** (green) | Terrain Builder, DayZ Editor, map objects, clutter, surfaces. | Heightmap / satellite must be grid-aligned. Object density caps for FPS. Respect surface count limits per cell. |
| **dayz-ui-specialist** (magenta) | `.layout` files, widget scripting, HUD/menu, **and** UI-side color/theme work — including overriding `Colors`-class call sites and HUD scripts in `5_mission/gui/`. | Anchors and alignments for responsiveness. Clean up widgets to prevent leaks. **`modded class Colors { const ... }` is a no-op** — override the calling method instead. |
| **dayz-server-admin** (red) | `types.xml`, `init.c`, `cfggameplay.json`, server performance, CE economy. | XML validity before anything (one bad node breaks CE). Backup `storage_*` before economy changes. Don't oversaturate loot. |
| **dayz-mod-debugger** (orange) | Log/RPT/crash analysis, BattlEye diagnosis, performance profiling. **Reads, doesn't write.** | Never guess from a symptom alone — ask for the artifact. Cite log lines. Diagnose, then hand off. Check the `extends`-on-modded-class anti-pattern first. |
| **dayz-mod-reviewer** (pink) | Audit `workspace/<ModName>/` for convention compliance and common defects. **Read-only.** | Don't fix — flag and route to the right specialist. Cite evidence (file:line). Critical / non-critical severity is binary on hidden-selection mismatches, missing `$PBOPREFIX$`, `extends` violations. |
| **dayz-workbench-specialist** (teal) | Enfusion Workbench plugin development (editor-time tooling, dockable panels, batch automation). | Editor-time, not runtime — don't ship runtime mod scripts inside a Workbench plugin. Reuse `find_dayz_tools()` for paths. Dockable, not modal. Idempotent batch ops. |
| **agent-creator** (lime) | Validate / generate / normalize agent definitions against the 9-section template. | Strict template compliance. Always include the L1 output-convention bullet first in `## CONSTRAINTS` for new agents. |
| **docs-wiki-sync** (gray) | Keep the Docusaurus mirror at `wiki/` in sync with canonical sources. Idempotent. | Never delete a wiki page automatically — orphans get flagged. Reduce frontmatter for Docusaurus. HTML-escape `<example>` / `<commentary>` blocks so MDX doesn't try to render them as components. |

### Lane boundaries that matter

These cross-references are explicit in the agent files and prevent finger-pointing during real work:

- **UI-script work lives with the UI specialist**, not the script specialist — even though `colors.c` and `5_mission/gui/` are in the script tree.
- **The debugger and reviewer never write fixes.** They produce diagnoses or punch lists and route to the matching specialist. Naive consolidation kills this discipline.
- **Workbench plugins are editor-time only.** Runtime mods belong to the script/config specialists.
- **Object Builder ≠ asset specialist.** Object Builder owns `.p3d` geometry/LODs/selections. Asset specialist owns `.paa` textures and `.rvmat` materials. Hidden selections cross both lanes — coordinate.

---

## 3. The 21 Skills (L3)

All DayZ skills gate on `/dayz-preflight` first per L2. Listed by lifecycle order.

### Environment & setup

| Skill | What it does |
|---|---|
| `/dayz-preflight` | Verify `P:\` mounted, AddonBuilder locatable, vanilla data unpacked, `P:\Mods\` is a junction to `!Workshop\`. Hard-fail on `P:\`; warn on the rest. Read-only — exports `find_dayz_tools()` / `find_vanilla_data()` / `find_dayz_diag()` / `find_dayz_server()` for every other skill to import. |
| `/dayz-mount-p` | Mount `P:\` without opening DayZ Tools (auto-resolves work drive from Tools' `settings.ini`). Per-session — `P:\` doesn't auto-mount across reboots. |
| `/dayz-setup-objectbuilder` | One-time machine setup for Object Builder (registry/file associations). |

### Authoring lifecycle

| Skill | What it does |
|---|---|
| `/dayz-new-mod <ModName> [--author X]` | Scaffold `workspace/<ModName>/` with `config.cpp` / `$PBOPREFIX$` / `scripts/{3_Game,4_World,5_Mission}/` / `data/` / `gui/`. Create `P:\<ModName>\` junction → `workspace/<ModName>/`. Author handle cached at `.claude/local-memory/dayz-author.txt`. Strict name regex (letter, then letters/digits/underscores, max 64). Refuses on collisions; auto-cleans dangling junctions matching the about-to-scaffold target. |
| `/dayz-add-map <map>` | One-time per map. Copy mission template (chernarus → `dayzOffline.chernarusplus`, livonia → `dayzOffline.enoch`, sakhal → `dayzOffline.sakhal`, custom by exact folder name) from DayZ Server install to `workspace/_server/missions/`, create `workspace/_server/maps/<map>/serverDZ.cfg` + `profiles/`. |
| `/dayz-build-pbo <ModName> [--clean]` | Verify junction, resolve `AddonBuilder.exe`, ensure `P:\Mods\@<ModName>\Addons\` and `P:\temp\<ModName>\` exist, invoke AddonBuilder with `-prefix=<ModName>` and stream stdout/stderr live, verify PBO refreshed, clean temp on success (kept on failure for debugging). `--clean` adds `-clear`. |
| `/dayz-pack-texture <input> <output>` | PNG/TGA → `.paa` via ImageToPAA. Validates `_co` / `_nohq` / `_smdi` suffix on output. |
| `/dayz-types-edit` | Programmatically upsert a single `<type>` node in `types.xml`. |
| `/dayz-types-split` | Split a monolithic `types.xml` into 18 categorized files (vendored TypeSplitter). |

### Test loop

| Skill | What it does |
|---|---|
| `/dayz-launch-test <Mod1> [<Mod2>...] [--map M] [--port N] [--dry-run]` | Verify each mod has a built PBO. Resolve diag exe. First-run only: bootstrap missions from DayZ Server. Auto-append `allowFilePatching = 1;` to existing `serverDZ.cfg` if missing. Spawn server (diag + `-server` + `-mission=<absolute>` + `-mod=@A;@B` + `-filePatching` + port). Wait 5 s. Spawn client (diag + `-profiles=workspace/_server/!ClientDiagLogs` + `-connect=127.0.0.1` + `-mod=...` + `-filePatching`). Print PIDs and exit. |
| `/dayz-stop-test` | Force-kill any running `DayZDiag_x64.exe` processes. **Doesn't gate on preflight** — emergency abort, the only documented exception to the gating rule. |
| `/dayz-launch-workbench` | Open Enfusion Workbench (script + UI editor) detached. |
| `/dayz-launch-objectbuilder` | Open Object Builder (`.p3d` editor) detached. |

### Knowledge / RAG

| Skill | What it does |
|---|---|
| `/dayz-rag-download` | Pull prebuilt vanilla+wiki vector index from GitHub releases (~1 min, no API key). Recommended for fresh clones — avoids the 25–30 min local build. |
| `/dayz-rag-index [--full]` | Build the local semantic-search index over vanilla DayZ source (`P:\scripts\`, `P:\dz\`, `P:\gui\`). |
| `/dayz-rag-wiki-index` | Index the Bohemia community wiki into the same DB. |

> **Note on the embedding backend:** the README states embeddings run via Voyage AI (`voyage-code-3`, paid API key needed), while `dayz-conventions.md` claims local embeddings via `nomic-ai/CodeRankEmbed`. The two docs disagree — see [`01-upgrades.md`](01-upgrades.md) for which is actually wired up and what to fix.

### Cleanup

| Skill | What it does |
|---|---|
| `/dayz-clean-workspace` | DayZ-only cleanup. Removes `workspace/<ModName>/`, the `P:\<ModName>\` junctions targeting our workspace, and `P:\Mods\@<ModName>\` deploy dirs. `--include-server` also wipes `workspace/_server/`. Match-on-scaffold rule keeps subscribed Workshop mods safe. |
| `/clean-repo` | Repo-wide cleanup orchestrator across every domain. |

### Meta

| Skill | What it does |
|---|---|
| `/sync-skills` | Symlink (or junction-fallback) `.claude/skills/` into Claude Code, Codex CLI, and Gemini CLI home dirs so all three discover the same slash commands. Required after fresh clone. Adding a new agent CLI = one entry in `.claude/skills/sync-skills/agents.json`. |
| `/docs-sync` | Detect drift between canonical sources and the Docusaurus wiki at `wiki/`. |
| `/agentic-z-update` | Pull and reconcile updates from the upstream template. |

---

## 4. The MCP Server — `dayz-rag`

Local MCP server at `.claude/mcp/dayz-rag/server.py` exposes semantic search to every agent.

### Tool surface

| Tool | Signature | Purpose |
|---|---|---|
| `search_dayz_source` | `(query: str, top_k: int = 5, file_type: str | None = None)` | Vector search over indexed vanilla. Returns chunks with `path`, `parent_context`, `line_start` / `line_end`, score, 1500-char snippet. `file_type` ∈ `c` / `cpp` / `hpp` / `h` / `layout` / `cfg` / `None`. |
| `get_dayz_file` | `(path: str, line_start: int = None, line_end: int = None)` | Fetch full or partial file content for follow-up after a search hit. Sandboxed to paths under `P:\`. |
| `list_indexed_sources` | `()` | Manifest summary. Useful to confirm what was indexed and when. |

### When to use it (per L2)

- "How does vanilla handle X?" with no symbol name in mind.
- Two or three Greps already came up empty — that's the signal you don't know the right term.
- Browsing for vanilla examples to mirror (e.g. "find a vanilla layout with scrollbars").

### When NOT to use it

- You already know the exact class/symbol — that's `Grep` territory.
- Binary content (`.p3d`, `.paa`) — not indexed.
- `.rvmat`, `types.xml`, `events.xml`, `layers.cfg`, `.json`, `.csv` — excluded by design.

### Setup gate

If `search_dayz_source` returns `"no index"`, run `/dayz-rag-download` (recommended) or `/dayz-rag-index --full`. After a DayZ update, the index goes stale — rerun.

---

## 5. Repo Conventions Summary

| Concern | Convention |
|---|---|
| Working directory | Repo root. Everything is relative. Don't litter the root. |
| One-shot deliverables | `output/<descriptive-folder>/` |
| In-progress mods | `workspace/<ModName>/` with junction `P:\<ModName>\` → here |
| Server staging | `workspace/_server/missions/`, `workspace/_server/maps/<map>/`, `workspace/_server/!ClientDiagLogs/` |
| Helper scripts | `scripts/` (tools, not products) |
| Per-clone caches | `.claude/local-memory/` (gitignored — user/machine notes only, NEVER rules) |
| Per-agent memory | `.claude/agent-memory/<agent-name>/MEMORY.md` (committed) |
| Built PBOs | `P:\Mods\@<ModName>\Addons\<ModName>.pbo` (junction target = `<DayZ install>\!Workshop\`) |
| L1 / L2 doc sync | `CLAUDE.md` / `AGENTS.md` / `GEMINI.md` are plain copies — edit all three together. No SYMLINKs. |

---

## 6. Model Routing — Match Model to Task

From `docs/model-routing.md`, summarized:

| Task | Model | Why |
|---|---|---|
| Trivial file-find ("where is X defined?") | Haiku 4.5 subagent | Single grep, no synthesis |
| Research / "tell me about X" / "how does Y work" | Sonnet 4.6 subagent | Multi-source synthesis, ~2-3× faster than Opus |
| Coding / editing / planning / debugging / design | Opus 4.7 main thread | Deepest reasoning |

The cost of mismatching down (Haiku for depth) is a thin answer. The cost of mismatching up (Opus for a lookup) is 30-60 s of wasted latency. **Default to Sonnet when unsure.** Dispatch via the `Agent` tool with `model: "sonnet"`; bound the report (word limit, file:line citations).

---

## 7. Prompt Conventions (caps, headers)

From `docs/prompt-conventions.md`:

- **Uppercase section headers** (`## NAME`, `## ROLE`, etc.) are structural — for tooling, not the model.
- **Inline caps directives** (`MUST`, `NEVER`, `ALWAYS`, `DO NOT`, `CRITICAL`) are behavioral — they raise compliance per RFC 2119, but only when used sparingly.
- The "remove the caps and re-read" test: if the sentence still feels like an absolute rule without caps, leave it lowercase. Caps are a finite signal — overspending evaporates the boost.

---

## 8. How to extend it

| Adding | What to do |
|---|---|
| A new skill | Create `.claude/skills/<name>/`, write `SKILL.md` with `name` / `description` frontmatter and a "How to run" section, drop the script in. Run `/sync-skills` to register it across CLIs. |
| A new agent | Use `/agent-creator` to generate it, then drop into `.claude/agents/`. Mirror the dayz-script-specialist file structure exactly (9 sections, `## NAME` headers). |
| A new agent CLI | Append an entry to `.claude/skills/sync-skills/agents.json` and run `/sync-skills`. The new home gets links for every skill automatically. |

---

## 9. What this template does NOT cover (gaps)

These show up as opportunities in [`01-upgrades.md`](01-upgrades.md):

- **Workshop publishing** — no skill for `DayZ Tools → Publisher → upload`, version bump, change-notes templating.
- **BattlEye filter sync** — no skill that diffs server-side `*.txt` filter files against client logs of recent kicks.
- **types.xml validator / dry-run** — `/dayz-types-edit` upserts but doesn't validate against the running CE schema.
- **CE balance scan** — no agent that audits loot tables for nominal/min consistency, lifetime sanity, restock pacing.
- **Mission init.c / event scan** — no skill that diffs custom mission files against vanilla baselines.
- **CUI (Community UI Framework) integration** — L2 mentions CUI as the answer to scattered theming, but no agent or skill knows how to generate a CUI-based theme stub.
- **Server admin tooling** — no skill to clear corrupted `storage_1`, regenerate persistence, or reset character DB.
- **Anti-cheat / RPT analyzer** — debugger reads logs, but no skill to *parse and summarize* RPTs into a punch list for the debugger to consume.
- **PboProject support** — only AddonBuilder is wired up. Some workflows prefer Mikero's PboProject for incremental rebuilds.
- **Versioned source-of-truth for `config.cpp`** — no schema/lint pass on the most defect-prone file in the stack.
