"""DayZ workspace RAG indexer.

Index your own mod source (under `workspace/<ModName>/`) into the same LanceDB
that backs the vanilla and wiki indexes. After this runs, the dayz-rag MCP
server's `search_dayz_workspace` tool can answer "how does MY mod do X" with
file:line citations the same way `search_dayz_source` answers vanilla.

Architecture:
  - Vanilla index   -> LanceDB table "chunks"            (built by /dayz-rag-index)
  - Wiki index      -> LanceDB table "wiki_chunks"       (built by /dayz-rag-wiki-index)
  - Workspace index -> LanceDB table "workspace_chunks"  (built by THIS skill)

All three live under `~/.claude/dayz-rag-index/lancedb/`.

Idempotent: re-running on an existing index UPSERTS by chunk content hash —
unchanged chunks are skipped (no Voyage call), changed chunks are re-embedded,
deleted source chunks have their rows pruned. So you can re-run after every
edit session for almost-free.

Run:
    python .claude/skills/dayz-rag-workspace-index/index.py                     # all mods under workspace/
    python .claude/skills/dayz-rag-workspace-index/index.py MyMod               # one mod
    python .claude/skills/dayz-rag-workspace-index/index.py --status            # show manifest
    python .claude/skills/dayz-rag-workspace-index/index.py --full              # drop and rebuild
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

# Reuse the vanilla indexer's chunkers, embedder, deps installer, and Voyage
# config. Keeps a single source of truth for chunk shape and embedding model.
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "dayz-rag-index"))
from index import (  # noqa: E402
    COST_PER_MTOKEN,
    DEFAULT_EMBED_MODEL,
    EMBED_DIM,
    EMBED_MAX_CHARS,
    EXT_TYPE_MAP,
    CLASS_BLOCK_TYPES,
    WHOLE_FILE_TYPES,
    INDEX_ROOT,
    FAIL,
    INFO,
    OK,
    WARN,
    _block_chunks,
    _embed_all,
    _ensure_deps,
    _load_env_and_key,
    chunk_rvmat,
    chunk_whole_file,
    chunk_xml,
)

# Resolve the repo root from this file: .claude/skills/dayz-rag-workspace-index/index.py
# parents[0] = skill dir, [1] = skills, [2] = .claude, [3] = repo root.
REPO_ROOT = _HERE.parents[2]
WORKSPACE_DIR = REPO_ROOT / "workspace"

WORKSPACE_TABLE_NAME = "workspace_chunks"
WORKSPACE_MANIFEST_NAME = "workspace-manifest.json"

# Folders we never index inside a mod (build artifacts, vcs, caches).
WORKSPACE_IGNORE_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", ".venv", "node_modules",
    ".idea", ".vscode", "_server",  # _server is the launch-test staging, not source
}

# Extra files we never index (binary models/textures — captured by other tools).
WORKSPACE_IGNORE_SUFFIXES = {
    ".p3d", ".paa", ".rtm", ".bisign", ".bikey", ".pbo", ".log", ".tmp",
    ".png", ".tga", ".jpg", ".jpeg",  # source images — chunked text only
}


def _list_mods(name: str | None) -> list[Path]:
    """Resolve which mod folders to index. None => all top-level dirs under workspace/."""
    if not WORKSPACE_DIR.exists():
        return []
    if name:
        target = WORKSPACE_DIR / name
        return [target] if target.is_dir() else []
    return sorted(
        p for p in WORKSPACE_DIR.iterdir()
        if p.is_dir() and not p.name.startswith("_") and p.name not in WORKSPACE_IGNORE_DIRS
    )


def _walk_mod(root: Path):
    """Yield every indexable file path under a mod root, skipping ignore dirs/suffixes."""
    for f in root.rglob("*"):
        try:
            if not f.is_file():
                continue
        except OSError:
            continue
        # Skip if any path part is in the ignore set
        parts = set(p.lower() for p in f.relative_to(root).parts)
        if parts & WORKSPACE_IGNORE_DIRS:
            continue
        suffix = f.suffix.lower()
        if suffix in WORKSPACE_IGNORE_SUFFIXES:
            continue
        if suffix not in EXT_TYPE_MAP:
            continue
        yield f


def _chunk_for_type(path: Path, file_type: str, seen_rvmat_hashes: set[str]) -> list[dict]:
    """Dispatch to the right chunker based on file_type. Mirrors the vanilla indexer."""
    if file_type == "rvmat":
        result = chunk_rvmat(path, seen_rvmat_hashes)
        return result or []
    if file_type == "xml":
        return chunk_xml(path, file_type)
    if file_type in WHOLE_FILE_TYPES:
        return chunk_whole_file(path, file_type)
    if file_type in CLASS_BLOCK_TYPES:
        return _block_chunks(path, file_type)
    return []


def _content_hash(chunk: dict) -> str:
    """Stable per-chunk hash. Same chunk content + path + parent_context => same hash."""
    h = hashlib.sha256()
    h.update(chunk.get("path", "").encode("utf-8", errors="replace"))
    h.update(b"\x00")
    h.update(chunk.get("parent_context", "").encode("utf-8", errors="replace"))
    h.update(b"\x00")
    h.update(str(chunk.get("line_start", 0)).encode("utf-8"))
    h.update(b":")
    h.update(str(chunk.get("line_end", 0)).encode("utf-8"))
    h.update(b"\x00")
    h.update((chunk.get("content", "") or "").encode("utf-8", errors="replace"))
    return h.hexdigest()


def _load_existing_hashes(table) -> dict[str, dict]:
    """Map chunk_hash -> existing row (with vector). Used to skip re-embedding."""
    if table is None:
        return {}
    try:
        rows = table.to_pandas().to_dict("records")
    except Exception:
        return {}
    return {r.get("chunk_hash", ""): r for r in rows if r.get("chunk_hash")}


def _print_summary(label: str, value):
    print(f"{INFO} {label}: {value}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mod_name", nargs="?", default=None,
                        help="One mod folder under workspace/ to index. Omit to index all mods.")
    parser.add_argument("--full", action="store_true",
                        help="Drop the existing workspace table and rebuild from scratch.")
    parser.add_argument("--status", action="store_true",
                        help="Print the workspace manifest and exit.")
    args = parser.parse_args()

    INDEX_ROOT.mkdir(parents=True, exist_ok=True)
    manifest_path = INDEX_ROOT / WORKSPACE_MANIFEST_NAME
    db_path = INDEX_ROOT / "lancedb"

    if args.status:
        if manifest_path.exists():
            print(manifest_path.read_text(encoding="utf-8"))
            return 0
        print(f"No workspace index. Run: python {_HERE.name}/index.py", file=sys.stderr)
        return 1

    print("DayZ workspace RAG indexer\n")

    mods = _list_mods(args.mod_name)
    if not mods:
        if args.mod_name:
            print(f"{FAIL} No mod folder at workspace/{args.mod_name}/", file=sys.stderr)
        else:
            print(f"{FAIL} No mods under workspace/. Scaffold one with /dayz-new-mod.", file=sys.stderr)
        return 1
    print(f"{OK} Mods to index: {', '.join(m.name for m in mods)}")

    _ensure_deps()
    api_key = _load_env_and_key()
    embed_model = os.environ.get("VOYAGE_MODEL", DEFAULT_EMBED_MODEL).strip() or DEFAULT_EMBED_MODEL
    print(f"{OK} VOYAGE_API_KEY loaded ({api_key[:6]}...{api_key[-4:]})")
    _print_summary("Index", INDEX_ROOT)
    _print_summary("Embedding model", f"{embed_model} ({EMBED_DIM}D, via Voyage cloud)")
    print()

    import lancedb
    from tqdm import tqdm

    # Walk + chunk every mod folder.
    chunks: list[dict] = []
    seen_rvmat: set[str] = set()
    counts_by_mod: dict[str, dict[str, dict[str, int]]] = {}

    for mod in mods:
        mod_counts: dict[str, dict[str, int]] = {}
        files = list(_walk_mod(mod))
        for f in tqdm(files, desc=f"  {mod.name}/", unit="f"):
            ft = EXT_TYPE_MAP[f.suffix.lower()]
            produced = _chunk_for_type(f, ft, seen_rvmat)
            for c in produced:
                c["mod_name"] = mod.name
            chunks.extend(produced)
            mod_counts.setdefault(ft, {"files": 0, "chunks": 0})
            mod_counts[ft]["files"] += 1
            mod_counts[ft]["chunks"] += len(produced)
        counts_by_mod[mod.name] = mod_counts
        if mod_counts:
            summary = ", ".join(
                f"{ft}={v['chunks']}c/{v['files']}f"
                for ft, v in sorted(mod_counts.items())
            )
            print(f"  {mod.name}/  {summary}")
        else:
            print(f"  {mod.name}/  (no indexed files)")

    if not chunks:
        print(f"\n{FAIL} No indexable content found under workspace/.", file=sys.stderr)
        return 1

    # Drop empties (Voyage 400s on empty input).
    chunks = [c for c in chunks if c.get("content", "").strip()]

    # Stamp every chunk with a content hash for incremental upsert.
    for c in chunks:
        c["chunk_hash"] = _content_hash(c)

    # Connect / open the table. If --full, drop and recreate. Otherwise upsert
    # by chunk_hash so unchanged chunks skip embedding.
    db = lancedb.connect(str(db_path))
    table = None
    existing_by_hash: dict[str, dict] = {}

    if WORKSPACE_TABLE_NAME in db.table_names():
        if args.full:
            print(f"{INFO} --full: dropping existing workspace table")
            db.drop_table(WORKSPACE_TABLE_NAME)
        else:
            table = db.open_table(WORKSPACE_TABLE_NAME)
            existing_by_hash = _load_existing_hashes(table)

    # Split chunks: those already embedded (reuse vector) vs need-to-embed.
    new_chunks: list[dict] = []
    reused_chunks: list[dict] = []
    for c in chunks:
        prior = existing_by_hash.get(c["chunk_hash"])
        if prior and prior.get("vector"):
            c["vector"] = prior["vector"]
            reused_chunks.append(c)
        else:
            new_chunks.append(c)

    print(f"\n{INFO} Chunks total: {len(chunks)}  "
          f"(reused {len(reused_chunks)}, new {len(new_chunks)})")

    total_tokens = 0
    cost_estimate_usd = 0.0
    cost_per_m = COST_PER_MTOKEN.get(embed_model, 0.18)

    if new_chunks:
        texts = [(c["content"] or " ")[:EMBED_MAX_CHARS] for c in new_chunks]
        print(f"Embedding {len(new_chunks)} new chunks via Voyage ({embed_model}, document mode)...")
        started = time.time()
        embeddings, total_tokens = _embed_all(texts, embed_model, api_key)
        elapsed = time.time() - started
        if len(embeddings) != len(new_chunks):
            print(f"\n{FAIL} Embedding count mismatch: {len(embeddings)} for {len(new_chunks)}",
                  file=sys.stderr)
            return 1
        for c, vec in zip(new_chunks, embeddings):
            c["vector"] = vec
        cost_estimate_usd = round((total_tokens / 1_000_000) * cost_per_m, 4)
        print(f"{OK} Embedded {len(new_chunks)} chunks in {elapsed:.1f}s  "
              f"({total_tokens:,} tok, ~${cost_estimate_usd:.4f})")
    else:
        print(f"{OK} Nothing new to embed — all chunks unchanged.")

    # Materialize: drop the table (if reusing existing rows we already have them
    # in our chunks list) and recreate with the full set. LanceDB's upsert API
    # is awkward for our schema; full-table-rewrite is simpler and the data is
    # tiny (workspace mods << vanilla).
    if WORKSPACE_TABLE_NAME in db.table_names():
        db.drop_table(WORKSPACE_TABLE_NAME)
    db.create_table(WORKSPACE_TABLE_NAME, data=chunks)

    manifest = {
        "indexed_at": int(time.time()),
        "indexed_at_iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "embed_model": embed_model,
        "embed_dim": EMBED_DIM,
        "embed_provider": "voyage",
        "workspace_root": str(WORKSPACE_DIR),
        "mods_indexed": [m.name for m in mods],
        "counts_by_mod": counts_by_mod,
        "total_chunks": len(chunks),
        "chunks_reused": len(reused_chunks),
        "chunks_newly_embedded": len(new_chunks),
        "tokens_used_this_run": total_tokens,
        "cost_estimate_usd_this_run": cost_estimate_usd,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"\n{OK} Workspace index ready: {len(chunks)} chunks across "
          f"{len(mods)} mod(s) at {INDEX_ROOT}")
    print(f"{INFO} Restart Claude Code so the dayz-rag MCP server picks up the new table.")
    print(f"{INFO} Then call: search_dayz_workspace(query, top_k=5, file_type=None, mod=None)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
