# The Unified `dayz-coder` Agent

## Where it lives

The agent file is `dayz-coder.md` in this folder.

Drop it into `.claude/agents/` to wire it in (the session can't write into `.claude/` directly):

```cmd
copy output\dayz-coder-extract\dayz-coder.md .claude\agents\dayz-coder.md
```

After moving it, run `/sync-skills` (or `python .claude\skills\sync-skills\sync.py`) so Codex CLI and Gemini CLI also pick it up.

## Design rationale

The cloned template ships 11 specialist agents. Each is sharp on its own lane but the user is left as dispatcher: "this is a script + config + asset thing, let me invoke three agents in sequence." Most real DayZ tasks span 2-4 lanes. The unified agent absorbs every specialist's strongest rules into one front door and routes internally.

### What it preserves

- **Lane-specific rules** — every specialist's load-bearing rules (EnScript style, CfgPatches discipline, texture suffixes, LOD ordering, `modded class Colors` no-op trap, types.xml validity) live in the unified `## RULES` and `## CAPABILITIES` sections.
- **Read-only modes** — debug mode (diagnose, don't fix) and audit mode (flag and route, don't modify) are explicit modes the agent enters from request-language cues. The original debugger and reviewer agents had these as their entire identity; the unified agent keeps them as switchable constraints.
- **Lifecycle drive** — the agent runs the existing slash-command skills (`/dayz-preflight`, `/dayz-new-mod`, `/dayz-build-pbo`, `/dayz-launch-test`) rather than re-implementing their work. Skills are the unit of automation; the agent is the orchestrator.
- **Vanilla recall via the `dayz-rag` MCP** — `search_dayz_source` with the right `file_type` scope, `get_dayz_file` for follow-up. The agent knows which file type maps to which lane.

### What it adds

- **Internal lane-routing decision table** — explicit mapping from request keywords to primary lane and cross-lane checks. Multi-lane requests get a sequence (preflight → config → script → asset → object-builder → server → build → launch).
- **Self-verification step** — before output, the agent walks a checklist of lane-specific traps (modded-class inheritance clause, ref placement, hidden-selection symmetry, XML well-formedness). Catches the most common defects before the user hits them.
- **Closed-loop process** — the `## PROCESS` section runs the user from idea to running mod in 7 steps, with explicit halt-on-fail at preflight.
- **Fixed memory path** — the original specialists hardcoded `G:\AI-Templates\.claude\agent-memory\<name>\` (a path that doesn't exist on this clone). The unified agent uses repo-relative resolution. See [`01-upgrades.md`](01-upgrades.md) §A1 for the same fix to apply to the original 11.

### What it deliberately doesn't do

- **Doesn't replace the specialists.** The 11 individual agents stay useful when a task is clearly single-lane and the user wants the specialist's voice unfiltered. The unified agent is the default front door; the specialists are still available.
- **Doesn't re-implement skills.** It drives them. If a skill needs to grow (e.g., `/dayz-launch-test --rebuild` from upgrade B1), update the skill, not the agent.
- **Doesn't store state across calls.** Per-mod context lives in the agent's persistent memory under `.claude/agent-memory/dayz-coder/`. The agent reads it on each invocation; the user doesn't have to re-explain.

## When to use vs. when to defer to a specialist

| Situation | Agent to invoke |
|---|---|
| New feature, multi-lane, lifecycle work | `dayz-coder` |
| Pre-release audit | `dayz-coder` (audit mode) |
| Log triage | `dayz-coder` (debug mode) |
| Pure Object Builder geometry work, no other lanes | `dayz-object-builder` (specialist's voice is sharper here) |
| Pure Workbench plugin development | `dayz-workbench-specialist` (separate domain — editor-time tooling) |
| Generating a new agent definition | `agent-creator` |
| Wiki / docs sync | `docs-wiki-sync` |

For everything else: `dayz-coder`.

## How to verify it's wired in

1. After copying to `.claude/agents/dayz-coder.md`, restart your Claude Code / Codex / Gemini session.
2. List available agents — `dayz-coder` should appear in red with model `opus`.
3. Try the example from the description frontmatter: "Add a custom medkit that heals over 30 seconds, give it 2% spawn rate at military, and bake the icon in." The agent should respond by recognizing four lanes (config / script / asset / server) and proposing the preflight + scaffold + author + types-edit + build + launch chain.
4. Try the audit example: "Look over `workspace/<some folder>/` and tell me what's broken before I publish." It should refuse to modify any file and produce a routed punch list.

If any of these fail, run `/agent-creator` against `.claude/agents/dayz-coder.md` to validate the 9-section template and frontmatter.
