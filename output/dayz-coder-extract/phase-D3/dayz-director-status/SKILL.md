---
name: dayz-director-status
description: Write/update the dayz-director live status JSON. The desktop app's sidecar tails the resulting file via SSE and renders a state-machine visualizer that updates in real time. The director invokes this skill on every state transition, subagent dispatch, file change, and skill invocation.
---

# /dayz-director-status

Internal helper for the `dayz-director` agent. Writes structured updates to `.claude/local-memory/dayz-director-status.json` so the desktop app can render the director's progress live.

This skill is rarely invoked directly by the user; the director agent calls it from inside its state machine loop. Power users may use `--status` to inspect the current run, or `--reset` to clear a stale state file.

Follow `.claude/skills/_shared/dayz-conventions.md`.

## Why a separate skill instead of the agent writing JSON itself

The director agent runs inside a CLI session (Claude Code / Codex / Gemini). It has the Write tool, but every Write is a complete file rewrite. Routing all status updates through this skill gives:

- **Atomic writes** — write to `.tmp` then `os.replace()` so the desktop app never reads a half-written file.
- **Schema enforcement** — subcommands constrain the update shape; the agent can't accidentally produce malformed JSON.
- **Single source of truth** — every state transition produces an entry in `transitions[]` with a real timestamp, not a self-reported one.
- **No Anthropic API tokens spent on JSON serialization** — the agent says `python write.py transition --from BUILD --to LAUNCH --notes "OK"` instead of regenerating a 200-line JSON blob.

## How the agent uses it

The dayz-director agent's `## PROCESS` section calls this on every transition:

```cmd
python .claude\skills\dayz-director-status\write.py start --goal "ship MyMod" --mod MyMod
python .claude\skills\dayz-director-status\write.py transition --from IDLE --to PREFLIGHT
python .claude\skills\dayz-director-status\write.py skill --name /dayz-preflight --exit 0 --elapsed 0.4
python .claude\skills\dayz-director-status\write.py transition --from PREFLIGHT --to AUDIT
python .claude\skills\dayz-director-status\write.py subagent --agent dayz-coder --mode audit \
       --digest "12 findings: 3 critical, 2 nit, 7 ok"
python .claude\skills\dayz-director-status\write.py file-changed --path workspace/MyMod/config.cpp
python .claude\skills\dayz-director-status\write.py done
```

## Subcommands

| Command | Purpose |
|---|---|
| `start --goal X --mod Y` | Begin a new run. Replaces any existing status. |
| `transition --from A --to B [--notes ...]` | Append a transition; update `current_state`. |
| `subagent --agent X --mode Y [--digest ...]` | Record a subagent dispatch. |
| `file-changed --path X` | Append to `files_changed` (deduped). |
| `skill --name X --exit N --elapsed F` | Record a skill invocation result. |
| `halt --reason X` | Mark run as halted (cap tripped, user interrupt, etc.). |
| `done` | Mark run as completed successfully. |
| `status` | Print current status JSON. |
| `reset` | Clear the status file (use between sessions). |

## Output schema

```json
{
  "run_id": "2026-05-04T15-32-08",
  "goal": "ship MyMod",
  "mod": "MyMod",
  "status": "running",
  "current_state": "BUILD",
  "transitions": [
    {"from": "IDLE", "to": "PREFLIGHT", "ts": 1735844000.5, "notes": ""}
  ],
  "subagent_calls": [
    {"ts": 1735844010.2, "agent": "dayz-coder", "mode": "audit", "digest": "..."}
  ],
  "files_changed": ["workspace/MyMod/config.cpp"],
  "skill_invocations": [
    {"ts": 1735844050.1, "skill": "/dayz-build-pbo", "exit": 0, "elapsed": 8.3}
  ],
  "halt_reason": null,
  "started_at": 1735844000.0,
  "updated_at": 1735844060.5
}
```

## Read side

The desktop app's sidecar exposes an SSE endpoint `/api/events/director` that tails this file. Each write triggers an event with the full JSON; the frontend's `DirectorPanel` re-renders the state diagram and updates the transition log. Postmortem markdown files at `.claude/agent-memory/dayz-director/runs/<ts>.md` are the long-term archive (written by the agent at the end of each run).

## Do not

- Don't bypass this skill and write the JSON directly from the agent. Atomicity matters; the desktop app polls fast enough to catch half-written files otherwise.
- Don't run two directors at once — there's one status file. The desktop app surfaces this as "director already running"; trying to start a second concurrent run will overwrite the first's status.
- Don't manually edit the status file. It's regenerated on every transition. To intervene, use `reset` and start over with `start`.
