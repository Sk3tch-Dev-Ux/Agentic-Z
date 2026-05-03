# Agentic-Z — Upgrade Plan

Concrete improvements layered on top of the cloned template, ordered by leverage. Every recommendation references a file path so you can act on it directly.

---

## A. Inherited bugs in your clone (fix these first)

### A1. Hardcoded `G:\AI-Templates\` memory path in every agent

Every agent definition contains this line near the bottom:

> You have a persistent, file-based memory system at `G:\AI-Templates\.claude\agent-memory\<name>\`. This directory already exists — write to it directly with the Write tool…

Your repo lives at `C:\Users\KurtE\OneDrive\Documents\GitHub\Agentic-Z`, so that path **does not exist on your machine**. Result: every "save this to memory" call from any agent silently fails or writes to a phantom path.

**Affected files** (16, all under `C:\Users\KurtE\OneDrive\Documents\GitHub\Agentic-Z`):

```
.claude\agents\agent-creator.md
.claude\agents\dayz-asset-specialist.md
.claude\agents\dayz-config-specialist.md
.claude\agents\dayz-map-specialist.md
.claude\agents\dayz-mod-debugger.md
.claude\agents\dayz-mod-reviewer.md
.claude\agents\dayz-object-builder.md
.claude\agents\dayz-script-specialist.md
.claude\agents\dayz-server-admin.md
.claude\agents\dayz-ui-specialist.md
.claude\agents\dayz-workbench-specialist.md
.claude\skills\dayz-mount-p\mount.py
.claude\skills\dayz-mount-p\SKILL.md
.claude\skills\sync-skills\SKILL.md
wiki\docs\skills\sync-skills.md
wiki\docs\skills\dayz-mount-p.md
```

**Fix.** Replace the absolute path with a repo-relative path so it works on any clone:

```text
You have a persistent, file-based memory system at `<repo>/.claude/agent-memory/<name>/`.
```

Or, even better, make the agent resolve the repo root at runtime by walking up from `__file__` until it finds `CLAUDE.md`. The `.claude/agent-memory/<name>/` directories already exist for the 9 DayZ specialists in your clone, so the directive will Just Work as soon as the path is fixed.

This is a 5-minute global find-and-replace. Highest-leverage single fix.

### A2. RAG backend documentation contradicts implementation

`docs/dayz-modding.md`, `README.md`, `.claude/mcp/dayz-rag/README.md`, and `.claude/mcp/dayz-rag/server.py` all agree: **embeddings run via Voyage AI cloud (`voyage-code-3`, 1024D)**, with `VOYAGE_API_KEY` required.

But `.claude/skills/_shared/dayz-conventions.md` (lines ~38-46) claims:

> The RAG layer (`/dayz-rag-index` + the `dayz-rag` MCP server) runs **fully locally** with `nomic-ai/CodeRankEmbed`… No API keys, no network calls, no per-query cost.

That paragraph is stale — it describes a previous local-embedding implementation that was replaced. **Agents reading L2 will be told there are no API keys; users will then hit "VOYAGE_API_KEY not set" and have to debug the contradiction.**

**Fix.** In `.claude/skills/_shared/dayz-conventions.md`, replace the "RAG embedding (local)" section with:

```markdown
## RAG embedding (cloud, optional)

The RAG layer (`/dayz-rag-index` + the `dayz-rag` MCP server) runs against **Voyage AI** (`voyage-code-3` by default, 1024D, asymmetric encoding). Free tier (200M tokens) covers ~3 full rebuilds. Add `VOYAGE_API_KEY=pa-…` to `.env` at the repo root before running `/dayz-rag-index` or any agent that uses `search_dayz_source`.

Skip the build entirely with `/dayz-rag-download` — pulls a prebuilt vanilla+wiki index from GitHub releases (~1 min, no key needed for download). Query-time embedding still requires the key.

Without a key, agents fall back to `Grep` over `P:\scripts\` and friends — fully functional, just less smart.
```

### A3. Workbench specialist's frontmatter inconsistency

The Explore agent reported the Workbench specialist file appears in the `G:\AI-Templates\...` grep hits but I haven't verified its full structure. Worth a 30-second `/agent-creator` validation pass on all 11 agents to make sure the frontmatter and 9-section structure compile clean. If you want, run the unified `dayz-coder` agent's `audit` mode instead (it absorbs the reviewer's logic).

---

## B. Modernize + tune for DayZ (medium-leverage, mostly additive)

### B1. Add a `--rebuild` flag to `/dayz-launch-test`

Right now you have to chain `/dayz-build-pbo MyMod && /dayz-launch-test MyMod`. Most iteration loops do exactly that. Adding `--rebuild` to `/dayz-launch-test` lets the agent issue a single command:

```python
# launch.py — pseudocode
if args.rebuild:
    for mod in args.mods:
        run_build_pbo(mod)        # imports build.py main()
# ... existing launch logic
```

Tiny change, huge ergonomic improvement.

### B2. Post-launch sanity check in `/dayz-launch-test`

Currently the skill spawns processes and exits. The user has to alt-tab to the diag client to know whether the mod actually loaded. Add a 3-5 second tail of `workspace/_server/maps/<map>/profiles/server_console.log` and `script.log` after launch, looking for:

- `"Mods loaded: @<ModName>"` (or absence of it → flag)
- `"compile error"` / `"unexpected eof"` / `"undefined variable"` (script compile failures)
- `"Mission script has no main function"` (mission folder mis-pointed)

Print findings before exiting. Doesn't block the launch — informational.

### B3. `/dayz-types-validate` skill (new)

`/dayz-types-edit` upserts a `<type>` node but doesn't validate. Add a sibling skill that:

- Schema-validates `types.xml` against the DayZ Server XSD (or a permissive lint when XSD isn't bundled).
- Sanity checks: `nominal >= min`, `lifetime > 0`, `restock` cadence within sensible range, no duplicate `name` keys, every `category`/`tag`/`usage`/`value` references something declared in the corresponding xml.
- Cross-references `cfgspawnabletypes.xml` and `events.xml` for orphan items.

Output: punch list with file:line citations, in the same shape as `dayz-mod-reviewer`.

### B4. `/dayz-publish-workshop` skill (new)

DayZ Tools' Publisher CLI exists (`PublisherCmd.exe`). A skill that:

- Reads a `workshop.json` next to `config.cpp` (title, description, tags, image path).
- Bumps a version field automatically.
- Calls `PublisherCmd.exe` with the right args (`-action=update -id=<published_file_id>` or `-action=create`).
- Verifies the upload succeeded by parsing stdout.

Removes the current "alt-tab into Publisher GUI" tax for releases.

### B5. `/dayz-battleye-sync` skill (new)

Server-side BattlEye filter files (`scripts.txt`, `createvehicle.txt`, etc.) are the #1 source of "my mod works locally but kicks players online" tickets. A skill that:

- Diffs your server's filter files against a vanilla baseline.
- Reads recent `BattlEye/*.log` kicks from `workspace/_server/!ClientDiagLogs/BattlEye/`.
- Suggests filter additions to whitelist your mod's actions, with rule-line stubs.

Pairs naturally with `dayz-mod-debugger` (debugger reads logs, this skill writes the fix).

### B6. `/dayz-rpt-triage` skill (new)

Currently `dayz-mod-debugger` reads logs but you have to hand-feed it the artifact. A skill that:

- Auto-locates the most recent `*.RPT` in `workspace/_server/maps/<map>/profiles/` and `workspace/_server/!ClientDiagLogs/`.
- Runs a regex pass for known-bad patterns (NPE, segfault traces, "Cannot find class", filter kicks, mod-load failures).
- Outputs a structured punch list ready for the debugger to consume.

### B7. CUI theme stub generator

L2 calls out CUI (Community UI Framework) as the answer to scattered theming. Add a skill that scaffolds a CUI-based theme stub:

```
workspace/<ModName>/scripts/3_Game/MyModTheme.c        # CUI theme registration
workspace/<ModName>/gui/layouts/themed/                 # layout overrides hooked into CUI
```

…and a corresponding L2 update naming CUI as the recommended path for new mods doing UI theming.

### B8. Vehicle-specific coordinator agent (or vehicle skill bundle)

Vehicles span script + config + asset + object-builder + sound. The 9 specialists handle each piece, but no agent owns the cross-cutting "I want to add a Lada" task. Two options:

- **Option A (lightweight):** A `/dayz-new-vehicle <Name>` skill that scaffolds the four-file vehicle pattern (config CfgVehicles entry, scripts subclass, simulationClass wiring, hidden selections placeholder, types.xml entry).
- **Option B (heavier):** A `dayz-vehicle-coordinator` agent that orchestrates the four specialists.

Lean toward A. Skills compose better than coordinator agents.

### B9. Sound / animation specialist agent

Currently no agent owns `.ogg` / `.wss` / sound shaders or `.asi` / animation graphs. For mods that touch either domain, the user is on their own. Spinning up a `dayz-sound-specialist` and a `dayz-animation-specialist` (or a combined `dayz-fx-specialist`) closes that gap.

### B10. PboProject (Mikero) parity

Some workflows prefer Mikero's PboProject for incremental rebuilds and better dependency tracking than AddonBuilder. `/dayz-build-pbo` could grow a `--builder=addonbuilder|pboproject` flag, with auto-detect if PboProject is on PATH.

---

## C. Process and tooling

### C1. `/agents-lint` skill

`/agent-creator` validates one agent on demand. A bulk-lint skill that runs over `.claude/agents/**/*.md` and `.claude/skills/**/SKILL.md`:

- Frontmatter parses cleanly.
- 9-section template present in canonical order (for agents).
- No hardcoded user-specific paths (catches A1 regressions).
- Cross-references resolve (e.g. "refer to dayz-config-specialist" → that file exists).
- L2 reference line present in every DayZ agent.

Run as a pre-commit hook or `/sync-skills` post-step.

### C2. CI for the skill scripts

The Python skill scripts have implicit contracts (CLI args, exit codes, stdout shape). One `pytest` per skill running `--dry-run` + asserting on output keeps drift under control. Lightweight — `tests/test_skills_dryrun.py` calling each `*.py main()` with `--help` and a no-op flag is enough to catch import-time and arg-parse regressions.

### C3. Version-aware agents

DayZ patches break things. Agents currently assume a vague "current vanilla". Two improvements:

- A `/dayz-version` skill that reads the installed DayZ version (`P:\dz\` manifest or registry) and writes it to `.claude/local-memory/dayz-version.txt`.
- Every DayZ specialist's `## RULES` gets a "If your advice depends on a specific DayZ version, cite the minimum version" rule.

### C4. Diagnostic tracing for the agent layer itself

Add a `/agentic-z-trace` skill that prints what each specialist would do for a given user prompt, without actually running. Useful for debugging routing decisions when the unified `dayz-coder` agent picks the wrong lane.

---

## D. The Ultimate DayZ Modding Assistant — what "ultimate" looks like

Three properties make the assistant ultimate, in priority order:

### D1. Single front door, internal lane routing

The user types one thing — "I want to retexture the assault vest red and have it spawn in mil tier loot" — and the assistant:

1. Recognizes this spans **config** (hidden selections), **asset** (texture path + naming), **types.xml** (CE entry), and optionally **script** (if dynamic behavior).
2. Drives each lane in sequence with the right specialist's voice/rules in mind.
3. Hands the user one cohesive output: edited `config.cpp`, packed `.paa`, types.xml node, and a `/dayz-build-pbo && /dayz-launch-test` chain to test it.

That's what the unified `dayz-coder.md` in `.claude/agents/` does — see [`02-unified-agent.md`](02-unified-agent.md) for the design rationale.

### D2. Preserve specialist discipline

Two identities are load-bearing and must survive consolidation:

- **Debugger doesn't write code.** Diagnose → hand off. If the unified agent fixes when it should diagnose, you lose the trail of what was wrong.
- **Reviewer doesn't modify.** Audit → punch list. If the unified agent edits during review, you lose the ability to inspect-without-mutating.

The unified agent's rules section calls these out explicitly so when the user enters "audit" mode or "debug" mode, the constraint sticks.

### D3. Closed-loop iteration

The current loop is open: edit → build → launch → manually inspect → edit. Closing the loop:

- B2 (post-launch sanity tail) feeds back into the conversation.
- B6 (RPT triage) feeds the debugger automatically.
- B5 (BattlEye sync) feeds the server-admin lane automatically.
- A "watch mode" skill (`/dayz-watch`) that re-runs preflight + rebuild + launch on `workspace/<ModName>/` file changes — the modding equivalent of `cargo watch`.

With the loop closed, the assistant goes from "answers questions about your mod" to "ships your mod with you."

---

## E. Roadmap (suggested order)

A 30-day plan, batched by leverage and effort.

| Week | Focus | Deliverables |
|---|---|---|
| **Week 1** | Fix the bugs, ship the unified agent. | A1 (path fix sweep), A2 (L2 RAG correction), drop in `dayz-coder.md` (already in your `.claude/agents/`). |
| **Week 2** | Close the iteration loop. | B1 (`--rebuild` flag), B2 (post-launch tail), B6 (`/dayz-rpt-triage`). |
| **Week 3** | Server-side discipline. | B3 (`/dayz-types-validate`), B5 (`/dayz-battleye-sync`), C3 (version awareness). |
| **Week 4** | Publishing + new domain coverage. | B4 (`/dayz-publish-workshop`), B8 (`/dayz-new-vehicle`), B9 (sound/animation specialist). |

Items B7 (CUI), B10 (PboProject), C1/C2 (lint + CI), C4 (trace), D3 (watch) are nice-to-haves. Slot them in as concrete needs surface from real mod work.

---

## F. What NOT to change

A few things in the cloned template look "improvable" but are already correct:

- **Three-CLI doc files (`CLAUDE.md` / `AGENTS.md` / `GEMINI.md`) as plain copies.** Tempting to symlink. Don't — each CLI auto-loads its own filename, and SYMLINKs add cross-platform fragility. The "edit all three together" rule is fine.
- **Strict 9-section agent template.** Tempting to relax for "small" agents. Don't — `/agent-creator` and `/agents-lint` (when added) rely on the structure; relaxing it everywhere means giving up validation everywhere.
- **Preflight gate on every DayZ skill.** Tempting to skip on offline-only skills like `/dayz-new-mod`. Don't — the discipline catches a dismounted drive at the first action of a session, not the third. The L2 doc explicitly defends this.
- **Match-on-scaffold rule in `/dayz-clean-workspace`.** Tempting to make it "rmrf everything DayZ-shaped." Don't — that nukes subscribed Workshop mods. The current rule is conservative on purpose.
