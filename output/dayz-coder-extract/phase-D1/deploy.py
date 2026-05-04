#!/usr/bin/env python3
"""deploy.py - install Phase D1 (desktop scaffold) into the Agentic-Z repo."""
from __future__ import annotations
import argparse, shutil, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# HERE = output/dayz-coder-extract/phase-D1/
# parents[0] = dayz-coder-extract/, [1] = output/, [2] = repo root.
REPO = HERE.parents[2]

DESKTOP_SRC = HERE / "desktop"
DESKTOP_DST = REPO / "desktop"


def deploy(dry_run: bool) -> int:
    print(f"Repo root: {REPO}")
    if dry_run:
        print("(dry run - no files will be written)")
    print()
    print("desktop/ scaffold")
    print("-" * 60)

    if not DESKTOP_SRC.exists():
        print(f"  [FAIL] source missing: {DESKTOP_SRC}")
        return 0

    changed = 0
    for src_file in DESKTOP_SRC.rglob("*"):
        if src_file.is_dir():
            continue
        skip_parts = {"__pycache__", "node_modules", "dist", "target"}
        if any(part in skip_parts for part in src_file.parts):
            continue
        if src_file.suffix in {".pyc", ".pyo"}:
            continue
        rel = src_file.relative_to(DESKTOP_SRC)
        dst = DESKTOP_DST / rel
        if dst.exists() and dst.read_bytes() == src_file.read_bytes():
            print(f"  [OK ] desktop/{rel.as_posix()} (already current)")
            continue
        action = "DRY" if dry_run else "WRITE"
        existed = "(replace)" if dst.exists() else "(new)"
        print(f"  [{action}] desktop/{rel.as_posix()} {existed}")
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst)
        changed += 1
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="preview without writing")
    args = parser.parse_args()
    total = deploy(args.dry_run)
    print()
    print(f"Done. {total} file change(s) {'would be ' if args.dry_run else ''}made.")
    if total and not args.dry_run:
        print()
        print("Next steps:")
        print("  cd desktop")
        print("  pnpm install")
        print("  pip install -r sidecar/requirements.txt")
        print("  pnpm tauri:dev")
    return 0


if __name__ == "__main__":
    sys.exit(main())
