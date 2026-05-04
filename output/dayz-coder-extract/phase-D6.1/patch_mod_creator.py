#!/usr/bin/env python3
"""Hotfix: patch anthropic_api.py to create the P:\\<ModName>\\ junction
after the Mod Creator finishes writing files.

This is what /dayz-new-mod does at the end of its scaffold step. The Mod
Creator was missing this final piece — files landed in workspace/<ModName>/
but the junction AddonBuilder needs wasn't created, so the build refused.

Idempotent: running twice is safe. Pass --dry-run to preview.

The patch:
  1. Copies _junction_helper.py to desktop/sidecar/.
  2. Adds 'from _junction_helper import create_junction' to anthropic_api.py.
  3. After the LLM signals `done`, calls create_junction() and yields a
     `junction_created` SSE event.
"""
from __future__ import annotations
import argparse, shutil, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

SIDECAR_DIR = REPO / "desktop" / "sidecar"
ANTHROPIC_FILE = SIDECAR_DIR / "anthropic_api.py"
HELPER_SRC = HERE / "desktop" / "sidecar" / "_junction_helper.py"
HELPER_DST = SIDECAR_DIR / "_junction_helper.py"


# ----- patch markers + replacements -----

IMPORT_OLD = "import asyncio"
IMPORT_NEW = (
    "import asyncio\n"
    "import sys as _sys\n"
    "_sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))\n"
    "from _junction_helper import create_junction"
)

DONE_OLD = '''                yield _format_sse({
                    "event": "done", "files": files_written, "summary": done_summary or "",
                    "iterations": iteration,
                }, event="control")'''

DONE_NEW = '''                # Create the P:\\<ModName>\\ junction so AddonBuilder can find the source.
                # Mirrors the post-scaffold step from /dayz-new-mod.
                jr = create_junction(mod_root, body.name)
                if jr["ok"]:
                    yield _format_sse({
                        "kind": jr["kind"], "target": jr["target"], "mod": body.name,
                    }, event="junction_created")
                else:
                    yield _format_sse({
                        "error": f"junction creation failed: {jr['error']}",
                        "target": jr["target"], "mod": body.name,
                    }, event="junction_failed")

                yield _format_sse({
                    "event": "done", "files": files_written, "summary": done_summary or "",
                    "iterations": iteration,
                    "junction": {"ok": jr["ok"], "kind": jr.get("kind"), "error": jr.get("error")},
                }, event="control")'''


def patch_anthropic_api(dry_run: bool) -> int:
    if not ANTHROPIC_FILE.exists():
        print(f"  [FAIL] {ANTHROPIC_FILE} not found")
        return 0
    text = ANTHROPIC_FILE.read_text(encoding="utf-8")
    changes = 0

    if "from _junction_helper import create_junction" in text:
        print(f"  [OK ] {ANTHROPIC_FILE.name}: import already present")
    elif IMPORT_OLD in text:
        text = text.replace(IMPORT_OLD, IMPORT_NEW, 1)
        changes += 1
        print(f"  [{'DRY' if dry_run else 'PATCH'}] {ANTHROPIC_FILE.name}: import")
    else:
        print(f"  [WARN] {ANTHROPIC_FILE.name}: import anchor not found")

    if "junction_created" in text and "create_junction(mod_root" in text:
        print(f"  [OK ] {ANTHROPIC_FILE.name}: junction-creation block already present")
    elif DONE_OLD in text:
        text = text.replace(DONE_OLD, DONE_NEW, 1)
        changes += 1
        print(f"  [{'DRY' if dry_run else 'PATCH'}] {ANTHROPIC_FILE.name}: done-event block")
    else:
        print(f"  [WARN] {ANTHROPIC_FILE.name}: done-event anchor not found")
        print("         (the file may have been hand-edited; inspect manually)")

    if changes and not dry_run:
        ANTHROPIC_FILE.write_text(text, encoding="utf-8")
    return changes


def copy_helper(dry_run: bool) -> int:
    if not HELPER_SRC.exists():
        print(f"  [FAIL] helper source missing: {HELPER_SRC}")
        return 0
    if HELPER_DST.exists() and HELPER_DST.read_bytes() == HELPER_SRC.read_bytes():
        print(f"  [OK ] {HELPER_DST.name}: already current")
        return 0
    action = "DRY" if dry_run else "WRITE"
    existed = "(replace)" if HELPER_DST.exists() else "(new)"
    print(f"  [{action}] {HELPER_DST.name} {existed}")
    if not dry_run:
        HELPER_DST.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HELPER_SRC, HELPER_DST)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"Repo root: {REPO}")
    if args.dry_run:
        print("(dry run - no files will be written)")
    print()

    print("1. Copy junction helper")
    print("-" * 60)
    total = copy_helper(args.dry_run)

    print()
    print("2. Patch anthropic_api.py")
    print("-" * 60)
    total += patch_anthropic_api(args.dry_run)

    print()
    print(f"Done. {total} file change(s) {'would be ' if args.dry_run else ''}made.")
    if total and not args.dry_run:
        print()
        print("Restart the desktop app (pnpm tauri:dev) so the sidecar reloads.")
        print()
        print("To unblock AntiAFK right now, manually create its junction:")
        print(f"  cmd /c mklink /J P:\\AntiAFK \"{REPO / 'workspace' / 'AntiAFK'}\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
