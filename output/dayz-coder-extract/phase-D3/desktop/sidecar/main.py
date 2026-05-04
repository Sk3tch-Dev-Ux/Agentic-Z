"""Agentic-Z desktop sidecar — D3.

D1: health, repo info, preflight, mods.
D2: SSE for watch-log + skill subprocess endpoints (build/launch/stop/new-mod) + run streams.
D3: SSE for director status + postmortem listing + reset endpoint.

The director-related routes live in director.py — kept separate so main.py
doesn't keep growing.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parents[1]
WORKSPACE_DIR = REPO_ROOT / "workspace"
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
PREFLIGHT_DIR = SKILLS_DIR / "dayz-preflight"
LOCAL_MEMORY = REPO_ROOT / ".claude" / "local-memory"
PORT_FILE = LOCAL_MEMORY / "agentic-z-desktop.port"
WATCH_LOG = LOCAL_MEMORY / "dayz-watch.log"

sys.path.insert(0, str(PREFLIGHT_DIR))
try:
    from preflight import find_dayz_tools, find_vanilla_data
    _PREFLIGHT_IMPORTED = True
except ImportError:
    find_dayz_tools = None
    find_vanilla_data = None
    _PREFLIGHT_IMPORTED = False

# D3: import director router
from director import make_router as make_director_router  # noqa: E402


# -------- pydantic schemas --------


class HealthResponse(BaseModel):
    status: str
    sidecar_started_at: float
    repo_root: str


class RepoInfoResponse(BaseModel):
    repo_root: str
    claude_dir: str
    workspace_dir: str
    has_dayz_preflight_skill: bool
    sidecar_version: str = "0.3.0"


class PreflightResponse(BaseModel):
    p_drive_mounted: bool
    dayz_tools_path: Optional[str]
    vanilla_data_path: Optional[str]
    workshop_junction_ok: bool
    overall_ok: bool
    errors: list[str]
    warnings: list[str]


class ModSummary(BaseModel):
    name: str
    path: str
    has_config_cpp: bool
    has_pboprefix: bool
    has_p_junction: bool
    last_modified: float


class ModListResponse(BaseModel):
    mods: list[ModSummary]


class NewModRequest(BaseModel):
    name: str
    author: Optional[str] = None


class StartRunResponse(BaseModel):
    run_id: str
    skill: str
    args: list[str]
    started_at: float


class ActiveRun(BaseModel):
    run_id: str
    mod_name: Optional[str]
    skill: str
    started_at: float
    pid: int


class ActiveRunsResponse(BaseModel):
    runs: list[ActiveRun]


# -------- app + lifecycle --------


app = FastAPI(
    title="Agentic-Z Desktop Sidecar",
    description="FastAPI backend for the Tauri-based desktop app.",
    version="0.3.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "tauri://localhost",
        "http://tauri.localhost",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
_started_at = time.time()

# D3: mount director routes
app.include_router(make_director_router(REPO_ROOT))


# -------- D1 endpoints --------


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", sidecar_started_at=_started_at, repo_root=str(REPO_ROOT))


@app.get("/api/repo/info", response_model=RepoInfoResponse)
def repo_info() -> RepoInfoResponse:
    return RepoInfoResponse(
        repo_root=str(REPO_ROOT),
        claude_dir=str(REPO_ROOT / ".claude"),
        workspace_dir=str(WORKSPACE_DIR),
        has_dayz_preflight_skill=_PREFLIGHT_IMPORTED,
    )


def _check_p_drive() -> bool: return Path("P:\\").exists()
def _check_workshop_junction() -> bool: return Path("P:\\Mods").exists()


@app.get("/api/preflight", response_model=PreflightResponse)
def preflight() -> PreflightResponse:
    errors: list[str] = []
    warnings: list[str] = []
    p_drive = _check_p_drive()
    if not p_drive:
        errors.append("P:\\ is not mounted. Run /dayz-mount-p or open DayZ Tools.")
    tools_path: Optional[str] = None
    if find_dayz_tools is not None:
        try:
            found = find_dayz_tools()
            if found: tools_path = str(found)
            else: warnings.append("DayZ Tools not detected on standard paths.")
        except Exception as e: warnings.append(f"DayZ Tools resolver raised: {e}")
    else: warnings.append("Preflight helpers not importable.")
    vanilla_path: Optional[str] = None
    if find_vanilla_data is not None:
        try:
            found = find_vanilla_data()
            if found: vanilla_path = str(found)
            else: warnings.append("Vanilla DayZ data not detected on P:\\.")
        except Exception as e: warnings.append(f"Vanilla data resolver raised: {e}")
    workshop_ok = _check_workshop_junction()
    if p_drive and not workshop_ok:
        warnings.append("P:\\Mods\\ junction missing.")
    return PreflightResponse(
        p_drive_mounted=p_drive, dayz_tools_path=tools_path, vanilla_data_path=vanilla_path,
        workshop_junction_ok=workshop_ok, overall_ok=p_drive and not errors,
        errors=errors, warnings=warnings,
    )


def _summarize_mod(path: Path) -> ModSummary:
    config_cpp = (path / "config.cpp").exists()
    pboprefix = (path / "$PBOPREFIX$").exists()
    p_junction = Path(f"P:\\{path.name}").exists()
    try: mtime = path.stat().st_mtime
    except OSError: mtime = 0.0
    return ModSummary(name=path.name, path=str(path),
                      has_config_cpp=config_cpp, has_pboprefix=pboprefix,
                      has_p_junction=p_junction, last_modified=mtime)


@app.get("/api/mods", response_model=ModListResponse)
def list_mods() -> ModListResponse:
    if not WORKSPACE_DIR.exists():
        return ModListResponse(mods=[])
    mods: list[ModSummary] = []
    for entry in sorted(WORKSPACE_DIR.iterdir()):
        if not entry.is_dir(): continue
        if entry.name.startswith("_") or entry.name.startswith("."): continue
        mods.append(_summarize_mod(entry))
    return ModListResponse(mods=mods)


# -------- D2 SSE: watch-log --------


def _format_sse(data: dict | str, event: Optional[str] = None) -> str:
    payload = json.dumps(data) if isinstance(data, dict) else str(data)
    msg = ""
    if event: msg += f"event: {event}\n"
    for line in payload.splitlines() or [""]: msg += f"data: {line}\n"
    msg += "\n"
    return msg


async def _tail_watch_log_async(request: Request, since_pos: int = 0):
    if WATCH_LOG.exists():
        try:
            with WATCH_LOG.open("r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            for line in lines[-100:]:
                line = line.strip()
                if not line: continue
                try: rec = json.loads(line)
                except Exception: continue
                rec["_replay"] = True
                yield _format_sse(rec)
            since_pos = WATCH_LOG.stat().st_size
        except OSError: pass
    yield _format_sse({"event": "replay_complete"}, event="control")
    last_heartbeat = time.time()
    while True:
        if await request.is_disconnected(): break
        try:
            if not WATCH_LOG.exists():
                if time.time() - last_heartbeat > 15:
                    yield _format_sse({"ts": time.time()}, event="heartbeat")
                    last_heartbeat = time.time()
                await asyncio.sleep(0.5); continue
            size = WATCH_LOG.stat().st_size
            if size < since_pos: since_pos = 0
            if size > since_pos:
                with WATCH_LOG.open("rb") as f:
                    f.seek(since_pos)
                    chunk = f.read(size - since_pos)
                since_pos = size
                text = chunk.decode("utf-8", errors="replace")
                for line in text.splitlines():
                    line = line.strip()
                    if not line: continue
                    try: rec = json.loads(line)
                    except Exception: continue
                    yield _format_sse(rec)
        except OSError: pass
        if time.time() - last_heartbeat > 15:
            yield _format_sse({"ts": time.time()}, event="heartbeat")
            last_heartbeat = time.time()
        await asyncio.sleep(0.5)


@app.get("/api/events/watch-log")
async def stream_watch_log(request: Request) -> StreamingResponse:
    return StreamingResponse(
        _tail_watch_log_async(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# -------- D2 subprocess management --------


class RunRecord:
    def __init__(self, mod_name: Optional[str], skill: str, cmd: list[str]):
        self.run_id = uuid.uuid4().hex[:12]
        self.mod_name = mod_name
        self.skill = skill
        self.cmd = cmd
        self.started_at = time.time()
        self.proc: Optional[asyncio.subprocess.Process] = None
        self.lines: list[dict] = []
        self.exit_code: Optional[int] = None
        self.subscribers: list[asyncio.Queue] = []

    @property
    def pid(self) -> int: return self.proc.pid if self.proc else 0

    @property
    def alive(self) -> bool: return self.proc is not None and self.exit_code is None

    def append(self, line: dict) -> None:
        self.lines.append(line)
        if len(self.lines) > 2000: self.lines = self.lines[-1000:]
        for q in list(self.subscribers):
            try: q.put_nowait(line)
            except asyncio.QueueFull: pass


_RUNS: dict[str, RunRecord] = {}
_ACTIVE_BY_KEY: dict[tuple[Optional[str], str], str] = {}


def _skill_python_args(skill_name: str, *args: str) -> list[str]:
    candidates = [
        SKILLS_DIR / skill_name / f"{skill_name.replace('dayz-', '').replace('-', '_')}.py",
        SKILLS_DIR / skill_name / "main.py",
    ]
    skill_dir = SKILLS_DIR / skill_name
    if skill_dir.exists():
        for p in skill_dir.glob("*.py"):
            if p not in candidates: candidates.append(p)
    for path in candidates:
        if path.exists():
            return [sys.executable, str(path), *args]
    raise FileNotFoundError(f"Skill script not found for {skill_name}")


async def _start_run(mod_name: Optional[str], skill: str, cmd: list[str]) -> RunRecord:
    key = (mod_name, skill)
    if key in _ACTIVE_BY_KEY:
        rid = _ACTIVE_BY_KEY[key]
        if rid in _RUNS and _RUNS[rid].alive:
            raise HTTPException(status_code=409,
                detail=f"{skill} already running for {mod_name or '<no mod>'} as run {rid}")
    rec = RunRecord(mod_name, skill, cmd)
    _RUNS[rec.run_id] = rec
    _ACTIVE_BY_KEY[key] = rec.run_id
    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=str(REPO_ROOT),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    rec.proc = proc

    async def reader():
        assert proc.stdout is not None
        while True:
            raw = await proc.stdout.readline()
            if not raw: break
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            rec.append({"ts": time.time(), "stream": "stdout", "line": line})
        rec.exit_code = await proc.wait()
        rec.append({"ts": time.time(), "stream": "exit",
                    "exit_code": rec.exit_code, "elapsed": time.time() - rec.started_at})
        for q in list(rec.subscribers):
            try: q.put_nowait({"stream": "_eof"})
            except asyncio.QueueFull: pass
        if _ACTIVE_BY_KEY.get(key) == rec.run_id:
            _ACTIVE_BY_KEY.pop(key, None)

    asyncio.create_task(reader())
    return rec


@app.post("/api/mods/new", response_model=StartRunResponse)
async def new_mod(req: NewModRequest) -> StartRunResponse:
    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="name is required")
    args = [req.name.strip()]
    if req.author: args += ["--author", req.author]
    cmd = _skill_python_args("dayz-new-mod", *args)
    rec = await _start_run(None, "dayz-new-mod", cmd)
    return StartRunResponse(run_id=rec.run_id, skill=rec.skill, args=args, started_at=rec.started_at)


@app.post("/api/mods/{mod_name}/build", response_model=StartRunResponse)
async def build_mod(mod_name: str, clean: bool = False) -> StartRunResponse:
    extra = ["--clean"] if clean else []
    cmd = _skill_python_args("dayz-build-pbo", mod_name, *extra)
    rec = await _start_run(mod_name, "dayz-build-pbo", cmd)
    return StartRunResponse(run_id=rec.run_id, skill=rec.skill,
                            args=[mod_name, *extra], started_at=rec.started_at)


@app.post("/api/mods/{mod_name}/launch", response_model=StartRunResponse)
async def launch_mod(mod_name: str, map_name: str = "chernarus") -> StartRunResponse:
    cmd = _skill_python_args("dayz-launch-test", mod_name, "--map", map_name)
    rec = await _start_run(mod_name, "dayz-launch-test", cmd)
    return StartRunResponse(run_id=rec.run_id, skill=rec.skill,
                            args=[mod_name, "--map", map_name], started_at=rec.started_at)


@app.post("/api/mods/{mod_name}/stop", response_model=StartRunResponse)
async def stop_diag(mod_name: str) -> StartRunResponse:
    cmd = _skill_python_args("dayz-stop-test")
    rec = await _start_run(mod_name, "dayz-stop-test", cmd)
    return StartRunResponse(run_id=rec.run_id, skill=rec.skill, args=[],
                            started_at=rec.started_at)


@app.get("/api/runs/active", response_model=ActiveRunsResponse)
def active_runs() -> ActiveRunsResponse:
    out = [ActiveRun(run_id=rid, mod_name=rec.mod_name, skill=rec.skill,
                     started_at=rec.started_at, pid=rec.pid)
           for rid, rec in _RUNS.items() if rec.alive]
    return ActiveRunsResponse(runs=out)


async def _run_stream(request: Request, run_id: str):
    rec = _RUNS.get(run_id)
    if rec is None:
        yield _format_sse({"error": "unknown run"}, event="error"); return
    for line in list(rec.lines): yield _format_sse(line)
    if rec.exit_code is not None: return
    queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
    rec.subscribers.append(queue)
    try:
        last_hb = time.time()
        while True:
            if await request.is_disconnected(): break
            try: line = await asyncio.wait_for(queue.get(), timeout=5.0)
            except asyncio.TimeoutError: line = None
            if line is None:
                if time.time() - last_hb > 15:
                    yield _format_sse({"ts": time.time()}, event="heartbeat")
                    last_hb = time.time()
                continue
            if line.get("stream") == "_eof": break
            yield _format_sse(line)
    finally:
        if queue in rec.subscribers: rec.subscribers.remove(queue)


@app.get("/api/runs/{run_id}/stream")
async def stream_run(request: Request, run_id: str) -> StreamingResponse:
    return StreamingResponse(_run_stream(request, run_id), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/runs/{run_id}/kill")
def kill_run(run_id: str) -> dict:
    rec = _RUNS.get(run_id)
    if rec is None or not rec.alive or rec.proc is None:
        raise HTTPException(status_code=404, detail="run not found or already exited")
    try:
        rec.proc.kill()
        return {"ok": True, "run_id": run_id}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


# -------- port discovery + entrypoint --------


def _is_port_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try: s.bind((host, port)); return True
        except OSError: return False


def _discover_port(start: int = 7321, attempts: int = 20) -> int:
    for offset in range(attempts):
        port = start + offset
        if _is_port_free(port): return port
    raise RuntimeError(f"No free port in range {start}-{start + attempts}")


def _write_port_file(port: int) -> None:
    LOCAL_MEMORY.mkdir(parents=True, exist_ok=True)
    PORT_FILE.write_text(json.dumps({"port": port, "pid_started_at": _started_at}),
                         encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    if args.port is not None:
        if not _is_port_free(args.port): print(f"port {args.port} taken", file=sys.stderr); return 1
        port = args.port
    else: port = _discover_port()
    _write_port_file(port)
    print(f"[sidecar] http://{args.host}:{port}")
    print(f"[sidecar] repo: {REPO_ROOT}")
    print(f"[sidecar] docs: http://{args.host}:{port}/docs")
    import uvicorn
    uvicorn.run("main:app", host=args.host, port=port, reload=args.reload, app_dir=str(_HERE))
    return 0


if __name__ == "__main__":
    sys.exit(main())
