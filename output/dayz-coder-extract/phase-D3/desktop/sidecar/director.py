"""Director status + postmortem endpoints for the desktop sidecar.

Imported by main.py. Adds:
  GET  /api/events/director       — SSE tail of dayz-director-status.json
  GET  /api/director/runs         — list postmortem markdown files
  GET  /api/director/runs/{name}  — fetch one postmortem
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


def make_router(repo_root: Path) -> APIRouter:
    router = APIRouter()

    STATUS_FILE = repo_root / ".claude" / "local-memory" / "dayz-director-status.json"
    POSTMORTEM_DIR = repo_root / ".claude" / "agent-memory" / "dayz-director" / "runs"

    # ---- schemas ----

    class PostmortemSummary(BaseModel):
        name: str
        path: str
        modified_at: float
        size_bytes: int
        first_line: str

    class PostmortemListResponse(BaseModel):
        runs: list[PostmortemSummary]

    class PostmortemDetail(BaseModel):
        name: str
        path: str
        content: str

    # ---- helpers ----

    def _format_sse(data: dict | str, event: Optional[str] = None) -> str:
        payload = json.dumps(data) if isinstance(data, dict) else str(data)
        msg = ""
        if event:
            msg += f"event: {event}\n"
        for line in payload.splitlines() or [""]:
            msg += f"data: {line}\n"
        msg += "\n"
        return msg

    def _read_status() -> Optional[dict]:
        if not STATUS_FILE.exists():
            return None
        try:
            return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    # ---- /api/events/director ----

    async def _tail_status(request: Request):
        last_mtime = 0.0
        last_payload: Optional[str] = None

        # Initial snapshot
        if STATUS_FILE.exists():
            try:
                last_mtime = STATUS_FILE.stat().st_mtime
            except OSError:
                last_mtime = 0.0
            cur = _read_status()
            if cur is not None:
                last_payload = json.dumps(cur, sort_keys=True)
                yield _format_sse(cur)
            else:
                yield _format_sse({"_empty": True}, event="control")
        else:
            yield _format_sse({"_empty": True}, event="control")

        last_hb = time.time()
        while True:
            if await request.is_disconnected():
                break

            try:
                if STATUS_FILE.exists():
                    mtime = STATUS_FILE.stat().st_mtime
                    if mtime != last_mtime:
                        cur = _read_status()
                        if cur is not None:
                            payload = json.dumps(cur, sort_keys=True)
                            if payload != last_payload:
                                yield _format_sse(cur)
                                last_payload = payload
                        last_mtime = mtime
                else:
                    if last_payload is not None:
                        # File was deleted (reset). Emit empty marker.
                        yield _format_sse({"_empty": True}, event="control")
                        last_payload = None
                        last_mtime = 0.0
            except OSError:
                pass

            if time.time() - last_hb > 15:
                yield _format_sse({"ts": time.time()}, event="heartbeat")
                last_hb = time.time()
            await asyncio.sleep(0.5)

    @router.get("/api/events/director")
    async def stream_director(request: Request) -> StreamingResponse:
        return StreamingResponse(
            _tail_status(request),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ---- /api/director/runs (list) ----

    @router.get("/api/director/runs", response_model=PostmortemListResponse)
    def list_runs() -> PostmortemListResponse:
        if not POSTMORTEM_DIR.exists():
            return PostmortemListResponse(runs=[])
        runs: list[PostmortemSummary] = []
        for p in sorted(POSTMORTEM_DIR.glob("*.md"), reverse=True):
            try:
                stat = p.stat()
            except OSError:
                continue
            first_line = ""
            try:
                with p.open("r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            first_line = line[:200]
                            break
            except OSError:
                pass
            runs.append(PostmortemSummary(
                name=p.stem,
                path=str(p),
                modified_at=stat.st_mtime,
                size_bytes=stat.st_size,
                first_line=first_line,
            ))
        return PostmortemListResponse(runs=runs)

    # ---- /api/director/runs/{name} (detail) ----

    @router.get("/api/director/runs/{name}", response_model=PostmortemDetail)
    def get_run(name: str) -> PostmortemDetail:
        # Refuse path traversal: name must not contain separators
        if "/" in name or "\\" in name or ".." in name:
            raise HTTPException(status_code=400, detail="invalid name")
        path = POSTMORTEM_DIR / f"{name}.md"
        if not path.exists():
            raise HTTPException(status_code=404, detail="postmortem not found")
        if path.resolve().parent != POSTMORTEM_DIR.resolve():
            raise HTTPException(status_code=400, detail="invalid path")
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            raise HTTPException(status_code=500, detail=str(e))
        return PostmortemDetail(name=name, path=str(path), content=content)

    # ---- POST /api/director/reset (clear stale status) ----

    @router.post("/api/director/reset")
    def reset_status() -> dict:
        if STATUS_FILE.exists():
            STATUS_FILE.unlink()
        return {"ok": True}

    return router
