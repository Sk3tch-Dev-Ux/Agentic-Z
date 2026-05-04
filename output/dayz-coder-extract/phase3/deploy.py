#!/usr/bin/env python3
"""
deploy.py — install Phase 3 (log tail + error routing) into the Agentic-Z repo.

Three things happen, all idempotent:

1. Replace `.claude/skills/dayz-watch/watch.py` and `SKILL.md` with the Phase 3
   versions (strict superset of Phase 2 — adds `--with-logs` flag and tail loop).
2. Add `.claude/skills/dayz-watch/log_tail.py` — the new module that classifies
   diag log lines.
3. Patch `.claude/agents/dayz-coder.md` to add a "READ RECENT EVENTS" rule so
   the agent ingests `.claude/local-memory/dayz-watch.log` at the start of
   every turn.

Pass --dry-run to preview without writing.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


SKILL_SRC = HERE / "dayz-watch"
SKILL_DST = REPO / ".claude" / "skills" / "dayz-watch"


def deploy_skill(dry_run: bool) -> int:
    print("1+2. Skill folder (watch.py update + log_tail.py addition)")
    print("-" * 60)
    if not SKILL_SRC.exists():
        print(f"  [FAIL] source missing: {SKILL_SRC}")
        return 0
    if not (REPO / ".claude" / "skills").exists():
        print(f"  [FAIL] {REPO / '.claude' / 'skills'} not found - wrong repo?")
        return 0

    changed = 0
    for src_file in SKILL_SRC.rglob("*"):
        if src_file.is_dir():
            continue
        if "__pycache__" in src_file.parts:
            continue
        if src_file.suffix in {".pyc", ".pyo"}:
            continue
        rel = src_file.relative_to(SKILL_SRC)
        dst = SKILL_DST / rel
        if dst.exists() and dst.read_bytes() == src_file.read_bytes():
            print(f"  [OK ] {dst.relative_to(REPO)} (already current)")
            continue
        action = "DRY" if dry_run else "WRITE"
        existed = "(replace)" if dst.exists() else "(new)"
        print(f"  [{action}] {dst.relative_to(REPO)} {existed}")
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst)
        changed += 1
    return changed


CODER_PATH = REPO / ".claude" / "agents" / "dayz-coder.md"

CODER_RULE_OLD = "## RULES"
CODER_RULE_NEW = """## RULES

- **Read recent watcher events at the start of every turn.** If `.claude/local-memory/dayz-watch.log` exists, scan the last 30 minutes for `log_error`, `log_warning`, `build_failed`, and `backoff_triggered` events. Treat them as the user's actual current state - even if they didn't mention it explicitly. Lead your response with a short "RECENT EVENTS" section listing severity, lane, pattern, and a one-line excerpt for each (max 5). Then proceed with whatever they asked. If the events suggest the user's question and the recent error are related, say so."""


def deploy_coder_patch(dry_run: bool) -> int:
    print()
    print("3. dayz-coder.md patch (read recent watcher events at turn start)")
    print("-" * 60)
    if not CODER_PATH.exists():
        print(f"  [SKIP] {CODER_PATH.relative_to(REPO)} not present (skipping)")
        return 0

    text = CODER_PATH.read_text(encoding="utf-8")

    if "Read recent watcher events at the start of every turn" in text:
        print(f"  [OK ] dayz-coder.md (already patched)")
        return 0

    if CODER_RULE_OLD not in text:
        print(f"  [WARN] anchor '## RULES' not found in {CODER_PATH.relative_to(REPO)} - skipped")
        return 0

    new_text = text.replace(CODER_RULE_OLD, CODER_RULE_NEW, 1)
    print(f"  [{'DRY' if dry_run else 'PATCH'}] inserted READ-EVENTS rule at top of ## RULES")
    if not dry_run:
        CODER_PATH.write_text(new_text, encoding="utf-8")
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
    total += deploy_skill(args.dry_run)
    total += deploy_coder_patch(args.dry_run)

    print()
    print(f"Done. {total} file change(s) {'would be ' if args.dry_run else ''}made.")
    if total and not args.dry_run:
        print()
        print("Next steps:")
        print("  1. python .claude\\skills\\sync-skills\\sync.py")
        print("  2. python .claude\\skills\\dayz-watch\\watch.py MyMod --with-logs")
        print("  3. Restart your agent CLI session.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
