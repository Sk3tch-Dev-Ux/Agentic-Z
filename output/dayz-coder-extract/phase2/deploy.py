#!/usr/bin/env python3
"""
deploy.py — install Phase 2 (/dayz-watch) into the Agentic-Z repo.

One thing happens, idempotently:
  - Copy the new skill folder into `.claude/skills/dayz-watch/`.

No MCP server patch needed — the watcher is a standalone CLI tool that calls
existing skill scripts via subprocess.

Usage (from the repo root):
    python output\\dayz-coder-extract\\phase2\\deploy.py
    python output\\dayz-coder-extract\\phase2\\deploy.py --dry-run
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
    print("1. Skill folder")
    print("-" * 60)
    if not SKILL_SRC.exists():
        print(f"  [FAIL] source missing: {SKILL_SRC}")
        return 0
    if not (REPO / ".claude" / "skills").exists():
        print(f"  [FAIL] {REPO / '.claude' / 'skills'} not found — wrong repo?")
        return 0

    changed = 0
    for src_file in SKILL_SRC.rglob("*"):
        if src_file.is_dir():
            continue
        rel = src_file.relative_to(SKILL_SRC)
        dst = SKILL_DST / rel
        if dst.exists() and dst.read_bytes() == src_file.read_bytes():
            print(f"  [OK ] {dst.relative_to(REPO)} (already current)")
            continue
        action = "DRY" if dry_run else "WRITE"
        print(f"  [{action}] {dst.relative_to(REPO)}")
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
        print("(dry run — no files will be written)")
    print()

    total = deploy_skill(args.dry_run)

    print()
    print(f"Done. {total} file change(s) {'would be ' if args.dry_run else ''}made.")
    if total and not args.dry_run:
        print()
        print("Next steps:")
        print("  1. python .claude\\skills\\sync-skills\\sync.py")
        print("     (registers /dayz-watch across Claude Code / Codex / Gemini)")
        print("  2. python .claude\\skills\\dayz-watch\\watch.py MyMod --once --dry-run")
        print("     (smoke-test the classifier on your active mod without running anything)")
        print("  3. python .claude\\skills\\dayz-watch\\watch.py MyMod")
        print("     (start the live loop — Ctrl+C to stop)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
