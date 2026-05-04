#!/usr/bin/env python3
"""deploy.py - install Phase D3 (director visualizer + status writer skill).

Two destinations:
  1. .claude/skills/dayz-director-status/  — new skill the director invokes
     to update the live status JSON.
  2. desktop/                              — sidecar additions, frontend
     additions, App route. No Tauri/Cargo changes.

Idempotent. Pass --dry-run to preview.
"""
from __future__ import annotations
import argparse, shutil, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def deploy_dir(src: Path, dst: Path, label: str, dry_run: bool) -> int:
    print(f"{label}")
    print("-" * 60)
    if not src.exists():
        print(f"  [FAIL] source missing: {src}")
        return 0
    changed = 0
    for src_file in src.rglob("*"):
        if src_file.is_dir(): continue
        skip_parts = {"__pycache__", "node_modules", "dist", "target"}
        if any(p in skip_parts for p in src_file.parts): continue
        if src_file.suffix in {".pyc", ".pyo"}: continue
        rel = src_file.relative_to(src)
        target = dst / rel
        if target.exists() and target.read_bytes() == src_file.read_bytes():
            print(f"  [OK ] {target.relative_to(REPO)} (already current)")
            continue
        action = "DRY" if dry_run else "WRITE"
        existed = "(replace)" if target.exists() else "(new)"
        print(f"  [{action}] {target.relative_to(REPO)} {existed}")
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, target)
        changed += 1
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"Repo root: {REPO}")
    if args.dry_run:
        print("(dry run - no files will be written)")
    print()

    total = 0
    total += deploy_dir(
        HERE / "dayz-director-status",
        REPO / ".claude" / "skills" / "dayz-director-status",
        "1. New skill: /dayz-director-status (.claude/skills/)",
        args.dry_run,
    )
    print()
    total += deploy_dir(
        HERE / "desktop",
        REPO / "desktop",
        "2. Desktop app additions (sidecar + frontend)",
        args.dry_run,
    )

    print()
    print(f"Done. {total} file change(s) {'would be ' if args.dry_run else ''}made.")
    if total and not args.dry_run:
        print()
        print("Next steps:")
        print("  python .claude\\skills\\sync-skills\\sync.py")
        print("  cd desktop && pnpm tauri:dev")
        print()
        print("To test the director visualizer with a synthetic run:")
        print("  python .claude\\skills\\dayz-director-status\\write.py start \\")
        print("    --goal 'ship MyMod' --mod MyMod")
        print("  python .claude\\skills\\dayz-director-status\\write.py transition \\")
        print("    --from IDLE --to PREFLIGHT")
        print("  ... watch the diagram light up live in the desktop app's /director page.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
