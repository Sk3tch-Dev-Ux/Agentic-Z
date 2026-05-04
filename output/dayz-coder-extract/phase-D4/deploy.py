#!/usr/bin/env python3
"""deploy.py - install Phase D4 (RAG search palette + Cmd+K) on top of D3.

Adds:
  - desktop/sidecar/rag.py        (new — search/file/manifests/open endpoints)
  - desktop/sidecar/main.py       (replace — mounts the rag router)
  - desktop/src/api/rag.ts        (new)
  - desktop/src/hooks/useHotkey.ts (new)
  - desktop/src/components/SearchPalette.tsx (new)
  - desktop/src/components/StatusBar.tsx     (replace — adds search button)
  - desktop/src/App.tsx           (replace — wires Cmd+K + palette)
  - desktop/src/pages/Dashboard.tsx (replace — RAG stat card live)

Idempotent. Pass --dry-run to preview.
"""
from __future__ import annotations
import argparse, shutil, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

DESKTOP_SRC = HERE / "desktop"
DESKTOP_DST = REPO / "desktop"


def deploy(dry_run: bool) -> int:
    print(f"Repo root: {REPO}")
    if dry_run:
        print("(dry run - no files will be written)")
    print()
    print("desktop/ patch (D3 -> D4)")
    print("-" * 60)

    if not DESKTOP_SRC.exists():
        print(f"  [FAIL] source missing: {DESKTOP_SRC}")
        return 0

    changed = 0
    for src_file in DESKTOP_SRC.rglob("*"):
        if src_file.is_dir(): continue
        skip_parts = {"__pycache__", "node_modules", "dist", "target"}
        if any(part in skip_parts for part in src_file.parts): continue
        if src_file.suffix in {".pyc", ".pyo"}: continue
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
        print("  pnpm tauri:dev          # restart the dev session")
        print()
        print("Then in the app: Ctrl+K → search 'modded class PlayerBase' →")
        print("                see vanilla + workspace hits with file:line preview.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
