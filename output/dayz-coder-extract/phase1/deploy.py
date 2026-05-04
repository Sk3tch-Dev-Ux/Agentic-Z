#!/usr/bin/env python3
"""
deploy.py — install Phase 1 (Workspace RAG) into the Agentic-Z repo.

Three things happen, all idempotent:

1. Copy the new skill folder into `.claude/skills/dayz-rag-workspace-index/`.
2. Patch `.claude/mcp/dayz-rag/server.py` to add the `search_dayz_workspace` tool.
3. Patch `.claude/agents/dayz-coder.md` to mention the workspace corpus
   (optional — only if dayz-coder.md exists; skipped otherwise).

Pass --dry-run to preview without writing.

Usage (from the repo root):
    python output\\dayz-coder-extract\\phase1\\deploy.py
    python output\\dayz-coder-extract\\phase1\\deploy.py --dry-run
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

# Resolve repo root: <repo>/output/dayz-coder-extract/phase1/deploy.py
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


# ---------- 1. skill folder copy --------------------------------------------

SKILL_SRC = HERE / "dayz-rag-workspace-index"
SKILL_DST = REPO / ".claude" / "skills" / "dayz-rag-workspace-index"


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


# ---------- 2. server.py patch ----------------------------------------------

SERVER_PATH = REPO / ".claude" / "mcp" / "dayz-rag" / "server.py"

# Where to splice the workspace constants (after the wiki constant).
SERVER_CONST_OLD = 'WIKI_TABLE_NAME = "wiki_chunks"'
SERVER_CONST_NEW = (
    'WIKI_TABLE_NAME = "wiki_chunks"\n'
    'WORKSPACE_TABLE_NAME = "workspace_chunks"'
)

# Add a `_workspace_table` lazy global next to `_wiki_table`.
SERVER_GLOBAL_OLD = "_wiki_table = None"
SERVER_GLOBAL_NEW = "_wiki_table = None\n_workspace_table = None"

# Add `_get_workspace_table()` after `_get_wiki_table()`. Anchor on the helper's
# closing — the next thing in the file is `_format_hit`. Splice between them.
SERVER_FUNC_OLD = "def _format_hit(row: dict) -> dict:"
SERVER_FUNC_NEW = '''def _get_workspace_table():
    global _workspace_table
    if _workspace_table is None:
        import lancedb
        db_path = INDEX_ROOT / "lancedb"
        if not db_path.exists():
            raise RuntimeError(
                f"No index at {INDEX_ROOT}. Run: python .claude/skills/dayz-rag-workspace-index/index.py"
            )
        db = lancedb.connect(str(db_path))
        if WORKSPACE_TABLE_NAME not in db.table_names():
            raise RuntimeError(
                f"Workspace index table '{WORKSPACE_TABLE_NAME}' missing. "
                "Run /dayz-rag-workspace-index first."
            )
        _workspace_table = db.open_table(WORKSPACE_TABLE_NAME)
    return _workspace_table


def search_dayz_workspace_impl(
    query: str,
    top_k: int = 5,
    file_type: Optional[str] = None,
    mod: Optional[str] = None,
) -> list[dict]:
    """Semantic search over your own mod source under workspace/<ModName>/."""
    if not query or not query.strip():
        return []
    top_k = max(1, min(int(top_k), MAX_TOP_K))
    if file_type is not None and file_type not in VALID_FILE_TYPES:
        raise ValueError(f"file_type must be one of {sorted(VALID_FILE_TYPES)} or None")

    table = _get_workspace_table()
    vec = _embed_query(query)
    # Over-fetch when filtering, then slice down to top_k after the filter.
    needed_overscan = 4 if (file_type or mod) else 1
    rows = table.search(vec).limit(top_k * needed_overscan).to_list()
    if file_type:
        rows = [r for r in rows if r.get("file_type") == file_type]
    if mod:
        rows = [r for r in rows if r.get("mod_name") == mod]
    rows = rows[:top_k]
    out = []
    for r in rows:
        hit = _format_hit(r)
        hit["mod_name"] = r.get("mod_name", "")
        out.append(hit)
    return out


def _format_hit(row: dict) -> dict:'''

# Update list_indexed_sources_impl to also return the workspace manifest.
SERVER_LIST_OLD = '''    src_manifest = INDEX_ROOT / "manifest.json"
    wiki_manifest = INDEX_ROOT / "wiki-manifest.json"
    if src_manifest.exists():
        try:
            out["source"] = json.loads(src_manifest.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            out["source"] = {"error": f"manifest unreadable: {e}"}
    if wiki_manifest.exists():
        try:
            out["wiki"] = json.loads(wiki_manifest.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            out["wiki"] = {"error": f"wiki manifest unreadable: {e}"}'''
SERVER_LIST_NEW = '''    src_manifest = INDEX_ROOT / "manifest.json"
    wiki_manifest = INDEX_ROOT / "wiki-manifest.json"
    workspace_manifest = INDEX_ROOT / "workspace-manifest.json"
    if src_manifest.exists():
        try:
            out["source"] = json.loads(src_manifest.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            out["source"] = {"error": f"manifest unreadable: {e}"}
    if wiki_manifest.exists():
        try:
            out["wiki"] = json.loads(wiki_manifest.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            out["wiki"] = {"error": f"wiki manifest unreadable: {e}"}
    if workspace_manifest.exists():
        try:
            out["workspace"] = json.loads(workspace_manifest.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            out["workspace"] = {"error": f"workspace manifest unreadable: {e}"}'''

# Register the new MCP tool. Splice before `@mcp.tool()\n    def list_indexed_sources`.
SERVER_TOOL_OLD = '''    @mcp.tool()
    def list_indexed_sources() -> dict:'''
SERVER_TOOL_NEW = '''    @mcp.tool()
    def search_dayz_workspace(
        query: str,
        top_k: int = 5,
        file_type: Optional[str] = None,
        mod: Optional[str] = None,
    ) -> list[dict]:
        """Semantic search over YOUR own mod source under workspace/<ModName>/.

        Use this for "how does my mod handle X" questions. Mirrors search_dayz_source
        but queries the workspace_chunks table populated by /dayz-rag-workspace-index.

        Args:
            query: natural-language question or description
            top_k: max results (1-25, default 5)
            file_type: filter to one of "c", "cpp", "hpp", "h", "layout", "cfg",
                "rvmat", "xml", "json", "csv" (default: all)
            mod: filter to a specific mod folder under workspace/ (default: all mods)

        Returns: list of {path, mod_name, file_type, parent_context, line_start,
            line_end, score, snippet}.
        """
        return search_dayz_workspace_impl(query, top_k, file_type, mod)

    @mcp.tool()
    def list_indexed_sources() -> dict:'''


SERVER_PATCHES = [
    ("constants", SERVER_CONST_OLD, SERVER_CONST_NEW),
    ("globals", SERVER_GLOBAL_OLD, SERVER_GLOBAL_NEW),
    ("helpers + impl", SERVER_FUNC_OLD, SERVER_FUNC_NEW),
    ("list_indexed_sources_impl", SERVER_LIST_OLD, SERVER_LIST_NEW),
    ("MCP tool registration", SERVER_TOOL_OLD, SERVER_TOOL_NEW),
]


def deploy_server_patch(dry_run: bool) -> int:
    print()
    print("2. server.py patch (add workspace MCP tool)")
    print("-" * 60)
    if not SERVER_PATH.exists():
        print(f"  [FAIL] {SERVER_PATH.relative_to(REPO)} not found")
        return 0

    text = SERVER_PATH.read_text(encoding="utf-8")
    original = text
    applied = 0

    for label, old, new in SERVER_PATCHES:
        if new in text:
            print(f"  [OK ] {label} (already patched)")
        elif old in text:
            text = text.replace(old, new, 1)
            applied += 1
            print(f"  [{'DRY' if dry_run else 'PATCH'}] {label}")
        else:
            print(f"  [WARN] {label}: anchor text not found — skipped")
            print(f"         (file may have been hand-edited; inspect manually)")

    if applied and not dry_run:
        SERVER_PATH.write_text(text, encoding="utf-8")
    return applied


# ---------- 3. dayz-coder.md patch (optional) -------------------------------

CODER_PATH = REPO / ".claude" / "agents" / "dayz-coder.md"

CODER_OLD_HEADER = "## VANILLA DATA — SEARCH HERE FIRST"
CODER_NEW_HEADER = "## RAG CORPORA — SEARCH HERE FIRST"

CODER_BULLET_OLD = """**Indexed by `dayz-rag` MCP** (backed by `/dayz-rag-index` or `/dayz-rag-download`):"""
CODER_BULLET_NEW = """**Three corpora, three MCP tools:**

| Tool | Corpus | Built by |
|---|---|---|
| `search_dayz_source` | Vanilla DayZ on `P:\\` (scripts, layouts, configs) | `/dayz-rag-index` or `/dayz-rag-download` |
| `search_dayz_wiki` | Bohemia community wiki (DayZ category) | `/dayz-rag-wiki-index` |
| `search_dayz_workspace` | Your own mods under `workspace/<ModName>/` | `/dayz-rag-workspace-index` |

`search_dayz_workspace(query, top_k=5, file_type=None, mod=None)` answers "how does MY mod do X" with file:line citations the same way `search_dayz_source` answers vanilla. Use it when the user asks about their own code rather than vanilla. Pass `mod="<ModName>"` to scope to one mod folder.

**Indexed by `dayz-rag` MCP** (vanilla side, backed by `/dayz-rag-index` or `/dayz-rag-download`):"""


def deploy_coder_patch(dry_run: bool) -> int:
    print()
    print("3. dayz-coder.md patch (mention workspace corpus)")
    print("-" * 60)
    if not CODER_PATH.exists():
        print(f"  [SKIP] {CODER_PATH.relative_to(REPO)} not present (skipping)")
        return 0

    text = CODER_PATH.read_text(encoding="utf-8")
    applied = 0

    if CODER_NEW_HEADER in text:
        print(f"  [OK ] section header (already renamed)")
    elif CODER_OLD_HEADER in text:
        text = text.replace(CODER_OLD_HEADER, CODER_NEW_HEADER, 1)
        applied += 1
        print(f"  [{'DRY' if dry_run else 'PATCH'}] section header")
    else:
        print("  [WARN] section header anchor not found — skipped")

    if CODER_BULLET_NEW.split("\n")[0] in text and "search_dayz_workspace" in text:
        print(f"  [OK ] corpora table (already present)")
    elif CODER_BULLET_OLD in text:
        text = text.replace(CODER_BULLET_OLD, CODER_BULLET_NEW, 1)
        applied += 1
        print(f"  [{'DRY' if dry_run else 'PATCH'}] corpora table")
    else:
        print("  [WARN] corpora bullet anchor not found — skipped")

    if applied and not dry_run:
        CODER_PATH.write_text(text, encoding="utf-8")
    return applied


# ---------- driver ----------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="preview without writing")
    args = parser.parse_args()

    print(f"Repo root: {REPO}")
    if args.dry_run:
        print("(dry run — no files will be written)")
    print()

    total = 0
    total += deploy_skill(args.dry_run)
    total += deploy_server_patch(args.dry_run)
    total += deploy_coder_patch(args.dry_run)

    print()
    print(f"Done. {total} file change(s) {'would be ' if args.dry_run else ''}made.")
    if total and not args.dry_run:
        print()
        print("Next steps:")
        print("  1. python .claude\\skills\\sync-skills\\sync.py")
        print("     (registers the new skill across Claude Code / Codex / Gemini)")
        print("  2. python .claude\\skills\\dayz-rag-workspace-index\\index.py")
        print("     (builds the workspace index for the first time)")
        print("  3. Restart your agent CLI session so the MCP server picks up the new tool.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
