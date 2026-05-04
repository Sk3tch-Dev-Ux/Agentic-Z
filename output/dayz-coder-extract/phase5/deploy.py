#!/usr/bin/env python3
"""
deploy.py - install Phase 5 (skill promotion) into the Agentic-Z repo.

One thing happens, idempotently:
  - Copy the new skill folder into `.claude/skills/agentic-z-promote-skill/`.

No agent patches, no MCP changes. The promoter is a pure scanner that reads
existing memories + the watch event log and writes proposals to
`output/skill-proposals/`.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

SKILL_SRC = HERE / "agentic-z-promote-skill"
SKILL_DST = REPO / ".claude" / "skills" / "agentic-z-promote-skill"


def deploy_skill(dry_run: bool) -> int:
    print("1. Skill folder")
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="preview without writing")
    args = parser.parse_args()

    print(f"Repo root: {REPO}")
    if args.dry_run:
        print("(dry run - no files will be written)")
    print()

    total = deploy_skill(args.dry_run)

    print()
    print(f"Done. {total} file change(s) {'would be ' if args.dry_run else ''}made.")
    if total and not args.dry_run:
        print()
        print("Next steps:")
        print("  1. python .claude\\skills\\sync-skills\\sync.py")
        print("     (registers the new skill across CLIs)")
        print("  2. python .claude\\skills\\agentic-z-promote-skill\\promote.py --status")
        print("     (count current clusters; nothing to propose yet on a fresh clone)")
        print("  3. After you've shipped a few mods through dayz-director, re-run")
        print("     without --status to see proposed skills.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
