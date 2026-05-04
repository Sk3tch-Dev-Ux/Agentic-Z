#!/usr/bin/env python3
"""deploy.py - install Phase D6 (polish + public release).

Adds:
  - desktop/src/components/OnboardingWizard.tsx  (new)
  - desktop/src/components/AboutDialog.tsx       (new)
  - desktop/src/components/StatusBar.tsx         (replace — adds About button)
  - desktop/src/App.tsx                          (replace — wires onboarding + about)
  - desktop/README.md                            (replace — public-facing)
  - desktop/docs/INSTALL.md                      (new)
  - desktop/docs/BUILDING.md                     (new)
  - desktop/docs/CONTRIBUTING.md                 (new)
  - desktop/docs/ARCHITECTURE.md                 (new)
  - .github/workflows/desktop-release.yml        (new — CI for release builds)

After install:
  cd desktop
  pnpm tauri:dev          # restart the dev session
  # First run: the onboarding wizard auto-shows if no Anthropic key is set.

To cut a release:
  git tag desktop-v1.0.0 && git push origin desktop-v1.0.0
  # GitHub Actions builds the .exe and creates a draft Release.
"""
from __future__ import annotations
import argparse, shutil, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def deploy_dir(src: Path, dst: Path, label: str, dry_run: bool) -> int:
    print(label)
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
        HERE / "desktop", REPO / "desktop",
        "1. Desktop additions (onboarding, about, public docs)",
        args.dry_run,
    )
    print()
    total += deploy_dir(
        HERE / ".github", REPO / ".github",
        "2. CI workflow for release builds",
        args.dry_run,
    )

    print()
    print(f"Done. {total} file change(s) {'would be ' if args.dry_run else ''}made.")
    if total and not args.dry_run:
        print()
        print("Next steps:")
        print("  cd desktop && pnpm tauri:dev")
        print()
        print("To cut a release once you're ready:")
        print("  git add -A && git commit -m 'desktop v0.6.0'")
        print("  git tag desktop-v0.6.0")
        print("  git push origin desktop-v0.6.0")
        print("  # GitHub Actions builds .exe + creates draft Release")
    return 0


if __name__ == "__main__":
    sys.exit(main())
