---
name: agentic-z-promote-skill
description: Scan agent memories, dayz-director postmortems, and the dayz-watch event log for recurring patterns. Cluster by topic and propose new skills (SKILL.md draft + skeleton script) for the top clusters. Always writes to `output/skill-proposals/` for human review — never auto-promotes into `.claude/skills/`. The toolkit gets sharper from your own modding patterns over time.
---

# /agentic-z-promote-skill

The closing piece of Agentic-Z Live Mode (Phase 5). After enough mods ship through `dayz-director`, recurring patterns surface in the agent memories and the runtime event log. This skill scans those sources, clusters by topic, and drafts new skill proposals for any pattern that's appeared often enough to warrant automation.

Always conservative: drafts go to `output/skill-proposals/<name>/` for you to review and flesh out. The skill never drops anything into `.claude/skills/` directly. Bad skills proliferate faster than good ones — every promotion gets a human eyeball.

Follow `.claude/skills/_shared/dayz-conventions.md`.

## Three input sources

| Source | What it contributes |
|---|---|
| `.claude/agent-memory/<agent>/*.md` with `type: feedback` frontmatter | User-noted lessons that worked — "use AddonBuilder, not PboProject for this project" type rules. |
| `.claude/agent-memory/dayz-director/runs/*.md` (Phase 4 postmortems) | Each postmortem's goal contributes one signal — repeated goal types reveal lifecycle work the user keeps invoking. |
| `.claude/local-memory/dayz-watch.log` (Phase 3 events) | Recurring `log_error` / `log_warning` patterns within the last 30 days suggest prophylactic skills (validators, linters). |

Each signal carries a topic key, source type, file path, and an excerpt. Clusters are formed by exact topic-key match.

## How clustering works

Topic keys come from:

- **For memories:** `name:` field in YAML frontmatter, or filename stem if frontmatter is absent. Boilerplate prefixes like `feedback_` are stripped, lowercase, non-alphanumerics collapsed to `_`.
- **For postmortems:** the `**Goal:**` line, normalized the same way.
- **For watch errors:** `<lane>_<pattern>` (e.g. `config_missing_class_declaration`).

Same topic key → same cluster. Cluster count = number of signals. Default threshold for proposing a skill is 2 — raise it via `--threshold N` for a higher bar.

## How to run

```cmd
:: Default — propose skills for clusters with 2+ signals
python .claude\skills\agentic-z-promote-skill\promote.py

:: Just count, don't write proposals
python .claude\skills\agentic-z-promote-skill\promote.py --status

:: Higher bar (more conservative)
python .claude\skills\agentic-z-promote-skill\promote.py --threshold 5

:: Preview what would be written
python .claude\skills\agentic-z-promote-skill\promote.py --dry-run

:: Cap proposals at top-N (default 10)
python .claude\skills\agentic-z-promote-skill\promote.py --top 5
```

## What gets written per proposal

A folder at `output/skill-proposals/<topic-slug>/` containing:

- **`SKILL.md`** — auto-generated frontmatter + body. Lists every signal that drove the proposal (file path + excerpt). Has placeholders for "What it should do" that the user fills in. Includes a promotion checklist.
- **`<slug>.py`** — bare skeleton script. Resolves the repo root, parses `--dry-run`, prints a TODO. The user replaces `main()` with real logic.

The SKILL.md is overwritten on each run (always reflects the latest signals). The skeleton .py is preserved if it differs from the bare template — once you start editing it, the scanner won't clobber your work.

## Idempotent re-runs

Safe to run after every modding session. Repeat runs:

- Update existing proposals' signal lists with any new memories that appeared.
- Add new proposals for clusters that crossed the threshold.
- Never delete proposals (even if a cluster's count drops below threshold — the user may already be working on it).

## Promoting a proposal into a real skill

Once you've reviewed a draft and want to ship it:

1. Edit `output/skill-proposals/<slug>/SKILL.md` — replace the `What it should do` TODOs with the actual specification.
2. Edit `output/skill-proposals/<slug>/<slug>.py` — replace the stub with real logic.
3. Copy the folder into `.claude/skills/<slug>/`.
4. Run `python .claude\skills\sync-skills\sync.py` so all three CLIs see the new skill.
5. Optionally update relevant agents' descriptions to mention the new skill if it lives in their lane.

The proposal in `output/skill-proposals/` is now redundant; you can delete it or keep it as a record.

## What gets skipped

- `MEMORY.md` index files (they're indexes, not memories).
- Memories without `type: feedback` frontmatter (user/project/reference memories don't contribute signals — they're context, not patterns).
- Watch events older than 30 days (stale).
- Watch events that aren't `log_error` or `log_warning` (build failures and reindex events don't suggest new skills).

## Do not

- Don't bypass review and copy proposals straight into `.claude/skills/`. The human-eyeball requirement is load-bearing.
- Don't lower the threshold below 2 unless you're auditing — single-signal clusters are noise.
- Don't run this in CI. It's a manual review step; running it automatically defeats the conservative-by-design property.
