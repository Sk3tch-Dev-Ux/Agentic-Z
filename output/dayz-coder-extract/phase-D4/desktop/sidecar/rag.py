"""RAG endpoints for the desktop sidecar.

Imported by main.py. Wraps the existing dayz-rag MCP server's impl functions
directly (no subprocess) so a search round-trip is dominated by Voyage
embedding latency, not Python startup.

Endpoints:
  GET  /api/rag/search       — search one or all 3 corpora
  GET  /api/rag/file         — fetch a file slice (P:\\ vanilla or repo workspace)
  GET  /api/rag/manifests    — index manifests + chunk counts
  POST /api/rag/open         — open a file in the OS-default editor
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


def make_router(repo_root: Path) -> APIRouter:
    router = APIRouter()

    # Make the dayz-rag server module importable. The MCP server file is at
    # .claude/mcp/dayz-rag/server.py and exposes the same impl functions the
    # MCP tools wrap — we just call them directly.
    rag_dir = repo_root / ".claude" / "mcp" / "dayz-rag"
    sys.path.insert(0, str(rag_dir))
    try:
        import server as rag_server  # type: ignore[import-not-found]
        _RAG_AVAILABLE = True
    except Exception:
        rag_server = None  # type: ignore[assignment]
        _RAG_AVAILABLE = False

    # ---- schemas ----

    class SearchHit(BaseModel):
        path: str
        file_type: str
        parent_context: str
        line_start: int
        line_end: int
        score: float
        snippet: str
        corpus: str  # "vanilla" | "workspace" | "wiki"
        mod_name: Optional[str] = None  # populated for workspace hits

    class SearchResponse(BaseModel):
        hits: list[SearchHit]
        corpora_queried: list[str]
        rag_available: bool
        error: Optional[str] = None

    class FileSliceResponse(BaseModel):
        path: str
        line_start: int
        line_end: int
        content: str
        error: Optional[str] = None

    class ManifestSummary(BaseModel):
        total_chunks: int
        embed_model: Optional[str]
        indexed_at_iso: Optional[str]

    class ManifestsResponse(BaseModel):
        rag_available: bool
        vanilla: Optional[ManifestSummary] = None
        wiki: Optional[ManifestSummary] = None
        workspace: Optional[ManifestSummary] = None
        total_chunks: int = 0
        error: Optional[str] = None

    # ---- /api/rag/manifests ----

    INDEX_ROOT = Path.home() / ".claude" / "dayz-rag-index"

    def _summarize_manifest(name: str) -> Optional[ManifestSummary]:
        path = INDEX_ROOT / name
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        return ManifestSummary(
            total_chunks=int(data.get("total_chunks", 0) or 0),
            embed_model=data.get("embed_model"),
            indexed_at_iso=data.get("indexed_at_iso"),
        )

    @router.get("/api/rag/manifests", response_model=ManifestsResponse)
    def manifests() -> ManifestsResponse:
        if not _RAG_AVAILABLE:
            return ManifestsResponse(
                rag_available=False,
                error="dayz-rag MCP server not importable. Check .claude/mcp/dayz-rag/.",
            )
        v = _summarize_manifest("manifest.json")
        w = _summarize_manifest("wiki-manifest.json")
        ws = _summarize_manifest("workspace-manifest.json")
        total = (v.total_chunks if v else 0) + (w.total_chunks if w else 0) + (ws.total_chunks if ws else 0)
        return ManifestsResponse(
            rag_available=True, vanilla=v, wiki=w, workspace=ws, total_chunks=total,
        )

    # ---- /api/rag/search ----

    def _wrap_hit(rec: dict, corpus: str) -> SearchHit:
        return SearchHit(
            path=rec.get("path", ""),
            file_type=rec.get("file_type", ""),
            parent_context=rec.get("parent_context", ""),
            line_start=int(rec.get("line_start", 0) or 0),
            line_end=int(rec.get("line_end", 0) or 0),
            score=float(rec.get("score", 0.0) or 0.0),
            snippet=rec.get("snippet", ""),
            corpus=corpus,
            mod_name=rec.get("mod_name"),
        )

    async def _run_corpus(corpus: str, query: str, top_k: int,
                          file_type: Optional[str], mod: Optional[str]) -> list[SearchHit]:
        if not _RAG_AVAILABLE:
            return []
        loop = asyncio.get_event_loop()
        try:
            if corpus == "vanilla":
                rows = await loop.run_in_executor(
                    None, rag_server.search_dayz_source_impl, query, top_k, file_type
                )
                return [_wrap_hit(r, "vanilla") for r in rows]
            if corpus == "wiki":
                rows = await loop.run_in_executor(
                    None, rag_server.search_dayz_wiki_impl, query, top_k
                )
                return [_wrap_hit(r, "wiki") for r in rows]
            if corpus == "workspace":
                # Newer impl signature: (query, top_k, file_type, mod)
                if hasattr(rag_server, "search_dayz_workspace_impl"):
                    rows = await loop.run_in_executor(
                        None, rag_server.search_dayz_workspace_impl,
                        query, top_k, file_type, mod
                    )
                    return [_wrap_hit(r, "workspace") for r in rows]
                return []
        except Exception as e:
            # Surface the error per-corpus rather than 500 the whole search.
            return [SearchHit(
                path=f"<{corpus} error>", file_type="", parent_context=str(e)[:200],
                line_start=0, line_end=0, score=0.0, snippet="", corpus=corpus,
            )]
        return []

    @router.get("/api/rag/search", response_model=SearchResponse)
    async def search(
        q: str,
        corpus: str = "all",
        top_k: int = 5,
        file_type: Optional[str] = None,
        mod: Optional[str] = None,
    ) -> SearchResponse:
        if not q or not q.strip():
            return SearchResponse(hits=[], corpora_queried=[], rag_available=_RAG_AVAILABLE)
        if not _RAG_AVAILABLE:
            return SearchResponse(
                hits=[], corpora_queried=[], rag_available=False,
                error="dayz-rag MCP server not importable — run /dayz-rag-download "
                      "or /dayz-rag-index first."
            )

        targets: list[str]
        if corpus == "all":
            targets = ["vanilla", "wiki", "workspace"]
        elif corpus in ("vanilla", "wiki", "workspace"):
            targets = [corpus]
        else:
            raise HTTPException(status_code=400, detail=f"unknown corpus: {corpus}")

        # Run all corpora in parallel.
        results = await asyncio.gather(
            *[_run_corpus(c, q, top_k, file_type, mod) for c in targets],
            return_exceptions=False,
        )
        all_hits: list[SearchHit] = []
        for hits in results:
            all_hits.extend(hits)
        # Sort by score (LanceDB returns smaller=closer for cosine distance,
        # but the wrapper's score field is whatever lancedb _distance was — keep it).
        all_hits.sort(key=lambda h: h.score)
        # When merging across corpora, cap the total at top_k * num_corpora.
        all_hits = all_hits[: top_k * len(targets)]
        return SearchResponse(hits=all_hits, corpora_queried=targets, rag_available=True)

    # ---- /api/rag/file ----

    def _resolve_safe_path(path: str) -> Optional[Path]:
        """Allow paths under P:\\ (vanilla) or under repo_root (workspace).
        Reject anything else."""
        try:
            p = Path(path).resolve()
        except OSError:
            return None
        # P:\ check
        try:
            if p.drive.upper() == "P:":
                return p
        except AttributeError:
            pass
        # repo_root check
        try:
            p.relative_to(repo_root.resolve())
            return p
        except ValueError:
            return None

    @router.get("/api/rag/file", response_model=FileSliceResponse)
    def file_slice(path: str, line_start: int = 1, line_end: int = 0) -> FileSliceResponse:
        safe = _resolve_safe_path(path)
        if safe is None:
            raise HTTPException(status_code=400, detail="path not under P:\\ or repo root")
        if not safe.exists() or not safe.is_file():
            raise HTTPException(status_code=404, detail="not a file")
        try:
            text = safe.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            raise HTTPException(status_code=500, detail=str(e))
        lines = text.splitlines()
        s = max(1, int(line_start))
        e = min(len(lines), int(line_end) if line_end else len(lines))
        slice_text = "\n".join(lines[s - 1: e])
        return FileSliceResponse(path=str(safe), line_start=s, line_end=e, content=slice_text)

    # ---- POST /api/rag/open ----

    @router.post("/api/rag/open")
    def open_in_editor(path: str, line: int = 1) -> dict:
        """Best-effort open in the user's preferred editor. Tries `code` first
        (VS Code with --goto), falls back to OS default handler."""
        safe = _resolve_safe_path(path)
        if safe is None:
            raise HTTPException(status_code=400, detail="path not under P:\\ or repo root")
        # Try VS Code with goto
        for cmd in (["code", "--goto", f"{safe}:{line}"], None):
            if cmd is None:
                # OS default
                try:
                    if os.name == "nt":
                        os.startfile(str(safe))  # type: ignore[attr-defined]
                    elif sys.platform == "darwin":
                        subprocess.Popen(["open", str(safe)])
                    else:
                        subprocess.Popen(["xdg-open", str(safe)])
                    return {"ok": True, "method": "os-default"}
                except Exception as e:
                    raise HTTPException(status_code=500, detail=str(e))
            try:
                # CREATE_NO_WINDOW on Windows so we don't flash a console.
                if os.name == "nt":
                    subprocess.Popen(cmd, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                else:
                    subprocess.Popen(cmd)
                return {"ok": True, "method": "vscode"}
            except FileNotFoundError:
                continue
        return {"ok": False}

    return router
