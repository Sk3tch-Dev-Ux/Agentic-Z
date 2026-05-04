#!/usr/bin/env python3
"""deploy.py - install Phase D5 (skill proposal manager + Mod Creator + Anthropic API).

D5 = D6's API key handling brought forward + the proposal manager.

Adds:
  - desktop/sidecar/proposals.py        (new)
  - desktop/sidecar/anthropic_api.py    (new)
  - desktop/sidecar/main.py             (replace — mounts the new routers)
  - desktop/sidecar/requirements.txt    (replace — adds anthropic)
  - desktop/src/api/proposals.ts        (new)
  - desktop/src/api/settings.ts         (new)
  - desktop/src/api/modCreator.ts       (new — SSE consumer)
  - desktop/src/components/ModCreatorDialog.tsx (new)
  - desktop/src/components/NewModDialog.tsx     (replace — adds Pitch tab)
  - desktop/src/components/StatusBar.tsx        (replace — settings + proposals icons)
  - desktop/src/pages/Dashboard.tsx     (replace — Proposals card live, hero button)
  - desktop/src/pages/SettingsPage.tsx  (new)
  - desktop/src/pages/ProposalsPage.tsx (new)
  - desktop/src/App.tsx                 (replace — adds /settings, /proposals routes)

After install:
  cd desktop
  pip install -r sidecar\\requirements.txt    # picks up `anthropic` package
  pnpm tauri:dev
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
    print("desktop/ patch (D4 -> D5 + Mod Creator)")
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
        print("  pip install -r sidecar/requirements.txt    # adds 'anthropic'")
        print("  pnpm tauri:dev")
        print()
        print("Then:")
        print("  1. Settings → paste your Anthropic API key → Test")
        print("  2. Dashboard → 'New mod from pitch' → describe an idea → watch Claude generate")
        print("  3. Open the new mod → Build → Launch")
    return 0


if __name__ == "__main__":
    sys.exit(main())
