#!/usr/bin/env python3
"""patch.py - Hotfix D6.3: give the Mod Creator RAG access.

Adds search_vanilla + read_vanilla_file tools to the Mod Creator. Updates
the user message preamble. Idempotent.
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ANTHROPIC_FILE = REPO / "desktop" / "sidecar" / "anthropic_api.py"

USER_MSG_OLD = '''        user_message = (
            f"Generate a complete DayZ mod scaffold for the pitch below by calling the "
            f"`write_file` tool repeatedly, one call per file. End with the `done` tool.\\n\\n"
            f"Mod name: {body.name}\\n"
            f"Author: {author}\\n"
            f"Pitch: {body.pitch}\\n\\n"
            f"Mandatory: write `config.cpp` (with CfgPatches) and `$PBOPREFIX$`. "
            f"Place Enforce Script files in scripts/3_Game/, scripts/4_World/, scripts/5_Mission/ "
            f"as appropriate. Follow the EnScript style guide and L2 conventions you already know. "
            f"Use prefixed class names (e.g. {body.name}_Foo). Use `modded class` (no inheritance "
            f"clause) when extending vanilla. Keep individual files focused — one class per file "
            f"unless very small. Do not exceed {MOD_CREATOR_MAX_FILES} files."
        )'''

USER_MSG_NEW = '''        user_message = (
            f"Generate a complete DayZ mod scaffold for the pitch below by calling the "
            f"`write_file` tool repeatedly, one call per file. End with the `done` tool.\\n\\n"
            f"Mod name: {body.name}\\n"
            f"Author: {author}\\n"
            f"Pitch: {body.pitch}\\n\\n"
            f"CRITICAL — verify before you write. Before declaring `modded class X`, "
            f"call `search_vanilla(query=\\"class X\\")` to confirm X exists in vanilla. If you "
            f"don't see X in the results, DO NOT modded-class it — pick a real vanilla class to "
            f"extend instead. Hallucinated class names cause `Unknown type 'X'` compile errors. "
            f"Use `read_vanilla_file` to inspect a hit's full context if you need to check method "
            f"signatures or override semantics. For medical mods, requiredAddons[] should include "
            f"\\"DZ_Gear_Medical\\". Weapons: \\"DZ_Weapons_Firearms\\". Vehicles: "
            f"\\"DZ_Vehicles_Wheeled\\".\\n\\n"
            f"ASCII ONLY in source files. Enforce Script's parser does NOT tolerate "
            f"non-ASCII characters anywhere - including comments. Use plain hyphens "
            f"(-) not em dashes, straight quotes (' \\") not curly, and avoid Unicode "
            f"arrows, bullets, or accented characters. Mojibake from em dashes is the "
            f"#1 cause of \\"Expected ',' or ')'\\" compile errors in generated mods.\\n\\n"
            f"SINGLE-LINE function calls. Enforce Script's parser can choke on "
            f"multi-line expressions inside argument lists (Print, Error, etc.). "
            f"For long string concatenations, build the message into a `string` "
            f"variable on its own line and pass that variable to Print(). Don't "
            f"write `Print(\\"... \\" + foo + \\" ...\\");` split across lines.\\n\\n"
            f"Mandatory: write `config.cpp` (with CfgPatches) and `$PBOPREFIX$`. "
            f"Place Enforce Script files in scripts/3_Game/, scripts/4_World/, scripts/5_Mission/ "
            f"as appropriate. Follow the EnScript style guide and L2 conventions you already know. "
            f"Use prefixed class names (e.g. {body.name}_Foo). Use `modded class` (no inheritance "
            f"clause) when extending vanilla. Keep individual files focused - one class per file "
            f"unless very small. Do not exceed {MOD_CREATOR_MAX_FILES} files."
        )'''

TOOLS_OLD = '''        tools = [
            {
                "name": "write_file",'''

TOOLS_NEW = '''        tools = [
            {
                "name": "search_vanilla",
                "description": (
                    "Semantic search over indexed vanilla DayZ source. "
                    "USE THIS to verify class names exist before writing a modded class. "
                    "Returns top-K matching chunks with file paths, line ranges, and snippets."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "top_k": {"type": "integer"},
                        "file_type": {"type": "string"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "read_vanilla_file",
                "description": (
                    "Fetch a line range from a vanilla DayZ source file (paths under P:\\\\). "
                    "Use after search_vanilla to read full context."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "line_start": {"type": "integer"},
                        "line_end": {"type": "integer"},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "write_file",'''

DISPATCH_OLD = '''                            if tool_name == "write_file":'''

DISPATCH_NEW = '''                            if tool_name == "search_vanilla":
                                try:
                                    rag_dir = repo_root / ".claude" / "mcp" / "dayz-rag"
                                    if str(rag_dir) not in sys.path:
                                        sys.path.insert(0, str(rag_dir))
                                    import server as _rag  # type: ignore
                                    rows = _rag.search_dayz_source_impl(
                                        str(tool_input.get("query", "")),
                                        int(tool_input.get("top_k", 3)),
                                        tool_input.get("file_type"),
                                    )
                                    digest = []
                                    for r in rows:
                                        digest.append({
                                            "path": r.get("path", ""),
                                            "parent": r.get("parent_context", ""),
                                            "lines": f"{r.get('line_start', 0)}-{r.get('line_end', 0)}",
                                            "snippet": (r.get("snippet", "") or "")[:1200],
                                        })
                                    result_text = json.dumps(digest, indent=2) if rows else (
                                        "No matches. The class/symbol likely does NOT exist in "
                                        "vanilla. Pick a different (real) class to extend."
                                    )
                                    yield _format_sse({"query": tool_input.get("query", ""),
                                                       "hits": len(rows)}, event="search")
                                    tool_results.append({
                                        "type": "tool_result", "tool_use_id": block.id,
                                        "content": result_text,
                                    })
                                except Exception as e:
                                    err = f"search_vanilla failed: {e}. Continue carefully."
                                    yield _format_sse({"error": err}, event="error")
                                    tool_results.append({
                                        "type": "tool_result", "tool_use_id": block.id,
                                        "content": err, "is_error": True,
                                    })
                                continue
                            if tool_name == "read_vanilla_file":
                                try:
                                    p = Path(str(tool_input.get("path", ""))).resolve()
                                    if p.drive.upper() != "P:":
                                        raise ValueError("path must be under P:\\\\")
                                    text_full = p.read_text(encoding="utf-8", errors="replace")
                                    lines_arr = text_full.splitlines()
                                    s = max(1, int(tool_input.get("line_start", 1)))
                                    e_end = (min(len(lines_arr), int(tool_input.get("line_end", 0)))
                                             if tool_input.get("line_end") else len(lines_arr))
                                    snippet = "\\n".join(lines_arr[s-1:e_end])[:8000]
                                    yield _format_sse({"path": str(p), "lines": f"{s}-{e_end}"},
                                                      event="read_file")
                                    tool_results.append({
                                        "type": "tool_result", "tool_use_id": block.id,
                                        "content": snippet,
                                    })
                                except Exception as e:
                                    err = f"read_vanilla_file failed: {e}"
                                    yield _format_sse({"error": err}, event="error")
                                    tool_results.append({
                                        "type": "tool_result", "tool_use_id": block.id,
                                        "content": err, "is_error": True,
                                    })
                                continue
                            if tool_name == "write_file":'''

PATCHES = [
    ("user_message",  USER_MSG_OLD,  USER_MSG_NEW),
    ("tools list",    TOOLS_OLD,     TOOLS_NEW),
    ("tool dispatch", DISPATCH_OLD,  DISPATCH_NEW),
]


def patch(dry_run: bool) -> int:
    if not ANTHROPIC_FILE.exists():
        print(f"  [FAIL] {ANTHROPIC_FILE} not found")
        return 0
    text = ANTHROPIC_FILE.read_text(encoding="utf-8")
    original_text = text
    already = {
        "user_message":  "verify before you write" in original_text,
        "tools list":    '"name": "search_vanilla"' in original_text,
        "tool dispatch": 'tool_name == "search_vanilla"' in original_text,
    }
    changed = 0
    for name, old, new in PATCHES:
        if already[name]:
            print(f"  [OK ] {ANTHROPIC_FILE.name}: {name} (already patched)")
            continue
        if old in text:
            text = text.replace(old, new, 1)
            changed += 1
            print(f"  [{'DRY' if dry_run else 'PATCH'}] {ANTHROPIC_FILE.name}: {name}")
        else:
            print(f"  [WARN] {ANTHROPIC_FILE.name}: {name} anchor not found")
    if changed and not dry_run:
        ANTHROPIC_FILE.write_text(text, encoding="utf-8")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(f"Repo root: {REPO}")
    if args.dry_run: print("(dry run)")
    print()
    print("Hotfix D6.3 - Mod Creator gets RAG tools")
    print("-" * 60)
    total = patch(args.dry_run)
    print()
    print(f"Done. {total} edit(s) {'would be ' if args.dry_run else ''}made.")
    if total and not args.dry_run:
        print()
        print("Restart pnpm tauri:dev so the sidecar reloads.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
