# Agentic-Z Live Mode — Design and Build Plan

The goal: turn Agentic-Z from a tool stack you operate into a continuous mod-shipping pipeline that operates *itself*. You stop being the dispatcher between edit, build, test, debug; the agents drive the inner loop and you supervise.

This doc is the architecture decision record + phased roadmap. Each phase is shippable on its own — you don't have to finish the whole thing to get value. Drop out at any phase and what you have still works.

---

## 1. The end state

```
                            ┌─────────────────────────────────┐
                            │   you (supervisor / goal-setter) │
                            └──────────────┬──────────────────┘
                                           │ "ship MyMod v1.0"
                                           ▼
                            ┌─────────────────────────────────┐
                            │  dayz-director (autonomous)     │
                            │   state: AUDIT → FIX → BUILD →  │
                            │          LAUNCH → TAIL → REPORT │
                            └──┬────────────┬───────────────┬─┘
                               │            │               │
                ┌──────────────▼─┐  ┌───────▼────────┐  ┌──▼──────────────┐
                │  dayz-coder    │  │  /dayz-watch   │  │  /dayz-rag-*    │
                │  (audit/fix/   │  │  (file watcher │  │  + workspace    │
                │   debug modes) │  │   + log tail)  │  │   RAG corpus    │
                └────────┬───────┘  └────────┬───────┘  └────────┬────────┘
                         │                   │                   │
                         │ writes/edits      │ events            │ search_dayz_source(
                         │                   │ errors            │   corpus="both")
                         ▼                   ▼                   ▼
                ┌─────────────────────────────────────────────────────────┐
                │   workspace/<ModName>/   +   P:\Mods\@<ModName>\        │
                │   workspace/_server/     +   diag client + diag server  │
                └─────────────────────────────────────────────────────────┘
```

You give the director a goal. The director consults the unified `dayz-coder` (which now knows your code thanks to workspace RAG), uses `/dayz-watch` to drive iteration, and converges on shipped. You watch — and step in when the director hits a decision it shouldn't auto-make.

---

## 2. The five phases

Each phase has: **effort** (rough), **deliverable** (what gets created), **standalone value** (why it's worth doing even if you stop here), and **dependencies** (what must come before).

### Phase 1 — Workspace RAG (smallest, highest immediate signal)

**Effort:** ~1 day.

**Deliverable:**
- New flag on `/dayz-rag-index`: `--workspace [<ModName>]`. Walks `workspace/<ModName>/` (or all mods when the name is omitted), chunks by file type the same way the vanilla indexer does, embeds via Voyage, writes to a separate LanceDB table named `workspace` (alongside the existing `vanilla` and `wiki` tables).
- `search_dayz_source` MCP tool gains a `corpus` parameter: `"vanilla"` (default, current behavior), `"workspace"`, `"wiki"`, `"both"`. Returns matched chunks tagged with corpus so the agent knows where the hit came from.
- `dayz-coder` agent's `## VANILLA DATA — SEARCH HERE FIRST` section is renamed to `## RAG CORPORA` and gains a one-line note that `corpus="workspace"` is available for "how does my mod do X" questions.
- Optional: `--watch` flag on the index command that re-embeds incrementally on file save (~3-second feedback). Phase 2 supersedes this; ship without it for now.

**Standalone value:** Massive. Right now the agent is brilliant about vanilla and clueless about your code. After this, "how is my MyMod_TacticalVest hidden-selection wired up?" becomes a 200ms RAG query with file:line citations. This compounds with the memory fix — the agent now has both committed memory of past decisions AND searchable knowledge of current code.

**Dependencies:** None. Voyage API key already set up.

**Risk / sharp edges:**
- Re-indexing on every commit would burn Voyage tokens. Mitigation: chunk-level content hash; only embed chunks whose hash changed. Implement on day one or you'll regret it.
- Workspace mods are small (~thousands of chunks) — full reindex is sub-minute. Incremental is a nice-to-have, not a blocker.

---

### Phase 2 — `/dayz-watch` (file watcher + smart rebuild)

**Effort:** ~2-3 days.

**Deliverable:**
- New skill `.claude/skills/dayz-watch/` with `watch.py` and `SKILL.md`.
- Python `watchdog` library (or polling fallback for OneDrive folders, where inotify-style events flake).
- Watches `workspace/<ModName>/` (and `workspace/_server/missions/<map>/` if the user opts in).
- Debounces events (default 500ms — adjustable).
- Classifies the changed file:

  | File pattern | Action |
  |---|---|
  | `*.c` (script) | No PBO rebuild needed. Engine reads via `-filePatching`. Just log "script changed; reconnect or restart server to pick up". |
  | `*.cpp`, `*.hpp`, `$PBOPREFIX$`, `*.layout`, anything in `data/` | Run `/dayz-build-pbo <ModName>` |
  | `*.png`, `*.tga` (paired with a `_co`/`_nohq`/`_smdi` suffix) | Run `/dayz-pack-texture` then `/dayz-build-pbo` |
  | `types.xml`, `events.xml`, `cfgspawnabletypes.xml` | No PBO. Log "server economy changed; restart server to apply". |
  | Anything in `.git/`, `node_modules/`, `__pycache__/` | Ignore. |

- Streams build output to stdout AND appends a structured JSON line per event to `.claude/local-memory/dayz-watch.log` so the agent can read recent events on its next turn.
- `--once` flag for one-shot evaluation (useful in tests).
- `--workspace-rag` flag to also kick off an incremental Phase 1 reindex on each change (cheap because of chunk-level hashing).

**Standalone value:** Even without the director, this collapses the inner loop. You save a `.c` file → the watcher logs "filePatching will pick this up". You save `config.cpp` → it builds. You save a new texture → it packs and builds. The "alt-tab to terminal, type `/dayz-build-pbo`" tax disappears.

**Dependencies:** Phase 1 nice-to-have for `--workspace-rag`, not required.

**Risk / sharp edges:**
- OneDrive's syncing creates phantom write events. Hard-test the debouncer against real OneDrive activity early — don't trust the first naive implementation.
- Editor "save atomic" patterns (write to tempfile, rename) trigger DELETE+CREATE not MODIFY. `watchdog` handles this, but verify.
- A bad config.cpp triggers a build loop. Add a "consecutive failure backoff" — after N failures, stop watching and wait for the user.

---

### Phase 3 — Log tail + error auto-routing

**Effort:** ~2-3 days.

**Deliverable:**
- Extend `/dayz-watch` with `--with-logs` mode.
- Spawns a tail thread for each of `workspace/_server/maps/<map>/profiles/server_console.log`, `*.RPT`, `script.log`, and `workspace/_server/!ClientDiagLogs/script.log`.
- Regex pass for known-bad patterns: `^ERROR `, `^EXCEPTION`, `^WARNING:.*Cannot find class`, BattlEye kicks (`Player .* kicked`), filter rejections, segfault signatures.
- On match, writes a structured event to `.claude/local-memory/dayz-watch.log` with `severity` + `file:line` + `excerpt` + `suggested_lane`.
- `dayz-coder` agent gets a new rule: at the start of every turn, read the last 30 minutes of `.claude/local-memory/dayz-watch.log` and prepend "RECENT EVENTS:" to its context. Tail of structured events keeps the agent grounded in what actually happened, not what the user remembers.
- Optional: `--auto-debug` flag on `/dayz-watch` that, on each new error event, dispatches a `dayz-coder` (debug mode) subagent to diagnose, writing the diagnosis back into the watch log. The user sees diagnoses appear without asking.

**Standalone value:** Errors stop falling through the cracks. You save a script → server reloads → script.log spits an error → 2 seconds later the agent has classified it. The first time you save buggy code and the agent says "your modded class still has the inheritance clause on line 12, that's why nothing's running" before you've even noticed the log line, the leverage is obvious.

**Dependencies:** Phase 2 (the watcher infrastructure).

**Risk / sharp edges:**
- Log rotation. RPT files get rotated by name. Re-resolve the latest file each tail-tick rather than holding an FD.
- False-positive errors (BI's vanilla logs are noisy). Allow the user to add patterns to `.claude/local-memory/dayz-watch-ignore.txt`.
- Privacy: don't auto-share log excerpts outside the local machine without consent. Voyage queries from `dayz-coder` are fine (they only see embedded query text), but don't ship log lines to any external service without opt-in.

---

### Phase 4 — `dayz-director` (the autonomous goal-pursuer)

**Effort:** ~1 week.

**Deliverable:**
- New agent `.claude/agents/dayz-director.md` (model: opus, color: gold).
- State machine driven by an explicit goal: `IDLE → AUDIT → FIX → REAUDIT → BUILD → LAUNCH → TAIL → REPORT → IDLE`.
- Triggered with a one-shot prompt: "Ship MyMod" or "Make MilitaryGear release-ready" or "Diagnose and fix the connection issue".
- At each state transition, emits a structured event ("entering BUILD", "found 3 critical issues") so the supervisor (you) can interrupt. Hard caps:

  | Cap | Default | Why |
  |---|---|---|
  | Max state-machine turns per goal | 20 | Prevent runaway loops |
  | Max consecutive build failures | 3 | Same as Phase 2 backoff |
  | Max files changed per FIX state | 5 | Forces the director to ask before wide refactors |
  | Destructive ops require confirmation | always | `rm`, `git reset --hard`, anything outside `workspace/<ModName>/` |

- The director invokes `dayz-coder` as a subagent for each state's actual work (audit-mode subagent for AUDIT, build-mode for FIX, debug-mode for the post-launch TAIL analysis).
- All state transitions logged to `.claude/agent-memory/dayz-director/runs/<timestamp>.md` for postmortem.

**Standalone value:** The "I'm going to ship this in one focused hour" workflow becomes "give the director the goal, refill coffee, supervise". The director catches its own mistakes by re-auditing after fixes.

**Dependencies:** Phases 1+2+3 ideally, but technically only depends on `dayz-coder` being installed. Without Phases 2/3, the director just calls skills explicitly instead of reacting to file events.

**Risk / sharp edges:**
- "Autonomous" agents are great until they aren't. The hard caps above are not optional — ship them with the agent. The director MUST stop and ask the user when caps trip.
- The director is OPUS — token costs add up over a long run. Add a `--max-cost` flag that stops when crossed.
- Don't make the director self-modifying. It can read agent memory; it can't edit `.claude/agents/` or `.claude/skills/`. That's the user's job (or `agent-creator`'s with explicit user invocation).

---

### Phase 5 — Memory-driven skill promotion

**Effort:** ~1 day.

**Deliverable:**
- After each successful auto-fix, `dayz-coder` writes a feedback memory: rule + why + how-to-apply.
- New meta-skill `/agentic-z-promote-skill` that:
  - Scans `.claude/agent-memory/dayz-coder/` for feedback memories.
  - Clusters by topic (e.g. multiple "missed CfgPatches entry → mod doesn't load" memories).
  - Proposes a new `SKILL.md` draft for clusters above a threshold (default: 3 occurrences).
  - User reviews, accepts, runs `/sync-skills`.
- The toolkit gets sharper from your own modding patterns over time. Skills that started as "lessons learned" become reusable automation.

**Standalone value:** This is the long-tail compounding interest. Each mod you ship leaves the toolkit measurably smarter. After 6 months, the skill set encodes a substantial chunk of your modding playbook automatically.

**Dependencies:** Phase 4 (or just heavy use of `dayz-coder` which writes feedback memories regardless).

**Risk / sharp edges:**
- Don't auto-promote skills. Always require user review — bad skills proliferate fast otherwise.
- The clustering needs to be conservative. Three "different reasons CfgPatches failed" don't necessarily share a fix.

---

## 3. Recommended start order

Phase 1 first. Always. Reasons:

1. **Smallest** (~1 day). You'll feel the ROI by tomorrow.
2. **No new infrastructure.** It's just an extra flag on an existing skill.
3. **Compounds with everything else.** The director (Phase 4) is dramatically smarter when it can search your code, not just vanilla. The auto-debug routing in Phase 3 can cite your code in diagnoses. Phase 1 is the substrate.
4. **De-risks the architecture.** If Voyage cost or LanceDB scaling is a problem at workspace size, you find out cheap.

Then Phase 2 → Phase 3 → Phase 4 → Phase 5 in order. Each adds a layer of autonomy on top of the previous.

If you want to skip ahead — Phase 4 (director) without Phases 2/3 (watcher/logs) is still useful but feels manual. Phase 4 + Phase 1 = a smart auditor. Phase 4 + Phases 1-3 = the moonshot.

---

## 4. What this is NOT

To keep scope honest:

- **Not a CI replacement.** Live Mode runs while you're at the keyboard. CI is still on you for cross-machine validation, multi-platform builds, etc.
- **Not a mod marketplace.** Workshop publishing (upgrade B4 in `01-upgrades.md`) is its own track and stays separate.
- **Not a substitute for testing on a real server.** Local diag is the inner loop. Public-server validation is still a manual handoff.
- **Not multi-user.** One developer per Live Mode session. Concurrent edits would race the watcher.
- **Not self-modifying.** The director can call `dayz-coder` to edit your mod source, but cannot edit agents/skills/conventions. You always own those changes.

---

## 5. What this means for the existing files

Live Mode is additive — nothing in the current Agentic-Z layout has to move or break. Touchpoints:

- `dayz-coder` agent gets a new sub-section about `corpus` parameter (Phase 1) and a new rule about reading the watch log (Phase 3).
- `/dayz-rag-index` gains the `--workspace` flag (Phase 1).
- New folders: `.claude/skills/dayz-watch/`, `.claude/agents/dayz-director.md`, `.claude/skills/agentic-z-promote-skill/`.
- New gitignored runtime files: `.claude/local-memory/dayz-watch.log`, `.claude/agent-memory/dayz-director/runs/`.

L1 / L2 conventions don't change. The "preflight first" rule still gates everything; the watcher gates on preflight at startup, not on every event.

---

## 6. Effort summary

| Phase | Effort | Cumulative |
|---|---|---|
| 1. Workspace RAG | 1 day | 1 day |
| 2. /dayz-watch | 2-3 days | 3-4 days |
| 3. Log tail + auto-routing | 2-3 days | 5-7 days |
| 4. dayz-director | 1 week | 12-14 days |
| 5. Skill promotion | 1 day | 13-15 days |

About **two-and-a-half weeks** of focused build to land all five. Three days to land the first two and start feeling the loop close.
