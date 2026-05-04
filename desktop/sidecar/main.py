"""Agentic-Z desktop sidecar — FastAPI backend for the Tauri shell.

Exposes the existing CLI skills as HTTP endpoints. Long-lived process: imports
the skill modules once at startup, holds caches, streams events.

D1 endpoints (this file):
  - GET  /api/health         — sidecar self-check (always 200)
  - GET  /api/repo/info      — repo root, .claude path, version
  - GET  /api/preflight      — runs `/dayz-preflight`, returns structured result
  - GET  /api/mods           — lists workspace/<ModName>/ folders

D2-D5 endpoints will be added in those phases. The shape stays the same: each
HTTP path wraps an existing skill or memory file, returning JSON.

Port discovery: tries 7321; if taken, 7322, 7323, ... up to 7340. Writes the
chosen port to `<repo>/.claude/local-memory/agentic-z-desktop.port` so the
Tauri shell knows where to connect.

Run:
  python desktop/sidecar/main.py                  # default
  python desktop/sidecar/main.py --port 8080      # explicit port
  python desktop/sidecar/main.py --reload         # dev mode (uvicorn auto-reload)
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Resolve the repo root from this file's location:
#   <repo>/desktop/sidecar/main.py
# parents[0] = sidecar, [1] = desktop, [2] = repo root
_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parents[1]
WORKSPACE_DIR = REPO_ROOT / "workspace"
PREFLIGHT_DIR = REPO_ROOT / ".claude" / "skills" / "dayz-preflight"
LOCAL_MEMORY = REPO_ROOT / ".claude" / "local-memory"
PORT_FILE = LOCAL_MEMORY / "agentic-z-desktop.port"

# Make the existing preflight helpers importable without invoking them via
# subprocess. This keeps preflight latency in the millisecond range.
sys.path.insert(0, str(PREFLIGHT_DIR))
try:
    from preflight import (  # noqa: E402
        find_dayz_tools,
        find_vanilla_data,
    )
    _PREFLIGHT_IMPORTED = True
except ImportError:
    find_dayz_tools = None  # type: ignore[assignment]
    find_vanilla_data = None  # type: ignore[assignment]
    _PREFLIGHT_IMPORTED = False


# ---------- pydantic schemas ------------------------------------------------


class HealthResponse(BaseModel):
    status: str
    sidecar_started_at: float
    repo_root: str


class RepoInfoResponse(BaseModel):
    repo_root: str
    claude_dir: str
    workspace_dir: str
    has_dayz_preflight_skill: bool
    sidecar_version: str = "0.1.0"


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


# ---------- app + lifecycle -------------------------------------------------


app = FastAPI(
    title="Agentic-Z Desktop Sidecar",
    description="FastAPI backend for the Tauri-based desktop app.",
    version="0.1.0",
)

# Tauri serves the WebView from a local origin; allow it.
# In dev mode Vite runs on http://localhost:5173. Production WebView origin is
# tauri://localhost. Both whitelisted.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "tauri://localhost",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_started_at = time.time()


# ---------- /api/health -----------------------------------------------------


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Sidecar self-check. Always 200 if the process is alive."""
    return HealthResponse(
        status="ok",
        sidecar_started_at=_started_at,
        repo_root=str(REPO_ROOT),
    )


# ---------- /api/repo/info --------------------------------------------------


@app.get("/api/repo/info", response_model=RepoInfoResponse)
def repo_info() -> RepoInfoResponse:
    """Repo root, .claude path, sidecar version. Used by the frontend to
    confirm it's wired to the expected workspace."""
    return RepoInfoResponse(
        repo_root=str(REPO_ROOT),
        claude_dir=str(REPO_ROOT / ".claude"),
        workspace_dir=str(WORKSPACE_DIR),
        has_dayz_preflight_skill=_PREFLIGHT_IMPORTED,
    )


# ---------- /api/preflight --------------------------------------------------


def _check_p_drive() -> bool:
    return Path("P:\\").exists()


def _check_workshop_junction() -> bool:
    """`P:\\Mods\\` should be a directory junction to `<DayZ install>\\!Workshop\\`.
    Best-effort: if `P:\\Mods` exists at all, treat as OK at this layer; the
    full strict check lives in dayz-preflight/preflight.py. We just want a
    binary signal for the dashboard."""
    return Path("P:\\Mods").exists()


@app.get("/api/preflight", response_model=PreflightResponse)
def preflight() -> PreflightResponse:
    """Run preflight checks and return structured result.

    Reuses helpers exported by `.claude/skills/dayz-preflight/preflight.py` —
    same source of truth the CLI skills use.
    """
    errors: list[str] = []
    warnings: list[str] = []

    p_drive = _check_p_drive()
    if not p_drive:
        errors.append("P:\\ is not mounted. Run /dayz-mount-p or open DayZ Tools.")

    tools_path: Optional[str] = None
    if find_dayz_tools is not None:
        try:
            found = find_dayz_tools()
            if found:
                tools_path = str(found)
            else:
                warnings.append(
                    "DayZ Tools not detected on standard paths. "
                    "Set DAYZ_TOOLS_PATH or install via Steam → Tools."
                )
        except Exception as e:  # don't let a helper error 500 the API
            warnings.append(f"DayZ Tools resolver raised: {e}")
    else:
        warnings.append(
            "Preflight helpers not importable (.claude/skills/dayz-preflight/ "
            "missing). Sidecar will return partial results."
        )

    vanilla_path: Optional[str] = None
    if find_vanilla_data is not None:
        try:
            found = find_vanilla_data()
            if found:
                vanilla_path = str(found)
            else:
                warnings.append(
                    "Vanilla DayZ data not detected on P:\\. "
                    "Run DayZ Tools → Extract Game Data."
                )
        except Exception as e:
            warnings.append(f"Vanilla data resolver raised: {e}")

    workshop_ok = _check_workshop_junction()
    if p_drive and not workshop_ok:
        warnings.append(
            "P:\\Mods\\ junction missing. Builds will deploy to a folder the "
            "engine doesn't read from."
        )

    overall_ok = p_drive and not errors

    return PreflightResponse(
        p_drive_mounted=p_drive,
        dayz_tools_path=tools_path,
        vanilla_data_path=vanilla_path,
        workshop_junction_ok=workshop_ok,
        overall_ok=overall_ok,
        errors=errors,
        warnings=warnings,
    )


# ---------- /api/mods -------------------------------------------------------


def _summarize_mod(path: Path) -> ModSummary:
    config_cpp = (path / "config.cpp").exists()
    pboprefix = (path / "$PBOPREFIX$").exists()
    p_junction = Path(f"P:\\{path.name}").exists()
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    return ModSummary(
        name=path.name,
        path=str(path),
        has_config_cpp=config_cpp,
        has_pboprefix=pboprefix,
        has_p_junction=p_junction,
        last_modified=mtime,
    )


@app.get("/api/mods", response_model=ModListResponse)
def list_mods() -> ModListResponse:
    """List mod folders under workspace/. Excludes `_server/` and other
    leading-underscore directories (per L2 conventions, those are server
    staging, not mod source)."""
    if not WORKSPACE_DIR.exists():
        return ModListResponse(mods=[])
    mods: list[ModSummary] = []
    for entry in sorted(WORKSPACE_DIR.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith("_") or entry.name.startswith("."):
            continue
        mods.append(_summarize_mod(entry))
    return ModListResponse(mods=mods)


# ---------- port discovery + entrypoint ------------------------------------


def _is_port_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def _discover_port(start: int = 7321, attempts: int = 20) -> int:
    """Find the first free port in [start, start+attempts)."""
    for offset in range(attempts):
        port = start + offset
        if _is_port_free(port):
            return port
    raise RuntimeError(f"No free port in range {start}-{start + attempts}")


def _write_port_file(port: int) -> None:
    """Tell the Tauri shell which port to connect to."""
    LOCAL_MEMORY.mkdir(parents=True, exist_ok=True)
    PORT_FILE.write_text(json.dumps({"port": port, "pid_started_at": _started_at}),
                         encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=None,
                        help="Explicit port (overrides discovery). Default: auto-discover from 7321.")
    parser.add_argument("--reload", action="store_true",
                        help="uvicorn auto-reload for dev. Off in production.")
    parser.add_argument("--host", default="127.0.0.1",
                        help="Bind host (default 127.0.0.1, localhost-only).")
    args = parser.parse_args()

    if args.port is not None:
        if not _is_port_free(args.port):
            print(f"port {args.port} is taken", file=sys.stderr)
            return 1
        port = args.port
    else:
        port = _discover_port()

    _write_port_file(port)
    print(f"[sidecar] starting on http://{args.host}:{port}")
    print(f"[sidecar] repo root: {REPO_ROOT}")
    print(f"[sidecar] port file: {PORT_FILE}")
    print(f"[sidecar] OpenAPI docs: http://{args.host}:{port}/docs")

    import uvicorn
    uvicorn.run(
        "main:app",
        host=args.host,
        port=port,
        reload=args.reload,
        app_dir=str(_HERE),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
