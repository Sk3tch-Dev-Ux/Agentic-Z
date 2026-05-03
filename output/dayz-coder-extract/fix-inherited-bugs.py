#!/usr/bin/env python3
"""
fix-inherited-bugs.py — one-shot fixup for two bugs inherited from the upstream
Agentic-Z template.

A1. Replace hardcoded `G:\\AI-Templates\\` paths in agent and skill files with
    repo-relative paths so memory and example output work on any clone.

A2. Rewrite the stale "fully local Nomic" paragraph in the L2 conventions doc
    so it matches the actual Voyage AI cloud backend in server.py / README.md.

Idempotent — safe to re-run. Pass --dry-run to preview without writing.

Usage (from the repo root):
    python output\\dayz-coder-extract\\fix-inherited-bugs.py
    python output\\dayz-coder-extract\\fix-inherited-bugs.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

# Resolve the repo root from this file's location:
#   <repo>/output/dayz-coder-extract/fix-inherited-bugs.py
# parents[0] = dayz-coder-extract, [1] = output, [2] = repo root.
REPO = Path(__file__).resolve().parents[2]


# ---------- A1: agent files (memory path) ----------------------------------

# Each agent has the line:
#   You have a persistent, file-based memory system at `G:\AI-Templates\.claude\agent-memory\<NAME>\`. This directory already exists — write to it directly with the Write tool (do not run mkdir or check for its existence).
# Replace with a repo-relative path; soften the "directory already exists" claim.

AGENT_NAMES = [
    "agent-creator",
    "dayz-asset-specialist",
    "dayz-config-specialist",
    "dayz-map-specialist",
    "dayz-mod-debugger",
    "dayz-mod-reviewer",
    "dayz-object-builder",
    "dayz-script-specialist",
    "dayz-server-admin",
    "dayz-ui-specialist",
    "dayz-workbench-specialist",
]


def agent_old_line(name: str) -> str:
    return (
        f"You have a persistent, file-based memory system at "
        f"`G:\\AI-Templates\\.claude\\agent-memory\\{name}\\`. "
        "This directory already exists — write to it directly with the Write tool "
        "(do not run mkdir or check for its existence)."
    )


def agent_new_line(name: str) -> str:
    return (
        f"You have a persistent, file-based memory system at "
        f"`.claude/agent-memory/{name}/`, resolved relative to the repo root "
        "(the directory containing `CLAUDE.md`). The directory should already exist for "
        "committed memory; create it on first write if not."
    )


# ---------- A1: skill / wiki files (example output strings) ----------------

# Misc references in skills + wiki where example output bakes in the upstream
# author's machine path. Use a placeholder like `<repo>/...` so re-runs are
# stable and the output reads correctly on any clone.

SKILL_REPLACEMENTS = [
    # .claude/skills/sync-skills/SKILL.md  &  wiki/docs/skills/sync-skills.md
    (
        "Repo skills: 1  (G:\\AI-Templates\\.claude\\skills)",
        "Repo skills: 1  (<repo>/.claude/skills)",
    ),
    # .claude/skills/dayz-mount-p/SKILL.md  &  wiki/docs/skills/dayz-mount-p.md
    (
        "[INFO]  Cached for future runs at G:\\AI-Templates\\.claude\\local-memory\\dayz-work-drive.json",
        "[INFO]  Cached for future runs at <repo>/.claude/local-memory/dayz-work-drive.json",
    ),
    # .claude/skills/dayz-mount-p/mount.py  (stale comment)
    (
        "REPO_ROOT = _HERE.parent.parent.parent  # G:\\AI-Templates",
        "REPO_ROOT = _HERE.parent.parent.parent  # repo root",
    ),
]


SKILL_FILES = [
    REPO / ".claude" / "skills" / "sync-skills" / "SKILL.md",
    REPO / ".claude" / "skills" / "dayz-mount-p" / "SKILL.md",
    REPO / ".claude" / "skills" / "dayz-mount-p" / "mount.py",
    REPO / "wiki" / "docs" / "skills" / "sync-skills.md",
    REPO / "wiki" / "docs" / "skills" / "dayz-mount-p.md",
]


# ---------- A2: dayz-conventions RAG section -------------------------------

CONVENTIONS_PATH = REPO / ".claude" / "skills" / "_shared" / "dayz-conventions.md"

# The original section (multi-line). Match the canonical text shipped by the
# upstream template; if the user has hand-edited it the script will print a
# warning and skip A2 (rather than blow it away).
A2_OLD = """## RAG embedding (local)

The RAG layer (`/dayz-rag-index` + the `dayz-rag` MCP server) runs **fully locally** with `nomic-ai/CodeRankEmbed` (137M-param code-specialised model, 768-dim, top of CoIR). No API keys, no network calls, no per-query cost.

- First indexer run downloads ~280MB of model weights to the HuggingFace cache (`~/.cache/huggingface/`). After that, indexing and queries are entirely offline.
- Full index: ~7,000 chunks, builds in ~90s on a typical CPU.
- Per-query latency: ~50-150ms (local embed + numpy cosine).

DayZ Tools is the only per-machine install needed. There's no per-clone API key."""

A2_NEW = """## RAG embedding (cloud, optional)

The RAG layer (`/dayz-rag-index` + the `dayz-rag` MCP server) runs against **Voyage AI** (`voyage-code-3` by default, 1024-dim, asymmetric encoding: `input_type=\"document\"` at index time, `input_type=\"query\"` at search time). Free tier covers ~3 full vanilla rebuilds. Add `VOYAGE_API_KEY=pa-…` to `.env` at the repo root before running `/dayz-rag-index` or any agent that uses `search_dayz_source`.

- Skip the build entirely with `/dayz-rag-download` — pulls a prebuilt vanilla+wiki index from GitHub releases (~1 min). No key needed for download; query-time embedding still requires the key.
- Full local rebuild via `/dayz-rag-index --full` is ~25-30 min and 5-65M tokens depending on the corpus and model.
- Without a key, agents fall back to `Grep` over `P:\\scripts\\` and the documented vanilla paths — fully functional, just less smart.

DayZ Tools is the only per-machine install needed. The Voyage key is per-clone (`.env` is gitignored by default)."""

# Second occurrence: in the "Vanilla source recall" section, the upstream
# template again describes the index as numpy+sqlite + local Nomic embeddings.
# Actual implementation uses LanceDB + Voyage AI. Rewrite that one sentence too.
A2B_OLD = (
    "The `dayz-rag` MCP server exposes semantic search over indexed vanilla DayZ source: "
    "`.c` (Enforce Script under `P:\\scripts\\`), `.layout` (GUI under `P:\\gui\\`), and "
    "`.cpp`/`.cfg`/`.hpp`/`.h` config blocks (under `P:\\dz\\` and friends). "
    "Backed by a per-user numpy + sqlite index at `~/.claude/dayz-rag-index/`, "
    "built and rebuilt by `/dayz-rag-index --full`. "
    "Embedding runs locally via `nomic-ai/CodeRankEmbed` — no API keys, no network calls."
)
A2B_NEW = (
    "The `dayz-rag` MCP server exposes semantic search over indexed vanilla DayZ source: "
    "`.c` (Enforce Script under `P:\\scripts\\`), `.layout` (GUI under `P:\\gui\\`), and "
    "`.cpp`/`.cfg`/`.hpp`/`.h` config blocks (under `P:\\dz\\` and friends). "
    "Backed by a per-user LanceDB index at `~/.claude/dayz-rag-index/`, "
    "built and rebuilt by `/dayz-rag-index --full`. "
    "Embeddings run via Voyage AI (`voyage-code-3` by default) — set `VOYAGE_API_KEY` in `.env` at the repo root."
)


# ---------- runner ----------------------------------------------------------


def fix_file(path: Path, replacements: Iterable[tuple[str, str]], dry_run: bool) -> int:
    """Apply each (old, new) replacement to `path`. Returns count of changes."""
    if not path.exists():
        print(f"  [SKIP] {path.relative_to(REPO)} (not found)")
        return 0
    text = path.read_text(encoding="utf-8")
    original = text
    changes = 0
    for old, new in replacements:
        if old in text:
            text = text.replace(old, new)
            changes += 1
        elif new in original:
            # Already fixed in a previous run.
            pass
    if changes and not dry_run:
        path.write_text(text, encoding="utf-8")
    rel = path.relative_to(REPO)
    if changes:
        print(f"  [{'DRY' if dry_run else 'FIX'}] {rel}: {changes} replacement(s)")
    else:
        print(f"  [OK ] {rel}: no change needed")
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="preview without writing")
    args = parser.parse_args()

    print(f"Repo root: {REPO}")
    if args.dry_run:
        print("(dry run — no files will be written)")
    print()

    total = 0

    # --- A1: agents ---
    print("A1. Agent memory paths")
    print("-" * 60)
    for name in AGENT_NAMES:
        path = REPO / ".claude" / "agents" / f"{name}.md"
        total += fix_file(path, [(agent_old_line(name), agent_new_line(name))], args.dry_run)

    # --- A1: skills + wiki example output ---
    print()
    print("A1. Skill / wiki example output paths")
    print("-" * 60)
    for path in SKILL_FILES:
        total += fix_file(path, SKILL_REPLACEMENTS, args.dry_run)

    # --- A2: dayz-conventions ---
    print()
    print("A2. RAG backend section in dayz-conventions.md")
    print("-" * 60)
    if not CONVENTIONS_PATH.exists():
        print(f"  [SKIP] {CONVENTIONS_PATH.relative_to(REPO)} (not found)")
    else:
        text = CONVENTIONS_PATH.read_text(encoding="utf-8")
        original = text
        changes = 0

        # First section: "## RAG embedding (local)"
        if A2_NEW in text:
            print(
                f"  [OK ] {CONVENTIONS_PATH.relative_to(REPO)}: "
                "RAG embedding section already fixed"
            )
        elif A2_OLD in text:
            text = text.replace(A2_OLD, A2_NEW)
            changes += 1
            print(
                f"  [{'DRY' if args.dry_run else 'FIX'}] "
                f"{CONVENTIONS_PATH.relative_to(REPO)}: RAG embedding section"
            )
        else:
            print(
                f"  [WARN] {CONVENTIONS_PATH.relative_to(REPO)}: "
                "'RAG embedding' section doesn't match upstream — skipped."
            )

        # Second sentence: in "## Vanilla source recall" section
        if A2B_NEW in text:
            print(
                f"  [OK ] {CONVENTIONS_PATH.relative_to(REPO)}: "
                "Vanilla source recall sentence already fixed"
            )
        elif A2B_OLD in text:
            text = text.replace(A2B_OLD, A2B_NEW)
            changes += 1
            print(
                f"  [{'DRY' if args.dry_run else 'FIX'}] "
                f"{CONVENTIONS_PATH.relative_to(REPO)}: Vanilla source recall sentence"
            )
        else:
            print(
                f"  [WARN] {CONVENTIONS_PATH.relative_to(REPO)}: "
                "'Vanilla source recall' sentence doesn't match upstream — skipped."
            )

        if changes and not args.dry_run:
            CONVENTIONS_PATH.write_text(text, encoding="utf-8")
        total += changes

    print()
    print(f"Done. {total} file(s) {'would be ' if args.dry_run else ''}changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
