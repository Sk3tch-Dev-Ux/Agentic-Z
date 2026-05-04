#!/usr/bin/env python3
"""
deploy.py - install Phase 4 (dayz-director agent) into the Agentic-Z repo.

Two things happen, idempotently:

1. Copy `dayz-director.md` into `.claude/agents/`.
2. Create `.claude/agent-memory/dayz-director/runs/` so the director can write
   postmortems on first run without a path-not-found error.

No skill changes, no MCP patches. The director is a pure agent definition that
uses existing skills + dayz-coder via the Task / Agent tool.

Pass --dry-run to preview without writing.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


AGENT_SRC = HERE / "dayz-director.md"
AGENT_DST = REPO / ".claude" / "agents" / "dayz-director.md"
MEMORY_DIR = REPO / ".claude" / "agent-memory" / "dayz-director"
RUNS_DIR = MEMORY_DIR / "runs"


def deploy_agent(dry_run: bool) -> int:
    print("1. Agent definition")
    print("-" * 60)
    if not AGENT_SRC.exists():
        print(f"  [FAIL] source missing: {AGENT_SRC}")
        return 0
    if not (REPO / ".claude" / "agents").exists():
        print(f"  [FAIL] {REPO / '.claude' / 'agents'} not found - wrong repo?")
        return 0

    if AGENT_DST.exists() and AGENT_DST.read_bytes() == AGENT_SRC.read_bytes():
        print(f"  [OK ] {AGENT_DST.relative_to(REPO)} (already current)")
        return 0
    action = "DRY" if dry_run else "WRITE"
    existed = "(replace)" if AGENT_DST.exists() else "(new)"
    print(f"  [{action}] {AGENT_DST.relative_to(REPO)} {existed}")
    if not dry_run:
        AGENT_DST.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(AGENT_SRC, AGENT_DST)
    return 1


def deploy_memory_scaffolding(dry_run: bool) -> int:
    print()
    print("2. Memory scaffolding (postmortem dir)")
    print("-" * 60)
    if RUNS_DIR.exists():
        print(f"  [OK ] {RUNS_DIR.relative_to(REPO)} (already exists)")
        return 0
    action = "DRY" if dry_run else "MKDIR"
    print(f"  [{action}] {RUNS_DIR.relative_to(REPO)}")
    if not dry_run:
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
    # Seed an empty MEMORY.md if neither it nor the dir existed
    memory_md = MEMORY_DIR / "MEMORY.md"
    if not memory_md.exists():
        action = "DRY" if dry_run else "WRITE"
        print(f"  [{action}] {memory_md.relative_to(REPO)}")
        if not dry_run:
            memory_md.write_text("# dayz-director memory\n\n", encoding="utf-8")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="preview without writing")
    args = parser.parse_args()

    print(f"Repo root: {REPO}")
    if args.dry_run:
        print("(dry run - no files will be written)")
    print()

    total = 0
    total += deploy_agent(args.dry_run)
    total += deploy_memory_scaffolding(args.dry_run)

    print()
    print(f"Done. {total} change(s) {'would be ' if args.dry_run else ''}made.")
    if total and not args.dry_run:
        print()
        print("Next steps:")
        print("  1. Restart your agent CLI session so dayz-director shows up")
        print("     (it's a new agent in .claude/agents/, not a skill).")
        print("  2. Make sure /dayz-watch --with-logs is running in another terminal")
        print("     so the director can read the structured event log during TAIL.")
        print("  3. Trigger the director by asking your CLI:")
        print('       "use dayz-director to ship MyMod"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
