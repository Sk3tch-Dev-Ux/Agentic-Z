#!/usr/bin/env python3
"""patch.py - Hotfix D6.4: real learning architecture.

Three tiers, idempotent:

  1. Closed-loop validation
     Copies _enscript_lint.py to desktop/sidecar/. Patches anthropic_api.py's
     write_file tool dispatch to call lint_enscript_source() before writing
     a .c file. If the lint fails, the tool_result tells Claude exactly what
     to fix and Claude regenerates the file in the same Mod Creator run.

  2. Canonical L2 docs (cross-agent learning)
     Appends a "Compile-time gotchas (learned the hard way)" section to
     .claude/skills/_shared/enscript-style.md. Every DayZ agent that reads
     L2 (which is every DayZ specialist) now has these rules in scope.

  3. Agent memory (cross-session learning)
     Writes feedback memories to .claude/agent-memory/dayz-coder/. Per-project
     accumulated lessons that survive across sessions and are auto-loaded by
     the dayz-coder agent on its next invocation.

After install: restart `pnpm tauri:dev` so the sidecar reloads.
"""
from __future__ import annotations
import argparse, shutil, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


# ---------- 1. Closed-loop validation ----------

LINTER_SRC = HERE / "desktop" / "sidecar" / "_enscript_lint.py"
LINTER_DST = REPO / "desktop" / "sidecar" / "_enscript_lint.py"
ANTHROPIC_FILE = REPO / "desktop" / "sidecar" / "anthropic_api.py"

# Add the import.
ANTHROPIC_IMPORT_OLD = "from _junction_helper import create_junction"
ANTHROPIC_IMPORT_NEW = (
    "from _junction_helper import create_junction\n"
    "from _enscript_lint import lint_enscript_source"
)

# Insert lint check at the start of the write_file dispatch. The existing
# write_file branch starts with the path-safety check; we add the lint check
# right after the path is resolved but before the file is written.
ANTHROPIC_LINT_OLD = '''                            if tool_name == "write_file":
                                rel = str(tool_input.get("path", "")).strip()
                                content = str(tool_input.get("content", ""))
                                target = _safe_path_in_mod(mod_root, rel)
                                if target is None:'''

ANTHROPIC_LINT_NEW = '''                            if tool_name == "write_file":
                                rel = str(tool_input.get("path", "")).strip()
                                content = str(tool_input.get("content", ""))
                                target = _safe_path_in_mod(mod_root, rel)
                                # D6.4: pre-write linter for .c files. If errors,
                                # tell Claude exactly what to fix and let it retry.
                                lint_errors = lint_enscript_source(content, path=rel)
                                if lint_errors:
                                    err = "Refused. Fix these issues and call write_file again:\\n" + \\
                                        "\\n".join(f"  - {e}" for e in lint_errors)
                                    yield _format_sse({"path": rel, "errors": lint_errors},
                                                      event="lint_failed")
                                    tool_results.append({
                                        "type": "tool_result", "tool_use_id": block.id,
                                        "content": err, "is_error": True,
                                    })
                                    continue
                                if target is None:'''


# ---------- 2. Canonical L2 docs ----------

ENSCRIPT_DOC = REPO / ".claude" / "skills" / "_shared" / "enscript-style.md"
APPEND_SRC = HERE / "enscript-style-append.md"


# ---------- 3. Agent memory ----------

MEMORY_SRC = HERE / "dayz-coder-memory"
MEMORY_DST = REPO / ".claude" / "agent-memory" / "dayz-coder"


# ---------- runner ----------

def copy_one(src: Path, dst: Path, label: str, dry_run: bool) -> int:
    if not src.exists():
        print(f"  [FAIL] source missing: {src}"); return 0
    if dst.exists() and dst.read_bytes() == src.read_bytes():
        print(f"  [OK ] {label} (already current)")
        return 0
    action = "DRY" if dry_run else "WRITE"
    existed = "(replace)" if dst.exists() else "(new)"
    print(f"  [{action}] {label} {existed}")
    if not dry_run:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return 1


def patch_anthropic(dry_run: bool) -> int:
    if not ANTHROPIC_FILE.exists():
        print(f"  [FAIL] {ANTHROPIC_FILE} not found"); return 0
    text = ANTHROPIC_FILE.read_text(encoding="utf-8")
    changed = 0

    # Idempotency markers
    has_import = "from _enscript_lint import lint_enscript_source" in text
    has_lint   = "lint_errors = lint_enscript_source" in text

    if has_import:
        print(f"  [OK ] anthropic_api.py: import (already patched)")
    elif ANTHROPIC_IMPORT_OLD in text:
        text = text.replace(ANTHROPIC_IMPORT_OLD, ANTHROPIC_IMPORT_NEW, 1)
        changed += 1
        print(f"  [{'DRY' if dry_run else 'PATCH'}] anthropic_api.py: import")
    else:
        print(f"  [WARN] anthropic_api.py: import anchor not found "
              f"(expected `{ANTHROPIC_IMPORT_OLD[:40]}...`)")

    if has_lint:
        print(f"  [OK ] anthropic_api.py: lint hook (already patched)")
    elif ANTHROPIC_LINT_OLD in text:
        text = text.replace(ANTHROPIC_LINT_OLD, ANTHROPIC_LINT_NEW, 1)
        changed += 1
        print(f"  [{'DRY' if dry_run else 'PATCH'}] anthropic_api.py: lint hook in write_file")
    else:
        print(f"  [WARN] anthropic_api.py: write_file anchor not found")

    if changed and not dry_run:
        ANTHROPIC_FILE.write_text(text, encoding="utf-8")
    return changed


def append_doc(dry_run: bool) -> int:
    if not ENSCRIPT_DOC.exists():
        print(f"  [FAIL] {ENSCRIPT_DOC} not found"); return 0
    if not APPEND_SRC.exists():
        print(f"  [FAIL] append source missing: {APPEND_SRC}"); return 0
    existing = ENSCRIPT_DOC.read_text(encoding="utf-8")
    if "Compile-time gotchas (learned the hard way)" in existing:
        print(f"  [OK ] enscript-style.md: already has gotchas section")
        return 0
    snippet = APPEND_SRC.read_text(encoding="utf-8")
    action = "DRY" if dry_run else "APPEND"
    print(f"  [{action}] enscript-style.md: append gotchas section "
          f"({len(snippet)} bytes)")
    if not dry_run:
        ENSCRIPT_DOC.write_text(existing + "\n" + snippet, encoding="utf-8")
    return 1


def copy_memories(dry_run: bool) -> int:
    if not MEMORY_SRC.exists():
        print(f"  [FAIL] memory source dir missing: {MEMORY_SRC}"); return 0
    changed = 0
    for src_file in sorted(MEMORY_SRC.glob("*.md")):
        dst = MEMORY_DST / src_file.name
        changed += copy_one(src_file, dst,
                            f"agent-memory/dayz-coder/{src_file.name}", dry_run)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"Repo root: {REPO}")
    if args.dry_run: print("(dry run)")
    print()

    total = 0
    print("1. Closed-loop validation (linter)")
    print("-" * 60)
    total += copy_one(LINTER_SRC, LINTER_DST, "desktop/sidecar/_enscript_lint.py", args.dry_run)
    total += patch_anthropic(args.dry_run)

    print()
    print("2. Canonical L2 docs (enscript-style.md)")
    print("-" * 60)
    total += append_doc(args.dry_run)

    print()
    print("3. Agent memory (.claude/agent-memory/dayz-coder/)")
    print("-" * 60)
    total += copy_memories(args.dry_run)

    print()
    print(f"Done. {total} change(s) {'would be ' if args.dry_run else ''}made.")
    if total and not args.dry_run:
        print()
        print("Restart `pnpm tauri:dev` so the sidecar reloads.")
        print()
        print("From now on:")
        print("  - The Mod Creator's write_file tool runs the linter on every .c")
        print("    file before writing. Claude sees lint errors as tool_result")
        print("    failures and self-corrects in the SAME run.")
        print("  - Every DayZ agent that reads enscript-style.md gets the new")
        print("    rules (ASCII-only, single-line calls, verify-before-modded).")
        print("  - dayz-coder's persistent memory has 3 feedback files with")
        print("    real-incident context. Future sessions auto-load these.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
