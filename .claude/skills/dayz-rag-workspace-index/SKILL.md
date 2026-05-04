---
name: dayz-rag-workspace-index
description: Index your own mod source under `workspace/<ModName>/` into the dayz-rag LanceDB so the `search_dayz_workspace` MCP tool can answer "how does MY mod do X" with file:line citations. Idempotent — re-running upserts by chunk hash, so unchanged chunks skip the Voyage call.
---

# /dayz-rag-workspace-index

Indexes mod source under `workspace/<ModName>/` into the same LanceDB that backs the vanilla and wiki indexes. After this runs, `dayz-coder` (and any other agent) can call the `search_dayz_workspace` MCP tool to do semantic search over your own code with the same recall quality it has for vanilla.

Three corpora, three indexers — keeps each focused and incremental:

| Corpus | Skill | LanceDB table | Manifest |
|---|---|---|---|
| Vanilla DayZ source on `P:\` | `/dayz-rag-index` | `chunks` | `manifest.json` |
| Bohemia community wiki | `/dayz-rag-wiki-index` | `wiki_chunks` | `wiki-manifest.json` |
| **Your `workspace/<ModName>/`** | **`/dayz-rag-workspace-index`** | **`workspace_chunks`** | **`workspace-manifest.json`** |

Follow `.claude/skills/_shared/dayz-conventions.md`.

## What it does

1. Walk `workspace/<ModName>/` (or every mod under `workspace/` if no name).
2. Skip ignore dirs (`.git`, `__pycache__`, `.venv`, `node_modules`, `_server/`, …) and binary suffixes (`.p3d`, `.paa`, `.png`, `.tga`, `.pbo`, `.bisign`, …).
3. Chunk by file type using the same chunkers the vanilla indexer uses (`_block_chunks` for `.c`/`.cpp`/`.layout`/`.cfg`, `chunk_xml` for `types.xml` etc., `chunk_whole_file` for `.json`/`.csv`).
4. Compute a content hash per chunk. If the hash already exists in the workspace table, reuse the prior vector (no Voyage call). Only newly-changed chunks get embedded.
5. Re-write the workspace table with the full chunk set (existing + new).
6. Save a manifest at `~/.claude/dayz-rag-index/workspace-manifest.json` with per-mod counts and embed cost.

The chunker reuse means workspace chunks have the exact same shape as vanilla chunks — `path`, `file_type`, `parent_context`, `line_start`, `line_end`, `content` — plus a `mod_name` field so the search tool can filter by mod.

## How to run

```cmd
:: All mods under workspace/
python .claude\skills\dayz-rag-workspace-index\index.py

:: One specific mod
python .claude\skills\dayz-rag-workspace-index\index.py MyMod

:: Show manifest
python .claude\skills\dayz-rag-workspace-index\index.py --status

:: Drop the table and rebuild from scratch (rare — only after major refactors)
python .claude\skills\dayz-rag-workspace-index\index.py --full
```

## When to run

- **First time** after cloning Agentic-Z and scaffolding your first mod.
- **After significant edits** — re-run any time. The hash-skip means it's almost free if nothing changed.
- **As part of `/dayz-watch`** (Phase 2 of Live Mode, future) — the watcher will call this on every save with debouncing.

## Cost

Voyage `voyage-code-3` at $0.18/M tokens. A typical workspace mod is small (~hundreds to low thousands of chunks). Re-runs after small edits cost cents because most chunks reuse their existing vector. Initial bulk index of a fresh scaffold is usually well under $0.01.

If you want to confirm before embedding, run `--status` first — it prints the most recent run's chunk count and token usage so you can extrapolate.

## After it runs

Restart Claude Code so the `dayz-rag` MCP server picks up the new table. Then your agents can call:

```python
search_dayz_workspace(
    query="how does MyMod_TacticalVest hide the camo selection",
    top_k=5,
    file_type="cpp",     # optional: c | cpp | hpp | h | layout | cfg | xml | json | csv
    mod="MyMod",         # optional: scope to one mod
)
```

Returns chunks with `path` / `mod_name` / `parent_context` / `line_start` / `line_end` / `score` / `snippet`.

## Output (example)

```
DayZ workspace RAG indexer

[OK]    Mods to index: MyMod, MilitaryGear
[OK]    VOYAGE_API_KEY loaded (pa-1a2...wxyz)
[INFO]  Index: C:\Users\you\.claude\dayz-rag-index
[INFO]  Embedding model: voyage-code-3 (1024D, via Voyage cloud)

  MyMod/         c=42c/12f, cpp=8c/1f, layout=4c/3f
  MilitaryGear/  c=14c/5f, cpp=3c/1f, xml=2c/1f

[INFO]  Chunks total: 73  (reused 65, new 8)
Embedding 8 new chunks via Voyage (voyage-code-3, document mode)...
[OK]    Embedded 8 chunks in 1.4s  (4,210 tok, ~$0.0008)

[OK]    Workspace index ready: 73 chunks across 2 mod(s) at C:\Users\you\.claude\dayz-rag-index
[INFO]  Restart Claude Code so the dayz-rag MCP server picks up the new table.
[INFO]  Then call: search_dayz_workspace(query, top_k=5, file_type=None, mod=None)
```

## Do not

- Don't index `workspace/_server/` — that's mission/server staging, not your mod source. The walker excludes it explicitly.
- Don't commit `~/.claude/dayz-rag-index/` to git — it's per-user runtime cache.
- Don't run this on a fresh clone before scaffolding a mod. The skill hard-fails if `workspace/` has no mod folders.
